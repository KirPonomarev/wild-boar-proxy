# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from wild_boar_proxy.ui_shell import (
    AccountPoolSnapshot,
    JsonCommandRunner,
    MinimalCompanionShell,
    UiShellError,
    build_account_pool_snapshot,
    build_runtime_snapshot,
    load_account_pool_snapshot,
    load_runtime_snapshot,
    main,
    parse_exact_json_object,
    run_account_validate_and_refresh,
    run_mode_control_and_refresh,
    run_sync_and_refresh,
)


def command_payload(**overrides: object) -> dict[str, object]:
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


def status_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Runtime status summary is available.",
        liveness="healthy",
        severity="info",
        operator_action="none",
        desired_mode="managed",
        effective_mode="managed",
        endpoint="127.0.0.1:9999",
        current_proxy_url="http://127.0.0.1:10808",
        pool_summary={
            "active": 2,
            "reserve": 1,
            "retired": 0,
            "healthy": 2,
            "degraded": 1,
            "down": 0,
        },
        attestation_summary={
            "status": "ok",
            "machine_error_code": "OK",
            "attestation_source": "healthcheck --json",
            "observed_at_utc": "2026-05-05T10:00:00+00:00",
        },
        last_error="",
    )
    payload.update(overrides)
    return payload


def mode_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Mode values are available.",
        desired_mode="managed",
        effective_mode="managed",
    )
    payload.update(overrides)
    return payload


def accounts_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Account registry snapshot is available.",
        accounts=[
            {
                "id": "backend-a",
                "label": "Backend A",
                "pool": "active",
                "manual_hold": False,
                "status": "healthy",
                "fail_count": 0,
                "success_count": 3,
                "last_success": "2026-05-05T10:00:00+00:00",
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
            {
                "id": "backend-b",
                "label": "Backend B",
                "pool": "reserve",
                "manual_hold": False,
                "status": "healthy",
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
        ],
        registry_identity={
            "status": "clear",
            "machine_error_code": "OK",
            "next_action": "none",
        },
        pool_policy={"active_min": 1, "active_target": 2, "reserve_target": 0},
        stable_default_backend_id="backend-a",
    )
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


class AccountPoolSnapshotTests(unittest.TestCase):
    def test_build_account_pool_snapshot_maps_account_truth(self) -> None:
        snapshot = build_account_pool_snapshot(accounts_payload())

        self.assertIsInstance(snapshot, AccountPoolSnapshot)
        self.assertEqual(snapshot.registry_identity_status, "clear")
        self.assertEqual(snapshot.active_count, 1)
        self.assertEqual(snapshot.reserve_count, 1)
        self.assertEqual(snapshot.capacity_target, 20)
        self.assertEqual(snapshot.accounts[0].backend_id, "backend-a")

    def test_build_account_pool_snapshot_rejects_missing_accounts_field(self) -> None:
        broken_payload = accounts_payload()
        del broken_payload["accounts"]

        with self.assertRaisesRegex(UiShellError, "accounts"):
            build_account_pool_snapshot(broken_payload)

    def test_build_account_pool_snapshot_rejects_missing_account_row_field(self) -> None:
        broken_payload = accounts_payload(
            accounts=[
                {
                    "id": "backend-a",
                    "label": "Backend A",
                    "pool": "active",
                    "manual_hold": False,
                    "status": "healthy",
                    "fail_count": 0,
                    "success_count": 3,
                    "last_success": "2026-05-05T10:00:00+00:00",
                    "last_error": "",
                    "cooldown_until": None,
                }
            ]
        )

        with self.assertRaisesRegex(UiShellError, "notes"):
            build_account_pool_snapshot(broken_payload)

    def test_build_account_pool_snapshot_rejects_missing_registry_identity_field(self) -> None:
        broken_payload = accounts_payload(
            registry_identity={
                "status": "clear",
                "machine_error_code": "OK",
            }
        )

        with self.assertRaisesRegex(UiShellError, "next_action"):
            build_account_pool_snapshot(broken_payload)

    def test_load_account_pool_snapshot_reads_accounts_list_only(self) -> None:
        runner = FakeRunner({("accounts", "list", "--json"): accounts_payload()})

        snapshot = load_account_pool_snapshot(runner)

        self.assertEqual(snapshot.accounts[0].label, "Backend A")
        self.assertEqual(runner.calls, [("accounts", "list", "--json")])


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
                ("sync", "--json"): command_payload(human_message="Managed sync completed."),
                ("status", "--json"): status_payload(),
                ("accounts", "list", "--json"): accounts_payload(),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_sync_and_refresh(runner)

        self.assertEqual(action_payload["human_message"], "Managed sync completed.")
        self.assertEqual(runtime_snapshot.effective_mode, "managed")
        self.assertEqual(account_snapshot.active_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("sync", "--json"),
                ("status", "--json"),
                ("accounts", "list", "--json"),
                ("mode", "get", "--json"),
            ],
        )


class AccountCheckTests(unittest.TestCase):
    def test_run_account_validate_and_refresh_uses_validate_then_accounts_list(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "validate", "backend-a", "--json"): command_payload(
                    human_message="Account validated."
                ),
                ("accounts", "list", "--json"): accounts_payload(),
            }
        )

        action_payload, snapshot = run_account_validate_and_refresh(runner, "backend-a")

        self.assertEqual(action_payload["human_message"], "Account validated.")
        self.assertEqual(snapshot.registry_identity_status, "clear")
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "validate", "backend-a", "--json"),
                ("accounts", "list", "--json"),
            ],
        )

    def test_recheck_alias_uses_same_validate_command_shape(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "validate", "backend-a", "--json"): command_payload(
                    human_message="Account validated."
                ),
                ("accounts", "list", "--json"): accounts_payload(),
            }
        )

        _action_payload, _snapshot = run_account_validate_and_refresh(runner, "backend-a")

        self.assertNotIn(("status", "--json"), runner.calls)
        self.assertEqual(runner.calls[0], ("accounts", "validate", "backend-a", "--json"))


class UiDispatchTests(unittest.TestCase):
    def test_run_recheck_action_delegates_to_account_check_alias(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_check_action = mock.Mock()

        shell.run_recheck_action()

        shell._run_account_check_action.assert_called_once_with("Recheck")


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
