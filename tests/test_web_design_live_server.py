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
                ("healthcheck", "--json"),
                ("mode", "get", "--json"),
                ("accounts", "list", "--json"),
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

    def test_command_error_becomes_integration_failure_without_stale_green(self) -> None:
        payloads = live_payloads()
        payloads[("healthcheck", "--json")] = command_packet(
            status="error",
            machine_error_code="provider_network_failed",
            human_message="Network failed.",
        )
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["ui_state"], "integration_failure")
        self.assertEqual(snapshot["runtime"]["visual_state"], "integration_failure")
        self.assertEqual(snapshot["pool_summary"]["active"], 0)
        self.assertIn("Network failed", snapshot["runtime"]["last_error"])

    def test_mode_status_disagreement_becomes_integration_failure(self) -> None:
        payloads = live_payloads()
        payloads[("mode", "get", "--json")] = mode_packet(effective_mode="stable")
        runner = MappingRunner(payloads)

        snapshot = build_live_readonly_snapshot(runner)

        self.assertEqual(snapshot["status"], "integration_failure")
        self.assertEqual(snapshot["runtime"]["machine_error_code"], "UI_LIVE_READONLY_PACKET_INVALID")
        self.assertIn("disagree", snapshot["runtime"]["last_error"])

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


if __name__ == "__main__":
    unittest.main()
