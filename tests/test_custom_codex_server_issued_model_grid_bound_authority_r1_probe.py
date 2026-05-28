# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_server_issued_model_grid_bound_authority_r1_probe import (
    TARGET_STATUS,
    build_false_green_audit,
    build_packets,
    build_summary_packet,
    build_sync_gate_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CustomCodexServerIssuedModelGridBoundAuthorityR1ProbeTests(unittest.TestCase):
    def test_sync_gate_skip_git_is_deterministic(self) -> None:
        packet = build_sync_gate_packet(
            REPO_ROOT,
            REPO_ROOT / "audit_results" / "unit-test-model-grid-evidence",
            skip_git=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["git_branch"], "SKIPPED_FOR_TEST")
        self.assertEqual(packet["git_head"], "SKIPPED_FOR_TEST")
        self.assertEqual(packet["git_status_short"], [])
        self.assertEqual(packet["quarantined_dirty_entries"], [])
        self.assertFalse(packet["historical_dirty_quarantined"])

    def test_false_green_audit_blocks_forbidden_true_claims(self) -> None:
        audit = build_false_green_audit(
            {
                "sync_gate_packet.json": {"status": "ok"},
                "model_catalog_contract_packet.json": {
                    "status": "ok",
                    "provider_reachability_proven": True,
                },
                "browser_selection_payload_negative_packet.json": {"status": "ok"},
                "server_selection_binding_packet.json": {"status": "ok"},
                "model_grid_visibility_boundary_packet.json": {"status": "ok"},
                "availability_claim_boundary_packet.json": {"status": "ok"},
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "model_catalog_contract_packet.json.provider_reachability_proven",
            audit["findings"],
        )

    def test_build_packets_closes_contour_without_route_readiness_claims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(
                repo_root=REPO_ROOT,
                evidence_dir=Path(tmp) / "evidence",
                skip_git=True,
            )

        summary = packets["model_grid_bound_authority_summary_packet.json"]
        independent = packets["independent_model_grid_audit.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["provider_reachability_proven"])
        self.assertFalse(summary["route_readiness_proven"])
        self.assertFalse(summary["all_models_work_claimed"])
        self.assertEqual(independent["status"], "ok")
        self.assertTrue(independent["browser_payload_model_id_only"])
        self.assertTrue(independent["disabled_route_rejected"])

    def test_summary_blocks_missing_independent_audit(self) -> None:
        summary = build_summary_packet(
            {
                "sync_gate_packet.json": {"status": "ok"},
                "model_catalog_contract_packet.json": {"status": "ok"},
                "browser_selection_payload_negative_packet.json": {"status": "ok"},
                "server_selection_binding_packet.json": {"status": "ok"},
                "model_grid_visibility_boundary_packet.json": {"status": "ok"},
                "availability_claim_boundary_packet.json": {"status": "ok"},
                "false_green_audit.json": {"status": "ok"},
            }
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("independent_model_grid_audit.json", summary["missing_required_packets"])


if __name__ == "__main__":
    unittest.main()
