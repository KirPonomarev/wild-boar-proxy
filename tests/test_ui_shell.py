# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from wild_boar_proxy.ui_shell import (
    JsonCommandRunner,
    UiShellError,
    build_runtime_snapshot,
    load_runtime_snapshot,
    main,
    parse_exact_json_object,
    run_mode_control_and_refresh,
    run_sync_and_refresh,
)


def status_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Runtime status summary is available.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "healthy",
        "severity": "info",
        "operator_action": "none",
        "desired_mode": "managed",
        "effective_mode": "managed",
        "endpoint": "127.0.0.1:9999",
        "current_proxy_url": "http://127.0.0.1:10808",
        "pool_summary": {
            "active": 2,
            "reserve": 1,
            "retired": 0,
            "healthy": 2,
            "degraded": 1,
            "down": 0,
        },
        "attestation_summary": {
            "status": "ok",
            "machine_error_code": "OK",
            "attestation_source": "healthcheck --json",
            "observed_at_utc": "2026-05-05T10:00:00+00:00",
        },
        "last_error": "",
    }
    payload.update(overrides)
    return payload


def mode_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Mode values are available.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "desired_mode": "managed",
        "effective_mode": "managed",
    }
    payload.update(overrides)
    return payload


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str):
        self.calls.append(args)
        payload = self.responses[args]
        return type("Result", (), {"payload": payload, "stderr": ""})()


class ParseExactJsonObjectTests(unittest.TestCase):
    def test_accepts_single_json_object(self) -> None:
        payload = parse_exact_json_object('{"status":"ok"}')
        self.assertEqual(payload["status"], "ok")

    def test_rejects_trailing_non_json_text(self) -> None:
        with self.assertRaisesRegex(UiShellError, "exactly one JSON object"):
            parse_exact_json_object('{"status":"ok"} trailing')

    def test_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(UiShellError, "must be an object"):
            parse_exact_json_object('["not","an","object"]')


class JsonCommandRunnerTests(unittest.TestCase):
    @mock.patch("wild_boar_proxy.ui_shell.subprocess.run")
    def test_run_parses_and_validates_command_payload(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["python3", "-m", "wild_boar_proxy", "status", "--json"],
            returncode=0,
            stdout='{"status":"ok","exit_code":0,"human_message":"ready","machine_error_code":"OK","changed_files":[],"next_action":"none"}',
            stderr="",
        )
        runner = JsonCommandRunner(base_command=["python3", "-m", "wild_boar_proxy"])

        result = runner.run("status", "--json")

        self.assertEqual(result.payload["human_message"], "ready")
        run_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.ui_shell.subprocess.run")
    def test_run_rejects_missing_required_command_fields(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["python3", "-m", "wild_boar_proxy", "status", "--json"],
            returncode=0,
            stdout='{"status":"ok","exit_code":0,"human_message":"ready","machine_error_code":"OK","changed_files":[]}',
            stderr="",
        )
        runner = JsonCommandRunner(base_command=["python3", "-m", "wild_boar_proxy"])

        with self.assertRaisesRegex(UiShellError, "next_action"):
            runner.run("status", "--json")


