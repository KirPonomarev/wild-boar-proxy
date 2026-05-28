# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.repeatable_operator_workflow_readiness_classification_r1_probe import (
    TARGET_STATUS,
    build_packets,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = (
    ROOT
    / "tools"
    / "repeatable_operator_workflow_readiness_classification_r1_probe.py"
)


class RepeatableOperatorWorkflowReadinessClassificationR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_repeatability_truth_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(temp_dir))

        matrix = packets["task_class_readiness_matrix_packet.json"]
        self.assertEqual(matrix["status"], "ok")
        self.assertEqual(matrix["task_class_count"], 3)
        self.assertEqual(
            matrix["task_class_ids"],
            ["route_selection", "coding_artifact_skeleton", "review_return_artifact"],
        )
        self.assertEqual(matrix["useful_with_limits_count"], 2)
        self.assertEqual(matrix["baseline_only_preferred_count"], 1)
        self.assertEqual(matrix["ceremony_only_count"], 0)
        self.assertEqual(matrix["indeterminate_count"], 0)
        self.assertFalse(matrix["class_count_summary_is_readiness_proof"])

        rows = {row["task_class_id"]: row for row in packets["baseline_vs_chain_task_class_results.json"]["rows"]}
        route = rows["route_selection"]
        self.assertTrue(route["baseline_completed"])
        self.assertTrue(route["chain_completed"])
        self.assertEqual(route["classification"], "baseline_only_preferred")
        self.assertFalse(route["useful_with_limits"])
        self.assertTrue(route["baseline_only_preferred"])
        self.assertFalse(route["preferred_by_default_proven"])
        self.assertFalse(route["same_execution_path"])

        coding = rows["coding_artifact_skeleton"]
        self.assertTrue(coding["baseline_completed"])
        self.assertTrue(coding["chain_completed"])
        self.assertEqual(coding["classification"], "useful_with_limits")
        self.assertTrue(coding["useful_with_limits"])
        self.assertTrue(coding["step_separation_observed"])
        self.assertTrue(coding["task_relevant_chain_signal_observed"])
        self.assertTrue(coding["coding_artifact_consumed_by_primary_return"])
        self.assertFalse(coding["preferred_by_default_proven"])

        review = rows["review_return_artifact"]
        self.assertTrue(review["baseline_completed"])
        self.assertTrue(review["chain_completed"])
        self.assertEqual(review["classification"], "useful_with_limits")
        self.assertTrue(review["useful_with_limits"])
        self.assertTrue(review["step_separation_observed"])
        self.assertTrue(review["task_relevant_chain_signal_observed"])
        self.assertTrue(review["coding_artifact_consumed_by_primary_return"])

        readiness = packets["operator_workflow_readiness_packet.json"]
        self.assertEqual(readiness["status"], "ok")
        self.assertEqual(readiness["final_status"], TARGET_STATUS)
        self.assertEqual(
            readiness["readiness_scope_classification"], "operator_facing_bounded_probe_only"
        )
        self.assertEqual(
            readiness["operator_facing_bounded_readiness_classification"],
            "repeatable_usefulness_observed_with_limits",
        )
        self.assertTrue(readiness["repeatable_usefulness_observed"])
        self.assertFalse(readiness["preferred_by_default_proven"])
        self.assertFalse(readiness["product_readiness_proven"])
        self.assertFalse(readiness["rollout_readiness_proven"])
        self.assertFalse(readiness["autonomous_workflow_quality_proven"])
        self.assertFalse(readiness["user_wide_productivity_gain_proven"])

        repeatability = packets["workflow_repeatability_packet.json"]
        self.assertEqual(
            repeatability["repeatability_scope_classification"],
            "bounded_task_class_probe_only",
        )
        self.assertEqual(repeatability["task_class_count"], 3)
        self.assertEqual(repeatability["useful_with_limits_count"], 2)
        self.assertTrue(repeatability["repeatable_usefulness_threshold_met"])
        self.assertTrue(repeatability["repeatable_usefulness_observed"])
        self.assertEqual(repeatability["baseline_only_preferred_count"], 1)
        self.assertTrue(repeatability["operator_mediated_repeatability_only"])
        self.assertFalse(repeatability["default_workflow_preference_proven"])
        self.assertTrue(repeatability["counts_not_used_as_primary_claim_basis"])

        non_claims = packets["readiness_non_claims_packet.json"]
        self.assertFalse(non_claims["useful_classes_prove_general_multi_agent_productivity"])
        self.assertFalse(non_claims["repeatability_implies_answer_quality_superiority"])
        self.assertFalse(non_claims["operator_mediated_repeatability_implies_autonomy"])
        self.assertFalse(non_claims["bounded_readiness_implies_product_wide_readiness"])
        self.assertFalse(non_claims["repeated_usefulness_implies_default_workflow_preference"])
        self.assertFalse(non_claims["class_count_summary_implies_readiness_by_itself"])
        self.assertFalse(non_claims["bounded_readiness_implies_rollout_readiness"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["one_useful_class_treated_as_general_workflow_readiness"])
        self.assertFalse(false_green["baseline_only_preferred_classes_hidden_or_averaged_away"])
        self.assertFalse(
            false_green["operator_mediated_repeatability_treated_as_autonomous_intelligence"]
        )
        self.assertFalse(false_green["cross_class_counts_treated_as_superiority_claim"])
        self.assertFalse(false_green["chain_ceremony_treated_as_workflow_value"])
        self.assertFalse(false_green["bounded_readiness_treated_as_rollout_readiness"])

        gap_ids = {gap["id"] for gap in packets["readiness_gap_matrix.json"]["gaps"]}
        self.assertIn("bounded_probe_task_classes_do_not_generalize_to_product_readiness", gap_ids)
        self.assertIn("operator_mediated_repeatability_not_autonomous_workflow_quality", gap_ids)
        self.assertIn("baseline_only_preferred_class_remains_admitted", gap_ids)
        self.assertIn("class_count_summary_cannot_stand_as_readiness_proof", gap_ids)

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
                "three_bounded_task_classes_observed_under_same_owner_authorized_plain_response_guard",
                finding_ids,
            )
            self.assertIn(
                "repeatable_usefulness_observed_in_two_task_classes_with_limits",
                finding_ids,
            )
            self.assertIn("baseline_only_preferred_class_remains_visible_in_matrix", finding_ids)
            self.assertIn(
                "operator_facing_bounded_readiness_does_not_expand_to_product_readiness",
                finding_ids,
            )
            self.assertIn(
                "class_count_summary_alone_does_not_support_default_workflow_preference",
                finding_ids,
            )


if __name__ == "__main__":
    unittest.main()
