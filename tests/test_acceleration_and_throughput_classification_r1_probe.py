# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.acceleration_and_throughput_classification_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "acceleration_and_throughput_classification_r1_probe.py"


class AccelerationAndThroughputClassificationR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_measurement_truth_separate_from_acceleration_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(repo_root=ROOT, evidence_dir=evidence_dir)

        latency = packets["latency_classification_packet.json"]
        self.assertEqual(latency["status"], "ok")
        self.assertEqual(
            latency["measurement_source_classification"],
            "bounded_contour_local_runner_harness_only",
        )
        self.assertTrue(latency["packet_latency_surface_present"])
        self.assertTrue(latency["wall_clock_surface_present"])
        self.assertFalse(latency["live_stack_acceleration_proven"])
        self.assertFalse(latency["user_visible_productivity_gain_proven"])
        self.assertGreaterEqual(len(latency["chatgpt_lane_packet_latency_ms"]), 2)
        self.assertGreaterEqual(len(latency["api_lane_packet_latency_ms"]), 2)

        throughput = packets["throughput_classification_packet.json"]
        self.assertEqual(throughput["status"], "ok")
        self.assertTrue(throughput["sequential_only"])
        self.assertTrue(throughput["concurrency_guard_required"])
        self.assertEqual(throughput["run_count_total"], 5)
        self.assertEqual(throughput["run_count_successful"], 4)
        self.assertEqual(throughput["run_count_failed"], 1)
        self.assertFalse(throughput["concurrent_throughput_proven"])
        self.assertFalse(throughput["throughput_implies_cost_efficiency"])

        comparison = packets["lane_measurement_comparison_packet.json"]
        self.assertTrue(comparison["chatgpt_lane_measured"])
        self.assertTrue(comparison["api_lane_measured"])
        self.assertTrue(comparison["same_harness_conditions"])
        self.assertTrue(comparison["same_guard_conditions"])
        self.assertFalse(comparison["same_execution_path"])
        self.assertFalse(comparison["comparison_admitted"])
        self.assertEqual(comparison["comparison_status"], "limited_or_not_admitted")
        self.assertFalse(comparison["clean_acceleration_ordering_claimed"])

        integrity = packets["measurement_integrity_packet.json"]
        self.assertEqual(integrity["run_count_declared"], 5)
        self.assertTrue(integrity["failed_runs_retained"])
        self.assertIn("ENGINE_PROMPT_FAILED", integrity["failed_run_machine_error_codes"])
        self.assertTrue(integrity["transcript_preserves_failed_or_blocked_events"])
        self.assertTrue(integrity["packet_latency_comes_from_runner_reported_duration"])
        self.assertTrue(integrity["operator_surface_wall_clock_duration_present"])
        self.assertTrue(integrity["cli_runner_wall_clock_duration_present"])
        self.assertTrue(integrity["mixed_timing_surfaces_detected"])
        self.assertFalse(integrity["cross_surface_comparison_currently_admitted"])

        non_claims = packets["acceleration_non_claims_packet.json"]
        self.assertFalse(non_claims["measured_latency_implies_better_answers"])
        self.assertFalse(non_claims["measured_latency_implies_user_visible_productivity_gain"])
        self.assertFalse(non_claims["sequential_throughput_implies_safe_parallel_throughput"])
        self.assertFalse(non_claims["throughput_implies_cost_efficiency"])

        gaps = packets["acceleration_gap_matrix.json"]
        gap_ids = {gap["id"] for gap in gaps["gaps"]}
        self.assertIn("live_stack_acceleration_not_proven_beyond_contour_local_harness", gap_ids)
        self.assertIn("mixed_timing_surfaces_block_clean_cross_surface_comparison", gap_ids)
        self.assertIn("concurrent_throughput_remains_unproven_here", gap_ids)

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["current_only_measurements_treated_as_comparative_speedup"])
        self.assertFalse(false_green["failed_or_slow_runs_dropped_from_evidence"])
        self.assertFalse(false_green["sequential_throughput_treated_as_concurrency_readiness"])
        self.assertFalse(false_green["speed_treated_as_quality_or_reasoning_gain"])
        self.assertFalse(false_green["timing_treated_as_cost_efficiency_proof"])

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

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["status"], "ok")
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn(
                "timing_surface_exists_in_custom_session_packets_and_wall_clock_helpers",
                finding_ids,
            )
            self.assertIn(
                "failed_runs_are_retained_in_measurement_packets_and_transcript",
                finding_ids,
            )
            self.assertIn(
                "clean_acceleration_comparison_remains_not_admitted_under_mixed_timing_surfaces",
                finding_ids,
            )


if __name__ == "__main__":
    unittest.main()
