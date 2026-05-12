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
from wild_boar_proxy.web_design_live_server import (
    READONLY_COMMAND_IDS,
    build_handler,
    build_live_readonly_snapshot,
    run_ui_action,
    ui_action_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"


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
) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "pool": pool,
        "manual_hold": manual_hold,
        "status": status,
        "fail_count": 0,
        "success_count": 1,
        "last_success": None,
        "last_error": last_error,
        "cooldown_until": None,
        "notes": "",
    }


class MappingRunner:
    def __init__(self, payloads: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> CommandResult:
        self.calls.append(args)
        return CommandResult(payload=dict(self.payloads[args]), stderr="")


class WebDesignLiveServerTests(unittest.TestCase):
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

    def test_http_server_serves_static_index_and_readonly_api(self) -> None:
        runner = MappingRunner(live_payloads())
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(runner=runner))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            index = fetch(f"{base_url}/?source=live")
            api = json.loads(fetch(f"{base_url}/api/live-readonly?command_id=sync"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertIn("sourcePicker", index)
        self.assertEqual(api["status"], "ok")
        self.assertNotIn(("sync", "--json"), runner.calls)
        self.assertNotIn(("launch", "client", "--json"), runner.calls)

    def test_ui_action_metadata_hides_adapter_commands_and_marks_confirmed_actions(self) -> None:
        metadata = ui_action_metadata()
        bounded_metadata = ui_action_metadata(launch_client_path="/Applications/Codex.app")

        self.assertEqual(metadata["status"], "ok")
        self.assertNotIn("adapter_command_id", json.dumps(metadata))
        self.assertTrue(metadata["actions"]["sync_runtime"]["confirmation_required"])
        self.assertTrue(metadata["actions"]["sync_runtime"]["mutates_runtime"])
        self.assertTrue(metadata["actions"]["sync_runtime"]["post_action_refresh_required"])
        self.assertTrue(metadata["actions"]["set_mode_stable"]["confirmation_required"])
        self.assertTrue(metadata["actions"]["set_mode_managed"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["launch_smoke"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["launch_smoke"]["mutates_runtime"])
        self.assertIn("not host-client launch", metadata["actions"]["launch_smoke"]["action_claim_scope"])
        self.assertIn("launch_client_dispatch", metadata["actions"])
        self.assertTrue(metadata["actions"]["launch_client_dispatch"]["confirmation_required"])
        self.assertFalse(metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertIn("unavailable", metadata["actions"]["launch_client_dispatch"]["unavailable_reason"])
        self.assertTrue(bounded_metadata["actions"]["launch_client_dispatch"]["available"])
        self.assertEqual(bounded_metadata["actions"]["launch_client_dispatch"]["unavailable_reason"], "")
        self.assertNotIn("/Applications/Codex.app", json.dumps(bounded_metadata))

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
        self.assertIn("not host-client launch", smoke["action_claim_scope"])
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
        self.assertIn("not host-client session success", dispatched["action_claim_scope"])
        self.assertEqual(
            runner.calls[-1],
            ("launch", "client", "--client-path", "/Applications/Codex.app", "--json"),
        )

    def test_ui_action_endpoint_blocks_command_id_payload_and_forbidden_actions(self) -> None:
        runner = MappingRunner(live_payloads())

        command_id_payload = run_ui_action(runner, {"command_id": "diagnostics_export"})
        stable_repair_apply = run_ui_action(runner, {"ui_action": "stable_repair_apply"})
        launch_client = run_ui_action(runner, {"ui_action": "launch_client"})
        client_path_payload = run_ui_action(
            runner,
            {"ui_action": "export_diagnostics", "client_path": "/Applications/Codex.app"},
        )
        unknown = run_ui_action(runner, {"ui_action": "policy_stage_set"})

        for payload in [command_id_payload, stable_repair_apply, launch_client, client_path_payload, unknown]:
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
        self.assertEqual(
            runner.calls,
            [
                ("diagnostics", "export", "--json"),
                ("launch", "client", "--client-path", "/Applications/Codex.app", "--json"),
            ],
        )

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
    }


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=3) as response:
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict[str, object]) -> str:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
