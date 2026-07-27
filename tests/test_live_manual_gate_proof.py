# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import interactive_codex_working_flow_delivery as join
from wild_boar_proxy import live_manual_gate_proof as gate
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.runtime import RuntimePaths

from tests.test_interactive_codex_working_flow_delivery import (
    EXPECTED_TEXT,
    PROMPT,
    ROOT,
    ROUTE_ID,
    _events_for_source,
    _prepare_interactive_proof,
    _write_jsonl,
)


def _write_positive_working_flow_packet(root: Path) -> tuple[RuntimePaths, Path, Path]:
    paths, interactive_file, proof_dir = _prepare_interactive_proof(root)
    source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
    source = json.loads(source_file.read_text(encoding="utf-8"))
    jsonl_file = root / "codex-exec.jsonl"
    _write_jsonl(jsonl_file, _events_for_source(source))
    packet = join.run_interactive_codex_working_flow_delivery_command(
        interactive_proof_file=str(interactive_file),
        integrated_live_provider_proof_file=str(source_file),
        codex_exec_jsonl_file=str(jsonl_file),
        proof_dir=str(proof_dir),
    )
    assert packet["status"] == "ok"
    assert packet["codex_working_flow_delivery_proven"] is True
    return paths, proof_dir, proof_dir / join.FINAL_PACKET_FILENAME


def _assert_no_product_or_ui_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_live_manual_gate_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["source_file_unforgeable"])
    testcase.assertFalse(packet["cryptographic_authenticity_proven"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router_product_ready"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


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
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class LiveManualGateProofTests(unittest.TestCase):
    def test_positive_accepts_strict_interactive_working_flow_packet(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            paths, proof_dir, working_flow_file = _write_positive_working_flow_packet(
                root
            )
            packet = gate.run_live_manual_gate_proof_command(
                paths=paths,
                interactive_working_flow_delivery_file=str(working_flow_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], gate.LIVE_MANUAL_GATE_PACKET_KIND)
        self.assertEqual(packet["effect"], "mutate")
        self.assertTrue(packet["live_manual_gate_proven"])
        self.assertTrue(packet["trusted_user_prompt_submit_hook_ran"])
        self.assertTrue(packet["real_custom_codex_prompt_submit_proven"])
        self.assertTrue(packet["interactive_custom_codex_flow_proven"])
        self.assertTrue(packet["hook_ledger_fresh"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["runtime_context_bound"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["return_path_bound"])
        self.assertTrue(packet["assistant_continuation_bound"])
        self.assertTrue(packet["handoff_digest_bound"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_exec_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["strict_sealed_evidence"])
        self.assertTrue(packet["proof_seal_verified"])
        self.assertTrue(packet["working_flow_seal_input_hashes_bound"])
        self.assertTrue(packet["working_flow_file_sha256_bound"])
        self.assertTrue(packet["sealed_working_flow_file_sha256_bound"])
        self.assertTrue(packet["working_flow_seal_file_verified"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        self.assertEqual(packet["blocking_reasons"], [])
        changed_names = {Path(path).name for path in packet["changed_files"]}
        self.assertIn(gate.FINAL_PACKET_FILENAME, changed_names)
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_tampered_working_flow_claim_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            paths, proof_dir, working_flow_file = _write_positive_working_flow_packet(
                root
            )
            tampered = json.loads(working_flow_file.read_text(encoding="utf-8"))
            tampered["interactive_custom_codex_flow_proven"] = False
            tampered_file = root / "tampered-working-flow.packet.json"
            tampered_file.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
            packet = gate.run_live_manual_gate_proof_command(
                paths=paths,
                interactive_working_flow_delivery_file=str(tampered_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            gate.LIVE_MANUAL_GATE_WORKING_FLOW_INVALID,
        )
        self.assertFalse(packet["live_manual_gate_proven"])
        self.assertFalse(packet["trusted_user_prompt_submit_hook_ran"])
        self.assertFalse(packet["real_custom_codex_prompt_submit_proven"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertFalse(packet["return_path_bound"])
        self.assertIn(
            "interactive_custom_codex_flow_not_proven",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)

    def test_orphaned_final_packet_without_sibling_seal_artifacts_blocks_gate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            paths, _proof_dir, working_flow_file = _write_positive_working_flow_packet(
                root
            )
            orphan_dir = root / "orphan"
            orphan_dir.mkdir()
            orphan_file = orphan_dir / working_flow_file.name
            orphan_file.write_bytes(working_flow_file.read_bytes())
            packet = gate.run_live_manual_gate_proof_command(
                paths=paths,
                interactive_working_flow_delivery_file=str(orphan_file),
                proof_dir=str(orphan_dir),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            gate.LIVE_MANUAL_GATE_WORKING_FLOW_INVALID,
        )
        self.assertFalse(packet["live_manual_gate_proven"])
        self.assertFalse(packet["sealed_working_flow_file_sha256_bound"])
        self.assertFalse(packet["working_flow_seal_file_verified"])
        self.assertIn("sealed_working_flow_file_not_read", packet["blocking_reasons"])
        self.assertIn("working_flow_seal_file_not_read", packet["blocking_reasons"])
        self.assertIn(
            "working_flow_seal_verify_file_not_read",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)

    def test_product_ready_overclaim_blocks_gate_without_repeating_claim(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            paths, proof_dir, working_flow_file = _write_positive_working_flow_packet(
                root
            )
            tampered = json.loads(working_flow_file.read_text(encoding="utf-8"))
            tampered["product_ready"] = True
            tampered_file = root / "product-ready-overclaim.packet.json"
            tampered_file.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
            packet = gate.run_live_manual_gate_proof_command(
                paths=paths,
                interactive_working_flow_delivery_file=str(tampered_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["live_manual_gate_proven"])
        self.assertIn("product_ready_preclaimed", packet["blocking_reasons"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)

    def test_cli_live_manual_gate_proof_emits_final_packet(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            _paths, proof_dir, working_flow_file = _write_positive_working_flow_packet(
                root
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "live-manual-gate-proof",
                    "--interactive-working-flow-delivery-file",
                    str(working_flow_file),
                    "--proof-dir",
                    str(proof_dir),
                    "--json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["packet_kind"], gate.LIVE_MANUAL_GATE_PACKET_KIND)
        self.assertTrue(packet["live_manual_gate_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])


if __name__ == "__main__":
    unittest.main()
