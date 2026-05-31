# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.native_custom_safety_admission_refresh_r2_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_false_green_audit,
    build_independent_audit_packet,
    build_packets,
    build_summary_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class NativeCustomSafetyAdmissionRefreshR2ProbeTests(unittest.TestCase):
    def test_summary_closes_r2_only_without_live_or_parent_overclaim(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        summary = packets["native_custom_safety_refresh_summary_packet.json"]
        live_gate = packets["native_custom_live_precondition_gate_packet.json"]

        if summary["status"] == "blocked":
            self.assertIn("sync_gate_packet.json", summary["blocked_packets"])
            self.assertFalse(summary["parent_target_closed"])
            self.assertFalse(summary["this_target_closed"])
            self.assertFalse(summary["native_launch_attempted"])
            return
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertTrue(summary["this_target_closed"])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["custom_app_launch_attempted"])
        self.assertFalse(summary["owner_prompt_required"])
        self.assertFalse(summary["live_provider_request_attempted"])
        self.assertFalse(summary["direct_egress_absence_claimed"])
        self.assertFalse(summary["native_ux_claimed"])
        self.assertFalse(summary["thread_history_persistence_claimed"])
        self.assertFalse(summary["keychain_independence_claimed"])
        self.assertFalse(summary["route_proof_claimed"])
        self.assertFalse(live_gate["live_execution_allowed_in_this_contour"])

    def test_profile_modes_distinguish_ephemeral_persistent_and_original(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        boundary = packets["native_custom_profile_mode_boundary_packet.json"]
        modes = boundary["profile_modes"]

        self.assertTrue(boundary["modes_distinguishable"])
        self.assertEqual(modes["ephemeral_custom"]["profile_lifetime"], "single_contour")
        self.assertEqual(modes["persistent_custom"]["profile_lifetime"], "long_lived")
        self.assertEqual(modes["original_codex"]["profile_lifetime"], "user_owned")
        self.assertFalse(modes["persistent_custom"]["cleanup_can_delete_history_by_default"])
        self.assertFalse(boundary["persistent_identity_counts_as_history_proof"])
        self.assertFalse(boundary["original_profile_shortcut_allowed"])

    def test_persistent_identity_is_not_thread_history_persistence(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        identity = packets["persistent_custom_profile_identity_packet.json"]
        history = packets["persistent_history_non_claim_packet.json"]

        self.assertEqual(identity["status"], "ok")
        self.assertTrue(history["stable_profile_identity_classified"])
        self.assertFalse(history["thread_history_persistence_claimed"])
        self.assertFalse(history["relaunch_storage_proof_present"])
        self.assertFalse(history["owner_visible_thread_counted_as_storage_proof"])
        self.assertFalse(history["route_trace_counted_as_saved_thread_proof"])
        self.assertFalse(history["identity_counts_as_history_proof"])

    def test_keychain_prompt_absence_is_not_keychain_independence(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        keychain = packets["keychain_prompt_non_claim_boundary_packet.json"]

        self.assertFalse(keychain["keychain_prompt_absence_counted_as_independence_proof"])
        self.assertFalse(keychain["keychain_independence_claimed"])
        self.assertFalse(keychain["keychain_mutation_performed"])
        self.assertFalse(keychain["keychain_reset_performed"])
        self.assertFalse(keychain["original_keychain_runtime_dependency"])

    def test_original_and_custom_surfaces_do_not_grant_runtime_authority(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        protected = packets["original_codex_protected_surface_packet.json"]
        custom = packets["custom_owned_surface_packet.json"]
        writes = packets["native_custom_declared_write_surfaces_packet.json"]

        self.assertFalse(protected["filesystem_write_performed"])
        self.assertFalse(protected["original_codex_mutated"])
        self.assertFalse(protected["original_codex_profile_write_allowed"])
        self.assertFalse(protected["original_codex_bundle_write_allowed"])
        self.assertFalse(protected["snapshot_is_runtime_authority"])
        self.assertFalse(custom["original_codex_surfaces_owned_by_custom"])
        self.assertFalse(custom["protected_surface_overlap_allowed"])
        self.assertFalse(writes["persistent_custom_profile_write_allowed"])
        self.assertFalse(writes["route_account_model_provider_mutation_allowed"])

    def test_cleanup_policy_preserves_persistent_history_by_default(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        cleanup = packets["native_custom_cleanup_rollback_policy_packet.json"]
        persistent = packets["persistent_cleanup_policy_packet.json"]

        self.assertEqual(cleanup["status"], "ok")
        self.assertEqual(persistent["status"], "ok")
        self.assertFalse(cleanup["persistent_history_delete_allowed_by_default"])
        self.assertTrue(cleanup["explicit_owner_delete_authorization_required"])
        self.assertTrue(persistent["ordinary_cleanup_must_preserve_history"])
        self.assertFalse(persistent["cleanup_deletes_persistent_profile_by_default"])

    def test_false_green_audit_blocks_profile_history_keychain_cleanup_and_live_overclaims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        profile_mode = dict(packets["native_custom_profile_mode_boundary_packet.json"])
        profile_mode["profile_modes"] = {
            **profile_mode["profile_modes"],
            "persistent_custom": {
                **profile_mode["profile_modes"]["persistent_custom"],
                "cleanup_can_delete_history_by_default": True,
            },
        }
        persistent_history = dict(packets["persistent_history_non_claim_packet.json"])
        persistent_history["thread_history_persistence_claimed"] = True
        keychain = dict(packets["keychain_prompt_non_claim_boundary_packet.json"])
        keychain["keychain_prompt_absence_counted_as_independence_proof"] = True
        cleanup = dict(packets["native_custom_cleanup_rollback_policy_packet.json"])
        cleanup["persistent_history_delete_allowed_by_default"] = True
        live_gate = dict(packets["native_custom_live_precondition_gate_packet.json"])
        live_gate["live_execution_allowed_in_this_contour"] = True

        audit = build_false_green_audit(
            profile_mode=profile_mode,
            persistent_history=persistent_history,
            keychain_boundary=keychain,
            cleanup_policy=cleanup,
            live_gate=live_gate,
            non_substitution=packets["native_custom_safety_non_substitution_packet.json"],
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("persistent_cleanup_can_delete_history_by_default", audit["findings"])
        self.assertIn("thread_history_persistence_claimed", audit["findings"])
        self.assertIn("keychain_prompt_absence_counted_as_independence", audit["findings"])
        self.assertIn("persistent_history_delete_allowed_by_default", audit["findings"])
        self.assertIn("live_execution_allowed", audit["findings"])

    def test_independent_audit_blocks_forbidden_true_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["native_custom_live_precondition_gate_packet.json"] = {
            **mutated["native_custom_live_precondition_gate_packet.json"],
            "native_launch_attempted": True,
        }
        audit = build_independent_audit_packet(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "native_custom_live_precondition_gate_packet.json.native_launch_attempted",
            audit["forbidden_true_fields"],
        )

    def test_summary_blocks_missing_or_blocked_gating_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        blocked_packets = dict(packets)
        blocked_packets["native_custom_safety_false_green_audit.json"] = {
            **blocked_packets["native_custom_safety_false_green_audit.json"],
            "status": "blocked",
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["native_custom_live_precondition_gate_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn(
            "native_custom_safety_false_green_audit.json",
            blocked_summary["blocked_packets"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "native_custom_live_precondition_gate_packet.json",
            missing_summary["missing_required_packets"],
        )

    def test_secret_audit_records_no_raw_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        secret = packets["secret_redaction_audit.json"]

        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["raw_prompt_found"])
        self.assertFalse(secret["raw_secret_recorded"])
        self.assertFalse(secret["raw_prompt_recorded"])
        self.assertFalse(secret["exhaustive_dlp_claimed"])
        self.assertEqual(secret["secret_marker_findings"], [])
        self.assertEqual(secret["prompt_marker_findings"], [])


if __name__ == "__main__":
    unittest.main()
