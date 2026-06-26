# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest import TestCase, mock

from wild_boar_proxy import custom_codex_native_response_matrix as matrix


def _native_packet(
    *,
    request_id: str,
    proven: bool = False,
    assistant_code: str = "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN",
    candidate_map_available: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_native_prompt_submit",
        "status": "ok",
        "machine_error_code": "OK",
        "request_id": request_id,
        "prompt_submitted": True,
        "native_prompt_turn_accepted": True,
        "assistant_turn_activity_observed": True,
        "assistant_turn_completed_observed": True,
        "assistant_turn_machine_error_code": "OK" if proven else assistant_code,
        "native_free_text_observer_machine_error_code": (
            "OK" if proven else "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
        ),
        "custom_response_exact_token_observed": proven,
        "custom_response_bound_to_request": proven,
        "custom_response_candidate_map_available": candidate_map_available,
        "custom_response_candidate_map_candidate_count": 2
        if candidate_map_available
        else 0,
        "custom_response_prompt_echo_candidate_count": 1
        if candidate_map_available
        else 0,
        "custom_response_prompt_suffix_echo_candidate_count": 1
        if candidate_map_available
        else 0,
        "custom_response_exact_token_candidate_count": 1 if proven else 0,
        "custom_response_like_candidate_count": 1 if proven else 0,
        "response_surface_candidate_count": 3,
        "native_codex_subagent_used_as_dip": False,
        "custom_codex_ui_visibility_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_dom_exposed": False,
        "raw_prompt_recorded": False,
        "text_value_captured": False,
        "native_ui_observer_packet_file_written": True,
        "native_ui_observer_packet_file_path_recorded": False,
        "native_ui_observer_packet_proven": proven,
        "exit_code": 0 if proven else 1,
    }


