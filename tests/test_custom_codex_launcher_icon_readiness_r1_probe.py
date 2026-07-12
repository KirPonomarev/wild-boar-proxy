# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_launcher_icon_readiness_r1_probe import (
    TARGET_STATUS,
    build_false_green_audit,
    build_launcher_authority_boundary_packet,
    build_packets,
    build_summary_packet,
    build_sync_gate_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CustomCodexLauncherIconReadinessR1ProbeTests(unittest.TestCase):
    def test_sync_gate_skip_git_is_deterministic(self) -> None:
        packet = build_sync_gate_packet(
            REPO_ROOT,
            REPO_ROOT / "audit_results" / "unit-test-launcher-icon-evidence",
            skip_git=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["git_branch"], "SKIPPED_FOR_TEST")
        self.assertEqual(packet["git_head"], "SKIPPED_FOR_TEST")
        self.assertEqual(packet["git_status_short"], [])
        self.assertEqual(packet["quarantined_dirty_entries"], [])
        self.assertFalse(packet["historical_dirty_quarantined"])

    def test_launcher_authority_boundary_blocks_external_override_from_shipping_ready(self) -> None:
        packet = build_launcher_authority_boundary_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["default_lane_path_kind"], "default_owned_provisioning_target")
        self.assertEqual(packet["override_lane_path_kind"], "explicit_external_override")
        self.assertFalse(packet["explicit_external_override_shipping_ready"])
        self.assertFalse(packet["launcher_owns_path_authority"])

    def test_false_green_audit_blocks_icon_shipped_claim(self) -> None:
        audit = build_false_green_audit(
            {
                "sync_gate_packet.json": {"status": "ok"},
                "launcher_contract_packet.json": {"status": "ok", "icon_shipped": True},
                "launcher_target_resolution_packet.json": {"status": "ok"},
                "launcher_authority_boundary_packet.json": {"status": "ok"},
                "relaunch_entrypoint_continuity_packet.json": {"status": "ok"},
                "failure_mode_boundary_packet.json": {"status": "ok"},
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("launcher_contract_packet.json.icon_shipped", audit["findings"])

    def test_build_packets_closes_with_no_icon_shipped_yet(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(
                repo_root=REPO_ROOT,
                evidence_dir=Path(tmp) / "evidence",
                skip_git=True,
            )

        summary = packets["launcher_icon_readiness_summary_packet.json"]
        independent = packets["independent_launcher_audit.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["icon_shipped"])
        self.assertFalse(summary["safe_wbp_managed_entrypoint_proven"])
        self.assertEqual(
            packets["launcher_target_resolution_packet.json"]["launch_argv"][:3],
            ["open", "-n", "/Applications/ChatGPT.app"],
        )
        self.assertEqual(independent["status"], "ok")
        self.assertEqual(independent["truthful_outcome"], TARGET_STATUS)
        self.assertTrue(independent["icon_path_inert_display_only"])
        self.assertTrue(packets["failure_mode_boundary_packet.json"]["no_separate_icon_action_surface"])
        self.assertTrue(packets["failure_mode_boundary_packet.json"]["no_fake_icon_shipping_claim"])

    def test_summary_blocks_missing_independent_audit(self) -> None:
        summary = build_summary_packet(
            {
                "sync_gate_packet.json": {"status": "ok"},
                "launcher_contract_packet.json": {"status": "ok"},
                "launcher_target_resolution_packet.json": {"status": "ok"},
                "launcher_authority_boundary_packet.json": {"status": "ok"},
                "relaunch_entrypoint_continuity_packet.json": {"status": "ok"},
                "failure_mode_boundary_packet.json": {"status": "ok"},
                "false_green_audit.json": {"status": "ok"},
            }
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("independent_launcher_audit.json", summary["missing_required_packets"])


if __name__ == "__main__":
    unittest.main()
