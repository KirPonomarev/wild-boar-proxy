# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import socket
import threading
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from wild_boar_proxy.runtime import RuntimePaths, run_installer_init
from wild_boar_proxy.ui_shell import CommandResult
import wild_boar_proxy.web_design_live_server as live_server
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
        self.assertNotIn("setup_discovery", metadata["actions"])
        self.assertNotIn("select_client", metadata["actions"])
        self.assertNotIn("save_selection", metadata["actions"])
        self.assertNotIn("verify_path", metadata["actions"])
        self.assertNotIn("legacy_import", metadata["actions"])
        self.assertNotIn("import_apply", metadata["actions"])
        self.assertNotIn("installer_init", metadata["actions"])
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
        runner = MappingRunner(live_payloads())

        result = run_ui_action(
            runner,
            {"ui_action": "account_login_status", "session_id": TEST_CODEX_LOGIN_SESSION_ID},
            launch_copy_contract=launch_copy_contract(),
            action_phase=SANDBOX_ACTION_PHASE,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["session_id"], TEST_CODEX_LOGIN_SESSION_ID)
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
        self.assertNotIn("/tmp/private-client-path", json.dumps(dispatched))

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
        self.assertNotIn("setup_discovery", metadata["actions"])
        self.assertNotIn("select_client", metadata["actions"])
        self.assertNotIn("legacy_import", metadata["actions"])
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
        ("healthcheck", "--json"): command_packet(human_message="Healthcheck passed."),
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

    def run_prompt(self, payload: dict[str, object], *, trace_wbp: bool = False) -> dict[str, object]:
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
            "configured_provider": "cliproxy",
            "configured_wire_api": "responses",
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


