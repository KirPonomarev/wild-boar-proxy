# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.historical_item_0_reconciliation_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "historical_item_0_reconciliation_r1_probe.py"


class HistoricalItem0ReconciliationR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_historical_seed_separate_from_current_runtime_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(tmpdir) / "evidence")

        current_inventory = packets["current_truth_inventory_packet.json"]
        self.assertEqual(current_inventory["status"], "ok")
        self.assertTrue(current_inventory["inventory_listing_does_not_create_proof"])
        self.assertEqual(
            current_inventory["evidence_precedence"],
            "packet_backed_current_contour_truth_only",
        )
        current_ids = {row["id"] for row in current_inventory["rows"]}
        self.assertIn("generic_model_registry", current_ids)
        self.assertIn("final_dual_lane_acceptance", current_ids)

        historical_inventory = packets["historical_seed_inventory_packet.json"]
        self.assertEqual(historical_inventory["status"], "ok")
        historical_ids = {row["id"] for row in historical_inventory["rows"]}
        self.assertIn("external_lab_model_registry_seed", historical_ids)
        self.assertIn("external_lab_tests", historical_ids)
        seed_row = next(
            row for row in historical_inventory["rows"] if row["id"] == "external_lab_model_registry_seed"
        )
        self.assertGreaterEqual(seed_row["entry_count"], 1)
        self.assertFalse(seed_row["current_runtime_proof"])

        reconciliation = packets["reconfirmed_vs_superseded_matrix.json"]
        self.assertEqual(reconciliation["status"], "ok")
        self.assertTrue(reconciliation["historical_item_0_pre_reconciliation_open"])
        row_index = {row["id"]: row for row in reconciliation["rows"]}
        self.assertEqual(
            row_index["historical_model_seed_inventory_is_active_runtime_catalog"]["classification"],
            "superseded_by_current_packets",
        )
        self.assertEqual(
            row_index["historical_seed_models_are_selectable_current_runtime_choices"]["classification"],
            "superseded_by_current_packets",
        )
        self.assertEqual(
            row_index["isolated_external_lab_non_integrated_lane_claim"]["classification"],
            "historical_only_non_counted",
        )
        self.assertEqual(
            row_index["provider_live_free_unittest_first_external_lab_acceptance"]["classification"],
            "historical_only_non_counted",
        )
        self.assertEqual(
            row_index["historical_artifacts_are_not_canonical_runtime_proof"]["classification"],
            "reconfirmed_by_current_packets",
        )
        self.assertEqual(
            row_index["external_lab_tests_prove_import_hygiene_not_runtime_integration"]["classification"],
            "historical_only_non_counted",
        )
        for row in reconciliation["rows"]:
            self.assertEqual(row["counting_status"], "non_counted")

        counting = packets["historical_item0_counting_boundary_packet.json"]
        self.assertEqual(counting["status"], "ok")
        self.assertEqual(
            counting["final_status"],
            "HISTORICAL_ITEM_0_RECONCILIATION_CLASSIFIED_AND_CLOSED",
        )
        self.assertTrue(counting["historical_item0_reconciliation_closed"])
        self.assertFalse(counting["inventory_enumeration_counts_as_runtime_proof"])
        self.assertFalse(counting["closeout_prose_counts_as_runtime_proof"])
        self.assertFalse(counting["historical_seed_counts_as_current_runtime_truth"])
        self.assertFalse(counting["superseded_rows_remain_active_proof"])
        self.assertTrue(counting["current_packet_truth_only_counts_for_runtime"])
        self.assertTrue(counting["item0_closed_as_reconciliation_only"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["inventory_table_treated_as_fresh_runtime_validation"])
        self.assertFalse(false_green["closeout_narrative_outranks_packet_evidence"])
        self.assertFalse(false_green["historical_rows_marked_reconfirmed_without_packet_support"])
        self.assertFalse(false_green["superseded_rows_treated_as_current_runtime_proof"])
        self.assertFalse(false_green["historical_seed_material_treated_as_fresh_reproof"])

        audit = packets["independent_audit_packet.json"]
        self.assertEqual(audit["status"], "ok")
        finding_ids = {finding["id"] for finding in audit["findings"]}
        self.assertIn("historical_seed_registry_is_not_current_runtime_catalog", finding_ids)
        self.assertIn("seed_only_models_remain_non_selectable_current_runtime_choices", finding_ids)
        self.assertIn(
            "isolated_external_lab_acceptance_docs_remain_historical_only_non_counted",
            finding_ids,
        )
        self.assertIn("historical_item0_closed_as_reconciliation_not_runtime_upgrade", finding_ids)

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
            self.assertEqual(summary["packet_count"], 6)

            counting = json.loads(
                (evidence_dir / "historical_item0_counting_boundary_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                counting["final_status"],
                "HISTORICAL_ITEM_0_RECONCILIATION_CLASSIFIED_AND_CLOSED",
            )


if __name__ == "__main__":
    unittest.main()
