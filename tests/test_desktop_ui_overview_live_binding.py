from __future__ import annotations

import json
import unittest
from typing import Sequence

from wild_boar_proxy.desktop_ui.command_adapter import RunnerResult
from wild_boar_proxy.desktop_ui.live_overview import READ_COMMAND_IDS, collect_live_overview_payload


def packet(**overrides):
    base = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "ok",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "healthy",
        "severity": "info",
        "operator_action": "none",
    }
    base.update(overrides)
    return base


class OverviewRunner:
    def __init__(self, packets: dict[tuple[str, ...], str]):
        self.packets = packets
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str], timeout_seconds: float) -> RunnerResult:
        tail = tuple(argv[3:])
        self.calls.append(tail)
        return RunnerResult(0, self.packets[tail])


def default_packets() -> dict[tuple[str, ...], str]:
    return {
        ("status", "--json"): json.dumps(packet(
            desired_mode="managed",
            effective_mode="managed",
            endpoint="http://127.0.0.1:8320",
            last_error="",
        )),
        ("healthcheck", "--json"): json.dumps(packet(attestation={"listener_ok": True})),
        ("mode", "get", "--json"): json.dumps(packet(desired_mode="managed", effective_mode="managed")),
        ("accounts", "list", "--json"): json.dumps(packet(accounts=[
            {"id": "active-1", "pool": "active", "status": "healthy", "auth_ref": "/private/auth.json"},
            {"id": "reserve-1", "pool": "reserve", "status": "healthy", "auth_ref": "/private/reserve.json"},
            {"id": "down-1", "pool": "active", "status": "down", "auth_ref": "/private/down.json"},
        ])),
        ("rollout", "rotation", "inspect", "--json"): json.dumps(packet(
            rotation_evidence_result={
                "participation_status": "observed",
                "evidence_status": "available",
            }
        )),
    }


class DesktopUiOverviewLiveBindingTests(unittest.TestCase):
    def test_collects_only_admitted_live_read_commands(self) -> None:
        runner = OverviewRunner(default_packets())
        payload = collect_live_overview_payload(runner=runner)

        self.assertEqual(payload["source"], "ui_desktop_html_live_overview_snapshot")
        self.assertIs(payload["synthetic"], False)
        self.assertEqual(payload["fixture_state"], "healthy")
        self.assertEqual(len(runner.calls), len(READ_COMMAND_IDS))
        self.assertEqual(set(runner.calls), {
            ("status", "--json"),
            ("healthcheck", "--json"),
            ("mode", "get", "--json"),
            ("accounts", "list", "--json"),
            ("rollout", "rotation", "inspect", "--json"),
        })

    def test_accounts_are_summarized_without_auth_refs(self) -> None:
        payload = collect_live_overview_payload(runner=OverviewRunner(default_packets()))

        summary = payload["accounts_packet"]["account_summary"]
        self.assertEqual(summary["active_count"], 2)
        self.assertEqual(summary["reserve_count"], 1)
        self.assertEqual(summary["problem_count"], 1)
        self.assertNotIn("auth_ref", json.dumps(payload))
        self.assertEqual(payload["accounts_packet"]["capacity_model"]["claim"], "capacity_model_only_not_scale_proof")

    def test_invalid_status_json_is_integration_failure_not_green(self) -> None:
        packets = default_packets()
        packets[("status", "--json")] = "{bad"
        payload = collect_live_overview_payload(runner=OverviewRunner(packets))

        self.assertEqual(payload["fixture_state"], "integration-failure")
        self.assertEqual(payload["status_packet"]["adapter_status"], "integration_failure")
        self.assertNotEqual(payload["status_packet"]["liveness"], "healthy")

    def test_command_error_status_is_visible_not_green(self) -> None:
        packets = default_packets()
        packets[("status", "--json")] = json.dumps(packet(
            status="error",
            exit_code=1,
            machine_error_code="LISTENER_DOWN",
            liveness="down",
            severity="recoverable",
            operator_action="user_action",
        ))
        payload = collect_live_overview_payload(runner=OverviewRunner(packets))

        self.assertEqual(payload["fixture_state"], "error")
        self.assertEqual(payload["status_packet"]["machine_error_code"], "LISTENER_DOWN")

    def test_stale_liveness_remains_stale_not_green(self) -> None:
        packets = default_packets()
        packets[("status", "--json")] = json.dumps(packet(liveness="stale"))
        payload = collect_live_overview_payload(runner=OverviewRunner(packets))

        self.assertEqual(payload["fixture_state"], "stale")
        self.assertNotEqual(payload["fixture_state"], "healthy")

    def test_desired_effective_mismatch_is_preserved(self) -> None:
        packets = default_packets()
        packets[("mode", "get", "--json")] = json.dumps(packet(
            desired_mode="managed",
            effective_mode="stable",
        ))
        payload = collect_live_overview_payload(runner=OverviewRunner(packets))

        self.assertEqual(payload["fixture_state"], "degraded")
        self.assertTrue(payload["mode_packet"]["mode_mismatch"])
        self.assertIn("Desired and effective modes differ", payload["notice"])

    def test_rotation_error_does_not_become_scale_claim(self) -> None:
        packets = default_packets()
        packets[("rollout", "rotation", "inspect", "--json")] = json.dumps(packet(
            status="error",
            exit_code=1,
            machine_error_code="ROTATION_EVIDENCE_CONTRADICTED",
            liveness="unknown",
            rotation_evidence_result={
                "participation_status": "contradicted",
                "evidence_status": "participation_evidence_contradicted",
            },
        ))
        payload = collect_live_overview_payload(runner=OverviewRunner(packets))

        self.assertEqual(payload["fixture_state"], "degraded")
        self.assertEqual(payload["rotation_summary"]["proof_claim"], "not_claimed")
        self.assertEqual(payload["rotation_summary"]["participation_status"], "contradicted")
        self.assertIn("rollout.rotation.inspect", payload["notice"])


if __name__ == "__main__":
    unittest.main()
