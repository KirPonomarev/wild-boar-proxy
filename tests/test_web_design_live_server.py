# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import http.client
import json
import os
import re
import socket
import sqlite3
import subprocess
import threading
import tempfile
import time
import unittest
import urllib.parse
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from wild_boar_proxy.model_availability import (
    build_catalog_availability_lattice_packet,
    build_model_direct_preflight_packet,
)
from wild_boar_proxy.runtime import RuntimePaths, run_installer_init
from wild_boar_proxy.ui_shell import CommandResult
import wild_boar_proxy.web_design_live_server as live_server


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    (path / "README.md").write_text("safe worktree test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
from wild_boar_proxy.web_design_command_adapter import ALLOWLIST
from wild_boar_proxy.web_design_live_server import (
    ACCOUNTS_READONLY_COMMAND_IDS,
    API_CONNECTIONS_READONLY_COMMAND_IDS,
    FULL_ACTION_PHASE,
    LIVE_READONLY_ACTION_PHASE,
    LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
    LIVE_READONLY_ACTION_DISABLED_REASONS,
    PARKED_IN_LIVE_READONLY_ACTIONS,
    READONLY_COMMAND_IDS,
    SANDBOX_ACTION_PHASE,
    LaunchCopyContract,
    build_api_connections_readonly_snapshot,
    build_accounts_readonly_snapshot,
    build_handler,
    build_live_readonly_snapshot,
    run_ui_action,
    ui_action_metadata,
    _sandbox_action_runner_env,
)
from wild_boar_proxy.web_rate_limit import WEB_RATE_LIMIT_MACHINE_ERROR_CODE, WebPostRateLimiter
from wild_boar_proxy.web_route_table import (
    CANONICAL_ROUTE_EFFECTS,
    EFFECT_MUTATE,
    EFFECT_READ,
    EFFECT_REPAIR,
    EFFECT_SOURCE_UI_ACTION_REGISTRY,
    WebRouteTable,
)
from wild_boar_proxy.web_token import (
    WEB_AUTH_HEADER,
    WEB_CSRF_HEADER,
    WEB_CSRF_META_NAME,
    WEB_TOKEN_FILENAME,
    WEB_TOKEN_META_NAME,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TEST_LAUNCH_CLIENT_PATH = "/bin/sh"
TEST_SANDBOX_LOGIN_SESSION_ID = "sandbox-test-session"
TEST_SANDBOX_LOGIN_STATE = "sandbox-state-test"
TEST_SANDBOX_AUTH_REF = "/tmp/wbp-sandbox-auth.json"
TEST_CODEX_LOGIN_SESSION_ID = "codex-test-session"
TEST_CODEX_DEVICE_URL = "https://auth.openai.com/codex/device"
TEST_CODEX_DEVICE_CODE = "WBP-1234"
REAL_CODEX_CUSTOM_SESSION_MANAGER = live_server.CodexCustomSessionManager


class StableProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "gpt-5.4"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/responses":
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length)
            body = json.dumps({"output_text": "OK"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def launch_copy_contract(*, action_server_port: int | None = None) -> LaunchCopyContract:
    copy_port = 9321 if action_server_port != 9321 else 9322
    return LaunchCopyContract(
        client_path=TEST_LAUNCH_CLIENT_PATH,
        profile_dir="/tmp/wbp-copy-profile",
        data_dir="/tmp/wbp-copy-data",
        copy_port=copy_port,
        action_server_port=action_server_port,
    )


def command_packet(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Command completed.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
    }
    payload.update(overrides)
    return payload


def healthcheck_ok_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Healthcheck passed.",
        effect="probe",
        attestation={
            "listener_ok": True,
            "models_ok": True,
            "responses_ok": True,
            "effective_mode_match": True,
            "base_url_match": True,
            "selected_backends_digest": "test-backends-digest",
            "observed_at_utc": "2026-01-01T00:00:00Z",
            "runtime_version": "test-runtime",
            "attestation_source": "healthcheck --json",
        },
    )
    payload.update(overrides)
    return payload


def credential_status_packet(
    *,
    present: bool = True,
    provider: str = "openrouter",
    credential_ref: str = "OPENROUTER_API_KEY",
    expected_refs: list[str] | None = None,
    provider_dashboard_url: str = "https://openrouter.ai/settings/keys",
) -> dict[str, object]:
    refs = (
        expected_refs
        if expected_refs is not None
        else [
            "OPENROUTER_API_KEY",
            "WBP_OPENROUTER_API_KEY",
            "WBP_PROVIDER_OPENROUTER_API_KEY",
        ]
    )
    return command_packet(
        human_message="External-models credential status collected from sandbox owner paths.",
        data={
            "credential_result": {
                "status": "present" if present else "missing",
                "provider": provider,
                "source": "sandbox-managed",
                "credential_ref": credential_ref,
                "credential_present": present,
                "supported_sources": ["owner-env"],
                "expected_refs": refs,
                "provider_dashboard_url": provider_dashboard_url,
                "secret_value_exposed": False,
                "browser_secret_intake": False,
                "browser_path_intake": False,
                "scope": "sandbox",
            }
        },
    )


def credential_admit_packet(
    *,
    provider: str = "openrouter",
    credential_ref: str = "OPENROUTER_API_KEY",
    expected_refs: list[str] | None = None,
    provider_dashboard_url: str = "https://openrouter.ai/settings/keys",
) -> dict[str, object]:
    refs = (
        expected_refs
        if expected_refs is not None
        else [
            "OPENROUTER_API_KEY",
            "WBP_OPENROUTER_API_KEY",
            "WBP_PROVIDER_OPENROUTER_API_KEY",
        ]
    )
    return command_packet(
        human_message="External-models credential admitted from owner source.",
        next_action="api_route_connect",
        changed_files=["/tmp/wbp-sandbox/external-models/secrets.env"],
        data={
            "credential_result": {
                "status": "admitted",
                "provider": provider,
                "source": "owner-env",
                "credential_ref": credential_ref,
                "credential_present": True,
                "supported_sources": ["owner-env"],
                "expected_refs": refs,
                "provider_dashboard_url": provider_dashboard_url,
                "secret_value_exposed": False,
                "browser_secret_intake": False,
                "browser_path_intake": False,
                "scope": "sandbox",
            }
        },
    )


def status_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Runtime is healthy.",
        liveness="healthy",
        severity="recoverable",
        operator_action="none",
        desired_mode="managed",
        effective_mode="managed",
        endpoint="127.0.0.1:8320",
        current_proxy_url="http://127.0.0.1:8320",
        pool_summary={
            "active": 2,
            "reserve": 1,
            "retired": 1,
            "healthy": 3,
            "degraded": 0,
            "down": 0,
        },
        attestation_summary={
            "status": "ok",
            "machine_error_code": "OK",
            "attestation_source": "fixture-test",
            "observed_at_utc": "2026-05-12T21:00:00Z",
        },
        last_error="",
    )
    payload.update(overrides)
    return payload


def mode_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(desired_mode="managed", effective_mode="managed")
    payload.update(overrides)
    return payload


def external_route(
    route_id: str,
    *,
    enabled: bool,
    display_name: str = "Route",
    upstream_model: str = "deepseek/deepseek-chat",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "route_id": route_id,
        "display_name": display_name,
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
        "cost_class": "paid_or_free_limited",
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": enabled,
    }


def accounts_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Accounts loaded.",
        accounts=[
            account("acct-active", "active", "healthy"),
            account("acct-reserve", "reserve", "healthy"),
            account("acct-hold", "reserve", "healthy", manual_hold=True),
            account("acct-problem", "retired", "down", last_error="auth failed"),
        ],
        registry_identity={
            "status": "ok",
            "machine_error_code": "OK",
            "next_action": "none",
        },
    )
    payload.update(overrides)
    return payload


def account(
    backend_id: str,
    pool: str,
    status: str,
    *,
    manual_hold: bool = False,
    last_error: str = "",
    label: str | None = None,
    auth_ref: str | None = None,
    last_error_class: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": backend_id,
        "label": label if label is not None else backend_id,
        "pool": pool,
        "manual_hold": manual_hold,
        "status": status,
        "fail_count": 0,
        "success_count": 1,
        "last_success": None,
        "last_error": last_error,
        "last_error_class": last_error_class,
        "cooldown_until": None,
        "notes": "",
    }
    if auth_ref is not None:
        payload["auth_ref"] = auth_ref
    return payload


def routes_list_packet(route_id: str = "wbp-deepseek-v3", *, enabled: bool = True) -> dict[str, object]:
    return command_packet(
        human_message="External-models routes listed from local registry.",
        data={
            "count": 1,
            "routes": [
                {
                    "schema_version": 1,
                    "route_id": route_id,
                    "display_name": "DeepSeek V3",
                    "provider": "openrouter",
                    "base_url": "http://127.0.0.1:54321/v1",
                    "endpoint_path": "/chat/completions",
                    "upstream_model": "deepseek/deepseek-chat",
                    "compatibility": "openai_chat_completions",
                    "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
                    "cost_class": "paid_or_free_limited",
                    "lane_role": "candidate",
                    "fallback_eligible": False,
                    "enabled": enabled,
                }
            ],
        },
    )


def routes_list_packet_for_operator_flow() -> dict[str, object]:
    enabled_route = routes_list_packet("wbp-deepseek-v3", enabled=True)["data"]["routes"][0]  # type: ignore[index]
    disabled_route = routes_list_packet("wbp-disabled", enabled=False)["data"]["routes"][0]  # type: ignore[index]
    return command_packet(
        human_message="External-models routes listed from local registry.",
        data={"count": 2, "routes": [enabled_route, disabled_route]},
    )


class MappingRunner:
    def __init__(self, payloads: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> CommandResult:
        self.calls.append(args)
        return CommandResult(payload=dict(self.payloads[args]), stderr="")


class WebDesignLiveServerTests(unittest.TestCase):
    def test_web_token_static_file_is_not_served_from_static_root(self) -> None:
        with tempfile.TemporaryDirectory() as static_dir:
            static_root = Path(static_dir)
            (static_root / "index.html").write_text("index-ok", encoding="utf-8")
            (static_root / WEB_TOKEN_FILENAME).write_text(
                "secret-web-token-should-not-leak",
                encoding="utf-8",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(static_dir=static_root),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                self.assertEqual(fetch(f"{base}/"), "index-ok")
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    fetch(f"{base}/{WEB_TOKEN_FILENAME}")
                error_body = raised.exception.read().decode("utf-8", errors="replace")
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(raised.exception.code, HTTPStatus.NOT_FOUND)
        self.assertNotIn("secret-web-token-should-not-leak", error_body)

    def test_index_bootstrap_injects_web_tokens_without_static_asset_leak(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            index = fetch(f"{base}/")
            token, csrf = _web_bootstrap_tokens(base)
            script = fetch(f"{base}/scripts/overview.js")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertIn(f'<meta name="{WEB_TOKEN_META_NAME}"', index)
        self.assertIn(f'<meta name="{WEB_CSRF_META_NAME}"', index)
        self.assertIn('data-source="live"', index)
        self.assertNotIn('data-source="fixture"', index)
        self.assertIn(token, index)
        self.assertIn(csrf, index)
        self.assertNotIn(token, script)
        self.assertNotIn(csrf, script)

    def test_web_design_main_rotates_runtime_web_token_and_deletes_on_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = root / "managed"
            observed_tokens: list[str] = []
            observed_modes: list[int] = []
            server_closed: list[bool] = []

            class OneShotServer:
                def __init__(self, address: tuple[str, int], handler: object) -> None:
                    self.server_address = address
                    self.RequestHandlerClass = handler

                def serve_forever(self) -> None:
                    token_path = managed_dir / WEB_TOKEN_FILENAME
                    observed_tokens.append(token_path.read_text(encoding="utf-8"))
                    observed_modes.append(token_path.stat().st_mode & 0o777)

                def server_close(self) -> None:
                    server_closed.append(True)

            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(managed_dir),
            }
            with (
                mock.patch.dict(os.environ, env_updates, clear=False),
                mock.patch.object(live_server, "ThreadingHTTPServer", OneShotServer),
            ):
                first_result = live_server.main(["--host", "127.0.0.1", "--port", "0"])
                second_result = live_server.main(["--host", "127.0.0.1", "--port", "0"])

            self.assertEqual(first_result, 0)
            self.assertEqual(second_result, 0)
            self.assertEqual(observed_modes, [0o600, 0o600])
            self.assertEqual(len(observed_tokens), 2)
            self.assertNotEqual(observed_tokens[0], observed_tokens[1])
            self.assertEqual(server_closed, [True, True])
            self.assertFalse((managed_dir / WEB_TOKEN_FILENAME).exists())

    def test_onboard_adapter_spec_uses_exact_argv_template(self) -> None:
        onboard = ALLOWLIST["accounts_onboard"]
        onboard_auth_ref = ALLOWLIST["accounts_onboard_auth_ref"]
        login_start = ALLOWLIST["accounts_login_start_sandbox"]
        login_complete = ALLOWLIST["accounts_login_complete_sandbox"]

        self.assertEqual(onboard.argv_template, ("accounts", "onboard", "--json"))
        self.assertEqual(onboard.category, "onboarding")
        self.assertTrue(onboard.confirmation_required)
        self.assertEqual(onboard.required_args, ())
        self.assertEqual(onboard.allowed_args, ())
        self.assertFalse(onboard_auth_ref.ui_enabled)
        self.assertEqual(
            onboard_auth_ref.argv_template,
            ("accounts", "onboard", "--json", "--auth-ref", "{auth_ref}"),
        )
        self.assertFalse(login_start.ui_enabled)
        self.assertEqual(
            login_start.argv_template,
            ("accounts", "login", "start", "--provider", "sandbox", "--json"),
        )
        self.assertFalse(login_complete.ui_enabled)
        self.assertEqual(
            login_complete.argv_template,
            (
                "accounts",
                "login",
                "complete",
                "--session",
                "{login_session_id}",
                "--state",
                "{state}",
                "--proof",
                "sandbox-ok",
                "--json",
            ),
        )

    def test_promote_demote_adapter_specs_use_exact_argv_templates(self) -> None:
        promote = ALLOWLIST["accounts_promote"]
        demote = ALLOWLIST["accounts_demote"]

        self.assertEqual(
            promote.argv_template,
            ("accounts", "promote", "{account_id}", "--json"),
        )
        self.assertTrue(promote.confirmation_required)
        self.assertEqual(promote.required_args, ("account_id",))
        self.assertEqual(promote.allowed_args, ("account_id",))
        self.assertEqual(
            demote.argv_template,
            ("accounts", "demote", "{account_id}", "--json"),
        )
        self.assertTrue(demote.confirmation_required)
        self.assertEqual(demote.required_args, ("account_id",))
        self.assertEqual(demote.allowed_args, ("account_id",))

    def test_retire_adapter_spec_uses_exact_argv_template(self) -> None:
        retire = ALLOWLIST["accounts_retire"]

        self.assertEqual(
            retire.argv_template,
            ("accounts", "retire", "{account_id}", "--json"),
        )
        self.assertTrue(retire.confirmation_required)
        self.assertEqual(retire.required_args, ("account_id",))
        self.assertEqual(retire.allowed_args, ("account_id",))

    def test_api_route_remove_adapter_spec_uses_exact_argv_template(self) -> None:
        remove = ALLOWLIST["external_models_routes_remove"]

        self.assertEqual(
            remove.argv_template,
            ("external-models", "routes", "remove", "--route", "{route_id}", "--json"),
        )
        self.assertEqual(remove.category, "external_models_registry_cleanup")
        self.assertTrue(remove.confirmation_required)
        self.assertEqual(remove.required_args, ("route_id",))
        self.assertEqual(remove.allowed_args, ("route_id",))

    def test_api_route_connect_adapter_spec_uses_server_owned_file_arg(self) -> None:
        add = ALLOWLIST["external_models_routes_add_server_owned"]
        status = ALLOWLIST["external_models_credentials_status_openrouter"]
        admit = ALLOWLIST["external_models_credentials_admit_openrouter_owner_env"]

        self.assertEqual(
            add.argv_template,
            ("external-models", "routes", "add", "--file", "{route_spec_ref}", "--json"),
        )
        self.assertEqual(add.category, "external_models_registry_admission")
        self.assertFalse(add.ui_enabled)
        self.assertTrue(add.confirmation_required)
        self.assertEqual(add.required_args, ("route_spec_ref",))
        self.assertEqual(add.allowed_args, ("route_spec_ref",))
        self.assertEqual(
            status.argv_template,
            ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
        )
        self.assertEqual(status.category, "external_models_credential_admission")
        self.assertFalse(status.ui_enabled)
        self.assertFalse(status.confirmation_required)
        self.assertEqual(
            admit.argv_template,
            (
                "external-models",
                "credentials",
                "admit",
                "--provider",
                "openrouter",
                "--source",
                "owner-env",
                "--json",
            ),
        )
        self.assertEqual(admit.category, "external_models_credential_admission")
        self.assertFalse(admit.ui_enabled)
        self.assertTrue(admit.confirmation_required)

    def test_live_snapshot_calls_only_readonly_commands_and_maps_shape(self) -> None:
        runner = MappingRunner(live_payloads())

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(
            runner.calls,
            [
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
                ("healthcheck", "--json"),
                ("rollout", "rotation", "inspect", "--json"),
            ],
        )
        self.assertEqual(tuple(snapshot["commands"]), READONLY_COMMAND_IDS)
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["source"], "live_readonly")
        self.assertEqual(snapshot["runtime"]["visual_state"], "healthy")
        self.assertEqual(snapshot["runtime"]["desired_mode"], "managed")
        self.assertEqual(snapshot["pool_summary"]["active"], 1)
        self.assertEqual(snapshot["pool_summary"]["reserve"], 2)
        self.assertEqual(snapshot["pool_summary"]["hold"], 1)
        self.assertEqual(snapshot["pool_summary"]["problem"], 1)
        self.assertFalse(snapshot["has_warnings"])
        self.assertTrue(snapshot["primary_truth_ok"])

    def test_healthcheck_error_becomes_degraded_warning_without_full_failure(self) -> None:
        payloads = live_payloads()
        payloads[("healthcheck", "--json")] = command_packet(
            status="error",
            machine_error_code="provider_network_failed",
            human_message="Network failed.",
        )
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["ui_state"], "degraded")
        self.assertEqual(snapshot["runtime"]["visual_state"], "degraded")
        self.assertEqual(snapshot["pool_summary"]["active"], 1)
        self.assertEqual(snapshot["warnings"][0]["role"], "runtime_detail")
        self.assertEqual(snapshot["warnings"][0]["severity"], "degraded")
        self.assertIn("Network failed", snapshot["warnings"][0]["human_message"])

    def test_rotation_error_becomes_warning_without_full_failure(self) -> None:
        payloads = live_payloads()
        payloads[("rollout", "rotation", "inspect", "--json")] = command_packet(
            status="error",
            machine_error_code="ROTATION_EVIDENCE_CONTRADICTED",
            human_message="Rotation evidence is contradicted.",
        )
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["ui_state"], "healthy")
        self.assertEqual(snapshot["runtime"]["visual_state"], "healthy")
        self.assertTrue(snapshot["has_warnings"])
        self.assertEqual(snapshot["warnings"][0]["role"], "rollout_evidence")
        self.assertEqual(snapshot["warnings"][0]["severity"], "warning")
        self.assertEqual(snapshot["evidence_summary"]["rollout_warnings"], 1)

    def test_primary_status_error_becomes_integration_failure_without_stale_green(self) -> None:
        payloads = live_payloads()
        payloads[("status", "--json")] = command_packet(
            status="error",
            machine_error_code="runtime_down",
            human_message="Runtime status failed.",
        )
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["ui_state"], "integration_failure")
        self.assertEqual(snapshot["runtime"]["visual_state"], "integration_failure")
        self.assertEqual(snapshot["pool_summary"]["active"], 0)
        self.assertFalse(snapshot["primary_truth_ok"])

    def test_mode_status_disagreement_becomes_integration_failure(self) -> None:
        payloads = live_payloads()
        payloads[("mode", "get", "--json")] = mode_packet(effective_mode="stable")
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["runtime"]["machine_error_code"], "UI_LIVE_READONLY_PACKET_INVALID")
        self.assertIn("disagree", snapshot["runtime"]["last_error"])

    def test_invalid_accounts_packet_becomes_integration_failure(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = command_packet(
            human_message="Accounts malformed.",
            accounts="not-a-list",
            registry_identity={
                "status": "ok",
                "machine_error_code": "OK",
                "next_action": "none",
            },
        )
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["runtime"]["machine_error_code"], "UI_LIVE_READONLY_PACKET_INVALID")
        self.assertIn("accounts must be a list", snapshot["runtime"]["last_error"])

    def test_accounts_readonly_calls_only_accounts_list_and_redacts_private_fields(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[
                account(
                    "acct-private",
                    "active",
                    "healthy",
                    label="private.user@example.com",
                    auth_ref="/Users/kirill/.cli-proxy-api/codex-private.json",
                ),
                account(
                    "acct-quota",
                    "reserve",
                    "down",
                    last_error="HTTP 429: usage_limit_reached in /tmp/private-token.json",
                    last_error_class="quota",
                ),
            ],
        )
        runner = MappingRunner(payloads)

        snapshot = build_accounts_readonly_snapshot(runner)

        self.assertEqual(runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(tuple(snapshot["commands"]), ACCOUNTS_READONLY_COMMAND_IDS)
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["source"], "accounts_readonly")
        self.assertTrue(snapshot["privacy"]["redacted"])
        self.assertFalse(snapshot["privacy"]["raw_command_packet_included"])
        self.assertEqual(snapshot["summary"]["active"], 1)
        self.assertEqual(snapshot["summary"]["reserve"], 1)
        self.assertEqual(snapshot["summary"]["problem"], 1)
        self.assertEqual(snapshot["accounts"][0]["label"], "pri***@***.com")
        self.assertEqual(snapshot["accounts"][1]["last_error_summary"], "квота или usage limit")
        serialized = json.dumps(snapshot)
        self.assertNotIn("auth_ref", serialized)
        self.assertNotIn("/Users/kirill", serialized)
        self.assertNotIn("/tmp/private-token", serialized)
        self.assertNotIn("private.user@example.com", serialized)

    def test_accounts_readonly_invalid_packet_becomes_integration_failure(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = command_packet(
            human_message="Accounts malformed.",
            accounts="not-a-list",
            registry_identity={
                "status": "ok",
                "machine_error_code": "OK",
                "next_action": "none",
            },
        )
        runner = MappingRunner(payloads)

        snapshot = build_accounts_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["source"], "accounts_readonly")
        self.assertEqual(snapshot["summary"]["machine_error_code"], "UI_ACCOUNTS_READONLY_PACKET_INVALID")
        self.assertEqual(snapshot["accounts"], [])

    def test_api_connections_readonly_calls_only_external_packets_and_keeps_bounded_secret_ref_only(self) -> None:
        runner = MappingRunner(live_payloads())

        snapshot = build_api_connections_readonly_snapshot(runner)

        self.assertEqual(
            runner.calls,
            [
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
        )
        self.assertEqual(tuple(snapshot["commands"]), API_CONNECTIONS_READONLY_COMMAND_IDS)
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["source"], "api_connections_readonly")
        self.assertTrue(snapshot["privacy"]["redacted"])
        self.assertFalse(snapshot["privacy"]["raw_command_packet_included"])
        self.assertEqual(snapshot["summary"]["routes_count"], 1)
        self.assertEqual(snapshot["summary"]["enabled_count"], 1)
        self.assertEqual(snapshot["summary"]["attention_count"], 1)
        self.assertEqual(snapshot["routes"][0]["status_label"], "Требует ключ")
        self.assertEqual(snapshot["routes"][0]["secret_ref"], "OPENROUTER_API_KEY")
        self.assertEqual(snapshot["routes"][0]["secret_status_label"], "missing")
        self.assertEqual(snapshot["routes"][0]["role_label"], "main route")
        self.assertTrue(snapshot["routes"][0]["primary"])
        serialized = json.dumps(snapshot)
        self.assertNotIn('"auth"', serialized)
        self.assertNotIn("/Users/", serialized)

    def test_api_connections_readonly_projects_observed_route_check_state(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "status", "--json")] = command_packet(
            human_message="External-models synthetic lifecycle status collected without live runtime claims.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "foundation_phase": "C3",
                "adapter_runtime_available": False,
                "lifecycle_mode": "synthetic",
                "adapter_state": "started",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "routes_count": 1,
                "observed_routes_count": 1,
                "observed_routes": {
                    "wbp-deepseek-v3": {
                        "availability_state": "verified",
                        "last_check": "2026-05-21T09:45:00Z",
                        "last_verified_at": "2026-05-21T09:45:00Z",
                        "effective_model": "deepseek/deepseek-chat",
                    }
                },
                "adapter": {
                    "state": "started",
                    "lifecycle_mode": "synthetic",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "base_url": "http://127.0.0.1:54321/v1",
                    "host": "127.0.0.1",
                    "port": 54321,
                    "started_at_utc": "2026-05-21T09:40:00Z",
                    "last_transition": "start",
                },
                "local_auth": {
                    "token_ref": "managed_local_token",
                    "token_present": True,
                    "token_created_at_utc": "2026-05-21T09:40:00Z",
                },
            },
        )
        runner = MappingRunner(payloads)

        snapshot = build_api_connections_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["summary"]["latest_check"], "2026-05-21T09:45:00Z")
        self.assertEqual(snapshot["routes"][0]["validation_label"], "ok")
        self.assertEqual(snapshot["routes"][0]["validation_visual_state"], "green")
        self.assertEqual(snapshot["routes"][0]["last_checked"], "2026-05-21T09:45:00Z")
        self.assertIn("bounded packet", snapshot["routes"][0]["note"])

    def test_api_connections_readonly_downgrades_route_when_provider_validation_failed(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "status", "--json")] = command_packet(
            human_message="External-models synthetic lifecycle status collected without live runtime claims.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "foundation_phase": "C3",
                "adapter_runtime_available": False,
                "lifecycle_mode": "synthetic",
                "adapter_state": "started",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "routes_count": 1,
                "observed_routes_count": 1,
                "observed_routes": {
                    "wbp-deepseek-v3": {
                        "availability_state": "provider_auth_failed",
                        "last_check": "2026-05-21T09:45:00Z",
                        "last_verified_at": "2026-05-21T09:45:00Z",
                        "effective_model": "deepseek/deepseek-chat",
                    }
                },
                "adapter": {
                    "state": "started",
                    "lifecycle_mode": "synthetic",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "base_url": "http://127.0.0.1:54321/v1",
                    "host": "127.0.0.1",
                    "port": 54321,
                    "started_at_utc": "2026-05-21T09:40:00Z",
                    "last_transition": "start",
                },
                "local_auth": {
                    "token_ref": "managed_local_token",
                    "token_present": True,
                    "token_created_at_utc": "2026-05-21T09:40:00Z",
                },
            },
        )
        runner = MappingRunner(payloads)

        snapshot = build_api_connections_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["summary"]["attention_count"], 1)
        self.assertEqual(snapshot["routes"][0]["status_code"], "validation_failed")
        self.assertEqual(snapshot["routes"][0]["status_label"], "Требует проверки")
        self.assertEqual(snapshot["routes"][0]["visual_state"], "red")
        self.assertEqual(snapshot["routes"][0]["validation_label"], "validate failed")
        self.assertEqual(snapshot["routes"][0]["validation_visual_state"], "red")
        self.assertIn("ошибкой", snapshot["routes"][0]["note"])

    def test_api_connections_readonly_invalid_packet_becomes_integration_failure(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External models malformed.",
            data={
                "count": 1,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": "not-a-list",
            },
        )
        runner = MappingRunner(payloads)

        snapshot = build_api_connections_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["source"], "api_connections_readonly")
        self.assertEqual(snapshot["summary"]["machine_error_code"], "UI_API_CONNECTIONS_PACKET_INVALID")
        self.assertEqual(snapshot["routes"], [])

    def test_http_server_serves_static_index_and_readonly_api(self) -> None:
        runner = MappingRunner(live_payloads())
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            index = fetch(f"{base_url}/?source=live")
            api = json.loads(fetch(f"{base_url}/api/live-readonly?command_id=sync"))
            accounts = json.loads(fetch(f"{base_url}/api/accounts-readonly?command_id=sync"))
            api_connections = json.loads(fetch(f"{base_url}/api/api-connections-readonly?command_id=sync"))
            metadata = json.loads(fetch(f"{base_url}/api/actions"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertIn("sourcePicker", index)
        self.assertEqual(api["status"], "ok")
        self.assertEqual(accounts["status"], "ok")
        self.assertEqual(accounts["source"], "accounts_readonly")
        self.assertEqual(api_connections["status"], "ok")
        self.assertEqual(api_connections["source"], "api_connections_readonly")
        self.assertEqual(metadata["action_phase"], LIVE_READONLY_ACTION_PHASE)
        self.assertFalse(metadata["actions"]["refresh_health_detail"]["available"])
        self.assertFalse(metadata["actions"]["stable_repair_plan"]["available"])
        self.assertFalse(metadata["actions"]["export_diagnostics"]["available"])
        self.assertFalse(metadata["actions"]["sync_runtime"]["available"])
        self.assertNotIn(("sync", "--json"), runner.calls)
        self.assertNotIn(("launch", "client", "--json"), runner.calls)

    def test_functional_app_integration_proof_wires_first_screen_lanes_and_three_modes(
        self,
    ) -> None:
        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={
                "active": 1,
                "reserve": 1,
                "retired": 0,
                "healthy": 2,
                "degraded": 0,
                "down": 0,
                "selected_backend_ids": ["acct-active"],
            },
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
                "launch_capable_backend_count": 1,
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[
                account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json"),
                account("acct-reserve", "reserve", "healthy", auth_ref="/tmp/wbp-reserve.json"),
            ]
        )
        payloads[("external-models", "status", "--json")] = command_packet(
            human_message=(
                "External-models synthetic lifecycle status collected without live runtime claims."
            ),
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "foundation_phase": "C5",
                "adapter_runtime_available": False,
                "lifecycle_mode": "synthetic",
                "adapter_state": "stopped",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "routes_count": 1,
                "observed_routes_count": 1,
                "available_secret_refs": ["DEEPSEEK_API_KEY"],
                "observed_routes": {
                    "wbp-deepseek-v3": {
                        "availability_state": "verified",
                        "last_check": "2026-05-25T00:00:00Z",
                        "last_verified_at": "2026-05-25T00:00:00Z",
                    }
                },
                "adapter": {
                    "state": "stopped",
                    "lifecycle_mode": "synthetic",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "base_url": None,
                    "host": "127.0.0.1",
                    "port": None,
                    "started_at_utc": None,
                    "last_transition": "init",
                },
                "local_auth": {
                    "token_ref": "managed_local_token",
                    "token_present": False,
                    "token_created_at_utc": None,
                },
            },
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "count": 1,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [
                    {
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "cost_class": "paid_or_free_limited",
                        "enabled": True,
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "synthetic_adapter_state": "stopped",
                        "profile_ready": False,
                    }
                ],
            },
        )
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "count": 1,
                "routes": [
                    {
                        "schema_version": 1,
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "auth": {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"},
                        "cost_class": "paid_or_free_limited",
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "enabled": True,
                    }
                ],
            },
        )
        runner = MappingRunner(payloads)
        created_sessions: list[ExternalRouteFakeOperatorSurfaceSession] = []

        def session_factory(*args: object, **kwargs: object) -> ExternalRouteFakeOperatorSurfaceSession:
            session = ExternalRouteFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        with mock.patch.object(
            live_server,
            "OperatorSurfaceSession",
            side_effect=session_factory,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=runner),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                index = fetch(f"{base}/?source=live")
                overview = json.loads(fetch(f"{base}/api/live-readonly?command_id=sync"))
                accounts = json.loads(fetch(f"{base}/api/accounts-readonly?command_id=sync"))
                api_connections = json.loads(
                    fetch(f"{base}/api/api-connections-readonly?command_id=sync")
                )
                actions = json.loads(fetch(f"{base}/api/actions"))
                launch_modes = json.loads(fetch(f"{base}/api/codex/launch-modes"))
                custom_accounts = json.loads(fetch(f"{base}/api/codex/custom/accounts"))
                account_selection = json.loads(fetch(f"{base}/api/codex/custom/account-selection"))
                chatgpt_only = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {"execution_mode": "chatgpt_only"},
                    )
                )
                api_only = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
                chatgpt_plus_api = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "chatgpt_plus_api",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
                quick_start = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
                api_executor_truth = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-executor-truth",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
                deepseek_live_blocked = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-deepseek/live-format",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        authorized_sessions: list[DualLaneFakeOperatorSurfaceSession] = []

        def authorized_session_factory() -> DualLaneFakeOperatorSurfaceSession:
            session = DualLaneFakeOperatorSurfaceSession()
            authorized_sessions.append(session)
            return session

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                mock.patch.object(
                    live_server,
                    "CodexCustomSessionManager",
                    side_effect=lambda root=None: REAL_CODEX_CUSTOM_SESSION_MANAGER(
                        Path(temp_dir) if root is None else root
                    ),
                ),
                mock.patch.object(
                    live_server,
                    "OperatorSurfaceSession",
                    side_effect=authorized_session_factory,
                ),
            ):
                authorized_server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(dict(payloads)),
                        owner_authorization_phrase=(
                            "разрешаю тебе любые законные действия в рамках разработки проекта"
                        ),
                    ),
                )
                authorized_thread = threading.Thread(
                    target=authorized_server.serve_forever,
                    daemon=True,
                )
                authorized_thread.start()
                authorized_base = f"http://127.0.0.1:{authorized_server.server_port}"
                try:
                    session_created = json.loads(
                        post_json(
                            f"{authorized_base}/api/codex/custom/sessions",
                            {
                                "primary_model_id": "gpt-5.3-codex",
                                "coding_agent_model_id": "wbp-deepseek-v3",
                            },
                        )
                    )
                    session_id = session_created["session"]["session_id"]
                    primary_prompt = json.loads(
                        post_json(
                            f"{authorized_base}/api/codex/custom/sessions/{session_id}/prompt",
                            {
                                "prompt": "Reply with exactly CHATGPT_LANE_OK.",
                                "slot_id": "primary_model_slot",
                            },
                        )
                    )
                    api_prompt = json.loads(
                        post_json(
                            f"{authorized_base}/api/codex/custom/sessions/{session_id}/prompt",
                            {
                                "prompt": "Reply with exactly API_LANE_OK.",
                                "slot_id": "coding_agent_model_slot",
                            },
                        )
                    )
                finally:
                    authorized_server.shutdown()
                    authorized_thread.join(timeout=2)
                    authorized_server.server_close()

        self.assertIn('data-source="live"', index)
        self.assertNotIn('data-source="fixture"', index)

        self.assertEqual(overview["status"], "ok")
        self.assertEqual(overview["source"], "live_readonly")
        self.assertTrue(overview["primary_truth_ok"])
        self.assertEqual(overview["runtime"]["machine_error_code"], "OK")
        self.assertEqual(overview["runtime"]["effective_mode"], "managed")
        self.assertEqual(overview["runtime"]["desired_mode"], "managed")
        self.assertEqual(overview["commands"]["healthcheck"]["status"], "ok")
        self.assertEqual(set(overview["commands"]), set(READONLY_COMMAND_IDS))

        self.assertEqual(accounts["status"], "ok")
        self.assertEqual(accounts["source"], "accounts_readonly")
        self.assertTrue(accounts["primary_truth_ok"])
        self.assertGreaterEqual(accounts["summary"]["active"], 1)
        self.assertGreaterEqual(accounts["summary"]["reserve"], 1)
        self.assertIn("next_action", accounts["registry_identity"])
        self.assertNotIn("auth_ref", json.dumps(accounts, ensure_ascii=False))

        self.assertEqual(api_connections["status"], "ok")
        self.assertEqual(api_connections["source"], "api_connections_readonly")
        self.assertTrue(api_connections["primary_truth_ok"])
        self.assertEqual(api_connections["routes"][0]["route_id"], "wbp-deepseek-v3")
        self.assertEqual(api_connections["routes"][0]["provider"], "deepseek")
        self.assertEqual(api_connections["routes"][0]["secret_ref"], "DEEPSEEK_API_KEY")
        self.assertEqual(api_connections["routes"][0]["secret_status_label"], "available")
        self.assertEqual(api_connections["routes"][0]["validation_label"], "ok")
        self.assertTrue(api_connections["routes"][0]["primary"])
        self.assertNotIn('"auth"', json.dumps(api_connections, ensure_ascii=False))

        self.assertEqual(actions["action_phase"], LIVE_READONLY_ACTION_PHASE)
        self.assertFalse(actions["actions"]["stable_repair_plan"]["available"])
        self.assertFalse(actions["actions"]["export_diagnostics"]["available"])
        self.assertFalse(actions["actions"]["sync_runtime"]["available"])
        self.assertFalse(actions["actions"]["launch_client_dispatch"]["available"])

        self.assertEqual(custom_accounts["status"], "ok")
        self.assertEqual(custom_accounts["account_source"], "provided_packet_or_fake")
        self.assertFalse(custom_accounts["account_mutation_performed"])
        self.assertFalse(custom_accounts["raw_backend_ids_exposed"])
        self.assertFalse(custom_accounts["raw_auth_refs_exposed"])
        self.assertEqual(custom_accounts["token_burn"], 0)
        self.assertEqual(account_selection["status"], "ok")
        self.assertEqual(account_selection["selected_source_class"], "gpt_account")
        self.assertTrue(account_selection["selection_dry_run_proven"])
        self.assertFalse(account_selection["inference_proven"])
        self.assertFalse(account_selection["provider_called"])

        modes = {mode["id"]: mode for mode in launch_modes["modes"]}
        self.assertIn("original_codex", modes)
        self.assertIn("codex_custom", modes)
        self.assertIn("safe_app_copy", modes)
        self.assertFalse(modes["safe_app_copy"]["live_launch_available"])

        self.assertEqual(chatgpt_only["status"], "ok")
        self.assertEqual(chatgpt_only["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertFalse(chatgpt_only["api_line_used_as_executor"])
        self.assertFalse(chatgpt_only["chatgpt_only_calls_api"])

        self.assertEqual(api_only["status"], "ok")
        self.assertEqual(api_only["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(api_only["primary_model_slot"]["model_id"], "wbp-deepseek-v3")
        self.assertFalse(api_only["chatgpt_line_used_as_executor"])
        self.assertFalse(api_only["api_only_calls_chatgpt"])
        self.assertFalse(api_only["live_call_attempted"])
        self.assertFalse(api_only["provider_called"])

        self.assertEqual(chatgpt_plus_api["status"], "ok")
        self.assertEqual(chatgpt_plus_api["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertEqual(chatgpt_plus_api["coding_agent_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(
            chatgpt_plus_api["coding_agent_model_slot"]["model_id"],
            "wbp-deepseek-v3",
        )
        self.assertTrue(chatgpt_plus_api["dual_lane_slots_preserved"])
        self.assertFalse(chatgpt_plus_api["live_call_attempted"])
        self.assertFalse(chatgpt_plus_api["provider_called"])

        self.assertEqual(quick_start["status"], "ok")
        self.assertEqual(quick_start["launch_admission"], "admitted")
        self.assertEqual(quick_start["api_route"]["status"], "admitted")
        self.assertFalse(quick_start["fallback_used"])
        self.assertFalse(quick_start["silent_fallback_used"])
        self.assertFalse(quick_start["live_call_attempted"])
        self.assertFalse(quick_start["provider_called"])
        self.assertFalse(quick_start["custom_codex_launch_attempted"])
        quick_start_json = json.dumps(quick_start, ensure_ascii=False)
        self.assertNotIn("DEEPSEEK_API_KEY", quick_start_json)
        self.assertNotIn('"secret_ref"', quick_start_json)
        self.assertNotIn('"base_url"', quick_start_json)
        self.assertNotIn('"route_id"', quick_start_json)

        self.assertEqual(api_executor_truth["status"], "ok")
        self.assertEqual(
            api_executor_truth["final_status"],
            "API_ONLY_EXECUTOR_TRUTH_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(api_executor_truth["api_primary_slot_proven"])
        self.assertEqual(api_executor_truth["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(api_executor_truth["selected_api_model"], "wbp-deepseek-v3")
        self.assertTrue(api_executor_truth["api_line_used_as_executor"])
        self.assertFalse(api_executor_truth["chatgpt_line_used_as_executor"])
        self.assertFalse(api_executor_truth["fallback_used"])
        self.assertFalse(api_executor_truth["provider_called"])
        self.assertFalse(api_executor_truth["live_call_attempted"])

        self.assertEqual(deepseek_live_blocked["status"], "blocked")
        self.assertEqual(
            deepseek_live_blocked["machine_error_code"],
            "API_ONLY_DEEPSEEK_OWNER_AUTH_REQUIRED",
        )
        self.assertFalse(deepseek_live_blocked["provider_called"])
        self.assertFalse(deepseek_live_blocked["live_call_attempted"])
        self.assertNotIn(
            (
                "external-models",
                "live-format-check",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Верни короткий ответ: API_ONLY_DEEPSEEK_READY",
                "--expected-text",
                "API_ONLY_DEEPSEEK_READY",
                "--json",
            ),
            runner.calls,
        )
        self.assertNotIn(("sync", "--json"), runner.calls)
        self.assertNotIn(("launch", "client", "--json"), runner.calls)
        self.assertNotIn(
            ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"),
            runner.calls,
        )
        self.assertEqual(len(created_sessions), 1)
        self.assertEqual(created_sessions[0].run_payloads, [])

        self.assertEqual(session_created["status"], "ok")
        self.assertTrue(session_created["session_created"])
        self.assertEqual(
            session_created["session"]["role_slots"]["primary_model_slot"]["model_id"],
            "gpt-5.3-codex",
        )
        self.assertEqual(
            session_created["session"]["role_slots"]["coding_agent_model_slot"]["model_id"],
            "wbp-deepseek-v3",
        )
        self.assertEqual(primary_prompt["status"], "ok")
        self.assertEqual(primary_prompt["current_execution_slot_id"], "primary_model_slot")
        self.assertEqual(primary_prompt["configured_provider"], "cliproxy")
        self.assertTrue(primary_prompt["live_prompt_full_success"])
        self.assertEqual(api_prompt["status"], "ok")
        self.assertEqual(api_prompt["current_execution_slot_id"], "coding_agent_model_slot")
        self.assertEqual(api_prompt["configured_provider"], "external_route")
        self.assertTrue(api_prompt["live_prompt_full_success"])
        self.assertEqual(
            authorized_sessions[0].run_payloads,
            [
                {
                    "prompt": "Reply with exactly CHATGPT_LANE_OK.",
                    "model_id": "gpt-5.3-codex",
                    "slot_id": "primary_model_slot",
                },
                {
                    "prompt": "Reply with exactly API_LANE_OK.",
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "coding_agent_model_slot",
                },
            ],
        )

    def test_live_server_rejects_public_bind_without_explicit_unsafe_flag(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            live_server.main(["--host", "0.0.0.0", "--port", "0"])

        self.assertEqual(raised.exception.code, 2)

    def test_sandbox_action_phase_routes_all_readonly_surfaces_to_sandbox_runner(self) -> None:
        default_payloads = live_payloads()
        default_payloads[("status", "--json")] = status_packet(
            machine_error_code="DEFAULT_RUNNER",
            human_message="Default runner should not serve sandbox readonly.",
        )
        sandbox_payloads = live_payloads()
        sandbox_payloads[("status", "--json")] = status_packet(
            machine_error_code="SANDBOX_RUNNER",
            human_message="Sandbox readonly runner used.",
        )
        default_runner = MappingRunner(default_payloads)
        sandbox_runner = MappingRunner(sandbox_payloads)

        with mock.patch.object(
            live_server,
            "JsonCommandRunner",
            side_effect=[default_runner, sandbox_runner],
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    launch_copy_contract=launch_copy_contract(),
                    action_phase=SANDBOX_ACTION_PHASE,
                ),
            )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            overview = json.loads(fetch(f"{base_url}/api/live-readonly"))
            accounts = json.loads(fetch(f"{base_url}/api/accounts-readonly"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(overview["runtime"]["machine_error_code"], "SANDBOX_RUNNER")
        self.assertIn(("status", "--json"), sandbox_runner.calls)
        self.assertIn(("accounts", "list", "--json"), sandbox_runner.calls)
        self.assertEqual(default_runner.calls, [])
        self.assertEqual(accounts["source"], "accounts_readonly")

    def test_ui_action_metadata_hides_adapter_commands_and_marks_confirmed_actions(self) -> None:
        metadata = ui_action_metadata()
        sandbox_blocked = ui_action_metadata(action_phase=SANDBOX_ACTION_PHASE)
        sandbox_metadata = ui_action_metadata(
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )
        full_metadata = ui_action_metadata(action_phase=FULL_ACTION_PHASE)
        bounded_metadata = ui_action_metadata(
            launch_client_path=TEST_LAUNCH_CLIENT_PATH,
            launch_copy_contract=launch_copy_contract(),
            action_phase=FULL_ACTION_PHASE,
        )

        self.assertEqual(metadata["status"], "ok")
        self.assertEqual(metadata["action_phase"], LIVE_READONLY_ACTION_PHASE)
        self.assertNotIn("adapter_command_id", json.dumps(metadata))
        self.assertNotIn("save_settings", metadata["actions"])
        self.assertNotIn("update_settings", metadata["actions"])
        self.assertNotIn("settings_write", metadata["actions"])
        self.assertNotIn("select_client", metadata["actions"])
        self.assertNotIn("save_selection", metadata["actions"])
        self.assertNotIn("verify_path", metadata["actions"])
        self.assertNotIn("import_apply", metadata["actions"])
        self.assertNotIn("installer_init", metadata["actions"])
        self.assertIn("setup_discovery", metadata["actions"])
        self.assertIn("legacy_import_discovery", metadata["actions"])
        self.assertIn("legacy_import", metadata["actions"])
        self.assertTrue(metadata["actions"]["setup_discovery"]["available"])
        self.assertEqual(
            metadata["actions"]["setup_discovery"]["availability_state"],
            live_server.SETUP_DISCOVERY_AVAILABLE_STATE,
        )
        self.assertEqual(metadata["actions"]["setup_discovery"]["disabled_reason_code"], "")
        self.assertTrue(metadata["actions"]["legacy_import_discovery"]["available"])
        self.assertEqual(
            metadata["actions"]["legacy_import_discovery"]["availability_state"],
            live_server.LEGACY_IMPORT_DISCOVERY_AVAILABLE_STATE,
        )
        self.assertEqual(
            metadata["actions"]["legacy_import_discovery"]["disabled_reason_code"], ""
        )
        self.assertFalse(metadata["actions"]["legacy_import"]["available"])
        self.assertEqual(
            metadata["actions"]["legacy_import"]["availability_state"],
            "token_required",
        )
        self.assertEqual(
            metadata["actions"]["legacy_import"]["disabled_reason_code"],
            live_server.LEGACY_IMPORT_TOKEN_REQUIRED_CODE,
        )
        self.assertFalse(metadata["actions"]["refresh_health_detail"]["available"])
        self.assertFalse(metadata["actions"]["stable_repair_plan"]["available"])
        self.assertFalse(metadata["actions"]["export_diagnostics"]["available"])
        self.assertFalse(metadata["actions"]["onboard_account_dry_run"]["available"])
        self.assertFalse(metadata["actions"]["onboard_account"]["available"])
        self.assertFalse(metadata["actions"]["validate_account"]["available"])
        self.assertFalse(metadata["actions"]["sync_runtime"]["available"])
        self.assertFalse(metadata["actions"]["api_route_validate"]["available"])
        self.assertFalse(metadata["actions"]["api_route_connect"]["available"])
        self.assertFalse(metadata["actions"]["quick_start_check_all"]["available"])
        self.assertFalse(metadata["actions"]["launch_client_dispatch"]["available"])
        for ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
            action = metadata["actions"][ui_action]
            self.assertFalse(action["available"], ui_action)
            self.assertEqual(action["availability_state"], "disabled_live_action")
            self.assertEqual(
                action["disabled_reason_code"],
                LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
            )
            self.assertEqual(
                tuple(action["disabled_reasons"]),
                LIVE_READONLY_ACTION_DISABLED_REASONS,
            )
            self.assertIn("LOCK_HELD", action["unavailable_reason"])
        self.assertIn("live-readonly", metadata["actions"]["export_diagnostics"]["unavailable_reason"])
        self.assertIn("live-readonly", metadata["actions"]["sync_runtime"]["unavailable_reason"])
        self.assertIn("live-readonly", metadata["actions"]["launch_client_dispatch"]["unavailable_reason"])
        self.assertTrue(sandbox_blocked["actions"]["setup_discovery"]["available"])
        self.assertTrue(sandbox_blocked["actions"]["legacy_import_discovery"]["available"])
        self.assertFalse(sandbox_blocked["actions"]["legacy_import"]["available"])
        self.assertTrue(sandbox_metadata["actions"]["setup_discovery"]["available"])
        self.assertTrue(sandbox_metadata["actions"]["legacy_import_discovery"]["available"])
        self.assertFalse(sandbox_metadata["actions"]["legacy_import"]["available"])
        self.assertTrue(full_metadata["actions"]["setup_discovery"]["available"])
        self.assertTrue(full_metadata["actions"]["legacy_import_discovery"]["available"])
        self.assertFalse(full_metadata["actions"]["legacy_import"]["available"])
        self.assertTrue(bounded_metadata["actions"]["setup_discovery"]["available"])
        self.assertTrue(bounded_metadata["actions"]["legacy_import_discovery"]["available"])
        self.assertFalse(bounded_metadata["actions"]["legacy_import"]["available"])

        self.assertEqual(sandbox_blocked["action_phase"], SANDBOX_ACTION_PHASE)
        self.assertEqual(sandbox_blocked["sandbox_preflight"]["status"], "denied")
        self.assertFalse(sandbox_blocked["actions"]["onboard_account_dry_run"]["available"])
        self.assertEqual(
            sandbox_blocked["actions"]["onboard_account_dry_run"]["disabled_reason_code"],
            "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED",
        )
        self.assertFalse(sandbox_blocked["actions"]["onboard_account"]["available"])
        self.assertEqual(
            sandbox_blocked["actions"]["onboard_account"]["disabled_reason_code"],
            "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED",
        )
        for ui_action in (
            "account_login_status",
            "account_login_complete",
            "account_login_cancel",
            "api_route_credential_check",
        ):
            self.assertFalse(sandbox_blocked["actions"][ui_action]["available"])
            self.assertEqual(
                sandbox_blocked["actions"][ui_action]["availability_state"],
                "preflight_blocked",
            )
            self.assertEqual(
                sandbox_blocked["actions"][ui_action]["disabled_reason_code"],
                "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED",
            )
            self.assertEqual(
                tuple(sandbox_blocked["actions"][ui_action]["disabled_reasons"]),
                ("sandbox_target_unproven",),
            )
        self.assertFalse(sandbox_blocked["actions"]["validate_account"]["available"])
        self.assertEqual(
            sandbox_blocked["actions"]["validate_account"]["disabled_reason_code"],
            "UI_ACTION_PHASE_NOT_ADMITTED",
        )
        self.assertIn(
            "Sandbox action phase допускает reserve-first onboarding lane",
            sandbox_blocked["actions"]["validate_account"]["unavailable_reason"],
        )

        self.assertEqual(sandbox_metadata["sandbox_preflight"]["status"], "admitted")
        self.assertTrue(sandbox_metadata["actions"]["onboard_account_dry_run"]["available"])
        self.assertTrue(sandbox_metadata["actions"]["api_route_connect"]["available"])
        self.assertTrue(sandbox_metadata["actions"]["api_route_validate"]["available"])
        self.assertTrue(sandbox_metadata["actions"]["onboard_account"]["available"])
        self.assertTrue(sandbox_metadata["actions"]["quick_start_check_all"]["available"])
        for ui_action in (
            "account_login_status",
            "account_login_complete",
            "account_login_cancel",
            "api_route_credential_check",
        ):
            self.assertTrue(sandbox_metadata["actions"][ui_action]["available"])
            self.assertEqual(
                sandbox_metadata["actions"][ui_action]["availability_state"],
                "displayable_readonly",
            )
            self.assertEqual(
                sandbox_metadata["actions"][ui_action]["disabled_reason_code"],
                "",
            )
            self.assertEqual(sandbox_metadata["actions"][ui_action]["disabled_reasons"], [])
        self.assertFalse(sandbox_metadata["actions"]["validate_account"]["available"])
        self.assertEqual(
            sandbox_metadata["actions"]["validate_account"]["availability_state"],
            "phase_not_admitted",
        )
        self.assertFalse(sandbox_metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertEqual(
            sandbox_metadata["actions"]["launch_client_dispatch"]["disabled_reason_code"],
            "UI_ACTION_PHASE_NOT_ADMITTED",
        )

        self.assertTrue(full_metadata["actions"]["sync_runtime"]["available"])
        self.assertTrue(full_metadata["actions"]["refresh_health_detail"]["available"])
        self.assertTrue(full_metadata["actions"]["stable_repair_plan"]["available"])
        self.assertTrue(full_metadata["actions"]["set_mode_stable"]["confirmation_required"])
        self.assertTrue(full_metadata["actions"]["set_mode_managed"]["confirmation_required"])
        self.assertFalse(full_metadata["actions"]["launch_smoke"]["confirmation_required"])
        self.assertEqual(full_metadata["actions"]["export_diagnostics"]["action_role"], "support_artifact")
        self.assertEqual(
            full_metadata["actions"]["onboard_account_dry_run"]["action_role"],
            "account_onboarding_preview",
        )
        self.assertEqual(full_metadata["actions"]["onboard_account"]["action_role"], "account_onboarding")
        self.assertEqual(full_metadata["actions"]["api_route_validate"]["action_role"], "api_route_validation")
        self.assertEqual(full_metadata["actions"]["api_route_connect"]["action_role"], "api_route_admission")
        self.assertEqual(full_metadata["actions"]["api_route_profile"]["action_role"], "api_route_profile_packet")
        self.assertNotIn(
            "openrouter",
            full_metadata["actions"]["api_route_credential_check"]["human_meaning"],
        )
        self.assertEqual(
            full_metadata["actions"]["quick_start_check_all"]["action_role"],
            "quick_start_verify_bundle",
        )
        self.assertTrue(full_metadata["actions"]["launch_client_dispatch"]["confirmation_required"])
        self.assertFalse(full_metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertTrue(bounded_metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertEqual(bounded_metadata["actions"]["launch_client_dispatch"]["unavailable_reason"], "")
        self.assertEqual(
            bounded_metadata["actions"]["launch_client_dispatch"]["launch_preflight"]["status"],
            "admitted",
        )
        self.assertTrue(
            bounded_metadata["actions"]["launch_client_dispatch"]["launch_preflight"]["process_confirmation_possible"]
        )
        self.assertNotIn(TEST_LAUNCH_CLIENT_PATH, json.dumps(bounded_metadata))

    def test_onboard_account_dry_run_returns_preview_without_command_or_browser_args(self) -> None:
        runner = MappingRunner(live_payloads())

        result = run_ui_action(runner, {"ui_action": "onboard_account_dry_run"})
        auth_ref = run_ui_action(
            runner,
            {"ui_action": "onboard_account_dry_run", "auth_ref": "/tmp/new-auth.json"},
        )
        token = run_ui_action(
            runner,
            {"ui_action": "onboard_account_dry_run", "token": "secret"},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "account_onboarding_preview")
        self.assertFalse(result["confirmation_required"])
        self.assertFalse(result["post_action_refresh_required"])
        self.assertEqual(result["result"]["onboarding"]["ui_state"], "dry_run_ready")
        self.assertEqual(
            result["result"]["onboarding"]["final_outcome"],
            "dry_run_preview_ready",
        )
        self.assertTrue(result["result"]["onboarding"]["preview_only"])
        self.assertEqual(result["result"]["onboarding"]["candidate_source_kind"], "server_owned_only")
        self.assertEqual(result["result"]["onboarding"]["required_follow_up"], "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS")
        self.assertEqual(result["result"]["changed_files"], [])
        self.assertEqual(runner.calls, [])
        for payload in [auth_ref, token]:
            self.assertEqual(payload["status"], "integration_failure")
            self.assertEqual(payload["action_role"], "blocked")
            self.assertEqual(payload["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")

    def test_http_action_endpoint_blocks_parked_actions_in_live_readonly_phase(self) -> None:
        runner = MappingRunner(live_payloads())
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            health = json.loads(
                post_json(f"{base_url}/api/action", {"ui_action": "refresh_health_detail"})
            )
            repair_plan = json.loads(
                post_json(f"{base_url}/api/action", {"ui_action": "stable_repair_plan"})
            )
            diagnostics = json.loads(
                post_json(f"{base_url}/api/action", {"ui_action": "export_diagnostics"})
            )
            validate = json.loads(
                post_json(
                    f"{base_url}/api/action",
                    {"ui_action": "validate_account", "account_id": "acct-active"},
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(health["status"], "integration_failure")
        self.assertEqual(
            health["result"]["machine_error_code"],
            LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
        )
        self.assertEqual(health["availability_state"], "disabled_live_action")
        self.assertEqual(repair_plan["status"], "integration_failure")
        self.assertEqual(
            repair_plan["result"]["machine_error_code"],
            LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
        )
        self.assertEqual(repair_plan["availability_state"], "disabled_live_action")
        self.assertEqual(diagnostics["status"], "integration_failure")
        self.assertEqual(diagnostics["result"]["machine_error_code"], LIVE_READONLY_ACTION_DISABLED_REASON_CODE)
        self.assertEqual(validate["status"], "integration_failure")
        self.assertEqual(validate["result"]["machine_error_code"], LIVE_READONLY_ACTION_DISABLED_REASON_CODE)
        self.assertEqual(runner.calls, [])

    def test_setup_discovery_returns_zero_write_none_packet_without_execution(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_updates = {
                "WBP_PROFILE_DIR": str(root / "profile"),
                "WBP_MANAGED_DIR": str(root / "managed"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                setup_discovery = run_ui_action(runner, {"ui_action": "setup_discovery"})
        legacy_import = run_ui_action(runner, {"ui_action": "legacy_import"})

        self.assertEqual(setup_discovery["status"], "ok")
        self.assertEqual(setup_discovery["ui_action"], "setup_discovery")
        self.assertEqual(setup_discovery["result"]["machine_error_code"], "OK")
        self.assertEqual(setup_discovery["result"]["changed_files"], [])
        self.assertEqual(setup_discovery["result"]["data"]["discovery_state"], "none")
        self.assertEqual(setup_discovery["result"]["data"]["source_kind"], live_server.SETUP_DISCOVERY_SOURCE_KIND)
        self.assertFalse(setup_discovery["result"]["data"]["browser_path_intake"])
        self.assertFalse(setup_discovery["result"]["data"]["selection_persisted"])
        self.assertEqual(setup_discovery["result"]["data"]["candidate_marker_count"], 0)
        self.assertEqual(legacy_import["status"], "integration_failure")
        self.assertEqual(legacy_import["ui_action"], "legacy_import")
        self.assertEqual(legacy_import["availability_state"], "token_required")
        self.assertEqual(
            legacy_import["result"]["machine_error_code"],
            live_server.LEGACY_IMPORT_TOKEN_REQUIRED_CODE,
        )
        self.assertEqual(legacy_import["result"]["changed_files"], [])
        self.assertEqual(runner.calls, [])

    def test_setup_discovery_returns_discovered_packet_from_current_owned_runtime_layout(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(data_dir / "external-models"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                install_payload = run_installer_init(RuntimePaths.from_env())
                self.assertEqual(install_payload["status"], "ok")
                setup_discovery = run_ui_action(runner, {"ui_action": "setup_discovery"})

        self.assertEqual(setup_discovery["status"], "ok")
        self.assertEqual(setup_discovery["result"]["machine_error_code"], "OK")
        self.assertEqual(setup_discovery["result"]["data"]["discovery_state"], "discovered")
        self.assertGreater(setup_discovery["result"]["data"]["candidate_marker_count"], 0)
        self.assertFalse(setup_discovery["result"]["data"]["filesystem_mutation_performed"])
        self.assertFalse(setup_discovery["result"]["data"]["import_execution_claimed"])
        self.assertEqual(runner.calls, [])

    def test_legacy_import_discovery_returns_zero_write_none_packet_without_execution(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(root / "profile"),
                "WBP_MANAGED_DIR": str(root / "managed"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                legacy_discovery = run_ui_action(
                    runner, {"ui_action": "legacy_import_discovery"}
                )

        self.assertEqual(legacy_discovery["status"], "ok")
        self.assertEqual(legacy_discovery["ui_action"], "legacy_import_discovery")
        self.assertEqual(legacy_discovery["result"]["machine_error_code"], "OK")
        self.assertEqual(legacy_discovery["result"]["changed_files"], [])
        self.assertEqual(legacy_discovery["result"]["data"]["discovery_state"], "none")
        self.assertEqual(
            legacy_discovery["result"]["data"]["source_kind"],
            live_server.LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
        )
        self.assertFalse(legacy_discovery["result"]["data"]["browser_path_intake"])
        self.assertFalse(legacy_discovery["result"]["data"]["selection_persisted"])
        self.assertFalse(legacy_discovery["result"]["data"]["session_token_materialized"])
        self.assertFalse(
            legacy_discovery["result"]["data"]["current_runtime_layout_reused"]
        )
        self.assertEqual(legacy_discovery["result"]["data"]["candidate_marker_count"], 0)
        self.assertEqual(runner.calls, [])

    def test_legacy_import_discovery_returns_discovered_packet_from_known_owned_source(self) -> None:
        runner = MappingRunner(live_payloads())
        token_store = live_server.LegacyImportTokenStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir = root / ".codex-custom-cli"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            (candidate_dir / "backend-registry.json").write_text(
                json.dumps({"backends": []}) + "\n", encoding="utf-8"
            )
            (candidate_dir / "supervisor-state.json").write_text(
                json.dumps({"schema_version": 1}) + "\n", encoding="utf-8"
            )
            (candidate_dir / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
            (candidate_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(root / "profile"),
                "WBP_MANAGED_DIR": str(root / "managed"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                legacy_discovery = run_ui_action(
                    runner,
                    {"ui_action": "legacy_import_discovery"},
                    legacy_import_token_store=token_store,
                )

        self.assertEqual(legacy_discovery["status"], "ok")
        self.assertEqual(legacy_discovery["result"]["machine_error_code"], "OK")
        self.assertEqual(legacy_discovery["result"]["data"]["discovery_state"], "discovered")
        self.assertGreaterEqual(
            legacy_discovery["result"]["data"]["candidate_marker_count"], 4
        )
        self.assertFalse(
            legacy_discovery["result"]["data"]["filesystem_mutation_performed"]
        )
        self.assertFalse(legacy_discovery["result"]["data"]["import_execution_claimed"])
        self.assertTrue(legacy_discovery["result"]["data"]["session_token_materialized"])
        self.assertTrue(legacy_discovery["result"]["data"]["token_server_owned"])
        self.assertEqual(legacy_discovery["result"]["data"]["token_status"], "active")
        self.assertTrue(str(legacy_discovery["result"]["data"]["token_ref"]).startswith("lid-"))
        self.assertFalse(
            legacy_discovery["result"]["data"]["current_runtime_layout_reused"]
        )
        self.assertEqual(runner.calls, [])

    def test_legacy_import_discovery_blocks_current_runtime_layout_reuse(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir = root / ".codex-custom-cli"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(candidate_dir),
                "WBP_MANAGED_DIR": str(candidate_dir / "managed"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                legacy_discovery = run_ui_action(
                    runner, {"ui_action": "legacy_import_discovery"}
                )

        self.assertEqual(legacy_discovery["status"], "command_error")
        self.assertEqual(
            legacy_discovery["result"]["machine_error_code"],
            live_server.LEGACY_IMPORT_DISCOVERY_SOURCE_BLOCKED_CODE,
        )
        self.assertEqual(legacy_discovery["result"]["data"]["discovery_state"], "blocked")
        self.assertTrue(legacy_discovery["result"]["data"]["current_runtime_layout_reused"])
        self.assertFalse(legacy_discovery["result"]["data"]["browser_path_intake"])
        self.assertEqual(runner.calls, [])

    def test_legacy_import_discovery_rejects_browser_owned_path_fields(self) -> None:
        runner = MappingRunner(live_payloads())
        legacy_discovery = run_ui_action(
            runner,
            {
                "ui_action": "legacy_import_discovery",
                "source_dir": "/tmp/legacy-source",
                "source_path": "/tmp/legacy-source",
            },
        )

        self.assertEqual(legacy_discovery["status"], "integration_failure")
        self.assertEqual(
            legacy_discovery["result"]["machine_error_code"],
            "UI_LEGACY_IMPORT_DISCOVERY_BROWSER_PATH_FORBIDDEN",
        )
        self.assertEqual(
            legacy_discovery["availability_state"],
            live_server.LEGACY_IMPORT_DISCOVERY_AVAILABLE_STATE,
        )
        self.assertEqual(legacy_discovery["disabled_reasons"], ["browser_path_forbidden"])
        self.assertEqual(legacy_discovery["result"]["changed_files"], [])
        self.assertEqual(runner.calls, [])

    def test_legacy_import_accepts_only_server_owned_token_reference(self) -> None:
        runner = MappingRunner(live_payloads())
        token_store = live_server.LegacyImportTokenStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir = root / ".codex-custom-cli"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            (candidate_dir / "backend-registry.json").write_text(
                json.dumps({"backends": []}) + "\n", encoding="utf-8"
            )
            (candidate_dir / "supervisor-state.json").write_text(
                json.dumps({"schema_version": 1}) + "\n", encoding="utf-8"
            )
            (candidate_dir / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(root / "profile"),
                "WBP_MANAGED_DIR": str(root / "managed"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                discovery = run_ui_action(
                    runner,
                    {"ui_action": "legacy_import_discovery"},
                    legacy_import_token_store=token_store,
                )
                token_ref = str(discovery["result"]["data"]["token_ref"])
                legacy_import = run_ui_action(
                    runner,
                    {"ui_action": "legacy_import", "token_ref": token_ref},
                    legacy_import_token_store=token_store,
                )
                metadata = ui_action_metadata(legacy_import_token_store=token_store)

        self.assertEqual(legacy_import["status"], "ok")
        self.assertTrue(legacy_import["confirmation_required"])
        self.assertEqual(legacy_import["result"]["machine_error_code"], "OK")
        self.assertEqual(legacy_import["result"]["data"]["reference_state"], "import_capable")
        self.assertTrue(legacy_import["result"]["data"]["session_token_materialized"])
        self.assertTrue(legacy_import["result"]["data"]["token_server_owned"])
        self.assertEqual(legacy_import["result"]["data"]["token_ref"], token_ref)
        self.assertFalse(legacy_import["result"]["data"]["filesystem_mutation_performed"])
        self.assertFalse(legacy_import["result"]["data"]["import_execution_claimed"])
        self.assertFalse(legacy_import["result"]["data"]["confirm_semantics_claimed"])
        self.assertTrue(metadata["actions"]["legacy_import"]["available"])
        self.assertEqual(
            metadata["actions"]["legacy_import"]["availability_state"],
            "token_bound_import_capable",
        )
        self.assertEqual(runner.calls, [])

    def test_legacy_import_blocks_unknown_token_reference(self) -> None:
        runner = MappingRunner(live_payloads())
        token_store = live_server.LegacyImportTokenStore()
        legacy_import = run_ui_action(
            runner,
            {"ui_action": "legacy_import", "token_ref": "lid-unknown-token"},
            legacy_import_token_store=token_store,
        )

        self.assertEqual(legacy_import["status"], "command_error")
        self.assertEqual(
            legacy_import["result"]["machine_error_code"],
            live_server.LEGACY_IMPORT_TOKEN_UNKNOWN_CODE,
        )
        self.assertEqual(legacy_import["result"]["changed_files"], [])
        self.assertEqual(runner.calls, [])

    def test_legacy_import_rejects_browser_owned_source_fields(self) -> None:
        runner = MappingRunner(live_payloads())
        legacy_import = run_ui_action(
            runner,
            {
                "ui_action": "legacy_import",
                "token_ref": "lid-browser",
                "source_dir": "/tmp/legacy-source",
            },
        )

        self.assertEqual(legacy_import["status"], "integration_failure")
        self.assertEqual(
            legacy_import["result"]["machine_error_code"],
            "UI_LEGACY_IMPORT_BROWSER_FIELDS_FORBIDDEN",
        )
        self.assertEqual(legacy_import["availability_state"], "token_required")
        self.assertEqual(legacy_import["disabled_reasons"], ["browser_fields_forbidden"])
        self.assertEqual(runner.calls, [])

    def test_legacy_import_confirmed_token_executes_owner_import_and_consumes_token(self) -> None:
        runner = MappingRunner(live_payloads())
        token_store = live_server.LegacyImportTokenStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = root / "managed"
            profile_dir.mkdir(parents=True, exist_ok=True)
            managed_dir.mkdir(parents=True, exist_ok=True)
            candidate_dir = root / ".codex-custom-cli"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            source_registry = {
                "schema_version": 2,
                "version": 2,
                "updated_at": "2026-05-07T00:00:00+00:00",
                "stable_default_backend_id": "legacy-backend",
                "pool_policy": {"active_min": 1, "active_target": 1, "reserve_target": 0},
                "backends": [
                    {
                        "id": "legacy-backend",
                        "label": "Legacy",
                        "provider": "openai",
                        "auth_ref": "/tmp/legacy.json",
                        "pool": "active",
                    }
                ],
            }
            source_state = {
                "schema_version": 2,
                "version": 2,
                "status": "healthy",
                "effective_mode": "managed",
                "last_sync_at": "2026-05-07T00:00:00+00:00",
                "last_error": "",
                "selected_backend_ids": ["legacy-backend"],
                "managed_port": 9999,
                "current_proxy_url": "http://127.0.0.1:10808",
                "stable_default_backend_id": "legacy-backend",
                "active_count": 1,
                "reserve_count": 0,
                "retired_count": 0,
                "healthy_count": 1,
                "degraded_count": 0,
                "down_count": 0,
            }
            (candidate_dir / "backend-registry.json").write_text(
                json.dumps(source_registry) + "\n", encoding="utf-8"
            )
            (candidate_dir / "supervisor-state.json").write_text(
                json.dumps(source_state) + "\n", encoding="utf-8"
            )
            (candidate_dir / "runtime-mode.txt").write_text("managed\n", encoding="utf-8")
            (candidate_dir / "runtime-effective-mode.txt").write_text(
                "managed\n", encoding="utf-8"
            )
            (candidate_dir / "config.toml").write_text(
                'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:8320/v1"\n',
                encoding="utf-8",
            )
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(managed_dir),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                discovery = run_ui_action(
                    runner,
                    {"ui_action": "legacy_import_discovery"},
                    legacy_import_token_store=token_store,
                )
                token_ref = str(discovery["result"]["data"]["token_ref"])
                legacy_import = run_ui_action(
                    runner,
                    {
                        "ui_action": "legacy_import",
                        "token_ref": token_ref,
                        "confirmed": True,
                    },
                    legacy_import_token_store=token_store,
                )
                metadata_after = ui_action_metadata(
                    legacy_import_token_store=token_store
                )
                imported_registry = json.loads(
                    (managed_dir / "backend-registry.json").read_text(encoding="utf-8")
                )
                imported_state = json.loads(
                    (managed_dir / "supervisor-state.json").read_text(encoding="utf-8")
                )

        self.assertEqual(legacy_import["status"], "ok")
        self.assertTrue(legacy_import["mutates_runtime"])
        self.assertTrue(legacy_import["post_action_refresh_required"])
        self.assertEqual(legacy_import["result"]["machine_error_code"], "OK")
        self.assertEqual(
            legacy_import["result"]["data"]["reference_state"], "import_completed"
        )
        self.assertFalse(legacy_import["result"]["data"]["session_token_materialized"])
        self.assertEqual(legacy_import["result"]["data"]["token_status"], "consumed")
        self.assertTrue(legacy_import["result"]["data"]["filesystem_mutation_performed"])
        self.assertTrue(legacy_import["result"]["data"]["import_execution_claimed"])
        self.assertTrue(legacy_import["result"]["data"]["confirm_semantics_claimed"])
        self.assertTrue(legacy_import["result"]["data"]["explicit_confirm_observed"])
        self.assertEqual(legacy_import["result"]["data"]["receipt_state"], "write_completed")
        self.assertEqual(
            legacy_import["result"]["data"]["legacy_import_result"]["final_outcome"],
            "import_completed",
        )
        self.assertNotIn("source_dir", legacy_import["result"]["data"]["legacy_import_result"])
        self.assertGreater(len(legacy_import["result"]["changed_files"]), 0)
        self.assertEqual(imported_registry["stable_default_backend_id"], "legacy-backend")
        self.assertEqual(imported_state["selected_backend_ids"], ["legacy-backend"])
        self.assertFalse(metadata_after["actions"]["legacy_import"]["available"])
        self.assertEqual(
            metadata_after["actions"]["legacy_import"]["availability_state"],
            "token_required",
        )
        self.assertNotIn(str(candidate_dir), json.dumps(legacy_import, ensure_ascii=False))
        self.assertEqual(runner.calls, [])

    def test_legacy_import_confirmed_failure_reports_rollback_without_source_leak(self) -> None:
        runner = MappingRunner(live_payloads())
        token_store = live_server.LegacyImportTokenStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = root / "managed"
            profile_dir.mkdir(parents=True, exist_ok=True)
            managed_dir.mkdir(parents=True, exist_ok=True)
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(managed_dir),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                install_payload = run_installer_init(RuntimePaths.from_env())
                self.assertEqual(install_payload["status"], "ok")
                before_registry = (managed_dir / "backend-registry.json").read_text(
                    encoding="utf-8"
                )
                before_state = (managed_dir / "supervisor-state.json").read_text(
                    encoding="utf-8"
                )
                candidate_dir = root / ".codex-custom-cli"
                candidate_dir.mkdir(parents=True, exist_ok=True)
                (candidate_dir / "backend-registry.json").write_text(
                    before_registry,
                    encoding="utf-8",
                )
                (candidate_dir / "supervisor-state.json").write_text(
                    "{broken-json}\n",
                    encoding="utf-8",
                )
                (candidate_dir / "config.toml").write_text(
                    'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:8320/v1"\n',
                    encoding="utf-8",
                )
                discovery = run_ui_action(
                    runner,
                    {"ui_action": "legacy_import_discovery"},
                    legacy_import_token_store=token_store,
                )
                token_ref = str(discovery["result"]["data"]["token_ref"])
                legacy_import = run_ui_action(
                    runner,
                    {
                        "ui_action": "legacy_import",
                        "token_ref": token_ref,
                        "confirmed": True,
                    },
                    legacy_import_token_store=token_store,
                )
                after_registry = (managed_dir / "backend-registry.json").read_text(
                    encoding="utf-8"
                )
                after_state = (managed_dir / "supervisor-state.json").read_text(
                    encoding="utf-8"
                )
                metadata_after = ui_action_metadata(
                    legacy_import_token_store=token_store
                )

        self.assertEqual(legacy_import["status"], "command_error")
        self.assertIn(
            legacy_import["result"]["machine_error_code"],
            {"INVALID_JSON_FILE", "LEGACY_IMPORT_VERIFY_FAILED"},
        )
        self.assertEqual(legacy_import["result"]["data"]["reference_state"], "write_failed")
        self.assertTrue(legacy_import["result"]["data"]["import_execution_claimed"])
        self.assertTrue(legacy_import["result"]["data"]["confirm_semantics_claimed"])
        self.assertEqual(legacy_import["result"]["data"]["receipt_state"], "write_failed")
        self.assertEqual(
            legacy_import["result"]["data"]["legacy_import_result"]["final_outcome"],
            "rollback_completed_after_failed_import",
        )
        self.assertTrue(
            legacy_import["result"]["data"]["legacy_import_result"]["rollback_attempted"]
        )
        self.assertEqual(
            legacy_import["result"]["data"]["legacy_import_result"]["rollback_outcome"],
            "completed",
        )
        self.assertNotIn("source_dir", legacy_import["result"]["data"]["legacy_import_result"])
        self.assertEqual(before_registry, after_registry)
        self.assertEqual(before_state, after_state)
        self.assertFalse(metadata_after["actions"]["legacy_import"]["available"])
        self.assertNotIn(str(candidate_dir), json.dumps(legacy_import, ensure_ascii=False))
        self.assertEqual(runner.calls, [])

    def test_http_legacy_import_token_persists_across_action_requests(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir = root / ".codex-custom-cli"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            (candidate_dir / "backend-registry.json").write_text(
                json.dumps({"backends": []}) + "\n", encoding="utf-8"
            )
            (candidate_dir / "supervisor-state.json").write_text(
                json.dumps({"schema_version": 1}) + "\n", encoding="utf-8"
            )
            (candidate_dir / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(root / "profile"),
                "WBP_MANAGED_DIR": str(root / "managed"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(runner=runner, action_phase=FULL_ACTION_PHASE),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_address[1]}"
                try:
                    discovery = json.loads(
                        post_json(f"{base}/api/action", {"ui_action": "legacy_import_discovery"})
                    )
                    token_ref = str(discovery["result"]["data"]["token_ref"])
                    metadata = json.loads(fetch(f"{base}/api/actions"))
                    legacy_import = json.loads(
                        post_json(
                            f"{base}/api/action",
                            {"ui_action": "legacy_import", "token_ref": token_ref},
                        )
                    )
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)

        self.assertEqual(discovery["status"], "ok")
        self.assertTrue(discovery["result"]["data"]["session_token_materialized"])
        self.assertTrue(metadata["actions"]["legacy_import"]["available"])
        self.assertEqual(
            metadata["actions"]["legacy_import"]["availability_state"],
            "token_bound_import_capable",
        )
        self.assertEqual(legacy_import["status"], "ok")
        self.assertEqual(legacy_import["result"]["data"]["token_ref"], token_ref)
        self.assertEqual(runner.calls, [])

    def test_http_legacy_import_confirmed_token_consumes_handler_store(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir = root / ".codex-custom-cli"
            profile_dir = root / "profile"
            managed_dir = root / "managed"
            profile_dir.mkdir(parents=True, exist_ok=True)
            managed_dir.mkdir(parents=True, exist_ok=True)
            candidate_dir.mkdir(parents=True, exist_ok=True)
            (candidate_dir / "backend-registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "version": 2,
                        "updated_at": "2026-05-07T00:00:00+00:00",
                        "stable_default_backend_id": "legacy-backend",
                        "pool_policy": {"active_min": 1, "active_target": 1, "reserve_target": 0},
                        "backends": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (candidate_dir / "supervisor-state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "version": 2,
                        "status": "healthy",
                        "effective_mode": "managed",
                        "selected_backend_ids": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (candidate_dir / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
            env_updates = {
                "HOME": str(root),
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(managed_dir),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(runner=runner, action_phase=FULL_ACTION_PHASE),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_address[1]}"
                try:
                    discovery = json.loads(
                        post_json(f"{base}/api/action", {"ui_action": "legacy_import_discovery"})
                    )
                    token_ref = str(discovery["result"]["data"]["token_ref"])
                    metadata_before = json.loads(fetch(f"{base}/api/actions"))
                    confirmed = json.loads(
                        post_json(
                            f"{base}/api/action",
                            {
                                "ui_action": "legacy_import",
                                "token_ref": token_ref,
                                "confirmed": True,
                            },
                        )
                    )
                    metadata_after = json.loads(fetch(f"{base}/api/actions"))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)

        self.assertTrue(metadata_before["actions"]["legacy_import"]["available"])
        self.assertEqual(confirmed["status"], "ok")
        self.assertTrue(confirmed["result"]["data"]["import_execution_claimed"])
        self.assertFalse(metadata_after["actions"]["legacy_import"]["available"])
        self.assertEqual(
            metadata_after["actions"]["legacy_import"]["availability_state"],
            "token_required",
        )
        self.assertEqual(runner.calls, [])

    def test_setup_discovery_blocks_relative_server_owned_runtime_paths(self) -> None:
        runner = MappingRunner(live_payloads())
        env_updates = {
            "WBP_PROFILE_DIR": "relative-profile",
            "WBP_MANAGED_DIR": "relative-managed",
        }
        with mock.patch.dict(os.environ, env_updates, clear=False):
            setup_discovery = run_ui_action(runner, {"ui_action": "setup_discovery"})

        self.assertEqual(setup_discovery["status"], "command_error")
        self.assertEqual(
            setup_discovery["result"]["machine_error_code"],
            live_server.SETUP_DISCOVERY_SOURCE_BLOCKED_CODE,
        )
        self.assertEqual(setup_discovery["result"]["data"]["discovery_state"], "blocked")
        self.assertFalse(setup_discovery["result"]["data"]["browser_path_intake"])
        self.assertEqual(runner.calls, [])

    def test_http_actions_endpoint_reports_sandbox_phase_and_opens_only_admitted_actions(self) -> None:
        runner = MappingRunner(live_payloads())
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                runner=runner,
                launch_copy_contract=launch_copy_contract(),
                action_phase=SANDBOX_ACTION_PHASE,
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            metadata = json.loads(fetch(f"{base_url}/api/actions"))
            onboard_preview = json.loads(post_json(f"{base_url}/api/action", {"ui_action": "onboard_account_dry_run"}))
            validate = json.loads(
                post_json(
                    f"{base_url}/api/action",
                    {"ui_action": "validate_account", "account_id": "acct-active"},
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(metadata["action_phase"], SANDBOX_ACTION_PHASE)
        self.assertEqual(metadata["sandbox_preflight"]["status"], "admitted")
        self.assertTrue(metadata["actions"]["onboard_account_dry_run"]["available"])
        self.assertTrue(metadata["actions"]["onboard_account"]["available"])
        self.assertTrue(metadata["actions"]["api_route_check"]["available"])
        self.assertFalse(metadata["actions"]["validate_account"]["available"])
        self.assertEqual(
            metadata["actions"]["validate_account"]["disabled_reason_code"],
            "UI_ACTION_PHASE_NOT_ADMITTED",
        )
        self.assertEqual(onboard_preview["status"], "ok")
        self.assertEqual(onboard_preview["ui_action"], "onboard_account_dry_run")
        self.assertTrue(onboard_preview["result"]["onboarding"]["preview_only"])
        self.assertEqual(validate["status"], "integration_failure")
        self.assertEqual(validate["result"]["machine_error_code"], "UI_ACTION_PHASE_NOT_ADMITTED")

    def test_sandbox_phase_keeps_actions_disabled_when_target_is_unproven(self) -> None:
        metadata = ui_action_metadata(
            launch_copy_contract=LaunchCopyContract(
                profile_dir="/tmp/wbp-copy-profile",
                data_dir="/tmp/wbp-copy-data",
                copy_port=8788,
                action_server_port=8788,
            ),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(metadata["sandbox_preflight"]["status"], "denied")
        self.assertFalse(metadata["actions"]["onboard_account_dry_run"]["available"])
        self.assertEqual(
            metadata["actions"]["onboard_account_dry_run"]["availability_state"],
            "preflight_blocked",
        )
        self.assertEqual(
            metadata["actions"]["onboard_account_dry_run"]["disabled_reason_code"],
            "UI_SANDBOX_ACTION_TARGET_UNPROVEN",
        )

    def test_quick_start_check_all_runs_verify_only_bundle_in_sandbox(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "status", "--json")]["data"]["local_auth"]["token_present"] = True  # type: ignore[index]
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[
                account("acct-active", "active", "healthy"),
                account("acct-reserve", "reserve", "healthy"),
            ]
        )
        runner = MappingRunner(payloads)

        result = run_ui_action(
            runner,
            {"ui_action": "quick_start_check_all"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "quick_start_verify_bundle")
        self.assertFalse(result["confirmation_required"])
        self.assertTrue(result["post_action_refresh_required"])
        self.assertEqual(result["result"]["machine_error_code"], "OK")
        self.assertEqual(result["result"]["data"]["bundle_verdict"], "ready")
        self.assertTrue(result["result"]["data"]["hidden_mutation_absent"])
        self.assertEqual(result["result"]["data"]["bundle"]["accounts"]["status"], "ok")
        self.assertEqual(result["result"]["data"]["bundle"]["api"]["status"], "ok")
        self.assertEqual(result["result"]["data"]["bundle"]["runtime"]["status"], "ok")
        self.assertEqual(
            result["result"]["data"]["api_check_packet"]["machine_error_code"],
            "OK",
        )
        self.assertNotIn(("sync", "--json"), runner.calls)
        self.assertNotIn(("accounts", "onboard", "--json"), runner.calls)
        self.assertNotIn(("mode", "set", "stable", "--json"), runner.calls)
        self.assertNotIn(("mode", "set", "managed", "--json"), runner.calls)
        self.assertIn(("external-models", "check", "--route", "wbp-deepseek-v3", "--json"), runner.calls)

    def test_quick_start_check_all_maps_runtime_degraded_to_partial(self) -> None:
        payloads = live_payloads()
        payloads[("healthcheck", "--json")] = command_packet(
            status="error",
            machine_error_code="provider_network_failed",
            human_message="Network failed.",
        )
        runner = MappingRunner(payloads)

        result = run_ui_action(
            runner,
            {"ui_action": "quick_start_check_all"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "partial_success")
        self.assertEqual(result["result"]["machine_error_code"], "UI_CHECK_ALL_PARTIAL")
        self.assertEqual(result["result"]["data"]["bundle_verdict"], "partial")
        self.assertEqual(result["result"]["data"]["bundle"]["runtime"]["status"], "partial")

    def test_onboard_account_action_starts_codex_login_session_without_browser_args(self) -> None:
        runner = MappingRunner(live_payloads())

        result = run_ui_action(
            runner,
            {"ui_action": "onboard_account"},
            launch_copy_contract=LaunchCopyContract(
                profile_dir="/tmp/wbp-copy-profile",
                data_dir="/tmp/wbp-copy-data",
                copy_port=8789,
                action_server_port=8788,
            ),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "account_onboarding")
        self.assertEqual(result["mutation_class"], "account_admission")
        self.assertFalse(result["mutates_runtime"])
        self.assertFalse(result["affects_primary_truth"])
        self.assertTrue(result["confirmation_required"])
        self.assertFalse(result["post_action_refresh_required"])
        self.assertEqual(result["account_id"], "")
        self.assertNotIn("onboarding", result["result"])
        self.assertEqual(result["session_id"], TEST_CODEX_LOGIN_SESSION_ID)
        self.assertEqual(result["result"]["data"]["login_bridge"]["status"], "waiting_for_user")
        self.assertEqual(result["result"]["data"]["login_bridge"]["provider"], "codex")
        self.assertEqual(result["result"]["data"]["login_bridge"]["mode"], "device")
        self.assertTrue(result["result"]["data"]["login_bridge"]["login_session_id_present"])
        self.assertTrue(result["result"]["data"]["login_bridge"]["login_url_present"])
        self.assertEqual(result["result"]["data"]["login_bridge"]["device_url"], TEST_CODEX_DEVICE_URL)
        self.assertEqual(result["result"]["data"]["login_bridge"]["device_code"], TEST_CODEX_DEVICE_CODE)
        self.assertFalse(result["result"]["data"]["login_bridge"]["browser_secret_intake"])
        serialized_result = json.dumps(result)
        self.assertNotIn(TEST_SANDBOX_AUTH_REF, serialized_result)
        self.assertNotIn("/tmp/wbp-sandbox-auth.json", serialized_result)
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "list", "--json"),
                (
                    "accounts",
                    "login",
                    "start",
                    "--provider",
                    "codex",
                    "--mode",
                    "device",
                    "--json",
                ),
            ],
        )

    def test_onboard_account_uses_codex_owner_lane_not_sandbox_synthetic_bridge(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
            }
        )

        result = run_ui_action(
            runner,
            {"ui_action": "onboard_account"},
            launch_copy_contract=LaunchCopyContract(
                profile_dir="/tmp/wbp-copy-profile",
                data_dir="/tmp/wbp-copy-data",
                copy_port=8789,
                action_server_port=8788,
            ),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["data"]["login_bridge"]["provider"], "codex")
        self.assertNotIn(
            ("accounts", "login", "start", "--provider", "sandbox", "--json"),
            runner.calls,
        )
        self.assertNotIn(
            (
                "accounts",
                "onboard",
                "--json",
            ),
            runner.calls,
        )

    def test_onboard_account_codex_owner_lane_failure_is_non_green(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
                (
                    "accounts",
                    "login",
                    "start",
                    "--provider",
                    "codex",
                    "--mode",
                    "device",
                    "--json",
                ): codex_login_start_packet(
                    status="error",
                    machine_error_code="LOGIN_DEVICE_HANDOFF_MISSING",
                    login_result={
                        "status": "failed",
                        "provider": "codex",
                        "mode": "device",
                        "session_id": TEST_CODEX_LOGIN_SESSION_ID,
                        "login_session_id": TEST_CODEX_LOGIN_SESSION_ID,
                        "device_url": "",
                        "device_code_present": False,
                        "auth_materialized": False,
                        "auth_ref_present": False,
                    },
                ),
            }
        )

        result = run_ui_action(
            runner,
            {"ui_action": "onboard_account"},
            launch_copy_contract=LaunchCopyContract(
                profile_dir="/tmp/wbp-copy-profile",
                data_dir="/tmp/wbp-copy-data",
                copy_port=8789,
                action_server_port=8788,
            ),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "command_error")
        self.assertEqual(
            result["result"]["machine_error_code"],
            "LOGIN_DEVICE_HANDOFF_MISSING",
        )
        self.assertEqual(result["result"]["data"]["login_bridge"]["provider"], "codex")
        self.assertEqual(result["result"]["data"]["login_bridge"]["status"], "failed")

    def test_account_login_status_action_executes_exact_command(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
                (
                    "accounts",
                    "login",
                    "status",
                    "--session",
                    TEST_CODEX_LOGIN_SESSION_ID,
                    "--json",
                ): codex_login_status_packet(effect=EFFECT_READ),
            }
        )

        result = run_ui_action(
            runner,
            {"ui_action": "account_login_status", "session_id": TEST_CODEX_LOGIN_SESSION_ID},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["session_id"], TEST_CODEX_LOGIN_SESSION_ID)
        self.assertEqual(live_server.UI_ACTION_EFFECT_REGISTRY["account_login_status"], EFFECT_READ)
        self.assertEqual(result["result"]["command_effect"], EFFECT_READ)
        self.assertEqual(result["result"]["data"]["login_bridge"]["status"], "auth_materialized")
        self.assertEqual(
            runner.calls,
            [("accounts", "login", "status", "--session", TEST_CODEX_LOGIN_SESSION_ID, "--json")],
        )

    def test_account_login_complete_action_executes_exact_command_and_returns_onboarding(self) -> None:
        runner = MappingRunner(live_payloads())

        result = run_ui_action(
            runner,
            {"ui_action": "account_login_complete", "session_id": TEST_CODEX_LOGIN_SESSION_ID},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["post_action_refresh_required"])
        self.assertEqual(result["session_id"], TEST_CODEX_LOGIN_SESSION_ID)
        self.assertEqual(result["result"]["data"]["login_bridge"]["status"], "completed")
        self.assertEqual(
            result["result"]["onboarding"]["final_outcome"],
            "explicit_auth_imported_to_reserve",
        )
        self.assertEqual(
            runner.calls,
            [("accounts", "login", "complete", "--session", TEST_CODEX_LOGIN_SESSION_ID, "--json")],
        )

    def test_account_login_cancel_action_executes_exact_command(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "login", "cancel", "--session", TEST_CODEX_LOGIN_SESSION_ID, "--json"): command_packet(
                    human_message="Codex login session cancelled.",
                    provider="codex",
                    session_id=TEST_CODEX_LOGIN_SESSION_ID,
                    login_session_id=TEST_CODEX_LOGIN_SESSION_ID,
                    login_result={
                        "status": "cancelled",
                        "provider": "codex",
                        "mode": "device",
                        "session_id": TEST_CODEX_LOGIN_SESSION_ID,
                        "login_session_id": TEST_CODEX_LOGIN_SESSION_ID,
                        "used": False,
                    },
                ),
            }
        )

        result = run_ui_action(
            runner,
            {"ui_action": "account_login_cancel", "session_id": TEST_CODEX_LOGIN_SESSION_ID},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["session_id"], TEST_CODEX_LOGIN_SESSION_ID)
        self.assertEqual(result["result"]["data"]["login_bridge"]["status"], "cancelled")
        self.assertEqual(
            runner.calls,
            [("accounts", "login", "cancel", "--session", TEST_CODEX_LOGIN_SESSION_ID, "--json")],
        )

    def test_real_json_runner_supports_codex_login_session_bridge_from_profile_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            auth_dir = data_dir / "device-login-auth"
            fake_cli = root / "fake-device-cli-proxy.py"
            argv_capture = data_dir / "device-login-argv.json"
            ready_file = data_dir / "device-login.ready"
            auth_ref = auth_dir / "codex-device-login.json"
            write_test_device_login_cli_proxy(
                fake_cli,
                argv_capture_path=argv_capture,
                ready_file=ready_file,
                auth_filename=auth_ref.name,
            )
            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(data_dir / "external-models"),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                paths = RuntimePaths.from_env()
                install_payload = run_installer_init(paths)
            self.assertEqual(install_payload["status"], "ok")
            stable_port = free_port()
            (data_dir / "stable-runtime-config.yaml").write_text(
                f'host: 127.0.0.1\nport: {stable_port}\nauth-dir: "device-login-auth"\n',
                encoding="utf-8",
            )
            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9341,
                action_server_port=9340,
            )
            from wild_boar_proxy.ui_shell import JsonCommandRunner

            sandbox_env = _sandbox_action_runner_env(contract)
            expected_sandbox_paths = {
                "WBP_PROFILE_DIR": profile_dir,
                "WBP_MANAGED_DIR": data_dir,
                "WBP_STABLE_CONFIG": data_dir / "stable-runtime-config.yaml",
                "WBP_AUTH_FILE": profile_dir / "auth.json",
                "WBP_CONFIG_TOML": profile_dir / "config.toml",
                "WBP_RUNTIME_MODE_FILE": profile_dir / "runtime-mode.txt",
                "WBP_RUNTIME_EFFECTIVE_MODE_FILE": profile_dir / "runtime-effective-mode.txt",
                "WBP_REGISTRY_FILE": data_dir / "backend-registry.json",
                "WBP_STATE_FILE": data_dir / "supervisor-state.json",
                "WBP_MANAGED_CONFIG_FILE": data_dir / "managed-config.yaml",
                "WBP_SYNC_SCRIPT": data_dir / "supervisor-sync.sh",
                "WBP_ACCOUNTS_BIN": data_dir / "bin" / "codex-accounts",
                "WBP_ONBOARD_BIN": data_dir / "bin" / "codex-account-onboard",
                "WBP_LOCK_FILE": data_dir / "wild-boar-proxy.lock",
                "WBP_LAUNCHER_LOCK_FILE": data_dir / "stable-runtime-launch.lock",
                "WBP_EXTERNAL_MODELS_DIR": data_dir / "external-models",
            }
            for key, expected in expected_sandbox_paths.items():
                self.assertEqual(sandbox_env[key], str(expected), key)
            self.assertEqual(sandbox_env["WBP_REQUIRE_SANDBOX_AUTH_DIR"], "1")
            sandbox_env["WBP_CLIPROXY_BIN"] = str(fake_cli)
            sandbox_env["WBP_TEST_DEVICE_LOGIN_WAIT_SECONDS"] = "10"
            sandbox_env["WBP_TEST_ONBOARD_ADDED_BACKENDS_JSON"] = json.dumps(
                [
                    account(
                        "acct-device-login",
                        "reserve",
                        "healthy",
                        auth_ref=str(auth_ref),
                    )
                ]
            )

            runner = JsonCommandRunner(
                cwd=str(profile_dir),
                env=sandbox_env,
            )

            readonly_before = build_accounts_readonly_snapshot(runner)
            self.assertEqual(readonly_before["status"], "ok")
            self.assertEqual(readonly_before["accounts"], [])
            self.assertEqual(readonly_before["registry_identity"]["status"], "clear")

            stable_server = ThreadingHTTPServer(
                ("127.0.0.1", stable_port), StableProbeHandler
            )
            stable_thread = threading.Thread(target=stable_server.serve_forever, daemon=True)
            stable_thread.start()
            try:
                started = run_ui_action(
                    runner,
                    {"ui_action": "onboard_account"},
                    launch_copy_contract=contract,
                    action_phase=SANDBOX_ACTION_PHASE,
                )
                self.assertEqual(started["status"], "ok")
                session_id = started["session_id"]
                self.assertTrue(session_id.startswith("codex-"))
                ready_file.write_text("ready\n", encoding="utf-8")

                status = run_ui_action(
                    runner,
                    {"ui_action": "account_login_status", "session_id": session_id},
                    launch_copy_contract=contract,
                    action_phase=SANDBOX_ACTION_PHASE,
                )
                deadline = time.time() + 5
                while status["result"]["data"]["login_bridge"]["status"] != "auth_materialized" and time.time() < deadline:
                    time.sleep(0.05)
                    status = run_ui_action(
                        runner,
                        {"ui_action": "account_login_status", "session_id": session_id},
                        launch_copy_contract=contract,
                        action_phase=SANDBOX_ACTION_PHASE,
                    )
                self.assertEqual(status["result"]["data"]["login_bridge"]["status"], "auth_materialized")
                result = run_ui_action(
                    runner,
                    {"ui_action": "account_login_complete", "session_id": session_id},
                    launch_copy_contract=contract,
                    action_phase=SANDBOX_ACTION_PHASE,
                )
            finally:
                stable_server.shutdown()
                stable_server.server_close()
                stable_thread.join(timeout=5)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(
                result["result"]["onboarding"]["final_outcome"],
                "explicit_auth_imported_to_reserve",
            )
            self.assertTrue(result["result"]["onboarding"]["reserve_first_proven"])
            self.assertEqual(
                result["result"]["data"]["login_bridge"]["status"],
                "completed",
            )
            selected_backend_id = result["result"]["onboarding"]["selected_backend_id"]
            self.assertTrue(selected_backend_id)
            self.assertEqual(
                json.loads(argv_capture.read_text(encoding="utf-8")),
                [
                    "-config",
                    str(data_dir / "stable-runtime-config.yaml"),
                    "-codex-device-login",
                    "-no-browser",
                ],
            )

            readonly_after = build_accounts_readonly_snapshot(runner)
            self.assertEqual(readonly_after["status"], "ok")
            self.assertEqual(len(readonly_after["accounts"]), 1)
            self.assertEqual(readonly_after["accounts"][0]["id"], selected_backend_id)
            self.assertEqual(readonly_after["accounts"][0]["pool"], "reserve")

    def test_real_json_runner_supports_sandbox_api_route_allow_from_profile_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            external_dir = data_dir / "external-models"
            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(external_dir),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                paths = RuntimePaths.from_env()
                install_payload = run_installer_init(paths)
            self.assertEqual(install_payload["status"], "ok")

            routes_path = external_dir / "routes.json"
            routes_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "routes": [
                            external_route("wbp-deepseek-v3", enabled=True, display_name="DeepSeek V3"),
                            external_route("wbp-disabled", enabled=False, display_name="Disabled Route"),
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            secrets_path = external_dir / "secrets.env"
            secrets_path.write_text("OPENROUTER_API_KEY=test-key\n", encoding="utf-8")
            os.chmod(secrets_path, 0o600)

            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9343,
                action_server_port=9342,
            )
            from wild_boar_proxy.ui_shell import JsonCommandRunner

            runner = JsonCommandRunner(
                cwd=str(profile_dir),
                env=_sandbox_action_runner_env(contract),
            )

            readonly_before = build_api_connections_readonly_snapshot(runner)
            self.assertEqual(readonly_before["status"], "ok")
            before_disabled = next(
                route for route in readonly_before["routes"] if route["route_id"] == "wbp-disabled"
            )
            self.assertFalse(before_disabled["enabled"])

            result = run_ui_action(
                runner,
                {"ui_action": "api_route_allow", "route_id": "wbp-disabled"},
                launch_copy_contract=contract,
                action_phase=SANDBOX_ACTION_PHASE,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["action_role"], "api_route_lifecycle_allow")
            self.assertEqual(result["route_id"], "wbp-disabled")
            self.assertEqual(result["result"]["machine_error_code"], "OK")
            self.assertIn(
                str(routes_path.resolve()),
                [str(Path(item).resolve()) for item in result["result"]["changed_files"]],
            )

            readonly_after = build_api_connections_readonly_snapshot(runner)
            self.assertEqual(readonly_after["status"], "ok")
            after_disabled = next(
                route for route in readonly_after["routes"] if route["route_id"] == "wbp-disabled"
            )
            self.assertTrue(after_disabled["enabled"])
            self.assertFalse(readonly_after["adapter"]["profile_ready"])
            self.assertTrue(readonly_after["adapter"]["runtime_claim_blocked"])

    def test_api_route_connect_creates_server_owned_route_without_browser_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            route_spec_path = (
                data_dir
                / "external-models"
                / "server-owned-route-specs"
                / "wbp-web-primary-openrouter.json"
            )
            payloads = live_payloads()
            payloads[("external-models", "routes", "list", "--json")] = command_packet(
                human_message="External-models routes listed from local registry.",
                data={"count": 0, "routes": []},
            )
            payloads[("external-models", "models", "--json")] = command_packet(
                human_message="External-models route models listed from local registry.",
                data={
                    "count": 0,
                    "source": "local_routes_registry",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "models": [],
                },
            )
            payloads[
                (
                    "external-models",
                    "routes",
                    "add",
                    "--file",
                    str(route_spec_path),
                    "--json",
                )
            ] = command_packet(
                human_message="External-models route added: wbp-web-primary-openrouter.",
                changed_files=[str(data_dir / "external-models" / "routes.json")],
                data={"route_id": "wbp-web-primary-openrouter"},
            )
            payloads[
                (
                    "external-models",
                    "routes",
                    "validate",
                    "--route",
                    "wbp-web-primary-openrouter",
                    "--json",
                )
            ] = command_packet(
                human_message="External-models route validation captured provider evidence without claiming runtime readiness.",
                data={
                    "route_id": "wbp-web-primary-openrouter",
                    "route_state": "model_visible",
                    "verification_scope": "route_provider_only",
                },
            )
            runner = MappingRunner(payloads)
            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9345,
                action_server_port=9344,
            )

            result = run_ui_action(
                runner,
                {"ui_action": "api_route_connect"},
                launch_copy_contract=contract,
                action_phase=SANDBOX_ACTION_PHASE,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["action_role"], "api_route_admission")
            self.assertEqual(result["mutation_class"], "api_route_registry_admission")
            self.assertEqual(result["route_id"], "")
            self.assertEqual(result["result"]["data"]["route_id"], "wbp-web-primary-openrouter")
            self.assertEqual(result["result"]["data"]["api_route_connect_phase"], "created_and_validated")
            self.assertEqual(result["result"]["data"]["admission_mode"], "create")
            self.assertEqual(result["result"]["data"]["credential_phase"], "credential_present")
            self.assertTrue(result["result"]["data"]["credential_present"])
            self.assertFalse(result["result"]["data"]["credential_admitted"])
            self.assertEqual(result["result"]["data"]["credential_ref"], "OPENROUTER_API_KEY")
            self.assertFalse(result["result"]["data"]["browser_secret_intake"])
            self.assertFalse(result["result"]["data"]["browser_path_intake"])
            self.assertFalse(result["result"]["data"]["browser_route_id_intake"])
            self.assertFalse(result["result"]["data"]["browser_api_key_intake"])
            self.assertFalse(result["result"]["data"]["secret_value_exposed"])
            self.assertFalse(result["result"]["data"]["route_spec_path_exposed"])
            self.assertEqual(result["result"]["changed_files"], ["api_route_connect_artifact"])
            serialized = json.dumps(result)
            self.assertNotIn(str(route_spec_path), serialized)
            self.assertNotIn(str(data_dir), serialized)
            self.assertNotIn("admit-owner-env-key", serialized)
            self.assertTrue(route_spec_path.exists())
            route_spec = json.loads(route_spec_path.read_text(encoding="utf-8"))
            self.assertEqual(route_spec["route_id"], "wbp-web-primary-openrouter")
            self.assertEqual(route_spec["auth"]["secret_ref"], "OPENROUTER_API_KEY")
            self.assertEqual(
                runner.calls,
                [
                    ("external-models", "status", "--json"),
                    ("external-models", "models", "--json"),
                    ("external-models", "routes", "list", "--json"),
                    ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
                    (
                        "external-models",
                        "routes",
                        "add",
                        "--file",
                        str(route_spec_path),
                        "--json",
                    ),
                    (
                        "external-models",
                        "routes",
                        "validate",
                        "--route",
                        "wbp-web-primary-openrouter",
                        "--json",
                    ),
                ],
            )

    def test_api_route_connect_can_create_direct_deepseek_server_owned_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            route_spec_path = (
                data_dir
                / "external-models"
                / "server-owned-route-specs"
                / "wbp-web-primary-deepseek.json"
            )
            payloads = live_payloads()
            payloads[("external-models", "routes", "list", "--json")] = command_packet(
                human_message="External-models routes listed from local registry.",
                data={"count": 0, "routes": []},
            )
            payloads[("external-models", "models", "--json")] = command_packet(
                human_message="External-models route models listed from local registry.",
                data={
                    "count": 0,
                    "source": "local_routes_registry",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "models": [],
                },
            )
            payloads[
                ("external-models", "credentials", "status", "--provider", "deepseek", "--json")
            ] = credential_status_packet(
                present=True,
                provider="deepseek",
                credential_ref="DEEPSEEK_API_KEY",
                expected_refs=["DEEPSEEK_API_KEY"],
                provider_dashboard_url="https://platform.deepseek.com/api_keys",
            )
            payloads[
                (
                    "external-models",
                    "routes",
                    "add",
                    "--file",
                    str(route_spec_path),
                    "--json",
                )
            ] = command_packet(
                human_message="External-models route added: wbp-web-primary-deepseek.",
                changed_files=[str(data_dir / "external-models" / "routes.json")],
                data={"route_id": "wbp-web-primary-deepseek"},
            )
            payloads[
                (
                    "external-models",
                    "routes",
                    "validate",
                    "--route",
                    "wbp-web-primary-deepseek",
                    "--json",
                )
            ] = command_packet(
                human_message="External-models route validation captured provider evidence without claiming runtime readiness.",
                data={
                    "route_id": "wbp-web-primary-deepseek",
                    "route_state": "model_visible",
                    "verification_scope": "route_provider_only",
                    "requested_model": "wbp-web-primary-deepseek",
                    "effective_model": "deepseek-chat",
                    "provider": "deepseek",
                },
            )
            runner = MappingRunner(payloads)
            runner._env = {
                "WBP_SERVER_OWNED_API_ROUTE_ID": "wbp-web-primary-deepseek",
                "WBP_SERVER_OWNED_API_ROUTE_PROVIDER": "deepseek",
                "WBP_SERVER_OWNED_API_ROUTE_DISPLAY_NAME": "DeepSeek primary",
                "WBP_SERVER_OWNED_API_ROUTE_BASE_URL": "https://api.deepseek.com",
                "WBP_SERVER_OWNED_API_ROUTE_ENDPOINT_PATH": "/chat/completions",
                "WBP_SERVER_OWNED_API_ROUTE_MODEL": "deepseek-chat",
                "WBP_SERVER_OWNED_API_ROUTE_SECRET_REF": "DEEPSEEK_API_KEY",
            }
            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9345,
                action_server_port=9344,
            )

            result = run_ui_action(
                runner,
                {"ui_action": "api_route_connect"},
                launch_copy_contract=contract,
                action_phase=SANDBOX_ACTION_PHASE,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["action_role"], "api_route_admission")
            self.assertEqual(result["result"]["data"]["route_id"], "wbp-web-primary-deepseek")
            self.assertEqual(result["result"]["data"]["credential_provider"], "deepseek")
            self.assertEqual(result["result"]["data"]["credential_ref"], "DEEPSEEK_API_KEY")
            self.assertEqual(result["result"]["data"]["api_route_connect_phase"], "created_and_validated")
            self.assertEqual(result["result"]["data"]["validate_machine_error_code"], "OK")
            self.assertFalse(result["result"]["data"]["browser_secret_intake"])
            self.assertFalse(result["result"]["data"]["browser_path_intake"])
            self.assertFalse(result["result"]["data"]["browser_route_id_intake"])
            self.assertFalse(result["result"]["data"]["browser_api_key_intake"])
            self.assertFalse(result["result"]["data"]["secret_value_exposed"])
            serialized = json.dumps(result)
            self.assertNotIn(str(route_spec_path), serialized)
            self.assertNotIn(str(data_dir), serialized)
            self.assertNotIn("deepseek-owner-key", serialized)
            self.assertTrue(route_spec_path.exists())
            route_spec = json.loads(route_spec_path.read_text(encoding="utf-8"))
            self.assertEqual(route_spec["route_id"], "wbp-web-primary-deepseek")
            self.assertEqual(route_spec["provider"], "deepseek")
            self.assertEqual(route_spec["auth"]["secret_ref"], "DEEPSEEK_API_KEY")
            self.assertFalse(route_spec["fallback_eligible"])
            self.assertIn(
                ("external-models", "credentials", "status", "--provider", "deepseek", "--json"),
                runner.calls,
            )
            self.assertNotIn(
                ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
                runner.calls,
            )

    def test_api_route_connect_adopts_existing_primary_route_without_add(self) -> None:
        payloads = live_payloads()
        runner = MappingRunner(payloads)
        contract = launch_copy_contract()

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_connect"},
            launch_copy_contract=contract,
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "api_route_admission")
        self.assertEqual(result["mutation_class"], "api_route_registry_admission")
        self.assertEqual(result["result"]["machine_error_code"], "OK")
        self.assertEqual(result["result"]["changed_files"], ["api_route_connect_artifact"])
        self.assertEqual(result["result"]["data"]["route_id"], "wbp-deepseek-v3")
        self.assertEqual(result["result"]["data"]["api_route_connect_phase"], "adopted_existing_route")
        self.assertEqual(result["result"]["data"]["admission_mode"], "adopt")
        self.assertEqual(result["result"]["data"]["credential_phase"], "credential_present")
        self.assertTrue(result["result"]["data"]["credential_present"])
        self.assertFalse(result["result"]["data"]["credential_admitted"])
        self.assertEqual(result["result"]["data"]["add_status"], "not_run")
        self.assertEqual(result["result"]["data"]["add_machine_error_code"], "NOT_RUN")
        self.assertEqual(result["result"]["data"]["validate_status"], "ok")
        self.assertEqual(result["result"]["data"]["validate_machine_error_code"], "OK")
        self.assertFalse(result["result"]["data"]["browser_secret_intake"])
        self.assertFalse(result["result"]["data"]["browser_path_intake"])
        self.assertFalse(result["result"]["data"]["browser_route_id_intake"])
        self.assertFalse(result["result"]["data"]["browser_api_key_intake"])
        self.assertFalse(result["result"]["data"]["secret_value_exposed"])
        self.assertFalse(result["result"]["data"]["route_spec_path_exposed"])
        self.assertEqual(
            runner.calls,
            [
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
                ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
                ("external-models", "routes", "validate", "--route", "wbp-deepseek-v3", "--json"),
            ],
        )

    def test_api_route_connect_prefers_primary_route_snapshot_provider(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 1,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [
                    {
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "cost_class": "paid_or_free_limited",
                        "enabled": True,
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "synthetic_adapter_state": "stopped",
                        "profile_ready": False,
                    }
                ],
            },
        )
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={
                "count": 1,
                "routes": [
                    {
                        "schema_version": 1,
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "auth": {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"},
                        "cost_class": "paid_or_free_limited",
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "enabled": True,
                    }
                ],
            },
        )
        payloads[
            ("external-models", "credentials", "status", "--provider", "deepseek", "--json")
        ] = credential_status_packet(
            present=True,
            provider="deepseek",
            credential_ref="DEEPSEEK_API_KEY",
            expected_refs=["DEEPSEEK_API_KEY"],
            provider_dashboard_url="https://platform.deepseek.com/api_keys",
        )
        payloads[
            ("external-models", "routes", "validate", "--route", "wbp-deepseek-v3", "--json")
        ] = command_packet(
            human_message="External-models route validation captured provider evidence without claiming runtime readiness.",
            data={
                "validation_kind": "provider_route_validate",
                "network_dependent": True,
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "verification_scope": "route_provider_only",
                "route_state": "model_visible",
                "requested_model": "wbp-deepseek-v3",
                "effective_model": "deepseek-chat",
                "provider": "deepseek",
            },
        )
        runner = MappingRunner(payloads)
        contract = launch_copy_contract()

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_connect"},
            launch_copy_contract=contract,
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["data"]["credential_provider"], "deepseek")
        self.assertEqual(result["result"]["data"]["credential_ref"], "DEEPSEEK_API_KEY")
        self.assertEqual(result["result"]["data"]["route_id"], "wbp-deepseek-v3")
        self.assertIn(
            ("external-models", "credentials", "status", "--provider", "deepseek", "--json"),
            runner.calls,
        )
        self.assertNotIn(
            ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
            runner.calls,
        )

    def test_api_route_connect_missing_credential_triggers_owner_admit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            route_spec_path = (
                data_dir
                / "external-models"
                / "server-owned-route-specs"
                / "wbp-web-primary-openrouter.json"
            )
            payloads = live_payloads()
            payloads[("external-models", "routes", "list", "--json")] = command_packet(
                human_message="External-models routes listed from local registry.",
                data={"count": 0, "routes": []},
            )
            payloads[("external-models", "models", "--json")] = command_packet(
                human_message="External-models route models listed from local registry.",
                data={
                    "count": 0,
                    "source": "local_routes_registry",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "models": [],
                },
            )
            payloads[
                ("external-models", "credentials", "status", "--provider", "openrouter", "--json")
            ] = credential_status_packet(present=False)
            payloads[
                (
                    "external-models",
                    "routes",
                    "add",
                    "--file",
                    str(route_spec_path),
                    "--json",
                )
            ] = command_packet(
                human_message="External-models route added: wbp-web-primary-openrouter.",
                changed_files=[str(data_dir / "external-models" / "routes.json")],
                data={"route_id": "wbp-web-primary-openrouter"},
            )
            payloads[
                (
                    "external-models",
                    "routes",
                    "validate",
                    "--route",
                    "wbp-web-primary-openrouter",
                    "--json",
                )
            ] = command_packet(
                human_message="External-models route validation captured provider evidence without claiming runtime readiness.",
                data={
                    "route_id": "wbp-web-primary-openrouter",
                    "route_state": "model_visible",
                    "verification_scope": "route_provider_only",
                },
            )
            runner = MappingRunner(payloads)
            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9345,
                action_server_port=9344,
            )

            result = run_ui_action(
                runner,
                {"ui_action": "api_route_connect"},
                launch_copy_contract=contract,
                action_phase=SANDBOX_ACTION_PHASE,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["result"]["data"]["credential_phase"], "credential_admitted")
            self.assertTrue(result["result"]["data"]["credential_present"])
            self.assertTrue(result["result"]["data"]["credential_admitted"])
            self.assertEqual(result["result"]["data"]["credential_admit_status"], "admitted")
            self.assertFalse(result["result"]["data"]["secret_value_exposed"])
            self.assertIn(
                ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
                runner.calls,
            )
            self.assertIn(
                (
                    "external-models",
                    "credentials",
                    "admit",
                    "--provider",
                    "openrouter",
                    "--source",
                    "owner-env",
                    "--json",
                ),
                runner.calls,
            )
            self.assertLess(
                runner.calls.index(
                    (
                        "external-models",
                        "credentials",
                        "admit",
                        "--provider",
                        "openrouter",
                        "--source",
                        "owner-env",
                        "--json",
                    )
                ),
                runner.calls.index(
                    (
                        "external-models",
                        "routes",
                        "add",
                        "--file",
                        str(route_spec_path),
                        "--json",
                    )
                ),
            )

    def test_api_route_connect_admit_failure_blocks_route_add(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={"count": 0, "routes": []},
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 0,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [],
            },
        )
        payloads[
            ("external-models", "credentials", "status", "--provider", "openrouter", "--json")
        ] = credential_status_packet(present=False)
        payloads[
            (
                "external-models",
                "credentials",
                "admit",
                "--provider",
                "openrouter",
                "--source",
                "owner-env",
                "--json",
            )
        ] = command_packet(
            status="error",
            exit_code=1,
            human_message="Owner credential source is missing for provider: openrouter",
            machine_error_code="EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING",
            next_action="user_action",
            data={
                "credential_result": {
                    "status": "missing",
                    "provider": "openrouter",
                    "source": "owner-env",
                    "credential_ref": "OPENROUTER_API_KEY",
                    "credential_present": False,
                    "supported_sources": ["owner-env"],
                    "expected_refs": [
                        "OPENROUTER_API_KEY",
                        "WBP_OPENROUTER_API_KEY",
                        "WBP_PROVIDER_OPENROUTER_API_KEY",
                    ],
                    "provider_dashboard_url": "https://openrouter.ai/settings/keys",
                    "secret_value_exposed": False,
                    "browser_secret_intake": False,
                    "browser_path_intake": False,
                    "scope": "sandbox",
                }
            },
        )
        runner = MappingRunner(payloads)

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_connect"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "command_error")
        self.assertEqual(
            result["result"]["machine_error_code"],
            "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING",
        )
        self.assertEqual(result["result"]["data"]["credential_phase"], "credential_missing")
        self.assertEqual(result["result"]["data"]["add_status"], "not_run")
        self.assertEqual(result["result"]["data"]["validate_status"], "not_run")
        self.assertFalse(result["result"]["data"]["credential_present"])
        self.assertFalse(result["result"]["data"]["secret_value_exposed"])
        self.assertEqual(
            result["result"]["data"]["credential_expected_refs"],
            [
                "OPENROUTER_API_KEY",
                "WBP_OPENROUTER_API_KEY",
                "WBP_PROVIDER_OPENROUTER_API_KEY",
            ],
        )
        self.assertEqual(
            result["result"]["data"]["credential_supported_sources"],
            ["owner-env"],
        )
        self.assertEqual(
            result["result"]["data"]["credential_provider_dashboard_url"],
            "https://openrouter.ai/settings/keys",
        )
        self.assertNotIn(
            (
                "external-models",
                "routes",
                "validate",
                "--route",
                "wbp-web-primary-openrouter",
                "--json",
            ),
            runner.calls,
        )

    def test_full_action_default_runner_uses_owner_external_models_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(managed_dir),
            }
            captured: list[dict[str, object]] = []

            class CapturingJsonCommandRunner:
                def __init__(
                    self,
                    *,
                    base_command: list[str] | None = None,
                    cwd: str | None = None,
                    env: dict[str, str] | None = None,
                ) -> None:
                    captured.append(
                        {
                            "base_command": base_command,
                            "cwd": cwd,
                            "env": dict(env or {}),
                        }
                    )

            with (
                mock.patch.dict(os.environ, env_updates, clear=False),
                mock.patch.object(
                    live_server,
                    "JsonCommandRunner",
                    CapturingJsonCommandRunner,
                ),
            ):
                build_handler(action_phase=FULL_ACTION_PHASE)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["cwd"], str(profile_dir))
        runner_env = captured[0]["env"]
        self.assertIsInstance(runner_env, dict)
        self.assertEqual(runner_env["WBP_PROFILE_DIR"], str(profile_dir))
        self.assertEqual(runner_env["WBP_MANAGED_DIR"], str(managed_dir))
        self.assertEqual(
            runner_env["WBP_EXTERNAL_MODELS_DIR"],
            str(managed_dir / "external-models"),
        )
        pythonpath = str(runner_env["PYTHONPATH"]).split(os.pathsep)
        self.assertIn(str(live_server.ROOT), pythonpath)

    def test_api_route_credential_check_surfaces_missing_owner_env_without_route_mutation(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={"count": 0, "routes": []},
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 0,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [],
            },
        )
        payloads[
            ("external-models", "credentials", "status", "--provider", "openrouter", "--json")
        ] = credential_status_packet(present=False)
        runner = MappingRunner(payloads)

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_credential_check"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "command_error")
        self.assertEqual(
            result["result"]["machine_error_code"],
            "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING",
        )
        self.assertEqual(result["result"]["data"]["credential_phase"], "credential_missing")
        self.assertEqual(result["result"]["data"]["credential_provider"], "openrouter")
        self.assertEqual(result["result"]["data"]["credential_ref"], "OPENROUTER_API_KEY")
        self.assertEqual(result["result"]["data"]["add_status"], "not_run")
        self.assertEqual(result["result"]["data"]["validate_status"], "not_run")
        self.assertFalse(result["result"]["data"]["credential_present"])
        self.assertFalse(result["result"]["data"]["browser_api_key_intake"])
        self.assertFalse(result["result"]["data"]["secret_value_exposed"])
        self.assertFalse(
            any(call[:3] == ("external-models", "routes", "add") for call in runner.calls)
        )

    def test_api_route_credential_check_reports_present_owner_env(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={"count": 0, "routes": []},
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 0,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [],
            },
        )
        payloads[
            ("external-models", "credentials", "status", "--provider", "openrouter", "--json")
        ] = credential_status_packet(present=True)
        runner = MappingRunner(payloads)

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_credential_check"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["data"]["credential_phase"], "credential_present")
        self.assertTrue(result["result"]["data"]["credential_present"])
        self.assertEqual(result["result"]["data"]["credential_provider"], "openrouter")
        self.assertEqual(result["result"]["data"]["credential_status"], "present")
        self.assertEqual(result["result"]["data"]["add_status"], "not_run")
        self.assertEqual(result["result"]["data"]["validate_status"], "not_run")

    def test_api_route_credential_check_uses_server_owned_route_provider(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={"count": 0, "routes": []},
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 0,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [],
            },
        )
        payloads[
            ("external-models", "credentials", "status", "--provider", "deepseek", "--json")
        ] = credential_status_packet(
            present=True,
            provider="deepseek",
            credential_ref="DEEPSEEK_API_KEY",
            expected_refs=["DEEPSEEK_API_KEY"],
            provider_dashboard_url="https://platform.deepseek.com/api_keys",
        )
        runner = MappingRunner(payloads)
        runner._env = {
            "WBP_SERVER_OWNED_API_ROUTE_PROVIDER": "deepseek",
            "WBP_SERVER_OWNED_API_ROUTE_SECRET_REF": "DEEPSEEK_API_KEY",
        }

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_credential_check"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["data"]["credential_provider"], "deepseek")
        self.assertEqual(result["result"]["data"]["credential_ref"], "DEEPSEEK_API_KEY")
        self.assertEqual(
            result["result"]["human_message"],
            "Owner credential status confirmed for provider: deepseek.",
        )
        self.assertIn(
            ("external-models", "credentials", "status", "--provider", "deepseek", "--json"),
            runner.calls,
        )

    def test_api_route_credential_check_prefers_primary_route_snapshot_provider(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 1,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [
                    {
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "cost_class": "paid_or_free_limited",
                        "enabled": True,
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "synthetic_adapter_state": "stopped",
                        "profile_ready": False,
                    }
                ],
            },
        )
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={
                "count": 1,
                "routes": [
                    {
                        "schema_version": 1,
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "auth": {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"},
                        "cost_class": "paid_or_free_limited",
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "enabled": True,
                    }
                ],
            },
        )
        payloads[
            ("external-models", "credentials", "status", "--provider", "deepseek", "--json")
        ] = credential_status_packet(
            present=True,
            provider="deepseek",
            credential_ref="DEEPSEEK_API_KEY",
            expected_refs=["DEEPSEEK_API_KEY"],
            provider_dashboard_url="https://platform.deepseek.com/api_keys",
        )
        runner = MappingRunner(payloads)

        result = run_ui_action(
            runner,
            {"ui_action": "api_route_credential_check"},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["data"]["credential_provider"], "deepseek")
        self.assertEqual(result["result"]["data"]["credential_ref"], "DEEPSEEK_API_KEY")
        self.assertIn(
            ("external-models", "credentials", "status", "--provider", "deepseek", "--json"),
            runner.calls,
        )
        self.assertNotIn(
            ("external-models", "credentials", "status", "--provider", "openrouter", "--json"),
            runner.calls,
        )

    def test_api_route_connect_rejects_forbidden_browser_fields(self) -> None:
        runner = MappingRunner(live_payloads())
        forbidden_payloads = [
            {"ui_action": "api_route_connect", "route_id": "wbp-user-chosen"},
            {"ui_action": "api_route_connect", "token": "secret"},
            {"ui_action": "api_route_connect", "secret": "secret"},
            {"ui_action": "api_route_connect", "api_key": "secret"},
            {"ui_action": "api_route_connect", "auth": "secret"},
            {"ui_action": "api_route_connect", "path": "/tmp/route.json"},
            {"ui_action": "api_route_connect", "backend_id": "route"},
            {"ui_action": "api_route_connect", "base_url": "https://browser.invalid"},
            {"ui_action": "api_route_connect", "endpoint_path": "/v1/responses"},
            {"ui_action": "api_route_connect", "secret_ref": "BROWSER_SECRET_REF"},
            {"ui_action": "api_route_connect", "CODEX_HOME": "/tmp/browser-codex-home"},
            {"ui_action": "api_route_connect", "route_config": {"secret_ref": "BROWSER_SECRET_REF"}},
        ]

        for payload in forbidden_payloads:
            result = run_ui_action(
                runner,
                payload,
                launch_copy_contract=launch_copy_contract(),
                action_phase=SANDBOX_ACTION_PHASE,
            )
            self.assertEqual(result["status"], "integration_failure", payload)
            self.assertEqual(result["action_role"], "blocked", payload)
            self.assertEqual(result["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED", payload)
        self.assertEqual(runner.calls, [])

    def test_real_json_runner_supports_sandbox_api_route_connect_from_profile_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            external_dir = data_dir / "external-models"
            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(external_dir),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                paths = RuntimePaths.from_env()
                install_payload = run_installer_init(paths)
            self.assertEqual(install_payload["status"], "ok")

            provider = ThreadingHTTPServer(("127.0.0.1", free_port()), StableProbeHandler)
            provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
            provider_thread.start()
            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9347,
                action_server_port=9346,
            )
            from wild_boar_proxy.ui_shell import JsonCommandRunner

            sandbox_env = _sandbox_action_runner_env(contract)
            sandbox_env["WBP_SERVER_OWNED_API_ROUTE_BASE_URL"] = (
                f"http://127.0.0.1:{provider.server_port}/v1"
            )
            sandbox_env["WBP_SERVER_OWNED_API_ROUTE_MODEL"] = "gpt-5.4"
            sandbox_env["OPENROUTER_API_KEY"] = "test-key"
            runner = JsonCommandRunner(cwd=str(profile_dir), env=sandbox_env)
            try:
                readonly_before = build_api_connections_readonly_snapshot(runner)
                self.assertEqual(readonly_before["status"], "ok")
                self.assertEqual(readonly_before["routes"], [])

                result = run_ui_action(
                    runner,
                    {"ui_action": "api_route_connect"},
                    launch_copy_contract=contract,
                    action_phase=SANDBOX_ACTION_PHASE,
                )

                readonly_after = build_api_connections_readonly_snapshot(runner)
            finally:
                provider.shutdown()
                provider.server_close()
                provider_thread.join(timeout=5)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["action_role"], "api_route_admission")
            self.assertEqual(result["result"]["data"]["api_route_connect_phase"], "created_and_validated")
            self.assertEqual(result["result"]["data"]["credential_phase"], "credential_admitted")
            self.assertTrue(result["result"]["data"]["credential_admitted"])
            self.assertFalse(result["result"]["data"]["secret_value_exposed"])
            self.assertEqual(result["result"]["data"]["route_id"], "wbp-web-primary-openrouter")
            self.assertEqual(result["result"]["machine_error_code"], "OK")
            self.assertEqual(result["result"]["data"]["validate_status"], "ok")
            self.assertEqual(result["result"]["data"]["validate_machine_error_code"], "OK")
            self.assertFalse(result["result"]["data"]["browser_secret_intake"])
            self.assertFalse(result["result"]["data"]["browser_path_intake"])
            self.assertFalse(result["result"]["data"]["browser_route_id_intake"])
            self.assertFalse(result["result"]["data"]["browser_api_key_intake"])
            self.assertNotIn("test-key", json.dumps(result))
            self.assertEqual(readonly_after["status"], "ok")
            self.assertEqual(len(readonly_after["routes"]), 1)
            self.assertEqual(readonly_after["routes"][0]["route_id"], "wbp-web-primary-openrouter")
            self.assertTrue(readonly_after["routes"][0]["enabled"])
            self.assertEqual(readonly_after["routes"][0]["secret_status_label"], "available")
            self.assertEqual(readonly_after["routes"][0]["validation_label"], "ok")
            self.assertFalse(readonly_after["adapter"]["profile_ready"])
            self.assertTrue(readonly_after["adapter"]["runtime_claim_blocked"])

    def test_api_connections_readonly_requires_matching_secret_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            data_dir = root / "managed"
            external_dir = data_dir / "external-models"
            env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(external_dir),
            }
            with mock.patch.dict(os.environ, env_updates, clear=False):
                paths = RuntimePaths.from_env()
                install_payload = run_installer_init(paths)
            self.assertEqual(install_payload["status"], "ok")

            (external_dir / "routes.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "routes": [
                            external_route(
                                "wbp-web-primary-openrouter",
                                enabled=True,
                                display_name="OpenRouter primary",
                            )
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (external_dir / "secrets.env").write_text(
                "WBP_EXTERNAL_MODELS_LOCAL_TOKEN=synthetic-only\n",
                encoding="utf-8",
            )
            os.chmod(external_dir / "secrets.env", 0o600)

            contract = LaunchCopyContract(
                client_path=TEST_LAUNCH_CLIENT_PATH,
                profile_dir=str(profile_dir),
                data_dir=str(data_dir),
                copy_port=9349,
                action_server_port=9348,
            )
            from wild_boar_proxy.ui_shell import JsonCommandRunner

            runner = JsonCommandRunner(
                cwd=str(profile_dir),
                env=_sandbox_action_runner_env(contract),
            )

            readonly_snapshot = build_api_connections_readonly_snapshot(runner)

            self.assertEqual(readonly_snapshot["status"], "ok")
            self.assertTrue(readonly_snapshot["adapter"]["local_token_present"])
            self.assertEqual(len(readonly_snapshot["routes"]), 1)
            self.assertEqual(readonly_snapshot["routes"][0]["secret_ref"], "OPENROUTER_API_KEY")
            self.assertEqual(readonly_snapshot["routes"][0]["secret_status_label"], "missing")
            self.assertEqual(readonly_snapshot["routes"][0]["validation_label"], "blocked by secret")

    def test_http_sandbox_readonly_endpoints_follow_sandbox_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current_profile_dir = root / "current-profile"
            current_data_dir = root / "current-managed"
            profile_dir = root / "copy-profile"
            data_dir = root / "copy-managed"
            auth_dir = data_dir / "device-login-auth"
            fake_cli = root / "fake-device-cli-proxy.py"
            argv_capture = data_dir / "device-login-argv.json"
            ready_file = data_dir / "device-login.ready"
            auth_ref = auth_dir / "codex-device-login.json"
            write_test_device_login_cli_proxy(
                fake_cli,
                argv_capture_path=argv_capture,
                ready_file=ready_file,
                auth_filename=auth_ref.name,
            )
            current_env_updates = {
                "WBP_PROFILE_DIR": str(current_profile_dir),
                "WBP_MANAGED_DIR": str(current_data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(current_data_dir / "external-models"),
                "WBP_CLIPROXY_BIN": str(fake_cli),
                "WBP_TEST_DEVICE_LOGIN_WAIT_SECONDS": "10",
                "WBP_TEST_ONBOARD_ADDED_BACKENDS_JSON": json.dumps(
                    [
                        account(
                            "acct-device-login",
                            "reserve",
                            "healthy",
                            auth_ref=str(auth_ref),
                        )
                    ]
                ),
            }
            target_env_updates = {
                "WBP_PROFILE_DIR": str(profile_dir),
                "WBP_MANAGED_DIR": str(data_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(data_dir / "external-models"),
            }
            with mock.patch.dict(os.environ, target_env_updates, clear=False):
                paths = RuntimePaths.from_env()
                install_payload = run_installer_init(paths)
                self.assertEqual(install_payload["status"], "ok")
                stable_port = free_port()
                (data_dir / "stable-runtime-config.yaml").write_text(
                    f'host: 127.0.0.1\nport: {stable_port}\nauth-dir: "device-login-auth"\n',
                    encoding="utf-8",
                )
            with mock.patch.dict(os.environ, current_env_updates, clear=False):
                stable_server = ThreadingHTTPServer(
                    ("127.0.0.1", stable_port), StableProbeHandler
                )
                stable_thread = threading.Thread(target=stable_server.serve_forever, daemon=True)
                stable_thread.start()
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        launch_client_path=TEST_LAUNCH_CLIENT_PATH,
                        launch_copy_contract=LaunchCopyContract(
                            client_path=TEST_LAUNCH_CLIENT_PATH,
                            profile_dir=str(profile_dir),
                            data_dir=str(data_dir),
                            copy_port=9343,
                            action_server_port=9342,
                        ),
                        action_phase=SANDBOX_ACTION_PHASE,
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base_url = f"http://127.0.0.1:{server.server_port}"
                    before_accounts = json.loads(fetch(f"{base_url}/api/accounts-readonly"))
                    before_api = json.loads(fetch(f"{base_url}/api/api-connections-readonly"))
                    dry_run = json.loads(
                        post_json(
                            f"{base_url}/api/action",
                            {"ui_action": "onboard_account_dry_run"},
                        )
                    )
                    live = json.loads(
                        post_json(
                            f"{base_url}/api/action",
                            {"ui_action": "onboard_account"},
                        )
                    )
                    session_id = str(live["session_id"])
                    self.assertTrue(session_id.startswith("codex-"))
                    ready_file.write_text("ready\n", encoding="utf-8")
                    login_status = json.loads(
                        post_json(
                            f"{base_url}/api/action",
                            {"ui_action": "account_login_status", "session_id": session_id},
                        )
                    )
                    deadline = time.time() + 5
                    while (
                        login_status["result"]["data"]["login_bridge"]["status"] != "auth_materialized"
                        and time.time() < deadline
                    ):
                        time.sleep(0.05)
                        login_status = json.loads(
                            post_json(
                                f"{base_url}/api/action",
                                {"ui_action": "account_login_status", "session_id": session_id},
                            )
                        )
                    live_complete = json.loads(
                        post_json(
                            f"{base_url}/api/action",
                            {"ui_action": "account_login_complete", "session_id": session_id},
                        )
                    )
                    after_accounts = json.loads(fetch(f"{base_url}/api/accounts-readonly"))
                    after_api = json.loads(fetch(f"{base_url}/api/api-connections-readonly"))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
                    stable_server.shutdown()
                    stable_server.server_close()
                    stable_thread.join(timeout=5)

            self.assertEqual(before_accounts["status"], "ok")
            self.assertEqual(before_accounts["source"], "accounts_readonly")
            self.assertEqual(before_accounts["accounts"], [])
            self.assertEqual(before_api["status"], "ok")
            self.assertEqual(before_api["source"], "api_connections_readonly")
            self.assertEqual(before_api["routes"], [])
            self.assertEqual(dry_run["status"], "ok")
            self.assertEqual(
                dry_run["result"]["onboarding"]["final_outcome"],
                "dry_run_preview_ready",
            )
            self.assertEqual(live["status"], "ok")
            self.assertEqual(
                live["result"]["data"]["login_bridge"]["status"],
                "waiting_for_user",
            )
            self.assertEqual(login_status["status"], "ok")
            self.assertEqual(
                login_status["result"]["data"]["login_bridge"]["status"],
                "auth_materialized",
            )
            self.assertEqual(live_complete["status"], "ok")
            self.assertEqual(
                live_complete["result"]["onboarding"]["final_outcome"],
                "explicit_auth_imported_to_reserve",
            )
            self.assertEqual(after_accounts["status"], "ok")
            self.assertEqual(len(after_accounts["accounts"]), 1)
            self.assertEqual(
                after_accounts["accounts"][0]["id"],
                live_complete["result"]["onboarding"]["selected_backend_id"],
            )
            self.assertEqual(after_accounts["accounts"][0]["pool"], "reserve")
            self.assertEqual(after_api["status"], "ok")
            self.assertEqual(after_api["routes"], [])

    def test_owner_login_sandbox_page_serves_bounded_owner_url_surface(self) -> None:
        runner = MappingRunner(live_payloads())
        handler = build_handler(
            runner=runner,
            launch_copy_contract=launch_copy_contract(action_server_port=8788),
            action_phase=SANDBOX_ACTION_PHASE,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            html = fetch(
                f"{base_url}/owner-login/sandbox?provider=sandbox&session={TEST_SANDBOX_LOGIN_SESSION_ID}&state={TEST_SANDBOX_LOGIN_STATE}&nonce=sandbox-nonce-test"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertIn("Sandbox owner login surface", html)
        self.assertIn(TEST_SANDBOX_LOGIN_SESSION_ID, html)
        self.assertIn(TEST_SANDBOX_LOGIN_STATE, html)

    def test_account_connect_preflight_admits_clear_registry_identity(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "list", "--json"): accounts_packet(
                    accounts=[],
                    registry_identity={
                        "status": "clear",
                        "machine_error_code": "OK",
                        "next_action": "none",
                    },
                ),
            }
        )
        preflight = run_ui_action(
            runner,
            {"ui_action": "onboard_account"},
            launch_copy_contract=LaunchCopyContract(
                profile_dir="/tmp/wbp-copy-profile",
                data_dir="/tmp/wbp-copy-data",
                copy_port=8789,
                action_server_port=8788,
            ),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(preflight["status"], "ok")
        self.assertEqual(preflight["result"]["data"]["login_bridge"]["status"], "waiting_for_user")

    def test_onboard_account_rejects_browser_args_and_raw_adapter_action(self) -> None:
        runner = MappingRunner(live_payloads())

        raw_action = run_ui_action(runner, {"ui_action": "accounts_onboard"})
        auth_ref = run_ui_action(
            runner,
            {"ui_action": "onboard_account", "auth_ref": "/tmp/new-auth.json"},
        )
        source_dir = run_ui_action(
            runner,
            {"ui_action": "onboard_account", "source_dir": "/tmp/auth-dir"},
        )
        credentials = run_ui_action(
            runner,
            {"ui_action": "onboard_account", "password": "secret"},
        )
        backend_id = run_ui_action(
            runner,
            {"ui_action": "onboard_account", "backend_id": "acct-new"},
        )
        bad_session = run_ui_action(
            runner,
            {"ui_action": "onboard_account", "session_id": TEST_CODEX_LOGIN_SESSION_ID},
        )

        for payload in [raw_action, auth_ref, source_dir, credentials, backend_id, bad_session]:
            self.assertEqual(payload["status"], "integration_failure")
            self.assertEqual(payload["action_role"], "blocked")
            self.assertEqual(payload["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(runner.calls, [])

    def test_account_login_follow_up_actions_require_safe_session_id_only(self) -> None:
        runner = MappingRunner(live_payloads())

        missing = run_ui_action(runner, {"ui_action": "account_login_status"})
        unsafe = run_ui_action(
            runner,
            {"ui_action": "account_login_complete", "session_id": "../codex-session"},
        )
        extra = run_ui_action(
            runner,
            {"ui_action": "account_login_cancel", "session_id": TEST_CODEX_LOGIN_SESSION_ID, "auth_ref": "/tmp/forbidden.json"},
        )

        self.assertEqual(missing["status"], "integration_failure")
        self.assertEqual(missing["result"]["machine_error_code"], "UI_LOGIN_SESSION_ID_REQUIRED")
        self.assertEqual(unsafe["status"], "integration_failure")
        self.assertEqual(unsafe["result"]["machine_error_code"], "UI_LOGIN_SESSION_ID_INVALID")
        self.assertEqual(extra["status"], "integration_failure")
        self.assertEqual(extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(runner.calls, [])

    def test_onboard_account_blocks_live_connect_when_server_owned_preflight_is_not_admitted(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "list", "--json"): accounts_packet(
                    registry_identity={
                        "status": "error",
                        "machine_error_code": "REGISTRY_IDENTITY_UNPROVEN",
                        "next_action": "repair_registry",
                    }
                ),
            }
        )

        result = run_ui_action(
            runner,
            {"ui_action": "onboard_account"},
            launch_copy_contract=LaunchCopyContract(
                profile_dir="/tmp/wbp-copy-profile",
                data_dir="/tmp/wbp-copy-data",
                copy_port=8789,
                action_server_port=8788,
            ),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "integration_failure")
        self.assertEqual(result["action_role"], "blocked")
        self.assertEqual(result["availability_state"], "preflight_blocked")
        self.assertEqual(
            result["result"]["machine_error_code"],
            "UI_ACCOUNT_CONNECT_SERVER_OWNED_SOURCE_UNPROVEN",
        )
        self.assertEqual(
            result["result"]["data"]["account_connect_preflight"]["status"],
            "denied",
        )
        self.assertEqual(
            result["result"]["data"]["account_connect_preflight"]["refresh_surface"],
            "accounts-readonly",
        )
        self.assertEqual(runner.calls, [("accounts", "list", "--json")])

    def test_onboard_outcomes_do_not_overclaim_success_without_reserve_proof(self) -> None:
        no_new_runner = MappingRunner({**live_payloads()})
        ambiguous_runner = MappingRunner({**live_payloads()})
        unknown_runner = MappingRunner({**live_payloads()})
        validate_failed_runner = MappingRunner({**live_payloads()})
        command_error_runner = MappingRunner(
            {
                **live_payloads(),
                (
                    "accounts",
                    "login",
                    "start",
                    "--provider",
                    "codex",
                    "--mode",
                    "device",
                    "--json",
                ): codex_login_start_packet(
                    status="error",
                    machine_error_code="LOGIN_DEVICE_HANDOFF_MISSING",
                    login_result={
                        "status": "failed",
                        "provider": "codex",
                        "mode": "device",
                        "session_id": TEST_CODEX_LOGIN_SESSION_ID,
                        "login_session_id": TEST_CODEX_LOGIN_SESSION_ID,
                        "device_url": "",
                        "device_code_present": False,
                        "auth_materialized": False,
                        "auth_ref_present": False,
                    },
                ),
            }
        )

        no_new = run_ui_action(no_new_runner, {"ui_action": "onboard_account"})
        ambiguous = run_ui_action(ambiguous_runner, {"ui_action": "onboard_account"})
        unknown = run_ui_action(unknown_runner, {"ui_action": "onboard_account"})
        validate_failed = run_ui_action(validate_failed_runner, {"ui_action": "onboard_account"})
        command_error = run_ui_action(command_error_runner, {"ui_action": "onboard_account"})

        self.assertEqual(no_new["result"]["data"]["login_bridge"]["status"], "waiting_for_user")
        self.assertEqual(ambiguous["result"]["data"]["login_bridge"]["status"], "waiting_for_user")
        self.assertEqual(unknown["result"]["data"]["login_bridge"]["status"], "waiting_for_user")
        self.assertEqual(validate_failed["result"]["data"]["login_bridge"]["status"], "waiting_for_user")
        self.assertEqual(command_error["status"], "command_error")
        self.assertEqual(command_error["result"]["data"]["login_bridge"]["status"], "failed")
        for payload in [no_new, ambiguous, unknown, validate_failed, command_error]:
            self.assertEqual(payload["result"]["data"]["login_bridge"]["provider"], "codex")
            self.assertFalse(payload["result"]["data"]["login_bridge"]["browser_secret_intake"])

    def test_ui_action_endpoint_accepts_allowlisted_actions_only(self) -> None:
        runner = MappingRunner(live_payloads())

        diagnostics = run_ui_action(runner, {"ui_action": "export_diagnostics"})
        repair_plan = run_ui_action(runner, {"ui_action": "stable_repair_plan"})
        health = run_ui_action(runner, {"ui_action": "refresh_health_detail"})
        sync = run_ui_action(runner, {"ui_action": "sync_runtime"})
        stable = run_ui_action(runner, {"ui_action": "set_mode_stable"})
        managed = run_ui_action(runner, {"ui_action": "set_mode_managed"})
        smoke = run_ui_action(runner, {"ui_action": "launch_smoke"})

        self.assertEqual(diagnostics["action_role"], "support_artifact")
        self.assertFalse(diagnostics["mutates_runtime"])
        self.assertFalse(diagnostics["affects_primary_truth"])
        self.assertEqual(diagnostics["result"]["data"]["bundle_path"], "wbp-diagnostics.zip")
        self.assertEqual(repair_plan["action_role"], "recovery_planning")
        self.assertFalse(repair_plan["mutates_runtime"])
        self.assertEqual(health["action_role"], "runtime_detail")
        self.assertTrue(sync["confirmation_required"])
        self.assertTrue(sync["mutates_runtime"])
        self.assertTrue(sync["post_action_refresh_required"])
        self.assertEqual(stable["action_role"], "controlled_mode_mutation")
        self.assertEqual(managed["action_role"], "controlled_mode_mutation")
        self.assertEqual(smoke["action_role"], "runtime_smoke_check")
        self.assertFalse(smoke["mutates_runtime"])
        self.assertIn("не успех запуска внешнего клиента", smoke["action_claim_scope"])
        self.assertEqual(
            runner.calls[-7:],
            [
                ("diagnostics", "export", "--json"),
                ("stable", "repair", "--dry-run", "--json"),
                ("healthcheck", "--json"),
                ("sync", "--json"),
                ("mode", "set", "stable", "--json"),
                ("mode", "set", "managed", "--json"),
                ("launch", "smoke", "--json"),
            ],
        )

    def test_validate_account_action_preflights_account_id_and_executes_exact_command(self) -> None:
        runner = MappingRunner(live_payloads())

        result = run_ui_action(
            runner,
            {"ui_action": "validate_account", "account_id": "acct-active"},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "account_verification")
        self.assertFalse(result["mutates_runtime"])
        self.assertFalse(result["affects_primary_truth"])
        self.assertFalse(result["confirmation_required"])
        self.assertTrue(result["post_action_refresh_required"])
        self.assertEqual(result["account_id"], "acct-active")
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "validate", "acct-active", "--json"),
            ],
        )

    def test_recheck_account_alias_uses_validate_command_without_confirmation(self) -> None:
        runner = MappingRunner(live_payloads())

        result = run_ui_action(
            runner,
            {"ui_action": "recheck_account", "account_id": "acct-active"},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "account_verification")
        self.assertFalse(result["confirmation_required"])
        self.assertTrue(result["post_action_refresh_required"])
        self.assertEqual(result["account_id"], "acct-active")
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "validate", "acct-active", "--json"),
            ],
        )

    def test_validate_account_rejects_bad_payloads_without_validate_execution(self) -> None:
        unsafe_runner = MappingRunner(live_payloads())
        unknown_runner = MappingRunner(live_payloads())
        extra_runner = MappingRunner(live_payloads())

        missing = run_ui_action(unsafe_runner, {"ui_action": "validate_account"})
        unsafe = run_ui_action(
            unsafe_runner,
            {"ui_action": "validate_account", "account_id": "../acct-active"},
        )
        unknown = run_ui_action(
            unknown_runner,
            {"ui_action": "validate_account", "account_id": "acct-missing"},
        )
        extra = run_ui_action(
            extra_runner,
            {"ui_action": "validate_account", "account_id": "acct-active", "argv": "accounts retire"},
        )

        self.assertEqual(missing["result"]["machine_error_code"], "UI_ACCOUNT_ID_REQUIRED")
        self.assertEqual(unsafe["result"]["machine_error_code"], "UI_ACCOUNT_ID_INVALID")
        self.assertEqual(unknown["result"]["machine_error_code"], "UI_ACCOUNT_ID_NOT_FOUND")
        self.assertEqual(extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(unsafe_runner.calls, [])
        self.assertEqual(unknown_runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(extra_runner.calls, [])
        for calls in [unsafe_runner.calls, unknown_runner.calls, extra_runner.calls]:
            self.assertNotIn(("accounts", "validate", "acct-active", "--json"), calls)

    def test_api_route_actions_preflight_route_and_execute_exact_commands(self) -> None:
        validate_runner = MappingRunner(live_payloads())
        check_runner = MappingRunner(live_payloads())
        allow_runner = MappingRunner(
            {
                **live_payloads(),
                ("external-models", "routes", "list", "--json"): routes_list_packet(
                    "wbp-disabled",
                    enabled=False,
                ),
                ("external-models", "routes", "enable", "--route", "wbp-disabled", "--json"): command_packet(
                    human_message="External-models route enabled: wbp-disabled.",
                    data={"route_id": "wbp-disabled", "enabled": True},
                ),
            }
        )
        disable_runner = MappingRunner(live_payloads())
        profile_runner = MappingRunner(live_payloads())
        evidence_runner = MappingRunner(live_payloads())
        remove_runner = MappingRunner(
            {
                **live_payloads(),
                ("external-models", "routes", "list", "--json"): routes_list_packet(
                    "wbp-disabled",
                    enabled=False,
                ),
                ("external-models", "routes", "remove", "--route", "wbp-disabled", "--json"): command_packet(
                    human_message="External-models route removed: wbp-disabled.",
                    changed_files=["/tmp/routes.json", "/tmp/state.json"],
                    data={"route_id": "wbp-disabled"},
                ),
            }
        )

        validate = run_ui_action(
            validate_runner,
            {"ui_action": "api_route_validate", "route_id": "wbp-deepseek-v3"},
        )
        check = run_ui_action(
            check_runner,
            {"ui_action": "api_route_check", "route_id": "wbp-deepseek-v3"},
        )
        allow = run_ui_action(
            allow_runner,
            {"ui_action": "api_route_allow", "route_id": "wbp-disabled"},
        )
        disable = run_ui_action(
            disable_runner,
            {"ui_action": "api_route_disable", "route_id": "wbp-deepseek-v3"},
        )
        profile = run_ui_action(
            profile_runner,
            {"ui_action": "api_route_profile", "route_id": "wbp-deepseek-v3"},
        )
        evidence = run_ui_action(
            evidence_runner,
            {"ui_action": "api_route_evidence_capture", "route_id": "wbp-deepseek-v3"},
        )
        remove = run_ui_action(
            remove_runner,
            {"ui_action": "api_route_remove", "route_id": "wbp-disabled"},
        )

        self.assertEqual(validate["status"], "ok")
        self.assertEqual(validate["action_role"], "api_route_validation")
        self.assertEqual(validate["mutation_class"], "api_route_verification")
        self.assertFalse(validate["mutates_runtime"])
        self.assertFalse(validate["affects_primary_truth"])
        self.assertTrue(validate["confirmation_required"])
        self.assertTrue(validate["post_action_refresh_required"])
        self.assertEqual(validate["route_id"], "wbp-deepseek-v3")
        self.assertEqual(
            validate_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "validate", "--route", "wbp-deepseek-v3", "--json"),
            ],
        )
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["action_role"], "api_route_smoke_check")
        self.assertEqual(check["mutation_class"], "api_route_verification")
        self.assertFalse(check["mutates_runtime"])
        self.assertFalse(check["affects_primary_truth"])
        self.assertTrue(check["confirmation_required"])
        self.assertTrue(check["post_action_refresh_required"])
        self.assertEqual(check["route_id"], "wbp-deepseek-v3")
        self.assertEqual(
            check_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"),
            ],
        )
        self.assertEqual(allow["status"], "ok")
        self.assertEqual(allow["action_role"], "api_route_lifecycle_allow")
        self.assertEqual(allow["mutation_class"], "api_route_lifecycle")
        self.assertFalse(allow["mutates_runtime"])
        self.assertFalse(allow["affects_primary_truth"])
        self.assertTrue(allow["confirmation_required"])
        self.assertTrue(allow["post_action_refresh_required"])
        self.assertEqual(allow["route_id"], "wbp-disabled")
        self.assertEqual(
            allow_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "enable", "--route", "wbp-disabled", "--json"),
            ],
        )
        self.assertEqual(disable["status"], "ok")
        self.assertEqual(disable["action_role"], "api_route_lifecycle_disable")
        self.assertEqual(disable["mutation_class"], "api_route_lifecycle")
        self.assertFalse(disable["mutates_runtime"])
        self.assertFalse(disable["affects_primary_truth"])
        self.assertTrue(disable["confirmation_required"])
        self.assertTrue(disable["post_action_refresh_required"])
        self.assertEqual(disable["route_id"], "wbp-deepseek-v3")
        self.assertEqual(
            disable_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "disable", "--route", "wbp-deepseek-v3", "--json"),
            ],
        )
        self.assertEqual(profile["status"], "ok")
        self.assertEqual(profile["action_role"], "api_route_profile_packet")
        self.assertEqual(profile["mutation_class"], "api_route_support")
        self.assertFalse(profile["mutates_runtime"])
        self.assertFalse(profile["affects_primary_truth"])
        self.assertTrue(profile["confirmation_required"])
        self.assertFalse(profile["post_action_refresh_required"])
        self.assertEqual(profile["route_id"], "wbp-deepseek-v3")
        self.assertFalse(profile["result"]["data"]["writes_external_config"])
        self.assertFalse(profile["result"]["data"]["profile_ready"])
        self.assertFalse(profile["result"]["data"]["listener_proven"])
        self.assertTrue(profile["result"]["data"]["runtime_claim_blocked"])
        self.assertEqual(
            profile_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "profile", "codex-desktop", "--route", "wbp-deepseek-v3", "--json"),
            ],
        )
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(evidence["action_role"], "api_route_local_evidence_capture")
        self.assertEqual(evidence["mutation_class"], "api_route_support_artifact")
        self.assertFalse(evidence["mutates_runtime"])
        self.assertFalse(evidence["affects_primary_truth"])
        self.assertTrue(evidence["confirmation_required"])
        self.assertFalse(evidence["post_action_refresh_required"])
        self.assertEqual(evidence["route_id"], "wbp-deepseek-v3")
        self.assertFalse(evidence["result"]["data"]["network_dependent_evidence"])
        self.assertIn("evidence_path", evidence["result"]["data"])
        self.assertIn("/tmp/wbp-evidence/", evidence["result"]["data"]["evidence_path"])
        self.assertEqual(
            evidence_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "evidence", "capture", "--route", "wbp-deepseek-v3", "--json"),
            ],
        )
        self.assertEqual(remove["status"], "ok")
        self.assertEqual(remove["action_role"], "api_route_registry_cleanup")
        self.assertEqual(remove["mutation_class"], "api_route_registry_cleanup")
        self.assertFalse(remove["mutates_runtime"])
        self.assertFalse(remove["affects_primary_truth"])
        self.assertTrue(remove["confirmation_required"])
        self.assertTrue(remove["post_action_refresh_required"])
        self.assertEqual(remove["route_id"], "wbp-disabled")
        self.assertEqual(remove["result"]["changed_files"], ["/tmp/routes.json", "/tmp/state.json"])
        self.assertEqual(
            remove_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "remove", "--route", "wbp-disabled", "--json"),
            ],
        )

    def test_api_route_actions_reject_bad_targets_without_execution(self) -> None:
        missing_runner = MappingRunner(live_payloads())
        unsafe_runner = MappingRunner(live_payloads())
        unknown_runner = MappingRunner(live_payloads())
        disabled_runner = MappingRunner(
            {
                **live_payloads(),
                ("external-models", "routes", "list", "--json"): routes_list_packet(
                    "wbp-disabled",
                    enabled=False,
                ),
                (
                    "external-models",
                    "profile",
                    "codex-desktop",
                    "--route",
                    "wbp-disabled",
                    "--json",
                ): command_packet(
                    human_message="Codex Desktop profile contract generated without mutating config.",
                    data={
                        "profile_kind": "codex_desktop_openai_compatible",
                        "route_id": "wbp-disabled",
                        "base_url": None,
                        "model": "wbp-disabled",
                        "api_key_source": "managed_local_token",
                        "writes_external_config": False,
                        "profile_ready": False,
                        "listener_proven": False,
                        "runtime_claim_blocked": True,
                        "synthetic_endpoint_contract": True,
                        "prerequisite": "live_listener_contour_required",
                    },
                ),
                (
                    "external-models",
                    "evidence",
                    "capture",
                    "--route",
                    "wbp-disabled",
                    "--json",
                ): command_packet(
                    human_message="Local external-models evidence captured from foundation contract.",
                    changed_files=["/tmp/wbp-evidence/wbp-disabled.json"],
                    data={
                        "route_id": "wbp-disabled",
                        "network_dependent_evidence": False,
                        "evidence_path": "/tmp/wbp-evidence/wbp-disabled.json",
                    },
                ),
            }
        )
        allow_enabled_runner = MappingRunner(live_payloads())
        malformed_runner = MappingRunner(
            {
                **live_payloads(),
                ("external-models", "routes", "list", "--json"): command_packet(
                    human_message="External-models routes malformed.",
                    data={"count": 1, "routes": "not-a-list"},
                ),
            }
        )
        extra_runner = MappingRunner(live_payloads())
        remove_enabled_runner = MappingRunner(live_payloads())
        remove_unproven_runner = MappingRunner(
            {
                **live_payloads(),
                ("external-models", "routes", "list", "--json"): command_packet(
                    human_message="External-models routes listed from local registry.",
                    data={
                        "count": 1,
                        "routes": [
                            {
                                "route_id": "wbp-unproven",
                                "display_name": "Unproven",
                            }
                        ],
                    },
                ),
            }
        )

        missing = run_ui_action(missing_runner, {"ui_action": "api_route_validate"})
        unsafe = run_ui_action(
            unsafe_runner,
            {"ui_action": "api_route_validate", "route_id": "../wbp-deepseek-v3"},
        )
        unknown = run_ui_action(
            unknown_runner,
            {"ui_action": "api_route_validate", "route_id": "wbp-missing"},
        )
        disabled = run_ui_action(
            disabled_runner,
            {"ui_action": "api_route_check", "route_id": "wbp-disabled"},
        )
        allow_enabled = run_ui_action(
            allow_enabled_runner,
            {"ui_action": "api_route_allow", "route_id": "wbp-deepseek-v3"},
        )
        allow_extra = run_ui_action(
            extra_runner,
            {
                "ui_action": "api_route_allow",
                "route_id": "wbp-disabled",
                "secret_ref": "OPENROUTER_API_KEY",
            },
        )
        disable_disabled = run_ui_action(
            disabled_runner,
            {"ui_action": "api_route_disable", "route_id": "wbp-disabled"},
        )
        malformed = run_ui_action(
            malformed_runner,
            {"ui_action": "api_route_validate", "route_id": "wbp-deepseek-v3"},
        )
        extra = run_ui_action(
            extra_runner,
            {
                "ui_action": "api_route_check",
                "route_id": "wbp-deepseek-v3",
                "argv": "external-models routes disable",
            },
        )
        profile_disabled = run_ui_action(
            disabled_runner,
            {"ui_action": "api_route_profile", "route_id": "wbp-disabled"},
        )
        evidence_disabled = run_ui_action(
            disabled_runner,
            {"ui_action": "api_route_evidence_capture", "route_id": "wbp-disabled"},
        )
        remove_enabled = run_ui_action(
            remove_enabled_runner,
            {"ui_action": "api_route_remove", "route_id": "wbp-deepseek-v3"},
        )
        remove_extra = run_ui_action(
            extra_runner,
            {
                "ui_action": "api_route_remove",
                "route_id": "wbp-disabled",
                "raw_route_json": "{}",
            },
        )
        remove_unproven = run_ui_action(
            remove_unproven_runner,
            {"ui_action": "api_route_remove", "route_id": "wbp-unproven"},
        )

        self.assertEqual(missing["result"]["machine_error_code"], "UI_API_ROUTE_ID_REQUIRED")
        self.assertEqual(unsafe["result"]["machine_error_code"], "UI_API_ROUTE_ID_INVALID")
        self.assertEqual(unknown["result"]["machine_error_code"], "UI_API_ROUTE_ID_NOT_FOUND")
        self.assertEqual(
            disabled["result"]["machine_error_code"],
            "UI_API_ROUTE_DISABLED_INELIGIBLE",
        )
        self.assertEqual(
            allow_enabled["result"]["machine_error_code"],
            "UI_API_ROUTE_ALLOW_INELIGIBLE",
        )
        self.assertEqual(allow_extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(
            disable_disabled["result"]["machine_error_code"],
            "UI_API_ROUTE_DISABLED_INELIGIBLE",
        )
        self.assertEqual(
            malformed["result"]["machine_error_code"],
            "UI_API_ROUTE_VALIDATE_ROUTE_LIST_INVALID",
        )
        self.assertEqual(extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(profile_disabled["status"], "ok")
        self.assertEqual(evidence_disabled["status"], "ok")
        self.assertEqual(
            remove_enabled["result"]["machine_error_code"],
            "UI_API_ROUTE_REMOVE_INELIGIBLE",
        )
        self.assertEqual(remove_extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(
            remove_unproven["result"]["machine_error_code"],
            "UI_API_ROUTE_REMOVE_STATE_UNPROVEN",
        )
        self.assertEqual(missing_runner.calls, [])
        self.assertEqual(unsafe_runner.calls, [])
        self.assertEqual(
            unknown_runner.calls,
            [("external-models", "routes", "list", "--json")],
        )
        self.assertEqual(
            disabled_runner.calls,
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "list", "--json"),
                ("external-models", "profile", "codex-desktop", "--route", "wbp-disabled", "--json"),
                ("external-models", "routes", "list", "--json"),
                ("external-models", "evidence", "capture", "--route", "wbp-disabled", "--json"),
            ],
        )
        self.assertEqual(
            allow_enabled_runner.calls,
            [("external-models", "routes", "list", "--json")],
        )
        self.assertEqual(
            remove_enabled_runner.calls,
            [("external-models", "routes", "list", "--json")],
        )
        self.assertEqual(
            remove_unproven_runner.calls,
            [("external-models", "routes", "list", "--json")],
        )
        self.assertEqual(
            malformed_runner.calls,
            [("external-models", "routes", "list", "--json")],
        )
        self.assertEqual(extra_runner.calls, [])
        for calls in [
            missing_runner.calls,
            unsafe_runner.calls,
            unknown_runner.calls,
            disabled_runner.calls,
            allow_enabled_runner.calls,
            malformed_runner.calls,
            extra_runner.calls,
        ]:
            self.assertNotIn(
                ("external-models", "routes", "validate", "--route", "wbp-deepseek-v3", "--json"),
                calls,
            )
            self.assertNotIn(
                ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"),
                calls,
            )
            self.assertNotIn(
                ("external-models", "routes", "enable", "--route", "wbp-deepseek-v3", "--json"),
                calls,
            )
            self.assertNotIn(
                ("external-models", "routes", "disable", "--route", "wbp-disabled", "--json"),
                calls,
            )

    def test_hold_release_actions_preflight_eligibility_and_execute_exact_commands(self) -> None:
        hold_runner = MappingRunner(live_payloads())
        release_runner = MappingRunner(live_payloads())

        hold = run_ui_action(
            hold_runner,
            {"ui_action": "hold_account", "account_id": "acct-active"},
        )
        release = run_ui_action(
            release_runner,
            {"ui_action": "release_account", "account_id": "acct-hold"},
        )

        self.assertEqual(hold["status"], "ok")
        self.assertEqual(hold["action_role"], "account_lifecycle_hold")
        self.assertFalse(hold["mutates_runtime"])
        self.assertTrue(hold["confirmation_required"])
        self.assertEqual(hold["account_id"], "acct-active")
        self.assertEqual(
            hold_runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "hold", "acct-active", "--json"),
            ],
        )
        self.assertEqual(release["status"], "ok")
        self.assertEqual(release["action_role"], "account_lifecycle_release")
        self.assertFalse(release["mutates_runtime"])
        self.assertTrue(release["confirmation_required"])
        self.assertEqual(release["account_id"], "acct-hold")
        self.assertEqual(
            release_runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "release", "acct-hold", "--json"),
            ],
        )

    def test_hold_release_reject_ineligible_targets_without_lifecycle_execution(self) -> None:
        hold_runner = MappingRunner(live_payloads())
        release_runner = MappingRunner(live_payloads())
        retired_runner = MappingRunner(live_payloads())
        extra_runner = MappingRunner(live_payloads())

        already_held = run_ui_action(
            hold_runner,
            {"ui_action": "hold_account", "account_id": "acct-hold"},
        )
        not_held = run_ui_action(
            release_runner,
            {"ui_action": "release_account", "account_id": "acct-active"},
        )
        retired = run_ui_action(
            retired_runner,
            {"ui_action": "hold_account", "account_id": "acct-problem"},
        )
        extra = run_ui_action(
            extra_runner,
            {"ui_action": "release_account", "account_id": "acct-hold", "argv": "accounts promote"},
        )

        self.assertEqual(already_held["result"]["machine_error_code"], "UI_ACCOUNT_HOLD_INELIGIBLE")
        self.assertEqual(not_held["result"]["machine_error_code"], "UI_ACCOUNT_RELEASE_INELIGIBLE")
        self.assertEqual(
            retired["result"]["machine_error_code"],
            "UI_ACCOUNT_LIFECYCLE_RETIRED_INELIGIBLE",
        )
        self.assertEqual(extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(hold_runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(release_runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(retired_runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(extra_runner.calls, [])
        for calls in [hold_runner.calls, release_runner.calls, retired_runner.calls, extra_runner.calls]:
            self.assertNotIn(("accounts", "hold", "acct-hold", "--json"), calls)
            self.assertNotIn(("accounts", "release", "acct-active", "--json"), calls)

    def test_promote_demote_actions_preflight_eligibility_and_execute_exact_commands(self) -> None:
        promote_runner = MappingRunner(live_payloads())
        demote_runner = MappingRunner(live_payloads())

        promote = run_ui_action(
            promote_runner,
            {"ui_action": "promote_account", "account_id": "acct-reserve"},
        )
        demote = run_ui_action(
            demote_runner,
            {"ui_action": "demote_account", "account_id": "acct-active"},
        )

        self.assertEqual(promote["status"], "ok")
        self.assertEqual(promote["action_role"], "account_lifecycle_promotion")
        self.assertFalse(promote["mutates_runtime"])
        self.assertFalse(promote["affects_primary_truth"])
        self.assertTrue(promote["confirmation_required"])
        self.assertTrue(promote["post_action_refresh_required"])
        self.assertEqual(promote["account_id"], "acct-reserve")
        self.assertEqual(
            promote_runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "promote", "acct-reserve", "--json"),
            ],
        )
        self.assertEqual(demote["status"], "ok")
        self.assertEqual(demote["action_role"], "account_lifecycle_demotion")
        self.assertFalse(demote["mutates_runtime"])
        self.assertFalse(demote["affects_primary_truth"])
        self.assertTrue(demote["confirmation_required"])
        self.assertTrue(demote["post_action_refresh_required"])
        self.assertEqual(demote["account_id"], "acct-active")
        self.assertEqual(
            demote_runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "demote", "acct-active", "--json"),
            ],
        )

    def test_promote_demote_reject_ineligible_targets_without_lifecycle_execution(self) -> None:
        promote_active_runner = MappingRunner(live_payloads())
        promote_hold_runner = MappingRunner(live_payloads())
        promote_retired_runner = MappingRunner(live_payloads())
        demote_reserve_runner = MappingRunner(live_payloads())
        demote_hold_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "list", "--json"): accounts_packet(
                    accounts=[
                        account("acct-active-hold", "active", "healthy", manual_hold=True),
                    ],
                ),
            }
        )
        demote_retired_runner = MappingRunner(live_payloads())
        extra_runner = MappingRunner(live_payloads())

        promote_active = run_ui_action(
            promote_active_runner,
            {"ui_action": "promote_account", "account_id": "acct-active"},
        )
        promote_hold = run_ui_action(
            promote_hold_runner,
            {"ui_action": "promote_account", "account_id": "acct-hold"},
        )
        promote_retired = run_ui_action(
            promote_retired_runner,
            {"ui_action": "promote_account", "account_id": "acct-problem"},
        )
        demote_reserve = run_ui_action(
            demote_reserve_runner,
            {"ui_action": "demote_account", "account_id": "acct-reserve"},
        )
        demote_hold = run_ui_action(
            demote_hold_runner,
            {"ui_action": "demote_account", "account_id": "acct-active-hold"},
        )
        demote_retired = run_ui_action(
            demote_retired_runner,
            {"ui_action": "demote_account", "account_id": "acct-problem"},
        )
        extra = run_ui_action(
            extra_runner,
            {"ui_action": "promote_account", "account_id": "acct-reserve", "argv": "accounts retire"},
        )

        self.assertEqual(
            promote_active["result"]["machine_error_code"],
            "UI_ACCOUNT_PROMOTE_INELIGIBLE",
        )
        self.assertEqual(
            promote_hold["result"]["machine_error_code"],
            "UI_ACCOUNT_PROMOTE_INELIGIBLE",
        )
        self.assertEqual(
            promote_retired["result"]["machine_error_code"],
            "UI_ACCOUNT_LIFECYCLE_RETIRED_INELIGIBLE",
        )
        self.assertEqual(
            demote_reserve["result"]["machine_error_code"],
            "UI_ACCOUNT_DEMOTE_INELIGIBLE",
        )
        self.assertEqual(
            demote_hold["result"]["machine_error_code"],
            "UI_ACCOUNT_DEMOTE_INELIGIBLE",
        )
        self.assertEqual(
            demote_retired["result"]["machine_error_code"],
            "UI_ACCOUNT_LIFECYCLE_RETIRED_INELIGIBLE",
        )
        self.assertEqual(extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(extra_runner.calls, [])
        for calls in [
            promote_active_runner.calls,
            promote_hold_runner.calls,
            promote_retired_runner.calls,
            demote_reserve_runner.calls,
            demote_hold_runner.calls,
            demote_retired_runner.calls,
        ]:
            self.assertEqual(calls, [("accounts", "list", "--json")])
            self.assertNotIn(("accounts", "promote", "acct-reserve", "--json"), calls)
            self.assertNotIn(("accounts", "demote", "acct-active", "--json"), calls)

    def test_retire_action_preflights_eligibility_and_executes_exact_commands(self) -> None:
        active_runner = MappingRunner(live_payloads())
        reserve_runner = MappingRunner(live_payloads())

        active = run_ui_action(
            active_runner,
            {"ui_action": "retire_account", "account_id": "acct-active"},
        )
        reserve = run_ui_action(
            reserve_runner,
            {"ui_action": "retire_account", "account_id": "acct-reserve"},
        )

        self.assertEqual(active["status"], "ok")
        self.assertEqual(active["action_role"], "account_lifecycle_retirement")
        self.assertFalse(active["mutates_runtime"])
        self.assertFalse(active["affects_primary_truth"])
        self.assertTrue(active["confirmation_required"])
        self.assertTrue(active["post_action_refresh_required"])
        self.assertEqual(active["account_id"], "acct-active")
        self.assertEqual(
            active_runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "retire", "acct-active", "--json"),
            ],
        )
        self.assertEqual(reserve["status"], "ok")
        self.assertEqual(reserve["action_role"], "account_lifecycle_retirement")
        self.assertEqual(reserve["account_id"], "acct-reserve")
        self.assertEqual(
            reserve_runner.calls,
            [
                ("accounts", "list", "--json"),
                ("accounts", "retire", "acct-reserve", "--json"),
            ],
        )

    def test_retire_rejects_bad_targets_without_lifecycle_execution(self) -> None:
        missing_runner = MappingRunner(live_payloads())
        retired_runner = MappingRunner(live_payloads())
        unknown_runner = MappingRunner(live_payloads())
        unsafe_runner = MappingRunner(live_payloads())
        extra_runner = MappingRunner(live_payloads())
        raw_action_runner = MappingRunner(live_payloads())
        malformed_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "list", "--json"): command_packet(
                    human_message="Accounts malformed.",
                    accounts="not-a-list",
                    registry_identity={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "next_action": "none",
                    },
                ),
            }
        )

        missing = run_ui_action(missing_runner, {"ui_action": "retire_account"})
        retired = run_ui_action(
            retired_runner,
            {"ui_action": "retire_account", "account_id": "acct-problem"},
        )
        unknown = run_ui_action(
            unknown_runner,
            {"ui_action": "retire_account", "account_id": "acct-missing"},
        )
        unsafe = run_ui_action(
            unsafe_runner,
            {"ui_action": "retire_account", "account_id": "../acct-active"},
        )
        extra = run_ui_action(
            extra_runner,
            {"ui_action": "retire_account", "account_id": "acct-active", "argv": "accounts retire"},
        )
        raw_action = run_ui_action(
            raw_action_runner,
            {"ui_action": "accounts_retire", "account_id": "acct-active"},
        )
        malformed = run_ui_action(
            malformed_runner,
            {"ui_action": "retire_account", "account_id": "acct-active"},
        )

        self.assertEqual(missing["result"]["machine_error_code"], "UI_ACCOUNT_ID_REQUIRED")
        self.assertEqual(
            retired["result"]["machine_error_code"],
            "UI_ACCOUNT_LIFECYCLE_RETIRED_INELIGIBLE",
        )
        self.assertEqual(unknown["result"]["machine_error_code"], "UI_ACCOUNT_ID_NOT_FOUND")
        self.assertEqual(unsafe["result"]["machine_error_code"], "UI_ACCOUNT_ID_INVALID")
        self.assertEqual(extra["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(raw_action["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(
            malformed["result"]["machine_error_code"],
            "UI_ACCOUNT_LIFECYCLE_ACCOUNT_LIST_INVALID",
        )
        self.assertEqual(missing_runner.calls, [])
        self.assertEqual(retired_runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(unknown_runner.calls, [("accounts", "list", "--json")])
        self.assertEqual(unsafe_runner.calls, [])
        self.assertEqual(extra_runner.calls, [])
        self.assertEqual(raw_action_runner.calls, [])
        self.assertEqual(malformed_runner.calls, [("accounts", "list", "--json")])
        for calls in [
            missing_runner.calls,
            retired_runner.calls,
            unknown_runner.calls,
            unsafe_runner.calls,
            extra_runner.calls,
            raw_action_runner.calls,
            malformed_runner.calls,
        ]:
            self.assertNotIn(("accounts", "retire", "acct-active", "--json"), calls)
            self.assertNotIn(("accounts", "retire", "acct-reserve", "--json"), calls)

    def test_launch_client_dispatch_uses_server_owned_bounded_path_only(self) -> None:
        runner = MappingRunner(live_payloads())

        unavailable = run_ui_action(runner, {"ui_action": "launch_client_dispatch"})
        browser_path = run_ui_action(
            runner,
            {
                "ui_action": "launch_client_dispatch",
                "client_path": "/Applications/Unsafe.app",
            },
            launch_client_path=TEST_LAUNCH_CLIENT_PATH,
            launch_copy_contract=launch_copy_contract(),
        )
        dispatched = run_ui_action(
            runner,
            {"ui_action": "launch_client_dispatch"},
            launch_client_path=TEST_LAUNCH_CLIENT_PATH,
            launch_copy_contract=launch_copy_contract(),
        )

        self.assertEqual(unavailable["status"], "integration_failure")
        self.assertEqual(
            unavailable["result"]["machine_error_code"],
            "UI_LAUNCH_CLIENT_PATH_UNAVAILABLE",
        )
        self.assertEqual(browser_path["status"], "integration_failure")
        self.assertEqual(browser_path["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(dispatched["status"], "ok")
        self.assertEqual(dispatched["action_role"], "host_client_dispatch")
        self.assertTrue(dispatched["confirmation_required"])
        self.assertTrue(dispatched["post_action_refresh_required"])
        self.assertIn("не успех сессии внешнего клиента", dispatched["action_claim_scope"])
        self.assertEqual(dispatched["result"]["data"]["launch_preflight"]["status"], "admitted")
        self.assertNotIn(TEST_LAUNCH_CLIENT_PATH, json.dumps(dispatched))
        self.assertNotIn("/tmp/wbp-copy-profile", json.dumps(dispatched))
        self.assertNotIn("/tmp/wbp-copy-data", json.dumps(dispatched))
        self.assertEqual(
            runner.calls[-1],
            ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"),
        )

    def test_launch_client_dispatch_requires_isolated_copy_preflight(self) -> None:
        runner = MappingRunner(live_payloads())

        denied = run_ui_action(
            runner,
            {"ui_action": "launch_client_dispatch"},
            launch_client_path=TEST_LAUNCH_CLIENT_PATH,
            action_phase=FULL_ACTION_PHASE,
        )

        self.assertEqual(denied["status"], "integration_failure")
        self.assertEqual(denied["availability_state"], "preflight_blocked")
        self.assertEqual(
            denied["result"]["machine_error_code"],
            "UI_LAUNCH_COPY_PREFLIGHT_REQUIRED",
        )
        self.assertEqual(denied["result"]["data"]["launch_phase"], "preflight_denied")
        self.assertEqual(
            denied["result"]["data"]["launch_preflight"]["status"],
            "denied",
        )
        self.assertEqual(runner.calls, [])

    def test_launch_client_dispatch_blocks_app_bundle_target_without_process_proof(self) -> None:
        runner = MappingRunner(live_payloads())
        with tempfile.TemporaryDirectory() as tmpdir:
            app_bundle = Path(tmpdir) / "FakeCodex.app"
            app_bundle.mkdir()
            denied = run_ui_action(
                runner,
                {"ui_action": "launch_client_dispatch"},
                launch_client_path=str(app_bundle),
                launch_copy_contract=LaunchCopyContract(
                    client_path=str(app_bundle),
                    profile_dir="/tmp/wbp-copy-profile",
                    data_dir="/tmp/wbp-copy-data",
                    copy_port=9321,
                ),
                action_phase=FULL_ACTION_PHASE,
            )

        self.assertEqual(denied["status"], "integration_failure")
        self.assertEqual(
            denied["result"]["machine_error_code"],
            "UI_LAUNCH_COPY_ISOLATION_UNPROVEN",
        )
        self.assertEqual(denied["result"]["data"]["launch_phase"], "preflight_denied")
        self.assertEqual(
            denied["result"]["data"]["launch_preflight"]["target_kind"],
            "app_bundle",
        )
        self.assertFalse(
            denied["result"]["data"]["launch_preflight"]["process_confirmation_possible"]
        )
        self.assertEqual(runner.calls, [])

    def test_launch_client_dispatch_redacts_changed_files_in_ui_result(self) -> None:
        runner = MappingRunner(
            {
                ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"): command_packet(
                    human_message="Client dispatch requested.",
                    changed_files=["/tmp/private-client-path"],
                    client_launch_result={
                        "dispatch_method": "detached_executable_spawn",
                        "dispatch_observed": True,
                        "dispatch_attempted": True,
                        "final_outcome": "dispatch_requested",
                    },
                )
            }
        )

        dispatched = run_ui_action(
            runner,
            {"ui_action": "launch_client_dispatch"},
            launch_client_path=TEST_LAUNCH_CLIENT_PATH,
            launch_copy_contract=launch_copy_contract(),
            action_phase=FULL_ACTION_PHASE,
        )

        self.assertEqual(
            dispatched["result"]["changed_files"],
            ["launch_dispatch_metadata"],
        )
        self.assertEqual(
            dispatched["result"]["data"]["launch_phase"],
            "launch_requested",
        )
        self.assertFalse(dispatched["result"]["data"]["real_codex_app_launched"])
        self.assertNotIn("/tmp/private-client-path", json.dumps(dispatched))

    def test_launch_client_dispatch_reports_real_app_process_observation(self) -> None:
        runner = MappingRunner(
            {
                ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"): command_packet(
                    human_message="Client launch observed.",
                    client_launch_result={
                        "dispatch_method": "detached_executable_spawn",
                        "dispatch_observed": True,
                        "dispatch_attempted": True,
                        "process_observed_running": True,
                        "real_codex_app_launched": True,
                        "final_outcome": "app_process_observed",
                    },
                )
            }
        )

        dispatched = run_ui_action(
            runner,
            {"ui_action": "launch_client_dispatch"},
            launch_client_path=TEST_LAUNCH_CLIENT_PATH,
            launch_copy_contract=launch_copy_contract(),
            action_phase=FULL_ACTION_PHASE,
        )

        self.assertEqual(
            dispatched["result"]["data"]["launch_phase"],
            "app_process_confirmed",
        )
        self.assertTrue(dispatched["result"]["data"]["process_confirmed"])
        self.assertTrue(dispatched["result"]["data"]["real_codex_app_launched"])
        self.assertEqual(
            dispatched["result"]["data"]["launch_claim_scope"],
            "bounded_executable_launch_with_process_observation",
        )

    def test_ui_action_endpoint_blocks_command_id_payload_and_forbidden_actions(self) -> None:
        runner = MappingRunner(live_payloads())

        command_id_payload = run_ui_action(runner, {"command_id": "diagnostics_export"})
        stable_repair_apply = run_ui_action(runner, {"ui_action": "stable_repair_apply"})
        launch_client = run_ui_action(runner, {"ui_action": "launch_client"})
        account_lifecycle = run_ui_action(runner, {"ui_action": "accounts_promote", "account_id": "acct-active"})
        route_create = run_ui_action(runner, {"ui_action": "api_route_create", "route_id": "wbp-new"})
        route_update = run_ui_action(runner, {"ui_action": "api_route_update", "route_id": "wbp-deepseek-v3"})
        route_draft = run_ui_action(runner, {"ui_action": "api_route_draft", "route_id": "wbp-draft"})
        save_settings = run_ui_action(runner, {"ui_action": "save_settings"})
        update_settings = run_ui_action(runner, {"ui_action": "update_settings"})
        settings_write = run_ui_action(runner, {"ui_action": "settings_write"})
        settings_route_config = run_ui_action(
            runner,
            {"ui_action": "save_settings", "route_config": {"route_id": "wbp-new"}},
        )
        client_path_payload = run_ui_action(
            runner,
            {"ui_action": "export_diagnostics", "client_path": "/Applications/Codex.app"},
        )
        bundle_path_payload = run_ui_action(
            runner,
            {"ui_action": "export_diagnostics", "bundle_path": "/tmp/wbp-diagnostics.zip"},
        )
        log_path_payload = run_ui_action(
            runner,
            {"ui_action": "export_diagnostics", "log_path": "/tmp/runtime.log"},
        )
        unknown = run_ui_action(runner, {"ui_action": "policy_stage_set"})

        for payload in [
            command_id_payload,
            stable_repair_apply,
            launch_client,
            account_lifecycle,
            route_create,
            route_update,
            route_draft,
            save_settings,
            update_settings,
            settings_write,
            settings_route_config,
            client_path_payload,
            bundle_path_payload,
            log_path_payload,
            unknown,
        ]:
            self.assertEqual(payload["status"], "integration_failure")
            self.assertEqual(payload["action_role"], "blocked")
            self.assertFalse(payload["mutates_runtime"])
            self.assertEqual(payload["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(runner.calls, [])

    def test_action_result_does_not_alter_runtime_visual_state(self) -> None:
        runner = MappingRunner(live_payloads())

        snapshot_before = build_live_readonly_snapshot(runner)
        diagnostics = run_ui_action(runner, {"ui_action": "export_diagnostics"})
        snapshot_after = build_live_readonly_snapshot(runner)

        self.assertEqual(diagnostics["action_role"], "support_artifact")
        self.assertEqual(snapshot_before["runtime"]["visual_state"], "healthy")
        self.assertEqual(snapshot_after["runtime"]["visual_state"], "healthy")
        self.assertFalse(diagnostics["affects_primary_truth"])

    def test_diagnostics_export_forwards_safe_artifact_metadata(self) -> None:
        runner = MappingRunner(
            {
                **live_payloads(),
                ("diagnostics", "export", "--json"): command_packet(
                    human_message="Diagnostics exported.",
                    changed_files=["/private/tmp/wild-boar-proxy-diagnostics-secret"],
                    bundle_path="/private/tmp/wild-boar-proxy-diagnostics-secret",
                ),
            }
        )

        diagnostics = run_ui_action(runner, {"ui_action": "export_diagnostics"})

        self.assertEqual(diagnostics["status"], "ok")
        self.assertEqual(diagnostics["action_role"], "support_artifact")
        self.assertEqual(
            diagnostics["result"]["data"]["bundle_path"],
            "wild-boar-proxy-diagnostics-secret",
        )
        self.assertEqual(diagnostics["result"]["changed_files"], ["diagnostics_bundle"])
        self.assertEqual(diagnostics["result"]["data"]["redaction_status"], "unreported")
        self.assertEqual(diagnostics["result"]["data"]["claim_scope"], "support_artifact_only")
        self.assertNotIn("/private/tmp", json.dumps(diagnostics))
        self.assertEqual(runner.calls[-1], ("diagnostics", "export", "--json"))

    def test_diagnostics_export_normalizes_redaction_status_without_widening_scope(self) -> None:
        passed_runner = MappingRunner(
            {
                **live_payloads(),
                ("diagnostics", "export", "--json"): command_packet(
                    changed_files=["/private/tmp/wbp-diagnostics"],
                    bundle_path="/private/tmp/wbp-diagnostics.zip",
                    redaction_status="passed",
                ),
            }
        )
        failed_runner = MappingRunner(
            {
                **live_payloads(),
                ("diagnostics", "export", "--json"): command_packet(
                    changed_files=["/private/tmp/wbp-diagnostics"],
                    bundle_path="/private/tmp/wbp-diagnostics.zip",
                    diagnostics_redaction_status="failed",
                ),
            }
        )

        passed = run_ui_action(passed_runner, {"ui_action": "export_diagnostics"})
        failed = run_ui_action(failed_runner, {"ui_action": "export_diagnostics"})

        self.assertEqual(passed["result"]["data"]["redaction_status"], "enabled")
        self.assertEqual(failed["result"]["data"]["redaction_status"], "failed")
        self.assertEqual(passed["result"]["data"]["claim_scope"], "support_artifact_only")
        self.assertEqual(failed["result"]["data"]["claim_scope"], "support_artifact_only")
        self.assertNotIn("/private/tmp", json.dumps(passed))
        self.assertNotIn("/private/tmp", json.dumps(failed))

    def test_http_action_endpoint_uses_ui_action_not_command_id(self) -> None:
        runner = MappingRunner(live_payloads())
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                runner=runner,
                launch_client_path=TEST_LAUNCH_CLIENT_PATH,
                launch_copy_contract=launch_copy_contract(),
                action_phase=FULL_ACTION_PHASE,
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            accepted = json.loads(
                post_json(f"{base_url}/api/action", {"ui_action": "export_diagnostics"})
            )
            rejected = json.loads(
                post_json(f"{base_url}/api/action", {"command_id": "diagnostics_export"})
            )
            metadata = json.loads(fetch(f"{base_url}/api/actions"))
            launch = json.loads(
                post_json(f"{base_url}/api/action", {"ui_action": "launch_client_dispatch"})
            )
            validate = json.loads(
                post_json(
                    f"{base_url}/api/action",
                    {"ui_action": "validate_account", "account_id": "acct-active"},
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(accepted["status"], "ok")
        self.assertEqual(rejected["status"], "integration_failure")
        self.assertIn("sync_runtime", metadata["actions"])
        self.assertNotIn("adapter_command_id", json.dumps(metadata))
        self.assertNotIn(TEST_LAUNCH_CLIENT_PATH, json.dumps(metadata))
        self.assertEqual(launch["status"], "ok")
        self.assertEqual(launch["result"]["data"]["launch_preflight"]["status"], "admitted")
        self.assertEqual(validate["status"], "ok")
        self.assertEqual(validate["action_role"], "account_verification")
        self.assertEqual(
            runner.calls,
            [
                ("diagnostics", "export", "--json"),
                ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"),
                ("accounts", "list", "--json"),
                ("accounts", "validate", "acct-active", "--json"),
            ],
        )

    def test_http_operator_flow_uses_fake_runner_and_canonical_refreshes(self) -> None:
        payloads = {
            **live_payloads(),
            ("external-models", "routes", "list", "--json"): routes_list_packet_for_operator_flow(),
            ("external-models", "routes", "enable", "--route", "wbp-disabled", "--json"): command_packet(
                human_message="External-models route enabled: wbp-disabled.",
                liveness="not_applicable",
                severity="recoverable",
                operator_action="none",
                data={"route_id": "wbp-disabled", "enabled": True},
            ),
            ("external-models", "routes", "remove", "--route", "wbp-disabled", "--json"): command_packet(
                human_message="External-models route removed: wbp-disabled.",
                liveness="not_applicable",
                severity="recoverable",
                operator_action="none",
                changed_files=["/tmp/routes.json", "/tmp/state.json"],
                data={"route_id": "wbp-disabled"},
            ),
        }
        runner = MappingRunner(payloads)
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                runner=runner,
                launch_client_path=TEST_LAUNCH_CLIENT_PATH,
                launch_copy_contract=launch_copy_contract(),
                action_phase=FULL_ACTION_PHASE,
                post_rate_limit_per_second=1000,
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            index = fetch(f"{base_url}/?source=live")
            overview = json.loads(fetch(f"{base_url}/api/live-readonly"))
            accounts = json.loads(fetch(f"{base_url}/api/accounts-readonly"))
            api_connections = json.loads(fetch(f"{base_url}/api/api-connections-readonly"))
            metadata = json.loads(fetch(f"{base_url}/api/actions"))
            flow_start = len(runner.calls)
            flow_steps = [
                ("refresh_health_detail", {}, None),
                ("stable_repair_plan", {}, None),
                ("sync_runtime", {}, "overview"),
                ("set_mode_stable", {}, "overview"),
                ("set_mode_managed", {}, "overview"),
                ("launch_smoke", {}, "overview"),
                ("launch_client_dispatch", {}, "overview"),
                ("validate_account", {"account_id": "acct-active"}, "accounts"),
                ("recheck_account", {"account_id": "acct-active"}, "accounts"),
                ("hold_account", {"account_id": "acct-active"}, "accounts"),
                ("release_account", {"account_id": "acct-hold"}, "accounts"),
                ("promote_account", {"account_id": "acct-reserve"}, "accounts"),
                ("demote_account", {"account_id": "acct-active"}, "accounts"),
                ("retire_account", {"account_id": "acct-reserve"}, "accounts"),
                ("onboard_account", {}, "accounts"),
                ("export_diagnostics", {}, None),
                ("api_route_validate", {"route_id": "wbp-deepseek-v3"}, "api_connections"),
                ("api_route_check", {"route_id": "wbp-deepseek-v3"}, "api_connections"),
                ("api_route_allow", {"route_id": "wbp-disabled"}, "api_connections"),
                ("api_route_disable", {"route_id": "wbp-deepseek-v3"}, "api_connections"),
                ("api_route_profile", {"route_id": "wbp-deepseek-v3"}, None),
                ("api_route_evidence_capture", {"route_id": "wbp-deepseek-v3"}, None),
                ("api_route_remove", {"route_id": "wbp-disabled"}, "api_connections"),
            ]
            action_results: dict[str, dict[str, object]] = {}
            for ui_action, extra_payload, refresh_target in flow_steps:
                action_results[ui_action] = json.loads(
                    post_json(
                        f"{base_url}/api/action",
                        {"ui_action": ui_action, **extra_payload},
                    )
                )
                if refresh_target == "accounts":
                    refreshed = json.loads(fetch(f"{base_url}/api/accounts-readonly"))
                    self.assertEqual(refreshed["status"], "ok")
                    self.assertEqual(refreshed["source"], "accounts_readonly")
                elif refresh_target == "overview":
                    refreshed = json.loads(fetch(f"{base_url}/api/live-readonly"))
                    self.assertEqual(refreshed["status"], "ok")
                    self.assertEqual(refreshed["source"], "live_readonly")
                elif refresh_target == "api_connections":
                    refreshed = json.loads(fetch(f"{base_url}/api/api-connections-readonly"))
                    self.assertEqual(refreshed["status"], "ok")
                    self.assertEqual(refreshed["source"], "api_connections_readonly")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertIn("sourcePicker", index)
        self.assertEqual(overview["status"], "ok")
        self.assertEqual(overview["source"], "live_readonly")
        self.assertEqual(accounts["status"], "ok")
        self.assertEqual(accounts["source"], "accounts_readonly")
        self.assertEqual(api_connections["status"], "ok")
        self.assertEqual(api_connections["source"], "api_connections_readonly")
        self.assertNotIn("adapter_command_id", json.dumps(metadata))
        self.assertIn("setup_discovery", metadata["actions"])
        self.assertIn("legacy_import_discovery", metadata["actions"])
        self.assertNotIn("select_client", metadata["actions"])
        self.assertIn("legacy_import", metadata["actions"])
        self.assertTrue(metadata["actions"]["setup_discovery"]["available"])
        self.assertTrue(metadata["actions"]["legacy_import_discovery"]["available"])
        self.assertFalse(metadata["actions"]["legacy_import"]["available"])
        self.assertNotIn("api_route_create", metadata["actions"])
        self.assertNotIn("api_route_update", metadata["actions"])
        self.assertNotIn("api_route_draft", metadata["actions"])
        for ui_action in [
            "refresh_health_detail",
            "stable_repair_plan",
            "sync_runtime",
            "set_mode_stable",
            "set_mode_managed",
            "launch_smoke",
            "launch_client_dispatch",
            "validate_account",
            "recheck_account",
            "hold_account",
            "release_account",
            "promote_account",
            "demote_account",
            "retire_account",
            "onboard_account",
            "export_diagnostics",
            "api_route_validate",
            "api_route_check",
            "api_route_allow",
            "api_route_disable",
            "api_route_profile",
            "api_route_evidence_capture",
            "api_route_remove",
        ]:
            self.assertEqual(action_results[ui_action]["status"], "ok")
            self.assertEqual(action_results[ui_action]["source"], "ui_action")
            self.assertFalse(action_results[ui_action]["affects_primary_truth"])

        self.assertTrue(action_results["sync_runtime"]["confirmation_required"])
        self.assertTrue(action_results["set_mode_stable"]["confirmation_required"])
        self.assertTrue(action_results["set_mode_managed"]["confirmation_required"])
        self.assertTrue(action_results["launch_client_dispatch"]["confirmation_required"])
        self.assertIn("не успех сессии внешнего клиента", action_results["launch_client_dispatch"]["action_claim_scope"])
        self.assertEqual(
            action_results["launch_client_dispatch"]["result"]["data"]["launch_preflight"]["status"],
            "admitted",
        )
        self.assertEqual(
            action_results["onboard_account"]["result"]["data"]["login_bridge"]["status"],
            "waiting_for_user",
        )
        self.assertFalse(action_results["onboard_account"]["post_action_refresh_required"])
        self.assertEqual(action_results["export_diagnostics"]["action_role"], "support_artifact")
        self.assertFalse(action_results["export_diagnostics"]["post_action_refresh_required"])
        self.assertEqual(action_results["api_route_remove"]["action_role"], "api_route_registry_cleanup")
        self.assertEqual(action_results["api_route_remove"]["route_id"], "wbp-disabled")
        self.assertFalse(action_results["api_route_profile"]["result"]["data"]["writes_external_config"])
        self.assertFalse(action_results["api_route_profile"]["result"]["data"]["profile_ready"])
        self.assertTrue(action_results["api_route_profile"]["result"]["data"]["runtime_claim_blocked"])
        self.assertFalse(action_results["api_route_evidence_capture"]["result"]["data"]["network_dependent_evidence"])

        expected_sequences = [
            [
                ("healthcheck", "--json"),
            ],
            [
                ("stable", "repair", "--dry-run", "--json"),
            ],
            [
                ("sync", "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
                ("healthcheck", "--json"),
                ("rollout", "rotation", "inspect", "--json"),
            ],
            [
                ("mode", "set", "stable", "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
                ("healthcheck", "--json"),
                ("rollout", "rotation", "inspect", "--json"),
            ],
            [
                ("mode", "set", "managed", "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
                ("healthcheck", "--json"),
                ("rollout", "rotation", "inspect", "--json"),
            ],
            [
                ("launch", "smoke", "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
                ("healthcheck", "--json"),
                ("rollout", "rotation", "inspect", "--json"),
            ],
            [
                ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
                ("healthcheck", "--json"),
                ("rollout", "rotation", "inspect", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                ("accounts", "validate", "acct-active", "--json"),
                ("accounts", "list", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                ("accounts", "hold", "acct-active", "--json"),
                ("accounts", "list", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                ("accounts", "release", "acct-hold", "--json"),
                ("accounts", "list", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                ("accounts", "promote", "acct-reserve", "--json"),
                ("accounts", "list", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                ("accounts", "demote", "acct-active", "--json"),
                ("accounts", "list", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                ("accounts", "retire", "acct-reserve", "--json"),
                ("accounts", "list", "--json"),
            ],
            [
                ("accounts", "list", "--json"),
                (
                    "accounts",
                    "login",
                    "start",
                    "--provider",
                    "codex",
                    "--mode",
                    "device",
                    "--json",
                ),
                ("accounts", "list", "--json"),
            ],
            [
                ("diagnostics", "export", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "validate", "--route", "wbp-deepseek-v3", "--json"),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "enable", "--route", "wbp-disabled", "--json"),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "disable", "--route", "wbp-deepseek-v3", "--json"),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "profile", "codex-desktop", "--route", "wbp-deepseek-v3", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "evidence", "capture", "--route", "wbp-deepseek-v3", "--json"),
            ],
            [
                ("external-models", "routes", "list", "--json"),
                ("external-models", "routes", "remove", "--route", "wbp-disabled", "--json"),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
        ]
        cursor = flow_start
        for sequence in expected_sequences:
            for command in sequence:
                try:
                    cursor = runner.calls.index(command, cursor) + 1
                except ValueError as exc:
                    raise AssertionError(f"missing command in operator flow: {command}") from exc
        forbidden_runtime_commands = [
            ("policy", "stage", "set", "--json"),
            ("rollout", "stage", "advance", "--json"),
            ("stable", "repair", "--apply", "--json"),
        ]
        for command in forbidden_runtime_commands:
            self.assertNotIn(command, runner.calls)

    def test_server_source_contains_no_direct_runtime_truth_file_reads(self) -> None:
        source = (ROOT / "wild_boar_proxy" / "web_design_live_server.py").read_text()
        forbidden = [
            "state" + ".json",
            "supervisor" + "-state",
            ".codex" + "-custom-cli",
            ".cli" + "-proxy-api",
        ]
        for fragment in forbidden:
            self.assertNotIn(fragment, source)


def live_payloads() -> dict[tuple[str, ...], dict[str, object]]:
    return {
        ("status", "--json"): status_packet(),
        ("healthcheck", "--json"): healthcheck_ok_packet(),
        ("mode", "get", "--json"): mode_packet(),
        ("accounts", "list", "--json"): accounts_packet(),
        (
            "accounts",
            "login",
            "start",
            "--provider",
            "codex",
            "--mode",
            "device",
            "--json",
        ): codex_login_start_packet(),
        (
            "accounts",
            "login",
            "status",
            "--session",
            TEST_CODEX_LOGIN_SESSION_ID,
            "--json",
        ): codex_login_status_packet(),
        (
            "accounts",
            "login",
            "complete",
            "--session",
            TEST_CODEX_LOGIN_SESSION_ID,
            "--json",
        ): codex_login_complete_packet(),
        ("accounts", "onboard", "--json"): onboarding_packet("reserve_only_success"),
        ("accounts", "login", "start", "--provider", "sandbox", "--json"): login_start_packet(),
        (
            "accounts",
            "login",
            "complete",
            "--session",
            TEST_SANDBOX_LOGIN_SESSION_ID,
            "--state",
            TEST_SANDBOX_LOGIN_STATE,
            "--proof",
            "sandbox-ok",
            "--json",
        ): login_complete_packet(),
        (
            "accounts",
            "onboard",
            "--json",
            "--auth-ref",
            TEST_SANDBOX_AUTH_REF,
        ): onboarding_packet("explicit_auth_imported_to_reserve"),
        ("accounts", "validate", "acct-active", "--json"): command_packet(
            human_message="Account validation completed."
        ),
        ("accounts", "promote", "acct-reserve", "--json"): command_packet(
            human_message="Account promotion requested."
        ),
        ("accounts", "demote", "acct-active", "--json"): command_packet(
            human_message="Account demotion requested."
        ),
        ("accounts", "retire", "acct-active", "--json"): command_packet(
            human_message="Account terminal retirement requested."
        ),
        ("accounts", "retire", "acct-reserve", "--json"): command_packet(
            human_message="Account terminal retirement requested."
        ),
        ("accounts", "hold", "acct-active", "--json"): command_packet(
            human_message="Account hold completed."
        ),
        ("accounts", "release", "acct-hold", "--json"): command_packet(
            human_message="Account release completed."
        ),
        ("diagnostics", "export", "--json"): command_packet(
            human_message="Diagnostics exported.",
            data={"bundle_path": "/tmp/wbp-diagnostics.zip"},
        ),
        ("stable", "repair", "--dry-run", "--json"): command_packet(
            human_message="Stable repair dry-run completed.",
            data={"would_change": False},
        ),
        ("sync", "--json"): command_packet(human_message="Sync completed."),
        ("mode", "set", "stable", "--json"): command_packet(human_message="Stable mode requested."),
        ("mode", "set", "managed", "--json"): command_packet(human_message="Managed mode requested."),
        ("launch", "smoke", "--json"): command_packet(human_message="Launch smoke passed."),
        ("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"): command_packet(
            human_message="Client dispatch requested.",
            data={"launch_claim_scope": "dispatch_requested"},
            client_launch_result={
                "dispatch_method": "detached_executable_spawn",
                "dispatch_observed": True,
                "dispatch_attempted": True,
                "final_outcome": "dispatch_requested",
            },
        ),
        ("rollout", "rotation", "inspect", "--json"): command_packet(
            human_message="Rotation inspect passed."
        ),
        ("external-models", "credentials", "status", "--provider", "openrouter", "--json"): credential_status_packet(),
        (
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "openrouter",
            "--source",
            "owner-env",
            "--json",
        ): credential_admit_packet(),
        ("external-models", "status", "--json"): command_packet(
            human_message="External-models synthetic lifecycle status collected without live runtime claims.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "foundation_phase": "C3",
                "adapter_runtime_available": False,
                "lifecycle_mode": "synthetic",
                "adapter_state": "stopped",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "routes_count": 1,
                "observed_routes_count": 0,
                "adapter": {
                    "state": "stopped",
                    "lifecycle_mode": "synthetic",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "base_url": None,
                    "host": "127.0.0.1",
                    "port": None,
                    "started_at_utc": None,
                    "last_transition": "init",
                },
                "local_auth": {
                    "token_ref": "managed_local_token",
                    "token_present": False,
                    "token_created_at_utc": None,
                },
            },
        ),
        ("external-models", "models", "--json"): command_packet(
            human_message="External-models route models listed from local registry.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "count": 1,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [
                    {
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "openrouter",
                        "base_url": "http://127.0.0.1:54321/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek/deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "cost_class": "paid_or_free_limited",
                        "enabled": True,
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "synthetic_adapter_state": "stopped",
                        "profile_ready": False,
                    }
                ],
            },
        ),
        ("external-models", "routes", "list", "--json"): command_packet(
            human_message="External-models routes listed from local registry.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "count": 1,
                "routes": [
                    {
                        "schema_version": 1,
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "openrouter",
                        "base_url": "http://127.0.0.1:54321/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek/deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
                        "cost_class": "paid_or_free_limited",
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "enabled": True,
                    }
                ],
            },
        ),
        ("external-models", "routes", "validate", "--route", "wbp-deepseek-v3", "--json"): command_packet(
            human_message="External-models route validation captured provider evidence without claiming runtime readiness.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "validation_kind": "provider_route_validate",
                "network_dependent": True,
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "verification_scope": "route_provider_only",
                "route_state": "model_visible",
                "requested_model": "wbp-deepseek-v3",
                "effective_model": "deepseek/deepseek-chat",
                "provider": "openrouter",
            },
        ),
        ("external-models", "routes", "disable", "--route", "wbp-deepseek-v3", "--json"): command_packet(
            human_message="External-models route disabled: wbp-deepseek-v3.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={"route_id": "wbp-deepseek-v3", "enabled": False},
        ),
        ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"): command_packet(
            human_message="External-models route smoke check captured provider evidence without claiming runtime readiness.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "check_kind": "provider_route_smoke",
                "network_dependent": True,
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "verification_scope": "route_provider_only",
                "route_state": "verified",
                "requested_model": "wbp-deepseek-v3",
                "effective_model": "deepseek/deepseek-chat",
                "provider": "openrouter",
            },
        ),
        (
            "external-models",
            "live-format-check",
            "--route",
            "wbp-deepseek-v3",
            "--prompt",
            "Верни короткий ответ: API_ONLY_DEEPSEEK_READY",
            "--expected-text",
            "API_ONLY_DEEPSEEK_READY",
            "--json",
        ): command_packet(
            human_message=(
                "External-models route live format check captured one provider response "
                "without writing state or evidence."
            ),
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            data={
                "check_kind": "api_only_live_route_format",
                "network_dependent": True,
                "verification_scope": "route_provider_only_no_write",
                "route_state": "live_response_observed_no_write",
                "requested_model": "wbp-deepseek-v3",
                "effective_model": "deepseek/deepseek-chat",
                "provider": "openrouter",
                "fallback_used": False,
                "fallback_chain": ["wbp-deepseek-v3"],
                "cost_class": "paid_or_free_limited",
                "latency_ms": 19,
                "request_count": 1,
                "retry_count": 0,
                "parallel_fanout_attempted": False,
                "expected_text": "API_ONLY_DEEPSEEK_READY",
                "expected_text_observed": True,
                "response_preview_bounded": "API_ONLY_DEEPSEEK_READY",
                "response_text_length": 23,
                "changed_files": [],
                "state_written": False,
                "evidence_written": False,
                "file_mutation_attempted": False,
                "commands_started_by_provider": False,
                "codex_history_sent": False,
                "repo_context_sent": False,
                "request_shape": "messages",
                "response_profile": "openai_chat_choices",
                "response_shape": "choices_message",
            },
        ),
        ("external-models", "profile", "codex-desktop", "--route", "wbp-deepseek-v3", "--json"): command_packet(
            human_message="Codex Desktop profile contract generated without mutating config.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "profile_kind": "codex_desktop_openai_compatible",
                "route_id": "wbp-deepseek-v3",
                "base_url": None,
                "model": "wbp-deepseek-v3",
                "api_key_source": "managed_local_token",
                "writes_external_config": False,
                "profile_ready": False,
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "synthetic_endpoint_contract": True,
                "prerequisite": "live_listener_contour_required",
            },
        ),
        ("external-models", "evidence", "capture", "--route", "wbp-deepseek-v3", "--json"): command_packet(
            human_message="Local external-models evidence captured from foundation contract.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            changed_files=["/tmp/wbp-evidence/wbp-deepseek-v3.json"],
            data={
                "route_id": "wbp-deepseek-v3",
                "network_dependent_evidence": False,
                "evidence_path": "/tmp/wbp-evidence/wbp-deepseek-v3.json",
            },
        ),
    }


def onboarding_packet(
    final_outcome: str,
    *,
    status: str = "ok",
    machine_error_code: str = "OK",
    selected_backend_id: str = "acct-new",
    pool_after_onboarding: str = "reserve",
    reserve_first_enforced: bool = True,
    active_routing_changed: bool = False,
) -> dict[str, object]:
    return command_packet(
        status=status,
        machine_error_code=machine_error_code,
        human_message="Onboarding owner packet emitted.",
        onboarding_result={
            "status": "ok",
            "attempted": True,
            "input_mode": "default",
            "explicit_auth_ref": "",
            "new_backend_ids": [selected_backend_id] if selected_backend_id else [],
            "selected_backend_id": selected_backend_id,
            "selection_status": "selected_unique_backend" if selected_backend_id else "not_selected",
            "reserve_first_enforced": reserve_first_enforced,
            "auth_snapshot_before_login_status": "ok",
            "auth_snapshot_before_login_count": 2,
            "auth_snapshot_before_login_digest": "redacted-digest",
            "auth_snapshot_before_login_source": "owner_packet",
            "pool_after_onboarding": pool_after_onboarding,
            "validate_attempted": True,
            "validate_outcome": "ok",
            "sync_attempted": True,
            "sync_outcome": "ok",
            "status_observed": {"command_status": "ok"},
            "external_command_exit_code": 7,
            "external_command_status": "nonzero",
            "active_routing_changed": active_routing_changed,
            "final_outcome": final_outcome,
        },
    )


def login_start_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Sandbox login session started.",
        next_action="login_complete",
        login_session_id=TEST_SANDBOX_LOGIN_SESSION_ID,
        state=TEST_SANDBOX_LOGIN_STATE,
        nonce="sandbox-nonce-test",
        expires_at="2026-05-21T12:00:00+00:00",
        login_url=(
            "http://127.0.0.1:8788/owner-login/sandbox?"
            f"session={TEST_SANDBOX_LOGIN_SESSION_ID}&state={TEST_SANDBOX_LOGIN_STATE}"
        ),
        login_result={
            "status": "started",
            "provider": "sandbox",
            "login_session_id": TEST_SANDBOX_LOGIN_SESSION_ID,
            "state": TEST_SANDBOX_LOGIN_STATE,
            "nonce": "sandbox-nonce-test",
            "expires_at": "2026-05-21T12:00:00+00:00",
            "login_url": (
                "http://127.0.0.1:8788/owner-login/sandbox?"
                f"session={TEST_SANDBOX_LOGIN_SESSION_ID}&state={TEST_SANDBOX_LOGIN_STATE}"
            ),
            "auth_materialized": False,
            "used": False,
        },
    )
    payload.update(overrides)
    return payload


def login_complete_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Sandbox login completed.",
        next_action="accounts_onboard",
        provider="sandbox",
        login_session_id=TEST_SANDBOX_LOGIN_SESSION_ID,
        auth_ref=TEST_SANDBOX_AUTH_REF,
        auth_ref_scope="sandbox",
        login_result={
            "status": "completed",
            "provider": "sandbox",
            "login_session_id": TEST_SANDBOX_LOGIN_SESSION_ID,
            "auth_materialized": True,
            "auth_ref": TEST_SANDBOX_AUTH_REF,
            "auth_ref_scope": "sandbox",
            "used": True,
        },
    )
    payload.update(overrides)
    return payload


def codex_login_start_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Codex device login session started.",
        next_action="wait_for_login",
        provider="codex",
        mode="device",
        session_id=TEST_CODEX_LOGIN_SESSION_ID,
        login_session_id=TEST_CODEX_LOGIN_SESSION_ID,
        device_url=TEST_CODEX_DEVICE_URL,
        device_code=TEST_CODEX_DEVICE_CODE,
        login_result={
            "status": "waiting_for_user",
            "provider": "codex",
            "mode": "device",
            "session_id": TEST_CODEX_LOGIN_SESSION_ID,
            "login_session_id": TEST_CODEX_LOGIN_SESSION_ID,
            "device_url": TEST_CODEX_DEVICE_URL,
            "device_code": TEST_CODEX_DEVICE_CODE,
            "device_code_present": True,
            "auth_materialized": False,
            "auth_ref_present": False,
            "used": False,
        },
    )
    payload.update(overrides)
    return payload


def codex_login_status_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Codex login session materialized sandbox auth.",
        next_action="accounts_onboard",
        provider="codex",
        session_id=TEST_CODEX_LOGIN_SESSION_ID,
        login_session_id=TEST_CODEX_LOGIN_SESSION_ID,
        login_result={
            "status": "auth_materialized",
            "provider": "codex",
            "mode": "device",
            "session_id": TEST_CODEX_LOGIN_SESSION_ID,
            "login_session_id": TEST_CODEX_LOGIN_SESSION_ID,
            "device_url": TEST_CODEX_DEVICE_URL,
            "device_code_present": True,
            "auth_materialized": True,
            "auth_ref_present": True,
            "auth_ref_scope": "sandbox",
            "used": False,
        },
    )
    payload.update(overrides)
    return payload


def codex_login_complete_packet(**overrides: object) -> dict[str, object]:
    payload = command_packet(
        human_message="Codex login session completed reserve-first onboarding.",
        next_action="accounts_refresh",
        provider="codex",
        session_id=TEST_CODEX_LOGIN_SESSION_ID,
        login_session_id=TEST_CODEX_LOGIN_SESSION_ID,
        onboarding_result=onboarding_packet("explicit_auth_imported_to_reserve")["onboarding_result"],  # type: ignore[index]
        login_result={
            "status": "completed",
            "provider": "codex",
            "mode": "device",
            "session_id": TEST_CODEX_LOGIN_SESSION_ID,
            "login_session_id": TEST_CODEX_LOGIN_SESSION_ID,
            "device_url": TEST_CODEX_DEVICE_URL,
            "device_code_present": True,
            "auth_materialized": True,
            "auth_ref_present": True,
            "auth_ref_scope": "sandbox",
            "used": True,
        },
    )
    payload.update(overrides)
    return payload


class FakeOperatorSurfaceSession:
    def __init__(self) -> None:
        self.run_payloads: list[dict[str, object]] = []
        self.status_payload_calls = 0
        self.transcript = {
            "captured_at_utc": "2026-05-23T00:00:00Z",
            "entries": [],
            "secret_value_recorded": False,
        }

    def status_payload(self) -> dict[str, object]:
        self.status_payload_calls += 1
        return {
            "captured_at_utc": "2026-05-23T00:00:00Z",
            "status": {"status": "ok", "machine_error_code": "OK"},
            "health": {"status": "ok", "machine_error_code": "OK"},
            "claim_gate": {"status": "blocked_by_policy_drift"},
            "models": {
                "ok": True,
                "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
                "server_issued": True,
            },
            "control_surface": {
                "localhost_only": True,
                "browser_secret_fields": False,
                "raw_path_fields": False,
            },
        }

    def probe_models(self) -> dict[str, object]:
        return {
            "ok": True,
            "captured_at_utc": "2026-05-23T00:00:00Z",
            "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
            "server_issued": True,
        }

    def transcript_payload(self) -> dict[str, object]:
        return self.transcript

    def run_prompt(
        self,
        payload: dict[str, object],
        *,
        trace_wbp: bool = False,
        sandbox_mode_override: str = "read-only",
        writable_additional_dir: Path | None = None,
        working_dir_override: Path | None = None,
    ) -> dict[str, object]:
        self.run_payloads.append(payload)
        trace_packet = {
            "request_observed": trace_wbp,
            "response_observed": trace_wbp,
            "forwarded_to_wbp": trace_wbp,
            "forwarded_endpoint": "http://127.0.0.1:8318/v1" if trace_wbp else "",
            "path": "/v1/responses" if trace_wbp else "",
            "upstream_status": 200 if trace_wbp else None,
            "prompt_body_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
        }
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Codex Operator prompt completed.",
            "selected_model": payload.get("model_id"),
            "requested_slot_id": payload.get("slot_id", ""),
            "requested_slot_explicit": payload.get("slot_id_explicit")
            if isinstance(payload.get("slot_id_explicit"), bool)
            else "slot_id" in payload,
            "configured_provider": "cliproxy",
            "configured_wire_api": "responses",
            "sandbox_mode": sandbox_mode_override,
            "workspace_write_admitted": sandbox_mode_override == "workspace-write",
            "additional_writable_dir_admitted": writable_additional_dir is not None,
            "working_dir_override_admitted": working_dir_override is not None,
            "working_dir_scope": "safe_worktree_only" if working_dir_override is not None else "temp_operator_work",
            "wbp_endpoint_configured": True,
            "config_endpoint_matches": True,
            "config_provider_matches": True,
            "config_wire_api_matches": True,
            "command_uses_stdin_dash": True,
            "command_json_mode": True,
            "env_codex_home_is_temp": True,
            "env_home_is_temp": True,
            "workdir_is_temp": True,
            "command_workdir_is_temp": True,
            "command_output_file_is_temp": True,
            "current_codex_home_used": False,
            "trace_observer_enabled": trace_wbp,
            "trace_observer_packet": trace_packet,
            "independent_wbp_trace_observed": trace_wbp,
            "final_message": "MAIN_WEB_OK",
            "stdin_prompt_used": True,
            "temp_root_removed": True,
            "refresh_packet": self.status_payload(),
            "transcript": {
                "entries": [
                    {
                        "prompt_id": "operator_prompt_1",
                        "prompt_hash": "hash",
                        "selected_model": payload.get("model_id"),
                        "final_message": "MAIN_WEB_OK",
                        "exit_code": 0,
                        "captured_at_utc": "2026-05-23T00:00:00Z",
                    }
                ],
                "secret_value_recorded": False,
            },
            "secret_value_recorded": False,
        }


class ReadyFakeOperatorSurfaceSession(FakeOperatorSurfaceSession):
    def status_payload(self) -> dict[str, object]:
        payload = dict(super().status_payload())
        payload["claim_gate"] = {"status": "ok"}
        return payload


class ExternalRouteFakeOperatorSurfaceSession(ReadyFakeOperatorSurfaceSession):
    def status_payload(self) -> dict[str, object]:
        payload = dict(super().status_payload())
        payload["models"] = {
            "ok": True,
            "model_ids": ["gpt-5.3-codex", "wbp-deepseek-v3"],
            "server_issued": True,
        }
        return payload

    def probe_models(self) -> dict[str, object]:
        return {
            "ok": True,
            "captured_at_utc": "2026-05-23T00:00:00Z",
            "model_ids": ["gpt-5.3-codex", "wbp-deepseek-v3"],
            "server_issued": True,
        }

    def run_prompt(
        self,
        payload: dict[str, object],
        *,
        trace_wbp: bool = False,
        sandbox_mode_override: str = "read-only",
        writable_additional_dir: Path | None = None,
        working_dir_override: Path | None = None,
    ) -> dict[str, object]:
        result = super().run_prompt(
            payload,
            trace_wbp=trace_wbp,
            sandbox_mode_override=sandbox_mode_override,
            writable_additional_dir=writable_additional_dir,
            working_dir_override=working_dir_override,
        )
        result["configured_provider"] = "external_route"
        return result


class DualLaneFakeOperatorSurfaceSession(ExternalRouteFakeOperatorSurfaceSession):
    def run_prompt(
        self,
        payload: dict[str, object],
        *,
        trace_wbp: bool = False,
        sandbox_mode_override: str = "read-only",
        writable_additional_dir: Path | None = None,
        working_dir_override: Path | None = None,
    ) -> dict[str, object]:
        self.run_payloads.append(payload)
        trace_packet = {
            "request_observed": trace_wbp,
            "response_observed": trace_wbp,
            "forwarded_to_wbp": trace_wbp,
            "forwarded_endpoint": "http://127.0.0.1:8318/v1" if trace_wbp else "",
            "path": "/v1/responses" if trace_wbp else "",
            "upstream_status": 200 if trace_wbp else None,
            "prompt_body_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
        }
        route_backed = payload.get("model_id") == "wbp-deepseek-v3"
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Codex Operator prompt completed.",
            "selected_model": payload.get("model_id"),
            "requested_slot_id": payload.get("slot_id", ""),
            "requested_slot_explicit": payload.get("slot_id_explicit")
            if isinstance(payload.get("slot_id_explicit"), bool)
            else "slot_id" in payload,
            "configured_provider": "external_route" if route_backed else "cliproxy",
            "configured_wire_api": "responses",
            "sandbox_mode": sandbox_mode_override,
            "workspace_write_admitted": sandbox_mode_override == "workspace-write",
            "additional_writable_dir_admitted": writable_additional_dir is not None,
            "working_dir_override_admitted": working_dir_override is not None,
            "working_dir_scope": "safe_worktree_only" if working_dir_override is not None else "temp_operator_work",
            "wbp_endpoint_configured": True,
            "config_endpoint_matches": True,
            "config_provider_matches": True,
            "config_wire_api_matches": True,
            "command_uses_stdin_dash": True,
            "command_json_mode": True,
            "env_codex_home_is_temp": True,
            "env_home_is_temp": True,
            "workdir_is_temp": True,
            "command_workdir_is_temp": True,
            "command_output_file_is_temp": True,
            "current_codex_home_used": False,
            "trace_observer_enabled": trace_wbp,
            "trace_observer_packet": trace_packet,
            "independent_wbp_trace_observed": trace_wbp,
            "final_message": "API_LANE_OK" if route_backed else "CHATGPT_LANE_OK",
            "stdin_prompt_used": True,
            "temp_root_removed": True,
            "refresh_packet": self.status_payload(),
            "transcript": {
                "entries": [
                    {
                        "prompt_id": "operator_prompt_1",
                        "prompt_hash": "hash",
                        "selected_model": payload.get("model_id"),
                        "final_message": "API_LANE_OK" if route_backed else "CHATGPT_LANE_OK",
                        "exit_code": 0,
                        "captured_at_utc": "2026-05-23T00:00:00Z",
                    }
                ],
                "secret_value_recorded": False,
            },
            "secret_value_recorded": False,
        }


class WebDesignRouteEffectRegistryTests(unittest.TestCase):
    @staticmethod
    def _handler_block(start_marker: str, end_marker: str) -> str:
        source = Path(live_server.__file__).read_text(encoding="utf-8")
        start = source.index(start_marker)
        end = source.index(end_marker, start)
        return source[start:end]

    @staticmethod
    def _representative_get_path(route) -> str:
        if route.prefix and route.path == "/api/codex/custom/sessions/":
            return "/api/codex/custom/sessions/probe-session/transcript"
        return route.path

    def test_registry_routes_have_get_and_post_dispatch_bindings(self) -> None:
        handler = build_handler(runner=mock.Mock())

        for method, dispatch_table in (
            ("GET", handler.GET_ROUTE_DISPATCH_TABLE),
            ("POST", handler.POST_ROUTE_DISPATCH_TABLE),
        ):
            registered_handler_ids = {
                route.handler_id
                for route in live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.routes
                if route.method == method
            }
            with self.subTest(method=method):
                self.assertEqual(set(dispatch_table), registered_handler_ids)
                self.assertEqual(len(set(dispatch_table.values())), len(registered_handler_ids))
                for handler_id, dispatcher_name in dispatch_table.items():
                    self.assertEqual(dispatcher_name, f"_handle_{handler_id}")
                    self.assertTrue(callable(getattr(handler, dispatcher_name, None)))

    def test_registered_get_routes_dispatch_to_their_bound_handlers(self) -> None:
        handler = build_handler(runner=mock.Mock())
        get_routes = [
            route
            for route in live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.routes
            if route.method == "GET"
        ]

        def make_probe(handler_id: str):
            def probe(self, request_path: str) -> None:
                self._send_json(
                    {
                        "status": "ok",
                        "handler_id": handler_id,
                        "request_path": request_path,
                    }
                )

            return probe

        for route in get_routes:
            handler_id = str(route.handler_id)
            dispatcher_name = handler.GET_ROUTE_DISPATCH_TABLE[handler_id]
            setattr(handler, dispatcher_name, make_probe(handler_id))

        server = ThreadingHTTPServer(("127.0.0.1", free_port()), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for route in get_routes:
                path = self._representative_get_path(route)
                with self.subTest(path=route.path, handler_id=route.handler_id):
                    packet = json.loads(fetch(f"{base}{path}"))
                    self.assertEqual(packet["status"], "ok")
                    self.assertEqual(packet["handler_id"], route.handler_id)
                    self.assertEqual(packet["request_path"], path)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_registry_specs_have_canonical_effects_and_post_auth_policy(self) -> None:
        for route in live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.routes:
            self.assertIn(route.effect, CANONICAL_ROUTE_EFFECTS)
            self.assertTrue(route.body_kind)
            self.assertTrue(route.browser_field_policy)
            if route.method in {"GET", "POST"}:
                self.assertTrue(route.handler_id, route.path)
            if route.method == "POST":
                self.assertTrue(route.auth_required, route.path)

    def test_registry_dynamic_prefixes_and_queryless_lookup(self) -> None:
        action = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup(
            "POST",
            "/api/action?attempt=1",
        )
        session_get = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup(
            "GET",
            "/api/codex/custom/sessions/session-1/transcript",
        )
        session_post = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup(
            "POST",
            "/api/codex/custom/sessions/session-1/prompt",
        )
        worktree_cleanup = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup(
            "POST",
            "/api/codex/custom/worktrees/session-1/cleanup",
        )

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.path, "/api/action")
        self.assertIsNotNone(session_get)
        assert session_get is not None
        self.assertTrue(session_get.prefix)
        self.assertEqual(session_get.effect, EFFECT_READ)
        self.assertIsNotNone(session_post)
        assert session_post is not None
        self.assertTrue(session_post.prefix)
        self.assertEqual(session_post.effect, EFFECT_MUTATE)
        self.assertIsNotNone(worktree_cleanup)
        assert worktree_cleanup is not None
        self.assertTrue(worktree_cleanup.prefix)
        self.assertEqual(worktree_cleanup.effect, EFFECT_REPAIR)

    def test_api_action_is_multiplexed_by_ui_action_effect_registry(self) -> None:
        action_route = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("POST", "/api/action")
        self.assertIsNotNone(action_route)
        assert action_route is not None
        self.assertEqual(action_route.effect_source, EFFECT_SOURCE_UI_ACTION_REGISTRY)
        self.assertEqual(action_route.multiplexed_by, "ui_action")
        self.assertEqual(action_route.effect, EFFECT_MUTATE)
        self.assertEqual(
            set(live_server.UI_ACTION_ALLOWLIST),
            set(live_server.UI_ACTION_EFFECT_REGISTRY),
        )
        for effect in live_server.UI_ACTION_EFFECT_REGISTRY.values():
            self.assertIn(effect, CANONICAL_ROUTE_EFFECTS)

    def test_unregistered_post_route_rejects_before_body_dispatch(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            status, packet = post_body_response(
                f"{base}/api/not-registered",
                b"{not-json",
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["source"], "web_ingress")
        self.assertEqual(packet["machine_error_code"], "WEB_ROUTE_NOT_REGISTERED")
        self.assertEqual(packet["changed_files"], [])

    def test_registered_get_routes_are_behaviorally_required_before_dispatch(self) -> None:
        cases = (
            ("/api/live-readonly", lambda route: route.method == "GET" and route.path == "/api/live-readonly"),
            (
                "/api/codex/custom/sessions/session-1/transcript",
                lambda route: route.method == "GET"
                and route.prefix
                and route.path == "/api/codex/custom/sessions/",
            ),
        )
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for path, remove_route in cases:
                reduced_table = WebRouteTable(
                    route
                    for route in live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.routes
                    if not remove_route(route)
                )
                with self.subTest(path=path), mock.patch.object(
                    live_server,
                    "WEB_DESIGN_LIVE_ROUTE_TABLE",
                    reduced_table,
                ):
                    try:
                        fetch(f"{base}{path}")
                    except urllib.error.HTTPError as exc:
                        status = HTTPStatus(exc.code)
                        packet = json.loads(exc.read().decode("utf-8"))
                    else:
                        self.fail("removed GET registry route should reject")
                    self.assertEqual(status, HTTPStatus.NOT_FOUND)
                    self.assertEqual(packet["status"], "rejected")
                    self.assertEqual(packet["source"], "web_ingress")
                    self.assertEqual(packet["machine_error_code"], "WEB_ROUTE_NOT_REGISTERED")
                    self.assertEqual(packet["changed_files"], [])
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_missing_get_dispatch_binding_rejects_before_handler_dispatch(self) -> None:
        handler = build_handler(runner=mock.Mock())
        route = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("GET", "/api/live-readonly")
        self.assertIsNotNone(route)
        assert route is not None
        binding = route.handler_id
        self.assertTrue(binding)
        handler.GET_ROUTE_DISPATCH_TABLE = {
            key: value for key, value in handler.GET_ROUTE_DISPATCH_TABLE.items() if key != binding
        }
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            try:
                fetch(f"{base}/api/live-readonly")
            except urllib.error.HTTPError as exc:
                status = HTTPStatus(exc.code)
                packet = json.loads(exc.read().decode("utf-8"))
            else:
                self.fail("missing GET dispatch binding should reject")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["source"], "web_ingress")
        self.assertEqual(packet["machine_error_code"], "WEB_GET_ROUTE_DISPATCH_MISSING")
        self.assertEqual(packet["changed_files"], [])

    def test_unknown_api_get_route_does_not_fall_through_to_static_success(self) -> None:
        with tempfile.TemporaryDirectory() as static_dir:
            static_root = Path(static_dir)
            (static_root / "index.html").write_text("index-ok", encoding="utf-8")
            (static_root / "asset.txt").write_text("asset-ok", encoding="utf-8")
            (static_root / "api").mkdir()
            (static_root / "api" / "not-registered").write_text(
                "static-api-asset-should-not-serve",
                encoding="utf-8",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(static_dir=static_root),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                static_asset = fetch(f"{base}/asset.txt")
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    fetch(f"{base}/api/not-registered")
                api_packet = json.loads(raised.exception.read().decode("utf-8"))
                with self.assertRaises(urllib.error.HTTPError) as prefix_raised:
                    fetch(f"{base}/api/codex/custom/sessions/session-1/not-registered")
                prefix_packet = json.loads(prefix_raised.exception.read().decode("utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(static_asset, "asset-ok")
        self.assertEqual(raised.exception.code, HTTPStatus.NOT_FOUND)
        self.assertEqual(api_packet["status"], "rejected")
        self.assertEqual(api_packet["source"], "web_ingress")
        self.assertEqual(api_packet["machine_error_code"], "WEB_ROUTE_NOT_REGISTERED")
        self.assertEqual(api_packet["changed_files"], [])
        self.assertNotIn("static-api-asset-should-not-serve", json.dumps(api_packet))
        self.assertEqual(prefix_raised.exception.code, HTTPStatus.NOT_FOUND)
        self.assertEqual(prefix_packet["status"], "rejected")
        self.assertEqual(prefix_packet["source"], "web_ingress")
        self.assertEqual(prefix_packet["machine_error_code"], "WEB_ROUTE_NOT_REGISTERED")
        self.assertEqual(prefix_packet["changed_files"], [])

    def test_get_dispatch_table_preserves_representative_outputs(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            live_readonly = json.loads(fetch(f"{base}/api/live-readonly"))
            operator_status = json.loads(fetch(f"{base}/api/operator/status"))
            custom_status = json.loads(fetch(f"{base}/api/codex/custom/status"))
            sessions = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
            transcript = json.loads(
                fetch(f"{base}/api/codex/custom/sessions/session-missing/transcript")
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(live_readonly["status"], "ok")
        self.assertIn(
            operator_status["status"]["machine_error_code"],
            {"OK", "CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_API_CATALOG_ONLY"},
        )
        self.assertTrue(operator_status["models"]["server_issued"])
        self.assertIn(custom_status["status"], {"ok", "degraded"})
        self.assertEqual(sessions["status"], "ok")
        self.assertEqual(transcript["status"], "rejected")
        self.assertEqual(transcript["machine_error_code"], "SESSION_NOT_FOUND")

    def test_registered_post_routes_are_behaviorally_required_before_dispatch(self) -> None:
        cases = (
            ("/api/operator/run", lambda route: route.method == "POST" and route.path == "/api/operator/run"),
            ("/api/action", lambda route: route.method == "POST" and route.path == "/api/action"),
            (
                "/api/codex/custom/sessions/session-1/prompt",
                lambda route: route.method == "POST"
                and route.prefix
                and route.path == "/api/codex/custom/sessions/",
            ),
            (
                "/api/codex/custom/worktrees/session-1/cleanup",
                lambda route: route.method == "POST"
                and route.prefix
                and route.path == "/api/codex/custom/worktrees/",
            ),
        )
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for path, remove_route in cases:
                reduced_table = WebRouteTable(
                    route
                    for route in live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.routes
                    if not remove_route(route)
                )
                with self.subTest(path=path), mock.patch.object(
                    live_server,
                    "WEB_DESIGN_LIVE_ROUTE_TABLE",
                    reduced_table,
                ):
                    status, packet = post_body_response(
                        f"{base}{path}",
                        b"{not-json",
                    )

                self.assertEqual(status, HTTPStatus.NOT_FOUND)
                self.assertEqual(packet["machine_error_code"], "WEB_ROUTE_NOT_REGISTERED")
                self.assertEqual(packet["changed_files"], [])
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_missing_post_dispatch_binding_rejects_before_body_dispatch(self) -> None:
        handler = build_handler(runner=mock.Mock())
        route = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("POST", "/api/operator/run")
        self.assertIsNotNone(route)
        assert route is not None
        binding = route.handler_id
        self.assertTrue(binding)
        reduced_dispatch = {
            key: value for key, value in handler.POST_ROUTE_DISPATCH_TABLE.items() if key != binding
        }
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with mock.patch.object(handler, "POST_ROUTE_DISPATCH_TABLE", reduced_dispatch):
                status, packet = post_body_response(
                    f"{base}/api/operator/run",
                    b"{not-json",
                )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["source"], "web_ingress")
        self.assertEqual(packet["machine_error_code"], "WEB_POST_ROUTE_DISPATCH_MISSING")
        self.assertEqual(packet["changed_files"], [])

    def test_post_dispatch_table_preserves_representative_exact_prefix_and_action_packets(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            exact = json.loads(post_json(f"{base}/api/review-command", {}))
            prefix = json.loads(
                post_json(f"{base}/api/codex/custom/worktrees/session-1/cleanup", {})
            )
            action = json.loads(post_json(f"{base}/api/action", {}))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(exact["machine_error_code"], "REVIEW_COMMAND_ID_REQUIRED")
        self.assertEqual(exact["status"], "command_error")
        self.assertEqual(prefix["machine_error_code"], "WORKTREE_NOT_FOUND")
        self.assertEqual(prefix["status"], "rejected")
        self.assertEqual(action["status"], "integration_failure")
        self.assertEqual(action["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")

    def test_registered_prefix_routes_reject_unknown_subactions(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for path in (
                "/api/codex/custom/sessions/session-1/unknown-action",
                "/api/codex/custom/worktrees/session-1/not-cleanup",
            ):
                with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as raised:
                    post_json(f"{base}{path}", {})
                self.assertEqual(raised.exception.code, HTTPStatus.NOT_FOUND)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


class WebDesignOperatorSurfaceEndpointTests(unittest.TestCase):
    def test_operator_endpoints_expose_status_models_transcript_and_run(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                models = json.loads(fetch(f"{base}/api/operator/models"))
                self.assertTrue(models["server_issued"])
                self.assertEqual(models["model_ids"], ["gpt-5.3-codex", "gpt-5.4"])

                status = json.loads(fetch(f"{base}/api/operator/status"))
                self.assertEqual(status["status"]["status"], "ok")
                self.assertFalse(status["control_surface"]["browser_secret_fields"])

                transcript = json.loads(fetch(f"{base}/api/operator/transcript"))
                self.assertFalse(transcript["secret_value_recorded"])

                result = json.loads(
                    post_json(
                        f"{base}/api/operator/run",
                        {"prompt": "Reply MAIN_WEB_OK.", "model_id": "gpt-5.3-codex"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["final_message"], "MAIN_WEB_OK")
        self.assertTrue(result["stdin_prompt_used"])
        self.assertTrue(result["refresh_packet"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [{"prompt": "Reply MAIN_WEB_OK.", "model_id": "gpt-5.3-codex"}],
        )

    def test_web_ingress_rejects_malformed_operator_post_before_runner(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                invalid_status, invalid_packet = post_body_response(
                    f"{base}/api/operator/run",
                    b"{not-json",
                )
                non_object_status, non_object_packet = post_body_response(
                    f"{base}/api/operator/run",
                    b'["run"]',
                )
                wrong_type_status, wrong_type_packet = post_body_response(
                    f"{base}/api/operator/run",
                    b'{"prompt":"wrong type"}',
                    headers={"Content-Type": "text/plain"},
                )
                secret_marker = "secret-token-should-not-leak"
                too_large_status, too_large_packet = post_body_response(
                    f"{base}/api/operator/run",
                    (
                        b'{"prompt":"'
                        + secret_marker.encode("utf-8")
                        + b"a" * live_server.MAX_WEB_REQUEST_BODY_BYTES
                        + b'"}'
                    ),
                )
                origin_status, origin_packet = post_body_response(
                    f"{base}/api/operator/run",
                    b'{"prompt":"evil origin"}',
                    headers={
                        "Content-Type": "application/json",
                        "Origin": "http://evil.example",
                    },
                )
                same_origin_status, same_origin_packet = post_body_response(
                    f"{base}/api/operator/run",
                    b'{"prompt":"Reply MAIN_WEB_OK.","model_id":"gpt-5.3-codex"}',
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                )
                bad_host_status, bad_host_packet = raw_http_json_response(
                    port=server.server_port,
                    method="GET",
                    path="/api/live-readonly",
                    host="evil.example",
                )
                bad_length_status, bad_length_packet = raw_http_json_response(
                    port=server.server_port,
                    method="POST",
                    path="/api/operator/run",
                    host=f"127.0.0.1:{server.server_port}",
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": "abc",
                    },
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(invalid_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(invalid_packet["machine_error_code"], "WEB_INGRESS_JSON_INVALID")
        self.assertEqual(non_object_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            non_object_packet["machine_error_code"],
            "WEB_INGRESS_JSON_OBJECT_REQUIRED",
        )
        self.assertEqual(wrong_type_status, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(
            wrong_type_packet["machine_error_code"],
            "WEB_INGRESS_CONTENT_TYPE_REJECTED",
        )
        self.assertEqual(too_large_status, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(too_large_packet["machine_error_code"], "WEB_INGRESS_BODY_TOO_LARGE")
        self.assertNotIn(secret_marker, json.dumps(too_large_packet))
        self.assertEqual(origin_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(origin_packet["machine_error_code"], "WEB_INGRESS_ORIGIN_REJECTED")
        self.assertEqual(bad_host_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(bad_host_packet["machine_error_code"], "WEB_INGRESS_HOST_REJECTED")
        self.assertEqual(bad_length_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            bad_length_packet["machine_error_code"],
            "WEB_INGRESS_CONTENT_LENGTH_INVALID",
        )
        for packet in (
            invalid_packet,
            non_object_packet,
            wrong_type_packet,
            too_large_packet,
            origin_packet,
            bad_host_packet,
            bad_length_packet,
        ):
            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["source"], "web_ingress")
            self.assertEqual(packet["changed_files"], [])
        self.assertEqual(same_origin_status, HTTPStatus.OK)
        self.assertEqual(same_origin_packet["status"], "ok")
        self.assertEqual(
            created_sessions[0].run_payloads,
            [{"prompt": "Reply MAIN_WEB_OK.", "model_id": "gpt-5.3-codex"}],
        )

    def test_web_ingress_rejects_missing_or_invalid_web_post_tokens_before_runner(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            body = b'{"prompt":"Reply MAIN_WEB_OK.","model_id":"gpt-5.3-codex"}'
            try:
                token, csrf = _web_bootstrap_tokens(base)
                no_token_status, no_token_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                    web_auth=False,
                )
                bad_token_status, bad_token_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                    token_override="wrong-web-token",
                )
                bad_csrf_status, bad_csrf_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                    csrf_override="wrong-csrf-token",
                )
                valid_status, valid_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(no_token_status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(
            no_token_packet["machine_error_code"],
            "WEB_INGRESS_WEB_TOKEN_REJECTED",
        )
        self.assertEqual(bad_token_status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(
            bad_token_packet["machine_error_code"],
            "WEB_INGRESS_WEB_TOKEN_REJECTED",
        )
        self.assertEqual(bad_csrf_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(bad_csrf_packet["machine_error_code"], "WEB_INGRESS_CSRF_REJECTED")
        self.assertEqual(valid_status, HTTPStatus.OK)
        self.assertEqual(valid_packet["status"], "ok")
        for packet in (no_token_packet, bad_token_packet, bad_csrf_packet):
            packet_text = json.dumps(packet)
            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["source"], "web_ingress")
            self.assertNotIn(token, packet_text)
            self.assertNotIn(csrf, packet_text)
        self.assertEqual(
            created_sessions[0].run_payloads,
            [{"prompt": "Reply MAIN_WEB_OK.", "model_id": "gpt-5.3-codex"}],
        )

    def test_web_ingress_rate_limits_valid_operator_posts_without_secret_leak(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        limiter = WebPostRateLimiter(clock=lambda: 0.0)
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=mock.Mock(), post_rate_limiter=limiter),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            body = b'{"prompt":"Reply MAIN_WEB_OK.","model_id":"gpt-5.3-codex"}'
            try:
                token, csrf = _web_bootstrap_tokens(base)
                statuses = [
                    post_body_response(f"{base}/api/operator/run", body)[0]
                    for _ in range(10)
                ]
                limited_status, limited_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(statuses, [HTTPStatus.OK] * 10)
        self.assertEqual(limited_status, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertEqual(limited_packet["machine_error_code"], WEB_RATE_LIMIT_MACHINE_ERROR_CODE)
        self.assertEqual(limited_packet["changed_files"], [])
        packet_text = json.dumps(limited_packet)
        self.assertNotIn(token, packet_text)
        self.assertNotIn(csrf, packet_text)
        self.assertEqual(len(created_sessions[0].run_payloads), 10)

    def test_web_ingress_rate_limit_key_ignores_query_string(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        limiter = WebPostRateLimiter(clock=lambda: 0.0)
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=mock.Mock(), post_rate_limiter=limiter),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            body = b'{"prompt":"Reply MAIN_WEB_OK.","model_id":"gpt-5.3-codex"}'
            try:
                statuses = [
                    post_body_response(f"{base}/api/operator/run?attempt={index}", body)[0]
                    for index in range(10)
                ]
                limited_status, limited_packet = post_body_response(
                    f"{base}/api/operator/run?attempt=10",
                    body,
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(statuses, [HTTPStatus.OK] * 10)
        self.assertEqual(limited_status, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertEqual(limited_packet["machine_error_code"], WEB_RATE_LIMIT_MACHINE_ERROR_CODE)
        self.assertEqual(len(created_sessions[0].run_payloads), 10)

    def test_invalid_web_post_tokens_do_not_consume_rate_limit_quota(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        limiter = WebPostRateLimiter(clock=lambda: 0.0)
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=mock.Mock(), post_rate_limiter=limiter),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            body = b'{"prompt":"Reply MAIN_WEB_OK.","model_id":"gpt-5.3-codex"}'
            try:
                bad_token_status, _bad_token_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                    token_override="wrong-web-token",
                )
                bad_csrf_status, _bad_csrf_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                    csrf_override="wrong-csrf-token",
                )
                statuses = [
                    post_body_response(f"{base}/api/operator/run", body)[0]
                    for _ in range(10)
                ]
                limited_status, limited_packet = post_body_response(
                    f"{base}/api/operator/run",
                    body,
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(bad_token_status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(bad_csrf_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(statuses, [HTTPStatus.OK] * 10)
        self.assertEqual(limited_status, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertEqual(limited_packet["machine_error_code"], WEB_RATE_LIMIT_MACHINE_ERROR_CODE)
        self.assertEqual(len(created_sessions[0].run_payloads), 10)


class WebDesignCodexLaunchModeEndpointTests(unittest.TestCase):
    @staticmethod
    def stable_bridge_preflight_ok_packet() -> dict[str, object]:
        return {
            "schema_version": 1,
            "packet_kind": "stable_bridge_preflight",
            "status": "ok",
            "machine_error_code": "OK",
            "final_status": "STABLE_BRIDGE_PREFLIGHT_PROVEN_WITH_LIMITS",
            "launch_allowed": True,
            "failure_reason": "",
            "blocking_reasons": [],
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

    @staticmethod
    def stable_bridge_prewarm_ok_packet() -> dict[str, object]:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_stable_bridge_prewarm",
            "status": "ok",
            "machine_error_code": "OK",
            "prewarm_required": True,
            "bridge_endpoint": "http://127.0.0.1:9543/v1",
            "downstream_endpoint": "http://127.0.0.1:8318/v1",
            "selected_model": "wbp-deepseek-v4-pro-max",
            "forced_route_used": True,
            "smoke_status": "ok",
            "smoke_http_status": 200,
            "final_status": "STABLE_BRIDGE_PREWARM_PROVEN_WITH_LIMITS",
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

    def test_codex_launch_mode_endpoints_expose_live_launch_surfaces_without_overclaim(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", FakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                launch_modes = json.loads(fetch(f"{base}/api/codex/launch-modes"))
                original_status = json.loads(fetch(f"{base}/api/codex/original/status"))
                custom_status = json.loads(fetch(f"{base}/api/codex/custom/status"))
                dry_run = json.loads(post_json(f"{base}/api/codex/original/launch-dry-run", {}))
                original_launch = json.loads(post_json(f"{base}/api/codex/original/launch", {}))
                custom_dry_run = json.loads(post_json(f"{base}/api/codex/custom/launch-dry-run", {}))
                custom_launch = json.loads(post_json(f"{base}/api/codex/custom/launch", {"model_id": "gpt-5.3-codex"}))
                app_copy_dry_run = json.loads(
                    post_json(f"{base}/api/codex/app-copy/launch-dry-run", {})
                )
                app_copy_admission = json.loads(
                    post_json(f"{base}/api/codex/app-copy/live-admission", {})
                )
                app_copy_live = json.loads(
                    post_json(f"{base}/api/codex/app-copy/launch", {})
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/original/launch-dry-run",
                        {"model_id": "gpt-5.3-codex", "route_id": "route", "CODEX_HOME": "/tmp/home"},
                    )
                )
                custom_rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/launch-dry-run",
                        {"model": "gpt-5.3-codex", "route_id": "route", "codex_home": "/tmp/home"},
                    )
                )
                app_copy_rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/app-copy/launch-dry-run",
                        {"path": "/tmp/app", "port": 1234, "env": {"HOME": "/tmp/home"}},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        modes = {mode["id"]: mode for mode in launch_modes["modes"]}
        self.assertFalse(modes["original_codex"]["proxy_enabled"])
        self.assertFalse(modes["original_codex"]["proxy_allowed"])
        self.assertTrue(modes["original_codex"]["live_launch_available"])
        self.assertEqual(modes["original_codex"]["launch_claim_scope"], "owner_authorized_baseline_launch")
        self.assertTrue(modes["codex_custom"]["proxy_enabled"])
        self.assertTrue(modes["codex_custom"]["custom_codex_home_required"])
        self.assertFalse(modes["codex_custom"]["current_codex_home_allowed"])
        self.assertTrue(modes["codex_custom"]["custom_session_available"])
        self.assertFalse(original_status["proxy_injection_allowed"])
        self.assertFalse(original_status["proxy_allowed"])
        self.assertFalse(original_status["custom_home_allowed"])
        self.assertEqual(original_status["browser_payload_allowed_keys"], [])
        self.assertEqual(custom_status["launch_claim_scope"], "isolated_session_workbench_launch_ready")
        self.assertFalse(custom_status["current_codex_home_allowed"])
        self.assertFalse(custom_status["last_process_isolation_proof"]["fresh_truth"])
        self.assertEqual(dry_run["status"], "ok")
        self.assertTrue(dry_run["dry_run"])
        self.assertTrue(dry_run["dispatch_plan_safe"])
        self.assertFalse(dry_run["proxy_env_injected"])
        self.assertFalse(dry_run["custom_home_injected"])
        self.assertEqual(original_launch["status"], "blocked")
        self.assertEqual(original_launch["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertFalse(original_launch["running_status"])
        self.assertFalse(original_launch["owner_authorization_phrase_present"])
        self.assertEqual(custom_dry_run["status"], "ok")
        self.assertTrue(custom_dry_run["dry_run"])
        self.assertTrue(custom_dry_run["custom_launch_plan_safe"])
        self.assertFalse(custom_dry_run["current_codex_home_allowed"])
        self.assertFalse(custom_dry_run["real_launch_attempted"])
        self.assertFalse(custom_dry_run["prompt_attempted"])
        self.assertEqual(custom_dry_run["token_burn"], 0)
        self.assertEqual(custom_launch["status"], "blocked")
        self.assertEqual(custom_launch["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertFalse(custom_launch["running_status"])
        self.assertFalse(custom_launch["workbench_ready"])
        self.assertFalse(custom_launch["owner_authorization_phrase_present"])
        self.assertEqual(app_copy_dry_run["status"], "ok")
        self.assertEqual(
            app_copy_dry_run["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY",
        )
        self.assertTrue(app_copy_dry_run["server_issued_plan"])
        self.assertFalse(app_copy_dry_run["browser_forbidden_fields_rejected"])
        self.assertTrue(app_copy_dry_run["browser_forbidden_fields_absent"])
        self.assertFalse(app_copy_dry_run["launch_performed"])
        self.assertFalse(app_copy_dry_run["live_launch_admitted"])
        self.assertTrue(app_copy_dry_run["app_path_redacted"])
        self.assertFalse(app_copy_dry_run["current_codex_touched"])
        self.assertFalse(app_copy_dry_run["uses_current_home"])
        self.assertEqual(app_copy_live["status"], "blocked")
        self.assertEqual(
            app_copy_live["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_NOT_ADMITTED",
        )
        self.assertFalse(app_copy_live["launch_performed"])
        self.assertEqual(app_copy_admission["status"], "blocked")
        self.assertEqual(
            app_copy_admission["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_NOT_ADMITTED",
        )
        self.assertEqual(app_copy_admission["final_verdict"], "WEB_SAFE_APP_COPY_LAUNCH_LIVE_BLOCKED")
        self.assertFalse(app_copy_admission["launch_ready_claimed"])
        self.assertFalse(app_copy_admission["bounded_live_launch_execution_ready"])
        self.assertTrue(app_copy_live["pid_not_exposed_to_browser"])
        self.assertEqual(app_copy_live["final_verdict"], "WEB_SAFE_APP_COPY_LAUNCH_LIVE_BLOCKED")
        self.assertEqual(app_copy_live["dry_run_final_verdict"], "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], ["model_id", "route_id", "CODEX_HOME"])
        self.assertEqual(custom_rejected["status"], "rejected")
        self.assertEqual(custom_rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(custom_rejected["forbidden_fields"], ["model", "route_id", "codex_home"])
        self.assertEqual(app_copy_rejected["status"], "blocked")
        self.assertEqual(
            app_copy_rejected["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
        )
        self.assertTrue(app_copy_rejected["browser_forbidden_fields_rejected"])
        self.assertFalse(app_copy_rejected["browser_forbidden_fields_absent"])
        self.assertEqual(app_copy_rejected["forbidden_fields"], ["path", "port", "env", "env.HOME"])

    def test_original_and_custom_launch_endpoints_prove_authorized_baseline_and_workbench(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = ReadyFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        review_import_context = live_server.default_review_import_context(ROOT)
        review_apply_context = live_server.default_review_apply_context(ROOT)

        with tempfile.TemporaryDirectory() as temp_dir:
            custom_sessions_root = Path(temp_dir) / "custom-sessions"
            app_bundle = Path(temp_dir) / "Codex.app"
            (app_bundle / "Contents" / "Resources").mkdir(parents=True)
            fake_binary = app_bundle / "Contents" / "Resources" / "codex"
            fake_binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_binary.chmod(0o755)
            protected = {"codex_config": {"exists": True, "mtime_ns": 1, "size": 1, "sha256": "a"}}
            with (
                mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory),
                mock.patch.object(live_server, "DEFAULT_CODEX_BIN", str(fake_binary)),
                mock.patch.object(live_server, "protected_snapshot", side_effect=[protected, protected]),
                mock.patch.object(live_server, "compare_snapshots", return_value={"codex_config": {"exists_unchanged": True, "mtime_ns_unchanged": True, "size_unchanged": True, "sha256_unchanged": True}}),
                mock.patch.object(live_server, "protected_surfaces_unchanged", return_value=True),
                mock.patch.object(live_server.subprocess, "run", return_value=live_server.subprocess.CompletedProcess(args=["open"], returncode=0, stdout="", stderr="")),
                mock.patch.object(
                    live_server,
                    "CodexCustomSessionManager",
                    side_effect=lambda root=None: REAL_CODEX_CUSTOM_SESSION_MANAGER(
                        custom_sessions_root if root is None else root
                    ),
                ),
            ):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                        review_import_context=review_import_context,
                        review_apply_context=review_apply_context,
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    original_launch = json.loads(post_json(f"{base}/api/codex/original/launch", {}))
                    custom_launch = json.loads(
                        post_json(f"{base}/api/codex/custom/launch", {"model_id": "gpt-5.3-codex"})
                    )
                    sessions = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(original_launch["status"], "ok")
        self.assertEqual(original_launch["machine_error_code"], "OK")
        self.assertTrue(original_launch["owner_authorization_phrase_present"])
        self.assertTrue(original_launch["running_status"])
        self.assertFalse(original_launch["proxy_env_present"])
        self.assertFalse(original_launch["wbp_endpoint_injected"])
        self.assertFalse(original_launch["custom_home_present"])
        self.assertFalse(original_launch["custom_codex_home_present"])
        self.assertFalse(original_launch["current_codex_touched"])
        self.assertEqual(custom_launch["status"], "ok")
        self.assertTrue(custom_launch["owner_authorization_phrase_present"])
        self.assertTrue(custom_launch["session_created"])
        self.assertTrue(custom_launch["running_status"])
        self.assertTrue(custom_launch["isolated_home"])
        self.assertTrue(custom_launch["isolated_codex_home"])
        self.assertTrue(custom_launch["isolated_workdir"])
        self.assertTrue(custom_launch["server_issued_model_list"])
        self.assertTrue(custom_launch["wbp_endpoint_configured"])
        self.assertFalse(custom_launch["browser_route_injection"])
        self.assertFalse(custom_launch["browser_backend_injection"])
        self.assertFalse(custom_launch["current_codex_touched"])
        self.assertTrue(custom_launch["workbench_ready"])
        self.assertEqual(custom_launch["selection_packet"]["selected_source_class"], "gpt_account")
        self.assertEqual(sessions["session_count"], 1)
        self.assertEqual(created_sessions[0].run_payloads, [])

    def test_custom_launch_requires_manual_model_selection_without_recommended_fallback(self) -> None:
        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession),
                mock.patch.object(
                    live_server,
                    "CodexCustomSessionManager",
                    side_effect=lambda root=None: REAL_CODEX_CUSTOM_SESSION_MANAGER(
                        Path(temp_dir) if root is None else root
                    ),
                ),
            ):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        owner_authorization_phrase=(
                            "разрешаю тебе любые законные действия в рамках разработки проекта"
                        ),
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    rejected = json.loads(post_json(f"{base}/api/codex/custom/launch", {}))
                    sessions = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "MANUAL_MODEL_SELECTION_REQUIRED")
        self.assertFalse(rejected["session_created"])
        self.assertFalse(rejected["model_auto_selected"])
        self.assertFalse(rejected["fallback_used"])
        self.assertFalse(rejected["external_route_selected"])
        self.assertFalse(rejected["running_status"])
        self.assertFalse(rejected["workbench_ready"])
        self.assertEqual(sessions["session_count"], 0)

    def test_custom_native_launch_endpoint_requires_owner_authorization(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(action_phase=live_server.FULL_ACTION_PHASE),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            blocked = json.loads(post_json(f"{base}/api/codex/custom/native-launch", {}))
            metadata = json.loads(fetch(f"{base}/api/actions"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertFalse(blocked["owner_authorization_phrase_present"])
        self.assertEqual(blocked["launch_claim_scope"], "custom_native_app_window_launch_only")
        native_action = metadata["actions"]["launch_custom_client_native"]
        self.assertFalse(native_action["available"])
        self.assertEqual(native_action["availability_state"], "owner_authorization_required")
        self.assertEqual(native_action["disabled_reason_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertIn("exact owner authorization", native_action["unavailable_reason"])

    def test_custom_native_launch_endpoint_rejects_browser_authority_fields(self) -> None:
        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {
                        "model_ids": ["gpt-5.3-codex"],
                        "server_issued": True,
                    },
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [],
                },
            ),
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "model_id": "gpt-5.3-codex",
                            "route_id": "wbp-route",
                            "profile_path": "/tmp/browser-profile",
                            "CODEX_HOME": "/tmp/browser-codex-home",
                            "HOME": "/tmp/browser-home",
                            "electron_user_data": "/tmp/browser-user-data",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            rejected["forbidden_fields"],
            ["route_id", "profile_path", "CODEX_HOME", "HOME", "electron_user_data"],
        )

    def test_custom_native_launch_endpoint_returns_native_proof_only_and_action_requires_selection(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-27T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native app launched and window proof passed.",
            "next_action": "none",
            "owner_authorization_phrase_present": True,
            "running_status": True,
            "process_started": True,
            "expected_custom_identity_observed": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "isolated_home": True,
            "isolated_codex_home": True,
            "isolated_profile_dir": True,
            "isolated_app_support_dir": True,
            "isolated_cache_dir": True,
            "isolated_runtime_dir": True,
            "server_owned_route_configuration": True,
            "browser_route_injection": False,
            "browser_backend_injection": False,
            "current_original_profile_shortcut_used": False,
            "current_codex_touched": False,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "workbench_ready": False,
            "native_launch_complete": False,
        }
        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )

        with (
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {
                        "model_ids": ["gpt-5.3-codex"],
                        "server_issued": True,
                    },
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={"status": "ok", "source": "api_connections_readonly", "primary_truth_ok": True, "routes": []},
            ),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                endpoint_packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "chatgpt_only",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
                ui_action = json.loads(
                    post_json(f"{base}/api/action", {"ui_action": "launch_custom_client_native"})
                )
                metadata = json.loads(fetch(f"{base}/api/actions"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(endpoint_packet["status"], "ok")
        self.assertEqual(launch_native.call_count, 1)
        self.assertTrue(launch_native.call_args.kwargs["keep_running_on_window_observed"])
        self.assertTrue(endpoint_packet["process_started"])
        self.assertTrue(endpoint_packet["expected_custom_identity_observed"])
        self.assertTrue(endpoint_packet["native_window_observed"])
        self.assertTrue(endpoint_packet["native_app_usable"])
        self.assertFalse(endpoint_packet["workbench_ready"])
        self.assertEqual(endpoint_packet["selection_packet"]["status"], "ok")
        self.assertEqual(endpoint_packet["execution_mode"], "chatgpt_only")
        self.assertEqual(endpoint_packet["chatgpt_model_id"], "gpt-5.3-codex")
        self.assertEqual(
            endpoint_packet["primary_model_slot"]["model_id"],
            "gpt-5.3-codex",
        )
        self.assertTrue(endpoint_packet["route_packet_matches_selection_packet"])
        self.assertTrue(endpoint_packet["quick_start_launch_route_truth_proven_with_limits"])
        self.assertEqual(
            endpoint_packet["launch_route_truth_final_status"],
            "QUICK_START_LAUNCH_ROUTE_TRUTH_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(ui_action["status"], "command_error")
        self.assertEqual(ui_action["result"]["status"], "failed")
        self.assertEqual(
            ui_action["result"]["machine_error_code"],
            "MANUAL_MODEL_SELECTION_REQUIRED",
        )
        self.assertEqual(
            ui_action["action_claim_scope"],
            "только Custom native app/window launch proof; это не prompt, route trace или egress truth",
        )
        self.assertFalse(ui_action["result"]["data"]["model_auto_selected"])
        self.assertFalse(ui_action["result"]["data"]["fallback_used"])
        self.assertFalse(ui_action["result"]["data"]["external_route_selected"])
        self.assertTrue(metadata["actions"]["launch_custom_client_native"]["available"])

    def test_custom_native_chatgpt_only_launch_does_not_occupy_api_bridge(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native app launched.",
            "next_action": "none",
            "owner_authorization_phrase_present": True,
            "process_started": True,
            "expected_custom_identity_observed": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "original_codex_touched": False,
            "asar_touched": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-deepseek-v4-pro-max",
            enabled=True,
        )

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(live_server._CustomNativeBridgeLease, "ensure") as ensure_bridge,
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                endpoint_packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "chatgpt_only",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(endpoint_packet["status"], "ok")
        stable_preflight.assert_not_called()
        ensure_bridge.assert_not_called()
        launch_native.assert_called_once()
        self.assertEqual(launch_native.call_args.kwargs["endpoint"], "http://127.0.0.1:8318/v1")
        self.assertEqual(endpoint_packet["execution_mode"], "chatgpt_only")
        self.assertEqual(endpoint_packet["selected_model"], "gpt-5.3-codex")
        self.assertFalse(endpoint_packet["external_route_selected"])
        self.assertFalse(endpoint_packet["bridge_endpoint_configured"])
        self.assertFalse(endpoint_packet["route_selected"])
        self.assertFalse(endpoint_packet["chatgpt_only_calls_api"])
        self.assertFalse(endpoint_packet["api_line_used_as_executor"])
        self.assertTrue(endpoint_packet["quick_start_launch_route_truth_proven_with_limits"])

    def test_custom_native_chatgpt_plus_api_launch_preserves_slots_and_routes_api_bridge(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native app launched.",
            "next_action": "none",
            "owner_authorization_phrase_present": True,
            "process_started": True,
            "expected_custom_identity_observed": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "original_codex_touched": False,
            "asar_touched": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-deepseek-v4-pro-max",
            enabled=True,
        )
        stable_preflight_ok = {
            "schema_version": 1,
            "packet_kind": "stable_bridge_preflight",
            "status": "ok",
            "machine_error_code": "OK",
            "final_status": "STABLE_BRIDGE_PREFLIGHT_PROVEN_WITH_LIMITS",
            "launch_allowed": True,
            "failure_reason": "",
            "blocking_reasons": [],
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=dict(stable_preflight_ok),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:9543/v1",
            ) as ensure_bridge,
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                endpoint_packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "chatgpt_plus_api",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(endpoint_packet["status"], "ok")
        stable_preflight.assert_called_once()
        bridge_prewarm.assert_called_once()
        ensure_bridge.assert_called_once()
        self.assertEqual(
            ensure_bridge.call_args.kwargs["forced_route_model_id"],
            "wbp-deepseek-v4-pro-max",
        )
        launch_native.assert_called_once()
        self.assertEqual(
            launch_native.call_args.kwargs["endpoint"],
            "http://127.0.0.1:9543/v1",
        )
        self.assertEqual(launch_native.call_args.kwargs["model"], "gpt-5.3-codex")
        self.assertEqual(endpoint_packet["execution_mode"], "chatgpt_plus_api")
        self.assertEqual(endpoint_packet["selected_model"], "gpt-5.3-codex")
        self.assertEqual(endpoint_packet["launch_model_id"], "gpt-5.3-codex")
        self.assertEqual(endpoint_packet["route_model_id"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(endpoint_packet["primary_model_slot"]["model_id"], "gpt-5.3-codex")
        self.assertEqual(
            endpoint_packet["coding_agent_model_slot"]["model_id"],
            "wbp-deepseek-v4-pro-max",
        )
        self.assertTrue(endpoint_packet["chatgpt_line_used_as_executor"])
        self.assertTrue(endpoint_packet["api_line_used_as_executor"])
        self.assertTrue(endpoint_packet["execution_mode_packet"]["dual_lane_slots_preserved"])
        self.assertFalse(endpoint_packet["execution_mode_packet"]["runtime_execution_proven"])
        self.assertFalse(
            endpoint_packet["execution_mode_packet"]["non_claims"]["simultaneous_execution_proven"]
        )
        self.assertFalse(endpoint_packet["api_only_calls_chatgpt"])
        self.assertFalse(endpoint_packet["chatgpt_only_calls_api"])
        self.assertTrue(endpoint_packet["external_route_selected"])
        self.assertTrue(endpoint_packet["bridge_endpoint_configured"])
        self.assertTrue(endpoint_packet["route_selected"])
        self.assertTrue(endpoint_packet["route_packet_matches_selection_packet"])
        self.assertTrue(endpoint_packet["stable_bridge_preflight_required"])
        self.assertEqual(endpoint_packet["stable_bridge_preflight_status"], "ok")
        self.assertTrue(endpoint_packet["stable_bridge_launch_allowed"])
        self.assertTrue(endpoint_packet["quick_start_launch_route_truth_proven_with_limits"])

    def test_custom_native_launch_blocks_api_modes_when_stable_bridge_preflight_blocks(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "process_started": True,
            "native_window_observed": True,
            "real_codex_app_launched": True,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        red_stable_preflight = {
            "schema_version": 1,
            "packet_kind": "stable_bridge_preflight",
            "status": "blocked",
            "machine_error_code": "STABLE_BRIDGE_PREFLIGHT_BLOCKED",
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN",
            "launch_allowed": False,
            "failure_reason": "missing_health_packet",
            "blocking_reasons": ["missing_health_packet", "unknown_not_admitted"],
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        cases = [
            (
                "api_only",
                {
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
            ),
            (
                "chatgpt_plus_api",
                {
                    "execution_mode": "chatgpt_plus_api",
                    "chatgpt_model_id": "gpt-5.3-codex",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
            ),
        ]
        for mode, payload in cases:
            with self.subTest(mode=mode):
                payloads = live_payloads()
                payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
                    "wbp-deepseek-v4-pro-max",
                    enabled=True,
                )
                with (
                    mock.patch.object(
                        live_server.OperatorSurfaceSession,
                        "status_payload",
                        return_value={
                            "status": {"configured_model": "gpt-5.3-codex"},
                            "claim_gate": {"status": "ok"},
                            "models": {
                                "model_ids": ["gpt-5.3-codex"],
                                "server_issued": True,
                            },
                        },
                    ),
                    mock.patch.object(
                        live_server,
                        "build_api_connections_readonly_snapshot",
                        return_value={
                            "status": "ok",
                            "source": "api_connections_readonly",
                            "primary_truth_ok": True,
                            "routes": [
                                {
                                    "route_id": "wbp-deepseek-v4-pro-max",
                                    "display_name": "DeepSeek V4 Pro · Максимум",
                                    "provider": "deepseek",
                                    "upstream_model": "deepseek-v4-pro",
                                    "enabled": True,
                                    "secret_ref": "DEEPSEEK_API_KEY",
                                    "thinking": {
                                        "type": "enabled",
                                        "reasoning_effort": "max",
                                    },
                                }
                            ],
                        },
                    ),
                    mock.patch.object(
                        live_server,
                        "collect_codex_process_inventory",
                        return_value={
                            "custom_process_count": 0,
                            "default_process_count": 0,
                            "custom_process_lines": [],
                        },
                    ),
                    mock.patch.object(
                        live_server,
                        "build_custom_codex_stable_bridge_preflight_packet",
                        return_value=dict(red_stable_preflight),
                    ) as stable_preflight,
                    mock.patch.object(
                        live_server,
                        "_custom_native_stable_bridge_prewarm_packet",
                        return_value=self.stable_bridge_prewarm_ok_packet(),
                    ) as bridge_prewarm,
                    mock.patch.object(
                        live_server,
                        "launch_custom_native_app_packet",
                        return_value=dict(native_packet),
                    ) as launch_native,
                    mock.patch.object(live_server.time, "sleep") as bridge_retry_sleep,
                ):
                    server = ThreadingHTTPServer(
                        ("127.0.0.1", free_port()),
                        build_handler(
                            runner=MappingRunner(payloads),
                            action_phase=live_server.FULL_ACTION_PHASE,
                            owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                        ),
                    )
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    base = f"http://127.0.0.1:{server.server_port}"
                    try:
                        packet = json.loads(
                            post_json(f"{base}/api/codex/custom/native-launch", payload)
                        )
                    finally:
                        server.shutdown()
                        thread.join(timeout=2)
                        server.server_close()

                self.assertEqual(packet["packet_kind"], "custom_native_launch_stability_guard")
                self.assertEqual(packet["status"], "blocked")
                self.assertEqual(packet["machine_error_code"], "STABLE_BRIDGE_PREFLIGHT_BLOCKED")
                self.assertTrue(packet["stable_bridge_preflight_required"])
                self.assertFalse(packet["stable_bridge_launch_allowed"])
                self.assertEqual(packet["stable_bridge_preflight_status"], "blocked")
                self.assertEqual(
                    packet["final_status"],
                    "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN",
                )
                self.assertEqual(stable_preflight.call_count, 2)
                self.assertEqual(bridge_prewarm.call_count, 2)
                bridge_retry_sleep.assert_called_once()
                launch_native.assert_not_called()

    def test_custom_native_launch_retries_stable_bridge_gate_after_successful_prewarm(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            route_id,
            enabled=True,
        )
        red_stable_preflight = {
            "schema_version": 1,
            "packet_kind": "stable_bridge_preflight",
            "status": "blocked",
            "machine_error_code": "STABLE_BRIDGE_PREFLIGHT_BLOCKED",
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN",
            "launch_allowed": False,
            "failure_reason": "cold_bridge_trace_not_ready",
            "blocking_reasons": ["cold_bridge_trace_not_ready"],
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "owner_authorization_phrase_present": True,
            "running_status": True,
            "process_started": True,
            "new_launch_started": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "current_codex_touched": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {
                        "model_ids": ["gpt-5.3-codex"],
                        "server_issued": True,
                    },
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": route_id,
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
            ),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                side_effect=[red_stable_preflight, self.stable_bridge_preflight_ok_packet()],
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:8319/v1",
            ),
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
            mock.patch.object(live_server.time, "sleep") as bridge_retry_sleep,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": route_id,
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["stable_bridge_preflight_required"])
        self.assertEqual(packet["stable_bridge_preflight_status"], "ok")
        self.assertTrue(packet["stable_bridge_launch_allowed"])
        self.assertTrue(packet["stable_bridge_preflight_retry_attempted"])
        self.assertEqual(packet["stable_bridge_preflight_retry_status"], "ok")
        self.assertTrue(packet["stable_bridge_prewarm_retry_attempted"])
        self.assertEqual(packet["stable_bridge_prewarm_retry_status"], "ok")
        self.assertTrue(packet["new_launch_started"])
        self.assertTrue(packet["real_codex_app_launched"])
        self.assertEqual(stable_preflight.call_count, 2)
        self.assertEqual(bridge_prewarm.call_count, 2)
        bridge_retry_sleep.assert_called_once()
        launch_native.assert_called_once()

    def test_custom_native_launch_blocks_api_only_when_stable_bridge_prewarm_fails(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "process_started": True,
            "native_window_observed": True,
            "real_codex_app_launched": True,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        prewarm_blocked = {
            "schema_version": 1,
            "packet_kind": "custom_native_stable_bridge_prewarm",
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_STABLE_WBP_BRIDGE_SMOKE_FAILED",
            "prewarm_required": True,
            "bridge_endpoint": "http://127.0.0.1:9543/v1",
            "selected_model": "wbp-deepseek-v4-pro-max",
            "smoke_status": "blocked",
            "smoke_http_status": 502,
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN",
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-deepseek-v4-pro-max",
            enabled=True,
        )

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
            ),
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=dict(prewarm_blocked),
            ) as bridge_prewarm,
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["packet_kind"], "custom_native_launch_stability_guard")
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_CODEX_STABLE_WBP_BRIDGE_SMOKE_FAILED",
        )
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN",
        )
        self.assertTrue(packet["stable_bridge_prewarm_required"])
        self.assertEqual(packet["stable_bridge_prewarm_status"], "blocked")
        bridge_prewarm.assert_called_once()
        stable_preflight.assert_not_called()
        launch_native.assert_not_called()

    def test_custom_native_launch_does_not_gate_chatgpt_only_on_stable_bridge_preflight(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native app launched.",
            "next_action": "none",
            "owner_authorization_phrase_present": True,
            "process_started": True,
            "expected_custom_identity_observed": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "original_codex_touched": False,
            "asar_touched": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        payloads = live_payloads()
        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "chatgpt_only",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["stable_bridge_preflight_required"])
        self.assertEqual(packet["stable_bridge_preflight_status"], "not_required")
        self.assertTrue(packet["stable_bridge_launch_allowed"])
        self.assertTrue(packet["selection_packet"]["api_model_ignored_for_mode"])
        self.assertTrue(packet["selection_packet"]["api_reasoning_option_ignored_for_mode"])
        self.assertFalse(packet["route_selected"])
        stable_preflight.assert_not_called()
        launch_native.assert_called_once()

    def test_custom_visible_history_confirmation_requires_fresh_stable_launch_and_owner_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "codex-home" / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            (session_dir / "thread.jsonl").write_text(
                "{\"type\":\"session_meta\"}\n",
                encoding="utf-8",
            )
            native_packet = {
                "schema_version": 1,
                "captured_at_utc": live_server.utc_now(),
                "mode_id": "codex_custom",
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "Custom Codex native app launched and window proof passed.",
                "next_action": "none",
                "owner_authorization_phrase_present": True,
                "process_started": True,
                "expected_custom_identity_observed": True,
                "native_window_observed": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "launch_claim_scope": "custom_native_app_window_launch_only",
                "profile_mode": "persistent_custom_profile",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root / "codex-home"),
                "temp_profile_used": False,
            }
            payloads = live_payloads()
            payloads[("status", "--json")] = status_packet(
                claim_gate={"status": "ok"},
                pool_summary={"selected_backend_ids": ["acct-active"]},
                auth_pool_hygiene={
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            )
            payloads[("accounts", "list", "--json")] = accounts_packet(
                accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
            )

            with (
                mock.patch.object(live_server, "launch_custom_native_app_packet", return_value=dict(native_packet)),
                mock.patch.object(
                    live_server.OperatorSurfaceSession,
                    "status_payload",
                    return_value={
                        "status": {"configured_model": "gpt-5.3-codex"},
                        "claim_gate": {"status": "ok"},
                        "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                    },
                ),
                mock.patch.object(
                    live_server,
                    "build_api_connections_readonly_snapshot",
                    return_value={"status": "ok", "source": "api_connections_readonly", "primary_truth_ok": True, "routes": []},
                ),
                mock.patch.object(
                    live_server,
                    "collect_codex_process_inventory",
                    return_value={
                        "custom_process_count": 0,
                        "default_process_count": 0,
                        "custom_process_lines": [],
                    },
                ),
            ):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        action_phase=live_server.FULL_ACTION_PHASE,
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    before_launch = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/visible-history/owner-confirmation",
                            {
                                "custom_codex_open": True,
                                "old_chat_visible": True,
                                "chat_not_empty": True,
                                "not_original_codex": True,
                                "raw_thread_content_not_recorded": True,
                            },
                        )
                    )
                    launch = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/native-launch",
                            {"model_id": "gpt-5.3-codex"},
                        )
                    )
                    confirmed = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/visible-history/owner-confirmation",
                            {
                                "custom_codex_open": True,
                                "old_chat_visible": True,
                                "chat_not_empty": True,
                                "not_original_codex": True,
                                "raw_thread_content_not_recorded": True,
                            },
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(before_launch["status"], "blocked")
        self.assertEqual(
            before_launch["machine_error_code"],
            "VISIBLE_HISTORY_FRESH_LAUNCH_PACKET_REQUIRED",
        )
        self.assertEqual(launch["status"], "ok")
        self.assertEqual(confirmed["status"], "ok")
        self.assertEqual(
            confirmed["final_status"],
            "VISIBLE_THREAD_HISTORY_RESTORE_OWNER_CONFIRMED_WITH_LIMITS",
        )
        self.assertTrue(confirmed["visible_thread_history_owner_confirmed"])
        self.assertTrue(confirmed["profile_storage_continuity_proven"])
        self.assertTrue(confirmed["session_storage_observed"])
        self.assertFalse(confirmed["session_file_content_read"])
        self.assertFalse(confirmed["raw_thread_content_recorded"])
        self.assertFalse(confirmed["full_history_restoration_claimed"])
        self.assertFalse(confirmed["all_threads_restored_claimed"])
        self.assertFalse(confirmed["cloud_history_restoration_claimed"])
        self.assertEqual(confirmed["persistent_profile_id"], "wbp-custom-main")
        self.assertNotIn("persistent_profile_root", confirmed)
        self.assertNotIn("persistent_codex_home", confirmed)
        self.assertFalse(confirmed["persistent_profile_path_exposed"])
        self.assertFalse(confirmed["persistent_codex_home_exposed"])
        self.assertFalse(confirmed["temp_profile_used"])
        self.assertTrue(confirmed["native_window_observed"])

    def test_custom_visible_history_confirmation_rejects_browser_raw_fields(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                action_phase=live_server.FULL_ACTION_PHASE,
                owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            rejected = json.loads(
                post_json(
                    f"{base}/api/codex/custom/visible-history/owner-confirmation",
                    {
                        "custom_codex_open": True,
                        "old_chat_visible": True,
                        "chat_not_empty": True,
                        "not_original_codex": True,
                        "raw_thread_content_not_recorded": True,
                        "raw_thread_text": "do not accept",
                        "profile_path": "/tmp/browser-profile",
                        "CODEX_HOME": "/tmp/browser-codex-home",
                    },
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            rejected["forbidden_fields"],
            ["CODEX_HOME", "profile_path", "raw_thread_text"],
        )
        self.assertFalse(rejected["raw_thread_content_recorded"])

    def test_custom_visible_history_confirmation_blocks_incomplete_owner_checklist_after_fresh_launch(self) -> None:
        packet = live_server.build_visible_thread_history_owner_confirmation_packet(
            {
                "custom_codex_open": True,
                "old_chat_visible": False,
                "chat_not_empty": True,
                "not_original_codex": True,
                "raw_thread_content_not_recorded": True,
            },
            owner_authorized=True,
            last_launch_packet={
                "captured_at_utc": live_server.utc_now(),
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "temp_profile_used": False,
                "native_window_observed": True,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "VISIBLE_HISTORY_OWNER_CONFIRMATION_INCOMPLETE",
        )
        self.assertFalse(packet["visible_thread_history_owner_confirmed"])
        self.assertEqual(
            packet["final_status"],
            "VISIBLE_THREAD_HISTORY_NOT_PROVEN_WITH_STORAGE_CONTINUITY",
        )

    def test_custom_visible_history_confirmation_blocks_stale_launch_packet(self) -> None:
        packet = live_server.build_visible_thread_history_owner_confirmation_packet(
            {
                "custom_codex_open": True,
                "old_chat_visible": True,
                "chat_not_empty": True,
                "not_original_codex": True,
                "raw_thread_content_not_recorded": True,
            },
            owner_authorized=True,
            last_launch_packet={
                "captured_at_utc": "2026-05-01T00:00:00Z",
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "temp_profile_used": False,
                "native_window_observed": True,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "VISIBLE_HISTORY_LAUNCH_PACKET_STALE")
        self.assertFalse(packet["visible_thread_history_owner_confirmed"])
        self.assertEqual(
            packet["final_status"],
            "VISIBLE_THREAD_HISTORY_NOT_PROVEN_WITH_STORAGE_CONTINUITY",
        )

    def test_custom_visible_history_relaunch_owner_confirmation_accepts_path_a(self) -> None:
        packet = live_server.build_custom_codex_visible_history_relaunch_owner_confirmation_packet(
            {
                "custom_codex_open": True,
                "old_chat_visible": True,
                "chat_not_empty": True,
                "not_original_codex": True,
                "owner_confirmed_after_relaunch": True,
                "raw_thread_content_not_recorded": True,
                "smoke_phrase_required": False,
                "smoke_phrase_visible": False,
            },
            owner_authorized=True,
            relaunch_profile_packet={
                "status": "ok",
                "profile_relaunch_proven": True,
                "session_storage_survived_relaunch": True,
                "original_codex_touched": False,
                "asar_touched": False,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_VISIBLE_HISTORY_RELAUNCH_OWNER_CONFIRMED_WITH_LIMITS",
        )
        self.assertTrue(packet["profile_relaunch_proven"])
        self.assertTrue(packet["session_storage_survived_relaunch"])
        self.assertTrue(packet["owner_confirmed_old_chat_visible"])
        self.assertTrue(packet["owner_confirmed_after_relaunch"])
        self.assertFalse(packet["owner_confirmed_smoke_phrase_visible"])
        self.assertFalse(packet["raw_thread_content_read"])
        self.assertFalse(packet["raw_thread_content_recorded"])
        self.assertFalse(packet["ocr_used_as_truth"])
        self.assertFalse(packet["all_history_restored_claimed"])
        self.assertFalse(packet["cloud_history_restored_claimed"])

    def test_custom_visible_history_relaunch_owner_confirmation_accepts_smoke_only_path(self) -> None:
        packet = live_server.build_custom_codex_visible_history_relaunch_owner_confirmation_packet(
            {
                "custom_codex_open": True,
                "old_chat_visible": False,
                "chat_not_empty": True,
                "not_original_codex": True,
                "owner_confirmed_after_relaunch": True,
                "raw_thread_content_not_recorded": True,
                "smoke_phrase_required": True,
                "smoke_phrase_visible": True,
            },
            owner_authorized=True,
            relaunch_profile_packet={
                "status": "ok",
                "profile_relaunch_proven": True,
                "session_storage_survived_relaunch": True,
                "original_codex_touched": False,
                "asar_touched": False,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_VISIBLE_HISTORY_SMOKE_CONFIRMED_WITH_LIMITS",
        )
        self.assertFalse(packet["owner_confirmed_old_chat_visible"])
        self.assertTrue(packet["owner_confirmed_smoke_phrase_visible"])
        self.assertTrue(packet["smoke_phrase_required"])

    def test_custom_visible_history_relaunch_owner_confirmation_requires_profile_truth(self) -> None:
        packet = live_server.build_custom_codex_visible_history_relaunch_owner_confirmation_packet(
            {
                "custom_codex_open": True,
                "old_chat_visible": True,
                "chat_not_empty": True,
                "not_original_codex": True,
                "owner_confirmed_after_relaunch": True,
                "raw_thread_content_not_recorded": True,
            },
            owner_authorized=True,
            relaunch_profile_packet={
                "status": "blocked",
                "profile_relaunch_proven": False,
                "session_storage_survived_relaunch": True,
                "original_codex_touched": False,
                "asar_touched": False,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_VISIBLE_HISTORY_UI_WITHOUT_PROFILE_PACKET_TRUTH",
        )
        self.assertEqual(
            packet["machine_error_code"],
            "VISIBLE_HISTORY_UI_WITHOUT_PROFILE_PACKET_TRUTH",
        )

    def test_custom_visible_history_relaunch_owner_confirmation_rejects_raw_fields(self) -> None:
        packet = live_server.build_custom_codex_visible_history_relaunch_owner_confirmation_packet(
            {
                "custom_codex_open": True,
                "old_chat_visible": True,
                "chat_not_empty": True,
                "not_original_codex": True,
                "owner_confirmed_after_relaunch": True,
                "raw_thread_content_not_recorded": True,
                "raw_thread_text": "do not accept",
                "CODEX_HOME": "/tmp/browser-codex-home",
            },
            owner_authorized=True,
            relaunch_profile_packet={
                "status": "ok",
                "profile_relaunch_proven": True,
                "session_storage_survived_relaunch": True,
                "original_codex_touched": False,
                "asar_touched": False,
            },
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["CODEX_HOME", "raw_thread_text"])
        self.assertFalse(packet["raw_thread_content_recorded"])

    def test_custom_native_launch_requires_manual_selection_before_fallback_or_native_launch(self) -> None:
        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            machine_error_code="AUTH_UNAVAILABLE",
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-web-primary-openrouter",
            enabled=True,
        )
        runner = MappingRunner(payloads)

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {
                        "configured_model": "gpt-5.3-codex",
                        "machine_error_code": "AUTH_UNAVAILABLE",
                    },
                    "claim_gate": {"status": "ok"},
                    "models": {"visible_model_ids": ["gpt-5.3-codex"]},
                },
            ) as status_payload,
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-web-primary-openrouter",
                            "enabled": True,
                            "primary": True,
                            "secret_ref": "OPENROUTER_API_KEY",
                        }
                    ],
                },
            ),
            mock.patch.object(live_server, "_build_live_native_availability_lattice_packet") as availability_lattice,
            mock.patch.object(live_server._CustomNativeBridgeLease, "ensure") as ensure_bridge,
            mock.patch.object(live_server, "launch_custom_native_app_packet") as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=runner,
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                endpoint_packet = json.loads(
                    post_json(f"{base}/api/codex/custom/native-launch", {})
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(endpoint_packet["status"], "rejected")
        self.assertEqual(endpoint_packet["machine_error_code"], "MANUAL_MODEL_SELECTION_REQUIRED")
        self.assertFalse(endpoint_packet["model_auto_selected"])
        self.assertFalse(endpoint_packet["fallback_used"])
        self.assertFalse(endpoint_packet["external_route_selected"])
        self.assertFalse(endpoint_packet["recommended_model_used"])
        self.assertFalse(endpoint_packet["route_fallback_used"])
        self.assertEqual(runner.calls, [])
        status_payload.assert_not_called()
        availability_lattice.assert_not_called()
        ensure_bridge.assert_not_called()
        launch_native.assert_not_called()

    def test_custom_native_launch_uses_explicit_api_route_when_codex_auth_unavailable(self) -> None:
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-29T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native app launched.",
            "next_action": "none",
            "owner_authorization_phrase_present": True,
            "process_started": True,
            "expected_custom_identity_observed": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "launch_claim_scope": "custom_native_app_window_launch_only",
        }
        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            machine_error_code="AUTH_UNAVAILABLE",
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-web-primary-openrouter",
            enabled=True,
        )

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {
                        "configured_model": "gpt-5.3-codex",
                        "machine_error_code": "AUTH_UNAVAILABLE",
                    },
                    "claim_gate": {"status": "ok"},
                    "models": {"visible_model_ids": ["gpt-5.3-codex"]},
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-web-primary-openrouter",
                            "enabled": True,
                            "primary": True,
                            "secret_ref": "OPENROUTER_API_KEY",
                        }
                    ],
                },
            ),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:9543/v1",
            ) as ensure_bridge,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=self.stable_bridge_preflight_ok_packet(),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                endpoint_packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {"model_id": "wbp-web-primary-openrouter"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(endpoint_packet["status"], "ok")
        bridge_prewarm.assert_called_once()
        stable_preflight.assert_called_once()
        ensure_bridge.assert_called_once()
        self.assertEqual(
            ensure_bridge.call_args.kwargs["forced_route_model_id"],
            "wbp-web-primary-openrouter",
        )
        launch_native.assert_called_once()
        _, kwargs = launch_native.call_args
        self.assertEqual(kwargs["endpoint"], "http://127.0.0.1:9543/v1")
        self.assertEqual(kwargs["model"], "wbp-web-primary-openrouter")

    def test_custom_native_launch_api_only_uses_execution_mode_api_model_without_chatgpt_fallback(self) -> None:
        profile_root = ROOT / "test_profiles" / "test-wbp-custom-main"
        native_packet = {
            "schema_version": 1,
            "captured_at_utc": "2026-05-29T00:00:00Z",
            "mode_id": "codex_custom",
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native app launched.",
            "next_action": "none",
            "owner_authorization_phrase_present": True,
            "process_started": True,
            "expected_custom_identity_observed": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "real_codex_app_launched": True,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "profile_mode": "persistent_custom",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": str(profile_root),
            "persistent_codex_home": str(profile_root),
            "persistent_user_data_dir": str(profile_root / "electron-user-data"),
            "persistent_runtime_tmp_dir": "/tmp/wbp-cdx-wbp-custom-main",
            "temp_profile_used": False,
            "current_codex_touched": False,
            "cleanup_deletes_persistent_profile_by_default": False,
            "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
            "original_codex_profile_runtime_dependency": False,
        }
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-deepseek-v4-pro-max",
            enabled=True,
        )
        runner = MappingRunner(payloads)
        stable_preflight_ok = {
            "schema_version": 1,
            "packet_kind": "stable_bridge_preflight",
            "status": "ok",
            "machine_error_code": "OK",
            "final_status": "STABLE_BRIDGE_PREFLIGHT_PROVEN_WITH_LIMITS",
            "launch_allowed": True,
            "failure_reason": "",
            "blocking_reasons": [],
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ) as status_payload,
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
            ),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:9543/v1",
            ) as ensure_bridge,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=dict(stable_preflight_ok),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "launch_custom_native_app_packet",
                return_value=dict(native_packet),
            ) as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=runner,
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                endpoint_packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(endpoint_packet["status"], "ok")
        bridge_prewarm.assert_called_once()
        stable_preflight.assert_called_once()
        self.assertEqual(endpoint_packet["execution_mode"], "api_only")
        self.assertEqual(endpoint_packet["api_model_id"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(endpoint_packet["api_reasoning_option_id"], "provider_declared_max")
        self.assertEqual(
            endpoint_packet["api_reasoning_option_packet"]["provider_option"]["thinking"],
            {"type": "enabled", "reasoning_effort": "max"},
        )
        self.assertFalse(endpoint_packet["api_reasoning_option_runtime_mutation_claimed"])
        self.assertEqual(endpoint_packet["selected_model"], "wbp-deepseek-v4-pro-max")
        self.assertTrue(endpoint_packet["api_line_used_as_executor"])
        self.assertFalse(endpoint_packet["chatgpt_line_used_as_executor"])
        self.assertFalse(endpoint_packet["api_only_calls_chatgpt"])
        self.assertNotIn(("healthcheck", "--json"), runner.calls)
        self.assertFalse(endpoint_packet["fallback_used"])
        self.assertFalse(endpoint_packet["model_auto_selected"])
        self.assertTrue(endpoint_packet["route_packet_matches_selection_packet"])
        self.assertTrue(endpoint_packet["quick_start_launch_route_truth_proven_with_limits"])
        self.assertEqual(
            endpoint_packet["launch_route_truth_final_status"],
            "QUICK_START_LAUNCH_ROUTE_TRUTH_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(endpoint_packet["server_issued_catalog_used"])
        self.assertFalse(endpoint_packet["raw_backend_details_exposed"])
        self.assertFalse(endpoint_packet["secret_value_exposed"])
        self.assertFalse(endpoint_packet["original_codex_touched"])
        self.assertFalse(endpoint_packet["asar_touched"])
        self.assertTrue(endpoint_packet["external_route_selected"])
        self.assertTrue(endpoint_packet["stable_bridge_preflight_required"])
        self.assertEqual(endpoint_packet["stable_bridge_preflight_status"], "ok")
        self.assertTrue(endpoint_packet["stable_bridge_launch_allowed"])
        self.assertTrue(
            endpoint_packet["custom_codex_window_deepseek_launch_proven_with_limits"]
        )
        self.assertEqual(
            endpoint_packet["custom_codex_window_deepseek_smoke_final_status"],
            "CUSTOM_CODEX_WINDOW_DEEPSEEK_LAUNCH_PROVEN_PROMPT_SMOKE_BLOCKED_WITH_LIMITS",
        )
        self.assertFalse(endpoint_packet["manual_prompt_smoke_attempted"])
        self.assertFalse(endpoint_packet["manual_prompt_smoke_proven"])
        self.assertFalse(endpoint_packet["manual_prompt_smoke_counts_as_model_truth"])
        self.assertEqual(
            endpoint_packet["manual_prompt_smoke_blocked_reason"],
            "manual_native_window_prompt_not_automated",
        )
        self.assertFalse(endpoint_packet["model_self_report_counts_as_runtime_truth"])
        self.assertFalse(endpoint_packet["deepseek_window_prompt_runtime_truth_proven"])
        self.assertFalse(endpoint_packet["history_persistence_claimed"])
        self.assertFalse(endpoint_packet["visible_thread_history_restored_claimed"])
        self.assertEqual(
            endpoint_packet["quick_start_stable_custom_launch_final_status"],
            "QUICK_START_STABLE_CUSTOM_LAUNCH_WITH_PROFILE_REUSE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(endpoint_packet["quick_start_stable_custom_launch_profile_reuse_proven_with_limits"])
        self.assertEqual(
            endpoint_packet["profile_final_status"],
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(endpoint_packet["profile_persistence_proven"])
        self.assertTrue(endpoint_packet["persistent_profile_reused"])
        self.assertTrue(endpoint_packet["codex_home_reused"])
        self.assertTrue(endpoint_packet["electron_user_data_reused"])
        self.assertFalse(endpoint_packet["temp_profile_used"])
        self.assertTrue(endpoint_packet["profile_path_stable"])
        self.assertFalse(endpoint_packet["persistent_profile_root_is_tmp"])
        self.assertFalse(endpoint_packet["persistent_codex_home_is_tmp"])
        self.assertFalse(endpoint_packet["persistent_user_data_dir_is_tmp"])
        self.assertFalse(endpoint_packet["persistent_profile_path_exposed"])
        self.assertFalse(endpoint_packet["persistent_codex_home_exposed"])
        self.assertFalse(endpoint_packet["persistent_user_data_dir_exposed"])
        self.assertTrue(endpoint_packet["profile_relaunch_required_for_strong_history_claim"])
        self.assertEqual(endpoint_packet["visible_history_restore"], "not_claimed")
        self.assertFalse(endpoint_packet["full_history_restoration_claimed"])
        self.assertEqual(
            endpoint_packet["primary_model_slot"]["model_id"],
            "wbp-deepseek-v4-pro-max",
        )
        self.assertEqual(endpoint_packet["primary_model_slot"]["lane"], "api_route_lane")
        ensure_bridge.assert_called_once()
        self.assertEqual(
            ensure_bridge.call_args.kwargs["forced_route_model_id"],
            "wbp-deepseek-v4-pro-max",
        )
        launch_native.assert_called_once()
        _, kwargs = launch_native.call_args
        self.assertEqual(
            set(kwargs),
            {
                "repo_root",
                "endpoint",
                "model",
                "owner_authorization_phrase",
                "keep_running_on_window_observed",
                "reuse_existing_window_if_present",
            },
        )
        self.assertTrue(kwargs["keep_running_on_window_observed"])
        self.assertFalse(kwargs["reuse_existing_window_if_present"])
        self.assertEqual(kwargs["endpoint"], "http://127.0.0.1:9543/v1")
        self.assertEqual(kwargs["model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(
            kwargs["owner_authorization_phrase"],
            "разрешаю тебе любые законные действия в рамках разработки проекта",
        )
        self.assertNotIn("api_key", kwargs)
        self.assertNotIn("base_url", kwargs)
        self.assertNotIn("secret_ref", kwargs)
        self.assertNotIn("CODEX_HOME", kwargs)
        status_payload.assert_called()
        self.assertEqual(runner.calls, [("external-models", "routes", "list", "--json")])

    def test_custom_window_prompt_trace_requires_matching_deepseek_route_packet(self) -> None:
        route_digest = live_server._safe_route_digest(
            {
                "route_id": "wbp-deepseek-v4-pro-max",
                "provider": "deepseek",
                "upstream_model": "deepseek-v4-pro",
                "endpoint_path": "/chat/completions",
                "thinking": {"type": "enabled", "reasoning_effort": "max"},
            }
        )
        packet = live_server.build_custom_codex_window_prompt_trace_packet(
            last_launch_packet={
                "status": "ok",
                "launch_id": "launch-test",
                "trace_id": "trace-test",
                "selected_model": "wbp-deepseek-v4-pro-max",
                "api_reasoning_option_id": "provider_declared_max",
                "launch_route_digest": route_digest,
                "custom_codex_window_deepseek_launch_proven_with_limits": True,
                "native_window_observed": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "original_codex_touched": False,
                "asar_touched": False,
            },
            bridge_trace_packet={
                "request_count": 1,
                "bridge_machine_error_code": "OK",
                "bridge_health_packet": {
                    "packet_kind": "hybrid_openai_compat_bridge_health",
                    "machine_error_code": "OK",
                    "responses_endpoint_ready": True,
                    "fallback_used": False,
                    "secret_value_recorded": False,
                },
                "bridge_request_trace_packet": {
                    "packet_kind": "hybrid_openai_compat_bridge_request_trace",
                    "machine_error_code": "OK",
                    "route_unchanged": True,
                    "fallback_used": False,
                    "retry_attempted": False,
                },
                "last_record": {
                    "launch_id": "launch-test",
                    "trace_id": "trace-test",
                    "path": "/v1/responses",
                    "request_seen_after_launch": True,
                    "selected_model": "wbp-deepseek-v4-pro-max",
                    "requested_model": "gpt-5.4",
                    "effective_route_model": "wbp-deepseek-v4-pro-max",
                    "forced_route_used": True,
                    "route_digest": route_digest,
                    "route_digest_matches_launch": True,
                    "provider_called": True,
                    "provider_id": "deepseek",
                    "upstream_model": "deepseek-v4-pro",
                    "api_reasoning_option_id": "provider_declared_max",
                    "known_smoke_phrase_matched": True,
                    "response_seen": True,
                    "upstream_status": 200,
                    "prompt_hash": "abc",
                    "response_body_sha256": "def",
                    "chatgpt_route_used": False,
                    "api_only_calls_chatgpt": False,
                    "fallback_used": False,
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                },
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_WINDOW_DEEPSEEK_PROMPT_TRACE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["request_seen_after_launch"])
        self.assertTrue(packet["provider_called"])
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertEqual(packet["upstream_model"], "deepseek-v4-pro")
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v4-pro-max")
        self.assertTrue(packet["native_app_usable"])
        self.assertEqual(packet["api_reasoning_option_id"], "provider_declared_max")
        self.assertTrue(packet["known_smoke_phrase_matched"])
        self.assertTrue(packet["route_digest_matches_launch"])
        self.assertTrue(packet["route_unchanged"])
        self.assertEqual(packet["bridge_machine_error_code"], "OK")
        self.assertEqual(
            packet["bridge_health_packet"]["packet_kind"],
            "hybrid_openai_compat_bridge_health",
        )
        self.assertEqual(
            packet["bridge_request_trace_packet"]["packet_kind"],
            "hybrid_openai_compat_bridge_request_trace",
        )
        self.assertFalse(packet["chatgpt_route_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["response_text_counts_as_model_truth"])
        self.assertFalse(packet["model_self_report_counts_as_runtime_truth"])
        self.assertFalse(packet["history_persistence_claimed"])
        self.assertFalse(packet["live_coding_claimed"])

    def test_custom_window_prompt_trace_blocks_legacy_window_proof_without_usability(self) -> None:
        launch, bridge = self._window_input_route_trace_fixture()
        launch.pop("native_app_usable", None)

        packet = live_server.build_custom_codex_window_prompt_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet=bridge,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["window_launch_proven_with_limits"])
        self.assertFalse(packet["native_app_usable"])
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_WINDOW_PROMPT_ROUTE_TRACE_NOT_PROVEN",
        )

    def test_custom_window_prompt_trace_rejects_browser_authority_fields(self) -> None:
        packet = live_server.build_custom_codex_window_prompt_trace_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={"trace_id": ["browser"], "provider_id": ["deepseek"]},
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["provider_id", "trace_id"])
        self.assertFalse(packet["browser_trace_authority"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["secret_value_exposed"])

    def _window_input_route_trace_fixture(
        self,
        *,
        request_seen: bool = True,
        fallback_used: bool = False,
    ) -> tuple[dict[str, object], dict[str, object]]:
        route_digest = live_server._safe_route_digest(
            {
                "route_id": "wbp-deepseek-v4-pro-max",
                "provider": "deepseek",
                "upstream_model": "deepseek-v4-pro",
                "endpoint_path": "/chat/completions",
                "thinking": {"type": "enabled", "reasoning_effort": "max"},
            }
        )
        launch: dict[str, object] = {
            "status": "ok",
            "launch_id": "launch-test",
            "trace_id": "trace-test",
            "execution_mode": "api_only",
            "selected_model": "wbp-deepseek-v4-pro-max",
            "api_reasoning_option_id": "provider_declared_max",
            "launch_route_digest": route_digest,
            "custom_codex_window_deepseek_launch_proven_with_limits": True,
            "native_window_observed": True,
            "native_app_usable": True,
            "custom_window_visible": True,
            "real_codex_app_launched": True,
            "custom_window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 783},
            "window_focus_action_attempted": True,
            "window_focus_action_succeeded": True,
            "chatgpt_only_calls_api": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        bridge: dict[str, object] = {
            "request_count": 1 if request_seen else 0,
            "last_record": {
                "launch_id": "launch-test",
                "trace_id": "trace-test",
                "path": "/v1/responses",
                "request_seen_after_launch": request_seen,
                "selected_model": "wbp-deepseek-v4-pro-max",
                "requested_model": "gpt-5.4",
                "effective_route_model": "wbp-deepseek-v4-pro-max",
                "forced_route_used": True,
                "route_digest": route_digest,
                "route_digest_matches_launch": True,
                "provider_called": True,
                "provider_id": "deepseek",
                "upstream_model": "deepseek-v4-pro",
                "api_reasoning_option_id": "provider_declared_max",
                "known_smoke_phrase_matched": True,
                "response_seen": request_seen,
                "upstream_status": 200,
                "prompt_hash": "abc" if request_seen else "",
                "response_body_sha256": "def" if request_seen else "",
                "chatgpt_route_used": False,
                "api_only_calls_chatgpt": False,
                "fallback_used": fallback_used,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            },
        }
        return launch, bridge

    def test_custom_window_input_route_trace_requires_input_prompt_seen(self) -> None:
        launch, bridge = self._window_input_route_trace_fixture(request_seen=False)
        packet = live_server.build_custom_codex_window_input_route_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet=bridge,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["input_surface_observed"])
        self.assertFalse(packet["input_proven"])
        self.assertFalse(packet["route_trace_proven"])
        self.assertFalse(packet["send_succeeded"])
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_INPUT_OR_ROUTE_NOT_PROVEN",
        )
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_custom_window_input_route_trace_does_not_treat_input_as_route(self) -> None:
        launch, bridge = self._window_input_route_trace_fixture(fallback_used=True)
        packet = live_server.build_custom_codex_window_input_route_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet=bridge,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["input_proven"])
        self.assertTrue(packet["send_succeeded"])
        self.assertFalse(packet["route_trace_proven"])
        self.assertTrue(packet["fallback_used"])
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertFalse(packet["response_text_counts_as_model_truth"])

    def test_custom_window_input_route_trace_proves_input_and_deepseek_route(self) -> None:
        launch, bridge = self._window_input_route_trace_fixture()
        packet = live_server.build_custom_codex_window_input_route_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet=bridge,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_INPUT_AND_DEEPSEEK_ROUTE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["input_proven"])
        self.assertTrue(packet["route_trace_proven"])
        self.assertTrue(packet["provider_called"])
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["history_persistence_claimed"])

    def test_custom_window_input_route_trace_rejects_browser_authority_fields(self) -> None:
        packet = live_server.build_custom_codex_window_input_route_trace_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={"model_id": ["wbp-deepseek-v4-pro-max"]},
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["model_id"])
        self.assertFalse(packet["browser_trace_authority"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_custom_window_input_route_trace_endpoint_rejects_query_authority(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/window-input-route-trace?trace_id=browser",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["trace_id"])
        self.assertFalse(packet["browser_trace_authority"])

    def test_custom_bridge_failure_recovery_truth_rejects_browser_authority_fields(self) -> None:
        packet = live_server.build_custom_codex_bridge_failure_recovery_truth_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={"route_id": ["browser"], "api_key": ["sk-browser"]},
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["api_key", "route_id"])
        self.assertFalse(packet["browser_trace_authority"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["restart_attempted"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_custom_stable_bridge_preflight_rejects_browser_authority_fields(self) -> None:
        packet = live_server.build_custom_codex_stable_bridge_preflight_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={"trace_id": ["browser"], "api_key": ["sk-browser"]},
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["api_key", "trace_id"])
        self.assertFalse(packet["launch_allowed"])
        self.assertFalse(packet["browser_trace_authority"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_custom_stable_bridge_preflight_endpoint_blocks_unknown_empty_bridge(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/stable-bridge-preflight",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["packet_kind"], "stable_bridge_preflight")
        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["launch_allowed"])
        self.assertIn("unknown_not_admitted", packet["blocking_reasons"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN",
        )

    def _live_bridge_launch_fixture(
        self,
        *,
        trace_id: str = "trace-live-bridge",
        launch_id: str = "launch-live-bridge",
        execution_mode: str = "api_only",
        native_window_observed: bool = True,
    ) -> dict[str, object]:
        return {
            "status": "ok",
            "launch_id": launch_id,
            "trace_id": trace_id,
            "execution_mode": execution_mode,
            "selected_model": "wbp-deepseek-v4-pro-max",
            "native_window_observed": native_window_observed,
            "bridge_port": 50555,
            "fallback_used": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }

    def _live_bridge_trace_fixture(
        self,
        *,
        trace_id: str = "trace-live-bridge",
        launch_id: str = "launch-live-bridge",
        bridge_code: str = "OK",
        upstream_status: int = 200,
        auth_ok: bool = True,
        fallback_used: bool = False,
        stream_requested: bool = False,
        stream_completed: bool = False,
        stale_port_detected: bool = False,
        route_unchanged: bool = True,
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "packet_kind": "hybrid_openai_compat_prompt_trace",
            "trace_id": trace_id,
            "launch_packet_id": launch_id,
            "bridge_alive": True,
            "responses_endpoint_alive": bridge_code == "OK",
            "bridge_machine_error_code": bridge_code,
            "fallback_used": fallback_used,
            "stale_port_detected": stale_port_detected,
            "route_unchanged": route_unchanged,
            "bridge_health_packet": {
                "bridge_alive": True,
                "responses_endpoint_ready": bridge_code == "OK",
                "bridge_port": 50555,
                "port_owned_by_bridge": True,
                "auth_header_expected": True,
                "auth_header_present": True,
                "auth_ok": auth_ok,
                "machine_error_code": bridge_code,
                "fallback_used": fallback_used,
                "route_unchanged": route_unchanged,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            },
            "bridge_request_trace_packet": {
                "request_started": True,
                "path": "/v1/responses",
                "machine_error_code": bridge_code,
                "upstream_status": upstream_status,
                "route_unchanged": route_unchanged,
                "provider_called": True,
                "downstream_called": True,
                "fallback_used": fallback_used,
                "fallback_attempted": fallback_used,
                "stream_requested": stream_requested,
                "stream_started": stream_requested,
                "stream_completed": stream_completed,
                "auth_header_expected": True,
                "auth_header_seen": True,
                "auth_ok": auth_ok,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            },
            "last_record": {
                "launch_packet_id": launch_id,
                "trace_id": trace_id,
                "request_seen_after_launch": True,
                "path": "/v1/responses",
                "upstream_status": upstream_status,
                "bridge_machine_error_code": bridge_code,
                "fallback_used": fallback_used,
                "provider_called": True,
                "downstream_called": True,
                "route_digest_matches_launch": route_unchanged,
                "auth_header_seen": True,
                "auth_ok": auth_ok,
                "response_seen": bridge_code == "OK",
                "stream_requested": stream_requested,
                "stream_started": stream_requested,
                "stream_completed": stream_completed,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            },
        }

    def test_custom_live_bridge_stability_reports_ready_packet(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=self._live_bridge_trace_fixture(),
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["bridge_status"], "BRIDGE_READY")
        self.assertEqual(packet["machine_error_code"], "BRIDGE_READY")
        self.assertTrue(packet["bridge_alive"])
        self.assertTrue(packet["bridge_port_known"])
        self.assertTrue(packet["launch_id_known"])
        self.assertTrue(packet["trace_id_known"])
        self.assertEqual(packet["failure_machine_error_code"], "OK")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_LIVE_BRIDGE_STABILITY_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["port_alive"])
        self.assertTrue(packet["responses_endpoint_available"])
        self.assertTrue(packet["auth_token_consistent"])
        self.assertTrue(packet["selected_mode_known"])
        self.assertTrue(packet["bridge_session_matches_active_window"])
        self.assertTrue(packet["request_seen_after_launch"])
        self.assertTrue(packet["last_request_seen"])
        self.assertTrue(packet["upstream_called"])
        self.assertTrue(packet["response_seen"])
        self.assertTrue(packet["stream_completed"])
        self.assertFalse(packet["stream_disconnected"])
        self.assertTrue(packet["auth_header_expected"])
        self.assertTrue(packet["auth_header_seen"])
        self.assertFalse(packet["auth_mismatch"])
        self.assertFalse(packet["stale_port"])
        self.assertFalse(packet["old_window_answered"])
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertFalse(packet["recovery_available"])
        self.assertEqual(packet["recommended_recovery_action"], "none")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["silent_fallback_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_custom_live_bridge_stability_classifies_auth_failure(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=self._live_bridge_trace_fixture(
                bridge_code="BRIDGE_AUTH_REJECTED",
                upstream_status=401,
                auth_ok=False,
            ),
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_AUTH_FAILED")
        self.assertEqual(packet["machine_error_code"], "BRIDGE_AUTH_FAILED")
        self.assertEqual(packet["failure_machine_error_code"], "BRIDGE_AUTH_MISMATCH")
        self.assertEqual(packet["last_http_status"], 401)
        self.assertTrue(packet["auth_mismatch"])
        self.assertEqual(packet["recommended_recovery_action"], "reauthorize")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["restart_attempted"])

    def test_custom_live_bridge_stability_classifies_stream_disconnect(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=self._live_bridge_trace_fixture(
                bridge_code="BRIDGE_STREAM_DISCONNECTED",
                stream_requested=True,
                stream_completed=False,
            ),
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_STREAM_DISCONNECTED")
        self.assertEqual(packet["failure_machine_error_code"], "UPSTREAM_STREAM_INTERRUPTED")
        self.assertTrue(packet["stream_disconnected"])
        self.assertFalse(packet["stream_completed"])
        self.assertEqual(packet["recommended_recovery_action"], "restart_bridge")
        self.assertTrue(packet["recovery_required"])
        self.assertFalse(packet["fallback_used"])

    def test_custom_live_bridge_stability_classifies_stale_port(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=self._live_bridge_trace_fixture(
                bridge_code="BRIDGE_PORT_STALE",
                stale_port_detected=True,
            ),
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_STALE_PORT")
        self.assertEqual(packet["failure_machine_error_code"], "BRIDGE_PORT_STALE")
        self.assertTrue(packet["stale_port"])
        self.assertEqual(packet["recommended_recovery_action"], "restart_bridge")
        self.assertTrue(packet["recovery_required"])
        self.assertFalse(packet["fallback_used"])

    def test_custom_live_bridge_stability_classifies_window_not_bound(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(trace_id="trace-current"),
            bridge_trace_packet=self._live_bridge_trace_fixture(trace_id="trace-old"),
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_WINDOW_NOT_BOUND")
        self.assertEqual(packet["failure_machine_error_code"], "WINDOW_BOUND_TO_OLD_BRIDGE")
        self.assertFalse(packet["bridge_session_matches_active_window"])
        self.assertFalse(packet["trace_id_matches_launch"])
        self.assertTrue(packet["old_window_answered"])
        self.assertEqual(packet["recommended_recovery_action"], "relaunch_custom")
        self.assertTrue(packet["recovery_required"])

    def test_custom_live_bridge_stability_exposes_fallback_without_green_status(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=self._live_bridge_trace_fixture(fallback_used=True),
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_RECOVERY_REQUIRED")
        self.assertEqual(packet["failure_machine_error_code"], "FALLBACK_USED")
        self.assertTrue(packet["fallback_used"])
        self.assertTrue(packet["fallback_attempted"])
        self.assertFalse(packet["silent_fallback_used"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_CUSTOM_CODEX_LIVE_BRIDGE_STABILITY_NOT_PROVEN",
        )

    def test_custom_live_bridge_stability_rejects_browser_authority_fields(self) -> None:
        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={"trace_id": ["browser"], "api_key": ["sk-browser"]},
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["api_key", "trace_id"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["browser_trace_authority"])

    def test_custom_live_bridge_stability_blocks_chatgpt_called_in_api_only(self) -> None:
        trace = self._live_bridge_trace_fixture()
        trace["last_record"]["chatgpt_route_used"] = True
        trace["bridge_request_trace_packet"]["chatgpt_route_used"] = True

        packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(execution_mode="api_only"),
            bridge_trace_packet=trace,
            expected_bridge_port=50555,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_API_ONLY_CHATGPT_CALLED")
        self.assertEqual(packet["failure_machine_error_code"], "CHATGPT_CALLED_IN_API_ONLY")
        self.assertTrue(packet["api_only_calls_chatgpt"])
        self.assertFalse(packet["fallback_used"])

    def test_custom_live_bridge_stability_blocks_request_not_seen_and_response_not_seen(self) -> None:
        no_request = self._live_bridge_trace_fixture()
        no_request["bridge_request_trace_packet"]["request_started"] = False
        no_request["last_record"]["request_seen_after_launch"] = False

        request_packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=no_request,
            expected_bridge_port=50555,
        )

        self.assertEqual(request_packet["status"], "blocked")
        self.assertEqual(request_packet["failure_machine_error_code"], "REQUEST_NOT_SEEN")
        self.assertFalse(request_packet["last_request_seen"])

        no_response = self._live_bridge_trace_fixture(bridge_code="BRIDGE_RESPONSES_ENDPOINT_UNREADY")
        no_response["last_record"]["response_seen"] = False

        response_packet = live_server.build_custom_codex_live_bridge_stability_packet(
            last_launch_packet=self._live_bridge_launch_fixture(),
            bridge_trace_packet=no_response,
            expected_bridge_port=50555,
        )

        self.assertEqual(response_packet["status"], "blocked")
        self.assertEqual(response_packet["failure_machine_error_code"], "RESPONSE_NOT_SEEN")
        self.assertFalse(response_packet["last_response_seen"])

    def test_custom_live_bridge_stability_endpoint_reports_current_packet(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/live-bridge-stability",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["packet_kind"], "custom_codex_live_bridge_stability")
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["bridge_status"], "BRIDGE_WINDOW_NOT_BOUND")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_custom_bridge_failure_recovery_truth_endpoint_rejects_query_authority(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/bridge-failure-recovery-truth?trace_id=browser",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["trace_id"])
        self.assertFalse(packet["browser_trace_authority"])

    def test_custom_bridge_failure_recovery_truth_endpoint_reports_current_trace_without_restart(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/bridge-failure-recovery-truth",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["packet_kind"], "custom_codex_bridge_failure_recovery_truth")
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "BRIDGE_RESPONSES_ENDPOINT_UNREADY")
        self.assertFalse(packet["browser_trace_authority"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["restart_attempted"])
        self.assertFalse(packet["live_paid_call_attempted_by_packet"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_chatgpt_plus_api_coder_trace_reports_slot_binding_without_dispatch(self) -> None:
        packet = live_server.build_custom_codex_chatgpt_plus_api_coder_trace_packet(
            last_launch_packet={
                "status": "ok",
                "launch_id": "launch-test",
                "trace_id": "trace-test",
                "execution_mode": "chatgpt_plus_api",
                "native_window_observed": True,
                "real_codex_app_launched": True,
                "stable_bridge_preflight_required": True,
                "stable_bridge_preflight_status": "ok",
                "stable_bridge_launch_allowed": True,
                "primary_model_slot": {
                    "slot_id": "primary_model_slot",
                    "status": "bound",
                    "lane": "codex_account_lane",
                    "model_id": "gpt-5.4",
                    "server_issued": True,
                },
                "coding_agent_model_slot": {
                    "slot_id": "coding_agent_model_slot",
                    "status": "bound",
                    "lane": "api_route_lane",
                    "provider": "deepseek",
                    "model_id": "wbp-deepseek-v4-pro-max",
                    "server_issued": True,
                },
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
                "original_codex_touched": False,
                "asar_touched": False,
            },
            bridge_trace_packet={
                "request_count": 1,
                "records": [
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "gpt-5.4",
                        "downstream_called": True,
                        "chatgpt_route_used": True,
                        "provider_called": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    }
                ],
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["slot_binding_proven"])
        self.assertTrue(packet["prompt_seen"])
        self.assertFalse(packet["coder_dispatch_proven"])
        self.assertEqual(
            packet["stage_statuses"]["coder_dispatch"],
            "KNOWN_BLOCKER_CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED",
        )
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_chatgpt_plus_api_coder_trace_proves_deepseek_coder_dispatch(self) -> None:
        launch = {
            "status": "ok",
            "launch_id": "launch-test",
            "trace_id": "trace-test",
            "execution_mode": "chatgpt_plus_api",
            "native_window_observed": True,
            "real_codex_app_launched": True,
            "stable_bridge_preflight_required": True,
            "stable_bridge_preflight_status": "ok",
            "stable_bridge_launch_allowed": True,
            "primary_model_slot": {
                "slot_id": "primary_model_slot",
                "status": "bound",
                "lane": "codex_account_lane",
                "model_id": "gpt-5.4",
                "server_issued": True,
            },
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "status": "bound",
                "lane": "api_route_lane",
                "provider": "deepseek",
                "model_id": "wbp-deepseek-v4-pro-max",
                "server_issued": True,
            },
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        packet = live_server.build_custom_codex_chatgpt_plus_api_coder_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet={
                "request_count": 2,
                "records": [
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "gpt-5.4",
                        "downstream_called": True,
                        "chatgpt_route_used": True,
                        "provider_called": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "wbp-deepseek-v4-pro-max",
                        "effective_route_model": "wbp-deepseek-v4-pro-max",
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "upstream_status": 200,
                        "response_seen": True,
                        "known_smoke_phrase_matched": True,
                        "chatgpt_route_used": False,
                        "fallback_used": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                ],
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CHATGPT_PLUS_API_ROUTE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["slot_binding_proven"])
        self.assertTrue(packet["primary_slot_bound"])
        self.assertTrue(packet["coding_slot_bound"])
        self.assertTrue(packet["dual_lane_slots_preserved"])
        self.assertTrue(packet["stable_bridge_preflight_ok"])
        self.assertTrue(packet["prompt_seen"])
        self.assertTrue(packet["chatgpt_route_observed"])
        self.assertTrue(packet["chatgpt_primary_route_observed"])
        self.assertTrue(packet["deepseek_route_observed"])
        self.assertTrue(packet["deepseek_coding_route_observed"])
        self.assertTrue(packet["coder_dispatch_proven"])
        self.assertTrue(packet["coder_work_result_proven_with_limits"])
        self.assertTrue(packet["trace_launch_packet_matches"])
        self.assertTrue(packet["trace_id_matches_launch"])
        self.assertEqual(packet["primary_provider"], "chatgpt")
        self.assertEqual(packet["coding_slot_provider"], "deepseek")
        self.assertEqual(packet["coding_slot_model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["api_only_mode_used"])
        self.assertFalse(packet["chatgpt_only_mode_used"])
        self.assertFalse(packet["response_text_counts_as_proof"])
        self.assertFalse(packet["ui_label_counts_as_proof"])
        self.assertFalse(packet["response_text_counts_as_model_truth"])

    def test_chatgpt_plus_api_coder_trace_blocks_missing_stable_preflight(self) -> None:
        launch = {
            "status": "ok",
            "launch_id": "launch-test",
            "trace_id": "trace-test",
            "execution_mode": "chatgpt_plus_api",
            "native_window_observed": True,
            "real_codex_app_launched": True,
            "stable_bridge_preflight_required": True,
            "stable_bridge_preflight_status": "blocked",
            "stable_bridge_launch_allowed": False,
            "primary_model_slot": {
                "slot_id": "primary_model_slot",
                "status": "bound",
                "lane": "codex_account_lane",
                "model_id": "gpt-5.4",
                "server_issued": True,
            },
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "status": "bound",
                "lane": "api_route_lane",
                "provider": "deepseek",
                "model_id": "wbp-deepseek-v4-pro-max",
                "server_issued": True,
            },
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        packet = live_server.build_custom_codex_chatgpt_plus_api_coder_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet={
                "request_count": 2,
                "records": [
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "gpt-5.4",
                        "chatgpt_route_used": True,
                        "provider_called": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "wbp-deepseek-v4-pro-max",
                        "effective_route_model": "wbp-deepseek-v4-pro-max",
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "upstream_status": 200,
                        "response_seen": True,
                        "known_smoke_phrase_matched": True,
                        "chatgpt_route_used": False,
                        "fallback_used": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                ],
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["stable_bridge_preflight_ok"])
        self.assertFalse(packet["slot_binding_proven"])
        self.assertFalse(packet["chatgpt_primary_route_observed"])
        self.assertFalse(packet["deepseek_coding_route_observed"])

    def test_chatgpt_plus_api_coder_trace_blocks_fallback(self) -> None:
        launch = {
            "status": "ok",
            "launch_id": "launch-test",
            "trace_id": "trace-test",
            "execution_mode": "chatgpt_plus_api",
            "native_window_observed": True,
            "real_codex_app_launched": True,
            "stable_bridge_preflight_required": True,
            "stable_bridge_preflight_status": "ok",
            "stable_bridge_launch_allowed": True,
            "primary_model_slot": {
                "slot_id": "primary_model_slot",
                "status": "bound",
                "lane": "codex_account_lane",
                "model_id": "gpt-5.4",
                "server_issued": True,
            },
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "status": "bound",
                "lane": "api_route_lane",
                "provider": "deepseek",
                "model_id": "wbp-deepseek-v4-pro-max",
                "server_issued": True,
            },
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        packet = live_server.build_custom_codex_chatgpt_plus_api_coder_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet={
                "request_count": 2,
                "records": [
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "gpt-5.4",
                        "chatgpt_route_used": True,
                        "provider_called": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "wbp-deepseek-v4-pro-max",
                        "effective_route_model": "wbp-deepseek-v4-pro-max",
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "upstream_status": 200,
                        "response_seen": True,
                        "known_smoke_phrase_matched": True,
                        "chatgpt_route_used": False,
                        "fallback_used": True,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                ],
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["fallback_used"])
        self.assertFalse(packet["coder_dispatch_proven"])

    def test_chatgpt_plus_api_coder_trace_blocks_missing_chatgpt_primary_record(self) -> None:
        launch = {
            "status": "ok",
            "launch_id": "launch-test",
            "trace_id": "trace-test",
            "execution_mode": "chatgpt_plus_api",
            "native_window_observed": True,
            "real_codex_app_launched": True,
            "stable_bridge_preflight_required": True,
            "stable_bridge_preflight_status": "ok",
            "stable_bridge_launch_allowed": True,
            "primary_model_slot": {
                "slot_id": "primary_model_slot",
                "status": "bound",
                "lane": "codex_account_lane",
                "model_id": "gpt-5.4",
                "server_issued": True,
            },
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "status": "bound",
                "lane": "api_route_lane",
                "provider": "deepseek",
                "model_id": "wbp-deepseek-v4-pro-max",
                "server_issued": True,
            },
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        packet = live_server.build_custom_codex_chatgpt_plus_api_coder_trace_packet(
            last_launch_packet=launch,
            bridge_trace_packet={
                "request_count": 1,
                "records": [
                    {
                        "launch_packet_id": "launch-test",
                        "trace_id": "trace-test",
                        "path": "/v1/responses",
                        "request_seen_after_launch": True,
                        "requested_model": "wbp-deepseek-v4-pro-max",
                        "effective_route_model": "wbp-deepseek-v4-pro-max",
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "upstream_status": 200,
                        "response_seen": True,
                        "known_smoke_phrase_matched": True,
                        "chatgpt_route_used": False,
                        "fallback_used": False,
                        "raw_prompt_recorded": False,
                        "secret_value_recorded": False,
                    },
                ],
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["prompt_seen"])
        self.assertFalse(packet["chatgpt_route_observed"])
        self.assertTrue(packet["deepseek_route_observed"])

    def test_chatgpt_plus_deepseek_file_edit_packet_requires_mixed_route_and_exact_file(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as profile_dir:
            repo_root = Path(repo_dir)
            profile_root = Path(profile_dir)
            probe_file = repo_root / ".tmp" / "mixed_mode_probe.txt"
            probe_file.parent.mkdir(parents=True)
            probe_file.write_text("WBP_CHATGPT_PLUS_DEEPSEEK_OK", encoding="utf-8")

            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    (
                        "thread-mixed",
                        str(repo_root),
                        "gpt-5.4",
                        "wbp",
                        1,
                        2,
                    ),
                )

            with sqlite3.connect(profile_root / "logs_2.sqlite") as connection:
                connection.execute(
                    "create table logs (id integer, thread_id text, feedback_log_body text)"
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        1,
                        "thread-mixed",
                        "turn model=wbp-deepseek-v4-pro-max cwd="
                        f"{repo_root}: ToolCall: exec_command .tmp/mixed_mode_probe.txt",
                    ),
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        2,
                        "thread-mixed",
                        ".tmp/mixed_mode_probe.txt success=true "
                        "model=wbp-deepseek-v4-pro-max",
                    ),
                )

            launch = {
                "status": "ok",
                "launch_id": "launch-mixed",
                "trace_id": "trace-mixed",
                "execution_mode": "chatgpt_plus_api",
                "native_window_observed": True,
                "real_codex_app_launched": True,
                "stable_bridge_preflight_required": True,
                "stable_bridge_preflight_status": "ok",
                "stable_bridge_launch_allowed": True,
                "persistent_profile_root": str(profile_root),
                "primary_model_slot": {
                    "slot_id": "primary_model_slot",
                    "status": "bound",
                    "lane": "codex_account_lane",
                    "model_id": "gpt-5.4",
                    "server_issued": True,
                },
                "coding_agent_model_slot": {
                    "slot_id": "coding_agent_model_slot",
                    "status": "bound",
                    "lane": "api_route_lane",
                    "provider": "deepseek",
                    "model_id": "wbp-deepseek-v4-pro-max",
                    "server_issued": True,
                },
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
                "original_codex_touched": False,
                "asar_touched": False,
            }
            packet = live_server.build_custom_codex_chatgpt_plus_deepseek_file_edit_packet(
                last_launch_packet=launch,
                bridge_trace_packet={
                    "request_count": 2,
                    "records": [
                        {
                            "launch_packet_id": "launch-mixed",
                            "trace_id": "trace-mixed",
                            "path": "/v1/responses",
                            "request_seen_after_launch": True,
                            "requested_model": "gpt-5.4",
                            "chatgpt_route_used": True,
                            "provider_called": False,
                            "raw_prompt_recorded": False,
                            "secret_value_recorded": False,
                        },
                        {
                            "launch_packet_id": "launch-mixed",
                            "trace_id": "trace-mixed",
                            "path": "/v1/responses",
                            "request_seen_after_launch": True,
                            "requested_model": "wbp-deepseek-v4-pro-max",
                            "effective_route_model": "wbp-deepseek-v4-pro-max",
                            "provider_called": True,
                            "provider_id": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "upstream_status": 200,
                            "response_seen": True,
                            "known_smoke_phrase_matched": True,
                            "chatgpt_route_used": False,
                            "fallback_used": False,
                            "changed_files": [".tmp/mixed_mode_probe.txt"],
                            "raw_prompt_recorded": False,
                            "secret_value_recorded": False,
                        },
                    ],
                },
                browser_payload={
                    "execution_mode": "chatgpt_plus_api",
                    "chatgpt_model_id": "gpt-5.4",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
                repo_root=repo_root,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CHATGPT_PLUS_API_CODE_EDIT_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(packet["execution_mode"], "chatgpt_plus_api")
        self.assertTrue(packet["chatgpt_primary_route_observed"])
        self.assertTrue(packet["deepseek_coding_route_observed"])
        self.assertTrue(packet["stable_bridge_preflight_ok"])
        self.assertEqual(packet["coding_slot_provider"], "deepseek")
        self.assertEqual(packet["coding_slot_model"], "wbp-deepseek-v4-pro-max")
        self.assertTrue(packet["file_created"])
        self.assertTrue(packet["file_content_exact"])
        self.assertTrue(packet["file_mutation_observed"])
        self.assertEqual(packet["changed_files"], [".tmp/mixed_mode_probe.txt"])
        self.assertTrue(packet["mutation_scope_allowed"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["chatgpt_patch_applier_used"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertFalse(packet["response_text_counts_as_proof"])
        self.assertFalse(packet["ui_label_counts_as_proof"])
        self.assertEqual(packet["mixed_route_trace_packet"]["status"], "ok")

    def test_chatgpt_plus_deepseek_file_edit_packet_blocks_extra_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as profile_dir:
            repo_root = Path(repo_dir)
            profile_root = Path(profile_dir)
            probe_file = repo_root / ".tmp" / "mixed_mode_probe.txt"
            probe_file.parent.mkdir(parents=True)
            probe_file.write_text("WBP_CHATGPT_PLUS_DEEPSEEK_OK", encoding="utf-8")

            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    ("thread-mixed", str(repo_root), "gpt-5.4", "wbp", 1, 2),
                )

            with sqlite3.connect(profile_root / "logs_2.sqlite") as connection:
                connection.execute(
                    "create table logs (id integer, thread_id text, feedback_log_body text)"
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        1,
                        "thread-mixed",
                        "turn model=wbp-deepseek-v4-pro-max cwd="
                        f"{repo_root}: ToolCall: exec_command .tmp/mixed_mode_probe.txt",
                    ),
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        2,
                        "thread-mixed",
                        ".tmp/mixed_mode_probe.txt success=true "
                        "model=wbp-deepseek-v4-pro-max",
                    ),
                )

            packet = live_server.build_custom_codex_chatgpt_plus_deepseek_file_edit_packet(
                last_launch_packet={
                    "status": "ok",
                    "launch_id": "launch-mixed",
                    "trace_id": "trace-mixed",
                    "execution_mode": "chatgpt_plus_api",
                    "native_window_observed": True,
                    "real_codex_app_launched": True,
                    "stable_bridge_preflight_required": True,
                    "stable_bridge_preflight_status": "ok",
                    "stable_bridge_launch_allowed": True,
                    "persistent_profile_root": str(profile_root),
                    "primary_model_slot": {
                        "slot_id": "primary_model_slot",
                        "status": "bound",
                        "lane": "codex_account_lane",
                        "model_id": "gpt-5.4",
                        "server_issued": True,
                    },
                    "coding_agent_model_slot": {
                        "slot_id": "coding_agent_model_slot",
                        "status": "bound",
                        "lane": "api_route_lane",
                        "provider": "deepseek",
                        "model_id": "wbp-deepseek-v4-pro-max",
                        "server_issued": True,
                    },
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                    "original_codex_touched": False,
                    "asar_touched": False,
                },
                bridge_trace_packet={
                    "request_count": 2,
                    "records": [
                        {
                            "launch_packet_id": "launch-mixed",
                            "trace_id": "trace-mixed",
                            "path": "/v1/responses",
                            "request_seen_after_launch": True,
                            "requested_model": "gpt-5.4",
                            "chatgpt_route_used": True,
                            "provider_called": False,
                            "raw_prompt_recorded": False,
                            "secret_value_recorded": False,
                        },
                        {
                            "launch_packet_id": "launch-mixed",
                            "trace_id": "trace-mixed",
                            "path": "/v1/responses",
                            "request_seen_after_launch": True,
                            "requested_model": "wbp-deepseek-v4-pro-max",
                            "effective_route_model": "wbp-deepseek-v4-pro-max",
                            "provider_called": True,
                            "provider_id": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "upstream_status": 200,
                            "response_seen": True,
                            "known_smoke_phrase_matched": True,
                            "chatgpt_route_used": False,
                            "fallback_used": False,
                            "changed_files": [".tmp/mixed_mode_probe.txt", "README.md"],
                            "raw_prompt_recorded": False,
                            "secret_value_recorded": False,
                        },
                    ],
                },
                browser_payload={
                    "execution_mode": "chatgpt_plus_api",
                    "chatgpt_model_id": "gpt-5.4",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
                repo_root=repo_root,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["changed_files"], [".tmp/mixed_mode_probe.txt", "README.md"])
        self.assertFalse(packet["mutation_scope_allowed"])
        self.assertTrue(packet["file_mutation_observed"])
        self.assertTrue(packet["chatgpt_primary_route_observed"])
        self.assertTrue(packet["deepseek_coding_route_observed"])

    def test_chatgpt_plus_deepseek_file_edit_packet_rejects_raw_backend_fields(self) -> None:
        packet = live_server.build_custom_codex_chatgpt_plus_deepseek_file_edit_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={
                "execution_mode": "chatgpt_plus_api",
                "api_model_id": "wbp-deepseek-v4-pro-max",
                "base_url": "https://example.invalid/v1",
            },
            repo_root=Path("/tmp/repo"),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("base_url", packet["forbidden_fields"])

    def test_custom_window_prompt_trace_endpoint_rejects_query_authority(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/window-prompt-trace?trace_id=browser",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["trace_id"])
        self.assertFalse(packet["browser_trace_authority"])

    def test_custom_persistent_profile_packet_separates_profile_and_session_storage(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            (session_dir / "thread.jsonl").write_text(
                "{\"type\":\"session_meta\"}\n",
                encoding="utf-8",
            )
            packet = live_server.build_custom_codex_persistent_profile_packet(
                last_launch_packet={
                    "status": "ok",
                    "profile_mode": "persistent_custom",
                    "persistent_profile_id": "wbp-custom-main",
                    "persistent_profile_root": str(profile_root),
                    "persistent_codex_home": str(profile_root),
                    "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                    "persistent_runtime_tmp_dir": "/tmp/wbp-cdx-wbp-custom-main",
                    "temp_profile_used": False,
                    "cleanup_deletes_persistent_profile_by_default": False,
                    "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                    "original_codex_touched": False,
                    "asar_touched": False,
                    "original_codex_profile_runtime_dependency": False,
                },
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["profile_final_status"],
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(
            packet["session_storage_final_status"],
            "CUSTOM_CODEX_SESSION_STORAGE_OBSERVED_WITH_LIMITS",
        )
        self.assertTrue(packet["profile_persistence_proven"])
        self.assertTrue(packet["session_storage_observed"])
        self.assertTrue(packet["session_files_observed"])
        self.assertFalse(packet["temp_profile_used"])
        self.assertFalse(packet["persistent_profile_root_is_tmp"])
        self.assertTrue(packet["persistent_runtime_tmp_dir_is_tmp"])
        self.assertFalse(packet["persistent_profile_path_exposed"])
        self.assertFalse(packet["persistent_codex_home_exposed"])
        self.assertFalse(packet["persistent_user_data_dir_exposed"])
        self.assertFalse(packet["raw_thread_content_read"])
        self.assertFalse(packet["raw_thread_content_recorded"])
        self.assertFalse(packet["history_persistence_claimed"])
        self.assertFalse(packet["full_history_restoration_claimed"])
        self.assertFalse(packet["relaunch_continuity_proven"])
        self.assertTrue(packet["profile_relaunch_required_for_strong_history_claim"])
        self.assertEqual(packet["visible_history_restore"], "not_claimed")
        self.assertFalse(packet["cleanup_deletes_persistent_profile_by_default"])
        self.assertTrue(packet["persistent_history_delete_requires_explicit_owner_action"])
        self.assertTrue(packet["cleanup_scope_runtime_tmp_only_or_deferred"])

    def test_custom_persistent_profile_packet_blocks_tmp_profile_root(self) -> None:
        packet = live_server.build_custom_codex_persistent_profile_packet(
            last_launch_packet={
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/tmp/wbp-custom-main",
                "persistent_codex_home": "/tmp/wbp-custom-main",
                "persistent_user_data_dir": "/tmp/wbp-custom-main/electron-user-data",
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["profile_final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN",
        )
        self.assertTrue(packet["persistent_profile_root_is_tmp"])
        self.assertTrue(packet["persistent_codex_home_is_tmp"])
        self.assertTrue(packet["persistent_user_data_dir_is_tmp"])
        self.assertFalse(packet["profile_persistence_proven"])

    def test_custom_persistent_profile_endpoint_rejects_browser_path_authority(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/persistent-profile?profile_path=/tmp/x",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["profile_path"])
        self.assertFalse(packet["browser_client_path_authority"])
        self.assertFalse(packet["raw_thread_content_recorded"])

    def test_custom_persistent_relaunch_profile_packet_proves_same_stable_profile(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            (session_dir / "thread.jsonl").write_text(
                "{\"type\":\"session_meta\"}\n",
                encoding="utf-8",
            )
            base_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root),
                "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                "persistent_runtime_tmp_dir": "/tmp/wbp-cdx-wbp-custom-main",
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            packet = live_server.build_custom_codex_persistent_relaunch_profile_packet(
                first_launch_packet={**base_launch, "launch_id": "first"},
                second_launch_packet={**base_launch, "launch_id": "second"},
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["profile_relaunch_proven"])
        self.assertTrue(packet["same_persistent_profile_id"])
        self.assertTrue(packet["same_persistent_codex_home"])
        self.assertTrue(packet["same_user_data_dir"])
        self.assertTrue(packet["session_storage_survived_relaunch"])
        self.assertFalse(packet["cleanup_deleted_persistent_profile"])
        self.assertNotIn("latest_session_file_relative", packet)
        self.assertNotIn("latest_session_file_size_bytes", packet)
        self.assertNotIn("latest_session_file_mtime_utc", packet)
        self.assertFalse(packet["raw_thread_content_read"])
        self.assertFalse(packet["raw_thread_content_recorded"])
        self.assertFalse(packet["visible_history_owner_confirmed"])
        self.assertFalse(packet["visible_history_restore_claimed"])

    def test_custom_persistent_relaunch_profile_packet_blocks_profile_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            first_root = Path(temp_dir) / "wbp-custom-main"
            second_root = Path(temp_dir) / "wbp-custom-next"
            first_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(first_root),
                "persistent_codex_home": str(first_root),
                "persistent_user_data_dir": str(first_root / "electron-user-data"),
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            second_launch = {
                **first_launch,
                "persistent_profile_id": "wbp-custom-next",
                "persistent_profile_root": str(second_root),
                "persistent_codex_home": str(second_root),
                "persistent_user_data_dir": str(second_root / "electron-user-data"),
            }
            packet = live_server.build_custom_codex_persistent_relaunch_profile_packet(
                first_launch_packet=first_launch,
                second_launch_packet=second_launch,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_NOT_PROVEN",
        )
        self.assertFalse(packet["profile_relaunch_proven"])
        self.assertFalse(packet["same_persistent_profile_id"])
        self.assertFalse(packet["same_persistent_codex_home"])
        self.assertFalse(packet["same_user_data_dir"])

    def test_custom_persistent_relaunch_profile_packet_allows_no_session_storage_limit(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            profile_root.mkdir(parents=True)
            base_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root),
                "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            packet = live_server.build_custom_codex_persistent_relaunch_profile_packet(
                first_launch_packet=dict(base_launch),
                second_launch_packet=dict(base_launch),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_PROVEN_SESSION_STORAGE_NOT_OBSERVED",
        )
        self.assertTrue(packet["profile_relaunch_proven"])
        self.assertFalse(packet["session_storage_survived_relaunch"])

    def test_custom_persistent_relaunch_profile_endpoint_rejects_browser_path_authority(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with NO_PROXY_OPENER.open(
                f"{base}/api/codex/custom/persistent-relaunch-profile?CODEX_HOME=/tmp/x",
                timeout=2,
            ) as response:
                packet = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["CODEX_HOME"])
        self.assertFalse(packet["browser_client_path_authority"])

    def test_custom_stable_profile_history_persistence_packet_proves_marker_after_relaunch(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            marker = "WBP_STABLE_HISTORY_MARKER"
            (session_dir / "thread.jsonl").write_text(
                json.dumps({"type": "message", "text": marker}) + "\n",
                encoding="utf-8",
            )
            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    ("thread-stable", str(ROOT), "gpt-5.4", "wbp", 1, 2),
                )
            base_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root),
                "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                "persistent_runtime_tmp_dir": "/tmp/wbp-cdx-wbp-custom-main",
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            before = live_server.build_custom_codex_stable_profile_history_before_snapshot_packet(
                last_launch_packet={**base_launch, "launch_id": "first"},
                browser_payload={"history_marker": marker},
            )
            packet = live_server.build_custom_codex_stable_profile_history_persistence_packet(
                first_launch_packet={**base_launch, "launch_id": "first"},
                second_launch_packet={**base_launch, "launch_id": "second"},
                before_history_snapshot=before["snapshot"],
                browser_payload={"history_marker": marker},
            )

        self.assertEqual(before["status"], "ok")
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_STABLE_PROFILE_HISTORY_PERSISTENCE_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["stable_profile_used"])
        self.assertFalse(packet["temporary_profile_used"])
        self.assertTrue(packet["same_profile_after_relaunch"])
        self.assertGreater(packet["thread_count_before"], 0)
        self.assertGreaterEqual(packet["thread_count_after"], packet["thread_count_before"])
        self.assertTrue(packet["history_marker_seen_before"])
        self.assertTrue(packet["history_marker_seen_after"])
        self.assertTrue(packet["visible_history_restored"])
        self.assertFalse(packet["browser_profile_authority"])
        self.assertFalse(packet["stable_profile_root_exposed"])
        self.assertFalse(packet["raw_thread_content_read"])
        self.assertFalse(packet["raw_thread_content_recorded"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])

    def test_custom_stable_profile_history_persistence_requires_before_snapshot(self) -> None:
        packet = live_server.build_custom_codex_stable_profile_history_persistence_packet(
            first_launch_packet={"status": "ok"},
            second_launch_packet={"status": "ok"},
            before_history_snapshot=None,
            browser_payload={"history_marker": "WBP_STABLE_HISTORY_MARKER"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "STABLE_PROFILE_HISTORY_BEFORE_SNAPSHOT_REQUIRED",
        )
        self.assertFalse(packet["visible_history_restored"])

    def test_custom_stable_profile_history_persistence_blocks_profile_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            first_root = Path(temp_dir) / "wbp-custom-main"
            second_root = Path(temp_dir) / "wbp-custom-next"
            for root in (first_root, second_root):
                session_dir = root / "sessions" / "2026"
                session_dir.mkdir(parents=True)
                (session_dir / "thread.jsonl").write_text(
                    "WBP_STABLE_HISTORY_MARKER\n",
                    encoding="utf-8",
                )
                with sqlite3.connect(root / "state_5.sqlite") as connection:
                    connection.execute(
                        "create table threads (id text, cwd text, model text, "
                        "model_provider text, created_at integer, updated_at integer)"
                    )
                    connection.execute(
                        "insert into threads values (?, ?, ?, ?, ?, ?)",
                        ("thread-stable", str(ROOT), "gpt-5.4", "wbp", 1, 2),
                    )
            first_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(first_root),
                "persistent_codex_home": str(first_root),
                "persistent_user_data_dir": str(first_root / "electron-user-data"),
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            second_launch = {
                **first_launch,
                "persistent_profile_id": "wbp-custom-next",
                "persistent_profile_root": str(second_root),
                "persistent_codex_home": str(second_root),
                "persistent_user_data_dir": str(second_root / "electron-user-data"),
            }
            before = live_server.build_custom_codex_stable_profile_history_before_snapshot_packet(
                last_launch_packet=first_launch,
                browser_payload={"history_marker": "WBP_STABLE_HISTORY_MARKER"},
            )
            packet = live_server.build_custom_codex_stable_profile_history_persistence_packet(
                first_launch_packet=first_launch,
                second_launch_packet=second_launch,
                before_history_snapshot=before["snapshot"],
                browser_payload={"history_marker": "WBP_STABLE_HISTORY_MARKER"},
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["same_profile_after_relaunch"])
        self.assertTrue(packet["history_marker_seen_before"])
        self.assertTrue(packet["history_marker_seen_after"])

    def test_custom_stable_profile_history_persistence_rejects_browser_profile_fields(self) -> None:
        packet = live_server.build_custom_codex_stable_profile_history_persistence_packet(
            first_launch_packet={},
            second_launch_packet={},
            before_history_snapshot={},
            browser_payload={
                "history_marker": "WBP_STABLE_HISTORY_MARKER",
                "CODEX_HOME": "/tmp/browser-codex-home",
                "profile_path": "/tmp/browser-profile",
            },
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("CODEX_HOME", packet["forbidden_fields"])
        self.assertIn("profile_path", packet["forbidden_fields"])
        self.assertFalse(packet["browser_profile_authority"])

    def test_custom_persistent_profile_history_proof_separates_profile_and_history_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            marker = "WBP_STABLE_HISTORY_MARKER"
            (session_dir / "thread.jsonl").write_text(
                json.dumps({"type": "message", "text": marker}) + "\n",
                encoding="utf-8",
            )
            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    ("thread-stable", str(ROOT), "gpt-5.4", "wbp", 1, 2),
                )
            base_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root),
                "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                "persistent_runtime_tmp_dir": "/tmp/wbp-cdx-wbp-custom-main",
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            before = live_server.build_custom_codex_stable_profile_history_before_snapshot_packet(
                last_launch_packet={**base_launch, "launch_id": "first"},
                browser_payload={"history_marker": marker},
            )
            packet = live_server.build_custom_codex_persistent_profile_history_proof_packet(
                first_launch_packet={**base_launch, "launch_id": "first"},
                second_launch_packet={**base_launch, "launch_id": "second"},
                before_history_snapshot=before["snapshot"],
                browser_payload={"history_marker": marker},
            )

        self.assertEqual(before["status"], "ok")
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_HISTORY_RESTORE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(
            packet["profile_final_status"],
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(
            packet["history_final_status"],
            "CUSTOM_CODEX_HISTORY_RESTORE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(packet["profile_id"], "wbp-custom-main")
        self.assertTrue(packet["persistent_profile_used"])
        self.assertFalse(packet["profile_path_is_tmp"])
        self.assertTrue(packet["same_profile_root"])
        self.assertTrue(packet["history_store_seen"])
        self.assertTrue(packet["thread_store_seen"])
        self.assertTrue(packet["previous_thread_seen_after_relaunch"])
        self.assertFalse(packet["history_reset_detected"])
        self.assertFalse(packet["owner_visible_relaunch_required"])
        self.assertFalse(packet["original_codex_profile_touched"])
        self.assertFalse(packet["asar_touched"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["ui_label_counts_as_proof"])
        self.assertFalse(packet["model_response_counts_as_proof"])
        self.assertEqual(packet["profile_root"], "server_owned_redacted")
        self.assertEqual(packet["first_launch_profile_root"], "server_owned_redacted")
        self.assertEqual(packet["second_launch_profile_root"], "server_owned_redacted")
        self.assertNotIn(str(profile_root), json.dumps(packet, ensure_ascii=False))

    def test_custom_persistent_profile_history_proof_can_close_profile_without_history(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            (session_dir / "thread.jsonl").write_text(
                "{\"type\":\"session_meta\"}\n",
                encoding="utf-8",
            )
            base_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root),
                "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            packet = live_server.build_custom_codex_persistent_profile_history_proof_packet(
                first_launch_packet={**base_launch, "launch_id": "first"},
                second_launch_packet={**base_launch, "launch_id": "second"},
                before_history_snapshot=None,
                browser_payload={"history_marker": "WBP_STABLE_HISTORY_MARKER"},
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(
            packet["profile_final_status"],
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(
            packet["history_final_status"],
            "CUSTOM_CODEX_HISTORY_RESTORE_OWNER_RELAUNCH_REQUIRED",
        )
        self.assertTrue(packet["persistent_profile_used"])
        self.assertFalse(packet["history_restore_proven"])
        self.assertTrue(packet["owner_visible_relaunch_required"])
        self.assertTrue(packet["history_reset_detected"])
        self.assertFalse(packet["previous_thread_seen_after_relaunch"])

    def test_custom_persistent_profile_history_proof_blocks_tmp_profile_root(self) -> None:
        base_launch = {
            "status": "ok",
            "profile_mode": "persistent_custom",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": "/tmp/wbp-custom-main",
            "persistent_codex_home": "/tmp/wbp-custom-main",
            "persistent_user_data_dir": "/tmp/wbp-custom-main/electron-user-data",
            "temp_profile_used": False,
            "cleanup_deletes_persistent_profile_by_default": False,
            "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
            "original_codex_touched": False,
            "asar_touched": False,
            "original_codex_profile_runtime_dependency": False,
        }
        packet = live_server.build_custom_codex_persistent_profile_history_proof_packet(
            first_launch_packet={**base_launch, "launch_id": "first"},
            second_launch_packet={**base_launch, "launch_id": "second"},
            before_history_snapshot={"thread_count": 1, "history_marker_seen": True},
            browser_payload={"history_marker": "WBP_STABLE_HISTORY_MARKER"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["profile_final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN",
        )
        self.assertTrue(packet["profile_path_is_tmp"])
        self.assertFalse(packet["persistent_profile_used"])
        self.assertFalse(packet["history_restore_proven"])

    def test_custom_persistent_profile_history_proof_blocks_profile_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            first_root = Path(temp_dir) / "wbp-custom-main"
            second_root = Path(temp_dir) / "wbp-custom-next"
            first_root.mkdir(parents=True)
            second_root.mkdir(parents=True)
            first_launch = {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(first_root),
                "persistent_codex_home": str(first_root),
                "persistent_user_data_dir": str(first_root / "electron-user-data"),
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            second_launch = {
                **first_launch,
                "persistent_profile_id": "wbp-custom-next",
                "persistent_profile_root": str(second_root),
                "persistent_codex_home": str(second_root),
                "persistent_user_data_dir": str(second_root / "electron-user-data"),
            }
            packet = live_server.build_custom_codex_persistent_profile_history_proof_packet(
                first_launch_packet=first_launch,
                second_launch_packet=second_launch,
                before_history_snapshot={"thread_count": 1, "history_marker_seen": True},
                browser_payload={"history_marker": "WBP_STABLE_HISTORY_MARKER"},
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["same_profile_root"])
        self.assertFalse(packet["persistent_profile_used"])
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN",
        )

    def test_custom_persistent_profile_history_proof_rejects_browser_path_authority(self) -> None:
        packet = live_server.build_custom_codex_persistent_profile_history_proof_packet(
            first_launch_packet={},
            second_launch_packet={},
            before_history_snapshot={},
            browser_payload={
                "history_marker": "WBP_STABLE_HISTORY_MARKER",
                "CODEX_HOME": "/tmp/browser-codex-home",
            },
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("CODEX_HOME", packet["forbidden_fields"])
        self.assertFalse(packet["browser_profile_authority"])

    def test_custom_persistent_relaunch_profile_endpoint_compares_two_native_launches(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            profile_root = Path(temp_dir) / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026"
            session_dir.mkdir(parents=True)
            (session_dir / "thread.jsonl").write_text(
                "{\"type\":\"session_meta\"}\n",
                encoding="utf-8",
            )
            base_native_packet = {
                "schema_version": 1,
                "captured_at_utc": "2026-05-30T00:00:00Z",
                "mode_id": "codex_custom",
                "status": "ok",
                "machine_error_code": "OK",
                "running_status": True,
                "process_started": True,
                "profile_mode": "persistent_custom",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": str(profile_root),
                "persistent_codex_home": str(profile_root),
                "persistent_user_data_dir": str(profile_root / "electron-user-data"),
                "persistent_runtime_tmp_dir": "/tmp/wbp-cdx-wbp-custom-main",
                "temp_profile_used": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
                "original_codex_touched": False,
                "asar_touched": False,
                "original_codex_profile_runtime_dependency": False,
            }
            payloads = live_payloads()
            payloads[("status", "--json")] = status_packet(
                claim_gate={"status": "ok"},
                pool_summary={"selected_backend_ids": ["acct-active"]},
                auth_pool_hygiene={
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            )
            payloads[("accounts", "list", "--json")] = accounts_packet(
                accounts=[
                    account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")
                ]
            )
            with (
                mock.patch.object(
                    live_server,
                    "launch_custom_native_app_packet",
                    side_effect=[
                        {**base_native_packet, "launch_id": "first"},
                        {**base_native_packet, "launch_id": "second"},
                    ],
                ),
                mock.patch.object(
                    live_server.OperatorSurfaceSession,
                    "status_payload",
                    return_value={
                        "status": {"configured_model": "gpt-5.3-codex"},
                        "claim_gate": {"status": "ok"},
                        "models": {
                            "model_ids": ["gpt-5.3-codex"],
                            "server_issued": True,
                        },
                    },
                ),
                mock.patch.object(
                    live_server,
                    "build_api_connections_readonly_snapshot",
                    return_value={
                        "status": "ok",
                        "source": "api_connections_readonly",
                        "primary_truth_ok": True,
                        "routes": [],
                    },
                ),
                mock.patch.object(
                    live_server,
                    "collect_codex_process_inventory",
                    return_value={
                        "custom_process_count": 0,
                        "default_process_count": 0,
                        "custom_process_lines": [],
                    },
                ),
            ):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        action_phase=live_server.FULL_ACTION_PHASE,
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    first = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/native-launch",
                            {"model_id": "gpt-5.3-codex"},
                        )
                    )
                    second = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/native-launch",
                            {"model_id": "gpt-5.3-codex"},
                        )
                    )
                    packet = json.loads(
                        fetch(f"{base}/api/codex/custom/persistent-relaunch-profile")
                    )
                    confirmed = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/visible-history/relaunch-owner-confirmation",
                            {
                                "custom_codex_open": True,
                                "old_chat_visible": True,
                                "chat_not_empty": True,
                                "not_original_codex": True,
                                "owner_confirmed_after_relaunch": True,
                                "raw_thread_content_not_recorded": True,
                                "smoke_phrase_required": False,
                                "smoke_phrase_visible": False,
                            },
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["profile_relaunch_proven"])
        self.assertTrue(packet["session_storage_survived_relaunch"])
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(confirmed["status"], "ok")
        self.assertEqual(
            confirmed["final_status"],
            "CUSTOM_CODEX_VISIBLE_HISTORY_RELAUNCH_OWNER_CONFIRMED_WITH_LIMITS",
        )
        self.assertTrue(confirmed["profile_relaunch_proven"])
        self.assertTrue(confirmed["owner_confirmed_old_chat_visible"])
        self.assertFalse(confirmed["raw_thread_content_recorded"])
        self.assertFalse(confirmed["all_history_restored_claimed"])

    def test_custom_native_launch_rejects_mixed_legacy_model_and_execution_mode_fields(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(
            "wbp-deepseek-v4-pro-max",
            enabled=True,
        )

        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ),
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                        }
                    ],
                },
            ),
            mock.patch.object(live_server, "launch_custom_native_app_packet") as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "model_id": "gpt-5.3-codex",
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(
            rejected["machine_error_code"],
            "CUSTOM_NATIVE_LAUNCH_AMBIGUOUS_MODEL_FIELDS",
        )
        self.assertFalse(rejected["fallback_used"])
        self.assertFalse(rejected["model_auto_selected"])
        launch_native.assert_not_called()

    def test_custom_native_launch_ui_action_rejects_browser_owned_route_field(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                action_phase=live_server.FULL_ACTION_PHASE,
                owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            rejected = json.loads(
                post_json(
                    f"{base}/api/action",
                    {"ui_action": "launch_custom_client_native", "route_id": "wbp-route"},
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(rejected["status"], "integration_failure")
        self.assertEqual(rejected["disabled_reason_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(rejected["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(rejected["action_claim_scope"], "blocked")
        self.assertIn("route_id", rejected["result"]["human_message"])

    def test_custom_native_launch_ui_action_passes_selected_execution_fields(self) -> None:
        captured_payload: dict[str, object] = {}

        def fake_launch(payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
            captured_payload.update(payload)
            return {
                "schema_version": 1,
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "Custom launch packet accepted.",
                "next_action": "prompt",
                "selected_model": payload.get("api_model_id"),
                "browser_raw_backend_authority_widened": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }

        with mock.patch.object(
            live_server,
            "_launch_custom_native_codex_packet",
            side_effect=fake_launch,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(live_payloads()),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                accepted = json.loads(
                    post_json(
                        f"{base}/api/action",
                        {
                            "ui_action": "launch_custom_client_native",
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(accepted["status"], "ok")
        self.assertEqual(accepted["result"]["status"], "ok")
        self.assertEqual(
            captured_payload,
            {
                "execution_mode": "api_only",
                "api_model_id": "wbp-deepseek-v4-pro-max",
                "api_reasoning_option_id": "provider_declared_max",
            },
        )
        self.assertNotIn("base_url", captured_payload)
        self.assertNotIn("api_key", captured_payload)
        self.assertNotIn("secret_ref", captured_payload)

    def test_show_custom_native_window_ui_action_returns_window_packet(self) -> None:
        with mock.patch.object(
            live_server,
            "show_custom_native_window_packet",
            return_value={
                "schema_version": 1,
                "packet_kind": "custom_codex_show_window",
                "status": "ok",
                "machine_error_code": "OK",
                "custom_process_pid": 222,
                "custom_window_visible": True,
                "custom_window_frontmost": True,
                "native_app_usable": True,
                "input_capable_ui_observed": True,
                "native_app_usability_source": "input_capable_ui",
                "original_codex_touched": False,
                "asar_touched": False,
            },
        ) as show_window:
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(live_payloads()),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                accepted = json.loads(
                    post_json(
                        f"{base}/api/action",
                        {"ui_action": "show_custom_client_native"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(accepted["status"], "ok")
        self.assertEqual(accepted["result"]["machine_error_code"], "OK")
        self.assertTrue(accepted["result"]["data"]["custom_window_visible"])
        self.assertTrue(accepted["result"]["data"]["native_app_usable"])
        self.assertFalse(accepted["result"]["data"]["original_codex_touched"])
        self.assertFalse(accepted["result"]["data"]["asar_touched"])
        show_window.assert_called_once()

    def test_show_custom_native_window_endpoint_returns_packet(self) -> None:
        with mock.patch.object(
            live_server,
            "show_custom_native_window_packet",
            return_value={
                "schema_version": 1,
                "packet_kind": "custom_codex_show_window",
                "status": "ok",
                "machine_error_code": "OK",
                "custom_process_pid": 222,
                "custom_window_visible": True,
                "custom_window_frontmost": True,
                "native_app_usable": True,
                "input_capable_ui_observed": True,
                "native_app_usability_source": "input_capable_ui",
                "original_codex_touched": False,
                "asar_touched": False,
            },
        ) as show_window:
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(live_payloads()),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(f"{base}/api/codex/custom/show-window", {})
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["native_app_usable"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        show_window.assert_called_once()

    def test_custom_native_launch_endpoint_rejects_raw_browser_backend_fields(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                action_phase=live_server.FULL_ACTION_PHASE,
                owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            rejected = json.loads(
                post_json(
                    f"{base}/api/codex/custom/native-launch",
                    {
                        "execution_mode": "api_only",
                        "api_model_id": "wbp-deepseek-v4-pro-max",
                        "base_url": "https://browser.invalid/v1",
                        "api_key": "browser-key",
                        "secret_ref": "BROWSER_SECRET_REF",
                        "route_id": "browser-route",
                        "CODEX_HOME": "/tmp/browser-codex-home",
                        "profile_path": "/tmp/browser-profile",
                        "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                    },
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("base_url", rejected["forbidden_fields"])
        self.assertIn("api_key", rejected["forbidden_fields"])
        self.assertIn("secret_ref", rejected["forbidden_fields"])
        self.assertIn("route_id", rejected["forbidden_fields"])
        self.assertIn("CODEX_HOME", rejected["forbidden_fields"])
        self.assertIn("profile_path", rejected["forbidden_fields"])
        self.assertIn("route_config.secret_ref", rejected["forbidden_fields"])
        self.assertTrue(rejected["browser_raw_backend_authority_widened"])
        self.assertFalse(rejected["raw_backend_details_exposed"])
        self.assertFalse(rejected["secret_value_exposed"])
        self.assertFalse(rejected["original_codex_touched"])
        self.assertFalse(rejected["asar_touched"])

    def test_custom_native_launch_preflight_rejects_raw_browser_backend_fields(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(
                action_phase=live_server.FULL_ACTION_PHASE,
                owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            rejected = json.loads(
                post_json(
                    f"{base}/api/codex/custom/native-launch-preflight",
                    {
                        "execution_mode": "api_only",
                        "api_model_id": "wbp-deepseek-v4-pro-max",
                        "base_url": "https://browser.invalid/v1",
                        "api_key": "browser-key",
                        "secret_ref": "BROWSER_SECRET_REF",
                        "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                    },
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("base_url", rejected["forbidden_fields"])
        self.assertIn("api_key", rejected["forbidden_fields"])
        self.assertIn("secret_ref", rejected["forbidden_fields"])
        self.assertIn("route_config.secret_ref", rejected["forbidden_fields"])
        self.assertFalse(rejected["new_launch_started"])
        self.assertFalse(rejected["show_window_attempted"])
        self.assertFalse(rejected["live_provider_called"])
        self.assertFalse(rejected["raw_backend_details_exposed"])
        self.assertFalse(rejected["secret_value_exposed"])
        self.assertFalse(rejected["original_codex_touched"])
        self.assertFalse(rejected["asar_touched"])

    def test_custom_native_launch_preflight_endpoint_accepts_owner_authorized_api_route(self) -> None:
        payloads = live_payloads()
        with (
            mock.patch.object(
                live_server.OperatorSurfaceSession,
                "status_payload",
                return_value={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
            ) as status_payload,
            mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v3",
                            "display_name": "DeepSeek V3",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-chat",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
            ) as api_snapshot,
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(live_server, "_loopback_port_accepts_connection", return_value=False),
            mock.patch.object(live_server, "launch_custom_native_app_packet") as launch_native,
        ):
            runner = MappingRunner(payloads)
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=runner,
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase=(
                        "разрешаю тебе любые законные действия в рамках разработки проекта"
                    ),
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch-preflight",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "custom_native_launch_preflight")
        self.assertTrue(packet["owner_authorization_phrase_present"])
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v3")
        self.assertTrue(packet["route_selected"])
        self.assertEqual(packet["bridge_status"], "not_started_or_down")
        self.assertEqual(packet["next_action"], "launch_custom_codex_to_create_bridge")
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["show_window_attempted"])
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        self.assertEqual(
            packet["final_status"],
            "QUICK_START_LIVE_BRIDGE_AND_WINDOW_REUSE_GUARDED_WITH_LIMITS",
        )
        status_payload.assert_called_once()
        api_snapshot.assert_called_once()
        launch_native.assert_not_called()
        self.assertIn(("external-models", "routes", "list", "--json"), runner.calls)
        self.assertNotIn(("healthcheck", "--json"), runner.calls)

    def test_custom_native_launch_preflight_classifies_window_bridge_and_model_truth_boundaries(self) -> None:
        with mock.patch.object(live_server, "_loopback_port_accepts_connection", return_value=False):
            packet = live_server._custom_native_launch_preflight_packet(
                {
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                },
                owner_authorized=True,
                operator_status={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
                api_snapshot={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                        }
                    ],
                },
                external_routes_packet=routes_list_packet("wbp-deepseek-v4-pro-max"),
                native_bridge_lease=None,
                last_launch_packet=None,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["packet_kind"], "custom_native_launch_preflight")
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(packet["bridge_status"], "not_started_or_down")
        self.assertFalse(packet["show_window_attempted"])
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["visible_window_counts_as_model_truth"])
        self.assertFalse(packet["bridge_alive_counts_as_model_truth"])
        self.assertFalse(packet["response_text_counts_as_route_truth"])
        self.assertTrue(packet["launch_packet_is_truth_source"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_path_exposed"])
        self.assertEqual(
            packet["final_status"],
            "QUICK_START_LIVE_BRIDGE_AND_WINDOW_REUSE_GUARDED_WITH_LIMITS",
        )

    def test_custom_native_launch_preflight_routes_chatgpt_plus_api_bridge_from_coding_slot(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        with (
            mock.patch.object(live_server, "_loopback_port_accepts_connection", return_value=False),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
        ):
            packet = live_server._custom_native_launch_preflight_packet(
                {
                    "execution_mode": "chatgpt_plus_api",
                    "chatgpt_model_id": "gpt-5.3-codex",
                    "api_model_id": route_id,
                    "api_reasoning_option_id": "provider_declared_max",
                },
                owner_authorized=True,
                operator_status={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
                api_snapshot={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": route_id,
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                            "thinking": {
                                "type": "enabled",
                                "reasoning_effort": "max",
                            },
                        }
                    ],
                },
                external_routes_packet=routes_list_packet(route_id),
                native_bridge_lease=None,
                last_launch_packet=None,
                runtime_health_result={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "human_message": "Healthcheck passed.",
                    "next_action": "none",
                    "packet": healthcheck_ok_packet(),
                },
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["execution_mode"], "chatgpt_plus_api")
        self.assertEqual(packet["selected_model"], "gpt-5.3-codex")
        self.assertEqual(packet["launch_model_id"], "gpt-5.3-codex")
        self.assertEqual(packet["route_model_id"], route_id)
        self.assertEqual(packet["selection_packet"]["primary_model_slot"]["model_id"], "gpt-5.3-codex")
        self.assertEqual(packet["selection_packet"]["coding_agent_model_slot"]["model_id"], route_id)
        self.assertTrue(packet["route_selected"])
        self.assertTrue(packet["bridge_required"])
        self.assertFalse(packet["bridge_alive"])
        self.assertEqual(packet["bridge_status"], "not_started_or_down")
        self.assertEqual(packet["next_action"], "launch_custom_codex_to_create_bridge")
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])

    def test_custom_native_launch_preflight_marks_existing_window_reuse_only_when_config_matches(self) -> None:
        with mock.patch.object(
            live_server,
            "collect_codex_process_inventory",
            return_value={
                "custom_process_count": 1,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"],
            },
        ):
            packet = live_server._custom_native_launch_preflight_packet(
                {
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                },
                owner_authorized=True,
                operator_status={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
                api_snapshot={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": "wbp-deepseek-v4-pro-max",
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                        }
                    ],
                },
                external_routes_packet=routes_list_packet("wbp-deepseek-v4-pro-max"),
                native_bridge_lease=None,
                last_launch_packet={
                    "status": "ok",
                    "execution_mode": "api_only",
                    "chatgpt_model_id": "",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "catalog_default",
                    "selected_model": "wbp-deepseek-v4-pro-max",
                },
            )

        self.assertTrue(packet["custom_process_observed"])
        self.assertEqual(packet["config_status"], "matches_last_launch")
        self.assertTrue(packet["selection_matches_last_launch"])
        self.assertTrue(packet["existing_window_reuse_admissible"])
        self.assertFalse(packet["new_launch_required"])
        self.assertFalse(packet["raw_process_lines_exposed"])
        self.assertFalse(packet["raw_path_exposed"])

    def test_custom_native_launch_preflight_marks_owner_authorized_relaunch_when_config_changes(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        with mock.patch.object(
            live_server,
            "collect_codex_process_inventory",
            return_value={
                "custom_process_count": 1,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"],
            },
        ), mock.patch.object(
            live_server,
            "_custom_native_launch_mode_selection_packet",
            return_value={
                "status": "ok",
                "execution_mode": "api_only",
                "api_model_id": route_id,
                "api_reasoning_option_id": "provider_declared_high",
                "chatgpt_model_id": "",
                "primary_model_slot": {
                    "slot_id": "primary_model_slot",
                    "model_id": route_id,
                },
                "coding_agent_model_slot": {
                    "slot_id": "coding_agent_model_slot",
                    "model_id": route_id,
                },
                "chatgpt_line_used_as_executor": False,
                "api_line_used_as_executor": True,
                "api_only_calls_chatgpt": False,
                "chatgpt_only_calls_api": False,
                "server_issued_catalog_used": True,
            },
        ):
            packet = live_server._custom_native_launch_preflight_packet(
                {
                    "execution_mode": "api_only",
                    "api_model_id": route_id,
                    "api_reasoning_option_id": "provider_declared_high",
                },
                owner_authorized=True,
                operator_status={
                    "status": {"configured_model": "gpt-5.3-codex"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
                api_snapshot={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": route_id,
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                        }
                    ],
                },
                external_routes_packet=routes_list_packet(route_id),
                native_bridge_lease=None,
                last_launch_packet={
                    "status": "ok",
                    "execution_mode": "api_only",
                    "chatgpt_model_id": "",
                    "api_model_id": route_id,
                    "api_reasoning_option_id": "provider_declared_max",
                    "selected_model": route_id,
                },
            )

        self.assertTrue(packet["custom_process_observed"])
        self.assertEqual(packet["config_status"], "changed")
        self.assertFalse(packet["selection_matches_last_launch"])
        self.assertFalse(packet["existing_window_reuse_admissible"])
        self.assertTrue(packet["existing_window_relaunch_admissible"])
        self.assertTrue(packet["new_launch_required"])
        self.assertEqual(packet["next_action"], "relaunch_custom_codex_with_new_selection")
        self.assertTrue(packet["launch_packet_is_truth_source"])
        self.assertFalse(packet["visible_window_counts_as_model_truth"])
        self.assertFalse(packet["bridge_alive_counts_as_model_truth"])
        self.assertFalse(packet["response_text_counts_as_route_truth"])
        self.assertFalse(packet["raw_process_lines_exposed"])
        self.assertFalse(packet["raw_path_exposed"])

    def test_custom_native_launch_preflight_allows_relaunch_after_proven_window_with_blocked_runtime_proof(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        with mock.patch.object(
            live_server,
            "collect_codex_process_inventory",
            return_value={
                "custom_process_count": 1,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"],
            },
        ), mock.patch.object(
            live_server,
            "_custom_native_launch_mode_selection_packet",
            return_value={
                "status": "ok",
                "execution_mode": "api_only",
                "api_model_id": route_id,
                "api_reasoning_option_id": "catalog_default",
                "chatgpt_model_id": "",
                "primary_model_slot": {
                    "slot_id": "primary_model_slot",
                    "model_id": route_id,
                },
                "coding_agent_model_slot": {
                    "slot_id": "coding_agent_model_slot",
                    "model_id": route_id,
                },
                "chatgpt_line_used_as_executor": False,
                "api_line_used_as_executor": True,
                "api_only_calls_chatgpt": False,
                "chatgpt_only_calls_api": False,
                "server_issued_catalog_used": True,
            },
        ):
            packet = live_server._custom_native_launch_preflight_packet(
                {
                    "execution_mode": "api_only",
                    "api_model_id": route_id,
                    "api_reasoning_option_id": "catalog_default",
                },
                owner_authorized=True,
                operator_status={
                    "status": {"configured_model": "codex-auto-review"},
                    "claim_gate": {"status": "ok"},
                    "models": {"model_ids": ["codex-auto-review"], "server_issued": True},
                },
                api_snapshot={
                    "status": "ok",
                    "source": "api_connections_readonly",
                    "primary_truth_ok": True,
                    "routes": [
                        {
                            "route_id": route_id,
                            "display_name": "DeepSeek V4 Pro · Максимум",
                            "provider": "deepseek",
                            "upstream_model": "deepseek-v4-pro",
                            "enabled": True,
                            "selection_enabled": True,
                            "secret_ref": "DEEPSEEK_API_KEY",
                        }
                    ],
                },
                external_routes_packet=routes_list_packet(route_id),
                native_bridge_lease=None,
                last_launch_packet={
                    "status": "blocked",
                    "machine_error_code": "CUSTOM_NATIVE_WINDOW_NOT_PROVEN",
                    "mode_id": "codex_custom",
                    "execution_mode": "chatgpt_only",
                    "chatgpt_model_id": "codex-auto-review",
                    "api_model_id": "",
                    "api_reasoning_option_id": "",
                    "selected_model": "codex-auto-review",
                    "owner_authorization_phrase_present": True,
                    "process_started": True,
                    "native_window_observed": True,
                    "native_app_usable": True,
                    "current_codex_touched": False,
                    "original_codex_touched": False,
                    "asar_touched": False,
                    "browser_raw_backend_authority_widened": False,
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                },
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["config_status"], "changed")
        self.assertFalse(packet["last_launch_packet_status_ok"])
        self.assertTrue(packet["last_launch_packet_relaunch_admissible"])
        self.assertFalse(packet["selection_matches_last_launch"])
        self.assertFalse(packet["existing_window_reuse_admissible"])
        self.assertTrue(packet["existing_window_relaunch_admissible"])
        self.assertEqual(packet["next_action"], "relaunch_custom_codex_with_new_selection")
        self.assertFalse(packet["visible_window_counts_as_model_truth"])
        self.assertFalse(packet["response_text_counts_as_route_truth"])

    def test_custom_native_launch_endpoint_reuses_matching_existing_window_without_new_launch(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(route_id)
        inventory_calls = {"count": 0}

        def fake_inventory(*_: object, **__: object) -> dict[str, object]:
            inventory_calls["count"] += 1
            process_count = 0 if inventory_calls["count"] == 1 else 1
            return {
                "custom_process_count": process_count,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"] if process_count else [],
            }

        execution_packet = {
            "status": "ok",
            "execution_mode": "api_only",
            "api_model_id": route_id,
            "api_reasoning_option_id": "provider_declared_max",
            "chatgpt_model_id": "",
            "primary_model_slot": {"slot_id": "primary_model_slot", "model_id": route_id},
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "model_id": route_id,
            },
            "chatgpt_line_used_as_executor": False,
            "api_line_used_as_executor": True,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "server_issued_catalog_used": True,
        }

        def fake_launch(**_: object) -> dict[str, object]:
            return {
                "schema_version": 1,
                "captured_at_utc": "2026-05-30T00:00:00Z",
                "mode_id": "codex_custom",
                "status": "ok",
                "machine_error_code": "OK",
                "owner_authorization_phrase_present": True,
                "running_status": True,
                "process_started": True,
                "new_launch_started": True,
                "expected_custom_identity_observed": True,
                "native_window_observed": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "temp_profile_used": False,
                "current_codex_touched": False,
                "original_codex_touched": False,
                "asar_touched": False,
                "browser_raw_backend_authority_widened": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }

        with (
            mock.patch.object(live_server, "collect_codex_process_inventory", side_effect=fake_inventory),
            mock.patch.object(
                live_server,
                "_custom_native_launch_mode_selection_packet",
                return_value=execution_packet,
            ),
            mock.patch.object(
                live_server,
                "build_custom_model_registry_packet",
                return_value={
                    "endpoint": "http://127.0.0.1:8318/v1",
                    "available_models": [
                        {"lane": "wbp_api", "model_id": route_id, "selection_enabled": True}
                    ],
                },
            ),
            mock.patch.object(live_server, "extract_local_api_key", return_value="sk-local"),
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-deepseek",
            ),
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:8319/v1",
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=self.stable_bridge_preflight_ok_packet(),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(live_server, "launch_custom_native_app_packet", side_effect=fake_launch) as launch,
            mock.patch.object(
                live_server,
                "show_custom_native_window_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_show_window",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "custom_window_visible": True,
                    "custom_window_frontmost": True,
                    "native_app_usable": True,
                    "input_capable_ui_observed": True,
                    "native_app_usability_source": "input_capable_ui",
                    "original_codex_touched": False,
                    "asar_touched": False,
                },
            ) as show_window,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                launch_payload = {
                    "execution_mode": "api_only",
                    "api_model_id": route_id,
                    "api_reasoning_option_id": "provider_declared_max",
                }
                first = json.loads(
                    post_json(f"{base}/api/codex/custom/native-launch", launch_payload)
                )
                second = json.loads(
                    post_json(f"{base}/api/codex/custom/native-launch", launch_payload)
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["packet_kind"], "custom_native_launch_stability_guard")
        self.assertEqual(second["status"], "ok")
        self.assertTrue(second["existing_window_reuse_admissible"])
        self.assertTrue(second["reused_existing_window"])
        self.assertFalse(second["new_launch_started"])
        self.assertFalse(second["launch_blocked"])
        self.assertFalse(second["visible_window_counts_as_model_truth"])
        self.assertFalse(second["response_text_counts_as_route_truth"])
        self.assertTrue(second["launch_packet_is_truth_source"])
        self.assertEqual(stable_preflight.call_count, 2)
        self.assertEqual(bridge_prewarm.call_count, 2)
        launch.assert_called_once()
        show_window.assert_called_once()

    def test_custom_native_launch_stability_guard_does_not_promote_visible_window_to_usable(self) -> None:
        packet = live_server._custom_native_launch_stability_guard_packet(
            {
                "execution_mode": "api_only",
                "api_model_id": "wbp-deepseek-chat",
                "selected_model": "wbp-deepseek-chat",
                "owner_authorization_phrase_present": True,
                "existing_window_reuse_admissible": True,
                "custom_process_observed": True,
                "custom_process_count": 1,
                "config_status": "matches_last_launch",
            },
            status="blocked",
            machine_error_code="CUSTOM_NATIVE_EXISTING_WINDOW_USABILITY_NOT_PROVEN",
            human_message="Existing Custom Codex window is visible, but input-capable UI was not proven.",
            show_window_packet={
                "schema_version": 1,
                "packet_kind": "custom_codex_show_window",
                "status": "ok",
                "machine_error_code": "OK",
                "custom_window_visible": True,
                "custom_window_frontmost": True,
                "native_app_usable": False,
                "input_capable_ui_observed": False,
                "native_app_usability_source": "not_proven",
                "native_app_usability_blocked_reason_class": "input_capable_ui_not_proven_for_pid_window_present",
                "original_codex_touched": False,
                "asar_touched": False,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_EXISTING_WINDOW_USABILITY_NOT_PROVEN",
        )
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["native_window_observed"])
        self.assertFalse(packet["native_app_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertTrue(packet["launch_blocked"])
        self.assertFalse(packet["reused_existing_window"])
        self.assertEqual(
            packet["native_app_usability_blocked_reason_class"],
            "input_capable_ui_not_proven_for_pid_window_present",
        )

    def test_custom_native_launch_endpoint_relaunches_changed_config_when_previous_launch_is_proven(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(route_id)
        inventory_calls = {"count": 0}

        def fake_inventory(*_: object, **__: object) -> dict[str, object]:
            inventory_calls["count"] += 1
            process_count = 0 if inventory_calls["count"] == 1 else 1
            return {
                "custom_process_count": process_count,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"] if process_count else [],
            }

        def execution_packet(reasoning: str) -> dict[str, object]:
            return {
                "status": "ok",
                "execution_mode": "api_only",
                "api_model_id": route_id,
                "api_reasoning_option_id": reasoning,
                "chatgpt_model_id": "",
                "primary_model_slot": {"slot_id": "primary_model_slot", "model_id": route_id},
                "coding_agent_model_slot": {
                    "slot_id": "coding_agent_model_slot",
                    "model_id": route_id,
                },
                "chatgpt_line_used_as_executor": False,
                "api_line_used_as_executor": True,
                "api_only_calls_chatgpt": False,
                "chatgpt_only_calls_api": False,
                "server_issued_catalog_used": True,
            }

        def fake_launch(**_: object) -> dict[str, object]:
            return {
                "schema_version": 1,
                "captured_at_utc": "2026-05-30T00:00:00Z",
                "mode_id": "codex_custom",
                "status": "ok",
                "machine_error_code": "OK",
                "owner_authorization_phrase_present": True,
                "running_status": True,
                "process_started": True,
                "new_launch_started": True,
                "expected_custom_identity_observed": True,
                "native_window_observed": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "temp_profile_used": False,
                "current_codex_touched": False,
                "original_codex_touched": False,
                "asar_touched": False,
                "browser_raw_backend_authority_widened": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }

        with (
            mock.patch.object(live_server, "collect_codex_process_inventory", side_effect=fake_inventory),
            mock.patch.object(
                live_server,
                "_custom_native_launch_mode_selection_packet",
                side_effect=[
                    execution_packet("provider_declared_max"),
                    execution_packet("provider_declared_max"),
                    execution_packet("provider_declared_high"),
                    execution_packet("provider_declared_high"),
                ],
            ),
            mock.patch.object(
                live_server,
                "build_custom_model_registry_packet",
                return_value={
                    "endpoint": "http://127.0.0.1:8318/v1",
                    "available_models": [
                        {"lane": "wbp_api", "model_id": route_id, "selection_enabled": True}
                    ],
                },
            ),
            mock.patch.object(live_server, "extract_local_api_key", return_value="sk-local"),
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-deepseek",
            ),
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:8319/v1",
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=self.stable_bridge_preflight_ok_packet(),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(
                live_server,
                "terminate_custom_processes",
                return_value={
                    "captured_at_utc": "2026-05-30T00:00:01Z",
                    "initial_custom_pids": [12345],
                    "custom_processes_gone": True,
                    "final_inventory": {
                        "custom_process_count": 0,
                        "custom_process_lines": [],
                    },
                },
            ) as terminate_custom,
            mock.patch.object(live_server, "launch_custom_native_app_packet", side_effect=fake_launch) as launch,
            mock.patch.object(live_server, "show_custom_native_window_packet") as show_window,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                first = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": route_id,
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
                second = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": route_id,
                            "api_reasoning_option_id": "provider_declared_high",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertEqual(second["machine_error_code"], "OK")
        self.assertEqual(second["config_status"], "changed")
        self.assertTrue(second["existing_window_relaunch_attempted"])
        self.assertTrue(second["existing_window_relaunch_admissible"])
        self.assertTrue(second["custom_process_observed_before_relaunch"])
        self.assertEqual(second["custom_process_count_after_relaunch_stop"], 0)
        self.assertEqual(
            second["existing_window_relaunch_termination"]["status"],
            "ok",
        )
        self.assertEqual(
            second["existing_window_relaunch_termination"][
                "initial_custom_process_count"
            ],
            1,
        )
        self.assertTrue(
            second["existing_window_relaunch_termination"]["custom_processes_gone"]
        )
        self.assertFalse(
            second["existing_window_relaunch_termination"]["raw_process_lines_exposed"]
        )
        self.assertFalse(
            second["existing_window_relaunch_termination"]["raw_path_exposed"]
        )
        self.assertFalse(second["selection_matches_last_launch"])
        self.assertFalse(second["reused_existing_window"])
        self.assertTrue(second["new_launch_started"])
        self.assertTrue(second["launch_packet_is_truth_source"])
        self.assertEqual(stable_preflight.call_count, 2)
        self.assertEqual(bridge_prewarm.call_count, 2)
        self.assertEqual(launch.call_count, 2)
        terminate_custom.assert_called_once()
        show_window.assert_not_called()

    def test_custom_native_launch_endpoint_blocks_existing_window_without_matching_last_launch_packet(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(route_id)

        def fake_inventory(*_: object, **__: object) -> dict[str, object]:
            return {
                "custom_process_count": 1,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"],
            }

        execution_packet = {
            "status": "ok",
            "execution_mode": "api_only",
            "api_model_id": route_id,
            "api_reasoning_option_id": "provider_declared_max",
            "chatgpt_model_id": "",
            "primary_model_slot": {"slot_id": "primary_model_slot", "model_id": route_id},
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "model_id": route_id,
            },
            "chatgpt_line_used_as_executor": False,
            "api_line_used_as_executor": True,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "server_issued_catalog_used": True,
        }

        with (
            mock.patch.object(live_server, "collect_codex_process_inventory", side_effect=fake_inventory),
            mock.patch.object(
                live_server,
                "_custom_native_launch_mode_selection_packet",
                return_value=execution_packet,
            ),
            mock.patch.object(
                live_server,
                "build_custom_model_registry_packet",
                return_value={
                    "endpoint": "http://127.0.0.1:8318/v1",
                    "available_models": [
                        {"lane": "wbp_api", "model_id": route_id, "selection_enabled": True}
                    ],
                },
            ),
            mock.patch.object(live_server, "extract_local_api_key", return_value="sk-local"),
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-deepseek",
            ),
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:8319/v1",
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=self.stable_bridge_preflight_ok_packet(),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(live_server, "launch_custom_native_app_packet") as launch,
            mock.patch.object(live_server, "show_custom_native_window_packet") as show_window,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": route_id,
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["packet_kind"], "custom_native_launch_stability_guard")
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_EXISTING_WINDOW_WITHOUT_MATCHING_LAUNCH_PACKET",
        )
        self.assertEqual(packet["config_status"], "no_previous_launch")
        self.assertEqual(
            packet["preflight_packet"]["next_action"],
            "block_existing_window_without_matching_launch_packet",
        )
        self.assertTrue(packet["custom_process_observed"])
        self.assertFalse(packet["selection_matches_last_launch"])
        self.assertFalse(packet["existing_window_reuse_admissible"])
        self.assertFalse(packet["reused_existing_window"])
        self.assertFalse(packet["new_launch_started"])
        self.assertTrue(packet["launch_blocked"])
        self.assertFalse(packet["raw_process_lines_exposed"])
        self.assertFalse(packet["raw_path_exposed"])
        stable_preflight.assert_called_once()
        bridge_prewarm.assert_called_once()
        launch.assert_not_called()
        show_window.assert_not_called()

    def test_custom_native_launch_endpoint_classifies_existing_window_show_failure_without_timeout_claim(self) -> None:
        route_id = "wbp-deepseek-v4-pro-max"
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = routes_list_packet(route_id)
        inventory_calls = {"count": 0}

        def fake_inventory(*_: object, **__: object) -> dict[str, object]:
            inventory_calls["count"] += 1
            process_count = 0 if inventory_calls["count"] == 1 else 1
            return {
                "custom_process_count": process_count,
                "default_process_count": 0,
                "custom_process_lines": ["redacted"] if process_count else [],
            }

        execution_packet = {
            "status": "ok",
            "execution_mode": "api_only",
            "api_model_id": route_id,
            "api_reasoning_option_id": "provider_declared_max",
            "chatgpt_model_id": "",
            "primary_model_slot": {"slot_id": "primary_model_slot", "model_id": route_id},
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "model_id": route_id,
            },
            "chatgpt_line_used_as_executor": False,
            "api_line_used_as_executor": True,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "server_issued_catalog_used": True,
        }

        def fake_launch(**_: object) -> dict[str, object]:
            return {
                "schema_version": 1,
                "captured_at_utc": "2026-05-30T00:00:00Z",
                "mode_id": "codex_custom",
                "status": "ok",
                "machine_error_code": "OK",
                "owner_authorization_phrase_present": True,
                "running_status": True,
                "process_started": True,
                "new_launch_started": True,
                "expected_custom_identity_observed": True,
                "native_window_observed": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "temp_profile_used": False,
                "current_codex_touched": False,
                "original_codex_touched": False,
                "asar_touched": False,
                "browser_raw_backend_authority_widened": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }

        with (
            mock.patch.object(live_server, "collect_codex_process_inventory", side_effect=fake_inventory),
            mock.patch.object(
                live_server,
                "_custom_native_launch_mode_selection_packet",
                return_value=execution_packet,
            ),
            mock.patch.object(
                live_server,
                "build_custom_model_registry_packet",
                return_value={
                    "endpoint": "http://127.0.0.1:8318/v1",
                    "available_models": [
                        {"lane": "wbp_api", "model_id": route_id, "selection_enabled": True}
                    ],
                },
            ),
            mock.patch.object(live_server, "extract_local_api_key", return_value="sk-local"),
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-deepseek",
            ),
            mock.patch.object(
                live_server._CustomNativeBridgeLease,
                "ensure",
                return_value="http://127.0.0.1:8319/v1",
            ),
            mock.patch.object(
                live_server,
                "build_custom_codex_stable_bridge_preflight_packet",
                return_value=self.stable_bridge_preflight_ok_packet(),
            ) as stable_preflight,
            mock.patch.object(
                live_server,
                "_custom_native_stable_bridge_prewarm_packet",
                return_value=self.stable_bridge_prewarm_ok_packet(),
            ) as bridge_prewarm,
            mock.patch.object(live_server, "launch_custom_native_app_packet", side_effect=fake_launch) as launch,
            mock.patch.object(
                live_server,
                "show_custom_native_window_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_show_window",
                    "status": "blocked",
                    "machine_error_code": "CUSTOM_CODEX_WINDOW_NOT_FOUND",
                    "custom_window_visible": False,
                    "custom_window_frontmost": False,
                    "original_codex_touched": False,
                    "asar_touched": False,
                },
            ) as show_window,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                launch_payload = {
                    "execution_mode": "api_only",
                    "api_model_id": route_id,
                    "api_reasoning_option_id": "provider_declared_max",
                }
                first = json.loads(
                    post_json(f"{base}/api/codex/custom/native-launch", launch_payload)
                )
                second = json.loads(
                    post_json(f"{base}/api/codex/custom/native-launch", launch_payload)
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["packet_kind"], "custom_native_launch_stability_guard")
        self.assertEqual(second["status"], "blocked")
        self.assertEqual(
            second["machine_error_code"],
            "CUSTOM_NATIVE_EXISTING_WINDOW_NOT_RESPONSIVE",
        )
        self.assertFalse(second["new_launch_started"])
        self.assertTrue(second["window_unresponsive_with_limits"])
        self.assertFalse(second["window_response_timeout"])
        self.assertEqual(stable_preflight.call_count, 2)
        self.assertEqual(bridge_prewarm.call_count, 2)
        launch.assert_called_once()
        show_window.assert_called_once()

    def test_custom_native_api_launch_uses_stable_wbp_bridge_port(self) -> None:
        stable_port = free_port()
        route_id = "wbp-deepseek-v4-pro-max"
        captured_endpoint: dict[str, str] = {}
        execution_packet = {
            "status": "ok",
            "execution_mode": "api_only",
            "api_model_id": route_id,
            "api_reasoning_option_id": "provider_declared_max",
            "chatgpt_model_id": "",
            "primary_model_slot": {"slot_id": "primary_model_slot", "model_id": route_id},
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "model_id": route_id,
            },
            "chatgpt_line_used_as_executor": False,
            "api_line_used_as_executor": True,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "server_issued_catalog_used": True,
        }
        routes_packet = {
            "data": {
                "routes": [
                    {
                        "route_id": route_id,
                        "enabled": True,
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-v4-pro",
                        "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
                    }
                ]
            }
        }

        def fake_launch(**kwargs: object) -> dict[str, object]:
            captured_endpoint["endpoint"] = str(kwargs["endpoint"])
            return {
                "schema_version": 1,
                "captured_at_utc": "2026-05-30T00:00:00Z",
                "mode_id": "codex_custom",
                "status": "ok",
                "machine_error_code": "OK",
                "owner_authorization_phrase_present": True,
                "running_status": True,
                "process_started": True,
                "expected_custom_identity_observed": True,
                "native_window_observed": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "temp_profile_used": False,
                "current_codex_touched": False,
                "original_codex_touched": False,
                "asar_touched": False,
                "browser_raw_backend_authority_widened": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }

        with (
            mock.patch.object(live_server, "extract_local_api_key", return_value="sk-local"),
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-deepseek",
            ),
            mock.patch.object(
                live_server,
                "_custom_native_launch_mode_selection_packet",
                return_value=execution_packet,
            ),
            mock.patch.object(
                live_server,
                "build_custom_model_registry_packet",
                return_value={
                    "endpoint": "http://127.0.0.1:8318/v1",
                    "available_models": [
                        {
                            "lane": "codex_native",
                            "model_id": "gpt-5.4",
                            "selection_enabled": True,
                        },
                        {
                            "lane": "wbp_api",
                            "model_id": route_id,
                            "selection_enabled": True,
                        },
                    ],
                },
            ),
            mock.patch.object(live_server, "launch_custom_native_app_packet", side_effect=fake_launch),
        ):
            lease = live_server._CustomNativeBridgeLease(bridge_port=stable_port)
            try:
                packet = live_server._launch_custom_native_codex_packet(
                    {
                        "execution_mode": "api_only",
                        "api_model_id": route_id,
                        "api_reasoning_option_id": "provider_declared_max",
                    },
                    owner_authorized=True,
                    commands={},
                    operator_status={},
                    api_snapshot={},
                    external_routes_packet=routes_packet,
                    native_bridge_lease=lease,
                )
            finally:
                lease.close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(captured_endpoint["endpoint"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertEqual(packet["bridge_url"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertEqual(packet["bridge_port"], stable_port)
        self.assertTrue(packet["bridge_alive"])
        self.assertEqual(packet["bridge_owner"], "wbp_current_process")
        self.assertTrue(packet["config_points_to_stable_bridge"])
        self.assertFalse(packet["random_port_used"])
        self.assertTrue(packet["route_selected"])
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertEqual(packet["selected_model"], route_id)
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["paid_provider_called"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertEqual(
            packet["stable_custom_codex_wbp_bridge_final_status"],
            "STABLE_CUSTOM_CODEX_WBP_BRIDGE_PROVEN_WITH_LIMITS",
        )

    def test_custom_native_api_launch_blocks_foreign_stable_bridge_port(self) -> None:
        occupied = ThreadingHTTPServer(("127.0.0.1", free_port()), StableProbeHandler)
        thread = threading.Thread(target=occupied.serve_forever, daemon=True)
        thread.start()
        stable_port = int(occupied.server_port)
        route_id = "wbp-deepseek-v4-pro-max"
        execution_packet = {
            "status": "ok",
            "execution_mode": "api_only",
            "api_model_id": route_id,
            "api_reasoning_option_id": "provider_declared_max",
            "chatgpt_model_id": "",
            "primary_model_slot": {"slot_id": "primary_model_slot", "model_id": route_id},
            "coding_agent_model_slot": {
                "slot_id": "coding_agent_model_slot",
                "model_id": route_id,
            },
            "chatgpt_line_used_as_executor": False,
            "api_line_used_as_executor": True,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "server_issued_catalog_used": True,
        }
        routes_packet = {
            "data": {
                "routes": [
                    {
                        "route_id": route_id,
                        "enabled": True,
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-v4-pro",
                        "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
                    }
                ]
            }
        }

        try:
            with (
                mock.patch.object(live_server, "extract_local_api_key", return_value="sk-local"),
                mock.patch(
                    "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                    return_value="sk-deepseek",
                ),
                mock.patch.object(
                    live_server,
                    "_custom_native_launch_mode_selection_packet",
                    return_value=execution_packet,
                ),
                mock.patch.object(
                    live_server,
                    "build_custom_model_registry_packet",
                    return_value={
                        "endpoint": "http://127.0.0.1:8318/v1",
                        "available_models": [{"lane": "wbp_api", "model_id": route_id}],
                    },
                ),
            ):
                lease = live_server._CustomNativeBridgeLease(bridge_port=stable_port)
                packet = live_server._launch_custom_native_codex_packet(
                    {
                        "execution_mode": "api_only",
                        "api_model_id": route_id,
                        "api_reasoning_option_id": "provider_declared_max",
                    },
                    owner_authorized=True,
                    commands={},
                    operator_status={},
                    api_snapshot={},
                    external_routes_packet=routes_packet,
                    native_bridge_lease=lease,
                )
        finally:
            occupied.shutdown()
            thread.join(timeout=2)
            occupied.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT_UNAVAILABLE",
        )
        self.assertEqual(packet["bridge_url"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertEqual(packet["bridge_port"], stable_port)
        self.assertTrue(packet["bridge_alive"])
        self.assertEqual(packet["bridge_owner"], "foreign_or_unavailable")
        self.assertFalse(packet["config_points_to_stable_bridge"])
        self.assertFalse(packet["random_port_used"])
        self.assertTrue(packet["route_selected"])
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["paid_provider_called"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertEqual(
            packet["stable_custom_codex_wbp_bridge_final_status"],
            "KNOWN_BLOCKER_STABLE_WBP_BRIDGE_UNAVAILABLE",
        )

    def test_app_copy_live_admission_and_bounded_helper_launch_use_server_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            helper_path = temp_path / "helper.sh"
            helper_path.write_text(
                "#!/bin/sh\n"
                "mkdir -p \"$WBP_MANAGED_DIR\"\n"
                "printf helper-ran > \"$WBP_MANAGED_DIR/helper-marker\"\n",
                encoding="utf-8",
            )
            helper_path.chmod(0o755)
            contract = LaunchCopyContract(
                client_path=str(helper_path),
                profile_dir=str(temp_path / "profile"),
                data_dir=str(temp_path / "data"),
                copy_port=9321,
                action_server_port=8788,
                helper_execution_provenance="server_owned_bounded_helper",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                build_handler(launch_copy_contract=contract),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                admission = json.loads(
                    post_json(f"{base}/api/codex/app-copy/live-admission", {})
                )
                live = json.loads(post_json(f"{base}/api/codex/app-copy/launch", {}))
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/app-copy/launch",
                        {"path": "/tmp/app", "pid": 123, "env": {"HOME": "/tmp/home"}},
                    )
                )
                marker_written = (temp_path / "data" / "helper-marker").exists()
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(admission["status"], "ok")
        self.assertEqual(
            admission["machine_error_code"],
            "WEB_SAFE_APP_COPY_LIVE_ADMISSION_READY",
        )
        self.assertEqual(admission["final_verdict"], "WEB_SAFE_APP_COPY_LIVE_ADMISSION_READY")
        self.assertTrue(admission["live_launch_admitted"])
        self.assertTrue(admission["owner_preflight_target_exists"])
        self.assertEqual(admission["owner_preflight_target_kind"], "executable")
        self.assertTrue(admission["owner_preflight_separate_profile"])
        self.assertTrue(admission["owner_preflight_separate_data_dir"])
        self.assertTrue(admission["owner_preflight_separate_port"])
        self.assertFalse(admission["launch_performed"])
        self.assertFalse(admission["launch_ready_claimed"])
        self.assertFalse(admission["bounded_live_launch_execution_ready"])
        self.assertFalse(admission["raw_path_exposed"])
        self.assertFalse(admission["raw_pid_exposed"])
        self.assertEqual(live["status"], "ok")
        self.assertEqual(
            live["machine_error_code"],
            "WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_READY",
        )
        self.assertEqual(live["final_verdict"], "WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_READY")
        self.assertTrue(live["live_launch_admitted"])
        self.assertTrue(live["launch_performed"])
        self.assertTrue(live["bounded_helper_execution"])
        self.assertFalse(live["real_codex_app_launched"])
        self.assertTrue(live["process_started"])
        self.assertTrue(live["cleanup_or_stop_completed"])
        self.assertTrue(live["receipt_redacted"])
        self.assertFalse(live["raw_path_exposed"])
        self.assertFalse(live["raw_pid_exposed"])
        self.assertFalse(live["raw_env_exposed"])
        self.assertNotIn(str(helper_path), json.dumps(live))
        self.assertNotIn(str(temp_path), json.dumps(live))
        self.assertTrue(marker_written)
        self.assertEqual(rejected["status"], "blocked")
        self.assertEqual(
            rejected["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
        )
        self.assertEqual(rejected["forbidden_fields"], ["path", "pid", "env", "env.HOME"])
        self.assertFalse(rejected["live_launch_admitted"])
        self.assertFalse(rejected["launch_performed"])
        self.assertEqual(
            rejected["block_reason_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
        )

    def test_app_copy_launch_forbidden_payload_does_not_execute_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            marker_path = temp_path / "data" / "helper-marker"
            helper_path = temp_path / "helper.sh"
            helper_path.write_text(
                "#!/bin/sh\n"
                "mkdir -p \"$WBP_MANAGED_DIR\"\n"
                "printf unsafe > \"$WBP_MANAGED_DIR/helper-marker\"\n",
                encoding="utf-8",
            )
            helper_path.chmod(0o755)
            contract = LaunchCopyContract(
                client_path=str(helper_path),
                profile_dir=str(temp_path / "profile"),
                data_dir=str(temp_path / "data"),
                copy_port=9321,
                action_server_port=8788,
                helper_execution_provenance="server_owned_bounded_helper",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                build_handler(launch_copy_contract=contract),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/app-copy/launch",
                        {"command": "run", "env": {"HOME": "/tmp/home"}},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "blocked")
        self.assertEqual(
            rejected["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
        )
        self.assertFalse(rejected["live_launch_admitted"])
        self.assertFalse(rejected["launch_performed"])
        self.assertFalse(marker_path.exists())

    def test_app_copy_launch_blocks_helper_target_that_resembles_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            helper_path = temp_path / "CodexHelper"
            helper_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            helper_path.chmod(0o755)
            contract = LaunchCopyContract(
                client_path=str(helper_path),
                profile_dir=str(temp_path / "profile"),
                data_dir=str(temp_path / "data"),
                copy_port=9321,
                action_server_port=8788,
                helper_execution_provenance="server_owned_bounded_helper",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                build_handler(launch_copy_contract=contract),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                blocked = json.loads(post_json(f"{base}/api/codex/app-copy/launch", {}))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(
            blocked["machine_error_code"],
            "WEB_SAFE_APP_COPY_HELPER_TARGET_UNSAFE",
        )
        self.assertFalse(blocked["live_launch_admitted"])
        self.assertFalse(blocked["launch_performed"])
        self.assertFalse(blocked["raw_path_exposed"])

    def test_app_copy_launch_invalid_json_does_not_execute_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            marker_path = temp_path / "data" / "helper-marker"
            helper_path = temp_path / "helper.sh"
            helper_path.write_text(
                "#!/bin/sh\n"
                "mkdir -p \"$WBP_MANAGED_DIR\"\n"
                "printf invalid-body > \"$WBP_MANAGED_DIR/helper-marker\"\n",
                encoding="utf-8",
            )
            helper_path.chmod(0o755)
            contract = LaunchCopyContract(
                client_path=str(helper_path),
                profile_dir=str(temp_path / "profile"),
                data_dir=str(temp_path / "data"),
                copy_port=9321,
                action_server_port=8788,
                helper_execution_provenance="server_owned_bounded_helper",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                build_handler(launch_copy_contract=contract),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                invalid_json_status, invalid_json = post_body_response(
                    f"{base}/api/codex/app-copy/launch",
                    b"{not-json",
                )
                non_object_status, non_object = post_body_response(
                    f"{base}/api/codex/app-copy/launch",
                    b'["run"]',
                )
                no_body_status, no_body = post_body_response(
                    f"{base}/api/codex/app-copy/launch",
                    b"",
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(invalid_json_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(invalid_json["status"], "rejected")
        self.assertEqual(invalid_json["machine_error_code"], "WEB_INGRESS_JSON_INVALID")
        self.assertEqual(non_object_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(non_object["status"], "rejected")
        self.assertEqual(
            non_object["machine_error_code"],
            "WEB_INGRESS_JSON_OBJECT_REQUIRED",
        )
        self.assertEqual(no_body_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(no_body["status"], "rejected")
        self.assertEqual(
            no_body["machine_error_code"],
            "WEB_INGRESS_JSON_BODY_REQUIRED",
        )
        for rejected in (invalid_json, non_object, no_body):
            self.assertEqual(rejected["source"], "web_ingress")
            self.assertEqual(rejected["changed_files"], [])
            self.assertNotIn(str(helper_path), json.dumps(rejected))
            self.assertNotIn(str(temp_path), json.dumps(rejected))
        self.assertFalse(marker_path.exists())

    def test_app_copy_launch_blocks_helper_without_server_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            marker_path = temp_path / "data" / "helper-marker"
            helper_path = temp_path / "helper.sh"
            helper_path.write_text(
                "#!/bin/sh\n"
                "mkdir -p \"$WBP_MANAGED_DIR\"\n"
                "printf no-provenance > \"$WBP_MANAGED_DIR/helper-marker\"\n",
                encoding="utf-8",
            )
            helper_path.chmod(0o755)
            contract = LaunchCopyContract(
                client_path=str(helper_path),
                profile_dir=str(temp_path / "profile"),
                data_dir=str(temp_path / "data"),
                copy_port=9321,
                action_server_port=8788,
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                build_handler(launch_copy_contract=contract),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                blocked = json.loads(post_json(f"{base}/api/codex/app-copy/launch", {}))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(
            blocked["machine_error_code"],
            "WEB_SAFE_APP_COPY_HELPER_TARGET_UNSAFE",
        )
        self.assertFalse(blocked["launch_performed"])
        self.assertFalse(marker_path.exists())

    def test_app_copy_launch_blocks_symlinked_helper_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            marker_path = temp_path / "data" / "helper-marker"
            real_helper_path = temp_path / "real-helper.sh"
            real_helper_path.write_text(
                "#!/bin/sh\n"
                "mkdir -p \"$WBP_MANAGED_DIR\"\n"
                "printf symlink > \"$WBP_MANAGED_DIR/helper-marker\"\n",
                encoding="utf-8",
            )
            real_helper_path.chmod(0o755)
            symlink_path = temp_path / "safe-helper"
            symlink_path.symlink_to(real_helper_path)
            contract = LaunchCopyContract(
                client_path=str(symlink_path),
                profile_dir=str(temp_path / "profile"),
                data_dir=str(temp_path / "data"),
                copy_port=9321,
                action_server_port=8788,
                helper_execution_provenance="server_owned_bounded_helper",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                build_handler(launch_copy_contract=contract),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                blocked = json.loads(post_json(f"{base}/api/codex/app-copy/launch", {}))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(
            blocked["machine_error_code"],
            "WEB_SAFE_APP_COPY_HELPER_TARGET_UNSAFE",
        )
        self.assertFalse(blocked["launch_performed"])
        self.assertFalse(marker_path.exists())


class WebDesignCodexCustomModelRegistryEndpointTests(unittest.TestCase):
    def test_codex_custom_model_registry_endpoints_are_readonly_and_zero_token(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=mock.Mock()))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                registry = json.loads(fetch(f"{base}/api/codex/custom/models"))
                compat = json.loads(fetch(f"{base}/api/codex/custom/api-compat"))
                dry_run = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/model-dry-run",
                        {"model_id": "gpt-5.3-codex"},
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/model-dry-run",
                        {"model_id": "gpt-5.3-codex", "route_id": "route", "backend_id": "backend"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(registry["status"], "degraded")
        self.assertEqual(registry["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertTrue(registry["server_issued"])
        self.assertEqual(registry["model_count"], 2)
        self.assertFalse(registry["route_or_backend_exposed"])
        self.assertEqual(registry["token_burn"], 0)
        self.assertFalse(registry["models_endpoint_called"])
        self.assertFalse(registry["network_calls_made"])
        self.assertTrue(registry["openai_compatible_shape_declared"])
        self.assertTrue(registry["models_endpoint_shape_declared"])
        self.assertEqual(registry["configured_wire_api"], "responses")
        self.assertFalse(registry["inference_called"])
        self.assertFalse(registry["provider_called"])
        self.assertFalse(registry["independent_runtime_meter_attached"])
        self.assertTrue(compat["openai_compatible_shape_declared"])
        self.assertFalse(compat["live_api_checked"])
        self.assertFalse(compat["compat_surfaces"]["/v1/models"]["called"])
        self.assertEqual(compat["compat_surfaces"]["/v1/models"]["status"], "shape_declared")
        self.assertFalse(compat["compat_surfaces"]["/v1/responses"]["called"])
        self.assertFalse(compat["compat_surfaces"]["/v1/chat/completions"]["called"])
        self.assertFalse(compat["network_call_summary"]["network_calls_made"])
        self.assertEqual(compat["network_call_summary"]["forbidden_calls_made"], [])
        self.assertEqual(dry_run["status"], "degraded")
        self.assertTrue(dry_run["dry_run"])
        self.assertTrue(dry_run["model_server_issued"])
        self.assertTrue(dry_run["selected_model_server_issued"])
        self.assertEqual(dry_run["model_provider"], "cliproxy")
        self.assertEqual(dry_run["wire_api"], "responses")
        self.assertFalse(dry_run["network_call_summary"]["network_calls_made"])
        self.assertFalse(dry_run["responses_called"])
        self.assertFalse(dry_run["chat_completions_called"])
        self.assertEqual(dry_run["token_burn"], 0)
        self.assertEqual(
            dry_run["negative_claim_basis"],
            "shape_declaration_no_live_api_or_inference_call",
        )
        self.assertFalse(dry_run["independent_runtime_meter_attached"])
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], ["route_id", "backend_id"])
        self.assertEqual(created_sessions[0].run_payloads, [])
        self.assertGreaterEqual(created_sessions[0].status_payload_calls, 1)

    def test_codex_custom_model_registry_timeout_returns_bounded_error_packet(self) -> None:
        class SlowOperatorSurfaceSession(FakeOperatorSurfaceSession):
            def status_payload(self) -> dict[str, object]:
                time.sleep(0.2)
                return super().status_payload()

        with mock.patch.object(
            live_server,
            "OperatorSurfaceSession",
            return_value=SlowOperatorSurfaceSession(),
        ):
            with mock.patch.object(live_server, "CUSTOM_CODEX_READONLY_TIMEOUT_SECONDS", 0.01):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(runner=MappingRunner(live_payloads())),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    registry = json.loads(fetch(f"{base}/api/codex/custom/models"))
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertNotEqual(registry["status"], "ok")
        self.assertEqual(registry["status"], "integration_failure")
        self.assertEqual(registry["machine_error_code"], "CUSTOM_CODEX_READONLY_TIMEOUT")
        self.assertEqual(registry["endpoint"], "/api/codex/custom/models")
        self.assertEqual(registry["timeout_scope"], "custom_models_readonly_snapshot")
        self.assertFalse(registry["fallback_used"])
        self.assertFalse(registry["model_auto_selected"])

    def test_bounded_operator_status_timeout_preserves_fast_model_catalog(self) -> None:
        class SlowStatusFastModelsSession(FakeOperatorSurfaceSession):
            def status_payload(self) -> dict[str, object]:
                time.sleep(0.2)
                return super().status_payload()

            def probe_models(self) -> dict[str, object]:
                return {
                    "ok": True,
                    "server_issued": True,
                    "model_ids": ["gpt-5.4", "wbp-deepseek-v4-pro-max"],
                    "model_entries": [
                        {"model_id": "gpt-5.4", "lane": "codex_native"},
                        {
                            "model_id": "wbp-deepseek-v4-pro-max",
                            "lane": "wbp_api",
                        },
                    ],
                }

        with mock.patch.object(
            live_server,
            "CUSTOM_CODEX_OPERATOR_STATUS_READONLY_TIMEOUT_SECONDS",
            0.01,
        ):
            packet, timed_out = live_server._bounded_operator_status_payload(
                SlowStatusFastModelsSession()
            )

        self.assertTrue(timed_out)
        self.assertEqual(
            packet["status"]["machine_error_code"],
            "CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_API_CATALOG_ONLY",
        )
        self.assertEqual(
            packet["models"]["model_ids"],
            ["gpt-5.4", "wbp-deepseek-v4-pro-max"],
        )
        self.assertTrue(packet["models"]["server_issued"])

    def test_operator_status_endpoint_uses_bounded_status_snapshot(self) -> None:
        class SlowStatusFastModelsSession(FakeOperatorSurfaceSession):
            def status_payload(self) -> dict[str, object]:
                time.sleep(0.2)
                return super().status_payload()

            def probe_models(self) -> dict[str, object]:
                return {
                    "ok": True,
                    "server_issued": True,
                    "model_ids": ["gpt-5.4", "wbp-deepseek-v4-pro-max"],
                    "model_entries": [
                        {"model_id": "gpt-5.4", "lane": "codex_native"},
                        {
                            "model_id": "wbp-deepseek-v4-pro-max",
                            "lane": "wbp_api",
                        },
                    ],
                }

        with (
            mock.patch.object(
                live_server,
                "OperatorSurfaceSession",
                return_value=SlowStatusFastModelsSession(),
            ),
            mock.patch.object(
                live_server,
                "CUSTOM_CODEX_OPERATOR_STATUS_READONLY_TIMEOUT_SECONDS",
                0.01,
            ),
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(live_payloads())),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(fetch(f"{base}/api/operator/status"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(
            packet["status"]["machine_error_code"],
            "CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_API_CATALOG_ONLY",
        )
        self.assertEqual(
            packet["models"]["model_ids"],
            ["gpt-5.4", "wbp-deepseek-v4-pro-max"],
        )
        self.assertTrue(packet["models"]["server_issued"])

    def test_codex_custom_model_registry_includes_server_owned_external_route_models(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                registry = json.loads(fetch(f"{base}/api/codex/custom/models"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        route_entry = next(
            entry for entry in registry["available_models"] if entry["model_id"] == "wbp-deepseek-v3"
        )
        self.assertEqual(route_entry["provider_class"], "external_route")
        self.assertEqual(route_entry["source"], "server_owned_external_route")
        self.assertEqual(route_entry["model_source_hint"], "server_owned_external_route")

    def test_codex_custom_model_registry_keeps_disabled_route_visible_but_not_selectable(self) -> None:
        api_snapshot = {
            "status": "ok",
            "source": "api_connections_readonly",
            "primary_truth_ok": True,
            "routes": [
                {
                    "route_id": "wbp-disabled-openrouter",
                    "provider": "openrouter",
                    "upstream_model": "openai/gpt-5",
                    "enabled": False,
                    "secret_ref": "OPENROUTER_API_KEY",
                }
            ],
        }
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            with mock.patch.object(
                live_server,
                "build_api_connections_readonly_snapshot",
                return_value=api_snapshot,
            ):
                server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    registry = json.loads(fetch(f"{base}/api/codex/custom/models"))
                    dry_run = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/model-dry-run",
                            {"model_id": "wbp-disabled-openrouter"},
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        route_entry = next(
            entry for entry in registry["available_models"] if entry["model_id"] == "wbp-disabled-openrouter"
        )
        self.assertFalse(route_entry["selection_enabled"])
        self.assertEqual(route_entry["selection_state"], "disabled")
        self.assertEqual(route_entry["selection_disabled_reason_code"], "ROUTE_DISABLED")
        self.assertEqual(dry_run["status"], "rejected")
        self.assertEqual(dry_run["machine_error_code"], "MODEL_NOT_SELECTABLE")
        self.assertTrue(dry_run["model_server_issued"])
        self.assertFalse(dry_run["selected_model_selectable"])
        self.assertFalse(dry_run["network_call_summary"]["network_calls_made"])

    def test_codex_custom_model_registry_keeps_readonly_catalog_free_of_live_native_probe(self) -> None:
        lattice = build_catalog_availability_lattice_packet(
            catalog_packet={"models": [{"model_id": "gpt-5.3-codex", "lane": "codex_native"}]},
            current_model_packets=[
                build_model_direct_preflight_packet(
                    model_id="gpt-5.3-codex",
                    source="current_live_native_probe",
                    listed=True,
                    selectable=True,
                    route_selected=True,
                    runtime_ready=True,
                    http_status=503,
                    error_payload={
                        "machine_error_code": "AUTH_UNAVAILABLE",
                        "error": {"type": "auth_error"},
                    },
                    prompt_text="Reply OK",
                    request_sent_to_wbp=True,
                    route_family="codex_native_account_route",
                )
            ],
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            with mock.patch.object(
                live_server,
                "_build_live_native_availability_lattice_packet",
                return_value=lattice,
            ) as availability_lattice:
                server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    registry = json.loads(fetch(f"{base}/api/codex/custom/models"))
                    dry_run = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/model-dry-run",
                            {"model_id": "gpt-5.3-codex"},
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        row = next(entry for entry in registry["available_models"] if entry["model_id"] == "gpt-5.3-codex")
        self.assertTrue(row["selection_enabled"])
        self.assertFalse(registry["live_api_checked"])
        self.assertFalse(registry["network_calls_made"])
        self.assertEqual(availability_lattice.call_count, 1)
        self.assertEqual(dry_run["status"], "rejected")
        self.assertEqual(dry_run["machine_error_code"], "MODEL_NOT_SELECTABLE")


class WebDesignCodexCustomDualLaneSelectorEndpointTests(unittest.TestCase):
    def test_codex_custom_dual_lane_selector_endpoint_separates_lanes_and_seed_reference(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                selector = json.loads(fetch(f"{base}/api/codex/custom/model-selector"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(selector["status"], "ok")
        self.assertTrue(selector["server_issued"])
        self.assertFalse(selector["flat_model_truth_presented"])
        self.assertFalse(selector["selector_runtime_readiness_claimed"])
        self.assertFalse(selector["simultaneous_execution_proven"])
        self.assertEqual(selector["allowed_browser_fields"], ["chatgpt_model_id", "api_model_id"])
        self.assertIn("model_id", selector["forbidden_browser_fields"])
        self.assertFalse(any(selector["browser_authority"].values()))
        self.assertGreaterEqual(selector["chatgpt_lane"]["model_count"], 1)
        self.assertGreaterEqual(selector["api_lane"]["model_count"], 1)
        self.assertGreaterEqual(selector["seed_only_reference"]["model_count"], 1)
        self.assertTrue(
            all(entry["lane_kind"] == "codex_native" for entry in selector["chatgpt_lane"]["models"])
        )
        self.assertTrue(
            all(entry["lane_kind"] == "wbp_api" for entry in selector["api_lane"]["models"])
        )
        self.assertTrue(
            all(entry["selection_enabled"] is False for entry in selector["seed_only_reference"]["models"])
        )

    def test_codex_custom_dual_lane_selector_timeout_returns_degraded_api_lane_fallback(self) -> None:
        class SlowOperatorSurfaceSession(FakeOperatorSurfaceSession):
            def status_payload(self) -> dict[str, object]:
                time.sleep(0.2)
                return super().status_payload()

        with mock.patch.object(
            live_server,
            "OperatorSurfaceSession",
            return_value=SlowOperatorSurfaceSession(),
        ):
            with mock.patch.object(live_server, "CUSTOM_CODEX_READONLY_TIMEOUT_SECONDS", 0.01):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(runner=MappingRunner(live_payloads())),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    selector = json.loads(fetch(f"{base}/api/codex/custom/model-selector"))
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(selector["status"], "degraded")
        self.assertEqual(selector["machine_error_code"], "CUSTOM_CODEX_READONLY_TIMEOUT")
        self.assertEqual(selector["endpoint"], "/api/codex/custom/model-selector")
        self.assertEqual(selector["timeout_scope"], "custom_model_selector_readonly_snapshot")
        self.assertTrue(selector["fallback_used"])
        self.assertFalse(selector["model_auto_selected"])
        self.assertFalse(selector["selector_runtime_readiness_claimed"])
        self.assertTrue(selector["outer_selector_timeout"])
        self.assertGreaterEqual(selector["api_lane"]["model_count"], 1)
        self.assertGreaterEqual(selector["api_lane"]["selectable_model_count"], 1)
        self.assertTrue(selector["api_lane_catalog_available"])

    def test_codex_custom_status_timeout_returns_bounded_error_packet(self) -> None:
        class SlowOperatorSurfaceSession(FakeOperatorSurfaceSession):
            def status_payload(self) -> dict[str, object]:
                time.sleep(0.2)
                return super().status_payload()

        with mock.patch.object(
            live_server,
            "OperatorSurfaceSession",
            return_value=SlowOperatorSurfaceSession(),
        ):
            with mock.patch.object(live_server, "CUSTOM_CODEX_READONLY_TIMEOUT_SECONDS", 0.01):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(runner=MappingRunner(live_payloads())),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    custom_status = json.loads(fetch(f"{base}/api/codex/custom/status"))
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(custom_status["status"], "integration_failure")
        self.assertEqual(custom_status["machine_error_code"], "CUSTOM_CODEX_READONLY_TIMEOUT")
        self.assertEqual(custom_status["endpoint"], "/api/codex/custom/status")
        self.assertEqual(custom_status["timeout_scope"], "custom_status_readonly_snapshot")
        self.assertFalse(custom_status["fallback_used"])
        self.assertFalse(custom_status["model_auto_selected"])

    def test_codex_custom_dual_lane_selector_keeps_readonly_catalog_free_of_live_native_probe(self) -> None:
        lattice = build_catalog_availability_lattice_packet(
            catalog_packet={"models": [{"model_id": "gpt-5.3-codex", "lane": "codex_native"}]},
            current_model_packets=[
                build_model_direct_preflight_packet(
                    model_id="gpt-5.3-codex",
                    source="current_live_native_probe",
                    listed=True,
                    selectable=True,
                    route_selected=True,
                    runtime_ready=True,
                    http_status=503,
                    error_payload={
                        "machine_error_code": "AUTH_UNAVAILABLE",
                        "error": {"type": "auth_error"},
                    },
                    prompt_text="Reply OK",
                    request_sent_to_wbp=True,
                    route_family="codex_native_account_route",
                )
            ],
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            with mock.patch.object(
                live_server,
                "_build_live_native_availability_lattice_packet",
                return_value=lattice,
            ) as availability_lattice:
                server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    selector = json.loads(fetch(f"{base}/api/codex/custom/model-selector"))
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        row = next(entry for entry in selector["chatgpt_lane"]["models"] if entry["model_id"] == "gpt-5.3-codex")
        self.assertTrue(row["selection_enabled"])
        self.assertFalse(selector["selector_runtime_readiness_claimed"])
        availability_lattice.assert_not_called()

    def test_codex_custom_dual_lane_selector_dry_run_is_intent_only_and_forbids_backend_fields(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                empty = json.loads(
                    post_json(f"{base}/api/codex/custom/model-selector-dry-run", {})
                )
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/model-selector-dry-run",
                        {
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/model-selector-dry-run",
                        {
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v3",
                            "route_id": "browser-route",
                            "provider": "deepseek",
                            "base_url": "http://127.0.0.1:9999/v1",
                            "account_id": "browser-account",
                            "auth_path": "/tmp/browser-auth.json",
                            "secret_ref": "BROWSER_SECRET_REF",
                            "codex_home": "/tmp/browser-codex-home",
                            "profile_path": "/tmp/browser-profile",
                            "api_key": "browser-key",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(empty["status"], "degraded")
        self.assertEqual(empty["machine_error_code"], "CHATGPT_LANE_SELECTION_UNRESOLVED")
        self.assertTrue(empty["selection_intent_only"])
        self.assertFalse(empty["selection_intent_proven"])
        self.assertFalse(empty["selected_models_are_server_issued"])
        self.assertFalse(empty["chatgpt_model_selected_by_user"])
        self.assertFalse(empty["api_model_selected_by_user"])
        self.assertFalse(empty["catalog_defaults_used_as_selection"])
        self.assertIsNone(empty["chatgpt_selection"])
        self.assertIsNone(empty["api_selection"])
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["selection_intent_only"])
        self.assertFalse(packet["selector_runtime_readiness_claimed"])
        self.assertFalse(packet["simultaneous_execution_proven"])
        self.assertFalse(packet["role_slot_binding_proven"])
        self.assertFalse(packet["session_execution_wired"])
        self.assertEqual(packet["current_execution_path_scope"], "chatgpt_lane_only_in_this_contour")
        self.assertEqual(packet["current_execution_path_source"], "operator_reported_configured_model")
        self.assertEqual(packet["api_lane_scope"], "selection_intent_only_until_role_slot_session_contour")
        self.assertEqual(packet["chatgpt_selection"]["model_id"], "gpt-5.3-codex")
        self.assertEqual(packet["api_selection"]["model_id"], "wbp-deepseek-v3")
        self.assertTrue(packet["chatgpt_model_selected_by_user"])
        self.assertTrue(packet["api_model_selected_by_user"])
        self.assertFalse(packet["catalog_defaults_used_as_selection"])
        self.assertFalse(packet["seed_only_selected"])
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("route_id", rejected["forbidden_fields"])
        self.assertIn("provider", rejected["forbidden_fields"])
        self.assertIn("base_url", rejected["forbidden_fields"])
        self.assertIn("account_id", rejected["forbidden_fields"])
        self.assertIn("auth_path", rejected["forbidden_fields"])
        self.assertIn("secret_ref", rejected["forbidden_fields"])
        self.assertIn("codex_home", rejected["forbidden_fields"])
        self.assertIn("profile_path", rejected["forbidden_fields"])
        self.assertIn("api_key", rejected["forbidden_fields"])

    def test_codex_custom_execution_mode_dry_run_binds_three_modes_without_live_claims(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                chatgpt_only = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {"execution_mode": "chatgpt_only"},
                    )
                )
                chatgpt_api = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "chatgpt_plus_api",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                api_only = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(chatgpt_only["status"], "ok")
        self.assertEqual(
            chatgpt_only["allowed_browser_fields"],
            ["api_model_id", "api_reasoning_option_id", "chatgpt_model_id", "execution_mode"],
        )
        self.assertEqual(chatgpt_only["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertEqual(chatgpt_only["api_model_id"], "")
        self.assertEqual(chatgpt_only["coding_agent_model_slot"]["status"], "not_bound_for_mode")
        self.assertFalse(chatgpt_only["api_line_used_as_executor"])
        self.assertFalse(chatgpt_only["chatgpt_only_calls_api"])

        self.assertEqual(chatgpt_api["status"], "ok")
        self.assertEqual(chatgpt_api["execution_mode"], "chatgpt_plus_api")
        self.assertEqual(chatgpt_api["chatgpt_model_id"], "gpt-5.3-codex")
        self.assertEqual(chatgpt_api["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertEqual(chatgpt_api["primary_model_slot"]["model_id"], "gpt-5.3-codex")
        self.assertEqual(chatgpt_api["coding_agent_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(chatgpt_api["coding_agent_model_slot"]["model_id"], "wbp-deepseek-v3")
        self.assertTrue(chatgpt_api["dual_lane_slots_preserved"])

        self.assertEqual(api_only["status"], "ok")
        self.assertEqual(api_only["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(api_only["primary_model_slot"]["model_id"], "wbp-deepseek-v3")
        self.assertEqual(api_only["api_reasoning_option_id"], "catalog_default")
        self.assertFalse(api_only["api_reasoning_option_runtime_mutation_claimed"])
        self.assertEqual(
            api_only["coding_agent_model_slot"]["reason"],
            "api_only_uses_primary_model_slot",
        )
        self.assertFalse(api_only["chatgpt_line_used_as_executor"])
        self.assertFalse(api_only["api_only_calls_chatgpt"])
        self.assertFalse(api_only["live_call_attempted"])
        self.assertFalse(api_only["provider_called"])
        self.assertFalse(api_only["original_codex_touched"])
        self.assertFalse(api_only["asar_touched"])
        self.assertFalse(api_only["wbp_patch_applier_used"])
        self.assertTrue(api_only["selector_packet_truth_only"])

    def test_codex_custom_execution_mode_dry_run_rejects_raw_backend_fields(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "base_url": "https://browser.invalid/v1",
                            "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                            "CODEX_HOME": "/tmp/browser-codex-home",
                            "api_key": "browser-key",
                        },
                    )
                )
                unknown = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "browser-invented-model",
                        },
                    )
                )
                unknown_mode = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/execution-mode-dry-run",
                        {
                            "execution_mode": "browser_mode",
                            "api_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(
            rejected["machine_error_code"],
            "CUSTOM_CODEX_EXECUTION_MODE_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertIn("base_url", rejected["forbidden_fields"])
        self.assertIn("route_config", rejected["forbidden_fields"])
        self.assertIn("route_config.secret_ref", rejected["forbidden_fields"])
        self.assertIn("CODEX_HOME", rejected["forbidden_fields"])
        self.assertIn("api_key", rejected["forbidden_fields"])
        self.assertTrue(rejected["browser_raw_backend_authority_widened"])
        self.assertFalse(rejected["live_call_attempted"])

        self.assertEqual(unknown["status"], "rejected")
        self.assertEqual(
            unknown["machine_error_code"],
            "CUSTOM_CODEX_EXECUTION_MODE_API_MODEL_NOT_SERVER_ISSUED",
        )
        self.assertFalse(unknown["live_call_attempted"])
        self.assertEqual(unknown_mode["status"], "rejected")
        self.assertEqual(
            unknown_mode["machine_error_code"],
            "CUSTOM_CODEX_EXECUTION_MODE_NOT_ADMITTED",
        )
        self.assertFalse(unknown_mode["live_call_attempted"])

    def test_codex_custom_server_model_selection_truth_endpoint_is_non_live(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/server-model-selection-truth",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/server-model-selection-truth",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "base_url": "https://browser.invalid/v1",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_SERVER_MODEL_SELECTION_TRUTH_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["model_selection_truth_proven"])
        self.assertEqual(packet["source"], "server_catalog")
        self.assertTrue(packet["server_catalog_source"])
        self.assertFalse(packet["browser_route_authority"])
        self.assertFalse(packet["browser_secret_authority"])
        self.assertFalse(packet["browser_model_authority"])
        self.assertFalse(packet["ui_label_counts_as_model_truth"])
        self.assertFalse(packet["model_self_report_counts_as_model_truth"])
        self.assertFalse(packet["codex_window_required"])
        self.assertTrue(packet["dry_server_truth_only"])
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["selected_api_model"], "wbp-deepseek-v3")
        self.assertEqual(packet["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(packet["coding_agent_model_slot"]["status"], "not_bound_for_mode")
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["runtime_execution_proven"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["ui_work_attempted"])
        self.assertFalse(packet["custom_codex_launch_attempted"])

        self.assertEqual(rejected["status"], "blocked")
        self.assertEqual(
            rejected["final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_SERVER_MODEL_SELECTION_TRUTH_NOT_PROVEN",
        )
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], [])
        self.assertEqual(rejected["forbidden_browser_fields"], [])
        self.assertEqual(rejected["forbidden_field_count"], 1)
        self.assertTrue(rejected["forbidden_fields_redacted"])
        self.assertTrue(rejected["forbidden_browser_fields_redacted"])
        self.assertTrue(rejected["browser_raw_backend_authority_widened"])
        self.assertFalse(rejected["live_call_attempted"])
        rejected_json = json.dumps(rejected, ensure_ascii=False)
        self.assertNotIn("https://browser.invalid/v1", rejected_json)
        self.assertNotIn('"base_url"', rejected_json)
        self.assertNotIn('"route_id"', rejected_json)
        self.assertNotIn('"secret_ref"', rejected_json)

    def test_quick_start_config_admission_endpoint_returns_bounded_packet(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "status", "--json")]["data"][
            "available_secret_refs"
        ] = ["OPENROUTER_API_KEY"]
        payloads[("external-models", "routes", "list", "--json")]["data"]["routes"][0][
            "secret_status_label"
        ] = "available"
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["final_status"], "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS")
        self.assertEqual(packet["packet_kind"], "quick_start_config_admission")
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["launch_admission"], "admitted")
        self.assertEqual(packet["chatgpt_model"]["status"], "not_required")
        self.assertEqual(packet["api_model"]["status"], "admitted")
        self.assertEqual(packet["api_model"]["model_id"], "wbp-deepseek-v3")
        self.assertEqual(packet["api_route"]["status"], "admitted")
        self.assertEqual(packet["api_route"]["route_reference"], "server-owned-api-route")
        self.assertIn(packet["api_reasoning"]["status"], {"accepted", "defaulted"})
        self.assertTrue(packet["dry_server_truth_only"])
        self.assertFalse(packet["runtime_execution_proven"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["custom_codex_launch_attempted"])
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["silent_fallback_used"])
        self.assertFalse(packet["browser_route_authority"])
        self.assertFalse(packet["browser_secret_authority"])
        self.assertFalse(packet["browser_model_authority"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_path_exposed"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        packet_json = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn("OPENROUTER_API_KEY", packet_json)
        self.assertNotIn('"secret_ref"', packet_json)
        self.assertNotIn('"base_url"', packet_json)
        self.assertNotIn('"endpoint_path"', packet_json)
        self.assertNotIn('"route_id"', packet_json)
        self.assertNotIn("native-launch", packet_json)
        self.assertNotIn(("healthcheck", "--json"), runner.calls)
        self.assertNotIn(("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"), runner.calls)

    def test_quick_start_config_admission_rejects_forbidden_browser_fields(self) -> None:
        runner = MappingRunner(live_payloads())
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "route_id": "browser-route",
                            "base_url": "https://browser.invalid/v1",
                            "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                            "path": "/tmp/browser-path",
                            "CODEX_HOME": "/tmp/browser-codex-home",
                            "api_key": "browser-key",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(
            rejected["machine_error_code"],
            "QUICK_START_CONFIG_ADMISSION_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertEqual(rejected["launch_admission"], "blocked")
        self.assertEqual(
            rejected["final_status"],
            "KNOWN_BLOCKER_QUICK_START_CONFIG_ADMISSION_NOT_PROVEN",
        )
        self.assertIn("base_url", rejected["forbidden_fields"])
        self.assertIn("route_id", rejected["forbidden_fields"])
        self.assertIn("route_config", rejected["forbidden_fields"])
        self.assertIn("route_config.secret_ref", rejected["forbidden_fields"])
        self.assertIn("path", rejected["forbidden_fields"])
        self.assertIn("CODEX_HOME", rejected["forbidden_fields"])
        self.assertIn("api_key", rejected["forbidden_fields"])
        self.assertTrue(rejected["dry_server_truth_only"])
        self.assertFalse(rejected["live_call_attempted"])
        self.assertFalse(rejected["provider_called"])
        self.assertFalse(rejected["network_calls_made"])
        self.assertFalse(rejected["custom_codex_launch_attempted"])
        self.assertFalse(rejected["fallback_used"])
        self.assertFalse(rejected["silent_fallback_used"])
        rejected_json = json.dumps(rejected, ensure_ascii=False)
        self.assertNotIn("https://browser.invalid/v1", rejected_json)
        self.assertNotIn("browser-route", rejected_json)
        self.assertNotIn("BROWSER_SECRET_REF", rejected_json)
        self.assertNotIn("/tmp/browser-path", rejected_json)
        self.assertNotIn("/tmp/browser-codex-home", rejected_json)
        self.assertNotIn("browser-key", rejected_json)
        self.assertNotIn(("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"), runner.calls)

    def test_quick_start_config_admission_blocks_api_only_without_api_route(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            data={"count": 0, "routes": []},
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            data={"count": 0, "source": "local_routes_registry", "models": []},
        )
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["launch_admission"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_QUICK_START_CONFIG_ADMISSION_NOT_PROVEN",
        )
        self.assertIn(packet["api_model"]["status"], {"missing", "unavailable"})
        self.assertEqual(packet["api_route"]["status"], "missing")
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["custom_codex_launch_attempted"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["silent_fallback_used"])
        self.assertNotIn(("launch", "client", "--client-path", TEST_LAUNCH_CLIENT_PATH, "--json"), runner.calls)

    def test_quick_start_config_admission_reports_chatgpt_plus_api_slots(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "status", "--json")]["data"][
            "available_secret_refs"
        ] = ["OPENROUTER_API_KEY"]
        payloads[("external-models", "routes", "list", "--json")]["data"]["routes"][0][
            "secret_status_label"
        ] = "available"
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "chatgpt_plus_api",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["launch_admission"], "admitted")
        self.assertEqual(packet["chatgpt_model"]["status"], "admitted")
        self.assertEqual(packet["chatgpt_model"]["lane"], "codex_account_lane")
        self.assertEqual(packet["api_model"]["status"], "admitted")
        self.assertEqual(packet["api_model"]["lane"], "api_route_lane")
        self.assertEqual(packet["api_route"]["status"], "admitted")
        self.assertIn(packet["api_reasoning"]["status"], {"accepted", "defaulted"})
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["silent_fallback_used"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["custom_codex_launch_attempted"])

    def test_quick_start_config_admission_blocks_chatgpt_when_healthcheck_is_red(self) -> None:
        payloads = live_payloads()
        payloads[("healthcheck", "--json")] = command_packet(
            status="error",
            exit_code=1,
            human_message="Proxy path is broken.",
            machine_error_code="PROXY_REPROBE_FAILED",
            next_action="restore_or_start_last_known_good_proxy_then_reprobe",
        )
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "chatgpt_only",
                            "chatgpt_model_id": "gpt-5.3-codex",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "PROXY_REPROBE_FAILED")
        self.assertEqual(packet["launch_admission"], "blocked")
        self.assertEqual(packet["chatgpt_model"]["status"], "admitted")
        self.assertEqual(packet["api_model"]["status"], "not_required")
        self.assertEqual(packet["api_route"]["status"], "not_required")
        self.assertEqual(packet["api_reasoning"]["status"], "not_required")
        self.assertEqual(packet["runtime_health_gate"]["status"], "blocked")
        self.assertEqual(
            packet["runtime_health_gate"]["runtime_health_machine_error_code"],
            "PROXY_REPROBE_FAILED",
        )
        self.assertEqual(
            packet["next_action"],
            "restore_or_start_last_known_good_proxy_then_reprobe",
        )
        self.assertFalse(packet["custom_codex_launch_attempted"])
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertIn(("healthcheck", "--json"), runner.calls)

    def test_quick_start_config_admission_blocks_chatgpt_when_healthcheck_attestation_missing(self) -> None:
        payloads = live_payloads()
        payloads[("healthcheck", "--json")] = command_packet(
            human_message="Healthcheck passed without attestation.",
        )
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/quick-start/config-admission",
                        {
                            "execution_mode": "chatgpt_only",
                            "chatgpt_model_id": "gpt-5.3-codex",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_CODEX_RUNTIME_ATTESTATION_INVALID",
        )
        self.assertEqual(packet["launch_admission"], "blocked")
        self.assertEqual(packet["chatgpt_model"]["status"], "admitted")
        self.assertEqual(packet["api_model"]["status"], "not_required")
        self.assertEqual(packet["api_route"]["status"], "not_required")
        self.assertEqual(packet["api_reasoning"]["status"], "not_required")
        self.assertEqual(packet["runtime_health_gate"]["status"], "blocked")
        self.assertEqual(
            packet["runtime_health_gate"]["runtime_health_machine_error_code"],
            "CUSTOM_CODEX_RUNTIME_ATTESTATION_INVALID",
        )
        self.assertEqual(packet["next_action"], "retry_healthcheck_attestation")
        self.assertFalse(packet["custom_codex_launch_attempted"])
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertIn(("healthcheck", "--json"), runner.calls)

    def test_custom_native_launch_blocks_chatgpt_when_healthcheck_is_red(self) -> None:
        payloads = live_payloads()
        payloads[("healthcheck", "--json")] = command_packet(
            status="error",
            exit_code=1,
            human_message="Proxy path is broken.",
            machine_error_code="PROXY_REPROBE_FAILED",
            next_action="restore_or_start_last_known_good_proxy_then_reprobe",
        )
        runner = MappingRunner(payloads)
        with (
            mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()),
            mock.patch.object(
                live_server,
                "collect_codex_process_inventory",
                return_value={
                    "custom_process_count": 0,
                    "default_process_count": 0,
                    "custom_process_lines": [],
                },
            ),
            mock.patch.object(live_server, "launch_custom_native_app_packet") as launch_native,
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=runner,
                    action_phase=live_server.FULL_ACTION_PHASE,
                    owner_authorization_phrase=(
                        "разрешаю тебе любые законные действия в рамках разработки проекта"
                    ),
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/native-launch",
                        {
                            "execution_mode": "chatgpt_only",
                            "chatgpt_model_id": "gpt-5.3-codex",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "PROXY_REPROBE_FAILED")
        self.assertEqual(packet["preflight_packet"]["status"], "blocked")
        self.assertEqual(
            packet["preflight_packet"]["runtime_health_machine_error_code"],
            "PROXY_REPROBE_FAILED",
        )
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["process_started"])
        self.assertFalse(packet["show_window_attempted"])
        self.assertFalse(packet["native_window_observed"])
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        launch_native.assert_not_called()
        self.assertIn(("healthcheck", "--json"), runner.calls)

    def test_codex_custom_chatgpt_plus_api_slot_truth_endpoint_is_non_live(self) -> None:
        payloads = live_payloads()
        payloads[("external-models", "routes", "list", "--json")] = command_packet(
            human_message="External-models routes listed from local registry.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "count": 1,
                "routes": [
                    {
                        "schema_version": 1,
                        "route_id": "wbp-deepseek-v4-pro-max",
                        "display_name": "DeepSeek V4 Pro Max",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-v4-pro",
                        "compatibility": "openai_chat_completions",
                        "auth": {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"},
                        "cost_class": "paid_or_free_limited",
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "enabled": True,
                        "thinking": {"type": "enabled", "reasoning_effort": "max"},
                        "api_parameter_sent": True,
                    }
                ],
            },
        )
        payloads[("external-models", "models", "--json")] = command_packet(
            human_message="External-models route models listed from local registry.",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            data={
                "count": 1,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [
                    {
                        "route_id": "wbp-deepseek-v4-pro-max",
                        "display_name": "DeepSeek V4 Pro Max",
                        "provider": "deepseek",
                        "base_url": "https://api.deepseek.com/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek-v4-pro",
                        "compatibility": "openai_chat_completions",
                        "cost_class": "paid_or_free_limited",
                        "enabled": True,
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "synthetic_adapter_state": "stopped",
                        "profile_ready": False,
                        "thinking": {"type": "enabled", "reasoning_effort": "max"},
                        "api_parameter_sent": True,
                    }
                ],
            },
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(payloads)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/chatgpt-plus-api-slot-truth",
                        {
                            "execution_mode": "chatgpt_plus_api",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "api_reasoning_option_id": "provider_declared_max",
                        },
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/chatgpt-plus-api-slot-truth",
                        {
                            "execution_mode": "chatgpt_plus_api",
                            "chatgpt_model_id": "gpt-5.3-codex",
                            "api_model_id": "wbp-deepseek-v4-pro-max",
                            "route_id": "browser-route",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["final_status"], "CHATGPT_PLUS_API_SLOT_ROUTING_PROVEN_WITH_LIMITS")
        self.assertTrue(packet["slot_truth_proven"])
        self.assertEqual(packet["execution_mode"], "chatgpt_plus_api")
        self.assertEqual(packet["selected_chatgpt_model"], "gpt-5.3-codex")
        self.assertEqual(packet["selected_api_model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(packet["source"], "server_selection_truth")
        self.assertTrue(packet["server_selection_truth_used"])
        self.assertTrue(packet["server_catalog_source"])
        self.assertTrue(packet["selected_chatgpt_model_server_issued"])
        self.assertTrue(packet["selected_api_model_server_issued"])
        self.assertTrue(packet["api_reasoning_option_model_bound"])
        self.assertTrue(packet["api_reasoning_option_server_validated"])
        self.assertFalse(packet["browser_route_authority"])
        self.assertFalse(packet["browser_secret_authority"])
        self.assertFalse(packet["browser_model_authority"])
        self.assertFalse(packet["ui_label_counts_as_model_truth"])
        self.assertFalse(packet["model_self_report_counts_as_model_truth"])
        self.assertFalse(packet["codex_window_required"])
        self.assertFalse(packet["codex_window_observed"])
        self.assertTrue(packet["dry_server_truth_only"])
        self.assertEqual(packet["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertEqual(packet["coding_agent_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(packet["coding_agent_model_slot"]["provider"], "deepseek")
        self.assertEqual(
            packet["coding_agent_model_slot"]["model_id"],
            "wbp-deepseek-v4-pro-max",
        )
        self.assertTrue(packet["coding_slot_provider_is_deepseek"])
        self.assertTrue(packet["coding_slot_model_is_deepseek_v4_pro_max"])
        self.assertFalse(packet["slots_collapsed"])
        self.assertTrue(packet["api_line_selected_as_coding_agent"])
        self.assertTrue(packet["api_line_used_as_coding_agent"])
        self.assertFalse(packet["api_line_used_as_primary_executor"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["fallback_attempted"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["route_or_backend_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["browser_raw_backend_authority_widened"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["live_api_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["runtime_execution_proven"])
        self.assertFalse(packet["ui_work_attempted"])
        self.assertFalse(packet["custom_codex_launch_attempted"])
        self.assertFalse(packet["live_paid_call_attempted"])
        self.assertFalse(packet["full_delegation_claimed"])

        self.assertEqual(rejected["status"], "blocked")
        self.assertEqual(
            rejected["final_status"],
            "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_ROUTING_NOT_PROVEN",
        )
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], [])
        self.assertEqual(rejected["forbidden_field_count"], 1)
        self.assertTrue(rejected["forbidden_fields_redacted"])
        rejected_json = json.dumps(rejected, ensure_ascii=False)
        self.assertNotIn("browser-route", rejected_json)
        self.assertNotIn('"route_id"', rejected_json)
        self.assertFalse(rejected["browser_route_authority"])
        self.assertFalse(rejected["browser_secret_authority"])
        self.assertFalse(rejected["browser_model_authority"])
        self.assertTrue(rejected["browser_raw_backend_authority_widened"])
        self.assertFalse(rejected["fallback_used"])
        self.assertFalse(rejected["live_call_attempted"])

    def test_codex_custom_api_only_executor_truth_endpoint_is_non_live(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-executor-truth",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "api_reasoning_option_id": "catalog_default",
                        },
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-executor-truth",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "route_id": "browser-route",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["final_status"], "API_ONLY_EXECUTOR_TRUTH_PROVEN_WITH_LIMITS")
        self.assertTrue(packet["executor_truth_proven"])
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["selected_api_model"], "wbp-deepseek-v3")
        self.assertEqual(packet["source"], "server_selection_truth")
        self.assertTrue(packet["server_selection_truth_used"])
        self.assertTrue(packet["server_catalog_source"])
        self.assertTrue(packet["selected_api_model_server_issued"])
        self.assertTrue(packet["api_primary_slot_proven"])
        self.assertEqual(packet["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(packet["primary_model_slot"]["source"], "server_catalog")
        self.assertEqual(packet["coding_agent_model_slot"]["status"], "not_bound_for_mode")
        self.assertTrue(packet["api_line_selected_as_executor"])
        self.assertTrue(packet["api_line_used_as_executor"])
        self.assertFalse(packet["chatgpt_line_used_as_executor"])
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["fallback_attempted"])
        self.assertFalse(packet["browser_route_authority"])
        self.assertFalse(packet["browser_secret_authority"])
        self.assertFalse(packet["browser_model_authority"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["route_or_backend_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["browser_raw_backend_authority_widened"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertFalse(packet["live_api_call_attempted"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["runtime_execution_proven"])
        self.assertFalse(packet["ui_work_attempted"])
        self.assertFalse(packet["custom_codex_launch_attempted"])

        self.assertEqual(rejected["status"], "blocked")
        self.assertEqual(
            rejected["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_EXECUTOR_TRUTH_NOT_PROVEN",
        )
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], [])
        self.assertEqual(rejected["forbidden_field_count"], 1)
        self.assertTrue(rejected["forbidden_fields_redacted"])
        rejected_json = json.dumps(rejected, ensure_ascii=False)
        self.assertNotIn("browser-route", rejected_json)
        self.assertNotIn('"route_id"', rejected_json)
        self.assertFalse(rejected["browser_route_authority"])
        self.assertFalse(rejected["browser_secret_authority"])
        self.assertFalse(rejected["browser_model_authority"])
        self.assertTrue(rejected["browser_raw_backend_authority_widened"])
        self.assertFalse(rejected["fallback_used"])
        self.assertFalse(rejected["live_call_attempted"])

    def test_codex_custom_api_only_deepseek_live_format_requires_owner_auth(self) -> None:
        runner = MappingRunner(live_payloads())
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-deepseek/live-format",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "API_ONLY_DEEPSEEK_OWNER_AUTH_REQUIRED",
        )
        self.assertTrue(packet["deepseek_selected_from_server_catalog"])
        self.assertTrue(packet["api_line_selected_as_executor"])
        self.assertFalse(packet["api_line_used_as_executor"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertEqual(packet["request_count"], 0)
        self.assertNotIn(
            (
                "external-models",
                "live-format-check",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Верни короткий ответ: API_ONLY_DEEPSEEK_READY",
                "--expected-text",
                "API_ONLY_DEEPSEEK_READY",
                "--json",
            ),
            runner.calls,
        )

    def test_codex_custom_api_only_deepseek_live_format_calls_provider_once_with_owner_auth(self) -> None:
        runner = MappingRunner(live_payloads())
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=runner,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-deepseek/live-format",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "API_ONLY_DEEPSEEK_LIVE_ROUTE_AND_FORMAT_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["deepseek_selected_from_server_catalog"])
        self.assertTrue(packet["owner_authorization_phrase_present"])
        self.assertFalse(packet["chatgpt_line_used_as_executor"])
        self.assertTrue(packet["api_line_selected_as_executor"])
        self.assertTrue(packet["api_line_used_as_executor"])
        self.assertTrue(packet["provider_called"])
        self.assertTrue(packet["live_call_attempted"])
        self.assertTrue(packet["upstream_response_observed"])
        self.assertTrue(packet["expected_text_observed"])
        self.assertTrue(packet["codex_compatible_response_shape"])
        self.assertEqual(packet["request_count"], 1)
        self.assertEqual(packet["retry_count"], 0)
        self.assertFalse(packet["parallel_fanout_attempted"])
        self.assertFalse(packet["fallback_attempted"])
        self.assertFalse(packet["file_mutation_attempted"])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        self.assertIn(
            (
                "external-models",
                "live-format-check",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Верни короткий ответ: API_ONLY_DEEPSEEK_READY",
                "--expected-text",
                "API_ONLY_DEEPSEEK_READY",
                "--json",
            ),
            runner.calls,
        )
        self.assertNotIn(
            ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"),
            runner.calls,
        )

    def test_codex_custom_api_only_deepseek_live_format_rejects_raw_browser_fields(self) -> None:
        runner = MappingRunner(live_payloads())
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=runner,
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-only-deepseek/live-format",
                        {
                            "execution_mode": "api_only",
                            "api_model_id": "wbp-deepseek-v3",
                            "base_url": "https://browser.invalid/v1",
                            "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                            "CODEX_HOME": "/tmp/browser-codex-home",
                            "api_key": "browser-key",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(
            packet["machine_error_code"],
            "API_ONLY_DEEPSEEK_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertIn("base_url", packet["forbidden_fields"])
        self.assertIn("route_config.secret_ref", packet["forbidden_fields"])
        self.assertIn("CODEX_HOME", packet["forbidden_fields"])
        self.assertIn("api_key", packet["forbidden_fields"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["live_call_attempted"])
        self.assertEqual(runner.calls.count(
            (
                "external-models",
                "live-format-check",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Верни короткий ответ: API_ONLY_DEEPSEEK_READY",
                "--expected-text",
                "API_ONLY_DEEPSEEK_READY",
                "--json",
            )
        ), 0)

    def test_codex_custom_api_action_gate_blocks_live_api_without_owner_auth(self) -> None:
        runner = MappingRunner(live_payloads())
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-action-gate",
                        {"api_model_id": "wbp-deepseek-v3"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_API_ACTION_GATE_OWNER_AUTH_REQUIRED",
        )
        self.assertEqual(packet["manual_api_choice_packet"]["status"], "ok")
        self.assertEqual(packet["manual_api_choice_packet"]["route_id"], "wbp-deepseek-v3")
        self.assertEqual(packet["manual_api_choice_packet"]["provider"], "openrouter")
        self.assertEqual(packet["manual_api_choice_packet"]["cost_class"], "paid_or_free_limited")
        self.assertTrue(packet["manual_api_choice_packet"]["selection_intent_only"])
        self.assertFalse(packet["manual_api_choice_packet"]["execution_proven"])
        self.assertFalse(packet["manual_api_choice_packet"]["provider_response_observed"])
        self.assertFalse(
            packet["manual_api_choice_packet"]["route_snapshot_counted_as_provider_response"]
        )
        self.assertEqual(packet["owner_authorization_packet"]["status"], "blocked")
        self.assertFalse(packet["owner_authorization_packet"]["owner_live_authorization_present"])
        self.assertEqual(packet["budget_policy_packet"]["status"], "blocked")
        boundary = packet["live_provider_request_boundary_packet"]
        self.assertFalse(boundary["live_provider_request_allowed"])
        self.assertFalse(boundary["live_call_attempted"])
        self.assertFalse(boundary["paid_route_used"])
        self.assertFalse(boundary["upstream_response_observed"])
        self.assertFalse(boundary["fallback_attempted"])
        self.assertFalse(boundary["parallel_fanout_attempted"])
        self.assertFalse(boundary["original_codex_touched"])
        self.assertFalse(boundary["raw_secret_recorded"])
        self.assertFalse(boundary["secret_value_recorded"])
        self.assertNotIn(
            ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"),
            runner.calls,
        )

    def test_codex_custom_api_action_gate_rejects_raw_browser_backend_fields(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-action-gate",
                        {
                            "api_model_id": "wbp-deepseek-v3",
                            "base_url": "https://browser.invalid/v1",
                            "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                            "CODEX_HOME": "/tmp/browser-codex-home",
                            "api_key": "browser-key",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_CODEX_API_ACTION_GATE_BROWSER_AUTHORITY_REJECTED",
        )
        guard = packet["browser_authority_guard_packet"]
        self.assertEqual(guard["status"], "rejected")
        self.assertTrue(guard["browser_raw_backend_authority_widened"])
        self.assertIn("base_url", guard["forbidden_fields"])
        self.assertIn("route_config", guard["forbidden_fields"])
        self.assertIn("route_config.secret_ref", guard["forbidden_fields"])
        self.assertIn("CODEX_HOME", guard["forbidden_fields"])
        self.assertIn("api_key", guard["forbidden_fields"])
        self.assertFalse(packet["live_provider_request_boundary_packet"]["live_call_attempted"])

    def test_codex_custom_api_action_gate_owner_auth_still_requires_budget(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(live_payloads()),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/api-action-gate",
                        {"api_model_id": "wbp-deepseek-v3"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_API_ACTION_GATE_BUDGET_POLICY_REQUIRED",
        )
        self.assertEqual(packet["owner_authorization_packet"]["status"], "ok")
        self.assertTrue(packet["owner_authorization_packet"]["owner_live_authorization_present"])
        self.assertEqual(packet["budget_policy_packet"]["status"], "blocked")
        self.assertFalse(
            packet["live_provider_request_boundary_packet"]["live_provider_request_allowed"]
        )


class WebDesignCodexCustomAccountSelectionEndpointTests(unittest.TestCase):
    def test_codex_custom_account_selection_endpoints_are_readonly_and_no_inference(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "blocked_by_policy_drift"},
            pool_summary={
                "active": 2,
                "reserve": 1,
                "retired": 1,
                "healthy": 3,
                "degraded": 0,
                "down": 1,
                "selected_backend_ids": ["acct-active"],
            },
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
                "launch_capable_backend_count": 1,
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[
                account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-redacted-auth.json"),
                account("acct-reserve", "reserve", "healthy", auth_ref="/tmp/wbp-reserve-auth.json"),
                account("acct-hold", "reserve", "healthy", manual_hold=True, auth_ref="/tmp/wbp-hold-auth.json"),
                account("acct-problem", "retired", "down", last_error="auth failed"),
            ]
        )
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                accounts = json.loads(fetch(f"{base}/api/codex/custom/accounts"))
                selection = json.loads(fetch(f"{base}/api/codex/custom/account-selection"))
                dry_run = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/account-smoke-dry-run",
                        {"model_id": "gpt-5.3-codex"},
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/account-smoke-dry-run",
                        {
                            "model_id": "gpt-5.3-codex",
                            "account_id": "acct-active",
                            "backend_id": "acct-active",
                            "route_id": "route",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(accounts["status"], "degraded")
        self.assertEqual(accounts["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertEqual(accounts["managed_total"], 4)
        self.assertEqual(accounts["account_source"], "provided_packet_or_fake")
        self.assertEqual(accounts["account_count_claim_scope"], "packet_shape_only")
        self.assertFalse(accounts["live_account_truth_checked"])
        self.assertEqual(accounts["launch_capable_count"], 1)
        self.assertTrue(accounts["account_ids_redacted"])
        self.assertEqual(accounts["launch_capable_backend_ids"], [])
        self.assertEqual(len(accounts["launch_capable_backend_refs"]), 1)
        self.assertEqual(accounts["selected_backend_ids_observed"], [])
        self.assertEqual(len(accounts["selected_backend_refs_observed"]), 1)
        self.assertFalse(accounts["account_mutation_performed"])
        self.assertFalse(accounts["raw_backend_ids_exposed"])
        self.assertFalse(accounts["raw_auth_refs_exposed"])
        self.assertFalse(accounts["raw_auth_visible"])
        self.assertEqual(accounts["token_burn"], 0)
        self.assertNotIn(TEST_SANDBOX_AUTH_REF, json.dumps(accounts))
        self.assertNotIn("acct-active", json.dumps(accounts))
        self.assertTrue(selection["selection_dry_run_proven"])
        self.assertFalse(selection["live_selection_proven"])
        self.assertTrue(selection["selection_proven"])
        self.assertFalse(selection["inference_proven"])
        self.assertEqual(selection["selected_source_class"], "gpt_account")
        self.assertEqual(selection["selected_backend_id"], "")
        self.assertTrue(selection["selected_backend_ref"])
        self.assertTrue(selection["selected_backend_id_redacted"])
        self.assertTrue(selection["selected_backend_server_issued"])
        self.assertEqual(selection["selected_backend_source"], "server_ranked_candidate")
        self.assertEqual(selection["account_candidate_source"], "server_ranked_candidate")
        self.assertTrue(selection["source_candidate_classified"])
        self.assertFalse(selection["source_provenance_proven"])
        self.assertFalse(selection["account_selected_by_user"])
        self.assertFalse(selection["account_execution_proven"])
        self.assertFalse(selection["runtime_execution_proven"])
        self.assertFalse(selection["live_compatibility_proven"])
        self.assertFalse(selection["browser_selected_backend"])
        self.assertFalse(selection["runtime_meter_attached"])
        self.assertFalse(selection["smoke_admitted"])
        self.assertFalse(selection["responses_called"])
        self.assertFalse(selection["chat_completions_called"])
        self.assertFalse(selection["provider_called"])
        self.assertFalse(selection["network_calls_made"])
        self.assertFalse(selection["raw_backend_id_exposed"])
        self.assertEqual(selection["token_burn"], 0)
        self.assertTrue(selection["selection_not_inference"])
        self.assertNotIn("acct-active", json.dumps(selection))
        self.assertTrue(dry_run["dry_run"])
        self.assertTrue(dry_run["model_server_issued"])
        self.assertTrue(dry_run["selection_dry_run_proven"])
        self.assertFalse(dry_run["live_selection_proven"])
        self.assertTrue(dry_run["selection_proven"])
        self.assertFalse(dry_run["inference_proven"])
        self.assertFalse(dry_run["smoke_admitted"])
        self.assertFalse(dry_run["responses_called"])
        self.assertFalse(dry_run["chat_completions_called"])
        self.assertFalse(dry_run["provider_called"])
        self.assertFalse(dry_run["network_calls_made"])
        self.assertTrue(dry_run["selected_backend_id_redacted"])
        self.assertEqual(dry_run["selected_backend_id"], "")
        self.assertTrue(dry_run["selected_backend_ref"])
        self.assertFalse(dry_run["account_mutation_performed"])
        self.assertEqual(dry_run["token_burn"], 0)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], ["account_id", "backend_id", "route_id"])
        self.assertEqual(created_sessions[0].run_payloads, [])
        self.assertIn(("accounts", "list", "--json"), runner.calls)
        self.assertIn(("rollout", "rotation", "inspect", "--json"), runner.calls)


class WebDesignCodexCustomSessionEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._codex_custom_session_tempdir = tempfile.TemporaryDirectory()
        self._codex_custom_session_manager_patcher = mock.patch.object(
            live_server,
            "CodexCustomSessionManager",
            side_effect=lambda: REAL_CODEX_CUSTOM_SESSION_MANAGER(
                Path(self._codex_custom_session_tempdir.name)
            ),
        )
        self._codex_custom_session_manager_patcher.start()

    def tearDown(self) -> None:
        self._codex_custom_session_manager_patcher.stop()
        self._codex_custom_session_tempdir.cleanup()
        super().tearDown()

    def test_codex_custom_sessions_endpoint_is_local_readonly(self) -> None:
        class ExplodingOperatorSurfaceSession(FakeOperatorSurfaceSession):
            def status_payload(self) -> dict[str, object]:
                raise AssertionError("sessions endpoint must not call operator status")

        with mock.patch.object(
            live_server,
            "OperatorSurfaceSession",
            return_value=ExplodingOperatorSurfaceSession(),
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(live_payloads())),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                sessions = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(sessions["status"], "ok")
        self.assertEqual(sessions["session_count"], 0)

    def test_bodyless_optional_post_rejects_wrong_content_type_before_runner(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        runner = MappingRunner(live_payloads())
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                status, packet = post_body_response(
                    f"{base}/api/codex/custom/sessions/ccs-ingress-test/revalidate",
                    b"",
                    headers={"Content-Type": "text/plain"},
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(status, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["source"], "web_ingress")
        self.assertEqual(
            packet["machine_error_code"],
            "WEB_INGRESS_CONTENT_TYPE_REJECTED",
        )
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(runner.calls, [])

    def test_codex_custom_session_create_requires_manual_model_selection(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", return_value=FakeOperatorSurfaceSession()):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(live_payloads())),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                rejected = json.loads(post_json(f"{base}/api/codex/custom/sessions", {}))
                legacy_alias = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"model_id": "gpt-5.3-codex"},
                    )
                )
                listed = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "MANUAL_MODEL_SELECTION_REQUIRED")
        self.assertFalse(rejected["session_created"])
        self.assertFalse(rejected["model_auto_selected"])
        self.assertFalse(rejected["fallback_used"])
        self.assertFalse(rejected["external_route_selected"])
        self.assertIn("primary_model_id", rejected["required_choice_fields"])
        self.assertEqual(legacy_alias["status"], "rejected")
        self.assertEqual(legacy_alias["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(legacy_alias["forbidden_fields"], ["model_id"])
        self.assertFalse(legacy_alias["session_created"])
        self.assertFalse(legacy_alias["model_auto_selected"])
        self.assertEqual(listed["session_count"], 0)

    def test_codex_custom_session_lifecycle_is_dry_run_and_server_owned(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "blocked_by_policy_drift"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        runner = MappingRunner(payloads)
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                empty = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "primary_model_id": "gpt-5.3-codex",
                            "coding_agent_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                session_id = created["session"]["session_id"]
                detail = json.loads(fetch(f"{base}/api/codex/custom/sessions/{session_id}"))
                revalidated = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions/{session_id}/revalidate", {})
                )
                prompt = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt-dry-run",
                        {"prompt": "Reply with exactly SESSION_OK."},
                    )
                )
                live_prompt = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {"prompt": "Reply with exactly REAL_SESSION_OK."},
                    )
                )
                transcript = json.loads(
                    fetch(f"{base}/api/codex/custom/sessions/{session_id}/transcript")
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt-dry-run",
                        {"prompt": "OK", "backend_id": "acct-active", "path": "/tmp/outside"},
                    )
                )
                cancel = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions/{session_id}/cancel", {})
                )
                cleanup = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions/{session_id}/cleanup", {})
                )
                listed = json.loads(fetch(f"{base}/api/codex/custom/sessions"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(empty["session_count"], 0)
        self.assertEqual(created["status"], "ok")
        self.assertTrue(created["session_created"])
        self.assertFalse(created["live_prompt_admitted"])
        self.assertTrue(created["session"]["model_server_issued"])
        self.assertEqual(created["session"]["session_schema_version"], 3)
        self.assertEqual(created["session"]["current_execution_slot_id"], "primary_model_slot")
        self.assertEqual(created["session"]["current_execution_path_source"], "session_primary_model_slot")
        self.assertEqual(created["session"]["role_slot_binding_count"], 2)
        self.assertEqual(
            created["session"]["role_slots"]["primary_model_slot"]["model_id"],
            "gpt-5.3-codex",
        )
        self.assertEqual(
            created["session"]["role_slots"]["coding_agent_model_slot"]["model_id"],
            "wbp-deepseek-v3",
        )
        self.assertTrue(created["session"]["selection_dry_run_proven"])
        self.assertFalse(created["session"]["live_selection_proven"])
        self.assertTrue(created["session"]["selection_proven"])
        self.assertTrue(created["session"]["selected_backend_id_redacted"])
        self.assertEqual(created["session"]["session_root_scope"], "owned_temp_session_root")
        self.assertEqual(
            created["role_slot_binding_packet"]["current_execution_slot_id"],
            "primary_model_slot",
        )
        self.assertEqual(
            created["role_slot_binding_packet"]["role_slot_binding_count"],
            2,
        )
        self.assertNotIn("/tmp/wbp-auth.json", json.dumps(created))
        self.assertNotIn("acct-active", json.dumps(created))
        self.assertEqual(detail["session"]["session_id"], session_id)
        self.assertEqual(revalidated["status"], "ok")
        self.assertTrue(revalidated["slot_catalog_revalidated"])
        self.assertTrue(revalidated["provider_model_identity_persistence_proven"])
        self.assertTrue(
            revalidated[
                "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven"
            ]
        )
        self.assertTrue(prompt["prompt_admitted"])
        self.assertEqual(prompt["prompt_length"], len("Reply with exactly SESSION_OK."))
        self.assertNotIn("Reply with exactly SESSION_OK.", json.dumps(prompt))
        self.assertFalse(prompt["model_response_present"])
        self.assertFalse(prompt["inference_proven"])
        self.assertFalse(prompt["runtime_meter_attached"])
        self.assertFalse(prompt["network_calls_made"])
        self.assertFalse(prompt["provider_called"])
        self.assertTrue(prompt["raw_prompt_not_stored"])
        self.assertEqual(prompt["token_burn"], 0)
        self.assertEqual(live_prompt["status"], "blocked")
        self.assertEqual(live_prompt["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertEqual(live_prompt["authorization_status"], "blocked_by_operator_authorization")
        self.assertFalse(live_prompt["owner_authorization_phrase_present"])
        self.assertFalse(live_prompt["live_prompt_admitted"])
        self.assertFalse(live_prompt["live_prompt_executed"])
        self.assertFalse(live_prompt["prompt_runner_called"])
        self.assertFalse(live_prompt["inference_proven"])
        self.assertFalse(live_prompt["model_response_present"])
        self.assertFalse(live_prompt["network_calls_made"])
        self.assertFalse(live_prompt["provider_called"])
        self.assertFalse(live_prompt["fallback_attempted"])
        self.assertNotIn("Reply with exactly REAL_SESSION_OK.", json.dumps(live_prompt))
        self.assertNotIn("acct-active", json.dumps(live_prompt))
        self.assertEqual(transcript["transcript_kind"], "service_ledger_only")
        self.assertFalse(transcript["model_response_present"])
        self.assertFalse(transcript["inference_proven"])
        self.assertTrue(transcript["raw_prompt_not_stored"])
        self.assertTrue(transcript["raw_response_not_stored"])
        self.assertNotIn("Reply with exactly SESSION_OK.", json.dumps(transcript))
        self.assertNotIn("Reply with exactly REAL_SESSION_OK.", json.dumps(transcript))
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], ["backend_id", "path"])
        self.assertFalse(cancel["process_kill_claimed"])
        self.assertTrue(cleanup["cleanup_performed"])
        self.assertTrue(cleanup["owned_session_root_only"])
        self.assertFalse(cleanup["current_codex_home_touched"])
        self.assertFalse(cleanup["arbitrary_path_accepted"])
        self.assertEqual(listed["session_count"], 1)
        self.assertEqual(listed["sessions"][0]["cleanup_state"], "cleaned")
        self.assertEqual(
            created_sessions[0].run_payloads,
            [],
        )

    def test_codex_custom_recovery_contract_endpoint_is_dry_run_only(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            runner = MappingRunner(live_payloads())
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(fetch(f"{base}/api/codex/custom/recovery/contract"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "RECOVERY_CONTRACT_DRY_RUN_ONLY")
        self.assertTrue(packet["contract_aggregator_only"])
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["recovery_live_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        self.assertIn("backend_id", packet["forbidden_browser_fields"])
        self.assertIn("CODEX_HOME", packet["forbidden_browser_fields"])
        self.assertTrue(packet["readonly_sources"]["original_status_ok"])
        self.assertTrue(packet["readonly_sources"]["custom_status_ok"])
        self.assertTrue(packet["readonly_sources"]["accounts_readonly_ok"])
        self.assertTrue(packet["readonly_sources"]["api_readonly_ok"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertTrue(packet["diagnostics_support_artifact_only"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertEqual(actions["stop_selected_custom_session"]["status"], "admitted")
        self.assertEqual(actions["cleanup_owned_session_root"]["status"], "admitted")
        self.assertEqual(actions["rollback_readiness"]["status"], "dry_run_only")
        self.assertEqual(actions["stuck_process_kill_readiness"]["status"], "dry_run_only")
        self.assertEqual(actions["cleanup_arbitrary_path"]["status"], "disabled")
        self.assertEqual(actions["touch_original_codex_profile"]["status"], "disabled")
        self.assertNotIn(("accounts", "list", "--json", "path"), runner.calls)

    def test_codex_custom_recovery_contract_blocks_readonly_failure(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = command_packet(
            status="failed",
            exit_code=1,
            machine_error_code="ACCOUNTS_LIST_FAILED",
            human_message="Accounts readonly failed.",
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(fetch(f"{base}/api/codex/custom/recovery/contract"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "RECOVERY_CONTRACT_DRY_RUN_ONLY")
        self.assertEqual(
            packet["contract_block_reason_code"],
            "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
        )
        self.assertFalse(packet["readonly_sources"]["accounts_readonly_ok"])
        self.assertTrue(packet["readonly_sources"]["api_readonly_ok"])
        self.assertFalse(packet["recovery_live_ready"])
        self.assertFalse(packet["operator_ready_claimed"])

    def test_codex_custom_recovery_operator_ready_endpoint_is_bounded_matrix(self) -> None:
        payloads = live_payloads()
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/operator-ready")
                )
                forbidden = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/operator-ready"
                        "?pid=123&path=/tmp/raw&auth=raw"
                    )
                )
                try:
                    post_json(f"{base}/api/codex/custom/recovery/operator-ready", {})
                    post_status = HTTPStatus.OK
                except urllib.error.HTTPError as exc:
                    post_status = HTTPStatus(exc.code)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_READY",
        )
        self.assertTrue(packet["operator_recovery_matrix_complete"])
        self.assertTrue(packet["session_recovery_actions_classified"])
        self.assertTrue(packet["rollback_lifecycle_actions_classified"])
        self.assertTrue(packet["dangerous_actions_disabled_or_preflight_only"])
        self.assertTrue(packet["process_kill_live_not_admitted_without_owned_target"])
        self.assertTrue(packet["diagnostics_export_redacted"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertFalse(packet["production_ready"])
        self.assertEqual(forbidden["status"], "blocked")
        self.assertEqual(
            forbidden["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_BROWSER_FIELD_REJECTED",
        )
        self.assertTrue(forbidden["browser_forbidden_fields_rejected"])
        self.assertIn("path", forbidden["forbidden_fields"])
        self.assertIn("pid", forbidden["forbidden_fields"])
        self.assertIn("auth", forbidden["forbidden_fields"])
        self.assertEqual(post_status, HTTPStatus.NOT_FOUND)

    def test_codex_custom_recovery_admitted_session_actions_endpoint_is_bounded(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                blocked = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/admitted-session-actions")
                )
                preflight_blocked = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight")
                )
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                ready = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/admitted-session-actions")
                )
                preflight_ready = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight")
                )
                preflight_with_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/stop-cleanup/preflight"
                        "?session_id=browser&path=/forbidden&pid=123&auth=browser"
                    )
                )
                preflight_blank_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/stop-cleanup/preflight"
                        "?session_id=&path=&pid=&auth="
                    )
                )
                session_id = created["session"]["session_id"]
                cancel = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions/{session_id}/cancel", {})
                )
                cleanup = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions/{session_id}/cleanup", {})
                )
                after_cleanup = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/admitted-session-actions")
                )
                preflight_after_cleanup = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight")
                )
                try:
                    post_json(f"{base}/api/codex/custom/recovery/admitted-session-actions", {})
                except urllib.error.HTTPError as exc:
                    post_rejected_status = exc.code
                else:  # pragma: no cover - defensive assertion branch
                    post_rejected_status = HTTPStatus.OK
                try:
                    post_json(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight", {})
                except urllib.error.HTTPError as exc:
                    preflight_post_rejected_status = exc.code
                else:  # pragma: no cover - defensive assertion branch
                    preflight_post_rejected_status = HTTPStatus.OK
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["block_reason_code"], "SELECTED_SESSION_REQUIRED")
        self.assertFalse(blocked["session_admitted_actions_ready"])
        self.assertEqual(preflight_blocked["status"], "blocked")
        self.assertEqual(
            preflight_blocked["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NO_SESSION",
        )
        self.assertFalse(preflight_blocked["stop_cleanup_preflight_ready"])
        self.assertFalse(preflight_blocked["filesystem_write_performed"])
        self.assertFalse(preflight_blocked["session_cancel_performed"])
        self.assertFalse(preflight_blocked["owned_cleanup_performed"])
        self.assertFalse(preflight_blocked["process_kill_performed"])
        self.assertEqual(ready["status"], "ok")
        self.assertEqual(ready["machine_error_code"], "ADMITTED_SESSION_ACTIONS_READY")
        self.assertTrue(ready["session_admitted_actions_ready"])
        self.assertTrue(ready["selected_session_cancel_ready"])
        self.assertTrue(ready["owned_session_cleanup_ready"])
        self.assertTrue(ready["selected_session_packet_valid"])
        self.assertFalse(ready["contract_endpoint_mutation_allowed"])
        self.assertFalse(ready["browser_payload_allowed"])
        self.assertEqual(ready["browser_payload_allowed_keys"], [])
        self.assertIn("backend_id", ready["forbidden_browser_fields"])
        self.assertFalse(ready["recovery_operator_ready"])
        self.assertFalse(ready["rollback_operator_ready"])
        self.assertFalse(ready["process_kill_operator_ready"])
        self.assertFalse(ready["diagnostics_counted_as_recovery_action"])
        self.assertFalse(ready["readonly_checks_counted_as_mutation"])
        self.assertFalse(ready["session_create_counted_as_recovery_action"])
        self.assertFalse(ready["current_codex_touched"])
        self.assertFalse(ready["current_codex_home_touched"])
        self.assertFalse(ready["arbitrary_path_accepted"])
        self.assertTrue(ready["dangerous_actions_disabled"])
        self.assertFalse(ready["dangerous_action_mutation_allowed"])
        self.assertEqual(preflight_ready["status"], "ok")
        self.assertEqual(
            preflight_ready["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_READY",
        )
        self.assertEqual(
            preflight_ready["verified_scope"],
            "owned_custom_session_stop_cleanup_preflight_only",
        )
        self.assertEqual(
            preflight_ready["contract_source_endpoint"],
            "/api/codex/custom/recovery/admitted-session-actions",
        )
        self.assertTrue(preflight_ready["stop_cleanup_preflight_ready"])
        self.assertEqual(
            preflight_ready["selected_session_source"],
            "server_selected_latest_owned_custom_session",
        )
        self.assertTrue(preflight_ready["selected_session_id_redacted"])
        self.assertNotIn("selected_session_id", preflight_ready)
        self.assertTrue(preflight_ready["selected_session_cancel_ready"])
        self.assertTrue(preflight_ready["owned_session_cleanup_ready"])
        self.assertFalse(preflight_ready["process_kill_ready"])
        self.assertFalse(preflight_ready["process_kill_performed"])
        self.assertFalse(preflight_ready["session_cancel_performed"])
        self.assertFalse(preflight_ready["owned_cleanup_performed"])
        self.assertTrue(preflight_ready["filesystem_read_performed"])
        self.assertFalse(preflight_ready["filesystem_write_performed"])
        self.assertFalse(preflight_ready["current_codex_touched"])
        self.assertFalse(preflight_ready["original_codex_touched"])
        self.assertFalse(preflight_ready["auth_material_touched"])
        self.assertFalse(preflight_ready["secret_value_recorded"])
        self.assertFalse(preflight_ready["recovery_operator_ready"])
        self.assertFalse(preflight_ready["rollback_live_ready"])
        self.assertEqual(
            preflight_ready["human_summary"],
            "stop/cleanup preflight verified · no action performed",
        )
        self.assertEqual(preflight_with_query["status"], "blocked")
        self.assertEqual(
            preflight_with_query["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_BROWSER_FIELD_REJECTED",
        )
        self.assertFalse(preflight_with_query["filesystem_read_performed"])
        for field in ("session_id", "path", "pid", "auth"):
            self.assertIn(field, preflight_with_query["forbidden_fields"])
        self.assertEqual(preflight_blank_query["status"], "blocked")
        self.assertEqual(
            preflight_blank_query["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_BROWSER_FIELD_REJECTED",
        )
        self.assertFalse(preflight_blank_query["filesystem_read_performed"])
        for field in ("session_id", "path", "pid", "auth"):
            self.assertIn(field, preflight_blank_query["forbidden_fields"])
        self.assertTrue(cancel["cancelled"])
        self.assertFalse(cancel["process_kill_claimed"])
        self.assertTrue(cleanup["cleanup_performed"])
        self.assertTrue(cleanup["owned_session_root_only"])
        self.assertFalse(cleanup["arbitrary_path_accepted"])
        self.assertEqual(after_cleanup["status"], "blocked")
        self.assertEqual(after_cleanup["block_reason_code"], "SELECTED_SESSION_ALREADY_CLEANED")
        self.assertFalse(after_cleanup["session_admitted_actions_ready"])
        self.assertEqual(preflight_after_cleanup["status"], "blocked")
        self.assertEqual(
            preflight_after_cleanup["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_SESSION_ALREADY_CLEANED",
        )
        self.assertFalse(preflight_after_cleanup["stop_cleanup_preflight_ready"])
        self.assertFalse(preflight_after_cleanup["session_cancel_performed"])
        self.assertFalse(preflight_after_cleanup["owned_cleanup_performed"])
        self.assertFalse(preflight_after_cleanup["process_kill_performed"])
        self.assertEqual(post_rejected_status, HTTPStatus.NOT_FOUND)
        self.assertEqual(preflight_post_rejected_status, HTTPStatus.NOT_FOUND)

    def test_codex_custom_recovery_stop_cleanup_live_endpoint_is_bounded(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                no_session = json.loads(
                    post_json(f"{base}/api/codex/custom/recovery/stop-cleanup", {})
                )
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/recovery/stop-cleanup",
                        {"session_id": "", "path": "", "pid": "", "auth": ""},
                    )
                )
                still_ready = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight")
                )
                live = json.loads(
                    post_json(f"{base}/api/codex/custom/recovery/stop-cleanup", {})
                )
                after_live = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight")
                )
                session_id = created["session"]["session_id"]
                session_after_live = json.loads(
                    fetch(f"{base}/api/codex/custom/sessions/{session_id}")
                )
                try:
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup")
                except urllib.error.HTTPError as exc:
                    get_live_status = exc.code
                else:  # pragma: no cover - defensive assertion branch
                    get_live_status = HTTPStatus.OK
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(no_session["status"], "blocked")
        self.assertEqual(
            no_session["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NOT_READY",
        )
        self.assertFalse(no_session["session_cancel_performed"])
        self.assertFalse(no_session["owned_cleanup_performed"])
        self.assertFalse(no_session["filesystem_write_performed"])

        self.assertEqual(rejected["status"], "blocked")
        self.assertEqual(
            rejected["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_BROWSER_FIELD_REJECTED",
        )
        self.assertFalse(rejected["session_cancel_performed"])
        self.assertFalse(rejected["owned_cleanup_performed"])
        self.assertFalse(rejected["filesystem_write_performed"])
        for field in ("session_id", "path", "pid", "auth"):
            self.assertIn(field, rejected["forbidden_fields"])
        self.assertEqual(still_ready["status"], "ok")
        self.assertTrue(still_ready["stop_cleanup_preflight_ready"])

        self.assertEqual(live["status"], "ok")
        self.assertEqual(
            live["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_READY",
        )
        self.assertTrue(live["session_cancel_performed"])
        self.assertTrue(live["owned_cleanup_performed"])
        self.assertTrue(live["filesystem_write_performed"])
        self.assertEqual(
            live["verified_scope"],
            "owned_custom_session_cancel_and_cleanup_only",
        )
        self.assertEqual(
            live["declared_write_surface"],
            "owned_temp_session_root_cleanup_only",
        )
        self.assertTrue(live["preflight_verified"])
        self.assertTrue(live["selected_session_id_redacted"])
        self.assertTrue(live["raw_session_id_omitted"])
        self.assertNotIn("selected_session_id", live)
        self.assertNotIn("session_id", live)
        self.assertTrue(live["same_selected_session_ref"])
        self.assertTrue(live["session_cancel_performed"])
        self.assertTrue(live["session_cancel_verified"])
        self.assertTrue(live["owned_cleanup_performed"])
        self.assertTrue(live["owned_cleanup_verified"])
        self.assertTrue(live["owned_session_root_only"])
        self.assertFalse(live["arbitrary_path_cleanup_allowed"])
        self.assertFalse(live["arbitrary_path_accepted"])
        self.assertFalse(live["process_kill_ready"])
        self.assertFalse(live["process_kill_performed"])
        self.assertTrue(live["filesystem_write_performed"])
        self.assertEqual(live["filesystem_write_scope"], "owned_temp_session_root_cleanup_only")
        self.assertFalse(live["current_codex_touched"])
        self.assertFalse(live["original_codex_touched"])
        self.assertFalse(live["auth_material_touched"])
        self.assertFalse(live["secret_value_recorded"])
        self.assertFalse(live["rollback_live_ready"])
        self.assertFalse(live["recovery_operator_ready"])
        self.assertEqual(
            live["human_summary"],
            "owned session cancelled and cleaned · not system recovery",
        )
        self.assertEqual(after_live["status"], "blocked")
        self.assertEqual(
            after_live["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_SESSION_ALREADY_CLEANED",
        )
        self.assertEqual(session_after_live["session"]["cleanup_state"], "cleaned")
        self.assertEqual(session_after_live["session"]["cancel_state"], "cancelled_dry_run_session")
        self.assertEqual(get_live_status, HTTPStatus.NOT_FOUND)

    def test_codex_custom_recovery_stop_cleanup_live_allows_claim_gate_blocked_custom_status(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", FakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                contract = json.loads(fetch(f"{base}/api/codex/custom/recovery/contract"))
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                admitted = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/admitted-session-actions")
                )
                preflight = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/stop-cleanup/preflight")
                )
                live = json.loads(
                    post_json(f"{base}/api/codex/custom/recovery/stop-cleanup", {})
                )
                session_id = created["session"]["session_id"]
                session_after_live = json.loads(
                    fetch(f"{base}/api/codex/custom/sessions/{session_id}")
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(contract["status"], "blocked")
        self.assertEqual(
            contract["contract_block_reason_code"],
            "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
        )
        self.assertTrue(contract["readonly_sources"]["original_status_ok"])
        self.assertFalse(contract["readonly_sources"]["custom_status_ok"])
        self.assertTrue(contract["readonly_sources"]["accounts_readonly_ok"])
        self.assertTrue(contract["readonly_sources"]["api_readonly_ok"])

        self.assertEqual(admitted["status"], "blocked")
        self.assertEqual(admitted["machine_error_code"], "ADMITTED_SESSION_ACTIONS_BLOCKED")
        self.assertEqual(
            admitted["block_reason_code"],
            "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
        )
        self.assertFalse(admitted["session_admitted_actions_ready"])
        self.assertTrue(admitted["selected_session_present"])
        self.assertTrue(admitted["selected_session_packet_valid"])
        self.assertFalse(admitted["selected_session_cancel_ready"])
        self.assertFalse(admitted["owned_session_cleanup_ready"])
        self.assertFalse(admitted["readonly_sources"]["custom_status_ok"])

        self.assertEqual(preflight["status"], "blocked")
        self.assertEqual(
            preflight["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_SOURCE_BLOCKED",
        )
        self.assertFalse(preflight["stop_cleanup_preflight_ready"])

        self.assertEqual(live["status"], "blocked")
        self.assertEqual(
            live["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NOT_READY",
        )
        self.assertFalse(live["session_cancel_performed"])
        self.assertFalse(live["owned_cleanup_performed"])
        self.assertFalse(live["filesystem_write_performed"])
        self.assertEqual(session_after_live["session"]["cleanup_state"], "not_cleaned")
        self.assertEqual(session_after_live["session"]["cancel_state"], "not_cancelled")

    def test_codex_custom_recovery_process_kill_preflight_endpoint_is_readonly(self) -> None:
        payloads = live_payloads()
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                no_session = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/process-kill/preflight")
                )
                query_rejected = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/process-kill/preflight"
                        "?pid=123&process_id=456&session_id=browser&path=/bad"
                        "&HOME=/bad&CODEX_HOME=/bad&auth=secret&token=secret"
                    )
                )
                blank_query_rejected = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/process-kill/preflight"
                        "?pid=&process_id=&session_id=&path=&HOME=&CODEX_HOME=&auth=&token="
                    )
                )
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                no_candidate = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/process-kill/preflight")
                )
                session_id = created["session"]["session_id"]
                session_after_preflight = json.loads(
                    fetch(f"{base}/api/codex/custom/sessions/{session_id}")
                )
                try:
                    post_json(f"{base}/api/codex/custom/recovery/process-kill/preflight", {})
                except urllib.error.HTTPError as exc:
                    post_preflight_status = exc.code
                else:  # pragma: no cover - defensive assertion branch
                    post_preflight_status = HTTPStatus.OK
                try:
                    post_json(f"{base}/api/codex/custom/recovery/process-kill", {})
                except urllib.error.HTTPError as exc:
                    post_live_status = exc.code
                else:  # pragma: no cover - defensive assertion branch
                    post_live_status = HTTPStatus.OK
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(no_session["status"], "blocked")
        self.assertEqual(
            no_session["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SOURCE_NOT_READY",
        )
        self.assertFalse(no_session["process_kill_preflight_ready"])
        self.assertFalse(no_session["process_kill_performed"])
        self.assertFalse(no_session["filesystem_write_performed"])

        for rejected in (query_rejected, blank_query_rejected):
            self.assertEqual(rejected["status"], "blocked")
            self.assertEqual(
                rejected["machine_error_code"],
                "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_BROWSER_FIELD_REJECTED",
            )
            self.assertFalse(rejected["filesystem_read_performed"])
            self.assertFalse(rejected["process_kill_performed"])
            for field in (
                "pid",
                "process_id",
                "session_id",
                "path",
                "HOME",
                "CODEX_HOME",
                "auth",
                "token",
            ):
                self.assertIn(field, rejected["forbidden_fields"])

        self.assertEqual(no_candidate["status"], "blocked")
        self.assertEqual(
            no_candidate["machine_error_code"],
            "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NO_PROCESS_CANDIDATE",
        )
        self.assertEqual(
            no_candidate["claim_scope"],
            "custom_codex_recovery_process_kill_preflight_only",
        )
        self.assertFalse(no_candidate["contract_endpoint_mutation_allowed"])
        self.assertFalse(no_candidate["browser_payload_allowed"])
        self.assertEqual(no_candidate["browser_payload_allowed_keys"], [])
        self.assertTrue(no_candidate["selected_session_id_redacted"])
        self.assertTrue(no_candidate["raw_session_id_omitted"])
        self.assertNotIn("selected_session_id", no_candidate)
        self.assertNotIn("session_id", no_candidate)
        self.assertFalse(no_candidate["process_kill_eligible"])
        self.assertFalse(no_candidate["process_kill_preflight_ready"])
        self.assertFalse(no_candidate["process_kill_ready"])
        self.assertFalse(no_candidate["process_kill_performed"])
        self.assertFalse(no_candidate["process_kill_live_ready"])
        self.assertFalse(no_candidate["process_kill_admitted"])
        self.assertFalse(no_candidate["process_kill_claimed"])
        self.assertFalse(no_candidate["current_codex_process_candidate"])
        self.assertFalse(no_candidate["original_codex_process_candidate"])
        self.assertFalse(no_candidate["filesystem_write_performed"])
        self.assertFalse(no_candidate["current_codex_touched"])
        self.assertFalse(no_candidate["original_codex_touched"])
        self.assertFalse(no_candidate["auth_material_touched"])
        self.assertFalse(no_candidate["recovery_operator_ready"])
        self.assertTrue(no_candidate["dangerous_actions_disabled"])
        self.assertFalse(no_candidate["dangerous_action_mutation_allowed"])
        self.assertEqual(session_after_preflight["session"]["cleanup_state"], "not_cleaned")
        self.assertEqual(session_after_preflight["session"]["cancel_state"], "not_cancelled")
        self.assertEqual(post_preflight_status, HTTPStatus.NOT_FOUND)
        self.assertEqual(post_live_status, HTTPStatus.NOT_FOUND)

    def test_codex_custom_recovery_rollback_process_owner_contract_endpoint_is_dry_run_only(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(live_payloads())),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/rollback-process-owner-contract")
                )
                forbidden_posts: dict[str, int] = {}
                for suffix in (
                    "rollback-process-owner-contract",
                    "rollback",
                    "kill",
                    "cleanup-path",
                    "snapshot",
                ):
                    try:
                        post_json(f"{base}/api/codex/custom/recovery/{suffix}", {})
                    except urllib.error.HTTPError as exc:
                        forbidden_posts[suffix] = exc.code
                    else:  # pragma: no cover - defensive assertion branch
                        forbidden_posts[suffix] = HTTPStatus.OK
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT")
        self.assertEqual(
            packet["claim_scope"],
            "custom_codex_recovery_rollback_process_owner_dry_run_contract_only",
        )
        self.assertTrue(packet["rollback_contract_defined"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertTrue(packet["rollback_point_required"])
        self.assertFalse(packet["rollback_point_present"])
        self.assertTrue(packet["rollback_write_surfaces_required"])
        self.assertFalse(packet["rollback_write_surfaces_declared"])
        self.assertTrue(packet["rollback_verification_packet_required"])
        self.assertFalse(packet["rollback_verification_packet_present"])
        self.assertTrue(packet["process_owner_contract_defined"])
        self.assertFalse(packet["process_kill_live_ready"])
        self.assertFalse(packet["process_kill_admitted"])
        self.assertTrue(packet["owned_process_identity_required"])
        self.assertFalse(packet["owned_process_identity_present"])
        self.assertTrue(packet["current_codex_process_exclusion_required"])
        self.assertFalse(packet["current_codex_process_excluded"])
        self.assertFalse(packet["current_codex_process_candidate"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_operator_ready"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertFalse(packet["diagnostics_counted_as_recovery_action"])
        self.assertFalse(packet["readonly_checks_counted_as_mutation"])
        self.assertFalse(packet["session_create_counted_as_recovery_action"])
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        self.assertIn("pid", packet["forbidden_browser_fields"])
        self.assertIn("process_id", packet["forbidden_browser_fields"])
        self.assertIn("path", packet["forbidden_browser_fields"])
        self.assertFalse(packet["arbitrary_path_accepted"])
        self.assertFalse(packet["arbitrary_process_kill_allowed"])
        self.assertFalse(packet["arbitrary_path_cleanup_allowed"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertFalse(packet["dangerous_action_mutation_allowed"])
        prerequisites = {item["id"]: item for item in packet["prerequisites"]}
        self.assertFalse(prerequisites["rollback_point"]["present"])
        self.assertTrue(prerequisites["rollback_point"]["blocks_live_ready"])
        self.assertFalse(prerequisites["rollback_point"]["blocks_contract_definition"])
        self.assertEqual(packet["next_contour"], "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS")
        self.assertFalse(packet["next_contour_claimed"])
        self.assertEqual(
            forbidden_posts,
            {
                "rollback-process-owner-contract": HTTPStatus.NOT_FOUND,
                "rollback": HTTPStatus.NOT_FOUND,
                "kill": HTTPStatus.NOT_FOUND,
                "cleanup-path": HTTPStatus.NOT_FOUND,
                "snapshot": HTTPStatus.NOT_FOUND,
            },
        )

    def test_codex_custom_recovery_rollback_point_dry_run_endpoint_is_readonly(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(live_payloads())),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/rollback-point-dry-run")
                )
                forbidden_posts: dict[str, int] = {}
                for suffix in (
                    "rollback-point-dry-run",
                    "snapshot",
                    "rollback",
                    "apply",
                    "cleanup-path",
                    "kill",
                ):
                    try:
                        post_json(f"{base}/api/codex/custom/recovery/{suffix}", {})
                    except urllib.error.HTTPError as exc:
                        forbidden_posts[suffix] = exc.code
                    else:  # pragma: no cover - defensive assertion branch
                        forbidden_posts[suffix] = HTTPStatus.OK
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_DRY_RUN_CONTRACT")
        self.assertEqual(packet["claim_scope"], "custom_codex_recovery_rollback_point_dry_run_only")
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        for forbidden_field in (
            "path",
            "snapshot_path",
            "rollback_target",
            "pid",
            "process_id",
            "CODEX_HOME",
            "HOME",
        ):
            self.assertIn(forbidden_field, packet["forbidden_browser_fields"])
        self.assertTrue(packet["rollback_point_contract_defined"])
        self.assertFalse(packet["rollback_point_present"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertTrue(packet["rollback_write_surfaces_contract_defined"])
        self.assertFalse(packet["rollback_write_surfaces_machine_checked"])
        self.assertTrue(packet["rollback_write_surfaces_dry_run_checked"])
        self.assertTrue(packet["rollback_verification_packet_defined"])
        self.assertFalse(packet["rollback_verification_packet_present"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_operator_ready"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertFalse(packet["process_kill_live_ready"])
        self.assertFalse(packet["process_kill_admitted"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["snapshot_create_admitted"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["current_codex_home_touched"])
        self.assertFalse(packet["current_codex_home_allowed_surface"])
        self.assertFalse(packet["auth_material_allowed_surface"])
        self.assertFalse(packet["arbitrary_path_accepted"])
        self.assertFalse(packet["arbitrary_path_allowed_surface"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertFalse(packet["dangerous_action_mutation_allowed"])
        self.assertEqual(
            packet["allowed_write_surface_ids"],
            [
                "owned_temp_session_root",
                "owned_wbp_runtime_state",
                "owned_generated_recovery_artifact",
            ],
        )
        for forbidden_surface in (
            "current_codex_home",
            "current_codex_process",
            "auth_material",
            "arbitrary_path",
        ):
            self.assertIn(forbidden_surface, packet["forbidden_surfaces"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertFalse(actions["rollback_point_create"]["mutation_allowed"])
        self.assertFalse(actions["rollback_point_create"]["browser_payload_allowed"])
        self.assertFalse(actions["rollback_point_create"]["admitted"])
        self.assertFalse(actions["rollback_apply"]["mutation_allowed"])
        self.assertFalse(actions["rollback_apply"]["admitted"])
        self.assertEqual(
            packet["next_contour"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS",
        )
        self.assertFalse(packet["next_contour_claimed"])
        self.assertEqual(
            forbidden_posts,
            {
                "rollback-point-dry-run": HTTPStatus.NOT_FOUND,
                "snapshot": HTTPStatus.NOT_FOUND,
                "rollback": HTTPStatus.NOT_FOUND,
                "apply": HTTPStatus.NOT_FOUND,
                "cleanup-path": HTTPStatus.NOT_FOUND,
                "kill": HTTPStatus.NOT_FOUND,
            },
        )

    def test_codex_custom_recovery_rollback_point_create_admission_endpoint_allows_bounded_create(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", ReadyFakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(live_payloads())),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                packet = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/rollback-point-create-admission")
                )
                forbidden_posts: dict[str, int] = {}
                for suffix in (
                    "rollback-point-create-admission",
                    "rollback-point/verify",
                    "rollback-apply/admission-dry-run",
                    "rollback-apply/live-preflight",
                    "rollback-apply/receipt/verify",
                    "snapshot",
                    "rollback",
                    "apply",
                    "cleanup-path",
                    "kill",
                ):
                    try:
                        post_json(f"{base}/api/codex/custom/recovery/{suffix}", {})
                    except urllib.error.HTTPError as exc:
                        forbidden_posts[suffix] = exc.code
                    else:  # pragma: no cover - defensive assertion branch
                        forbidden_posts[suffix] = HTTPStatus.OK
                create_packet = json.loads(
                    post_json(f"{base}/api/codex/custom/recovery/rollback-point", {})
                )
                rejected_create = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/recovery/rollback-point",
                        {"path": "/tmp/forbidden", "session_id": "ccs-forbidden"},
                    )
                )
                non_object_create_status, non_object_create = post_body_response(
                    f"{base}/api/codex/custom/recovery/rollback-point",
                    b"[]",
                )
                verify_packet = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/rollback-point/verify")
                )
                verify_with_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/rollback-point/verify"
                        "?artifact_id=browser&path=/tmp/forbidden&digest=browser"
                    )
                )
                apply_admission_packet = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/admission-dry-run"
                    )
                )
                apply_admission_with_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/admission-dry-run"
                        "?artifact_id=browser&path=/tmp/forbidden&digest=browser"
                    )
                )
                apply_preflight_packet = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/live-preflight"
                    )
                )
                apply_preflight_with_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/live-preflight"
                        "?artifact_id=browser&artifact_path=/tmp/artifact"
                        "&path=/tmp/forbidden&digest=browser&session_id=ccs-browser"
                        "&backend_id=browser-backend&route_id=browser-route"
                        "&CODEX_HOME=/tmp/codex&HOME=/tmp/home"
                        "&auth=browser-auth&token=browser-token"
                        "&api_key=browser-key&secret=browser-secret"
                    )
                )
                apply_packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/recovery/rollback-apply",
                        {},
                    )
                )
                apply_with_payload = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/recovery/rollback-apply",
                        {
                            "artifact_id": "browser",
                            "artifact_path": "/tmp/artifact",
                            "path": "/tmp/forbidden",
                            "snapshot_path": "/tmp/snapshot",
                            "rollback_target": "/tmp/target",
                            "digest": "browser",
                            "session_id": "ccs-browser",
                            "backend_id": "browser-backend",
                            "route_id": "browser-route",
                            "pid": "123",
                            "process_id": "456",
                            "CODEX_HOME": "/tmp/codex",
                            "HOME": "/tmp/home",
                            "auth": "browser-auth",
                            "token": "browser-token",
                            "api_key": "browser-key",
                            "secret": "browser-secret",
                        },
                    )
                )
                non_object_apply_status, non_object_apply = post_body_response(
                    f"{base}/api/codex/custom/recovery/rollback-apply",
                    b"[]",
                )
                receipt_verify_packet = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/receipt/verify"
                    )
                )
                receipt_verify_with_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/receipt/verify"
                        "?receipt_id=browser&receipt_path=/tmp/receipt"
                        "&artifact_id=browser&artifact_path=/tmp/artifact"
                        "&path=/tmp/forbidden&snapshot_path=/tmp/snapshot"
                        "&rollback_target=/tmp/target&digest=browser"
                        "&session_id=ccs-browser&backend_id=browser-backend"
                        "&route_id=browser-route&pid=123&process_id=456"
                        "&CODEX_HOME=/tmp/codex&HOME=/tmp/home"
                        "&auth=browser-auth&token=browser-token"
                        "&api_key=browser-key&secret=browser-secret"
                    )
                )
                receipt_verify_blank_query = json.loads(
                    fetch(
                        f"{base}/api/codex/custom/recovery/"
                        "rollback-apply/receipt/verify"
                        "?backend_id=&session_id=&auth=&path="
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_CREATE_ADMISSION_READY")
        self.assertEqual(
            packet["claim_scope"],
            "custom_codex_recovery_rollback_point_create_admission_only",
        )
        self.assertTrue(packet["rollback_point_dry_run_contract_valid"])
        self.assertTrue(packet["rollback_point_create_admission_defined"])
        self.assertTrue(packet["rollback_point_create_admitted"])
        self.assertEqual(packet["rollback_point_create_admitted_scope"], "next_contour_only")
        self.assertFalse(packet["rollback_point_create_admitted_for_current_contour"])
        self.assertFalse(packet["rollback_point_create_performed"])
        self.assertFalse(packet["rollback_point_created"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertTrue(packet["write_surface_machine_check_performed"])
        self.assertTrue(packet["write_surfaces_all_eligible"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        for forbidden_field in (
            "path",
            "snapshot_path",
            "rollback_target",
            "pid",
            "process_id",
            "CODEX_HOME",
            "HOME",
        ):
            self.assertIn(forbidden_field, packet["forbidden_browser_fields"])
        self.assertEqual(
            packet["allowed_write_surface_ids"],
            [
                "owned_temp_session_root",
                "owned_wbp_runtime_state",
                "owned_generated_recovery_artifact",
            ],
        )
        for surface in packet["allowed_write_surfaces"]:
            self.assertTrue(surface["machine_check_performed"])
            self.assertFalse(surface["filesystem_write_performed"])
            self.assertFalse(surface["write_admitted_for_current_contour"])
            self.assertTrue(surface["eligible_for_next_contour"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertTrue(actions["rollback_point_create"]["admitted"])
        self.assertFalse(actions["rollback_point_create"]["admitted_for_current_contour"])
        self.assertFalse(actions["rollback_point_create"]["mutation_allowed"])
        self.assertFalse(actions["rollback_point_create"]["performed"])
        self.assertFalse(actions["rollback_apply"]["admitted"])
        self.assertEqual(
            packet["result_token"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_READY",
        )
        self.assertFalse(packet["next_contour_claimed"])
        self.assertEqual(
            forbidden_posts,
            {
                "rollback-point-create-admission": HTTPStatus.NOT_FOUND,
                "rollback-point/verify": HTTPStatus.NOT_FOUND,
                "rollback-apply/admission-dry-run": HTTPStatus.NOT_FOUND,
                "rollback-apply/live-preflight": HTTPStatus.NOT_FOUND,
                "rollback-apply/receipt/verify": HTTPStatus.NOT_FOUND,
                "snapshot": HTTPStatus.NOT_FOUND,
                "rollback": HTTPStatus.NOT_FOUND,
                "apply": HTTPStatus.NOT_FOUND,
                "cleanup-path": HTTPStatus.NOT_FOUND,
                "kill": HTTPStatus.NOT_FOUND,
            },
        )
        self.assertEqual(create_packet["status"], "ok")
        self.assertEqual(create_packet["machine_error_code"], "ROLLBACK_POINT_CREATE_LIVE_READY")
        self.assertEqual(
            create_packet["claim_scope"],
            "custom_codex_recovery_rollback_point_create_live_only",
        )
        self.assertEqual(
            create_packet["result_token"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_READY",
        )
        self.assertTrue(create_packet["rollback_point_create_admission_valid"])
        self.assertTrue(create_packet["rollback_point_create_admitted_for_current_contour"])
        self.assertTrue(create_packet["rollback_point_create_performed"])
        self.assertTrue(create_packet["rollback_point_created"])
        self.assertTrue(create_packet["filesystem_write_performed"])
        self.assertEqual(create_packet["filesystem_write_scope"], "owned_generated_recovery_artifact")
        self.assertTrue(create_packet["rollback_point_artifact_path_redacted"])
        self.assertTrue(create_packet["rollback_point_artifact_digest_present"])
        self.assertRegex(create_packet["rollback_point_artifact_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("/tmp/", json.dumps(create_packet))
        self.assertFalse(create_packet["snapshot_file_created"])
        self.assertFalse(create_packet["rollback_apply_admitted"])
        self.assertFalse(create_packet["rollback_apply_performed"])
        self.assertFalse(create_packet["rollback_completed"])
        self.assertFalse(create_packet["rollback_live_ready"])
        self.assertFalse(create_packet["recovery_operator_ready"])
        self.assertFalse(create_packet["current_codex_touched"])
        self.assertFalse(create_packet["original_codex_touched"])
        self.assertFalse(create_packet["auth_material_touched"])
        self.assertFalse(create_packet["secret_value_recorded"])
        self.assertEqual(rejected_create["status"], "blocked")
        self.assertEqual(
            rejected_create["machine_error_code"],
            "ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
        )
        self.assertIn("path", rejected_create["forbidden_fields"])
        self.assertIn("session_id", rejected_create["forbidden_fields"])
        self.assertFalse(rejected_create["filesystem_write_performed"])
        self.assertEqual(non_object_create_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(non_object_create["status"], "rejected")
        self.assertEqual(
            non_object_create["machine_error_code"],
            "WEB_INGRESS_JSON_OBJECT_REQUIRED",
        )
        self.assertEqual(non_object_create["source"], "web_ingress")
        self.assertEqual(non_object_create["changed_files"], [])
        self.assertEqual(verify_packet["status"], "ok")
        self.assertEqual(verify_packet["machine_error_code"], "ROLLBACK_POINT_VERIFY_READY")
        self.assertEqual(
            verify_packet["claim_scope"],
            "custom_codex_recovery_rollback_point_verify_only",
        )
        self.assertEqual(
            verify_packet["result_token"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_READY",
        )
        self.assertTrue(verify_packet["rollback_point_verify_performed"])
        self.assertTrue(verify_packet["rollback_point_verified"])
        self.assertEqual(
            verify_packet["rollback_point_selection_source"],
            "server_owned_latest_valid_artifact",
        )
        self.assertFalse(verify_packet["rollback_point_selection_ambiguous"])
        self.assertTrue(verify_packet["rollback_point_artifact_path_redacted"])
        self.assertTrue(verify_packet["rollback_point_digest_verified"])
        self.assertTrue(verify_packet["rollback_point_provenance_verified"])
        self.assertTrue(verify_packet["rollback_point_schema_valid"])
        self.assertTrue(verify_packet["rollback_point_kind_valid"])
        self.assertTrue(verify_packet["rollback_point_surface_verified"])
        self.assertTrue(verify_packet["filesystem_read_performed"])
        self.assertEqual(verify_packet["filesystem_read_scope"], "owned_generated_recovery_artifact")
        self.assertFalse(verify_packet["filesystem_write_performed"])
        self.assertFalse(verify_packet["rollback_apply_admitted"])
        self.assertFalse(verify_packet["rollback_apply_ready"])
        self.assertFalse(verify_packet["rollback_apply_performed"])
        self.assertFalse(verify_packet["rollback_completed"])
        self.assertFalse(verify_packet["rollback_live_ready"])
        self.assertFalse(verify_packet["recovery_operator_ready"])
        self.assertFalse(verify_packet["current_codex_touched"])
        self.assertFalse(verify_packet["original_codex_touched"])
        self.assertFalse(verify_packet["auth_material_touched"])
        self.assertFalse(verify_packet["secret_value_recorded"])
        self.assertIn("artifact_id", verify_packet["forbidden_browser_fields"])
        self.assertIn("digest", verify_packet["forbidden_browser_fields"])
        self.assertNotIn("/tmp/", json.dumps(verify_packet))
        self.assertEqual(verify_with_query["status"], "blocked")
        self.assertEqual(
            verify_with_query["machine_error_code"],
            "ROLLBACK_POINT_VERIFY_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("artifact_id", verify_with_query["forbidden_fields"])
        self.assertIn("path", verify_with_query["forbidden_fields"])
        self.assertIn("digest", verify_with_query["forbidden_fields"])
        self.assertFalse(verify_with_query["filesystem_read_performed"])
        self.assertEqual(apply_admission_packet["status"], "ok")
        self.assertEqual(
            apply_admission_packet["machine_error_code"],
            "ROLLBACK_APPLY_ADMISSION_DRY_RUN_EVALUATED",
        )
        self.assertEqual(
            apply_admission_packet["claim_scope"],
            "custom_codex_recovery_rollback_apply_admission_dry_run_only",
        )
        self.assertTrue(apply_admission_packet["rollback_apply_admission_evaluated"])
        self.assertEqual(
            apply_admission_packet["rollback_apply_admission_result"],
            "eligible_for_next_contour",
        )
        self.assertTrue(apply_admission_packet["rollback_point_verify_valid"])
        self.assertTrue(apply_admission_packet["rollback_point_verified"])
        self.assertTrue(apply_admission_packet["rollback_point_manifest_verified"])
        self.assertTrue(apply_admission_packet["rollback_point_provenance_verified"])
        self.assertTrue(apply_admission_packet["rollback_point_digest_verified"])
        self.assertTrue(apply_admission_packet["rollback_point_surface_verified"])
        self.assertTrue(apply_admission_packet["recovery_contract_readonly_sources_ok"])
        self.assertTrue(apply_admission_packet["rollback_process_owner_contract_ok"])
        self.assertTrue(apply_admission_packet["session_state_read_performed"])
        self.assertFalse(apply_admission_packet["filesystem_read_performed"])
        self.assertFalse(apply_admission_packet["filesystem_write_performed"])
        self.assertFalse(apply_admission_packet["rollback_apply_admitted"])
        self.assertFalse(apply_admission_packet["rollback_apply_ready"])
        self.assertFalse(apply_admission_packet["rollback_apply_performed"])
        self.assertFalse(apply_admission_packet["rollback_completed"])
        self.assertFalse(apply_admission_packet["rollback_live_ready"])
        self.assertFalse(apply_admission_packet["process_kill_performed"])
        self.assertFalse(apply_admission_packet["recovery_operator_ready"])
        self.assertFalse(apply_admission_packet["current_codex_touched"])
        self.assertFalse(apply_admission_packet["original_codex_touched"])
        self.assertFalse(apply_admission_packet["auth_material_touched"])
        self.assertFalse(apply_admission_packet["secret_value_recorded"])
        self.assertNotIn("/tmp/", json.dumps(apply_admission_packet))
        self.assertEqual(apply_admission_with_query["status"], "blocked")
        self.assertEqual(
            apply_admission_with_query["machine_error_code"],
            "ROLLBACK_APPLY_ADMISSION_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("artifact_id", apply_admission_with_query["forbidden_fields"])
        self.assertIn("path", apply_admission_with_query["forbidden_fields"])
        self.assertIn("digest", apply_admission_with_query["forbidden_fields"])
        self.assertFalse(apply_admission_with_query["filesystem_read_performed"])
        self.assertFalse(apply_admission_with_query["filesystem_write_performed"])
        self.assertEqual(apply_preflight_packet["status"], "ok")
        self.assertEqual(
            apply_preflight_packet["machine_error_code"],
            "ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED",
        )
        self.assertEqual(
            apply_preflight_packet["claim_scope"],
            "custom_codex_recovery_rollback_apply_live_preflight_only",
        )
        self.assertTrue(apply_preflight_packet["rollback_apply_live_preflight_evaluated"])
        self.assertEqual(
            apply_preflight_packet["rollback_apply_live_preflight_result"],
            "eligible_for_bounded_apply_contour",
        )
        self.assertTrue(apply_preflight_packet["rollback_apply_dry_run_eligible"])
        self.assertTrue(apply_preflight_packet["rollback_point_verified"])
        self.assertTrue(apply_preflight_packet["future_write_surfaces_declared"])
        self.assertTrue(apply_preflight_packet["future_write_surfaces_all_owned"])
        self.assertTrue(apply_preflight_packet["current_codex_excluded"])
        self.assertTrue(apply_preflight_packet["original_codex_excluded"])
        self.assertTrue(apply_preflight_packet["auth_material_excluded"])
        self.assertTrue(apply_preflight_packet["arbitrary_path_rejected"])
        self.assertTrue(apply_preflight_packet["process_kill_not_admitted"])
        self.assertTrue(apply_preflight_packet["source_filesystem_read_performed"])
        self.assertEqual(
            apply_preflight_packet["source_filesystem_read_scope"],
            "owned_generated_recovery_artifact",
        )
        self.assertTrue(apply_preflight_packet["filesystem_read_performed"])
        self.assertEqual(
            apply_preflight_packet["filesystem_read_scope"],
            "owned_generated_recovery_artifact",
        )
        self.assertFalse(apply_preflight_packet["filesystem_write_performed"])
        self.assertFalse(apply_preflight_packet["rollback_apply_admitted"])
        self.assertFalse(apply_preflight_packet["rollback_apply_ready"])
        self.assertFalse(apply_preflight_packet["rollback_apply_performed"])
        self.assertFalse(apply_preflight_packet["rollback_completed"])
        self.assertFalse(apply_preflight_packet["rollback_live_ready"])
        self.assertFalse(apply_preflight_packet["process_kill_performed"])
        self.assertFalse(apply_preflight_packet["recovery_operator_ready"])
        self.assertFalse(apply_preflight_packet["current_codex_touched"])
        self.assertFalse(apply_preflight_packet["original_codex_touched"])
        self.assertFalse(apply_preflight_packet["auth_material_touched"])
        self.assertFalse(apply_preflight_packet["secret_value_recorded"])
        self.assertNotIn("/tmp/", json.dumps(apply_preflight_packet))
        self.assertEqual(apply_preflight_with_query["status"], "blocked")
        self.assertEqual(
            apply_preflight_with_query["machine_error_code"],
            "ROLLBACK_APPLY_LIVE_PREFLIGHT_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("artifact_id", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("artifact_path", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("path", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("digest", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("session_id", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("backend_id", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("route_id", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("CODEX_HOME", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("HOME", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("auth", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("token", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("api_key", apply_preflight_with_query["forbidden_fields"])
        self.assertIn("secret", apply_preflight_with_query["forbidden_fields"])
        self.assertFalse(apply_preflight_with_query["source_filesystem_read_performed"])
        self.assertFalse(apply_preflight_with_query["filesystem_read_performed"])
        self.assertFalse(apply_preflight_with_query["filesystem_write_performed"])
        self.assertEqual(apply_packet["status"], "ok")
        self.assertEqual(
            apply_packet["machine_error_code"],
            "ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED",
        )
        self.assertEqual(
            apply_packet["claim_scope"],
            "custom_codex_recovery_rollback_apply_bounded_live_only",
        )
        self.assertTrue(apply_packet["rollback_apply_preflight_required"])
        self.assertTrue(apply_packet["rollback_apply_preflight_valid"])
        self.assertTrue(apply_packet["rollback_apply_bounded_live_performed"])
        self.assertTrue(apply_packet["rollback_apply_receipt_created"])
        self.assertTrue(apply_packet["rollback_apply_receipt_path_redacted"])
        self.assertTrue(apply_packet["rollback_apply_receipt_digest_present"])
        self.assertRegex(apply_packet["rollback_apply_receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(apply_packet["rollback_apply_receipt_provenance_verified"])
        self.assertTrue(apply_packet["rollback_apply_receipt_payload_digest_verified"])
        self.assertTrue(apply_packet["source_preflight_sha256_present"])
        self.assertTrue(apply_packet["rollback_point_verified"])
        self.assertTrue(apply_packet["filesystem_read_performed"])
        self.assertEqual(apply_packet["filesystem_read_scope"], "owned_generated_recovery_artifact")
        self.assertTrue(apply_packet["filesystem_write_performed"])
        self.assertEqual(apply_packet["filesystem_write_scope"], "owned_generated_recovery_artifact")
        self.assertTrue(apply_packet["rollback_apply_admitted"])
        self.assertTrue(apply_packet["rollback_apply_ready"])
        self.assertTrue(apply_packet["rollback_apply_performed"])
        self.assertEqual(
            apply_packet["rollback_apply_completed_scope"],
            "bounded_apply_receipt_only",
        )
        self.assertTrue(apply_packet["rollback_completed"])
        self.assertFalse(apply_packet["rollback_live_ready"])
        self.assertFalse(apply_packet["process_kill_performed"])
        self.assertFalse(apply_packet["recovery_operator_ready"])
        self.assertFalse(apply_packet["current_codex_touched"])
        self.assertFalse(apply_packet["original_codex_touched"])
        self.assertFalse(apply_packet["current_codex_home_touched"])
        self.assertFalse(apply_packet["auth_material_touched"])
        self.assertFalse(apply_packet["secret_value_recorded"])
        self.assertNotIn("/tmp/", json.dumps(apply_packet))
        actions = {action["id"]: action for action in apply_packet["actions"]}
        self.assertEqual(actions["rollback_apply"]["status"], "performed")
        self.assertEqual(
            actions["rollback_apply"]["completed_scope"],
            "bounded_apply_receipt_only",
        )
        self.assertFalse(actions["process_kill"]["performed"])
        self.assertEqual(apply_with_payload["status"], "blocked")
        self.assertEqual(
            apply_with_payload["machine_error_code"],
            "ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
        )
        for field in (
            "artifact_id",
            "artifact_path",
            "path",
            "snapshot_path",
            "rollback_target",
            "digest",
            "session_id",
            "backend_id",
            "route_id",
            "pid",
            "process_id",
            "CODEX_HOME",
            "HOME",
            "auth",
            "token",
            "api_key",
            "secret",
        ):
            self.assertIn(field, apply_with_payload["forbidden_fields"])
        self.assertFalse(apply_with_payload["filesystem_read_performed"])
        self.assertFalse(apply_with_payload["filesystem_write_performed"])
        self.assertFalse(apply_with_payload["rollback_apply_performed"])
        self.assertEqual(non_object_apply_status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(non_object_apply["status"], "rejected")
        self.assertEqual(
            non_object_apply["machine_error_code"],
            "WEB_INGRESS_JSON_OBJECT_REQUIRED",
        )
        self.assertEqual(non_object_apply["source"], "web_ingress")
        self.assertEqual(non_object_apply["changed_files"], [])
        self.assertEqual(receipt_verify_packet["status"], "ok")
        self.assertEqual(
            receipt_verify_packet["machine_error_code"],
            "ROLLBACK_APPLY_RECEIPT_VERIFY_READY",
        )
        self.assertEqual(
            receipt_verify_packet["claim_scope"],
            "custom_codex_recovery_rollback_apply_receipt_verify_only",
        )
        self.assertTrue(receipt_verify_packet["receipt_verify_performed"])
        self.assertTrue(receipt_verify_packet["receipt_verified"])
        self.assertTrue(receipt_verify_packet["rollback_apply_receipt_verified"])
        self.assertEqual(receipt_verify_packet["verified_scope"], "bounded_apply_receipt_only")
        self.assertEqual(
            receipt_verify_packet["receipt_selection_source"],
            "server_owned_latest_valid_receipt",
        )
        self.assertFalse(receipt_verify_packet["receipt_selection_ambiguous"])
        self.assertTrue(receipt_verify_packet["receipt_path_redacted"])
        self.assertTrue(receipt_verify_packet["receipt_digest_present"])
        self.assertTrue(receipt_verify_packet["receipt_payload_digest_verified"])
        self.assertTrue(receipt_verify_packet["receipt_provenance_verified"])
        self.assertTrue(receipt_verify_packet["source_preflight_sha256_present"])
        self.assertTrue(receipt_verify_packet["source_rollback_point_ref_present"])
        self.assertTrue(receipt_verify_packet["filesystem_read_performed"])
        self.assertEqual(
            receipt_verify_packet["filesystem_read_scope"],
            "owned_generated_recovery_artifact",
        )
        self.assertFalse(receipt_verify_packet["filesystem_write_performed"])
        self.assertFalse(receipt_verify_packet["rollback_apply_performed"])
        self.assertFalse(receipt_verify_packet["rollback_completed"])
        self.assertFalse(receipt_verify_packet["rollback_live_ready"])
        self.assertFalse(receipt_verify_packet["process_kill_performed"])
        self.assertFalse(receipt_verify_packet["recovery_operator_ready"])
        self.assertFalse(receipt_verify_packet["current_codex_touched"])
        self.assertFalse(receipt_verify_packet["original_codex_touched"])
        self.assertFalse(receipt_verify_packet["current_codex_home_touched"])
        self.assertFalse(receipt_verify_packet["auth_material_touched"])
        self.assertFalse(receipt_verify_packet["secret_value_recorded"])
        self.assertEqual(
            receipt_verify_packet["human_summary"],
            "receipt verified · not system recovery",
        )
        self.assertNotIn("/tmp/", json.dumps(receipt_verify_packet))
        self.assertEqual(receipt_verify_with_query["status"], "blocked")
        self.assertEqual(
            receipt_verify_with_query["machine_error_code"],
            "ROLLBACK_APPLY_RECEIPT_VERIFY_BROWSER_FIELD_REJECTED",
        )
        for field in (
            "receipt_id",
            "receipt_path",
            "artifact_id",
            "artifact_path",
            "path",
            "snapshot_path",
            "rollback_target",
            "digest",
            "session_id",
            "backend_id",
            "route_id",
            "pid",
            "process_id",
            "CODEX_HOME",
            "HOME",
            "auth",
            "token",
            "api_key",
            "secret",
        ):
            self.assertIn(field, receipt_verify_with_query["forbidden_fields"])
        self.assertFalse(receipt_verify_with_query["filesystem_read_performed"])
        self.assertFalse(receipt_verify_with_query["filesystem_write_performed"])
        self.assertFalse(receipt_verify_with_query["receipt_verified"])
        self.assertEqual(receipt_verify_blank_query["status"], "blocked")
        self.assertEqual(
            receipt_verify_blank_query["machine_error_code"],
            "ROLLBACK_APPLY_RECEIPT_VERIFY_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("backend_id", receipt_verify_blank_query["forbidden_fields"])
        self.assertIn("session_id", receipt_verify_blank_query["forbidden_fields"])
        self.assertIn("auth", receipt_verify_blank_query["forbidden_fields"])
        self.assertIn("path", receipt_verify_blank_query["forbidden_fields"])
        self.assertFalse(receipt_verify_blank_query["filesystem_read_performed"])
        self.assertFalse(receipt_verify_blank_query["receipt_verified"])

    def test_codex_custom_session_create_rejects_free_form_model_and_backend(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", FakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                bad_model = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions", {"primary_model_id": "free-form"})
                )
                bad_backend = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "primary_model_id": "gpt-5.3-codex",
                            "account_id": "acct-active",
                            "backend_id": "acct-active",
                            "route_id": "route",
                            "codex_home": "/tmp/home",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(bad_model["status"], "rejected")
        self.assertEqual(bad_model["machine_error_code"], "MODEL_NOT_SERVER_ISSUED")
        self.assertEqual(bad_backend["status"], "rejected")
        self.assertEqual(bad_backend["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("account_id", bad_backend["forbidden_fields"])
        self.assertIn("backend_id", bad_backend["forbidden_fields"])
        self.assertIn("route_id", bad_backend["forbidden_fields"])
        self.assertIn("codex_home", bad_backend["forbidden_fields"])

    def test_codex_custom_prompt_endpoint_is_not_admitted_and_never_runs_prompt(self) -> None:
        class FailingOperatorSurfaceSession(FakeOperatorSurfaceSession):
            def run_prompt(self, payload: dict[str, object], *, trace_wbp: bool = False) -> dict[str, object]:
                self.run_payloads.append(payload)
                return {
                    "status": "failed",
                    "machine_error_code": "ENGINE_PROMPT_FAILED",
                    "human_message": "Codex Operator prompt failed.",
                    "selected_model": payload.get("model_id"),
                    "secret_value_recorded": False,
                }

        created_sessions: list[FailingOperatorSurfaceSession] = []

        def factory() -> FailingOperatorSurfaceSession:
            session = FailingOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "blocked_by_policy_drift"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(payloads)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                session_id = created["session"]["session_id"]
                rejected = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {
                            "prompt": "OK",
                            "model_id": "browser-model",
                            "backend_id": "acct-active",
                            "route_id": "route",
                            "path": "/tmp/outside",
                        },
                    )
                )
                blocked = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {"prompt": "OK"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("model_id", rejected["forbidden_fields"])
        self.assertIn("backend_id", rejected["forbidden_fields"])
        self.assertIn("route_id", rejected["forbidden_fields"])
        self.assertIn("path", rejected["forbidden_fields"])
        self.assertFalse(rejected["inference_proven"])
        self.assertFalse(rejected["model_response_present"])
        self.assertFalse(rejected["prompt_runner_called"])
        self.assertFalse(rejected["network_calls_made"])
        self.assertFalse(rejected["provider_called"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertEqual(blocked["authorization_status"], "blocked_by_operator_authorization")
        self.assertFalse(blocked["live_prompt_admitted"])
        self.assertFalse(blocked["live_prompt_executed"])
        self.assertFalse(blocked["prompt_runner_called"])
        self.assertFalse(blocked["inference_proven"])
        self.assertFalse(blocked["model_response_present"])
        self.assertFalse(blocked["network_calls_made"])
        self.assertFalse(blocked["provider_called"])
        self.assertFalse(blocked["fallback_attempted"])
        self.assertEqual(created_sessions[0].run_payloads, [])

    def test_codex_custom_prompt_endpoint_authorized_path_requires_trace_observer(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "blocked_by_policy_drift"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                session_id = created["session"]["session_id"]
                proof = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {"prompt": "Reply with exactly WBP_LIVE_OK."},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["machine_error_code"], "OK")
        self.assertTrue(proof["owner_authorization_phrase_present"])
        self.assertTrue(proof["live_prompt_admitted"])
        self.assertTrue(proof["live_prompt_executed"])
        self.assertTrue(proof["prompt_runner_called"])
        self.assertTrue(proof["model_response_present"])
        self.assertTrue(proof["inference_proven"])
        self.assertTrue(proof["independent_wbp_trace_observed"])
        self.assertTrue(proof["wbp_path_observed"])
        self.assertTrue(proof["cli_proxy_api_path_observed"])
        self.assertEqual(proof["trace_path"], "/v1/responses")
        self.assertEqual(proof["upstream_status"], 200)
        self.assertTrue(proof["forwarded_to_wbp"])
        self.assertTrue(proof["wbp_path_proven"])
        self.assertTrue(proof["cli_proxy_api_path_proven"])
        self.assertEqual(proof["selected_source_provenance"], "backend_proven")
        self.assertEqual(proof["account_candidate_source"], "server_ranked_candidate")
        self.assertFalse(proof["account_selected_by_user"])
        self.assertFalse(proof["account_execution_proven"])
        self.assertEqual(proof["configured_provider"], "cliproxy")
        self.assertFalse(proof["current_codex_touched"])
        self.assertTrue(proof["live_prompt_full_success"])
        self.assertFalse(proof["browser_selected_backend"])
        self.assertFalse(proof["requested_slot_explicit"])
        self.assertTrue(proof["requested_slot_defaulted_to_primary"])
        self.assertEqual(proof["wbp_runner_payload_slot_id"], "primary_model_slot")
        self.assertEqual(proof["wbp_runner_payload_model_id"], "gpt-5.3-codex")
        self.assertTrue(proof["wbp_runner_payload_slot_matches_requested"])
        self.assertTrue(proof["wbp_runner_payload_model_matches_slot"])
        self.assertTrue(proof["wbp_session_manager_slot_dispatch_proven"])
        self.assertEqual(proof["runtime_slot_dispatch_proof_scope"], "wbp_session_manager_payload_plus_downstream_echo")
        self.assertTrue(proof["runtime_slot_dispatch_proven"])
        self.assertTrue(proof["slot_binding_runtime_dispatch_claimed"])
        self.assertFalse(proof["parallel_slot_execution_proven"])
        self.assertFalse(proof["fanout_execution_proven"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": "Reply with exactly WBP_LIVE_OK.",
                    "model_id": "gpt-5.3-codex",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            ],
        )

    def test_codex_custom_same_session_prompt_can_exercise_chatgpt_and_api_lanes(self) -> None:
        created_sessions: list[DualLaneFakeOperatorSurfaceSession] = []

        def factory() -> DualLaneFakeOperatorSurfaceSession:
            session = DualLaneFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "primary_model_id": "gpt-5.3-codex",
                            "coding_agent_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                session_id = created["session"]["session_id"]
                primary = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {
                            "prompt": "Reply with exactly CHATGPT_LANE_OK.",
                            "slot_id": "primary_model_slot",
                        },
                    )
                )
                api_lane = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {
                            "prompt": "Reply with exactly API_LANE_OK.",
                            "slot_id": "coding_agent_model_slot",
                        },
                    )
                )
                detail = json.loads(fetch(f"{base}/api/codex/custom/sessions/{session_id}"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(created["status"], "ok")
        self.assertEqual(primary["status"], "ok")
        self.assertEqual(primary["current_execution_slot_id"], "primary_model_slot")
        self.assertEqual(primary["requested_slot_id"], "primary_model_slot")
        self.assertTrue(primary["requested_slot_explicit"])
        self.assertEqual(primary["model_id"], "gpt-5.3-codex")
        self.assertEqual(primary["selected_source_provenance"], "backend_proven")
        self.assertEqual(primary["account_candidate_source"], "server_ranked_candidate")
        self.assertFalse(primary["account_selected_by_user"])
        self.assertFalse(primary["account_execution_proven"])
        self.assertEqual(primary["configured_provider"], "cliproxy")
        self.assertTrue(primary["live_prompt_full_success"])
        self.assertEqual(api_lane["status"], "ok")
        self.assertEqual(api_lane["session_id"], session_id)
        self.assertEqual(api_lane["current_execution_slot_id"], "coding_agent_model_slot")
        self.assertEqual(api_lane["requested_slot_id"], "coding_agent_model_slot")
        self.assertTrue(api_lane["requested_slot_explicit"])
        self.assertEqual(api_lane["current_execution_path_source"], "session_bound_slot_runtime")
        self.assertEqual(api_lane["model_id"], "wbp-deepseek-v3")
        self.assertEqual(api_lane["selected_source_class"], "route_backed")
        self.assertEqual(api_lane["selected_source_provenance"], "route_proven")
        self.assertEqual(api_lane["configured_provider"], "external_route")
        self.assertFalse(api_lane["selected_backend_server_issued"])
        self.assertTrue(api_lane["selected_route_server_issued"])
        self.assertTrue(api_lane["route_provenance_required"])
        self.assertTrue(api_lane["route_provenance_proven"])
        self.assertTrue(api_lane["live_prompt_full_success"])
        self.assertEqual(
            detail["session"]["current_execution_slot_id"],
            "coding_agent_model_slot",
        )
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": "Reply with exactly CHATGPT_LANE_OK.",
                    "model_id": "gpt-5.3-codex",
                    "slot_id": "primary_model_slot",
                },
                {
                    "prompt": "Reply with exactly API_LANE_OK.",
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "coding_agent_model_slot",
                },
            ],
        )

    def test_codex_custom_mixed_slot_dispatch_probe_endpoint_proves_two_slots(self) -> None:
        created_sessions: list[DualLaneFakeOperatorSurfaceSession] = []

        def factory() -> DualLaneFakeOperatorSurfaceSession:
            session = DualLaneFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "primary_model_id": "gpt-5.3-codex",
                            "coding_agent_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                session_id = created["session"]["session_id"]
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/mixed-slot-dispatch-probe",
                        {},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CHATGPT_PLUS_API_SLOT_DISPATCH_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["same_session_dispatch_proven"])
        self.assertTrue(packet["primary_dispatch_proven"])
        self.assertTrue(packet["coding_dispatch_proven"])
        self.assertEqual(packet["primary_model_id"], "gpt-5.3-codex")
        self.assertEqual(packet["coding_agent_model_id"], "wbp-deepseek-v3")
        self.assertEqual(packet["primary_runner_payload_slot_id"], "primary_model_slot")
        self.assertEqual(packet["coding_runner_payload_slot_id"], "coding_agent_model_slot")
        self.assertEqual(packet["primary_configured_provider"], "cliproxy")
        self.assertEqual(packet["coding_configured_provider"], "external_route")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["ui_label_counts_as_runtime_truth"])
        self.assertFalse(packet["model_self_report_counts_as_runtime_truth"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["live_file_mutation_claimed"])
        self.assertEqual(created_sessions[0].run_payloads, [])

    def test_codex_custom_mixed_slot_dispatch_probe_endpoint_requires_owner_auth(self) -> None:
        created_sessions: list[DualLaneFakeOperatorSurfaceSession] = []

        def factory() -> DualLaneFakeOperatorSurfaceSession:
            session = DualLaneFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(runner=MappingRunner(payloads)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "primary_model_id": "gpt-5.3-codex",
                            "coding_agent_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                session_id = created["session"]["session_id"]
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/mixed-slot-dispatch-probe",
                        {},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_DISPATCH_NOT_PROVEN",
        )
        self.assertFalse(packet["same_session_dispatch_proven"])
        self.assertFalse(packet["prompt_runner_called"])
        self.assertEqual(created_sessions[0].run_payloads, [])

    def test_codex_custom_mixed_slot_dispatch_probe_endpoint_rejects_browser_fields(self) -> None:
        created_sessions: list[DualLaneFakeOperatorSurfaceSession] = []

        def factory() -> DualLaneFakeOperatorSurfaceSession:
            session = DualLaneFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "primary_model_id": "gpt-5.3-codex",
                            "coding_agent_model_id": "wbp-deepseek-v3",
                        },
                    )
                )
                session_id = created["session"]["session_id"]
                packet = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/mixed-slot-dispatch-probe",
                        {
                            "base_url": "https://example.invalid/v1",
                            "route_id": "raw-route",
                        },
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("base_url", packet["forbidden_fields"])
        self.assertIn("route_id", packet["forbidden_fields"])
        self.assertEqual(created_sessions[0].run_payloads, [])
        self.assertFalse(packet["same_session_dispatch_proven"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_codex_custom_launch_and_prompt_support_route_backed_external_model(self) -> None:
        created_sessions: list[ExternalRouteFakeOperatorSurfaceSession] = []

        def factory() -> ExternalRouteFakeOperatorSurfaceSession:
            session = ExternalRouteFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                launched = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/launch",
                        {"model_id": "wbp-deepseek-v3"},
                    )
                )
                session_id = launched["session"]["session_id"]
                proof = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {"prompt": "Reply with exactly WBP_CUSTOM_EXTERNAL_API_OK."},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(launched["status"], "ok")
        self.assertTrue(launched["running_status"])
        self.assertTrue(launched["workbench_ready"])
        self.assertEqual(launched["selection_packet"]["selected_source_class"], "route_backed")
        self.assertTrue(launched["selection_packet"]["selected_route_server_issued"])
        self.assertTrue(launched["selection_packet"]["route_provenance_required"])
        self.assertFalse(launched["selection_packet"]["route_provenance_proven"])
        self.assertTrue(launched["selection_packet"]["route_candidate_classified"])
        self.assertTrue(launched["selection_packet"]["route_static_readiness_classified"])
        self.assertFalse(launched["selection_packet"]["route_execution_proven"])
        self.assertFalse(launched["selection_packet"]["provider_response_proven"])
        self.assertFalse(launched["selection_packet"]["secret_validity_proven"])
        self.assertFalse(launched["selection_packet"]["live_compatibility_proven"])
        self.assertEqual(
            launched["selection_packet"]["source_provenance_status"],
            "route_static_candidate_classified",
        )
        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["machine_error_code"], "OK")
        self.assertEqual(proof["selected_source_provenance"], "route_proven")
        self.assertEqual(proof["configured_provider"], "external_route")
        self.assertTrue(proof["live_prompt_full_success"])
        self.assertFalse(proof["current_codex_touched"])
        self.assertFalse(proof["requested_slot_explicit"])
        self.assertTrue(proof["requested_slot_defaulted_to_primary"])
        self.assertEqual(proof["wbp_runner_payload_slot_id"], "primary_model_slot")
        self.assertEqual(proof["wbp_runner_payload_model_id"], "wbp-deepseek-v3")
        self.assertTrue(proof["wbp_runner_payload_slot_matches_requested"])
        self.assertTrue(proof["wbp_runner_payload_model_matches_slot"])
        self.assertTrue(proof["wbp_session_manager_slot_dispatch_proven"])
        self.assertEqual(proof["runtime_slot_dispatch_proof_scope"], "wbp_session_manager_payload_plus_downstream_echo")
        self.assertTrue(proof["runtime_slot_dispatch_proven"])
        self.assertTrue(proof["slot_binding_runtime_dispatch_claimed"])
        self.assertFalse(proof["parallel_slot_execution_proven"])
        self.assertFalse(proof["fanout_execution_proven"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": "Reply with exactly WBP_CUSTOM_EXTERNAL_API_OK.",
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            ],
        )

    def test_codex_custom_temp_write_probe_uses_api_only_workspace_write_surface(self) -> None:
        class TempWriteExternalRouteFakeOperatorSurfaceSession(ExternalRouteFakeOperatorSurfaceSession):
            def run_prompt(
                self,
                payload: dict[str, object],
                *,
                trace_wbp: bool = False,
                sandbox_mode_override: str = "read-only",
                writable_additional_dir: Path | None = None,
                working_dir_override: Path | None = None,
            ) -> dict[str, object]:
                assert sandbox_mode_override == "workspace-write"
                assert writable_additional_dir is not None
                prompt = str(payload["prompt"])
                target = Path(prompt.split("> ", 1)[1].split(" &&", 1)[0]).resolve()
                assert target.parent == writable_additional_dir
                target.write_text("WBP_DEEPSEEK_TEMP_WRITE_OK", encoding="utf-8")
                result = super().run_prompt(
                    payload,
                    trace_wbp=trace_wbp,
                    sandbox_mode_override=sandbox_mode_override,
                    writable_additional_dir=writable_additional_dir,
                    working_dir_override=working_dir_override,
                )
                trace_packet = dict(result["trace_observer_packet"])
                trace_packet["request_count"] = 2
                result.update(
                    {
                        "runtime_model": "wbp-deepseek-v3",
                        "final_message": "WBP_DEEPSEEK_TEMP_WRITE_OK",
                        "trace_observer_packet": trace_packet,
                        "additional_writable_dir_admitted": True,
                    }
                )
                return result

        created_sessions: list[TempWriteExternalRouteFakeOperatorSurfaceSession] = []

        def factory() -> TempWriteExternalRouteFakeOperatorSurfaceSession:
            session = TempWriteExternalRouteFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                launched = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/launch",
                        {"model_id": "wbp-deepseek-v3"},
                    )
                )
                session_id = launched["session"]["session_id"]
                proof = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/temp-write-probe",
                        {"api_model_id": "wbp-deepseek-v3"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(proof["status"], "ok")
        self.assertEqual(
            proof["final_status"],
            "API_ONLY_DEEPSEEK_TEMP_WRITE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(proof["execution_mode"], "api_only")
        self.assertEqual(proof["model_id"], "wbp-deepseek-v3")
        self.assertTrue(proof["tool_loop_proven"])
        self.assertTrue(proof["file_existed_after_tool"])
        self.assertTrue(proof["file_content_matches"])
        self.assertTrue(proof["file_removed_after_probe"])
        self.assertEqual(proof["write_surface"], "temp_only")
        self.assertTrue(proof["workspace_write_admitted"])
        self.assertFalse(proof["danger_full_access_admitted"])
        self.assertFalse(proof["repo_mutation_attempted"])
        self.assertFalse(proof["original_codex_touched"])
        self.assertFalse(proof["wbp_patch_applier_used"])
        self.assertFalse(proof["live_product_code_edit_claimed"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": created_sessions[0].run_payloads[0]["prompt"],
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            ],
        )

    def test_codex_custom_safe_worktree_edit_probe_uses_isolated_worktree(self) -> None:
        class SafeWorktreeExternalRouteFakeOperatorSurfaceSession(ExternalRouteFakeOperatorSurfaceSession):
            def run_prompt(
                self,
                payload: dict[str, object],
                *,
                trace_wbp: bool = False,
                sandbox_mode_override: str = "read-only",
                writable_additional_dir: Path | None = None,
                working_dir_override: Path | None = None,
            ) -> dict[str, object]:
                assert sandbox_mode_override == "workspace-write"
                assert writable_additional_dir is not None
                prompt = str(payload["prompt"])
                target = Path(prompt.split("> ", 1)[1].split(" &&", 1)[0]).resolve()
                assert target.parent == writable_additional_dir
                target.write_text("WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK", encoding="utf-8")
                result = super().run_prompt(
                    payload,
                    trace_wbp=trace_wbp,
                    sandbox_mode_override=sandbox_mode_override,
                    writable_additional_dir=writable_additional_dir,
                    working_dir_override=working_dir_override,
                )
                trace_packet = dict(result["trace_observer_packet"])
                trace_packet["request_count"] = 2
                result.update(
                    {
                        "runtime_model": "wbp-deepseek-v3",
                        "final_message": "WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK",
                        "trace_observer_packet": trace_packet,
                        "additional_writable_dir_admitted": True,
                    }
                )
                return result

        created_sessions: list[SafeWorktreeExternalRouteFakeOperatorSurfaceSession] = []

        def factory() -> SafeWorktreeExternalRouteFakeOperatorSurfaceSession:
            session = SafeWorktreeExternalRouteFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with tempfile.TemporaryDirectory() as repo_dir:
            init_git_repo(Path(repo_dir))
            with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                        safe_worktree_repo_root=Path(repo_dir),
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    launched = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/launch",
                            {"model_id": "wbp-deepseek-v3"},
                        )
                    )
                    session_id = launched["session"]["session_id"]
                    proof = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/sessions/{session_id}/safe-worktree-edit-probe",
                            {"api_model_id": "wbp-deepseek-v3"},
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(proof["status"], "ok")
        self.assertEqual(
            proof["final_status"],
            "API_ONLY_DEEPSEEK_SAFE_WORKTREE_EDIT_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(proof["execution_mode"], "api_only")
        self.assertEqual(proof["model_id"], "wbp-deepseek-v3")
        self.assertTrue(proof["safe_worktree_used"])
        self.assertTrue(proof["tool_loop_proven"])
        self.assertEqual(proof["write_surface"], "safe_worktree_only")
        self.assertTrue(proof["file_changed_by_codex_tool"])
        self.assertTrue(proof["git_diff_observed"])
        self.assertTrue(proof["expected_diff_observed"])
        self.assertFalse(proof["main_worktree_mutated_by_probe"])
        self.assertFalse(proof["secret_in_diff"])
        self.assertTrue(proof["worktree_removed_after_probe"])
        self.assertFalse(proof["danger_full_access_admitted"])
        self.assertFalse(proof["original_codex_touched"])
        self.assertFalse(proof["original_codex_profile_touched"])
        self.assertFalse(proof["wbp_patch_applier_used"])
        self.assertFalse(proof["commit_attempted"])
        self.assertFalse(proof["push_attempted"])
        self.assertFalse(proof["merge_attempted"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": created_sessions[0].run_payloads[0]["prompt"],
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            ],
        )

    def test_quick_start_deepseek_coder_check_uses_safe_worktree_button_path(self) -> None:
        class QuickStartDeepSeekFakeOperatorSurfaceSession(ExternalRouteFakeOperatorSurfaceSession):
            def run_prompt(
                self,
                payload: dict[str, object],
                *,
                trace_wbp: bool = False,
                sandbox_mode_override: str = "read-only",
                writable_additional_dir: Path | None = None,
                working_dir_override: Path | None = None,
            ) -> dict[str, object]:
                assert sandbox_mode_override == "workspace-write"
                assert writable_additional_dir is not None
                prompt = str(payload["prompt"])
                target = Path(prompt.split("> ", 1)[1].split(" &&", 1)[0]).resolve()
                assert target.parent == writable_additional_dir
                target.write_text("WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK", encoding="utf-8")
                result = super().run_prompt(
                    payload,
                    trace_wbp=trace_wbp,
                    sandbox_mode_override=sandbox_mode_override,
                    writable_additional_dir=writable_additional_dir,
                    working_dir_override=working_dir_override,
                )
                trace_packet = dict(result["trace_observer_packet"])
                trace_packet["request_count"] = 2
                result.update(
                    {
                        "runtime_model": "wbp-deepseek-v3",
                        "final_message": "WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK",
                        "trace_observer_packet": trace_packet,
                        "additional_writable_dir_admitted": True,
                    }
                )
                return result

        created_sessions: list[QuickStartDeepSeekFakeOperatorSurfaceSession] = []

        def factory() -> QuickStartDeepSeekFakeOperatorSurfaceSession:
            session = QuickStartDeepSeekFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        with tempfile.TemporaryDirectory() as repo_dir:
            init_git_repo(Path(repo_dir))
            with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                        safe_worktree_repo_root=Path(repo_dir),
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    packet = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/quick-start/deepseek-safe-worktree-check",
                            {
                                "execution_mode": "api_only",
                                "api_model_id": "wbp-deepseek-v3",
                            },
                        )
                    )
                    rejected = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/quick-start/deepseek-safe-worktree-check",
                            {
                                "execution_mode": "api_only",
                                "api_model_id": "wbp-deepseek-v3",
                                "base_url": "https://example.invalid/v1",
                            },
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "DEEPSEEK_LIVE_EXECUTOR_PACKET_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(
            packet["legacy_quick_start_final_status"],
            "QUICK_START_API_ONLY_DEEPSEEK_SAFE_WORKTREE_BUTTON_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["deepseek_live_executor_packet_proven_with_limits"])
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["api_model_id"], "wbp-deepseek-v3")
        self.assertEqual(packet["api_reasoning_option_id"], "")
        self.assertFalse(packet["api_reasoning_option_runtime_mutation_claimed"])
        self.assertFalse(packet["api_reasoning_intelligence_measured"])
        self.assertFalse(packet["api_reasoning_codex_parity_claimed"])
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v3")
        self.assertTrue(packet["server_issued_catalog_used"])
        self.assertFalse(packet["chatgpt_line_used_as_executor"])
        self.assertTrue(packet["api_line_used_as_executor"])
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertTrue(packet["no_chatgpt"])
        self.assertFalse(packet["fallback_attempted"])
        self.assertTrue(packet["no_fallback"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["tool_loop_proven"])
        self.assertTrue(packet["safe_worktree_used"])
        self.assertEqual(packet["write_surface"], "safe_worktree_only")
        self.assertTrue(packet["file_changed_by_codex_tool"])
        self.assertTrue(packet["git_diff_observed"])
        self.assertTrue(packet["expected_diff_observed"])
        self.assertFalse(packet["main_worktree_mutated_by_probe"])
        self.assertTrue(packet["main_tree_untouched"])
        self.assertFalse(packet["secret_in_diff"])
        self.assertTrue(packet["worktree_removed_after_probe"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["browser_raw_backend_authority_widened"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertTrue(packet["no_patch_applier"])
        self.assertFalse(packet["commit_attempted"])
        self.assertFalse(packet["push_attempted"])
        self.assertFalse(packet["merge_attempted"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": created_sessions[0].run_payloads[0]["prompt"],
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            ],
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("base_url", rejected["forbidden_fields"])

    def test_codex_custom_repo_tmp_edit_probe_endpoint_proves_api_only_deepseek_edit(self) -> None:
        class RepoTmpDeepSeekFakeOperatorSurfaceSession(ExternalRouteFakeOperatorSurfaceSession):
            def run_prompt(
                self,
                payload: dict[str, object],
                *,
                trace_wbp: bool = False,
                sandbox_mode_override: str = "read-only",
                writable_additional_dir: Path | None = None,
                working_dir_override: Path | None = None,
                declared_repo_tmp_dir: Path | None = None,
            ) -> dict[str, object]:
                assert sandbox_mode_override == "workspace-write"
                assert writable_additional_dir is not None
                assert declared_repo_tmp_dir == writable_additional_dir
                target = writable_additional_dir / "deepseek_api_only_live_edit_probe.txt"
                target.write_text("WBP_API_ONLY_DEEPSEEK_EDIT_OK", encoding="utf-8")
                result = super().run_prompt(
                    payload,
                    trace_wbp=trace_wbp,
                    sandbox_mode_override=sandbox_mode_override,
                    writable_additional_dir=writable_additional_dir,
                    working_dir_override=working_dir_override,
                )
                trace_packet = dict(result["trace_observer_packet"])
                trace_packet["request_count"] = 2
                result.update(
                    {
                        "runtime_model": "wbp-deepseek-v3",
                        "final_message": "WBP_API_ONLY_DEEPSEEK_EDIT_OK",
                        "trace_observer_packet": trace_packet,
                        "additional_writable_dir_admitted": True,
                        "additional_writable_dir_scope": "declared_repo_tmp_only",
                    }
                )
                return result

        created_sessions: list[RepoTmpDeepSeekFakeOperatorSurfaceSession] = []

        def factory() -> RepoTmpDeepSeekFakeOperatorSurfaceSession:
            session = RepoTmpDeepSeekFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        written_content = ""
        with tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)
            init_git_repo(repo)
            with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                        safe_worktree_repo_root=repo,
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    launched = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/launch",
                            {"model_id": "wbp-deepseek-v3"},
                        )
                    )
                    session_id = launched["session"]["session_id"]
                    packet = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/sessions/{session_id}/repo-tmp-edit-probe",
                            {"api_model_id": "wbp-deepseek-v3"},
                        )
                    )
                    rejected = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/sessions/{session_id}/repo-tmp-edit-probe",
                            {"api_model_id": "wbp-deepseek-v3", "path": ".tmp/owned"},
                        )
                    )
                    written_content = (repo / ".tmp/deepseek_api_only_live_edit_probe.txt").read_text(
                        encoding="utf-8"
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["model_id"], "wbp-deepseek-v3")
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertTrue(packet["main_tree_mutation_admitted"])
        self.assertEqual(packet["write_surface"], ".tmp_only")
        self.assertTrue(packet["provider_called"])
        self.assertTrue(packet["tool_loop_proven"])
        self.assertTrue(packet["setup_probe_file_seeded_by_wbp"])
        self.assertTrue(packet["file_changed_by_codex_tool"])
        self.assertTrue(packet["file_content_matches"])
        self.assertFalse(packet["outside_write_surface_changed"])
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["push_attempted"])
        self.assertEqual(written_content, "WBP_API_ONLY_DEEPSEEK_EDIT_OK")
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": created_sessions[0].run_payloads[0]["prompt"],
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                    "declared_write_surface": ".tmp_only",
                    "target_relative_path": ".tmp/deepseek_api_only_live_edit_probe.txt",
                }
            ],
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("path", rejected["forbidden_fields"])

    def test_codex_custom_product_safe_worktree_coder_and_cleanup_endpoint(self) -> None:
        class ProductCoderExternalRouteFakeOperatorSurfaceSession(ExternalRouteFakeOperatorSurfaceSession):
            def run_prompt(
                self,
                payload: dict[str, object],
                *,
                trace_wbp: bool = False,
                sandbox_mode_override: str = "read-only",
                writable_additional_dir: Path | None = None,
                working_dir_override: Path | None = None,
            ) -> dict[str, object]:
                assert sandbox_mode_override == "workspace-write"
                assert writable_additional_dir is None
                assert working_dir_override is not None
                assert (working_dir_override / "README.md").exists()
                (working_dir_override / "README.md").write_text(
                    "safe worktree test repo\nDeepSeek product coder touched this file.\n",
                    encoding="utf-8",
                )
                result = super().run_prompt(
                    payload,
                    trace_wbp=trace_wbp,
                    sandbox_mode_override=sandbox_mode_override,
                    writable_additional_dir=writable_additional_dir,
                    working_dir_override=working_dir_override,
                )
                trace_packet = dict(result["trace_observer_packet"])
                trace_packet["request_count"] = 2
                result.update(
                    {
                        "runtime_model": "wbp-deepseek-v3",
                        "final_message": "changed README.md",
                        "trace_observer_packet": trace_packet,
                        "working_dir_override_admitted": True,
                        "working_dir_scope": "safe_worktree_only",
                        "direct_non_wbp_model_egress_absent_proven": True,
                    }
                )
                return result

        created_sessions: list[ProductCoderExternalRouteFakeOperatorSurfaceSession] = []

        def factory() -> ProductCoderExternalRouteFakeOperatorSurfaceSession:
            session = ProductCoderExternalRouteFakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "ok"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with tempfile.TemporaryDirectory() as repo_dir:
            init_git_repo(Path(repo_dir))
            with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_handler(
                        runner=MappingRunner(payloads),
                        owner_authorization_phrase="разрешаю тебе любые законные действия в рамках разработки проекта",
                        safe_worktree_repo_root=Path(repo_dir),
                    ),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    launched = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/launch",
                            {"model_id": "wbp-deepseek-v3"},
                        )
                    )
                    session_id = launched["session"]["session_id"]
                    packet = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/sessions/{session_id}/safe-worktree-coder",
                            {
                                "api_model_id": "wbp-deepseek-v3",
                                "task": "Append a short sentence to README.md.",
                            },
                        )
                    )
                    cleanup = json.loads(
                        post_json(
                            f"{base}/api/codex/custom/worktrees/{packet['worktree_id']}/cleanup",
                            {},
                        )
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "API_ONLY_DEEPSEEK_PRODUCT_SAFE_WORKTREE_CODER_READY_WITH_LIMITS",
        )
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["model_id"], "wbp-deepseek-v3")
        self.assertTrue(packet["diff_present"])
        self.assertEqual(packet["changed_files"], ["README.md"])
        self.assertTrue(packet["cleanup_required"])
        self.assertEqual(packet["safe_worktree_status"], "active")
        self.assertFalse(packet["main_worktree_mutated_by_run"])
        self.assertFalse(packet["secret_in_diff"])
        self.assertFalse(packet["commit_attempted"])
        self.assertFalse(packet["push_attempted"])
        self.assertFalse(packet["merge_attempted"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertTrue(packet["working_dir_override_admitted"])
        self.assertEqual(packet["working_dir_scope"], "safe_worktree_only")
        self.assertIn("DeepSeek product coder touched this file", packet["diff_text_bounded"])
        self.assertEqual(cleanup["status"], "ok")
        self.assertTrue(cleanup["cleanup_performed"])
        self.assertEqual(cleanup["safe_worktree_status"], "cleaned")
        self.assertEqual(
            created_sessions[0].run_payloads,
            [
                {
                    "prompt": created_sessions[0].run_payloads[0]["prompt"],
                    "model_id": "wbp-deepseek-v3",
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            ],
        )

    def test_codex_custom_prompt_endpoint_rejects_near_miss_authorization_phrase(self) -> None:
        created_sessions: list[FakeOperatorSurfaceSession] = []

        def factory() -> FakeOperatorSurfaceSession:
            session = FakeOperatorSurfaceSession()
            created_sessions.append(session)
            return session

        payloads = live_payloads()
        payloads[("status", "--json")] = status_packet(
            claim_gate={"status": "blocked_by_policy_drift"},
            pool_summary={"selected_backend_ids": ["acct-active"]},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "selection_alignment_status": "aligned",
            },
        )
        payloads[("accounts", "list", "--json")] = accounts_packet(
            accounts=[account("acct-active", "active", "healthy", auth_ref="/tmp/wbp-auth.json")]
        )
        with mock.patch.object(live_server, "OperatorSurfaceSession", side_effect=factory):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_handler(
                    runner=MappingRunner(payloads),
                    owner_authorization_phrase="начинай работу по данному контуру",
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"primary_model_id": "gpt-5.3-codex"},
                    )
                )
                session_id = created["session"]["session_id"]
                blocked = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions/{session_id}/prompt",
                        {"prompt": "OK"},
                    )
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertFalse(blocked["owner_authorization_phrase_present"])
        self.assertFalse(blocked["prompt_runner_called"])
        self.assertEqual(created_sessions[0].run_payloads, [])


class WebDesignCodexCustomDeepSeekCodeEditProofTests(unittest.TestCase):
    def _api_only_live_code_edit_truth_packet(
        self,
        *,
        file_text: str | None = "WBP_API_ONLY_DEEPSEEK_EDIT_OK",
        launch_overrides: dict[str, object] | None = None,
        record_overrides: dict[str, object] | None = None,
        write_logs: bool = True,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as profile_dir:
            repo_root = Path(repo_dir)
            profile_root = Path(profile_dir)
            if file_text is not None:
                probe_file = repo_root / ".tmp" / "deepseek_api_only_live_edit_probe.txt"
                probe_file.parent.mkdir(parents=True)
                probe_file.write_text(file_text, encoding="utf-8")

            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    (
                        "thread-deepseek",
                        str(repo_root),
                        "wbp-deepseek-v4-pro-max",
                        "wbp",
                        1,
                        2,
                    ),
                )

            with sqlite3.connect(profile_root / "logs_2.sqlite") as connection:
                connection.execute(
                    "create table logs (id integer, thread_id text, feedback_log_body text)"
                )
                if write_logs:
                    connection.execute(
                        "insert into logs values (?, ?, ?)",
                        (
                            1,
                            "thread-deepseek",
                            "turn model=wbp-deepseek-v4-pro-max cwd="
                            f"{repo_root}: ToolCall: exec_command "
                            ".tmp/deepseek_api_only_live_edit_probe.txt",
                        ),
                    )
                    connection.execute(
                        "insert into logs values (?, ?, ?)",
                        (
                            2,
                            "thread-deepseek",
                            ".tmp/deepseek_api_only_live_edit_probe.txt success=true "
                            "model=wbp-deepseek-v4-pro-max",
                        ),
                    )

            launch: dict[str, object] = {
                "launch_id": "launch-deepseek-code-edit",
                "trace_id": "trace-deepseek-code-edit",
                "status": "ok",
                "execution_mode": "api_only",
                "selected_model": "wbp-deepseek-v4-pro-max",
                "api_reasoning_option_id": "provider_declared_max",
                "custom_codex_window_deepseek_launch_proven_with_limits": True,
                "native_app_usable": True,
                "real_codex_app_launched": True,
                "stable_bridge_preflight_required": True,
                "stable_bridge_preflight_status": "ok",
                "stable_bridge_launch_allowed": True,
                "persistent_profile_root": str(profile_root),
                "original_codex_touched": False,
                "asar_touched": False,
            }
            if launch_overrides:
                launch.update(launch_overrides)
            record: dict[str, object] = {
                "launch_packet_id": "launch-deepseek-code-edit",
                "trace_id": "trace-deepseek-code-edit",
                "route_digest_matches_launch": True,
                "request_seen_after_launch": True,
                "provider_called": True,
                "provider_id": "deepseek",
                "upstream_model": "deepseek-v4-pro",
                "effective_route_model": "wbp-deepseek-v4-pro-max",
                "response_seen": True,
                "forced_route_used": True,
                "fallback_used": False,
                "chatgpt_route_used": False,
            }
            if record_overrides:
                record.update(record_overrides)

            return live_server.build_api_only_deepseek_live_code_edit_truth_packet(
                last_launch_packet=launch,
                bridge_trace_packet={
                    "bridge_request_trace_packet": {
                        "route_unchanged": record.get("route_digest_matches_launch") is True,
                        "fallback_used": record.get("fallback_used") is True,
                    },
                    "last_record": record,
                },
                browser_payload={
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
                repo_root=repo_root,
            )

    def test_api_only_deepseek_live_code_edit_truth_proves_file_route_and_no_fallback(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["packet_kind"], "api_only_deepseek_live_code_edit_truth")
        self.assertEqual(
            packet["expected_file"],
            ".tmp/deepseek_api_only_live_edit_probe.txt",
        )
        self.assertIn("WBP_API_ONLY_DEEPSEEK_EDIT_OK", packet["manual_prompt_required"])
        self.assertEqual(
            packet["final_status"],
            "API_ONLY_DEEPSEEK_LIVE_CODE_EDIT_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v4-pro-max")
        self.assertTrue(packet["api_primary_slot_proven"])
        self.assertTrue(packet["api_only_executor_truth_proven"])
        self.assertEqual(packet["primary_model_slot"]["slot_id"], "primary_model_slot")
        self.assertEqual(packet["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(packet["primary_model_slot"]["provider_id"], "deepseek")
        self.assertEqual(
            packet["coding_agent_model_slot"]["status"],
            "not_bound_for_mode",
        )
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertEqual(packet["upstream_model"], "deepseek-v4-pro")
        self.assertEqual(packet["stable_bridge_preflight"], "ok")
        self.assertTrue(packet["stable_bridge_preflight_ok"])
        self.assertTrue(packet["stable_bridge_preflight_required"])
        self.assertTrue(packet["stable_bridge_launch_allowed"])
        self.assertTrue(packet["native_app_usable"])
        self.assertTrue(packet["file_edit_observed"])
        self.assertTrue(packet["file_mutation_observed"])
        self.assertTrue(packet["file_content_matches_expected"])
        self.assertEqual(packet["changed_files"], [".tmp/deepseek_api_only_live_edit_probe.txt"])
        self.assertTrue(packet["mutation_scope_allowed"])
        self.assertEqual(packet["file_size_bytes"], 29)
        self.assertEqual(
            packet["file_content_sha256"],
            "8824e44257ce27045c1e47e79807aa93ceb66b90a31c1f49a5b88637b97a3a0c",
        )
        self.assertTrue(packet["route_unchanged"])
        self.assertTrue(packet["selected_route_preserved"])
        self.assertFalse(packet["chatgpt_called"])
        self.assertFalse(packet["api_only_calls_chatgpt"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["response_text_counts_as_proof"])
        self.assertFalse(packet["ui_label_counts_as_proof"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_api_only_deepseek_live_code_edit_truth_blocks_legacy_window_proof_without_usability(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(
            launch_overrides={"native_app_usable": False},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["window_launch_proven_with_limits"])
        self.assertFalse(packet["native_app_usable"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )

    def test_api_only_deepseek_live_code_edit_truth_blocks_missing_stable_preflight(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(
            launch_overrides={
                "stable_bridge_preflight_status": "blocked",
                "stable_bridge_launch_allowed": False,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["stable_bridge_preflight_ok"])
        self.assertTrue(packet["file_mutation_observed"])
        self.assertTrue(packet["mutation_scope_allowed"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )

    def test_api_only_deepseek_live_code_edit_truth_blocks_missing_file(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(file_text=None)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )
        self.assertFalse(packet["file_edit_observed"])
        self.assertFalse(packet["file_content_matches_expected"])
        self.assertTrue(packet["provider_called"])
        self.assertFalse(packet["fallback_used"])

    def test_api_only_deepseek_live_code_edit_truth_blocks_content_mismatch(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(file_text="WRONG")

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["file_edit_observed"])
        self.assertFalse(packet["file_mutation_observed"])
        self.assertFalse(packet["file_content_matches_expected"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )

    def test_api_only_deepseek_live_code_edit_truth_blocks_extra_changed_file(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(
            record_overrides={
                "changed_files": [
                    ".tmp/deepseek_api_only_live_edit_probe.txt",
                    "README.md",
                ],
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["changed_files"],
            [".tmp/deepseek_api_only_live_edit_probe.txt", "README.md"],
        )
        self.assertFalse(packet["mutation_scope_allowed"])
        self.assertTrue(packet["file_mutation_observed"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )

    def test_api_only_deepseek_live_code_edit_truth_blocks_route_or_trace_mismatch(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(
            record_overrides={
                "provider_id": "openai",
                "effective_route_model": "gpt-5.4",
                "route_digest_matches_launch": False,
                "forced_route_used": False,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertNotEqual(packet["provider_id"], "deepseek")
        self.assertFalse(packet["api_primary_slot_proven"])
        self.assertFalse(packet["api_only_executor_truth_proven"])
        self.assertFalse(packet["route_unchanged"])
        self.assertFalse(packet["selected_route_preserved"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )

    def test_api_only_deepseek_live_code_edit_truth_blocks_chatgpt_or_fallback(self) -> None:
        packet = self._api_only_live_code_edit_truth_packet(
            record_overrides={
                "fallback_used": True,
                "chatgpt_route_used": True,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["chatgpt_called"])
        self.assertTrue(packet["api_only_calls_chatgpt"])
        self.assertTrue(packet["fallback_used"])
        self.assertFalse(packet["selected_route_preserved"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )

    def test_api_only_deepseek_live_code_edit_truth_endpoint_reports_blocked_without_live_call(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            packet = json.loads(
                post_json(
                    f"{base}/api/codex/custom/quick-start/api-only-deepseek-live-code-edit-truth",
                    {
                        "execution_mode": "api_only",
                        "api_model_id": "wbp-deepseek-v4-pro-max",
                        "api_reasoning_option_id": "provider_declared_max",
                    },
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["packet_kind"], "api_only_deepseek_live_code_edit_truth")
        self.assertEqual(
            packet["expected_file"],
            ".tmp/deepseek_api_only_live_edit_probe.txt",
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        )
        self.assertFalse(packet["commit_attempted"])
        self.assertFalse(packet["push_attempted"])
        self.assertFalse(packet["merge_attempted"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_api_only_deepseek_live_code_edit_truth_endpoint_rejects_forbidden_browser_fields(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            packet = json.loads(
                post_json(
                    f"{base}/api/codex/custom/quick-start/api-only-deepseek-live-code-edit-truth",
                    {
                        "execution_mode": "api_only",
                        "api_model_id": "wbp-deepseek-v4-pro-max",
                        "base_url": "https://api.deepseek.example",
                    },
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["packet_kind"], "api_only_deepseek_live_code_edit_truth")
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(packet["forbidden_fields"], ["base_url"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_deepseek_code_edit_reproduction_packet_requires_file_thread_logs_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as profile_dir:
            repo_root = Path(repo_dir)
            profile_root = Path(profile_dir)
            probe_file = repo_root / ".tmp" / "deepseek_live_probe.txt"
            probe_file.parent.mkdir(parents=True)
            probe_file.write_text("WBP_DEEPSEEK_CODE_EDIT_OK", encoding="utf-8")

            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    (
                        "thread-deepseek",
                        str(repo_root),
                        "wbp-deepseek-v4-pro-max",
                        "wbp",
                        1,
                        2,
                    ),
                )

            with sqlite3.connect(profile_root / "logs_2.sqlite") as connection:
                connection.execute(
                    "create table logs (id integer, thread_id text, feedback_log_body text)"
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        1,
                        "thread-deepseek",
                        "turn model=wbp-deepseek-v4-pro-max cwd="
                        f"{repo_root}: ToolCall: exec_command .tmp/deepseek_live_probe.txt",
                    ),
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        2,
                        "thread-deepseek",
                        ".tmp/deepseek_live_probe.txt success=true model=wbp-deepseek-v4-pro-max",
                    ),
                )

            packet = live_server.build_custom_codex_deepseek_code_edit_reproduction_packet(
                last_launch_packet={
                    "launch_id": "launch-deepseek-code-edit",
                    "trace_id": "trace-deepseek-code-edit",
                    "status": "ok",
                    "execution_mode": "api_only",
                    "selected_model": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                    "custom_codex_window_deepseek_launch_proven_with_limits": True,
                    "native_app_usable": True,
                    "real_codex_app_launched": True,
                    "stable_bridge_preflight_required": True,
                    "stable_bridge_preflight_status": "ok",
                    "stable_bridge_launch_allowed": True,
                    "persistent_profile_root": str(profile_root),
                    "original_codex_touched": False,
                    "asar_touched": False,
                },
                bridge_trace_packet={
                    "last_record": {
                        "launch_packet_id": "launch-deepseek-code-edit",
                        "trace_id": "trace-deepseek-code-edit",
                        "route_digest_matches_launch": True,
                        "request_seen_after_launch": True,
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "response_seen": True,
                        "forced_route_used": True,
                        "fallback_used": False,
                        "chatgpt_route_used": False,
                    }
                },
                browser_payload={
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
                repo_root=repo_root,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCIBLE_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(packet["execution_mode"], "api_only")
        self.assertEqual(packet["selected_model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(packet["cwd"], str(repo_root))
        self.assertTrue(packet["file_created"])
        self.assertTrue(packet["file_content_exact"])
        self.assertEqual(packet["file_path_relative"], ".tmp/deepseek_live_probe.txt")
        self.assertEqual(packet["launch_id"], "launch-deepseek-code-edit")
        self.assertEqual(packet["trace_id"], "trace-deepseek-code-edit")
        self.assertTrue(packet["trace_launch_packet_matches"])
        self.assertTrue(packet["trace_id_matches_launch"])
        self.assertTrue(packet["trace_server_issued"])
        self.assertTrue(packet["forced_route_used"])
        self.assertFalse(packet["forced_route_counts_as_fallback"])
        self.assertFalse(packet["chatgpt_called"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        self.assertFalse(packet["wbp_patch_applier_used"])
        self.assertTrue(packet["small_real_edit_probe_supported"])

    def test_deepseek_code_edit_reproduction_blocks_trace_from_other_launch(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as profile_dir:
            repo_root = Path(repo_dir)
            profile_root = Path(profile_dir)
            probe_file = repo_root / ".tmp" / "deepseek_live_probe.txt"
            probe_file.parent.mkdir(parents=True)
            probe_file.write_text("WBP_DEEPSEEK_CODE_EDIT_OK", encoding="utf-8")

            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    (
                        "thread-deepseek",
                        str(repo_root),
                        "wbp-deepseek-v4-pro-max",
                        "wbp",
                        1,
                        2,
                    ),
                )

            with sqlite3.connect(profile_root / "logs_2.sqlite") as connection:
                connection.execute(
                    "create table logs (id integer, thread_id text, feedback_log_body text)"
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        1,
                        "thread-deepseek",
                        "turn model=wbp-deepseek-v4-pro-max cwd="
                        f"{repo_root}: ToolCall: exec_command .tmp/deepseek_live_probe.txt",
                    ),
                )
                connection.execute(
                    "insert into logs values (?, ?, ?)",
                    (
                        2,
                        "thread-deepseek",
                        ".tmp/deepseek_live_probe.txt success=true model=wbp-deepseek-v4-pro-max",
                    ),
                )

            packet = live_server.build_custom_codex_deepseek_code_edit_reproduction_packet(
                last_launch_packet={
                    "launch_id": "launch-deepseek-code-edit",
                    "trace_id": "trace-deepseek-code-edit",
                    "status": "ok",
                    "execution_mode": "api_only",
                    "selected_model": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                    "custom_codex_window_deepseek_launch_proven_with_limits": True,
                    "native_app_usable": True,
                    "real_codex_app_launched": True,
                    "stable_bridge_preflight_required": True,
                    "stable_bridge_preflight_status": "ok",
                    "stable_bridge_launch_allowed": True,
                    "persistent_profile_root": str(profile_root),
                    "original_codex_touched": False,
                    "asar_touched": False,
                },
                bridge_trace_packet={
                    "last_record": {
                        "launch_packet_id": "other-launch",
                        "trace_id": "other-trace",
                        "route_digest_matches_launch": True,
                        "request_seen_after_launch": True,
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "response_seen": True,
                        "forced_route_used": True,
                        "fallback_used": False,
                        "chatgpt_route_used": False,
                    }
                },
                browser_payload={
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
                repo_root=repo_root,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "KNOWN_BLOCKER_CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCTION_FAILED",
        )
        self.assertFalse(packet["trace_launch_packet_matches"])
        self.assertFalse(packet["trace_id_matches_launch"])
        self.assertTrue(packet["file_content_exact"])
        self.assertFalse(packet["fallback_used"])

    def test_deepseek_code_edit_reproduction_rejects_raw_backend_fields(self) -> None:
        packet = live_server.build_custom_codex_deepseek_code_edit_reproduction_packet(
            last_launch_packet={},
            bridge_trace_packet={},
            browser_payload={
                "execution_mode": "api_only",
                "api_model_id": "wbp-deepseek-v4-pro-max",
                "base_url": "https://example.invalid/v1",
            },
            repo_root=Path("/tmp/repo"),
        )
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertIn("base_url", packet["forbidden_fields"])

    def test_deepseek_route_bound_real_edit_packet_accepts_session_jsonl_tool_trace(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as profile_dir:
            repo_root = Path(repo_dir)
            profile_root = Path(profile_dir)
            probe_file = repo_root / ".tmp" / "deepseek_route_bound_edit.txt"
            probe_file.parent.mkdir(parents=True)
            probe_file.write_text("WBP_DEEPSEEK_ROUTE_BOUND_EDIT_OK", encoding="utf-8")

            with sqlite3.connect(profile_root / "state_5.sqlite") as connection:
                connection.execute(
                    "create table threads (id text, cwd text, model text, model_provider text, "
                    "created_at integer, updated_at integer)"
                )
                connection.execute(
                    "insert into threads values (?, ?, ?, ?, ?, ?)",
                    (
                        "thread-route-bound",
                        str(repo_root),
                        "wbp-deepseek-v4-pro-max",
                        "wbp",
                        1,
                        2,
                    ),
                )

            session_path = (
                profile_root
                / "sessions"
                / "2026"
                / "05"
                / "30"
                / "rollout-route-bound.jsonl"
            )
            session_path.parent.mkdir(parents=True)
            session_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "id": "thread-route-bound",
                                    "cwd": str(repo_root),
                                    "model_provider": "wbp",
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "payload": {
                                    "model": "wbp-deepseek-v4-pro-max",
                                    "cwd": str(repo_root),
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "function_call",
                                    "name": "exec_command",
                                    "arguments": (
                                        "mkdir -p .tmp && echo -n "
                                        "'WBP_DEEPSEEK_ROUTE_BOUND_EDIT_OK' > "
                                        ".tmp/deepseek_route_bound_edit.txt"
                                    ),
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "function_call_output",
                                    "output": "Process exited with code 0",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            packet = live_server.build_custom_codex_deepseek_route_bound_real_edit_packet(
                last_launch_packet={
                    "launch_id": "launch-route-bound-edit",
                    "trace_id": "trace-route-bound-edit",
                    "status": "ok",
                    "execution_mode": "api_only",
                    "selected_model": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                    "custom_codex_window_deepseek_launch_proven_with_limits": True,
                    "native_app_usable": True,
                    "real_codex_app_launched": True,
                    "stable_bridge_preflight_required": True,
                    "stable_bridge_preflight_status": "ok",
                    "stable_bridge_launch_allowed": True,
                    "persistent_profile_root": str(profile_root),
                    "original_codex_touched": False,
                    "asar_touched": False,
                },
                bridge_trace_packet={
                    "last_record": {
                        "launch_packet_id": "launch-route-bound-edit",
                        "trace_id": "trace-route-bound-edit",
                        "route_digest_matches_launch": True,
                        "request_seen_after_launch": True,
                        "provider_called": True,
                        "provider_id": "deepseek",
                        "upstream_model": "deepseek-v4-pro",
                        "response_seen": True,
                        "forced_route_used": True,
                        "fallback_used": False,
                        "chatgpt_route_used": False,
                    }
                },
                browser_payload={
                    "execution_mode": "api_only",
                    "api_model_id": "wbp-deepseek-v4-pro-max",
                    "api_reasoning_option_id": "provider_declared_max",
                },
                repo_root=repo_root,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_DEEPSEEK_ROUTE_BOUND_REAL_EDIT_PROVEN_WITH_LIMITS",
        )
        self.assertEqual(packet["packet_kind"], "custom_codex_deepseek_route_bound_real_edit")
        self.assertTrue(packet["file_created"])
        self.assertTrue(packet["file_content_exact"])
        self.assertTrue(packet["provider_called"])
        self.assertEqual(packet["provider_id"], "deepseek")
        self.assertEqual(packet["upstream_model"], "deepseek-v4-pro")
        self.assertTrue(packet["route_digest_matches_launch"])
        self.assertTrue(packet["trace_launch_packet_matches"])
        self.assertTrue(packet["trace_id_matches_launch"])
        self.assertTrue(packet["forced_route_used"])
        self.assertFalse(packet["forced_route_counts_as_fallback"])
        self.assertTrue(packet["log_evidence"]["session_jsonl_seen"])
        self.assertTrue(packet["log_evidence"]["tool_call_seen"])
        self.assertTrue(packet["log_evidence"]["tool_result_success"])
        self.assertFalse(packet["chatgpt_called"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["wbp_patch_applier_used"])


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_test_device_login_cli_proxy(
    path: Path,
    *,
    argv_capture_path: Path,
    ready_file: Path,
    auth_filename: str = "codex-device-login.json",
) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, re, sys, time\n"
        "from pathlib import Path\n"
        f"argv_capture = Path({str(argv_capture_path)!r})\n"
        f"ready_file = Path({str(ready_file)!r})\n"
        "argv_capture.write_text(json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n"
        "config = Path(sys.argv[sys.argv.index('-config') + 1])\n"
        "text = config.read_text(encoding='utf-8')\n"
        "match = re.search(r'^auth-dir:\\s*[\"\\']?(.*?)[\"\\']?\\s*$', text, re.M)\n"
        "if not match:\n"
        "    raise SystemExit('missing auth-dir')\n"
        "auth_dir = Path(match.group(1)).expanduser()\n"
        "if not auth_dir.is_absolute():\n"
        "    auth_dir = config.parent / auth_dir\n"
        "auth_dir.mkdir(parents=True, exist_ok=True)\n"
        "print('Codex device URL: https://auth.openai.com/codex/device', flush=True)\n"
        "print('Codex device code: WBP-1234', flush=True)\n"
        "deadline = time.time() + float(os.environ.get('WBP_TEST_DEVICE_LOGIN_WAIT_SECONDS', '10'))\n"
        "while time.time() < deadline:\n"
        "    if ready_file.exists():\n"
        "        payload = {\n"
        "            'type': 'codex',\n"
        "            'email': 'device-login@example.com',\n"
        "            'access_token': 'token-device-login',\n"
        "            'account_id': 'acct-device-login',\n"
        "        }\n"
        f"        (auth_dir / {auth_filename!r}).write_text(json.dumps(payload) + '\\n', encoding='utf-8')\n"
        "        raise SystemExit(0)\n"
        "    time.sleep(0.05)\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def fetch(url: str) -> str:
    with NO_PROXY_OPENER.open(url, timeout=3) as response:
        return response.read().decode("utf-8")


def _web_origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _web_bootstrap_tokens(url: str) -> tuple[str, str]:
    origin = _web_origin(url)
    html = fetch(f"{origin}/")

    def meta(name: str) -> str:
        pattern = rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]+)"'
        match = re.search(pattern, html)
        if match is None:
            raise AssertionError(f"missing web bootstrap meta: {name}")
        return match.group(1)

    return (meta(WEB_TOKEN_META_NAME), meta(WEB_CSRF_META_NAME))


def _web_post_headers(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    web_auth: bool = True,
    token_override: str | None = None,
    csrf_override: str | None = None,
) -> dict[str, str]:
    merged = dict(headers or {})
    if not web_auth:
        return merged
    token, csrf = _web_bootstrap_tokens(url)
    merged[WEB_AUTH_HEADER] = f"Bearer {token if token_override is None else token_override}"
    merged[WEB_CSRF_HEADER] = csrf if csrf_override is None else csrf_override
    return merged


def post_json(
    url: str,
    payload: dict[str, object],
    *,
    web_auth: bool = True,
    token_override: str | None = None,
    csrf_override: str | None = None,
) -> str:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_web_post_headers(
            url,
            {"Content-Type": "application/json"},
            web_auth=web_auth,
            token_override=token_override,
            csrf_override=csrf_override,
        ),
        method="POST",
    )
    with NO_PROXY_OPENER.open(request, timeout=10) as response:
        return response.read().decode("utf-8")


def post_body(url: str, body: bytes, *, web_auth: bool = True) -> str:
    request = urllib.request.Request(
        url,
        data=body,
        headers=_web_post_headers(
            url,
            {"Content-Type": "application/json"},
            web_auth=web_auth,
        ),
        method="POST",
    )
    with NO_PROXY_OPENER.open(request, timeout=10) as response:
        return response.read().decode("utf-8")


def post_body_response(
    url: str,
    body: bytes,
    *,
    headers: dict[str, str] | None = None,
    web_auth: bool = True,
    token_override: str | None = None,
    csrf_override: str | None = None,
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url,
        data=body,
        headers=_web_post_headers(
            url,
            headers or {"Content-Type": "application/json"},
            web_auth=web_auth,
            token_override=token_override,
            csrf_override=csrf_override,
        ),
        method="POST",
    )
    try:
        with NO_PROXY_OPENER.open(request, timeout=10) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8"))


def raw_http_json_response(
    *,
    port: int,
    method: str,
    path: str,
    host: str,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    web_auth: bool = True,
) -> tuple[int, dict[str, object]]:
    merged_headers = dict(headers or {})
    if method.upper() == "POST" and web_auth:
        token, csrf = _web_bootstrap_tokens(f"http://127.0.0.1:{port}/")
        merged_headers[WEB_AUTH_HEADER] = f"Bearer {token}"
        merged_headers[WEB_CSRF_HEADER] = csrf
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest(method, path, skip_host=True)
    conn.putheader("Host", host)
    for key, value in merged_headers.items():
        conn.putheader(key, value)
    conn.endheaders()
    if body:
        conn.send(body)
    response = conn.getresponse()
    raw_body = response.read().decode("utf-8")
    status = int(response.status)
    conn.close()
    return status, json.loads(raw_body)


if __name__ == "__main__":
    unittest.main()
