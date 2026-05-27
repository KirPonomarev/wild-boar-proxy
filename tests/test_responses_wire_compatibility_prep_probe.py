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

        summary = packets["responses_wire_prep_summary_packet.json"]
        contract = packets["responses_wire_contract_packet.json"]
        readiness = packets["responses_live_readiness_gate_packet.json"]

        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_master_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_master_target_closed"])
        self.assertFalse(contract["closes_parent_master_target"])
        self.assertFalse(readiness["live_execution_allowed_by_this_contour"])
        self.assertFalse(readiness["may_start_future_live_contour"])

    def test_prep_packets_keep_fixture_wire_live_native_layers_separate(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_prep_packets(REPO_ROOT, Path(tmp))

        contract = packets["responses_wire_contract_packet.json"]
        false_green = packets["responses_wire_false_green_audit.json"]
        stream = packets["responses_stream_fixture_packet.json"]
        tool_loop = packets["responses_tool_loop_fixture_packet.json"]
        failures = packets["responses_failure_semantics_fixture_packet.json"]
        summary = packets["responses_wire_prep_summary_packet.json"]

        self.assertTrue(contract["fixture_truth_present"])
        self.assertTrue(contract["wire_shape_truth_present"])
        self.assertFalse(contract["live_truth_present"])
        self.assertFalse(contract["native_acceptance_truth_present"])
        self.assertFalse(stream["live_stream_compatibility_proven"])
        self.assertFalse(stream["stream_started_counts_as_compatible"])
        self.assertFalse(tool_loop["tool_call_emitted_counts_as_tool_loop"])
        self.assertFalse(tool_loop["live_tool_loop_compatibility_proven"])
        self.assertTrue(failures["local_error_semantics_not_upstream_provider_failure_semantics"])
        self.assertFalse(failures["upstream_provider_failure_semantics_proven"])
        self.assertTrue(failures["empty_input_error_ok"])
        self.assertTrue(summary["transform_profile_fixture_ok"])
        self.assertEqual(false_green["status"], "ok")
        self.assertFalse(false_green["fixture_compatibility_claimed_as_live"])
        self.assertFalse(false_green["model_availability_inferred_from_fixture"])


if __name__ == "__main__":
    unittest.main()
