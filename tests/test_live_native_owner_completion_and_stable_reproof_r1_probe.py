# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from unittest import mock
import unittest

from tools import live_native_owner_completion_and_stable_reproof_r1_probe as probe


def _command(machine_error_code: str, login_status: str = "", **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"machine_error_code": machine_error_code}
    if login_status:
        login_result = {
            "status": login_status,
            "auth_materialized": login_status in {"auth_materialized", "completed"},
            "auth_ref_present": login_status in {"auth_materialized", "completed"},
        }
        for key in ("failure_reason", "handoff_observed", "session_process_alive"):
            if key in extra:
                login_result[key] = extra.pop(key)
        payload["login_result"] = login_result
    payload.update(extra)
    return {
        "exit_code": 0 if machine_error_code in {"OK", "LOGIN_COMPLETE_NOT_ATTEMPTED"} else 1,
        "stdout_json": payload,
        "stderr_redacted_len": 0,
        "captured_at_utc": "2026-05-29T00:00:00Z",
        "args": [],
    }


class LiveNativeOwnerCompletionAndStableReproofProbeTests(unittest.TestCase):
    def test_build_packets_classifies_owner_action_pending(self) -> None:
        def fake_run_json_command(_repo_root: Path, args: list[str]) -> dict[str, object]:
            if args == ["healthcheck", "--json"]:
                return _command(
                    "AUTH_UNAVAILABLE",
                    auth_pool_hygiene={"selected_backend_runtime_loaded_count": 0},
                )
            if args == ["status", "--json"]:
                return _command("AUTH_UNAVAILABLE")
            if args == [
                "accounts",
                "login",
                "status",
                "--session",
                "codex-test-session",
                "--json",
            ]:
                return _command("OK", "waiting_for_user")
            if args == [
                "accounts",
                "login",
                "complete",
                "--session",
                "codex-test-session",
                "--json",
            ]:
                return _command("LOGIN_AUTH_NOT_MATERIALIZED", "waiting_for_user")
            raise AssertionError(args)

        with (
            mock.patch.object(probe, "_run_json_command", side_effect=fake_run_json_command),
            mock.patch.object(
                probe,
                "_direct_native_probe",
                return_value={"status": "http_error", "http_status": 503, "body_preview": ""},
            ),
        ):
            packets = probe.build_packets(
                repo_root=Path("/Volumes/Work/wild-boar-proxy"),
                session_id="codex-test-session",
            )

        completion = packets["native_owner_completion_packet.json"]
        dependency = packets["native_owner_dependency_packet.json"]
        runtime_load = packets["native_runtime_load_packet.json"]

        self.assertFalse(completion["owner_completed"])
        self.assertEqual(dependency["classification"], "owner_action_pending")
        self.assertTrue(dependency["owner_action_required"])
        self.assertFalse(runtime_load["runtime_loaded"])
        self.assertEqual(
            dependency["complete_machine_error_code"], "LOGIN_AUTH_NOT_MATERIALIZED"
        )

    def test_build_packets_classifies_auth_materialized_but_runtime_not_loaded(self) -> None:
        def fake_run_json_command(_repo_root: Path, args: list[str]) -> dict[str, object]:
            if args == ["healthcheck", "--json"]:
                return _command(
                    "AUTH_UNAVAILABLE",
                    auth_pool_hygiene={"selected_backend_runtime_loaded_count": 0},
                )
            if args == ["status", "--json"]:
                return _command("AUTH_UNAVAILABLE")
            if args == [
                "accounts",
                "login",
                "status",
                "--session",
                "codex-test-session",
                "--json",
            ]:
                return _command("OK", "auth_materialized")
            if args == [
                "accounts",
                "login",
                "complete",
                "--session",
                "codex-test-session",
                "--json",
            ]:
                return _command("LOGIN_AUTH_NOT_MATERIALIZED", "auth_materialized")
            raise AssertionError(args)

        with (
            mock.patch.object(probe, "_run_json_command", side_effect=fake_run_json_command),
            mock.patch.object(
                probe,
                "_direct_native_probe",
                return_value={"status": "http_error", "http_status": 503, "body_preview": ""},
            ),
        ):
            packets = probe.build_packets(
                repo_root=Path("/Volumes/Work/wild-boar-proxy"),
                session_id="codex-test-session",
            )

        materialization = packets["native_auth_materialization_packet.json"]
        dependency = packets["native_owner_dependency_packet.json"]

        self.assertTrue(materialization["auth_materialized"])
        self.assertEqual(dependency["classification"], "auth_materialized_but_runtime_not_loaded")
        self.assertEqual(dependency["runtime_loaded_count"], 0)

    def test_post_login_materialization_gap_packet_detects_existing_auth_without_local_update(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            login_sessions_dir = managed_dir / "login-sessions"
            auth_dir = root / "auth-dir"
            logs_dir = auth_dir / "logs"
            login_sessions_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            session_path = login_sessions_dir / "codex-test-session.json"
            auth_path = auth_dir / "codex-21c5ac82-kir.test.gpt26@gmail.com-team.json"
            session_path.write_text(
                json.dumps(
                    {
                        "login_session_id": "codex-test-session",
                        "provider": "codex",
                        "mode": "device",
                        "pid": 0,
                        "created_at": "2026-05-29T02:44:09+00:00",
                        "expires_at": "2026-05-29T02:49:09+00:00",
                        "state": "waiting_for_user",
                        "device_url": "https://auth.openai.com/codex/device",
                        "device_code": "TEST-12345",
                        "device_code_present": True,
                        "auth_materialized": False,
                        "auth_ref": "",
                        "auth_inventory_before": [str(auth_path)],
                    }
                ),
                encoding="utf-8",
            )
            auth_path.write_text(
                json.dumps(
                    {
                        "email": "kir.test.gpt26@gmail.com",
                        "account_id": "acct-1",
                        "disabled": False,
                        "expired": "2026-06-07T12:13:49+03:00",
                        "last_refresh": "2026-05-28T12:13:49+03:00",
                    }
                ),
                encoding="utf-8",
            )
            created_epoch = 1748486649
            os.utime(auth_path, (created_epoch - 60, created_epoch - 60))
            (logs_dir / "main.log").write_text(
                "Provided authentication token is expired.\nrefresh_token_reused\n",
                encoding="utf-8",
            )
            paths = probe.runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=root / "stable" / "config.yaml",
                auth_file=profile_dir / "auth.json",
                config_toml=profile_dir / "config.toml",
                runtime_mode_file=profile_dir / "runtime-mode.txt",
                runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
                registry_file=managed_dir / "backend-registry.json",
                state_file=managed_dir / "supervisor-state.json",
                managed_config_file=managed_dir / "managed-config.yaml",
                launcher_script=profile_dir / "codex-custom-launch.sh",
                sync_script=managed_dir / "supervisor-sync.sh",
                accounts_bin=managed_dir / "bin" / "codex-accounts",
                onboard_bin=managed_dir / "bin" / "codex-account-onboard",
                lock_file=managed_dir / "wild-boar-proxy.lock",
                launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
                repair_target_inventory_dir=managed_dir / "stable-repair-target",
                repair_target_reference_file=managed_dir / "approved-repair-target.json",
                target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )
            with (
                mock.patch.object(probe.runtime.RuntimePaths, "from_env", return_value=paths),
                mock.patch.object(
                    probe.runtime,
                    "login_session_auth_inventory_dir",
                    return_value=(auth_dir, {"source": "auth-dir"}),
                ),
                mock.patch.object(
                    probe.runtime,
                    "list_login_auth_inventory_entries",
                    return_value=[auth_path],
                ),
            ):
                packet = probe._build_post_login_materialization_gap_packet(
                    session_id="codex-test-session",
                    owner_email="kir.test.gpt26@gmail.com",
                    session_result={"status": "waiting_for_user", "auth_materialized": False},
                )

        self.assertTrue(packet["refresh_token_reused_observed_in_recent_logs"])
        self.assertTrue(packet["expired_token_observed_in_recent_logs"])
        self.assertEqual(packet["matching_auth_entry_count"], 1)
        self.assertEqual(packet["auth_inventory_added_count"], 0)
        self.assertFalse(packet["session_pid_alive"])
        self.assertEqual(
            packet["classification"], "existing_auth_ref_present_but_unmaterialized"
        )
        self.assertTrue(packet["existing_auth_ref_present_but_unmaterialized_gap_detected"])

    def test_post_login_materialization_gap_packet_detects_dead_handoff_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            login_sessions_dir = managed_dir / "login-sessions"
            auth_dir = root / "auth-dir"
            logs_dir = auth_dir / "logs"
            login_sessions_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            session_path = login_sessions_dir / "codex-test-session.json"
            auth_path = auth_dir / "codex-21c5ac82-kir.test.gpt26@gmail.com-team.json"
            session_path.write_text(
                json.dumps(
                    {
                        "login_session_id": "codex-test-session",
                        "provider": "codex",
                        "mode": "device",
                        "pid": 0,
                        "created_at": "2026-05-29T02:44:09+00:00",
                        "expires_at": "2026-05-29T02:49:09+00:00",
                        "state": "failed",
                        "device_url": "https://auth.openai.com/codex/device",
                        "device_code": "TEST-12345",
                        "device_code_present": True,
                        "failure_reason": "device_handoff_process_exited_before_auth_materialized",
                        "auth_materialized": False,
                        "auth_ref": "",
                        "auth_inventory_before": [str(auth_path)],
                    }
                ),
                encoding="utf-8",
            )
            auth_path.write_text(
                json.dumps({"email": "kir.test.gpt26@gmail.com", "account_id": "acct-1"}),
                encoding="utf-8",
            )
            created_epoch = 1748486649
            os.utime(auth_path, (created_epoch - 60, created_epoch - 60))
            (logs_dir / "main.log").write_text("", encoding="utf-8")
            paths = probe.runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=root / "stable" / "config.yaml",
                auth_file=profile_dir / "auth.json",
                config_toml=profile_dir / "config.toml",
                runtime_mode_file=profile_dir / "runtime-mode.txt",
                runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
                registry_file=managed_dir / "backend-registry.json",
                state_file=managed_dir / "supervisor-state.json",
                managed_config_file=managed_dir / "managed-config.yaml",
                launcher_script=profile_dir / "codex-custom-launch.sh",
                sync_script=managed_dir / "supervisor-sync.sh",
                accounts_bin=managed_dir / "bin" / "codex-accounts",
                onboard_bin=managed_dir / "bin" / "codex-account-onboard",
                lock_file=managed_dir / "wild-boar-proxy.lock",
                launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
                repair_target_inventory_dir=managed_dir / "stable-repair-target",
                repair_target_reference_file=managed_dir / "approved-repair-target.json",
                target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )
            with (
                mock.patch.object(probe.runtime.RuntimePaths, "from_env", return_value=paths),
                mock.patch.object(
                    probe.runtime,
                    "login_session_auth_inventory_dir",
                    return_value=(auth_dir, {"source": "auth-dir"}),
                ),
                mock.patch.object(
                    probe.runtime,
                    "list_login_auth_inventory_entries",
                    return_value=[auth_path],
                ),
            ):
                packet = probe._build_post_login_materialization_gap_packet(
                    session_id="codex-test-session",
                    owner_email="kir.test.gpt26@gmail.com",
                    session_result={
                        "status": "failed",
                        "auth_materialized": False,
                        "failure_reason": "device_handoff_process_exited_before_auth_materialized",
                    },
                )

        self.assertTrue(packet["handoff_observed"])
        self.assertFalse(packet["session_pid_alive"])
        self.assertEqual(
            packet["classification"],
            "device_handoff_process_exited_before_auth_materialized",
        )

    def test_post_login_materialization_gap_packet_detects_live_process_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            login_sessions_dir = managed_dir / "login-sessions"
            auth_dir = root / "auth-dir"
            logs_dir = auth_dir / "logs"
            login_sessions_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            session_path = login_sessions_dir / "codex-test-session.json"
            auth_path = auth_dir / "codex-21c5ac82-kir.test.gpt26@gmail.com-team.json"
            session_path.write_text(
                json.dumps(
                    {
                        "login_session_id": "codex-test-session",
                        "provider": "codex",
                        "mode": "device",
                        "pid": 424242,
                        "created_at": "2026-05-29T02:44:09+00:00",
                        "expires_at": "2026-05-29T02:49:09+00:00",
                        "state": "waiting_for_user",
                        "device_url": "https://auth.openai.com/codex/device",
                        "device_code": "TEST-12345",
                        "device_code_present": True,
                        "auth_materialized": False,
                        "auth_ref": "",
                        "auth_inventory_before": [str(auth_path)],
                    }
                ),
                encoding="utf-8",
            )
            auth_path.write_text(
                json.dumps({"email": "kir.test.gpt26@gmail.com", "account_id": "acct-1"}),
                encoding="utf-8",
            )
            created_epoch = 1748486649
            os.utime(auth_path, (created_epoch - 60, created_epoch - 60))
            (logs_dir / "main.log").write_text("", encoding="utf-8")
            paths = probe.runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=root / "stable" / "config.yaml",
                auth_file=profile_dir / "auth.json",
                config_toml=profile_dir / "config.toml",
                runtime_mode_file=profile_dir / "runtime-mode.txt",
                runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
                registry_file=managed_dir / "backend-registry.json",
                state_file=managed_dir / "supervisor-state.json",
                managed_config_file=managed_dir / "managed-config.yaml",
                launcher_script=profile_dir / "codex-custom-launch.sh",
                sync_script=managed_dir / "supervisor-sync.sh",
                accounts_bin=managed_dir / "bin" / "codex-accounts",
                onboard_bin=managed_dir / "bin" / "codex-account-onboard",
                lock_file=managed_dir / "wild-boar-proxy.lock",
                launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
                repair_target_inventory_dir=managed_dir / "stable-repair-target",
                repair_target_reference_file=managed_dir / "approved-repair-target.json",
                target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )
            with (
                mock.patch.object(probe.runtime.RuntimePaths, "from_env", return_value=paths),
                mock.patch.object(
                    probe.runtime,
                    "login_session_auth_inventory_dir",
                    return_value=(auth_dir, {"source": "auth-dir"}),
                ),
                mock.patch.object(
                    probe.runtime,
                    "list_login_auth_inventory_entries",
                    return_value=[auth_path],
                ),
                mock.patch.object(probe, "_pid_alive", return_value=True),
            ):
                packet = probe._build_post_login_materialization_gap_packet(
                    session_id="codex-test-session",
                    owner_email="kir.test.gpt26@gmail.com",
                    session_result={"status": "waiting_for_user", "auth_materialized": False},
                )

        self.assertTrue(packet["session_pid_alive"])
        self.assertEqual(packet["auth_inventory_added_count"], 0)
        self.assertEqual(
            packet["classification"], "process_alive_but_no_materialization_write"
        )
        self.assertTrue(packet["process_alive_without_materialization_write"])

    def test_build_packets_emits_materialization_repair_and_failure_taxonomy_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            login_sessions_dir = managed_dir / "login-sessions"
            auth_dir = root / "auth-dir"
            logs_dir = auth_dir / "logs"
            login_sessions_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            session_path = login_sessions_dir / "codex-test-session.json"
            auth_path = auth_dir / "codex-21c5ac82-kir.test.gpt26@gmail.com-team.json"
            session_path.write_text(
                json.dumps(
                    {
                        "login_session_id": "codex-test-session",
                        "provider": "codex",
                        "mode": "device",
                        "pid": 0,
                        "created_at": "2026-05-29T02:44:09+00:00",
                        "expires_at": "2026-05-29T02:49:09+00:00",
                        "state": "waiting_for_user",
                        "device_url": "https://auth.openai.com/codex/device",
                        "device_code": "TEST-12345",
                        "device_code_present": True,
                        "auth_materialized": False,
                        "auth_ref": "",
                        "auth_inventory_before": [str(auth_path)],
                    }
                ),
                encoding="utf-8",
            )
            auth_path.write_text(
                json.dumps({"email": "kir.test.gpt26@gmail.com", "account_id": "acct-1"}),
                encoding="utf-8",
            )
            created_epoch = 1748486649
            os.utime(auth_path, (created_epoch - 60, created_epoch - 60))
            (logs_dir / "main.log").write_text("refresh_token_reused\n", encoding="utf-8")
            paths = probe.runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=root / "stable" / "config.yaml",
                auth_file=profile_dir / "auth.json",
                config_toml=profile_dir / "config.toml",
                runtime_mode_file=profile_dir / "runtime-mode.txt",
                runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
                registry_file=managed_dir / "backend-registry.json",
                state_file=managed_dir / "supervisor-state.json",
                managed_config_file=managed_dir / "managed-config.yaml",
                launcher_script=profile_dir / "codex-custom-launch.sh",
                sync_script=managed_dir / "supervisor-sync.sh",
                accounts_bin=managed_dir / "bin" / "codex-accounts",
                onboard_bin=managed_dir / "bin" / "codex-account-onboard",
                lock_file=managed_dir / "wild-boar-proxy.lock",
                launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
                repair_target_inventory_dir=managed_dir / "stable-repair-target",
                repair_target_reference_file=managed_dir / "approved-repair-target.json",
                target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )

            def fake_run_json_command(_repo_root: Path, args: list[str]) -> dict[str, object]:
                if args == ["healthcheck", "--json"]:
                    return _command(
                        "AUTH_UNAVAILABLE",
                        auth_pool_hygiene={"selected_backend_runtime_loaded_count": 0},
                    )
                if args == ["status", "--json"]:
                    return _command("AUTH_UNAVAILABLE")
                if args == [
                    "accounts",
                    "login",
                    "status",
                    "--session",
                    "codex-test-session",
                    "--json",
                ]:
                    return _command("LOGIN_HANDOFF_PROCESS_EXITED", "failed", failure_reason="device_handoff_process_exited_before_auth_materialized")
                if args == [
                    "accounts",
                    "login",
                    "complete",
                    "--session",
                    "codex-test-session",
                    "--json",
                ]:
                    return _command(
                        "LOGIN_HANDOFF_PROCESS_EXITED",
                        "failed",
                        failure_reason="device_handoff_process_exited_before_auth_materialized",
                    )
                raise AssertionError(args)

            with (
                mock.patch.object(probe, "_run_json_command", side_effect=fake_run_json_command),
                mock.patch.object(
                    probe,
                    "_direct_native_probe",
                    return_value={"status": "http_error", "http_status": 503, "body_preview": ""},
                ),
                mock.patch.object(probe.runtime.RuntimePaths, "from_env", return_value=paths),
                mock.patch.object(
                    probe.runtime,
                    "login_session_auth_inventory_dir",
                    return_value=(auth_dir, {"source": "auth-dir"}),
                ),
                mock.patch.object(
                    probe.runtime,
                    "list_login_auth_inventory_entries",
                    return_value=[auth_path],
                ),
            ):
                packets = probe.build_packets(
                    repo_root=Path("/Volumes/Work/wild-boar-proxy"),
                    session_id="codex-test-session",
                    owner_email="kir.test.gpt26@gmail.com",
                )

        repair = packets["native_materialization_repair_packet.json"]
        taxonomy = packets["native_materialization_failure_taxonomy_packet.json"]
        refresh_contract = packets["native_existing_auth_refresh_contract_packet.json"]
        session_bound = packets["native_session_bound_refresh_packet.json"]
        handoff = packets["native_browser_success_handoff_packet.json"]
        transition = packets["native_local_session_transition_packet.json"]
        self.assertEqual(repair["repair_result"], "materialization_not_observed")
        self.assertFalse(repair["repair_effective_for_materialization"])
        self.assertTrue(taxonomy["browser_success_without_local_materialization"])
        self.assertTrue(taxonomy["browser_success_without_local_session_handoff"])
        self.assertTrue(taxonomy["refresh_token_reused_prevents_materialization"])
        self.assertFalse(refresh_contract["existing_auth_refresh_emitted"])
        self.assertFalse(refresh_contract["existing_auth_refresh_adopted"])
        self.assertFalse(session_bound["session_bound_refresh_proven"])
        self.assertEqual(session_bound["classification"], "session_bound_refresh_unproven")
        self.assertEqual(
            handoff["classification"], "handoff_emitted_but_local_session_not_promoted"
        )
        self.assertEqual(
            transition["classification"], "handoff_received_but_session_not_promoted"
        )


if __name__ == "__main__":
    unittest.main()
