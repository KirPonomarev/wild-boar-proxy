# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.responses_streaming_tools_failure_semantics_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "responses_streaming_tools_failure_semantics_r1_probe.py"


class ResponsesStreamingToolsFailureSemanticsR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_adapter_semantics_separate_from_consumer_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(repo_root=ROOT, evidence_dir=evidence_dir)

        responses = packets["responses_semantics_packet.json"]
        self.assertEqual(responses["status"], "ok")
        self.assertTrue(responses["chatgpt_plain_response_consumer_accepted"])
        self.assertTrue(responses["api_plain_response_consumer_accepted"])
        self.assertTrue(responses["text_only_semantics_proven"])
        self.assertFalse(responses["structured_semantics_proven"])

        streaming = packets["streaming_semantics_packet.json"]
        self.assertEqual(streaming["status"], "ok")
        self.assertTrue(streaming["adapter_stream_transport_observed"])
        self.assertFalse(streaming["upstream_request_stream_flag_true"])
        self.assertTrue(streaming["adapter_generated_sse_only"])
        self.assertFalse(streaming["consumer_streaming_observed"])
        self.assertFalse(streaming["consumer_streaming_accepted"])
        self.assertIn("response.output_text.delta", streaming["stream_event_names"])

        tools = packets["tool_call_semantics_packet.json"]
        self.assertEqual(tools["status"], "ok")
        self.assertTrue(tools["adapter_tool_call_shape_observed"])
        self.assertTrue(tools["adapter_tool_output_shape_observed"])
        self.assertTrue(tools["adapter_function_tool_request_admitted"])
        self.assertTrue(tools["upstream_tool_declaration_forwarded"])
        self.assertFalse(tools["model_driven_function_tool_protocol_supported"])
        self.assertTrue(tools["unsupported_tool_type_rejected"])
        self.assertFalse(tools["consumer_tool_execution_proven"])
        self.assertFalse(tools["consumer_tool_semantics_accepted"])

        consumer = packets["consumer_acceptance_boundary_packet.json"]
        self.assertEqual(consumer["status"], "ok")
        self.assertTrue(consumer["plain_text_consumer_accepted"])
        self.assertFalse(consumer["streaming_consumer_accepted"])
        self.assertFalse(consumer["tool_semantics_consumer_accepted"])
        self.assertTrue(consumer["adapter_can_shape_more_than_consumer_accepts"])

    def test_probe_writes_required_packets_and_failure_boundaries(self) -> None:
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
            self.assertEqual(summary["packet_count"], 9)

            failures = json.loads(
                (evidence_dir / "failure_semantics_packet.json").read_text(encoding="utf-8")
            )
            self.assertEqual(failures["unsupported_tool_type_status_code"], 400)
            self.assertEqual(failures["unsupported_tool_type_code"], "unsupported_tool_type")
            self.assertEqual(failures["invalid_upstream_response_status_code"], 502)
            self.assertEqual(failures["invalid_upstream_response_code"], "invalid_upstream_response")
            self.assertEqual(failures["prompt_runner_exception_status"], "failed")
            self.assertEqual(failures["prompt_runner_exception_code"], "PROMPT_RUNNER_EXCEPTION")
            self.assertFalse(failures["silent_lane_substitution_detected"])

            non_claims = json.loads(
                (evidence_dir / "protocol_non_claims_packet.json").read_text(encoding="utf-8")
            )
            self.assertFalse(non_claims["streaming_production_ready"])
            self.assertFalse(non_claims["tool_support_complete"])
            self.assertFalse(non_claims["model_driven_function_tool_protocol_proven"])
            self.assertFalse(non_claims["adapter_normalized_success_equals_upstream_native_compatibility"])

            gaps = json.loads(
                (evidence_dir / "protocol_gap_matrix.json").read_text(encoding="utf-8")
            )
            gap_ids = {gap["id"] for gap in gaps["gaps"]}
            self.assertIn("consumer_streaming_not_proven_here", gap_ids)
            self.assertIn("consumer_tool_execution_not_proven_here", gap_ids)
            self.assertIn("upstream_native_streaming_blocked_by_current_adapter", gap_ids)
            self.assertIn(
                "model_driven_function_tool_protocol_not_supported_by_current_adapter", gap_ids
            )

            false_green = json.loads(
                (evidence_dir / "false_green_boundary_packet.json").read_text(encoding="utf-8")
            )
            self.assertFalse(false_green["adapter_sse_treated_as_upstream_streaming"])
            self.assertFalse(false_green["adapter_tool_shape_treated_as_consumer_tool_execution"])
            self.assertFalse(
                false_green["adapter_function_tool_admission_treated_as_model_driven_tool_support"]
            )
            self.assertFalse(false_green["text_success_treated_as_structured_semantics"])


if __name__ == "__main__":
    unittest.main()
