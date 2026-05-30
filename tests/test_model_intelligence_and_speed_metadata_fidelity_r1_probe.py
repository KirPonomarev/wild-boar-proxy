# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.model_intelligence_and_speed_metadata_fidelity_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "model_intelligence_and_speed_metadata_fidelity_r1_probe.py"


class ModelIntelligenceAndSpeedMetadataFidelityR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_metadata_truth_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(temp_dir))

        native = packets["native_lane_metadata_fidelity_packet.json"]
        self.assertEqual(native["status"], "ok")
        self.assertEqual(native["lane"], "codex_native")
        self.assertGreater(native["model_count"], 0)
        self.assertEqual(native["source_classification"], "current_build_catalog_visible_only")
        self.assertTrue(native["visible_native_label_preserved_narrowly"])
        self.assertTrue(native["all_native_tiers_unavailable_unknown"])
        self.assertEqual(native["native_metadata_truth_strength"], "unknown_unproven_only")
        self.assertFalse(native["native_label_internal_ranking_semantics_proven"])
        self.assertFalse(native["native_metadata_is_capability_proof"])
        self.assertFalse(native["native_metadata_is_benchmark_ranking"])
        self.assertTrue(all(row["source"] for row in native["native_intelligence_metadata_rows"]))
        self.assertTrue(all(row["proof_level"] for row in native["native_speed_metadata_rows"]))

        api = packets["api_lane_metadata_fidelity_packet.json"]
        self.assertEqual(api["status"], "ok")
        self.assertEqual(api["lane"], "wbp_api")
        self.assertGreater(api["model_count"], 0)
        self.assertTrue(api["wbp_prefixed_non_impersonating_display"])
        self.assertFalse(api["all_api_tiers_unavailable_unknown"])
        self.assertEqual(api["api_metadata_truth_strength"], "mixed_or_stronger")
        self.assertFalse(api["provider_declared_intelligence_parity_proven"])
        self.assertFalse(api["provider_declared_speed_superiority_proven"])
        self.assertFalse(api["api_label_equals_codex_high_or_extra_high"])
        self.assertFalse(api["api_metadata_is_capability_proof"])
        self.assertTrue(all(row["source"] for row in api["api_intelligence_metadata_rows"]))
        self.assertTrue(all(row["proof_level"] for row in api["api_speed_metadata_rows"]))

        source_proof = packets["metadata_source_and_proof_level_packet.json"]
        self.assertEqual(source_proof["status"], "ok")
        self.assertTrue(source_proof["source_and_proof_complete"])
        self.assertFalse(source_proof["measured_source_rows_present"])
        self.assertTrue(source_proof["selector_metadata_is_display_only"])
        self.assertFalse(source_proof["all_current_rows_unavailable_unknown"])
        self.assertFalse(source_proof["display_rows_unavailable_unknown"])
        self.assertFalse(source_proof["selector_rows_unavailable_unknown"])
        self.assertFalse(source_proof["metadata_completeness_without_stronger_truth"])
        self.assertFalse(source_proof["ui_badge_is_packet_proof"])
        self.assertTrue(all(row["source"] for row in source_proof["catalog_display_rows"]))
        self.assertTrue(all(row["proof_level"] for row in source_proof["selector_rows"]))

        non_claims = packets["intelligence_parity_non_claims_packet.json"]
        self.assertFalse(non_claims["provider_declared_intelligence_equals_measured_intelligence"])
        self.assertFalse(non_claims["api_label_equals_codex_high_or_extra_high"])
        self.assertFalse(non_claims["label_coexistence_implies_comparability"])
        self.assertFalse(non_claims["preserved_native_label_proves_internal_ranking_semantics"])
        self.assertFalse(non_claims["metadata_badge_proves_underlying_capability"])

        speed = packets["speed_metadata_boundary_packet.json"]
        self.assertEqual(speed["status"], "ok")
        self.assertFalse(speed["measured_speed_rows_present"])
        self.assertFalse(speed["speed_metadata_reopens_acceleration_proof"])
        self.assertFalse(speed["measured_speed_implies_intelligence"])
        self.assertEqual(speed["speed_metadata_scope_classification"], "catalog_and_selector_metadata_only")
        self.assertFalse(speed["unknown_speed_tiers_present"])
        self.assertTrue(speed["all_current_speed_rows_unavailable_unknown"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["api_lane_receives_codex_native_parity_wording"])
        self.assertFalse(false_green["label_source_hidden"])
        self.assertFalse(false_green["proof_level_absent_or_inflated"])
        self.assertFalse(false_green["measured_speed_treated_as_intelligence"])
        self.assertFalse(false_green["provider_declared_label_treated_as_proven_quality"])
        self.assertFalse(false_green["ui_badge_treated_as_proof"])
        self.assertFalse(false_green["unknown_unproven_rows_treated_as_strong_metadata"])
        self.assertFalse(false_green["historical_item_0_treated_as_closed_here"])

        gap_ids = {gap["id"] for gap in packets["metadata_gap_matrix.json"]["gaps"]}
        self.assertIn("native_visible_labels_do_not_prove_internal_ranking_semantics", gap_ids)
        self.assertIn("api_lane_intelligence_parity_with_codex_high_not_proven", gap_ids)
        self.assertIn("speed_metadata_remains_unmeasured_catalog_truth_only", gap_ids)
        self.assertIn("current_metadata_rows_remain_unknown_unproven_not_strengthened", gap_ids)
        self.assertIn("metadata_fidelity_does_not_close_historical_item_0", gap_ids)

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
                "catalog_models_carry_intelligence_and_speed_source_and_proof_level_fields",
                finding_ids,
            )
            self.assertIn(
                "selector_entries_preserve_metadata_but_remain_selection_intent_only",
                finding_ids,
            )
            self.assertIn(
                "wbp_api_display_surface_remains_non_impersonating_and_non_parity",
                finding_ids,
            )
            self.assertIn(
                "api_lane_parity_with_codex_high_or_extra_high_remains_unproven",
                finding_ids,
            )
            self.assertIn(
                "speed_metadata_remains_catalog_truth_only_not_measured_speed_proof",
                finding_ids,
            )
            self.assertIn(
                "current_metadata_rows_remain_unknown_unproven_even_when_source_and_proof_fields_exist",
                finding_ids,
            )


if __name__ == "__main__":
    unittest.main()
