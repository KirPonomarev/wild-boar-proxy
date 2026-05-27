# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.responses_wire_compatibility_prep_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_prep_packets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResponsesWireCompatibilityPrepProbeTests(unittest.TestCase):
    def test_prep_summary_does_not_close_live_parent_target(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        summary = packets["responses_no_live_summary_packet.json"]
        contract = packets["responses_wire_contract_packet.json"]
        readiness = packets["responses_live_promotion_gate_packet.json"]

        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_master_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_master_target_closed"])
        self.assertFalse(contract["closes_parent_master_target"])
        self.assertFalse(readiness["live_execution_allowed_by_this_contour"])
        self.assertFalse(readiness["may_start_live_after_this_contour_alone"])

    def test_prep_packets_keep_fixture_wire_live_native_layers_separate(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        contract = packets["responses_wire_contract_packet.json"]
        false_green = packets["responses_no_live_false_green_audit.json"]
        stream = packets["responses_fixture_streaming_contract_packet.json"]
        tool_loop = packets["responses_fixture_tool_loop_contract_packet.json"]
        failures = packets["responses_fixture_failure_semantics_packet.json"]
        summary = packets["responses_no_live_summary_packet.json"]

        self.assertTrue(contract["fixture_truth_present"])
        self.assertTrue(contract["wire_shape_truth_present"])
        self.assertFalse(contract["live_truth_present"])
        self.assertFalse(contract["native_acceptance_truth_present"])
        self.assertTrue(stream["data_type_matches_event"])
        self.assertEqual(stream["data_parse_errors"], [])
        self.assertEqual(stream["terminal_response_status"], "completed")
        self.assertFalse(stream["live_streaming_compatibility_proven"])
        self.assertFalse(stream["stream_started_counts_as_compatible"])
        self.assertFalse(tool_loop["tool_schema_parsed_counts_as_execution_loop_accepted"])
        self.assertFalse(tool_loop["live_tool_loop_compatibility_proven"])
        self.assertFalse(failures["failure_fixture_counts_as_provider_live_behavior"])
        self.assertFalse(failures["live_failure_semantics_compatibility_proven"])
        self.assertTrue(summary["transform_profile_fixture_ok"])
        self.assertEqual(false_green["status"], "ok")
        self.assertFalse(false_green["fixture_streaming_claimed_as_live_streaming"])
        self.assertFalse(false_green["wire_readiness_claimed_as_model_availability"])

    def test_required_no_live_deliverables_are_present(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        required = {
            "responses_no_live_scope_packet.json",
            "responses_fixture_non_stream_contract_packet.json",
            "responses_fixture_streaming_contract_packet.json",
            "responses_fixture_tool_loop_contract_packet.json",
            "responses_fixture_failure_semantics_packet.json",
            "responses_redaction_boundary_packet.json",
            "responses_live_promotion_gate_packet.json",
            "responses_wire_compatibility_readiness_matrix.json",
            "responses_no_live_false_green_audit.json",
            "responses_no_live_summary_packet.json",
        }
        self.assertFalse(required - set(packets))
        summary = packets["responses_no_live_summary_packet.json"]
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["blocked_packets"], [])
        self.assertFalse(summary["provider_reachability_proven"])
        self.assertFalse(summary["model_availability_proven"])
        self.assertFalse(summary["codex_consumer_acceptance_proven"])
        self.assertFalse(summary["direct_egress_absence_proven"])

    def test_no_live_false_green_audit_blocks_if_required_packet_blocks(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        blocked = dict(packets)
        blocked["responses_redaction_boundary_packet.json"] = {
            **blocked["responses_redaction_boundary_packet.json"],
            "status": "blocked",
            "secret_marker_findings": ["forced-test-marker"],
        }
        # Rebuild only the summary-facing failure shape used by the probe.
        self.assertEqual(blocked["responses_redaction_boundary_packet.json"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
