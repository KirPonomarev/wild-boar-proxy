# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.model_catalog_fidelity_prep_probe import (
    AVAILABILITY_STATUS,
    PARENT_STATUS,
    TARGET_STATUS,
    build_prep_packets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ModelCatalogFidelityPrepProbeTests(unittest.TestCase):
    def test_prep_summary_does_not_close_parent_or_availability_targets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        summary = packets["catalog_fidelity_prep_summary_packet.json"]
        schema = packets["model_registry_schema_packet.json"]
        false_green = packets["model_catalog_fidelity_false_green_audit.json"]

        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_master_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_master_target_closed"])
        self.assertEqual(summary["model_availability_target"], AVAILABILITY_STATUS)
        self.assertFalse(summary["model_availability_target_closed"])
        self.assertFalse(schema["closes_parent_master_target"])
        self.assertFalse(false_green["full_catalog_fidelity_claimed"])
        self.assertFalse(false_green["model_availability_claimed"])

    def test_catalog_source_and_non_impersonation_packets_are_strict(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        source = packets["codex_native_catalog_source_packet.json"]
        non_impersonation = packets["wbp_api_non_impersonation_packet.json"]
        alias = packets["alias_authority_boundary_packet.json"]
        false_green = packets["model_catalog_fidelity_false_green_audit.json"]

        self.assertEqual(source["status"], "ok")
        self.assertTrue(source["source_rows"])
        self.assertFalse(source["inferred_fixture_displayed_as_current_build_truth"])
        self.assertFalse(source["pinned_entries_claimed_as_currently_available"])
        self.assertEqual(non_impersonation["status"], "ok")
        for model in non_impersonation["models"]:
            self.assertTrue(model["display_name"].lower().startswith(("wbp ", "wbp:")))
            self.assertTrue(model["provider_model_id"])
        self.assertEqual(alias["status"], "ok")
        self.assertFalse(alias["alias_selected_is_route_proof"])
        self.assertFalse(alias["client_can_inject_alias_provider_account_authority"])
        self.assertFalse(false_green["lane_presence_hardcoded_without_model_cross_check"])
        self.assertFalse(false_green["lane_integrity"]["lanes_mixed"])

    def test_prep_packets_keep_display_runtime_capability_and_availability_separate(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        display = packets["model_display_metadata_packet.json"]
        runtime = packets["runtime_truth_packet.json"]
        capability = packets["capability_claims_packet.json"]
        metadata = packets["metadata_source_proof_level_packet.json"]
        summary = packets["catalog_fidelity_prep_summary_packet.json"]

        self.assertFalse(display["display_metadata_is_runtime_truth"])
        self.assertFalse(runtime["display_metadata_becomes_runtime_truth"])
        self.assertFalse(runtime["model_availability_proven"])
        self.assertFalse(capability["runtime_truth_boundary_is_capability_proof"])
        self.assertEqual(metadata["status"], "ok")
        for row in metadata["rows"]:
            self.assertTrue(row["source"])
            self.assertTrue(row["proof_level"])
            self.assertFalse(row["treated_as_live_proof"])
        self.assertFalse(summary["model_availability_proven"])
        self.assertFalse(summary["provider_compatibility_proven"])


if __name__ == "__main__":
    unittest.main()
