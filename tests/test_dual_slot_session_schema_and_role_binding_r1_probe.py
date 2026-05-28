# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.dual_slot_session_schema_and_role_binding_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "dual_slot_session_schema_and_role_binding_r1_probe.py"


class DualSlotSessionSchemaAndRoleBindingR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_binding_truth_separate_from_runtime_truth(self) -> None:
        packets = build_packets()

        schema = packets["dual_slot_session_schema_packet.json"]
        self.assertEqual(schema["status"], "ok")
        self.assertEqual(schema["session_schema_version"], 2)
        self.assertEqual(schema["role_slot_binding_count"], 2)
        self.assertFalse(schema["single_model_truth_remaining"])

        binding = packets["role_slot_binding_packet.json"]
        self.assertTrue(binding["role_slot_binding_present"])
        self.assertFalse(binding["runtime_execution_truth_closed_here"])
        self.assertTrue(binding["primary_slot_bound"])
        self.assertTrue(binding["coding_agent_slot_bound"])

        current_path = packets["current_execution_path_separation_packet.json"]
        self.assertEqual(current_path["current_execution_slot_id"], "primary_model_slot")
        self.assertEqual(current_path["current_execution_path_model_id"], "gpt-5.3-codex")
        self.assertTrue(current_path["coding_agent_bound_not_dispatched"])
        self.assertFalse(current_path["slot_binding_implies_runtime_dispatch"])

    def test_build_packets_capture_authority_boundary_and_safe_migration(self) -> None:
        packets = build_packets()

        boundary = packets["session_slot_authority_boundary_packet.json"]
        self.assertTrue(boundary["authority_boundary_held"])
        self.assertFalse(boundary["browser_can_supply_provider"])
        self.assertFalse(boundary["browser_can_supply_route_id"])
        self.assertFalse(boundary["browser_can_supply_account_id"])

        migration = packets["single_to_multi_slot_migration_packet.json"]
        self.assertTrue(migration["legacy_single_model_migrated"])
        self.assertEqual(migration["migration_status"], "legacy_single_model_migrated")
        self.assertEqual(migration["primary_slot_model_id"], "gpt-5.3-codex")
        self.assertFalse(migration["coding_agent_slot_fabricated"])
        self.assertFalse(migration["history_loss_claimed"])

    def test_probe_writes_expected_packets(self) -> None:
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

            non_claims = json.loads(
                (evidence_dir / "session_slot_non_claims_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(non_claims["simultaneous_execution_proven"])
            self.assertFalse(non_claims["coding_agent_dispatch_proven"])
            self.assertFalse(non_claims["runtime_honors_slot_binding_proven"])

            gaps = json.loads(
                (evidence_dir / "session_slot_gap_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            gap_ids = {gap["id"] for gap in gaps["gaps"]}
            self.assertIn("simultaneous_chatgpt_api_execution_not_closed_here", gap_ids)
            self.assertIn("runtime_dispatch_truth_not_closed_here", gap_ids)

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn("role_slot_binding_is_packet_backed_session_truth", finding_ids)
            self.assertIn("simultaneous_execution_and_dispatch_truth_remain_open", finding_ids)
