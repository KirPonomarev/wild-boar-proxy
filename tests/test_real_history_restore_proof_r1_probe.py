# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.real_history_restore_proof_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "real_history_restore_proof_r1_probe.py"


class RealHistoryRestoreProofR1ProbeTests(unittest.TestCase):
    def test_build_packets_strengthens_history_only_to_helper_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(temp_dir))

        restore = packets["history_restore_packet.json"]
        self.assertEqual(restore["status"], "ok")
        self.assertEqual(restore["final_status"], "REAL_HISTORY_RESTORE_CLASSIFIED_WITH_LIMITS")
        self.assertEqual(restore["classification"], "helper_reload_observed_with_limits")
        self.assertTrue(restore["prior_synthetic_storage_limiter_reduced"])
        self.assertTrue(restore["stable_profile_identity_observed"])
        self.assertFalse(restore["stable_profile_identity_counted_as_thread_restore"])
        self.assertTrue(restore["storage_state_observed"])
        self.assertFalse(restore["storage_file_presence_counted_as_restore"])
        self.assertTrue(restore["helper_reload_observed"])
        self.assertFalse(restore["helper_reload_counted_as_native_visible_restore"])
        self.assertFalse(restore["native_visible_restore_proven"])
        self.assertFalse(restore["role_slot_persistence_counted_as_thread_history"])
        self.assertFalse(restore["original_codex_profile_participates_in_proof"])

        profile = packets["profile_relaunch_continuity_packet.json"]
        self.assertEqual(profile["status"], "ok")
        self.assertEqual(profile["classification"], "helper_reload_like_only_with_limits")
        self.assertTrue(profile["same_persistent_profile_identity"])
        self.assertTrue(profile["helper_reload_observed"])
        self.assertFalse(profile["native_app_relaunch_observed"])
        self.assertFalse(profile["helper_reload_equals_native_app_relaunch"])
        self.assertEqual(profile["ledger_event_count_after_reload"], 3)
        self.assertIn("session_created", profile["ledger_event_names_after_reload"])
        self.assertIn("prompt_completed_e2e", profile["ledger_event_names_after_reload"])
        self.assertTrue(profile["primary_slot_reloaded"])
        self.assertTrue(profile["coding_slot_reloaded"])
        self.assertFalse(profile["role_slot_reload_counted_as_thread_history"])

        separation = packets["history_vs_slot_separation_packet.json"]
        self.assertEqual(separation["status"], "ok")
        self.assertTrue(separation["thread_ledger_restored"])
        self.assertTrue(separation["role_slots_restored"])
        self.assertFalse(separation["role_slot_persistence_counted_as_thread_history"])
        self.assertFalse(separation["thread_history_file_presence_counted_as_runtime_slot_truth"])
        self.assertFalse(separation["history_and_slot_truth_collapsed"])

        native = packets["native_visible_restore_boundary_packet.json"]
        self.assertEqual(native["status"], "ok")
        self.assertFalse(native["native_visible_restore_observed"])
        self.assertFalse(native["native_visible_restore_claimed"])
        self.assertTrue(native["helper_level_reload_observed"])
        self.assertFalse(native["helper_level_reload_counts_as_native_visible_restore"])
        self.assertFalse(native["native_app_relaunch_attempted"])

        gaps = packets["history_restore_gap_matrix.json"]
        self.assertEqual(gaps["status"], "ok")
        self.assertTrue(gaps["open_native_visible_restore_gap"])
        self.assertTrue(gaps["synthetic_storage_limiter_reduced"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertEqual(false_green["status"], "ok")
        self.assertFalse(false_green["file_presence_treated_as_restore"])
        self.assertFalse(false_green["stable_profile_identity_treated_as_thread_restore"])
        self.assertFalse(false_green["helper_reload_treated_as_native_visible_restore"])
        self.assertFalse(false_green["role_slot_persistence_treated_as_thread_history"])
        self.assertFalse(false_green["original_codex_profile_used_as_history_proof"])
        self.assertFalse(false_green["native_visible_restore_claimed_without_observation"])

        audit = packets["independent_audit_packet.json"]
        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["agent_verdict_counted"])
        finding_ids = {finding["id"] for finding in audit["findings"]}
        self.assertIn("helper_reload_observed_but_not_native_visible_restore", finding_ids)
        self.assertIn("history_slot_separation_preserved", finding_ids)
        self.assertIn("native_visible_restore_remains_open_non_claim", finding_ids)

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    temp_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 7)
            self.assertEqual(
                summary["history_restore_classification"],
                "helper_reload_observed_with_limits",
            )

            restore = json.loads(
                (Path(temp_dir) / "history_restore_packet.json").read_text(encoding="utf-8")
            )
            self.assertEqual(restore["classification"], "helper_reload_observed_with_limits")


if __name__ == "__main__":
    unittest.main()
