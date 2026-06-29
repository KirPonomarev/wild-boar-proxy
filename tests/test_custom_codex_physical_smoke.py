# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import custom_codex_physical_smoke as smoke


def _router_proof_packet(expected: str) -> dict[str, object]:
    return {
        "packet_kind": "wbp_api_agent_auto_router",
        "status": "ok",
        "machine_error_code": "OK",
        "auto_router_proven": True,
        "direct_reply_proven": True,
        "api_route_selected": True,
        "direct_reply_selected": True,
        "output_text": expected,
        "exact_plain_reply_matched": True,
        "output_passthrough_required": True,
        "repo_bridge_evidence_response_proven": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "tools_wbp_dip_invoked": False,
        "dip_run_invoked": False,
        "codex_exec_invoked": False,
        "native_codex_subagent_used_as_dip": False,
        "secret_value_exposed": False,
    }


def _router_fail_closed_packet(machine_error_code: str) -> dict[str, object]:
    return {
        "packet_kind": "wbp_api_agent_auto_router",
        "status": "error",
        "machine_error_code": machine_error_code,
        "auto_router_proven": False,
        "auto_router_fail_closed": True,
        "direct_reply_proven": False,
        "api_route_selected": False,
        "direct_reply_selected": False,
        "output_text": "",
        "fallback_used": False,
        "local_imitation_used": False,
        "tools_wbp_dip_invoked": False,
        "dip_run_invoked": False,
        "codex_exec_invoked": False,
        "native_codex_subagent_used_as_dip": False,
        "secret_value_exposed": False,
        "blocking_reasons": ["unknown_addressed_alias"],
    }


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

    def test_router_proof_requirement_blocks_visible_self_claim_without_proof(self) -> None:
        expected = "WBP_PHYSICAL_ROUTER_PROOF_OK"
        prompt = (
            "Codex: через shell вызови router-hook auto-route-output для DIP "
            f"и ответь ровно {expected}"
        )
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
                mode="native",
                evidence_dir=Path(temp_dir),
                cdp_url="http://127.0.0.1:9223",
                owner_proof={"status": "ok", "machine_error_code": "OK"},
                router_proof_file=Path(temp_dir) / "missing-router-proof.json",
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_PHYSICAL_ROUTER_PROOF_FILE_MISSING",
        )
        self.assertTrue(packet["false_green_blocked"])
        self.assertFalse(packet["custom_response_bound_to_request"])
        self.assertIn("router_proof_file_missing", packet["blocking_reasons"])
        self.assertFalse(packet["router_proof"]["router_proof_proven"])

    def test_router_proof_requirement_accepts_visible_output_with_matching_packet(self) -> None:
        expected = "WBP_PHYSICAL_ROUTER_PROOF_OK"
        prompt = (
            "Codex: через shell вызови router-hook auto-route-output для DIP "
            f"и ответь ровно {expected}"
        )
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
            proof_file = Path(temp_dir) / "router-proof.json"
            proof_file.write_text(
                json.dumps(_router_proof_packet(expected)),
                encoding="utf-8",
            )
            packet = smoke.build_packet(
                raw=raw,
                prompt=prompt,
                expected_text=expected,
                mode="native",
                evidence_dir=Path(temp_dir),
                cdp_url="http://127.0.0.1:9223",
                owner_proof={"status": "ok", "machine_error_code": "OK"},
                router_proof_file=proof_file,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["custom_response_bound_to_request"])
        self.assertTrue(packet["router_proof"]["router_proof_proven"])
        self.assertEqual(packet["router_proof"]["router_proof_machine_error_code"], "OK")
        self.assertTrue(packet["router_proof"]["router_proof_evidence_copy_recorded"])
        self.assertEqual(packet["router_proof"]["router_proof_evidence_copy"], "router-proof.packet.json")

    def test_router_proof_requirement_accepts_fail_closed_unknown_alias_packet(self) -> None:
        expected = "WBP_API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS"
        prompt = "DIPP: ответь ровно SHOULD_NOT_ROUTE"
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
            proof_file = Path(temp_dir) / "router-proof.json"
            proof_file.write_text(
                json.dumps(_router_fail_closed_packet(expected)),
                encoding="utf-8",
            )
            packet = smoke.build_packet(
                raw=raw,
                prompt=prompt,
                expected_text=expected,
                mode="fail_closed",
                evidence_dir=Path(temp_dir),
                cdp_url="http://127.0.0.1:9223",
                owner_proof={"status": "ok", "machine_error_code": "OK"},
                router_proof_file=proof_file,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["custom_response_bound_to_request"])
        self.assertTrue(packet["router_proof"]["router_proof_proven"])
        self.assertEqual(packet["router_proof"]["router_proof_machine_error_code"], "OK")
        self.assertTrue(packet["router_proof"]["router_proof_evidence_copy_recorded"])
        self.assertEqual(packet["router_proof"]["router_proof_evidence_copy"], "router-proof.packet.json")


if __name__ == "__main__":
    unittest.main()
