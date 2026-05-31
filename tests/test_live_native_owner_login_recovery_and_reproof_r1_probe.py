# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

from tools import live_native_owner_login_recovery_and_reproof_r1_probe as probe


def _command(machine_error_code: str, login_status: str = "", **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"machine_error_code": machine_error_code}
    if login_status:
        payload["login_result"] = {
            "status": login_status,
            "auth_materialized": login_status in {"auth_materialized", "completed"},
            "auth_ref_present": login_status in {"auth_materialized", "completed"},
        }
    payload.update(extra)
    return {
        "exit_code": 0 if machine_error_code in {"OK", "LOGIN_COMPLETE_NOT_ATTEMPTED"} else 1,
        "stdout_json": payload,
        "stderr_redacted_len": 0,
        "captured_at_utc": "2026-05-29T00:00:00Z",
        "args": [],
    }


class LiveNativeOwnerLoginRecoveryAndReproofProbeTests(unittest.TestCase):
    def test_build_packets_classifies_owner_action_pending_without_runtime_recovery(self) -> None:
        def fake_run_json_command(_repo_root: Path, args: list[str]) -> dict[str, object]:
            if args == ["healthcheck", "--json"]:
                return _command("AUTH_UNAVAILABLE")
            if args == ["status", "--json"]:
                return _command("AUTH_UNAVAILABLE")
            if args == [
                "accounts",
                "login",
                "start",
                "--provider",
                "codex",
                "--mode",
                "device",
                "--json",
            ]:
                return _command(
                    "OK",
                    "waiting_for_user",
                    login_session_id="codex-test-session",
                    session_id="codex-test-session",
                    device_url="https://auth.openai.com/codex/device",
                    device_code="WBP-1234",
                    device_code_present=True,
                )
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
                "cancel",
                "--session",
                "codex-test-session",
                "--json",
            ]:
                return _command("OK", "cancelled")
            raise AssertionError(args)

        with (
            mock.patch.object(probe, "_run_json_command", side_effect=fake_run_json_command),
            mock.patch.object(
                probe,
                "_direct_native_probe",
                return_value={"status": "http_error", "http_status": 503, "body_preview": ""},
            ),
        ):
            packets = probe.build_packets(repo_root=Path("/Volumes/Work/wild-boar-proxy"))

        session_packet = packets["native_owner_login_session_packet.json"]
        owner_packet = packets["native_owner_dependency_packet.json"]
        non_claims = packets["native_auth_non_claims_packet.json"]
        false_green = packets["false_green_boundary_packet.json"]

        self.assertTrue(session_packet["session_id_present"])
        self.assertTrue(session_packet["device_code_present"])
        self.assertEqual(owner_packet["classification"], "owner_action_pending")
        self.assertTrue(owner_packet["owner_action_required"])
        self.assertFalse(non_claims["login_started_counts_as_native_recovery"])
        self.assertTrue(false_green["login_started_without_auth_materialized"])


if __name__ == "__main__":
    unittest.main()