class CustomCodexNativeResponseMatrixTests(TestCase):
    def test_case_expected_text_preserves_handoff_digest_sized_prefix(self) -> None:
        handoff_digest = "c" * 64
        request_id = "ui-matrix-1-exact"
        expected_text = matrix._case_expected_text(
            expected_prefix=f"WBP_UI_VISIBLE_{handoff_digest}",
            request_id=request_id,
        )

        self.assertIn(handoff_digest, expected_text)
        self.assertIn(request_id, expected_text)

    def test_matrix_writes_file_backed_summary_without_raw_prompt_or_expected_text(self) -> None:
        variants = [
            matrix.NativeResponsePromptVariant(
                name="one",
                template="Reply exactly:\n{expected_text}",
            ),
            matrix.NativeResponsePromptVariant(
                name="two",
                template="Only this:\n{expected_text}",
            ),
        ]
        prompts: list[str] = []
        expected_texts: list[str] = []

        def fake_runner(**kwargs: object) -> dict[str, object]:
            prompts.append(str(kwargs["prompt_text"]))
            expected_texts.append(str(kwargs["expected_text"]))
            return _native_packet(request_id=str(kwargs["request_id"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_response_matrix.run_native_ui_observer_proof_command",
                side_effect=fake_runner,
            ):
                packet = matrix.run_native_response_matrix_command(
                    paths=paths,
                    proof_dir=str(proof_dir),
                    matrix_id="matrix-1",
                    request_prefix="req",
                    variants=variants,
                )

            written = proof_dir / matrix.NATIVE_RESPONSE_MATRIX_PACKET_FILE_NAME
            self.assertTrue(written.exists())
            persisted = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(persisted, packet)
            self.assertEqual(packet["case_count"], 2)
            self.assertFalse(packet["native_response_matrix_proven"])
            self.assertEqual(packet["exit_code"], 1)
            self.assertFalse(packet["product_ready"])
            self.assertFalse(packet["custom_codex_ui_visibility_proven"])
            self.assertTrue(all(case["packet_file_written"] for case in packet["cases"]))
            self.assertFalse(any(case["packet_file_path_recorded"] for case in packet["cases"]))
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            for prompt in prompts:
                self.assertNotIn(prompt, serialized)
            for expected_text in expected_texts:
                self.assertNotIn(expected_text, serialized)
            self.assertNotIn("Reply exactly", serialized)
            self.assertNotIn("Only this", serialized)
            self.assertFalse(packet["raw_prompt_recorded"])
            self.assertFalse(packet["raw_dom_exposed"])

    def test_matrix_turns_green_only_when_native_observer_packet_is_proven(self) -> None:
        variants = [
            matrix.NativeResponsePromptVariant(name="bad", template="{expected_text}"),
            matrix.NativeResponsePromptVariant(name="good", template="{expected_text}"),
        ]

        def fake_runner(**kwargs: object) -> dict[str, object]:
            request_id = str(kwargs["request_id"])
            return _native_packet(request_id=request_id, proven=request_id.endswith("-good"))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_response_matrix.run_native_ui_observer_proof_command",
                side_effect=fake_runner,
            ):
                packet = matrix.run_native_response_matrix_command(
                    paths=SimpleNamespace(managed_dir=root / "managed"),
                    proof_dir=str(root / "proof"),
                    matrix_id="matrix-2",
                    request_prefix="req",
                    variants=variants,
                    active_project_root={
                        "active_project_root_required": True,
                        "active_project_root_available": True,
                        "active_project_root_source": "server_runtime_env",
                        "active_project_root_status": "ok",
                        "active_project_root_path_recorded": False,
                        "active_project_root_sha256": "7" * 64,
                        "active_project_root_is_wbp_repo": False,
                        "active_project_root_git_available": True,
                        "active_project_root_fallback_used": False,
                        "active_project_root_legacy_target_repo_alias_used": False,
                    },
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["execution_mode"], "chatgpt_only")
        self.assertEqual(packet["selected_mode"], "chatgpt_only")
        self.assertEqual(packet["orchestrator"], "custom_codex_chatgpt")
        self.assertEqual(packet["executor"], "custom_codex_chatgpt")
        self.assertTrue(packet["runtime_dispatch_mode_truth_recorded"])
        self.assertTrue(packet["dispatch_mode_truth_proven"])
        self.assertTrue(packet["chatgpt_only_mode_proven"])
        self.assertTrue(packet["gpt_mode_proven"])
        self.assertFalse(packet["api_only_mode_proven"])
        self.assertFalse(packet["gpt_api_mode_proven"])
        self.assertTrue(packet["chatgpt_lane_selected"])
        self.assertFalse(packet["api_route_selected"])
        self.assertTrue(packet["chatgpt_lane_called"])
        self.assertFalse(packet["api_route_called"])
        self.assertTrue(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertEqual(packet["active_project_root_source"], "server_runtime_env")
        self.assertEqual(packet["active_project_root_status"], "ok")
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertEqual(packet["active_project_root_sha256"], "7" * 64)
        self.assertFalse(packet["active_project_root_is_wbp_repo"])
        self.assertTrue(packet["active_project_root_git_available"])
        self.assertFalse(packet["active_project_root_fallback_used"])
        self.assertFalse(packet["active_project_root_legacy_target_repo_alias_used"])
        self.assertFalse(packet["wrapper_substitution_used"])
        self.assertTrue(packet["native_response_matrix_proven"])
        self.assertEqual(packet["positive_case_count"], 1)
        self.assertEqual(packet["exit_code"], 0)
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_candidate_map_and_completed_turn_do_not_greenwash_matrix(self) -> None:
        variants = [
            matrix.NativeResponsePromptVariant(name="map", template="{expected_text}"),
        ]

        def fake_runner(**kwargs: object) -> dict[str, object]:
            return _native_packet(
                request_id=str(kwargs["request_id"]),
                candidate_map_available=True,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_response_matrix.run_native_ui_observer_proof_command",
                side_effect=fake_runner,
            ):
                packet = matrix.run_native_response_matrix_command(
                    paths=SimpleNamespace(managed_dir=root / "managed"),
                    proof_dir=str(root / "proof"),
                    matrix_id="matrix-3",
                    request_prefix="req",
                    variants=variants,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_RESPONSE_MATRIX_COMPLETED_WITHOUT_EXACT_TOKEN",
        )
        self.assertFalse(packet["native_response_matrix_proven"])
        self.assertEqual(packet["positive_case_count"], 0)
        self.assertEqual(packet["exit_code"], 1)
        self.assertTrue(packet["cases"][0]["custom_response_candidate_map_available"])
        self.assertEqual(packet["cases"][0]["custom_response_candidate_map_candidate_count"], 2)
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["product_ready"])
