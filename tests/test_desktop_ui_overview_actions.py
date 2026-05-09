from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from wild_boar_proxy.desktop_ui.command_adapter import RunnerResult
from wild_boar_proxy.desktop_ui.overview_actions import (
    list_action_specs,
    list_deferred_action_ids,
    main,
    run_overview_action,
)


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


class RecordingRunner:
    def __init__(self, packets: dict[tuple[str, ...], str]):
        self.packets = packets
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str], timeout_seconds: float) -> RunnerResult:
        tail = tuple(argv[3:])
        self.calls.append(tail)
        return RunnerResult(0, self.packets[tail])


def refresh_packets() -> dict[tuple[str, ...], str]:
    return {
        ("status", "--json"): json.dumps(packet(desired_mode="stable", effective_mode="stable")),
        ("healthcheck", "--json"): json.dumps(packet()),
        ("mode", "get", "--json"): json.dumps(packet(desired_mode="stable", effective_mode="stable")),
        ("accounts", "list", "--json"): json.dumps(packet(accounts=[])),
        ("rollout", "rotation", "inspect", "--json"): json.dumps(packet()),
    }


class DesktopUiOverviewActionRunnerTests(unittest.TestCase):
    def test_allowed_action_with_confirmation_executes_and_refreshes(self) -> None:
        packets = refresh_packets()
        packets[("mode", "set", "stable", "--json")] = json.dumps(packet(changed_files=["state"]))
        runner = RecordingRunner(packets)
        with TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "overview_live_snapshot.json"
            result = run_overview_action("switch_stable", confirmed=True, runner=runner, snapshot_path=snapshot)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["command_id"], "mode.set.stable")
        self.assertEqual(result["post_action_refresh_status"], "ok")
        self.assertTrue(result["snapshot_written"])
        self.assertIn(("mode", "set", "stable", "--json"), runner.calls)
        self.assertIn(("status", "--json"), runner.calls)
        self.assertEqual(result["changed_files"], ["state"])

    def test_confirmation_is_required_before_adapter_execution(self) -> None:
        runner = RecordingRunner(refresh_packets())
        result = run_overview_action("switch_managed", confirmed=False, runner=runner)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(result["adapter_status"], "not_executed")
        self.assertEqual(runner.calls, [])

    def test_unknown_action_is_rejected_before_execution(self) -> None:
        runner = RecordingRunner(refresh_packets())
        result = run_overview_action("unknown_action", confirmed=True, runner=runner)

        self.assertEqual(result["machine_error_code"], "ACTION_FORBIDDEN")
        self.assertEqual(runner.calls, [])

    def test_deferred_action_is_rejected_before_execution(self) -> None:
        runner = RecordingRunner(refresh_packets())
        result = run_overview_action("stable_repair_apply", confirmed=True, runner=runner)

        self.assertEqual(result["machine_error_code"], "ACTION_DEFERRED")
        self.assertEqual(runner.calls, [])

    def test_command_error_is_not_success_even_after_refresh(self) -> None:
        packets = refresh_packets()
        packets[("sync", "--json")] = json.dumps(packet(
            status="error",
            exit_code=1,
            machine_error_code="SYNC_FAILED",
            liveness="unknown",
        ))
        runner = RecordingRunner(packets)
        result = run_overview_action("run_sync", confirmed=True, runner=runner)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["adapter_status"], "command_error")
        self.assertEqual(result["machine_error_code"], "SYNC_FAILED")
        self.assertEqual(result["post_action_refresh_status"], "ok")

    def test_invalid_json_is_integration_failure(self) -> None:
        packets = refresh_packets()
        packets[("launch", "smoke", "--json")] = "{bad"
        runner = RecordingRunner(packets)
        result = run_overview_action("run_smoke", confirmed=True, runner=runner)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["adapter_status"], "integration_failure")
        self.assertEqual(result["machine_error_code"], "INVALID_JSON")

    def test_post_action_refresh_failure_prevents_green_result(self) -> None:
        packets = refresh_packets()
        packets[("launch", "client", "--json")] = json.dumps(packet())
        runner = RecordingRunner(packets)

        def failing_refresh(snapshot_path: Path):
            raise RuntimeError("refresh unavailable")

        result = run_overview_action(
            "launch_client",
            confirmed=True,
            runner=runner,
            refresh_writer=failing_refresh,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["adapter_status"], "ok")
        self.assertEqual(result["machine_error_code"], "POST_ACTION_REFRESH_FAILED")
        self.assertEqual(result["post_action_refresh_status"], "error")
        self.assertFalse(result["snapshot_written"])

    def test_action_maps_contain_only_admitted_overview_actions(self) -> None:
        specs = list_action_specs()
        self.assertEqual(set(specs), {"switch_stable", "switch_managed", "run_sync", "launch_client", "run_smoke"})
        self.assertEqual({spec.command_id for spec in specs.values()}, {
            "mode.set.stable",
            "mode.set.managed",
            "sync",
            "launch.client",
            "launch.smoke",
        })

    def test_deferred_actions_include_rollout_and_stable_target_families(self) -> None:
        deferred = list_deferred_action_ids()
        self.assertIn("rollout_stage_prove", deferred)
        self.assertIn("rollout_stage_advance", deferred)
        self.assertIn("rollout_evidence_capture", deferred)
        self.assertIn("policy_stage_set", deferred)
        self.assertIn("stable_target_switch", deferred)

    def test_cli_emits_json_for_deferred_action(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "action.json"
            code = main(["stable_repair_apply", "--output", str(output)])
            packet_out = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 1)
        self.assertEqual(packet_out["machine_error_code"], "ACTION_DEFERRED")
        self.assertEqual(packet_out["adapter_status"], "not_executed")


if __name__ == "__main__":
    unittest.main()
