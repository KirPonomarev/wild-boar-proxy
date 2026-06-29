# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import custom_codex_physical_smoke as smoke


class CustomCodexPhysicalSmokeTests(unittest.TestCase):
    def test_owner_proof_accepts_single_main_process_with_shared_helper_fd(self) -> None:
        profile_dir = Path("/tmp/wbp-profile")
        user_data_dir = profile_dir / "electron-user-data"
        resolved_user_data_dir = user_data_dir.resolve(strict=False)
        main_command = (
            "/Users/example/Applications/Codex WBP Clean.app/Contents/MacOS/Codex "
            "--remote-debugging-address=127.0.0.1 "
            "--remote-debugging-port=9223 "
            f"--user-data-dir={resolved_user_data_dir}"
        )
        commands = {
            100: main_command,
            200: "/Users/example/.codex/computer-use/SkyComputerUseService",
        }

        with mock.patch.object(
            smoke,
            "_listening_pids_for_port",
            return_value=[100, 200],
        ), mock.patch.object(
            smoke,
            "_process_command",
            side_effect=lambda pid: commands[int(pid)],
        ):
            proof = smoke.prove_cdp_owner(
                cdp_url="http://127.0.0.1:9223",
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
                allow_unbound_cdp=False,
            )

        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["cdp_owner_proven"])
        self.assertEqual(proof["candidate_pid_count"], 2)
        self.assertEqual(proof["owner_candidate_pid_count"], 1)
        self.assertEqual(proof["cdp_owner_pid"], 100)

    def test_packet_does_not_record_screenshot_path_by_default(self) -> None:
        prompt = "DIP: answer exactly WBP_PHYSICAL_PACKET_OK"
        expected = "WBP_PHYSICAL_PACKET_OK"
        raw = {
            "status": "ok",
            "before_text": "",
            "after_text": f"{prompt}\nРаботал на протяжении 1s\n{expected}",
            "run_active": False,
            "prompt_submitted": True,
            "input_text_insert_succeeded": True,
            "insertion_strategy_used": "insertText",
            "elapsed_ms": 1000,
            "screenshot_path": "",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            packet = smoke.build_packet(
                raw=raw,
                prompt=prompt,
                expected_text=expected,
                mode="api",
                evidence_dir=Path(temp_dir),
                cdp_url="http://127.0.0.1:9223",
                owner_proof={"status": "ok", "machine_error_code": "OK"},
            )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["raw_text_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["screenshot_recorded"])
        self.assertEqual(packet["screenshot_path"], "")
        self.assertRegex(str(packet["prompt_sha256"]), r"^[0-9a-f]{64}$")
        self.assertRegex(str(packet["after_text_sha256"]), r"^[0-9a-f]{64}$")
        self.assertNotIn("after_text", packet)
        self.assertNotIn("before_text", packet)


if __name__ == "__main__":
    unittest.main()
