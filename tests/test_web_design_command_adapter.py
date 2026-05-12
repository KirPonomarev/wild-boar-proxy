# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from wild_boar_proxy.ui_shell import CommandResult, UiShellError
from wild_boar_proxy.web_design_command_adapter import (
    ALLOWLIST,
    allowlist_metadata,
    execute_command,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"


def packet(**overrides: object) -> dict[str, object]:
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


class RecordingRunner:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.payload = payload or packet()

    def run(self, *args: str) -> CommandResult:
        self.calls.append(args)
        return CommandResult(payload=dict(self.payload), stderr="")


class RaisingRunner:
    def __init__(self, error: Exception) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.error = error

    def run(self, *args: str) -> CommandResult:
        self.calls.append(args)
        raise self.error


class WebDesignCommandAdapterTests(unittest.TestCase):
    def test_allowlist_is_explicit_and_launch_client_is_disabled(self) -> None:
        expected = {
            "status",
            "healthcheck",
            "mode_get",
            "accounts_list",
            "rollout_rotation_inspect",
            "mode_stable",
            "mode_managed",
            "sync",
            "smoke",
            "stable_repair_dry_run",
            "stable_repair_apply",
            "diagnostics_export",
            "launch_client",
        }

        self.assertEqual(set(ALLOWLIST), expected)
        self.assertFalse(ALLOWLIST["launch_client"].ui_enabled)
        self.assertTrue(ALLOWLIST["launch_client"].confirmation_required)
        self.assertFalse(ALLOWLIST["smoke"].confirmation_required)
        self.assertIn(
            {
                "command_id": "launch_client",
                "category": "action",
                "ui_enabled": False,
                "confirmation_required": True,
                "required_args": ["client_path"],
                "allowed_args": ["client_path"],
                "argv": ["launch", "client", "--client-path", "{client_path}", "--json"],
            },
            allowlist_metadata(),
        )

    def test_allowed_truth_command_runs_exact_argv(self) -> None:
        runner = RecordingRunner()

        result = execute_command(runner, "status")

        self.assertEqual(runner.calls, [("status", "--json")])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["ui_state"], "success")
        self.assertEqual(result["machine_error_code"], "OK")

    def test_forbidden_command_is_rejected_without_runner_call(self) -> None:
        runner = RecordingRunner()

        result = execute_command(runner, "policy_stage_advance")

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["status"], "integration_failure")
        self.assertEqual(result["ui_state"], "integration_failure")
        self.assertEqual(result["machine_error_code"], "UI_COMMAND_INTEGRATION_FAILURE")
        self.assertIn("not allowlisted", result["human_message"])

    def test_extra_structured_args_are_rejected(self) -> None:
        runner = RecordingRunner()

        result = execute_command(runner, "sync", structured_args={"shell": "rm -rf /"})

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["status"], "integration_failure")
        self.assertIn("unsupported args", result["human_message"])

    def test_disabled_command_does_not_validate_into_execution_path(self) -> None:
        runner = RecordingRunner()

        result = execute_command(
            runner,
            "launch_client",
            structured_args={"client_path": 123},  # type: ignore[dict-item]
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["status"], "integration_failure")
        self.assertIn("disabled", result["human_message"])

    def test_disabled_launch_client_is_not_executable_in_this_contour(self) -> None:
        runner = RecordingRunner()

        result = execute_command(
            runner,
            "launch_client",
            structured_args={"client_path": "/Applications/Codex.app"},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["status"], "integration_failure")
        self.assertIn("disabled", result["human_message"])

    def test_runner_parse_error_maps_to_integration_failure(self) -> None:
        runner = RaisingRunner(UiShellError("stdout must contain exactly one JSON object"))

        result = execute_command(runner, "healthcheck")

        self.assertEqual(runner.calls, [("healthcheck", "--json")])
        self.assertEqual(result["status"], "integration_failure")
        self.assertEqual(result["machine_error_code"], "UI_COMMAND_INTEGRATION_FAILURE")
        self.assertIn("stdout", result["human_message"])

    def test_timeout_maps_to_recoverable_integration_failure(self) -> None:
        runner = RaisingRunner(subprocess.TimeoutExpired(cmd=("status", "--json"), timeout=5))

        result = execute_command(runner, "status")

        self.assertEqual(result["status"], "integration_failure")
        self.assertEqual(result["machine_error_code"], "UI_COMMAND_TIMEOUT")
        self.assertEqual(result["packet"]["severity"], "recoverable")
        self.assertEqual(result["packet"]["operator_action"], "retry")

    def test_top_level_error_packet_remains_error_even_with_exit_zero(self) -> None:
        runner = RecordingRunner(packet(machine_error_code="provider_network_failed"))

        result = execute_command(runner, "smoke")

        self.assertEqual(result["status"], "command_error")
        self.assertEqual(result["ui_state"], "error")
        self.assertEqual(result["machine_error_code"], "provider_network_failed")

    def test_missing_required_packet_field_is_integration_failure(self) -> None:
        broken = packet()
        broken.pop("next_action")
        runner = RecordingRunner(broken)

        result = execute_command(runner, "mode_get")

        self.assertEqual(result["status"], "integration_failure")
        self.assertIn("missing required fields", result["human_message"])

    def test_changed_files_must_be_list(self) -> None:
        runner = RecordingRunner(packet(changed_files="README.md"))

        result = execute_command(runner, "diagnostics_export")

        self.assertEqual(result["status"], "integration_failure")
        self.assertIn("changed_files", result["human_message"])

    def test_static_first_screen_keeps_launch_client_disabled(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()

        self.assertIn("Запустить клиент", html)
        self.assertIn('class="button primary disabled"', html)
        self.assertIn("disabled", html)
        self.assertNotIn("execute_command", html)


if __name__ == "__main__":
    unittest.main()
