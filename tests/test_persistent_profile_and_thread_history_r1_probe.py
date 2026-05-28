# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.persistent_profile_and_thread_history_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "persistent_profile_and_thread_history_r1_probe.py"


class PersistentProfileAndThreadHistoryR1ProbeTests(unittest.TestCase):
    def test_build_packets_keep_persistence_history_and_runtime_truth_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(
                repo_root=ROOT,
                evidence_dir=evidence_dir,
                profile_id="wbp-custom-main",
            )

        identity = packets["persistent_profile_identity_packet.json"]
        self.assertEqual(identity["status"], "ok")
        self.assertTrue(identity["profile_root_materialized_by_probe"])
        self.assertFalse(identity["identity_counts_as_thread_history_preservation"])

        relaunch = packets["relaunch_continuity_packet.json"]
        self.assertEqual(relaunch["status"], "ok")
        self.assertTrue(relaunch["same_persistent_profile_identity"])
        self.assertFalse(relaunch["owner_visible_thread_continuity_proven"])
        self.assertFalse(relaunch["storage_level_thread_history_proven"])
        self.assertFalse(relaunch["live_native_relaunch_attempted"])

        role_slots = packets["role_slot_persistence_packet.json"]
        self.assertEqual(role_slots["status"], "ok")
        self.assertEqual(role_slots["role_slot_binding_count_before_reload"], 2)
        self.assertEqual(role_slots["role_slot_binding_count_after_reload"], 2)
        self.assertFalse(role_slots["slot_catalog_revalidated_after_reload"])
        self.assertFalse(role_slots["counts_as_thread_history_restoration"])

        reload_boundary = packets["reload_revalidation_boundary_packet.json"]
        self.assertEqual(reload_boundary["status"], "ok")
        self.assertTrue(reload_boundary["slot_catalog_revalidated_before_reload"])
        self.assertFalse(reload_boundary["slot_catalog_revalidated_after_reload"])
        self.assertFalse(reload_boundary["prompt_admitted_without_revalidation"])
        self.assertEqual(
            reload_boundary["blocked_machine_error_code"],
            "SLOT_CATALOG_REVALIDATION_REQUIRED",
        )

        thread_history = packets["thread_history_classification_packet.json"]
        self.assertEqual(thread_history["status"], "ok")
        self.assertEqual(
            thread_history["classification"],
            "synthetic_storage_only_with_limits",
        )
        self.assertTrue(thread_history["synthetic_history_state_preserved"])
        self.assertFalse(thread_history["thread_history_preserved"])
        self.assertFalse(thread_history["owner_visible_thread_continuity_proven"])
        self.assertFalse(thread_history["storage_level_thread_history_proven"])
        self.assertFalse(thread_history["native_thread_history_restoration_proven"])
        self.assertFalse(thread_history["role_slot_persistence_counted_as_thread_history"])

    def test_probe_writes_required_packets_and_gap_non_claim_boundaries(self) -> None:
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
            self.assertEqual(summary["packet_count"], 17)

            non_claims = json.loads(
                (evidence_dir / "persistent_profile_non_claims_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(non_claims["simultaneous_execution_proven"])
            self.assertFalse(non_claims["runtime_dispatch_truth_proven"])
            self.assertFalse(non_claims["slot_persistence_implies_slot_catalog_revalidation"])

            gaps = json.loads(
                (evidence_dir / "persistent_profile_gap_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            gap_ids = {gap["id"] for gap in gaps["gaps"]}
            self.assertIn("live_native_relaunch_not_attempted_here", gap_ids)
            self.assertIn(
                "role_slot_persistence_not_linked_to_persistent_profile_root_here",
                gap_ids,
            )

            false_green = json.loads(
                (evidence_dir / "false_green_boundary_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(false_green["visible_continuity_treated_as_storage_proof"])
            self.assertFalse(false_green["synthetic_storage_state_treated_as_native_history_restore"])

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn("persistent_profile_identity_is_packet_backed", finding_ids)
            self.assertIn(
                "live_native_relaunch_and_owner_visible_history_truth_remain_open",
                finding_ids,
            )
