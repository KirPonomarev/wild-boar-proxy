# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.native_custom_safety_refresh_pre_live_r1_probe import (
    TARGET_STATUS,
    build_false_green_audit,
    build_independent_audit_packet,
    build_packets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class NativeCustomSafetyRefreshPreLiveR1ProbeTests(unittest.TestCase):
    def test_summary_closes_this_contour_without_live_or_native_overclaim(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        summary = packets["native_custom_safety_refresh_summary_packet.json"]
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertTrue(summary["this_target_closed"])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["route_proof_claimed"])
        self.assertFalse(summary["direct_egress_absence_claimed"])
        self.assertFalse(summary["native_ux_claimed"])
        self.assertFalse(summary["original_codex_reversibility_claimed"])
        self.assertFalse(summary["final_e2e_claimed"])

    def test_launcher_identity_and_effective_paths_stay_under_tmp_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        launcher = packets["native_custom_launcher_identity_packet.json"]
        paths = packets["native_custom_effective_paths_packet.json"]
        self.assertEqual(launcher["status"], "ok")
        self.assertTrue(launcher["launcher_under_tmp_root"])
        self.assertFalse(launcher["counts_as_launch_success"])
        self.assertEqual(paths["status"], "ok")
        self.assertFalse(paths["native_launch_attempted"])
        self.assertTrue(paths["home_under_tmp_root"])
        self.assertTrue(paths["tmp_dir_under_tmp_root"])
        self.assertEqual(paths["codex_home_packet"]["status"], "ok")
        self.assertEqual(paths["user_data_dir_packet"]["status"], "ok")

    def test_auth_boundary_refresh_is_dependency_check_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        auth = packets["native_custom_auth_boundary_refresh_packet.json"]
        self.assertEqual(auth["status"], "ok")
        self.assertEqual(auth["selected_strategy"], "auth.command")
        self.assertTrue(auth["auth_boundary_dependency_check_only"])
        self.assertFalse(auth["auth_boundary_clean_counts_as_route_proof"])
        self.assertFalse(auth["auth_boundary_clean_counts_as_launcher_usability_proof"])
        self.assertFalse(auth["ambient_authority_used_for_native_launch"])

    def test_false_green_audit_blocks_boundary_collapses(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        auth = dict(packets["native_custom_auth_boundary_refresh_packet.json"])
        auth["auth_boundary_clean_counts_as_route_proof"] = True
        hygiene = dict(packets["native_custom_execution_hygiene_packet.json"])
        hygiene["execution_hygiene_is_product_truth"] = True

        audit = build_false_green_audit(
            admission_packet=packets["native_custom_safety_admission_packet.json"],
            launcher_identity_packet=packets["native_custom_launcher_identity_packet.json"],
            protected_surface_observation_packet=packets[
                "native_custom_protected_surface_observation_packet.json"
            ],
            auth_boundary_refresh_packet=auth,
            execution_hygiene_packet=hygiene,
        )

        self.assertEqual(audit["status"], "blocked")
        failed = {check["name"] for check in audit["checks"] if not check["passed"]}
        self.assertIn("auth_boundary_not_route_or_usability_proof", failed)
        self.assertIn("execution_hygiene_not_product_truth", failed)

    def test_independent_audit_blocks_forbidden_true_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["native_custom_safety_admission_packet.json"] = {
            **mutated["native_custom_safety_admission_packet.json"],
            "native_launch_attempted": True,
        }
        audit = build_independent_audit_packet(mutated)
        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "native_custom_safety_admission_packet.json.native_launch_attempted",
            audit["forbidden_true_fields"],
        )


if __name__ == "__main__":
    unittest.main()
