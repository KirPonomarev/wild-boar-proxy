from __future__ import annotations

import json
import subprocess
import unittest
from typing import Sequence

from wild_boar_proxy.desktop_ui.command_adapter import (
    AdapterErrorCode,
    RunnerResult,
    list_command_specs,
    run_command,
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
    def __init__(self, result: RunnerResult):
        self.result = result
        self.calls: list[tuple[tuple[str, ...], float]] = []

    def __call__(self, argv: Sequence[str], timeout_seconds: float) -> RunnerResult:
        self.calls.append((tuple(argv), timeout_seconds))
        return self.result


class DesktopUiCommandAdapterTests(unittest.TestCase):
    def test_valid_json_packet_returns_normalized_success(self) -> None:
        runner = RecordingRunner(RunnerResult(0, json.dumps(packet()), "debug detail"))
        result = run_command("status", runner=runner)

        self.assertTrue(result.allowed)
        self.assertEqual(result.adapter_status, "ok")
        self.assertEqual(result.raw_packet["machine_error_code"], "OK")
        self.assertEqual(result.support_stderr, "debug detail")
        self.assertEqual(result.command_class, "read")
        self.assertEqual(runner.calls[0][0][-2:], ("status", "--json"))

    def test_top_level_error_packet_is_command_error_not_integration_failure(self) -> None:
        runner = RecordingRunner(
            RunnerResult(1, json.dumps(packet(status="error", machine_error_code="LOCK_HELD")))
        )
        result = run_command("status", runner=runner)

        self.assertEqual(result.adapter_status, "command_error")
        self.assertEqual(result.error_code, AdapterErrorCode.OK)
        self.assertEqual(result.raw_packet["machine_error_code"], "LOCK_HELD")

    def test_invalid_json_is_integration_failure_even_when_exit_code_zero(self) -> None:
        runner = RecordingRunner(RunnerResult(0, "not json"))
        result = run_command("status", runner=runner)

        self.assertEqual(result.adapter_status, "integration_failure")
        self.assertEqual(result.error_code, AdapterErrorCode.INVALID_JSON)
        self.assertIsNone(result.raw_packet)

    def test_extra_stdout_after_json_is_integration_failure(self) -> None:
        runner = RecordingRunner(RunnerResult(0, json.dumps(packet()) + "\nnoise"))
        result = run_command("status", runner=runner)

        self.assertEqual(result.adapter_status, "integration_failure")
        self.assertEqual(result.error_code, AdapterErrorCode.INVALID_JSON)

    def test_missing_required_top_level_fields_is_integration_failure(self) -> None:
        bad_packet = packet()
        del bad_packet["machine_error_code"]
        runner = RecordingRunner(RunnerResult(0, json.dumps(bad_packet)))
        result = run_command("status", runner=runner)

        self.assertEqual(result.adapter_status, "integration_failure")
        self.assertEqual(result.error_code, AdapterErrorCode.INVALID_PACKET)
        self.assertIn("machine_error_code", result.error_message)

    def test_timeout_is_integration_failure(self) -> None:
        def timeout_runner(argv: Sequence[str], timeout_seconds: float) -> RunnerResult:
            raise subprocess.TimeoutExpired(argv, timeout_seconds)

        result = run_command("status", timeout_seconds=0.25, runner=timeout_runner)

        self.assertEqual(result.adapter_status, "integration_failure")
        self.assertEqual(result.error_code, AdapterErrorCode.COMMAND_TIMEOUT)
        self.assertEqual(result.timeout_seconds, 0.25)

    def test_forbidden_command_is_rejected_before_execution(self) -> None:
        runner = RecordingRunner(RunnerResult(0, json.dumps(packet())))
        result = run_command("rollout.stage.advance", runner=runner)

        self.assertFalse(result.allowed)
        self.assertEqual(result.error_code, AdapterErrorCode.COMMAND_FORBIDDEN)
        self.assertEqual(runner.calls, [])

    def test_account_argument_is_argv_part_not_shell_string(self) -> None:
        account_id = "acct; rm -rf /"
        runner = RecordingRunner(RunnerResult(0, json.dumps(packet())))
        result = run_command("accounts.validate", args={"id": account_id}, runner=runner)

        self.assertEqual(result.adapter_status, "ok")
        argv = runner.calls[0][0]
        self.assertIn(account_id, argv)
        self.assertEqual(argv[-4:], ("accounts", "validate", account_id, "--json"))

    def test_missing_structured_argument_is_integration_failure(self) -> None:
        result = run_command("accounts.validate", args={}, runner=RecordingRunner(RunnerResult(0, "{}")))

        self.assertEqual(result.adapter_status, "integration_failure")
        self.assertEqual(result.error_code, AdapterErrorCode.INVALID_PACKET)

    def test_previous_success_is_not_reused_after_invalid_json(self) -> None:
        success = RecordingRunner(RunnerResult(0, json.dumps(packet())))
        failure = RecordingRunner(RunnerResult(0, "{bad"))

        first = run_command("status", runner=success)
        second = run_command("status", runner=failure)

        self.assertEqual(first.adapter_status, "ok")
        self.assertEqual(second.adapter_status, "integration_failure")
        self.assertIsNone(second.raw_packet)

    def test_high_confirmation_actions_are_explicit(self) -> None:
        specs = list_command_specs()
        self.assertEqual(specs["stable.repair.apply"].confirmation_level, "high")
        self.assertEqual(specs["accounts.promote"].confirmation_level, "high")
        self.assertEqual(specs["mode.set.managed"].confirmation_level, "high")
        self.assertEqual(specs["stable.repair.dry_run"].confirmation_level, "none")

    def test_deferred_rollout_and_stable_target_commands_are_not_allowlisted(self) -> None:
        specs = list_command_specs()
        self.assertNotIn("rollout.stage.prove", specs)
        self.assertNotIn("rollout.stage.advance", specs)
        self.assertNotIn("rollout.evidence.capture", specs)
        self.assertNotIn("stable.target.switch", specs)


if __name__ == "__main__":
    unittest.main()
