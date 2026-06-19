# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import fresh_live_custom_codex_e2e_proof as fresh_live
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_admission import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    ROUTE_ID,
    _paths,
    _write_fake_codex,
    _write_profile,
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
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_expected_text_recorded"])
    testcase.assertFalse(packet["expected_text_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_product_ui_or_native_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _admission_ok_packet() -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "packet_kind": "wbp_repeatable_custom_codex_admission",
        "admission_proven": True,
        "same_turn_custom_codex_flow_proven": True,
        "hook_ledger_fresh": True,
        "user_prompt_submit_hook_ran": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "live_provider_response_proven": True,
        "codex_exec_prompt_digest": "a" * 64,
        "expected_text_digest": "b" * 64,
        "blocking_reasons": [],
    }


def _fresh_runner_ok_packet(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "machine_error_code": "OK",
        "packet_kind": "wbp_official_e2e_fresh_working_flow_proof_runner",
        "fresh_e2e_working_flow_proven": True,
        "official_e2e_working_flow_proven": True,
        "proof_run_started_at_ns_bound": True,
        "fresh_inputs_created_after_start": True,
        "real_custom_hook_proof_file_sha256_bound_to_fresh_inputs": True,
        "codex_exec_jsonl_file_sha256_bound_to_fresh_inputs": True,
        "real_custom_hook_contract_valid": True,
        "official_e2e_runner_valid": True,
        "custom_codex_hook_to_official_working_flow_bound": True,
        "custom_codex_flow_origin_proven": True,
        "user_prompt_submit_hook_ran": True,
        "api_lane_called": True,
        "dispatch_proven": True,
        "live_provider_response_proven": True,
        "codex_working_flow_delivery_proven": True,
        "official_delivery_candidate_lineage_proven": True,
        "official_observation_lineage_file_backed": True,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "blocking_reasons": [],
    }
    payload.update(overrides)
    return payload


class FreshLiveCustomCodexE2EProofTests(unittest.TestCase):
    def test_positive_runs_admission_then_fresh_official_e2e_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")

            with mock.patch.dict(
                "os.environ",
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = fresh_live.run_fresh_live_custom_codex_e2e_proof_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

            changed_names = {Path(path).name for path in packet["changed_files"]}

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            fresh_live.FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND,
        )
        self.assertTrue(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertTrue(packet["fresh_live_e2e_working_flow_proven"])
        self.assertTrue(packet["admission_proven"])
        self.assertTrue(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["hook_ledger_fresh"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["official_fresh_runner_valid"])
        self.assertTrue(packet["official_e2e_working_flow_proven"])
        self.assertTrue(packet["custom_codex_hook_to_official_working_flow_bound"])
        self.assertTrue(packet["proof_run_started_at_ns_bound"])
        self.assertTrue(packet["source_proof_file_present"])
        self.assertTrue(packet["codex_exec_jsonl_file_present"])
        self.assertTrue(packet["fresh_runner_inputs_file_present"])
        self.assertTrue(packet["fresh_runner_packet_file_present"])
        self.assertTrue(packet["source_proof_sha256"])
        self.assertTrue(packet["codex_exec_jsonl_sha256"])
        self.assertTrue(packet["fresh_runner_inputs_sha256"])
        self.assertTrue(packet["official_fresh_runner_packet_sha256"])
        self.assertTrue(packet["admission_packet_sha256"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["runtime_effective_truth_written"])
        self.assertTrue(packet["evidence_written"])
        self.assertTrue(packet["file_mutation_attempted"])
        self.assertIn("fresh-runner-inputs.packet.json", changed_names)
        self.assertIn("official-fresh-runner.packet.json", changed_names)
        self.assertIn("fresh-live-e2e-proof.packet.json", changed_names)
        self.assertIn("custom-codex-admission.packet.json", changed_names)
        self.assertIn("codex-exec.jsonl", changed_names)
        _assert_no_product_ui_or_native_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_final_packet_uses_admission_dispatch_when_legacy_field_is_absent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_proof = root / "proof" / "admission" / "source.json"
            codex_jsonl = root / "proof" / "admission" / "codex-exec.jsonl"
            inputs_file = root / "proof" / "fresh-runner-inputs.packet.json"
            runner_file = root / "proof" / "official-fresh-runner.packet.json"
            final_file = root / "proof" / "fresh-live-e2e-proof.packet.json"
            for path in (source_proof, codex_jsonl, inputs_file, runner_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            admission = dict(_admission_ok_packet())
            admission.pop("route_bound_dispatch_proven", None)
            admission["dispatch_proven"] = True
            packet = fresh_live.build_fresh_live_custom_codex_e2e_packet(
                admission_packet=admission,
                fresh_runner_packet=_fresh_runner_ok_packet(dispatch_proven=True),
                proof_run_id="WBP_FRESH_LIVE_E2E_TEST_DISPATCH_PASSTHROUGH",
                proof_run_started_at_ns=1,
                proof_root=root / "proof",
                admission_dir=root / "proof" / "admission",
                fresh_runner_inputs_file=inputs_file,
                fresh_runner_packet_file=runner_file,
                source_proof_path=source_proof,
                codex_exec_jsonl_path=codex_jsonl,
                final_packet_path=final_file,
                changed_files=[],
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_final_packet_blocks_runner_only_dispatch_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_proof = root / "proof" / "admission" / "source.json"
            codex_jsonl = root / "proof" / "admission" / "codex-exec.jsonl"
            inputs_file = root / "proof" / "fresh-runner-inputs.packet.json"
            runner_file = root / "proof" / "official-fresh-runner.packet.json"
            final_file = root / "proof" / "fresh-live-e2e-proof.packet.json"
            for path in (source_proof, codex_jsonl, inputs_file, runner_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            admission = dict(_admission_ok_packet())
            admission.pop("route_bound_dispatch_proven", None)
            admission.pop("dispatch_proven", None)
            admission["api_lane_called"] = False
            packet = fresh_live.build_fresh_live_custom_codex_e2e_packet(
                admission_packet=admission,
                fresh_runner_packet=_fresh_runner_ok_packet(dispatch_proven=True),
                proof_run_id="WBP_FRESH_LIVE_E2E_TEST_RUNNER_ONLY_DISPATCH_BLOCKED",
                proof_run_started_at_ns=1,
                proof_root=root / "proof",
                admission_dir=root / "proof" / "admission",
                fresh_runner_inputs_file=inputs_file,
                fresh_runner_packet_file=runner_file,
                source_proof_path=source_proof,
                codex_exec_jsonl_path=codex_jsonl,
                final_packet_path=final_file,
                changed_files=[],
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh_live.FRESH_LIVE_E2E_ADMISSION_FAILED,
        )
        self.assertTrue(packet["admission_proven"])
        self.assertTrue(packet["official_fresh_runner_valid"])
        self.assertNotIn(
            "fresh_live_official_fresh_runner_not_proven",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertIn(
            "fresh_live_admission_dispatch_not_proven",
            packet["blocking_reasons"],
        )
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_missing_admission_artifacts_block_even_when_admission_claims_ok(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = fresh_live.build_fresh_live_custom_codex_e2e_packet(
                admission_packet=_admission_ok_packet(),
                fresh_runner_packet=_fresh_runner_ok_packet(),
                proof_run_id="WBP_FRESH_LIVE_E2E_TEST_MISSING_ARTIFACTS",
                proof_run_started_at_ns=1,
                proof_root=root / "proof",
                admission_dir=root / "proof" / "admission",
                fresh_runner_inputs_file=root / "proof" / "fresh-runner-inputs.packet.json",
                fresh_runner_packet_file=root / "proof" / "official-fresh-runner.packet.json",
                source_proof_path=root / "proof" / "admission" / "missing-source.json",
                codex_exec_jsonl_path=root / "proof" / "admission" / "missing-jsonl.jsonl",
                final_packet_path=root / "proof" / "fresh-live-e2e-proof.packet.json",
                changed_files=[],
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh_live.FRESH_LIVE_E2E_ARTIFACT_MISSING,
        )
        self.assertFalse(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertFalse(packet["source_proof_file_present"])
        self.assertFalse(packet["codex_exec_jsonl_file_present"])
        self.assertIn(
            "fresh_live_required_artifacts_missing",
            packet["blocking_reasons"],
        )
        _assert_no_product_ui_or_native_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_tampered_fresh_runner_green_packet_is_not_enough_without_bindings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            admission_dir = root / "proof" / "admission"
            admission_dir.mkdir(parents=True)
            source_proof = admission_dir / "user-prompt-submit-proof.packet.json"
            codex_jsonl = admission_dir / "codex-exec.jsonl"
            source_proof.write_text('{"packet_kind":"source"}\n', encoding="utf-8")
            codex_jsonl.write_text('{"type":"turn.completed"}\n', encoding="utf-8")

            packet = fresh_live.build_fresh_live_custom_codex_e2e_packet(
                admission_packet=_admission_ok_packet(),
                fresh_runner_packet=_fresh_runner_ok_packet(
                    proof_run_started_at_ns_bound=False,
                    codex_exec_jsonl_file_sha256_bound_to_fresh_inputs=False,
                ),
                proof_run_id="WBP_FRESH_LIVE_E2E_TEST_TAMPERED_RUNNER",
                proof_run_started_at_ns=1,
                proof_root=root / "proof",
                admission_dir=admission_dir,
                fresh_runner_inputs_file=root / "proof" / "fresh-runner-inputs.packet.json",
                fresh_runner_packet_file=root / "proof" / "official-fresh-runner.packet.json",
                source_proof_path=source_proof,
                codex_exec_jsonl_path=codex_jsonl,
                final_packet_path=root / "proof" / "fresh-live-e2e-proof.packet.json",
                changed_files=[],
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh_live.FRESH_LIVE_E2E_FRESH_RUNNER_FAILED,
        )
        self.assertFalse(packet["official_fresh_runner_valid"])
        self.assertFalse(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertIn(
            "fresh_runner_proof_run_started_at_ns_bound_not_true",
            packet["official_fresh_runner_acceptance_failures"],
        )
        self.assertIn(
            "fresh_runner_codex_exec_jsonl_file_sha256_bound_to_fresh_inputs_not_true",
            packet["official_fresh_runner_acceptance_failures"],
        )
        self.assertIn(
            "fresh_live_official_fresh_runner_not_proven",
            packet["blocking_reasons"],
        )
        _assert_no_product_ui_or_native_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_admission_failure_blocks_before_fresh_runner_inputs_are_claimed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")

            with mock.patch.dict(
                "os.environ",
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                    "WBP_FAKE_CODEX_MODE": "missing_run_id",
                },
            ):
                packet = fresh_live.run_fresh_live_custom_codex_e2e_proof_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh_live.FRESH_LIVE_E2E_ADMISSION_FAILED,
        )
        self.assertFalse(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertFalse(packet["official_fresh_runner_valid"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        self.assertFalse(packet["fresh_runner_inputs_file_present"])
        self.assertIn("fresh_live_admission_not_proven", packet["blocking_reasons"])
        self.assertIn(
            "fresh_live_official_fresh_runner_not_proven",
            packet["blocking_reasons"],
        )
        _assert_no_product_ui_or_native_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_cli_effect_classifier_marks_fresh_live_runner_as_mutate(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "codex-runner",
                "fresh-live-e2e-proof",
                "--prompt",
                "hi",
                "--codex-model",
                "gpt-5.4",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "mutate")
        self.assertEqual(args.codex_model, "gpt-5.4")

    def test_cli_emits_fresh_live_packet(self) -> None:
        expected = packets.build_command_packet(
            ok=True,
            human_message="fresh live ok",
            machine_error_code="OK",
            liveness="network_dependent",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            effect="mutate",
            extra={
                "schema_version": 1,
                "packet_kind": fresh_live.FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND,
                "fresh_live_custom_codex_e2e_proven": True,
                "state_written": False,
                "runtime_effective_truth_written": False,
                "evidence_written": True,
                "file_mutation_attempted": True,
                "blocking_reasons": [],
            },
        )
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_fresh_live_custom_codex_e2e_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "codex-runner",
                    "fresh-live-e2e-proof",
                    "--prompt",
                    "hi",
                    "--codex-model",
                    "gpt-5.4",
                    "--proof-dir",
                    "proof",
                    "--codex-cwd",
                    str(ROOT),
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["fresh_live_custom_codex_e2e_proven"])
        run_command.assert_called_once_with(
            paths=mock.ANY,
            prompt_text="hi",
            codex_bin=None,
            codex_model="gpt-5.4",
            proof_dir="proof",
            codex_cwd=str(ROOT),
            expected_text="WBP_DIP_DISPATCH_OK",
            sandbox="danger-full-access",
            timeout_seconds=300,
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
