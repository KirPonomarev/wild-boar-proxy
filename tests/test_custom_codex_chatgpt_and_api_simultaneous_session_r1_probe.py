# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_chatgpt_and_api_simultaneous_session_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py"


class CustomCodexChatgptAndApiSimultaneousSessionR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_same_session_truth_separate_from_concurrent_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(repo_root=ROOT, evidence_dir=evidence_dir)

        runtime = packets["simultaneous_session_runtime_packet.json"]
        self.assertEqual(runtime["status"], "ok")
        self.assertTrue(runtime["same_session_identity_proven"])
        self.assertTrue(runtime["same_session_callability_proven"])
        self.assertFalse(runtime["concurrent_execution_observed"])
        self.assertFalse(runtime["simultaneous_dispatch_proven"])
        self.assertEqual(runtime["runner_call_count"], 2)

        chatgpt = packets["chatgpt_lane_runtime_packet.json"]
        self.assertEqual(chatgpt["status"], "ok")
        self.assertEqual(chatgpt["current_execution_slot_id"], "primary_model_slot")
        self.assertEqual(chatgpt["selected_source_provenance"], "backend_proven")
        self.assertEqual(chatgpt["configured_provider"], "cliproxy")
        self.assertFalse(chatgpt["counts_as_api_lane_truth"])

        api_lane = packets["api_lane_runtime_packet.json"]
        self.assertEqual(api_lane["status"], "ok")
        self.assertEqual(api_lane["current_execution_slot_id"], "coding_agent_model_slot")
        self.assertEqual(api_lane["selected_source_provenance"], "route_proven")
        self.assertEqual(api_lane["configured_provider"], "external_route")
        self.assertTrue(api_lane["route_provenance_required"])
        self.assertFalse(api_lane["counts_as_provider_family_compatibility"])

        provenance = packets["dual_lane_source_provenance_packet.json"]
        self.assertEqual(provenance["status"], "ok")
        self.assertEqual(provenance["chatgpt_configured_provider"], "cliproxy")
        self.assertEqual(provenance["api_configured_provider"], "external_route")
        self.assertFalse(provenance["silent_source_collapse_observed"])

        boundary = packets["fallback_and_substitution_boundary_packet.json"]
        self.assertEqual(boundary["status"], "ok")
        self.assertEqual(boundary["chatgpt_runtime_provider"], "cliproxy")
        self.assertEqual(boundary["api_runtime_provider"], "external_route")
        self.assertFalse(boundary["chatgpt_fallback_attempted"])
        self.assertFalse(boundary["api_fallback_attempted"])
        self.assertFalse(boundary["silent_gpt_substitution_for_api_lane"])
        self.assertFalse(boundary["silent_api_substitution_for_chatgpt_lane"])

    def test_probe_writes_required_packets_and_records_gap_boundaries(self) -> None:
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
            self.assertEqual(summary["packet_count"], 10)

            non_claims = json.loads(
                (evidence_dir / "simultaneous_session_non_claims_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(non_claims["concurrent_execution_proven"])
            self.assertFalse(non_claims["provider_family_compatibility_proven"])

            gaps = json.loads(
                (evidence_dir / "simultaneous_session_gap_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            gap_ids = {gap["id"] for gap in gaps["gaps"]}
            self.assertIn("concurrent_execution_not_observed_here", gap_ids)
            self.assertIn("provider_family_compatibility_not_proven_here", gap_ids)

            false_green = json.loads(
                (evidence_dir / "false_green_boundary_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(false_green["same_session_callability_treated_as_concurrent_execution"])
            self.assertFalse(false_green["binding_treated_as_dispatch"])

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn("same_session_dual_lane_callability_is_packet_backed", finding_ids)
            self.assertIn("concurrent_execution_remains_unproven_here", finding_ids)


if __name__ == "__main__":
    unittest.main()
