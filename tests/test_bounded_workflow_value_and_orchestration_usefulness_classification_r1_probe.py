# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.bounded_workflow_value_and_orchestration_usefulness_classification_r1_probe import (
    build_packets,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = (
    ROOT
    / "tools"
    / "bounded_workflow_value_and_orchestration_usefulness_classification_r1_probe.py"
)


class BoundedWorkflowValueAndOrchestrationUsefulnessClassificationR1ProbeTests(
    unittest.TestCase
):
    def test_build_packets_keep_workflow_value_claims_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(temp_dir))

        baseline = packets["primary_only_baseline_packet.json"]
        self.assertEqual(baseline["status"], "ok")
        self.assertEqual(baseline["task_fixture_id"], "workflow_task_alpha")
        self.assertEqual(baseline["path_kind"], "primary_only")
        self.assertTrue(baseline["completion_observed"])
        self.assertTrue(baseline["output_present"])
        self.assertEqual(baseline["baseline_output_view"]["execution_slot_id"], "primary_model_slot")
        self.assertEqual(baseline["baseline_output_view"]["artifact_kind"], "single_path_summary")
        self.assertTrue(baseline["baseline_output_view"]["artifact_task_relevant"])

        chain = packets["bounded_orchestration_outcome_packet.json"]
        self.assertEqual(chain["status"], "ok")
        self.assertEqual(chain["task_fixture_id"], "workflow_task_alpha")
        self.assertEqual(chain["path_kind"], "primary_to_coding_to_primary")
        self.assertEqual(chain["step_count"], 3)
        self.assertTrue(chain["completion_observed"])
        self.assertTrue(chain["step_separation_observed"])
        self.assertTrue(chain["coding_artifact_task_relevant"])
        self.assertTrue(chain["coding_artifact_consumed_by_primary_return"])
        self.assertEqual(chain["primary_plan_step"]["execution_slot_id"], "primary_model_slot")
        self.assertEqual(chain["coding_step"]["execution_slot_id"], "coding_agent_model_slot")
        self.assertEqual(chain["primary_return_step"]["execution_slot_id"], "primary_model_slot")
        self.assertTrue(chain["operator_mediated_chain_only"])

        comparison = packets["workflow_usefulness_comparison_packet.json"]
        self.assertEqual(
            comparison["structural_signal_source_classification"],
            "contour_local_runner_harness_packetized_by_probe",
        )
        self.assertEqual(
            comparison["comparison_status"], "bounded_structural_signal_only_with_limits"
        )
        self.assertTrue(comparison["comparison_admitted_for_structure"])
        self.assertFalse(comparison["comparison_admitted_for_superiority"])
        self.assertTrue(comparison["task_relevant_structural_signal_observed"])
        self.assertFalse(comparison["chain_only_ceremony_observed"])
        self.assertTrue(comparison["bounded_chain_structural_signal_only"])
        self.assertFalse(comparison["workflow_usefulness_superiority_proven"])
        self.assertFalse(comparison["answer_quality_superiority_proven"])
        self.assertFalse(comparison["general_productivity_gain_proven"])
        self.assertTrue(comparison["operator_mediated_not_autonomous"])

        comparability = packets["workflow_comparability_packet.json"]
        self.assertEqual(comparability["comparison_scope_classification"], "bounded_probe_only")
        self.assertTrue(comparability["same_task_class"])
        self.assertTrue(comparability["same_policy_guard_conditions"])
        self.assertTrue(comparability["same_admitted_semantic_mode"])
        self.assertTrue(comparability["same_runtime_family"])
        self.assertFalse(comparability["same_lane_topology"])
        self.assertFalse(comparability["same_execution_path"])
        self.assertTrue(comparability["materially_comparable_for_structure"])
        self.assertFalse(comparability["materially_comparable_for_superiority_claim"])
        self.assertEqual(
            comparability["comparison_blocker"],
            "harness_local_synthetic_outputs_do_not_support_superiority_claim",
        )
        self.assertFalse(comparability["latency_or_throughput_decisive_here"])

        non_claims = packets["workflow_non_claims_packet.json"]
        self.assertFalse(non_claims["bounded_chain_proves_general_multi_agent_productivity"])
        self.assertFalse(non_claims["successful_chain_implies_better_coding_quality_generally"])
        self.assertFalse(non_claims["extra_role_steps_imply_useful_orchestration"])
        self.assertFalse(non_claims["longer_output_implies_better_workflow_usefulness"])
        self.assertFalse(non_claims["bounded_usefulness_implies_answer_quality_superiority"])
        self.assertFalse(non_claims["structured_chain_implies_better_spend_efficiency"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["handoff_success_treated_as_workflow_value_by_itself"])
        self.assertFalse(
            false_green["extra_chain_steps_treated_as_better_outcome_without_packet_evidence"]
        )
        self.assertFalse(false_green["longer_output_treated_as_better_workflow_value"])
        self.assertFalse(false_green["operator_mediated_chain_treated_as_autonomous_intelligence"])
        self.assertFalse(false_green["latency_or_throughput_reused_as_usefulness_proof"])
        self.assertFalse(false_green["chain_complexity_treated_as_usefulness"])

        gap_ids = {gap["id"] for gap in packets["workflow_gap_matrix.json"]["gaps"]}
        self.assertIn("workflow_superiority_over_primary_only_not_proven", gap_ids)
        self.assertIn("harness_local_synthetic_outputs_limit_usefulness_claim_scope", gap_ids)
        self.assertIn("operator_mediated_chain_not_autonomous_workflow_intelligence", gap_ids)
        self.assertIn("single_task_fixture_does_not_generalize_to_broader_workloads", gap_ids)

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
            self.assertEqual(summary["packet_count"], 8)

            audit = json.loads(
                (Path(temp_dir) / "independent_audit_packet.json").read_text(encoding="utf-8")
            )
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn(
                "baseline_and_chain_both_run_under_authorized_plain_response_guards",
                finding_ids,
            )
            self.assertIn(
                "bounded_chain_preserves_primary_coding_primary_step_separation",
                finding_ids,
            )
            self.assertIn(
                "task_relevant_coding_artifact_is_observed_and_consumed_by_primary_return",
                finding_ids,
            )
            self.assertIn(
                "same_execution_path_remains_false_even_when_structural_comparison_is_admitted",
                finding_ids,
            )
            self.assertIn(
                "workflow_superiority_claim_remains_not_admitted_under_harness_local_synthetic_outputs",
                finding_ids,
            )
            self.assertIn("general_productivity_gain_remains_unproven", finding_ids)


if __name__ == "__main__":
    unittest.main()
