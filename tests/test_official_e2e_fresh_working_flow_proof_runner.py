# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import official_e2e_fresh_working_flow_proof_runner as fresh
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_codex_working_flow_delivery_proof import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _events_for_packet,
    _integrated_packet,
    _jsonl_from_events,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(_jsonl_from_events(events), encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _secret_values() -> list[str]:
    return [PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT]


def _fresh_inputs_payload(
    *,
    started_at_ns: int,
    expected_real_hook_sha256: str,
    expected_jsonl_sha256: str,
    proof_run_id: str = "WBP_FRESH_E2E_RUN_001",
    real_hook_file: str = "real-hook.json",
    jsonl_file: str = "codex-exec.jsonl",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet_kind": (
            fresh.OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND
        ),
        "proof_run_id": proof_run_id,
        "proof_run_started_at_ns": started_at_ns,
        "real_custom_hook_proof_file": real_hook_file,
        "codex_exec_jsonl_file": jsonl_file,
        "expected_real_custom_hook_proof_file_sha256": expected_real_hook_sha256,
        "expected_codex_exec_jsonl_file_sha256": expected_jsonl_sha256,
    }


def _write_fresh_fixture(
    root: Path,
    *,
    source: dict[str, object] | None = None,
    started_at_ns: int | None = None,
) -> tuple[dict[str, object], Path, Path, Path]:
    source_packet = _integrated_packet() if source is None else source
    events = _events_for_packet(source_packet)
    start_ns = time.time_ns() - 1_000_000 if started_at_ns is None else started_at_ns
    real_hook_file = root / "real-hook.json"
    jsonl_file = root / "codex-exec.jsonl"
    inputs_file = root / "fresh-runner-inputs.json"
    _write_json(real_hook_file, source_packet)
    _write_jsonl(jsonl_file, events)
    _write_json(
        inputs_file,
        _fresh_inputs_payload(
            started_at_ns=start_ns,
            expected_real_hook_sha256=_file_sha256(real_hook_file),
            expected_jsonl_sha256=_file_sha256(jsonl_file),
        ),
    )
    return source_packet, inputs_file, real_hook_file, jsonl_file


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


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in _secret_values():
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_task_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class OfficialE2EFreshWorkingFlowProofRunnerTests(unittest.TestCase):
    def test_positive_builds_fresh_file_backed_chain_from_hook_and_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, inputs_file, _, _ = _write_fresh_fixture(root)
            proof_dir = root / "proof"

            packet = fresh.run_official_e2e_fresh_working_flow_proof_runner_command(
                inputs_file=str(inputs_file),
                proof_output_dir=str(proof_dir),
            )

            artifact_names = set(packet["proof_artifact_file_names"])
            written_artifacts = sorted(path.name for path in proof_dir.glob("*.json"))

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            fresh.OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "mutate")
        self.assertTrue(packet["fresh_runner_inputs_valid"])
        self.assertTrue(packet["fresh_inputs_created_after_start"])
        self.assertTrue(packet["proof_run_started_at_ns_bound"])
        self.assertTrue(packet["real_custom_hook_proof_file_created_after_start"])
        self.assertTrue(packet["codex_exec_jsonl_file_created_after_start"])
        self.assertTrue(packet["real_custom_hook_proof_file_sha256_bound_to_fresh_inputs"])
        self.assertTrue(packet["codex_exec_jsonl_file_sha256_bound_to_fresh_inputs"])
        self.assertTrue(packet["real_custom_hook_contract_valid"])
        self.assertTrue(packet["hook_event_digest_bound"])
        self.assertTrue(packet["hook_session_digest_bound"])
        self.assertTrue(packet["hook_thread_or_turn_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["official_chain_artifacts_written"])
        self.assertTrue(packet["proof_output_dir_artifacts_written"])
        self.assertEqual(packet["official_chain_artifact_failures"], [])
        self.assertTrue(packet["official_e2e_runner_valid"])
        self.assertTrue(packet["fresh_e2e_working_flow_proven"])
        self.assertTrue(packet["official_e2e_working_flow_proven"])
        self.assertTrue(packet["custom_codex_hook_to_official_working_flow_bound"])
        self.assertTrue(packet["custom_codex_flow_origin_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["official_delivery_candidate_lineage_proven"])
        self.assertTrue(packet["official_observation_lineage_file_backed"])
        self.assertTrue(packet["evidence_written"])
        self.assertTrue(packet["file_mutation_attempted"])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["runtime_effective_truth_written"])
        self.assertEqual(packet["changed_files"], [])
        self.assertFalse(packet["proof_artifact_file_paths_recorded"])
        self.assertFalse(packet["proof_output_dir_path_recorded"])
        self.assertIn("official-e2e-runner.packet.json", artifact_names)
        self.assertEqual(artifact_names, set(written_artifacts))
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_product_ui_or_native_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_stale_input_files_block_before_official_chain_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, inputs_file, real_hook_file, jsonl_file = _write_fresh_fixture(root)
            stale_start_ns = max(
                real_hook_file.stat().st_mtime_ns,
                jsonl_file.stat().st_mtime_ns,
            ) + 1_000_000
            _write_json(
                inputs_file,
                _fresh_inputs_payload(
                    started_at_ns=stale_start_ns,
                    expected_real_hook_sha256=_file_sha256(real_hook_file),
                    expected_jsonl_sha256=_file_sha256(jsonl_file),
                ),
            )

            with mock.patch(
                "wild_boar_proxy.official_e2e_fresh_working_flow_proof_runner."
                "_run_official_chain"
            ) as official_chain:
                packet = fresh.run_official_e2e_fresh_working_flow_proof_runner_command(
                    inputs_file=str(inputs_file),
                    proof_output_dir=str(root / "proof"),
                )

        official_chain.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh.OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_STALE_REPLAY,
        )
        self.assertIn(
            "real_custom_hook_proof_file_not_created_after_start",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "codex_exec_jsonl_file_not_created_after_start",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["fresh_inputs_created_after_start"])
        self.assertFalse(packet["fresh_e2e_working_flow_proven"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        _assert_no_product_ui_or_native_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_jsonl_digest_mismatch_blocks_before_official_chain_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, inputs_file, real_hook_file, _ = _write_fresh_fixture(root)
            payload = _fresh_inputs_payload(
                started_at_ns=time.time_ns() - 1_000_000,
                expected_real_hook_sha256=_file_sha256(real_hook_file),
                expected_jsonl_sha256="0" * 64,
            )
            _write_json(inputs_file, payload)

            with mock.patch(
                "wild_boar_proxy.official_e2e_fresh_working_flow_proof_runner."
                "_run_official_chain"
            ) as official_chain:
                packet = fresh.run_official_e2e_fresh_working_flow_proof_runner_command(
                    inputs_file=str(inputs_file),
                    proof_output_dir=str(root / "proof"),
                )

        official_chain.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh.OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertIn(
            "codex_exec_jsonl_file_sha256_not_bound_to_fresh_inputs",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["codex_exec_jsonl_file_sha256_bound_to_fresh_inputs"])
        self.assertFalse(packet["fresh_e2e_working_flow_proven"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        _assert_no_product_ui_or_native_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_hook_event_digest_blocks_before_official_chain_runs(self) -> None:
        source = dict(_integrated_packet())
        source["hook_event_digest"] = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, inputs_file, _, _ = _write_fresh_fixture(root, source=source)

            with mock.patch(
                "wild_boar_proxy.official_e2e_fresh_working_flow_proof_runner."
                "_run_official_chain"
            ) as official_chain:
                packet = fresh.run_official_e2e_fresh_working_flow_proof_runner_command(
                    inputs_file=str(inputs_file),
                    proof_output_dir=str(root / "proof"),
                )

        official_chain.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh.OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertIn(
            "real_custom_hook_hook_event_digest_missing",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["real_custom_hook_contract_valid"])
        self.assertFalse(packet["fresh_e2e_working_flow_proven"])
        _assert_no_product_ui_or_native_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_fresh_runner_as_mutate(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-e2e-fresh-working-flow-proof-runner",
                "--inputs-file",
                "fresh-runner-inputs.json",
                "--proof-output-dir",
                "proof",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "mutate")

    def test_cli_emits_fresh_runner_packet(self) -> None:
        expected = packets.build_command_packet(
            ok=True,
            human_message="fresh runner ok",
            machine_error_code="OK",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            effect="mutate",
            extra={
                "schema_version": 1,
                "packet_kind": (
                    fresh.OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND
                ),
                "fresh_e2e_working_flow_proven": True,
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
                "wild_boar_proxy.cli."
                "run_official_e2e_fresh_working_flow_proof_runner_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-e2e-fresh-working-flow-proof-runner",
                    "--inputs-file",
                    "fresh-runner-inputs.json",
                    "--proof-output-dir",
                    "proof",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["fresh_e2e_working_flow_proven"])
        run_command.assert_called_once_with(
            inputs_file="fresh-runner-inputs.json",
            proof_output_dir="proof",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
