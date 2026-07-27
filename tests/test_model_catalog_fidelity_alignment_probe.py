# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.model_catalog_fidelity_alignment_probe import (
    EXTERNAL_ROUTE_ID,
    TARGET_STATUS,
    build_alignment_packets,
    corrected_operator_status,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ModelCatalogFidelityAlignmentProbeTests(unittest.TestCase):
    def test_alignment_probe_packets_reflect_corrected_truth_set(self) -> None:
        packets = build_alignment_packets()

        catalog = packets["catalog_inventory_packet.json"]
        lattice = packets["availability_lattice_packet.json"]
        smoke = packets["bounded_smoke_examples_packet.json"]
        false_green = packets["false_green_audit.json"]

        self.assertEqual(catalog["status"], "degraded")
        self.assertTrue(catalog["availability_lattice_imported"])
        self.assertEqual(catalog["default_model"], "gpt-5.5")
        self.assertEqual(catalog["availability_lattice_status"], "ok")
        rows = {row["model_id"]: row for row in lattice["rows"]}
        self.assertEqual(
            rows["gpt-5.5"]["availability_claim_level"],
            "direct_wbp_non_stream_response_accepted",
        )
        self.assertEqual(
            rows[EXTERNAL_ROUTE_ID]["availability_claim_level"],
            "historically_direct_wbp_non_stream_response_accepted",
        )
        self.assertEqual(smoke["target_status"], TARGET_STATUS)
        self.assertTrue(smoke["spark_absent_from_current_operator_model_list"])
        self.assertEqual(smoke["out_of_catalog_negative_examples"][0]["model_id"], "gpt-5.5-spark")
        self.assertEqual(false_green["status"], "ok")
        self.assertFalse(false_green["all_models_work_claimed"])

    def test_alignment_probe_emits_required_packet_names(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results"):
            packets = build_alignment_packets()

        self.assertEqual(
            sorted(packets),
            [
                "availability_lattice_packet.json",
                "bounded_smoke_examples_packet.json",
                "catalog_inventory_packet.json",
                "false_green_audit.json",
                "lane_truth_mapping_packet.json",
                "model_label_alignment_packet.json",
            ],
        )
        self.assertEqual(corrected_operator_status()["claim_gate"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
