# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import role_profile_ui_polish_classification_r1_probe as probe


class RoleProfileUiPolishClassificationR1ProbeTests(unittest.TestCase):
    def test_build_packets_classifies_role_profile_ui_polish_as_admitted_and_bounded(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = probe.build_packets(repo_root=repo_root, evidence_dir=evidence_dir)

        summary = packets["role_profile_ui_summary_packet.json"]
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], "ROLE_PROFILE_UI_POLISH_CLASSIFIED")
        self.assertFalse(summary["new_command_surfaces_introduced"])
        self.assertFalse(summary["authority_boundary_changed"])

    def test_browser_packet_confirms_role_normalization_without_raw_authority_copy(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        browser_packet = probe._node_browser_check(repo_root)
        self.assertEqual(browser_packet["status"], "ok")
        result = browser_packet["result"]
        self.assertTrue(result["main_role_normalized"])
        self.assertTrue(result["reserve_role_normalized"])
        self.assertTrue(result["raw_main_role_hidden"])
        self.assertEqual(result["role_pill_class"], "mini-pill api-route-role-pill blue")

    def test_probe_writes_packets_and_exit_code_zero(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            exit_code = probe.main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                ]
            )
            self.assertEqual(exit_code, 0)
            summary = json.loads((evidence_dir / "role_profile_ui_summary_packet.json").read_text())
            verification = json.loads((evidence_dir / "verification_results_packet.json").read_text())
            self.assertEqual(summary["final_status"], "ROLE_PROFILE_UI_POLISH_CLASSIFIED")
            self.assertEqual(verification["status"], "ok")


if __name__ == "__main__":
    unittest.main()