class WebDesignCodexLaunchModeEndpointTests(unittest.TestCase):
    def test_codex_launch_mode_endpoints_are_bounded_and_readonly(self) -> None:
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
                custom_dry_run = json.loads(post_json(f"{base}/api/codex/custom/launch-dry-run", {}))
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
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        modes = {mode["id"]: mode for mode in launch_modes["modes"]}
        self.assertFalse(modes["original_codex"]["proxy_enabled"])
        self.assertFalse(modes["original_codex"]["proxy_allowed"])
        self.assertEqual(modes["original_codex"]["launch_claim_scope"], "dry_run_guard_only")
        self.assertTrue(modes["codex_custom"]["proxy_enabled"])
        self.assertTrue(modes["codex_custom"]["custom_codex_home_required"])
        self.assertFalse(modes["codex_custom"]["current_codex_home_allowed"])
        self.assertFalse(modes["codex_custom"]["custom_session_available"])
        self.assertFalse(original_status["proxy_injection_allowed"])
        self.assertFalse(original_status["proxy_allowed"])
        self.assertFalse(original_status["custom_home_allowed"])
        self.assertEqual(original_status["browser_payload_allowed_keys"], [])
        self.assertEqual(custom_status["launch_claim_scope"], "readonly_readiness_only")
        self.assertFalse(custom_status["current_codex_home_allowed"])
        self.assertFalse(custom_status["last_process_isolation_proof"]["fresh_truth"])
        self.assertEqual(dry_run["status"], "ok")
        self.assertTrue(dry_run["dry_run"])
        self.assertTrue(dry_run["dispatch_plan_safe"])
        self.assertFalse(dry_run["proxy_env_injected"])
        self.assertFalse(dry_run["custom_home_injected"])
        self.assertEqual(custom_dry_run["status"], "ok")
        self.assertTrue(custom_dry_run["dry_run"])
        self.assertTrue(custom_dry_run["custom_launch_plan_safe"])
        self.assertFalse(custom_dry_run["current_codex_home_allowed"])
        self.assertFalse(custom_dry_run["real_launch_attempted"])
        self.assertFalse(custom_dry_run["prompt_attempted"])
        self.assertEqual(custom_dry_run["token_burn"], 0)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(rejected["forbidden_fields"], ["model_id", "route_id", "CODEX_HOME"])
        self.assertEqual(custom_rejected["status"], "rejected")
        self.assertEqual(custom_rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(custom_rejected["forbidden_fields"], ["model", "route_id", "codex_home"])


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
        self.assertEqual(selection["selected_backend_source"], "server")
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
                        {"model_id": "gpt-5.3-codex"},
                    )
                )
                session_id = created["session"]["session_id"]
                detail = json.loads(fetch(f"{base}/api/codex/custom/sessions/{session_id}"))
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
        self.assertTrue(created["session"]["selection_dry_run_proven"])
        self.assertFalse(created["session"]["live_selection_proven"])
        self.assertTrue(created["session"]["selection_proven"])
        self.assertTrue(created["session"]["selected_backend_id_redacted"])
        self.assertEqual(created["session"]["session_root_scope"], "owned_temp_session_root")
        self.assertNotIn("/tmp/wbp-auth.json", json.dumps(created))
        self.assertNotIn("acct-active", json.dumps(created))
        self.assertEqual(detail["session"]["session_id"], session_id)
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
                created = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {"model_id": "gpt-5.3-codex"},
                    )
                )
                ready = json.loads(
                    fetch(f"{base}/api/codex/custom/recovery/admitted-session-actions")
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
                try:
                    post_json(f"{base}/api/codex/custom/recovery/admitted-session-actions", {})
                except urllib.error.HTTPError as exc:
                    post_rejected_status = exc.code
                else:  # pragma: no cover - defensive assertion branch
                    post_rejected_status = HTTPStatus.OK
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["block_reason_code"], "SELECTED_SESSION_REQUIRED")
        self.assertFalse(blocked["session_admitted_actions_ready"])
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
        self.assertTrue(cancel["cancelled"])
        self.assertFalse(cancel["process_kill_claimed"])
        self.assertTrue(cleanup["cleanup_performed"])
        self.assertTrue(cleanup["owned_session_root_only"])
        self.assertFalse(cleanup["arbitrary_path_accepted"])
        self.assertEqual(after_cleanup["status"], "blocked")
        self.assertEqual(after_cleanup["block_reason_code"], "SELECTED_SESSION_ALREADY_CLEANED")
        self.assertFalse(after_cleanup["session_admitted_actions_ready"])
        self.assertEqual(post_rejected_status, HTTPStatus.NOT_FOUND)

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
                non_object_request = urllib.request.Request(
                    f"{base}/api/codex/custom/recovery/rollback-point",
                    data=b"[]",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                non_object_create = json.loads(
                    NO_PROXY_OPENER.open(non_object_request, timeout=10)
                    .read()
                    .decode("utf-8")
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
                non_object_apply_request = urllib.request.Request(
                    f"{base}/api/codex/custom/recovery/rollback-apply",
                    data=b"[]",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                non_object_apply = json.loads(
                    NO_PROXY_OPENER.open(non_object_apply_request, timeout=10)
                    .read()
                    .decode("utf-8")
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
        self.assertEqual(non_object_create["status"], "blocked")
        self.assertEqual(
            non_object_create["machine_error_code"],
            "ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
        )
        self.assertIn("invalid_body", non_object_create["forbidden_fields"])
        self.assertFalse(non_object_create["filesystem_write_performed"])
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
        self.assertEqual(non_object_apply["status"], "blocked")
        self.assertEqual(
            non_object_apply["machine_error_code"],
            "ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("invalid_body", non_object_apply["forbidden_fields"])
        self.assertFalse(non_object_apply["filesystem_write_performed"])

    def test_codex_custom_session_create_rejects_free_form_model_and_backend(self) -> None:
        with mock.patch.object(live_server, "OperatorSurfaceSession", FakeOperatorSurfaceSession):
            server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=MappingRunner(live_payloads())))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                bad_model = json.loads(
                    post_json(f"{base}/api/codex/custom/sessions", {"model_id": "free-form"})
                )
                bad_backend = json.loads(
                    post_json(
                        f"{base}/api/codex/custom/sessions",
                        {
                            "model_id": "gpt-5.3-codex",
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
                        {"model_id": "gpt-5.3-codex"},
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
                        {"model_id": "gpt-5.3-codex"},
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
        self.assertFalse(proof["current_codex_touched"])
        self.assertTrue(proof["live_prompt_full_success"])
        self.assertFalse(proof["browser_selected_backend"])
        self.assertEqual(
            created_sessions[0].run_payloads,
            [{"prompt": "Reply with exactly WBP_LIVE_OK.", "model_id": "gpt-5.3-codex"}],
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
                        {"model_id": "gpt-5.3-codex"},
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


def post_json(url: str, payload: dict[str, object]) -> str:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with NO_PROXY_OPENER.open(request, timeout=10) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
