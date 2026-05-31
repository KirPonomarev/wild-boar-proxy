# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.original_vs_custom_acceleration_reconciliation_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "original_vs_custom_acceleration_reconciliation_r1_probe.py"


class OriginalVsCustomAccelerationReconciliationR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_measurement_visibility_separate_from_comparability(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(tmpdir) / "evidence")

        comparability = packets["original_vs_custom_comparability_packet.json"]
        self.assertEqual(comparability["status"], "ok")
        self.assertTrue(comparability["launch_modes_cover_original_and_custom"])
        self.assertFalse(comparability["same_binary_proven_for_measured_paths"])
        self.assertFalse(comparability["same_binary_scope_counts_as_same_path"])
        self.assertFalse(comparability["same_execution_path_proven"])
        self.assertEqual(
            comparability["execution_path_equivalence_classification"],
            "unknown_or_divergent",
        )
        self.assertEqual(
            comparability["custom_measurement_source_classification"],
            "bounded_contour_local_runner_harness_only",
        )
        self.assertEqual(
            comparability["original_measurement_source_classification"],
            "not_observed_in_admitted_inputs",
        )
        self.assertFalse(comparability["measurement_visibility_does_not_prove_comparison_admissibility"])
        self.assertFalse(comparability["approximate_equivalence_counts_as_clean_acceleration"])
        self.assertFalse(comparability["comparison_admitted"])
        self.assertEqual(comparability["comparison_status"], "limited_or_not_admitted")

        measurement = packets["acceleration_measurement_packet.json"]
        self.assertEqual(measurement["status"], "ok")
        self.assertTrue(measurement["custom_packet_latency_surface_present"])
        self.assertTrue(measurement["custom_wall_clock_surface_present"])
        self.assertFalse(measurement["original_side_timing_visible"])
        self.assertFalse(measurement["original_side_request_count_visible"])
        self.assertFalse(measurement["original_side_token_usage_visible"])
        self.assertFalse(measurement["visible_timing_fields_authorize_comparison"])
        self.assertTrue(measurement["measurement_surface_truth_only"])

        classification = packets["acceleration_classification_packet.json"]
        self.assertEqual(classification["status"], "ok")
        self.assertEqual(
            classification["final_status"],
            "ORIGINAL_VS_CUSTOM_ACCELERATION_RECONCILIATION_CLASSIFIED_WITH_LIMITS",
        )
        self.assertEqual(classification["current_comparison_status"], "limited_or_not_admitted")
        self.assertTrue(classification["blocker_refined_here"])
        self.assertTrue(classification["known_blocker_localized"])
        self.assertFalse(classification["prior_limiter_reduced"])
        self.assertFalse(classification["observed_acceleration_claim_admitted"])
        self.assertFalse(classification["bounded_observed_acceleration_implies_product_wide_gain"])
        self.assertFalse(classification["timing_difference_implies_quality_superiority"])
        self.assertFalse(classification["same_binary_clean_proof_observed"])
        self.assertTrue(classification["integrity_boundary_kept_separate"])
        self.assertFalse(classification["history_boundary_reopened"])

        non_claims = packets["acceleration_non_claims_packet.json"]
        self.assertFalse(non_claims["timing_difference_implies_quality_superiority"])
        self.assertFalse(non_claims["provider_declared_fast_path_equals_observed_acceleration"])
        self.assertFalse(
            non_claims["imported_earlier_timing_packets_alone_prove_original_vs_custom_acceleration"]
        )
        self.assertFalse(non_claims["one_bounded_comparison_proves_broad_product_acceleration"])
        self.assertFalse(non_claims["visible_timing_fields_alone_authorize_comparison"])
        self.assertFalse(non_claims["same_binary_alone_proves_fair_acceleration_comparison"])
        self.assertFalse(non_claims["bounded_observed_acceleration_implies_product_wide_speed_gain"])
        self.assertFalse(
            non_claims["approximate_model_mode_equivalence_yields_clean_acceleration_proof"]
        )

        gaps = packets["acceleration_gap_matrix.json"]
        gap_ids = {gap["id"] for gap in gaps["gaps"]}
        self.assertIn("original_side_timing_surface_not_observed_in_admitted_inputs", gap_ids)
        self.assertIn("same_binary_not_proven_for_measured_paths", gap_ids)
        self.assertIn("execution_path_equivalence_not_proven", gap_ids)

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["visible_timing_data_treated_as_sufficient_comparison_proof"])
        self.assertFalse(false_green["same_binary_treated_as_same_path"])
        self.assertFalse(false_green["partial_equivalence_treated_as_clean_comparability"])
        self.assertFalse(false_green["bounded_acceleration_treated_as_broad_product_speedup"])
        self.assertFalse(false_green["timing_treated_as_quality_gain"])
        self.assertFalse(false_green["imported_packets_treated_as_reproven_acceleration"])

        audit = packets["independent_audit_packet.json"]
        self.assertEqual(audit["status"], "ok")
        finding_ids = {finding["id"] for finding in audit["findings"]}
        self.assertIn("custom_side_measurement_surfaces_exist_but_remain_contour_local_only", finding_ids)
        self.assertIn("original_side_timing_surface_absent_in_admitted_inputs", finding_ids)
        self.assertIn(
            "same_binary_scope_observation_does_not_upgrade_path_equivalence",
            finding_ids,
        )
        self.assertIn(
            "clean_original_vs_custom_acceleration_claim_remains_not_admitted",
            finding_ids,
        )

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    str(evidence_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 7)

            classification = json.loads(
                (evidence_dir / "acceleration_classification_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                classification["final_status"],
                "ORIGINAL_VS_CUSTOM_ACCELERATION_RECONCILIATION_CLASSIFIED_WITH_LIMITS",
            )


if __name__ == "__main__":
    unittest.main()
