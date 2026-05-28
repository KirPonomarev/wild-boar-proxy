from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.role_slot_runtime_honor_and_handoff_semantics_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "role_slot_runtime_honor_and_handoff_semantics_r1_probe.py"


class RoleSlotRuntimeHonorAndHandoffSemanticsR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_handoff_truth_narrow_and_packet_backed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(temp_dir))

        dispatch = packets["role_slot_dispatch_packet.json"]
        self.assertEqual(dispatch["status"], "ok")
        self.assertTrue(dispatch["primary_slot_dispatched"])
        self.assertTrue(dispatch["coding_agent_slot_dispatched"])
        self.assertEqual(
            dispatch["requested_slot_ids"],
            ["primary_model_slot", "coding_agent_model_slot", "primary_model_slot"],
        )
        self.assertEqual(
            dispatch["runner_received_slot_ids"],
            ["primary_model_slot", "coding_agent_model_slot", "primary_model_slot"],
        )
        self.assertTrue(dispatch["operator_mediated_sequential_dispatch_proven"])
        self.assertFalse(dispatch["runtime_native_orchestration_proven"])
        self.assertFalse(dispatch["slot_binding_implies_dispatch"])

        handoff = packets["orchestration_handoff_packet.json"]
        self.assertEqual(handoff["status"], "ok")
        self.assertEqual(handoff["handoff_kind"], "operator_mediated_sequential")
        self.assertTrue(handoff["primary_to_coding_handoff_observed"])
        self.assertTrue(handoff["coding_to_primary_return_observed"])
        self.assertFalse(handoff["concurrent_execution_observed"])
        self.assertFalse(handoff["generalized_workflow_capability_proven"])
        self.assertFalse(handoff["autonomous_runtime_native_orchestration_proven"])

        provenance = packets["step_provenance_packet.json"]
        self.assertEqual(provenance["status"], "ok")
        self.assertEqual(len(provenance["steps"]), 3)
        self.assertEqual(
            [step["packet_execution_slot_id"] for step in provenance["steps"]],
            ["primary_model_slot", "coding_agent_model_slot", "primary_model_slot"],
        )
        self.assertTrue(
            all(step["runner_slot_id_matches_requested"] for step in provenance["steps"])
        )
        self.assertTrue(provenance["transcript_preserves_step_events"])

        blocked = packets["blocked_handoff_packet.json"]
        self.assertEqual(blocked["status"], "ok")
        self.assertEqual(blocked["blocked_packet_status"], "rejected")
        self.assertEqual(blocked["blocked_packet_machine_error_code"], "SLOT_NOT_BOUND")
        self.assertEqual(blocked["requested_slot_id"], "reviewer_model_slot")
        self.assertEqual(blocked["current_execution_slot_id"], "primary_model_slot")
        self.assertIn("SLOT_NOT_BOUND", blocked["precondition_failures"])
        self.assertTrue(blocked["runner_call_count_unchanged"])
        self.assertFalse(blocked["fallback_attempted"])
        self.assertTrue(blocked["blocked_handoff_honest"])

        non_claims = packets["orchestration_non_claims_packet.json"]
        self.assertFalse(non_claims["stored_slots_imply_autonomous_orchestration"])
        self.assertFalse(non_claims["single_handoff_proves_generalized_workflow"])
        self.assertFalse(non_claims["sequential_handoff_implies_concurrent_execution"])
        self.assertFalse(non_claims["operator_mediated_equals_runtime_native"])
        self.assertFalse(non_claims["completed_chain_implies_workflow_usefulness"])
        self.assertFalse(non_claims["implicit_primary_defaulting_is_handoff_proof"])

        boundary = packets["role_honor_boundary_packet.json"]
        self.assertTrue(boundary["implicit_primary_default_observed"])

        gap_ids = {gap["id"] for gap in packets["orchestration_gap_matrix.json"]["gaps"]}
        self.assertIn("runtime_native_orchestration_not_proven", gap_ids)
        self.assertIn("downstream_reviewer_scanner_slots_unproven", gap_ids)
        self.assertIn("concurrent_orchestration_not_proven", gap_ids)
        self.assertIn("same_model_multi_role_disambiguation_not_proven", gap_ids)
        self.assertIn("implicit_primary_defaulting_remains_admitted", gap_ids)

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["stored_slot_treated_as_dispatch_proof"])
        self.assertFalse(false_green["operator_mediated_sequence_treated_as_autonomous"])
        self.assertFalse(false_green["sequential_handoff_treated_as_concurrent"])
        self.assertFalse(false_green["completed_chain_treated_as_workflow_value"])
        self.assertFalse(false_green["blocked_handoff_treated_as_successful_fallback"])

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    temp_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 9)

            audit = json.loads(
                (Path(temp_dir) / "independent_audit_packet.json").read_text(encoding="utf-8")
            )
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn("explicit_slot_target_is_forwarded_to_runner_payload", finding_ids)
            self.assertIn("primary_coding_primary_sequence_is_packet_backed", finding_ids)
            self.assertIn("blocked_unbound_reviewer_slot_does_not_fallback", finding_ids)
            self.assertIn(
                "distinct_runtime_model_and_provider_paths_observed_for_primary_and_coding_slots",
                finding_ids,
            )
            self.assertIn(
                "implicit_primary_defaulting_is_packet_visible_and_left_narrow",
                finding_ids,
            )
            self.assertIn("autonomous_runtime_native_orchestration_remains_unproven", finding_ids)


if __name__ == "__main__":
    unittest.main()
