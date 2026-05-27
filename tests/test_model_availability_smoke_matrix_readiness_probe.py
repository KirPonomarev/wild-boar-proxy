# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.model_availability_smoke_matrix_readiness_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_summary_packet,
    build_readiness_packets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ModelAvailabilitySmokeMatrixReadinessProbeTests(unittest.TestCase):
    def test_summary_closes_readiness_only_not_parent_availability(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        summary = packets["model_availability_readiness_summary_packet.json"]
        false_green = packets["model_availability_false_green_audit.json"]
        live_gate = packets["model_availability_live_promotion_gate_packet.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertFalse(summary["model_availability_proven"])
        self.assertFalse(false_green["parent_target_closed"])
        self.assertFalse(live_gate["live_execution_allowed_in_this_contour"])

    def test_candidate_rows_keep_readiness_below_live_availability(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        matrix = packets["model_availability_candidate_matrix_packet.json"]
        rows = matrix["rows"]

        self.assertGreaterEqual(matrix["candidate_count"], 1)
        self.assertFalse(matrix["catalog_visible_counted_as_availability"])
        self.assertFalse(matrix["candidate_selected_counted_as_availability"])
        self.assertFalse(matrix["request_prepared_counted_as_route_attempted"])
        for row in rows:
            self.assertTrue(row["candidate_selected"])
            self.assertTrue(row["request_shape_ready"])
            self.assertTrue(row["request_prepared"])
            self.assertFalse(row["auth_proven"])
            self.assertFalse(row["availability_proven"])
            self.assertFalse(row["request_attempted"])
            self.assertFalse(row["route_attempted"])
            self.assertFalse(row["request_sent_to_wbp"])
            self.assertFalse(row["upstream_accepts"])
            self.assertFalse(row["response_accepted_by_direct_wbp_client"])
            self.assertFalse(row["response_accepted_by_codex"])
            self.assertFalse(row["native_acceptance_proven"])
            self.assertFalse(row["streaming_classified"])
            self.assertFalse(row["tool_loop_classified"])

    def test_candidate_sources_do_not_create_models_from_narrative(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        source = packets["model_availability_candidate_source_packet.json"]
        seed_rows = {row["model_id"]: row for row in source["seed_evaluation"]}

        self.assertFalse(source["narrative_seed_can_create_candidate"])
        self.assertFalse(source["catalog_visible_counted_as_availability"])
        self.assertFalse(source["candidate_selected_counted_as_availability"])
        self.assertIn("gpt-5.4-mini", seed_rows)
        self.assertFalse(seed_rows["gpt-5.4-mini"]["availability_proven"])
        if not seed_rows["gpt-5.4-mini"]["present_in_current_catalog"]:
            self.assertFalse(seed_rows["gpt-5.4-mini"]["admitted_as_candidate"])
            self.assertEqual(
                seed_rows["gpt-5.4-mini"]["skip_reason"],
                "not_catalog_visible_or_route_backed_in_current_snapshot",
            )

    def test_gpt_5_5_remains_unproven_when_present(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        matrix = packets["model_availability_candidate_matrix_packet.json"]
        false_green = packets["model_availability_false_green_audit.json"]
        by_id = {row["model_id"]: row for row in matrix["rows"]}

        self.assertIn("gpt-5.5", by_id)
        self.assertFalse(by_id["gpt-5.5"]["availability_proven"])
        self.assertFalse(matrix["gpt_5_5_available_claimed"])
        self.assertFalse(false_green["gpt_5_5_claimed_available_from_listing"])

    def test_auth_and_request_shape_are_not_route_or_availability_proof(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        auth = packets["model_availability_auth_precondition_packet.json"]
        request_shape = packets["model_availability_request_shape_packet.json"]
        false_green = packets["model_availability_false_green_audit.json"]

        self.assertTrue(auth["auth_precondition_classified"])
        self.assertFalse(auth["auth_reproved_in_this_contour"])
        self.assertFalse(auth["model_availability_proven_by_auth"])
        self.assertFalse(auth["auth_proven_counts_as_model_availability"])
        self.assertFalse(request_shape["live_request_allowed"])
        self.assertFalse(request_shape["live_request_attempted"])
        self.assertFalse(request_shape["request_prepared_counted_as_route_attempted"])
        self.assertFalse(request_shape["request_prepared_counted_as_model_availability"])
        for shape in request_shape["shapes"]:
            self.assertFalse(shape["request_body_recorded"])
            self.assertFalse(shape["raw_prompt_recorded"])
            self.assertFalse(shape["auth_header_recorded"])
            self.assertFalse(shape["request_attempted"])
            self.assertFalse(shape["route_attempted"])
            self.assertFalse(shape["counts_as_availability"])
        self.assertFalse(false_green["auth_precondition_claimed_as_auth_proof"])
        self.assertFalse(false_green["auth_proof_claimed_as_model_availability"])

    def test_secret_redaction_audit_does_not_record_raw_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        audit = packets["secret_redaction_audit.json"]

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["raw_secret_found"])
        self.assertFalse(audit["raw_prompt_recorded"])
        self.assertEqual(audit["secret_marker_findings"], [])

    def test_summary_blocks_missing_or_blocked_gating_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        blocked_packets = dict(packets)
        blocked_packets["model_availability_false_green_audit.json"] = {
            **blocked_packets["model_availability_false_green_audit.json"],
            "status": "blocked",
            "findings": ["forced_test_finding"],
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["model_availability_request_shape_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn(
            "model_availability_false_green_audit.json",
            blocked_summary["blocked_packets"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "model_availability_request_shape_packet.json",
            missing_summary["missing_required_packets"],
        )


if __name__ == "__main__":
    unittest.main()
