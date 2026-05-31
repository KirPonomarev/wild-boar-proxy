# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.api_provider_compatibility_and_smoke_matrix_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "api_provider_compatibility_and_smoke_matrix_r1_probe.py"


class ApiProviderCompatibilityAndSmokeMatrixR1ProbeTests(unittest.TestCase):
    def test_build_packets_classify_exact_current_rows_without_family_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(repo_root=ROOT, evidence_dir=evidence_dir)

        matrix = packets["provider_smoke_matrix_packet.json"]
        self.assertEqual(matrix["status"], "ok")
        self.assertEqual(matrix["actual_row_count"], 4)
        self.assertTrue(matrix["narrower_than_target_honestly_recorded"])
        self.assertFalse(matrix["live_provider_calls_attempted"])
        self.assertFalse(matrix["upstream_provider_acceptance_proven"])
        self.assertTrue(matrix["session_runtime_harness_only"])
        self.assertFalse(matrix["provider_family_compatibility_claimed"])
        self.assertFalse(matrix["streaming_compatibility_claimed"])
        self.assertFalse(matrix["tool_compatibility_claimed"])

        rows = {
            row["model_id"]: row
            for row in packets["provider_smoke_row_results.json"]["rows"]
        }
        self.assertEqual(rows["wbp:deepseek-max"]["row_result"], "pass_with_limits")
        self.assertEqual(rows["native-looking-external"]["row_result"], "pass_with_limits")
        self.assertEqual(
            rows["wbp:deepseek-max"]["row_pass_basis"],
            "bounded_session_runtime_harness_plain_response_only",
        )
        self.assertFalse(rows["wbp:deepseek-max"]["live_provider_call_attempted"])
        self.assertFalse(rows["wbp:deepseek-max"]["upstream_provider_acceptance_proven"])
        self.assertEqual(
            rows["direct-mistral-devstral-2512"]["row_result"],
            "blocked_by_runtime_path",
        )
        self.assertEqual(
            rows["direct-mistral-devstral-2512"]["failure_category"],
            "catalog_runtime_route_visibility_mismatch",
        )
        self.assertEqual(rows["wbp-disabled-route"]["row_result"], "blocked_by_runtime_path")
        self.assertEqual(
            rows["wbp-disabled-route"]["failure_category"],
            "route_disabled_or_not_selectable",
        )

        inherited = rows["wbp:deepseek-max"]["semantic_limits_inherited"]
        self.assertTrue(inherited["plain_text_only"])
        self.assertEqual(
            inherited["streaming_classification"],
            "current_adapter_sse_only_with_limits",
        )
        self.assertFalse(inherited["model_driven_function_tool_protocol_supported"])
        self.assertFalse(inherited["consumer_streaming_accepted"])
        self.assertFalse(inherited["consumer_tool_semantics_accepted"])

        gaps = packets["provider_gap_matrix.json"]
        gap_ids = {gap["id"] for gap in gaps["gaps"]}
        self.assertIn("current_server_issued_api_row_count_below_target_matrix_size", gap_ids)
        self.assertIn("catalog_runtime_route_visibility_mismatch_for_direct_external_row", gap_ids)
        self.assertIn("live_provider_row_smoke_not_attempted_here", gap_ids)

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["row_pass_treated_as_provider_family_support"])
        self.assertFalse(false_green["text_only_smoke_treated_as_streaming_or_tools_compatibility"])
        self.assertFalse(false_green["synthetic_harness_pass_treated_as_live_provider_compatibility"])
        self.assertFalse(false_green["semantic_limits_dropped_from_passing_rows"])

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
            self.assertEqual(summary["packet_count"], 8)
            self.assertFalse((evidence_dir / "probe_session_root").exists())

            failure_taxonomy = json.loads(
                (evidence_dir / "provider_failure_taxonomy_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            categories = {
                row["category"] for row in failure_taxonomy["observed_failure_categories"]
            }
            self.assertIn("catalog_runtime_route_visibility_mismatch", categories)
            self.assertIn("route_disabled_or_not_selectable", categories)
            self.assertFalse(failure_taxonomy["silent_substitution_detected"])
            self.assertFalse(failure_taxonomy["fallback_policy_settled_here"])

            semantic_limits = json.loads(
                (evidence_dir / "provider_semantic_limits_inheritance_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                semantic_limits["streaming_classification_inherited"],
                "current_adapter_sse_only_with_limits",
            )
            self.assertFalse(semantic_limits["model_driven_function_tool_protocol_supported"])
            self.assertFalse(semantic_limits["semantic_limits_dropped_from_passing_rows"])

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(audit["status"], "ok")
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn("live_provider_acceptance_remains_unproven_here", finding_ids)
            self.assertIn("direct_external_catalog_row_blocks_on_current_route_visibility", finding_ids)


if __name__ == "__main__":
    unittest.main()
