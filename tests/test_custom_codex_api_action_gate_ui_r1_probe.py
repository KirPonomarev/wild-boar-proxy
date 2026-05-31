# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_api_action_gate_ui_r1_probe import FINAL_STATUS, build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "custom_codex_api_action_gate_ui_r1_probe.py"


class CustomCodexApiActionGateUiR1ProbeTests(unittest.TestCase):
    def test_build_packets_blocks_without_owner_live_auth(self) -> None:
        packets = build_packets()
        gate = packets["custom_codex_api_action_gate_packet.json"]
        summary = packets["summary_packet.json"]
        choice = packets["manual_api_choice_packet.json"]
        boundary = packets["live_provider_request_boundary_packet.json"]
        validation = packets["validation_packet.json"]

        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(gate["final_status"], FINAL_STATUS)
        self.assertEqual(summary["status"], "blocked")
        self.assertFalse(summary["live_provider_request_allowed"])
        self.assertFalse(summary["live_request_attempted"])
        self.assertFalse(summary["upstream_response_observed"])
        self.assertTrue(choice["selection_intent_only"])
        self.assertFalse(choice["execution_proven"])
        self.assertFalse(choice["provider_response_observed"])
        self.assertFalse(choice["route_snapshot_counted_as_provider_response"])
        self.assertFalse(boundary["live_call_attempted"])
        self.assertFalse(boundary["paid_route_used"])
        self.assertFalse(boundary["fallback_attempted"])
        self.assertFalse(boundary["parallel_fanout_attempted"])
        self.assertFalse(boundary["original_codex_touched"])
        self.assertFalse(boundary["raw_secret_recorded"])
        self.assertFalse(boundary["secret_value_recorded"])
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["violation_count"], 0)

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
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
            self.assertEqual(summary["final_status"], FINAL_STATUS)
            written = json.loads(
                (evidence_dir / "summary_packet.json").read_text(encoding="utf-8")
            )
            self.assertEqual(written["final_status"], FINAL_STATUS)


if __name__ == "__main__":
    unittest.main()
