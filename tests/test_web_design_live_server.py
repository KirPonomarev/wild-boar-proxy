# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import socket
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from wild_boar_proxy.ui_shell import CommandResult
from wild_boar_proxy.web_design_command_adapter import ALLOWLIST
from wild_boar_proxy.web_design_live_server import (
    ACCOUNTS_READONLY_COMMAND_IDS,
    API_CONNECTIONS_READONLY_COMMAND_IDS,
    READONLY_COMMAND_IDS,
    build_api_connections_readonly_snapshot,
    build_accounts_readonly_snapshot,
    build_handler,
    build_live_readonly_snapshot,
    run_ui_action,
    ui_action_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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

        self.assertEqual(onboard.argv_template, ("accounts", "onboard", "--json"))
        self.assertEqual(onboard.category, "onboarding")
        self.assertTrue(onboard.confirmation_required)
        self.assertEqual(onboard.required_args, ())
        self.assertEqual(onboard.allowed_args, ())

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

    def test_api_connections_readonly_calls_only_external_packets_and_redacts_secret_refs(self) -> None:
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
        serialized = json.dumps(snapshot)
        self.assertNotIn("OPENROUTER_API_KEY", serialized)
        self.assertNotIn('"secret_ref"', serialized)
        self.assertNotIn("/Users/", serialized)

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
        self.assertNotIn(("sync", "--json"), runner.calls)
        self.assertNotIn(("launch", "client", "--json"), runner.calls)

    def test_ui_action_metadata_hides_adapter_commands_and_marks_confirmed_actions(self) -> None:
        metadata = ui_action_metadata()
        bounded_metadata = ui_action_metadata(launch_client_path="/Applications/Codex.app")

        self.assertEqual(metadata["status"], "ok")
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
        self.assertTrue(metadata["actions"]["sync_runtime"]["confirmation_required"])
        self.assertTrue(metadata["actions"]["sync_runtime"]["mutates_runtime"])
        self.assertTrue(metadata["actions"]["sync_runtime"]["post_action_refresh_required"])
        self.assertTrue(metadata["actions"]["set_mode_stable"]["confirmation_required"])
        self.assertTrue(metadata["actions"]["set_mode_managed"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["launch_smoke"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["launch_smoke"]["mutates_runtime"])
        self.assertIn("не успех запуска внешнего клиента", metadata["actions"]["launch_smoke"]["action_claim_scope"])
        self.assertIn("export_diagnostics", metadata["actions"])
        self.assertEqual(metadata["actions"]["export_diagnostics"]["action_role"], "support_artifact")
        self.assertFalse(metadata["actions"]["export_diagnostics"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["export_diagnostics"]["affects_primary_truth"])
        self.assertFalse(metadata["actions"]["export_diagnostics"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["export_diagnostics"]["post_action_refresh_required"])
        self.assertIn("диагностический пакет поддержки", metadata["actions"]["export_diagnostics"]["action_claim_scope"])
        self.assertIn("onboard_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["onboard_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["onboard_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["onboard_account"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["onboard_account"]["action_role"], "account_onboarding")
        self.assertEqual(metadata["actions"]["onboard_account"]["mutation_class"], "account_admission")
        self.assertIn(
            "пакет команды и обновлённый список аккаунтов",
            metadata["actions"]["onboard_account"]["action_claim_scope"],
        )
        self.assertTrue(metadata["actions"]["onboard_account"]["post_action_refresh_required"])
        self.assertIn("validate_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["validate_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["validate_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["validate_account"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["validate_account"]["action_role"], "account_verification")
        self.assertTrue(metadata["actions"]["validate_account"]["post_action_refresh_required"])
        self.assertIn("promote_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["promote_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["promote_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["promote_account"]["affects_primary_truth"])
        self.assertEqual(
            metadata["actions"]["promote_account"]["action_role"],
            "account_lifecycle_promotion",
        )
        self.assertTrue(metadata["actions"]["promote_account"]["post_action_refresh_required"])
        self.assertIn("demote_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["demote_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["demote_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["demote_account"]["affects_primary_truth"])
        self.assertEqual(
            metadata["actions"]["demote_account"]["action_role"],
            "account_lifecycle_demotion",
        )
        self.assertTrue(metadata["actions"]["demote_account"]["post_action_refresh_required"])
        self.assertIn("retire_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["retire_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["retire_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["retire_account"]["affects_primary_truth"])
        self.assertEqual(
            metadata["actions"]["retire_account"]["action_role"],
            "account_lifecycle_retirement",
        )
        self.assertIn(
            "терминальный lifecycle-запрос",
            metadata["actions"]["retire_account"]["action_claim_scope"],
        )
        self.assertTrue(metadata["actions"]["retire_account"]["post_action_refresh_required"])
        self.assertIn("hold_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["hold_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["hold_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["hold_account"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["hold_account"]["action_role"], "account_lifecycle_hold")
        self.assertTrue(metadata["actions"]["hold_account"]["post_action_refresh_required"])
        self.assertIn("release_account", metadata["actions"])
        self.assertTrue(metadata["actions"]["release_account"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["release_account"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["release_account"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["release_account"]["action_role"], "account_lifecycle_release")
        self.assertTrue(metadata["actions"]["release_account"]["post_action_refresh_required"])
        self.assertIn("api_route_validate", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_validate"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_validate"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_validate"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["api_route_validate"]["action_role"], "api_route_validation")
        self.assertEqual(
            metadata["actions"]["api_route_validate"]["mutation_class"],
            "api_route_verification",
        )
        self.assertTrue(metadata["actions"]["api_route_validate"]["post_action_refresh_required"])
        self.assertIn("runtime readiness", metadata["actions"]["api_route_validate"]["action_claim_scope"])
        self.assertIn("api_route_check", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_check"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_check"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_check"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["api_route_check"]["action_role"], "api_route_smoke_check")
        self.assertEqual(
            metadata["actions"]["api_route_check"]["mutation_class"],
            "api_route_verification",
        )
        self.assertTrue(metadata["actions"]["api_route_check"]["post_action_refresh_required"])
        self.assertIn("runtime readiness", metadata["actions"]["api_route_check"]["action_claim_scope"])
        self.assertIn("api_route_allow", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_allow"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_allow"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_allow"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["api_route_allow"]["action_role"], "api_route_lifecycle_allow")
        self.assertEqual(
            metadata["actions"]["api_route_allow"]["mutation_class"],
            "api_route_lifecycle",
        )
        self.assertTrue(metadata["actions"]["api_route_allow"]["post_action_refresh_required"])
        self.assertIn("runtime readiness", metadata["actions"]["api_route_allow"]["action_claim_scope"])
        self.assertIn("api_route_disable", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_disable"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_disable"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_disable"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["api_route_disable"]["action_role"], "api_route_lifecycle_disable")
        self.assertEqual(
            metadata["actions"]["api_route_disable"]["mutation_class"],
            "api_route_lifecycle",
        )
        self.assertTrue(metadata["actions"]["api_route_disable"]["post_action_refresh_required"])
        self.assertIn("runtime readiness", metadata["actions"]["api_route_disable"]["action_claim_scope"])
        self.assertIn("api_route_remove", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_remove"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_remove"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_remove"]["affects_primary_truth"])
        self.assertEqual(
            metadata["actions"]["api_route_remove"]["action_role"],
            "api_route_registry_cleanup",
        )
        self.assertEqual(
            metadata["actions"]["api_route_remove"]["mutation_class"],
            "api_route_registry_cleanup",
        )
        self.assertTrue(metadata["actions"]["api_route_remove"]["post_action_refresh_required"])
        self.assertIn("registry-записи", metadata["actions"]["api_route_remove"]["action_claim_scope"])
        self.assertIn("api_route_profile", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_profile"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_profile"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_profile"]["affects_primary_truth"])
        self.assertEqual(metadata["actions"]["api_route_profile"]["action_role"], "api_route_profile_packet")
        self.assertEqual(
            metadata["actions"]["api_route_profile"]["mutation_class"],
            "api_route_support",
        )
        self.assertFalse(metadata["actions"]["api_route_profile"]["post_action_refresh_required"])
        self.assertIn("Codex config mutation", metadata["actions"]["api_route_profile"]["action_claim_scope"])
        self.assertIn("api_route_evidence_capture", metadata["actions"])
        self.assertTrue(metadata["actions"]["api_route_evidence_capture"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["api_route_evidence_capture"]["mutates_runtime"])
        self.assertFalse(metadata["actions"]["api_route_evidence_capture"]["affects_primary_truth"])
        self.assertEqual(
            metadata["actions"]["api_route_evidence_capture"]["action_role"],
            "api_route_local_evidence_capture",
        )
        self.assertEqual(
            metadata["actions"]["api_route_evidence_capture"]["mutation_class"],
            "api_route_support_artifact",
        )
        self.assertFalse(metadata["actions"]["api_route_evidence_capture"]["post_action_refresh_required"])
        self.assertIn(
            "runtime proof",
            metadata["actions"]["api_route_evidence_capture"]["action_claim_scope"],
        )
        self.assertIn("launch_client_dispatch", metadata["actions"])
        self.assertTrue(metadata["actions"]["launch_client_dispatch"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertIn("недоступен", metadata["actions"]["launch_client_dispatch"]["unavailable_reason"])
        self.assertTrue(bounded_metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertEqual(bounded_metadata["actions"]["launch_client_dispatch"]["unavailable_reason"], "")
        self.assertNotIn("/Applications/Codex.app", json.dumps(bounded_metadata))

    def test_onboard_account_action_executes_exact_command_without_browser_args(self) -> None:
        runner = MappingRunner(live_payloads())

        result = run_ui_action(runner, {"ui_action": "onboard_account"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action_role"], "account_onboarding")
        self.assertEqual(result["mutation_class"], "account_admission")
        self.assertFalse(result["mutates_runtime"])
        self.assertFalse(result["affects_primary_truth"])
        self.assertTrue(result["confirmation_required"])
        self.assertTrue(result["post_action_refresh_required"])
        self.assertEqual(result["account_id"], "")
        self.assertEqual(result["result"]["onboarding"]["ui_state"], "success")
        self.assertEqual(
            result["result"]["onboarding"]["final_outcome"],
            "reserve_only_success",
        )
        self.assertEqual(result["result"]["onboarding"]["input_mode"], "default")
        self.assertEqual(
            result["result"]["onboarding"]["auth_snapshot_before_login_status"],
            "ok",
        )
        self.assertEqual(result["result"]["onboarding"]["external_command_status"], "nonzero")
        self.assertTrue(result["result"]["onboarding"]["reserve_first_proven"])
        self.assertEqual(result["result"]["onboarding"]["selected_backend_id"], "acct-new")
        self.assertEqual(runner.calls, [("accounts", "onboard", "--json")])

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

        for payload in [raw_action, auth_ref, source_dir, credentials, backend_id]:
            self.assertEqual(payload["status"], "integration_failure")
            self.assertEqual(payload["action_role"], "blocked")
            self.assertEqual(payload["result"]["machine_error_code"], "UI_ACTION_NOT_ALLOWED")
        self.assertEqual(runner.calls, [])

    def test_onboard_outcomes_do_not_overclaim_success_without_reserve_proof(self) -> None:
        no_new_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "onboard", "--json"): onboarding_packet("no_new_auth_detected"),
            }
        )
        ambiguous_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "onboard", "--json"): onboarding_packet(
                    "ambiguous_new_auth_detection",
                    selected_backend_id="",
                    pool_after_onboarding="",
                    reserve_first_enforced=False,
                ),
            }
        )
        unknown_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "onboard", "--json"): command_packet(
                    human_message="Onboarding packet had no structured result."
                ),
            }
        )
        validate_failed_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "onboard", "--json"): onboarding_packet("validate_failed"),
            }
        )
        command_error_runner = MappingRunner(
            {
                **live_payloads(),
                ("accounts", "onboard", "--json"): onboarding_packet(
                    "reserve_only_success",
                    status="error",
                    machine_error_code="ONBOARDING_OWNER_FAILED",
                ),
            }
        )

        no_new = run_ui_action(no_new_runner, {"ui_action": "onboard_account"})
        ambiguous = run_ui_action(ambiguous_runner, {"ui_action": "onboard_account"})
        unknown = run_ui_action(unknown_runner, {"ui_action": "onboard_account"})
        validate_failed = run_ui_action(validate_failed_runner, {"ui_action": "onboard_account"})
        command_error = run_ui_action(command_error_runner, {"ui_action": "onboard_account"})

        self.assertEqual(no_new["result"]["onboarding"]["ui_state"], "needs_user_action")
        self.assertTrue(no_new["result"]["onboarding"]["operator_action_required"])
        self.assertEqual(ambiguous["result"]["onboarding"]["ui_state"], "needs_user_action")
        self.assertTrue(ambiguous["result"]["onboarding"]["operator_action_required"])
        self.assertEqual(unknown["result"]["onboarding"]["ui_state"], "unknown_outcome")
        self.assertTrue(unknown["result"]["onboarding"]["operator_action_required"])
        self.assertEqual(validate_failed["result"]["onboarding"]["ui_state"], "command_error")
        self.assertTrue(validate_failed["result"]["onboarding"]["operator_action_required"])
        self.assertEqual(command_error["status"], "command_error")
        self.assertEqual(command_error["result"]["onboarding"]["ui_state"], "command_error")
        self.assertTrue(command_error["result"]["onboarding"]["operator_action_required"])
        for payload in [no_new, ambiguous, unknown, validate_failed, command_error]:
            self.assertNotEqual(payload["result"]["onboarding"]["ui_state"], "success")
            self.assertEqual(payload["result"]["onboarding"]["selected_backend_id"], "")

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
        self.assertTrue(result["confirmation_required"])
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
            launch_client_path="/Applications/Codex.app",
        )
        dispatched = run_ui_action(
            runner,
            {"ui_action": "launch_client_dispatch"},
            launch_client_path="/Applications/Codex.app",
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
        self.assertEqual(
            runner.calls[-1],
            ("launch", "client", "--client-path", "/Applications/Codex.app", "--json"),
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

    def test_http_action_endpoint_uses_ui_action_not_command_id(self) -> None:
        runner = MappingRunner(live_payloads())
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(runner=runner, launch_client_path="/Applications/Codex.app"),
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
        self.assertNotIn("/Applications/Codex.app", json.dumps(metadata))
        self.assertEqual(launch["status"], "ok")
        self.assertEqual(validate["status"], "ok")
        self.assertEqual(validate["action_role"], "account_verification")
        self.assertEqual(
            runner.calls,
            [
                ("diagnostics", "export", "--json"),
                ("launch", "client", "--client-path", "/Applications/Codex.app", "--json"),
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
            build_handler(runner=runner, launch_client_path="/Applications/Codex.app"),
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
            action_results["onboard_account"]["result"]["onboarding"]["final_outcome"],
            "reserve_only_success",
        )
        self.assertTrue(
            action_results["onboard_account"]["result"]["onboarding"]["reserve_first_proven"]
        )
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
                ("launch", "client", "--client-path", "/Applications/Codex.app", "--json"),
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
                ("accounts", "onboard", "--json"),
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
        ("accounts", "onboard", "--json"): onboarding_packet("reserve_only_success"),
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
        ("launch", "client", "--client-path", "/Applications/Codex.app", "--json"): command_packet(
            human_message="Client dispatch requested.",
            data={"launch_claim_scope": "dispatch_requested"},
        ),
        ("rollout", "rotation", "inspect", "--json"): command_packet(
            human_message="Rotation inspect passed."
        ),
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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
    with NO_PROXY_OPENER.open(request, timeout=3) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