class RuntimeSnapshotTests(unittest.TestCase):
    def test_build_runtime_snapshot_maps_runtime_truth(self) -> None:
        snapshot = build_runtime_snapshot(
            status_payload=status_payload(),
            mode_payload=mode_payload(),
        )

        self.assertEqual(snapshot.overall_state, "ok")
        self.assertEqual(snapshot.exit_code, 0)
        self.assertEqual(snapshot.desired_mode, "managed")
        self.assertEqual(snapshot.current_proxy_url, "http://127.0.0.1:10808")
        self.assertEqual(snapshot.attestation_source, "healthcheck --json")
        self.assertEqual(snapshot.degraded_count, 1)

    def test_build_runtime_snapshot_rejects_missing_required_pool_field(self) -> None:
        broken_status = status_payload(
            pool_summary={
                "reserve": 1,
                "retired": 0,
                "healthy": 2,
                "degraded": 1,
                "down": 0,
            }
        )

        with self.assertRaisesRegex(UiShellError, "active"):
            build_runtime_snapshot(
                status_payload=broken_status,
                mode_payload=mode_payload(),
            )

    def test_build_runtime_snapshot_rejects_malformed_pool_field(self) -> None:
        broken_status = status_payload(
            pool_summary={
                "active": None,
                "reserve": 1,
                "retired": 0,
                "healthy": 2,
                "degraded": 1,
                "down": 0,
            }
        )

        with self.assertRaisesRegex(UiShellError, "pool_summary.active"):
            build_runtime_snapshot(
                status_payload=broken_status,
                mode_payload=mode_payload(),
            )

    def test_build_runtime_snapshot_rejects_missing_required_attestation_summary_field(self) -> None:
        broken_status = status_payload(
            attestation_summary={
                "status": "ok",
                "machine_error_code": "OK",
                "observed_at_utc": "2026-05-05T10:00:00+00:00",
            }
        )

        with self.assertRaisesRegex(UiShellError, "attestation_source"):
            build_runtime_snapshot(
                status_payload=broken_status,
                mode_payload=mode_payload(),
            )

    def test_load_runtime_snapshot_rejects_mode_mismatch(self) -> None:
        runner = FakeRunner(
            {
                ("status", "--json"): status_payload(effective_mode="managed"),
                ("mode", "get", "--json"): mode_payload(effective_mode="stable"),
            }
        )

        with self.assertRaisesRegex(UiShellError, "effective mode"):
            load_runtime_snapshot(runner)


class ModeControlTests(unittest.TestCase):
    def test_run_mode_control_and_refresh_uses_command_then_truth_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("mode", "set", "stable", "--json"): mode_payload(
                    human_message="Desired mode set to stable.",
                    desired_mode="stable",
                    effective_mode="managed",
                ),
                ("status", "--json"): status_payload(
                    desired_mode="stable",
                    effective_mode="managed",
                ),
                ("mode", "get", "--json"): mode_payload(
                    desired_mode="stable",
                    effective_mode="managed",
                ),
            }
        )

        action_payload, snapshot = run_mode_control_and_refresh(
            runner, ("mode", "set", "stable", "--json")
        )

        self.assertEqual(action_payload["human_message"], "Desired mode set to stable.")
        self.assertEqual(snapshot.desired_mode, "stable")
        self.assertEqual(
            runner.calls,
            [
                ("mode", "set", "stable", "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
            ],
        )

    def test_run_sync_and_refresh_includes_accounts_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("sync", "--json"): mode_payload(human_message="Managed sync completed."),
                ("status", "--json"): status_payload(),
                ("accounts", "list", "--json"): status_payload(
                    human_message="Accounts listed."
                ),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        action_payload, snapshot = run_sync_and_refresh(runner)

        self.assertEqual(action_payload["human_message"], "Managed sync completed.")
        self.assertEqual(snapshot.effective_mode, "managed")
        self.assertEqual(
            runner.calls,
            [
                ("sync", "--json"),
                ("status", "--json"),
                ("accounts", "list", "--json"),
                ("mode", "get", "--json"),
            ],
        )


class MainTests(unittest.TestCase):
    @mock.patch("wild_boar_proxy.ui_shell.MinimalCompanionShell")
    @mock.patch("wild_boar_proxy.ui_shell.Tk")
    def test_main_bootstraps_shell(self, tk_mock: mock.Mock, shell_mock: mock.Mock) -> None:
        root = tk_mock.return_value

        result = main()

        self.assertEqual(result, 0)
        tk_mock.assert_called_once_with()
        shell_mock.assert_called_once()
        self.assertIsInstance(shell_mock.call_args.args[1], JsonCommandRunner)
        root.mainloop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
