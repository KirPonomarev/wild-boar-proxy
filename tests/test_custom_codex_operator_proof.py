# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import custom_codex_operator_proof as operator
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_admission import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    ROOT,
    ROUTE_ID,
    _paths,
    _write_fake_codex,
    _write_profile,
)


def _hex(char: str) -> str:
    return char * 64


def _admission_packet(
    *,
    run_id: str,
    prompt_digest: str = "",
    run_graph_digest: str = "",
    transcript_digest: str = "",
    **overrides: object,
) -> dict[str, object]:
    extra: dict[str, object] = {
        "packet_kind": "wbp_repeatable_custom_codex_admission",
        "admission_scope": "repeatable_custom_codex_runtime_proof",
        "same_turn_claim_ceiling": (
            "custom_codex_exec_working_flow_only_no_ui_no_native_router_no_product"
        ),
        "runner_launch_surface_kind": "custom_codex_cli_exec",
        "admission_proven": True,
        "same_turn_custom_codex_flow_proven": True,
        "admission_run_id_digest_bound": True,
        "admission_run_id_digest": run_id,
        "admission_run_id_recorded": False,
        "run_id_bound": True,
        "run_graph_digest": run_graph_digest or _hex("b"),
        "hook_ledger_fresh": True,
        "prompt_digest_bound": True,
        "codex_exec_prompt_digest": prompt_digest or _hex("a"),
        "codex_exec_command_sha256": _hex("d"),
        "external_models_dir_source": "env.WBP_EXTERNAL_MODELS_DIR",
        "runtime_context_digest_bound": True,
        "api_lane_called": True,
        "external_live_provider_response_proven": True,
        "codex_exec_transcript_bound": True,
        "same_codex_exec_jsonl_bound": True,
        "codex_exec_transcript_sha256": transcript_digest or _hex("c"),
        "codex_exec_assistant_continuation_proven": True,
        "proof_seal_verified": True,
        "source_seal_runtime_context_digest_bound": True,
        "source_seal_hook_ledger_digest_bound": True,
        "source_seal_profile_hook_config_digest_bound": True,
        "working_flow_seal_input_hashes_bound": True,
        "same_turn_binding_failures": [],
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_expected_text_recorded": False,
        "expected_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    extra.update(overrides)
    return packets.build_command_packet(
        ok=True,
        human_message="admission ok",
        machine_error_code="OK",
        liveness="network_dependent",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="mutate",
        extra=extra,
    )


def _write_packet(path: Path, packet: dict[str, object]) -> Path:
    path.write_text(json.dumps(packet, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _operator_packet(
    root: Path,
    first: dict[str, object],
    second: dict[str, object],
) -> dict[str, object]:
    first_file = _write_packet(root / "run-1.packet.json", first)
    second_file = _write_packet(root / "run-2.packet.json", second)
    return operator.build_repeatable_operator_packet(
        admission_packets=[first, second],
        admission_packet_files=[first_file, second_file],
        changed_files=[str(first_file), str(second_file)],
        secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
    )


def _assert_no_raw_sensitive_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["product_ready"])


class CustomCodexOperatorProofTests(unittest.TestCase):
    def test_build_positive_repeatable_operator_packet_without_product_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _operator_packet(
                root,
                _admission_packet(run_id=_hex("1"), run_graph_digest=_hex("2")),
                _admission_packet(run_id=_hex("3"), run_graph_digest=_hex("4")),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["repeatable_same_turn_operator_proof_proven"])
        self.assertTrue(packet["same_turn_custom_codex_flow_proven"])
        self.assertEqual(packet["operator_run_count"], 2)
        self.assertTrue(packet["admission_run_ids_distinct"])
        self.assertFalse(packet["admission_run_ids_recorded"])
        self.assertTrue(packet["prompt_digest_consistent"])
        self.assertTrue(packet["operator_invariant_digest_consistent"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_reused_admission_run_id_blocks_operator_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _operator_packet(
                root,
                _admission_packet(run_id=_hex("1"), run_graph_digest=_hex("2")),
                _admission_packet(run_id=_hex("1"), run_graph_digest=_hex("4")),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], operator.OPERATOR_RUN_ID_REUSED)
        self.assertFalse(packet["repeatable_same_turn_operator_proof_proven"])
        self.assertTrue(packet["admission_run_id_reused"])
        self.assertIn("admission_run_id_reused", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])

    def test_missing_admission_run_id_blocks_operator_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _operator_packet(
                root,
                _admission_packet(run_id=_hex("1"), run_graph_digest=_hex("2")),
                _admission_packet(
                    run_id="",
                    run_graph_digest=_hex("4"),
                    admission_run_id_digest_bound=False,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            operator.OPERATOR_DIGEST_BINDING_FAILED,
        )
        self.assertFalse(packet["repeatable_same_turn_operator_proof_proven"])
        self.assertIn("run_2_admission_run_id_digest_missing", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])

    def test_stable_invariant_digest_mismatch_blocks_operator_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _operator_packet(
                root,
                _admission_packet(run_id=_hex("1"), run_graph_digest=_hex("2")),
                _admission_packet(
                    run_id=_hex("3"),
                    run_graph_digest=_hex("4"),
                    codex_exec_command_sha256=_hex("e"),
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            operator.OPERATOR_DIGEST_BINDING_FAILED,
        )
        self.assertFalse(packet["repeatable_same_turn_operator_proof_proven"])
        self.assertFalse(packet["operator_invariant_digest_consistent"])
        self.assertIn(
            "operator_invariant_digest_not_repeatable",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])

    def test_fail_closed_operator_negative_matrix(self) -> None:
        cases = [
            (
                {"hook_ledger_fresh": False},
                operator.OPERATOR_DIGEST_BINDING_FAILED,
                "run_2_hook_ledger_fresh_not_true",
            ),
            (
                {"runtime_context_digest_bound": False},
                operator.OPERATOR_DIGEST_BINDING_FAILED,
                "run_2_runtime_context_digest_bound_not_true",
            ),
            (
                {"api_lane_called": False},
                operator.OPERATOR_DIGEST_BINDING_FAILED,
                "run_2_api_lane_called_not_true",
            ),
            (
                {"local_imitation_used": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_local_imitation_used_not_false",
            ),
            (
                {"tool_call_arguments_recorded": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_tool_call_arguments_recorded_not_false",
            ),
            (
                {"selected_api_route_id_recorded": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_selected_api_route_id_recorded_not_false",
            ),
            (
                {"expected_text_recorded": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_expected_text_recorded_not_false",
            ),
            (
                {"product_ready": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_product_ready_not_false",
            ),
            (
                {"custom_codex_ui_visibility_proven": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_custom_codex_ui_visibility_proven_not_false",
            ),
            (
                {"native_free_chat_router_proven": True},
                operator.OPERATOR_FALSE_CLAIM,
                "run_2_native_free_chat_router_proven_not_false",
            ),
        ]
        for overrides, machine_error_code, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                packet = _operator_packet(
                    root,
                    _admission_packet(run_id=_hex("1"), run_graph_digest=_hex("2")),
                    _admission_packet(
                        run_id=_hex("3"),
                        run_graph_digest=_hex("4"),
                        **overrides,
                    ),
                )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], machine_error_code)
            self.assertFalse(packet["repeatable_same_turn_operator_proof_proven"])
            self.assertIn(reason, packet["blocking_reasons"])
            self.assertFalse(packet["product_ready"])

    def test_cli_operator_proof_runs_two_admissions_and_emits_strict_json_packet(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_PROFILE_DIR": str(paths.profile_dir),
                    "WBP_MANAGED_DIR": str(paths.managed_dir),
                    "WBP_CONFIG_TOML": str(paths.config_toml),
                    "WBP_RUNTIME_EFFECTIVE_MODE_FILE": str(
                        paths.runtime_effective_mode_file
                    ),
                    "WBP_MANAGED_CONFIG_FILE": str(paths.managed_config_file),
                    "WBP_STATE_FILE": str(paths.state_file),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "operator-proof",
                    "--prompt",
                    PROMPT,
                    "--codex-bin",
                    str(fake_codex),
                    "--proof-dir",
                    str(root / "proof"),
                    "--codex-cwd",
                    str(ROOT),
                    "--expected-text",
                    EXPECTED_TEXT,
                    "--timeout-seconds",
                    "20",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["packet_kind"], operator.REPEATABLE_OPERATOR_PACKET_KIND)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["repeatable_same_turn_operator_proof_proven"])
        self.assertEqual(packet["operator_run_count"], 2)
        self.assertTrue(packet["admission_run_ids_distinct"])
        self.assertTrue(packet["operator_invariant_digest_consistent"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        changed_names = {Path(path).name for path in packet["changed_files"]}
        self.assertIn("repeatable-same-turn-operator-proof.packet.json", changed_names)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
