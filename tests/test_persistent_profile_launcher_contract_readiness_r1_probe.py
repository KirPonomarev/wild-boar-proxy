# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.persistent_profile_launcher_contract_readiness_r1_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_independent_audit_packet,
    build_persistent_launcher_false_green_audit,
    build_readiness_packets,
    build_summary_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PersistentProfileLauncherContractReadinessR1ProbeTests(unittest.TestCase):
    def test_summary_closes_readiness_only_and_keeps_parent_open(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        summary = packets["persistent_launcher_readiness_summary_packet.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertTrue(summary["this_target_closed"])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["custom_app_launch_attempted"])
        self.assertFalse(summary["owner_prompt_required"])
        self.assertFalse(summary["owner_input_required"])
        self.assertFalse(summary["live_provider_request_attempted"])
        self.assertFalse(summary["command_executed"])
        self.assertFalse(summary["persistent_profile_state_written"])
        self.assertFalse(summary["cleanup_executed"])
        self.assertFalse(summary["backup_export_executed"])
        self.assertFalse(summary["thread_history_preservation_claimed"])
        self.assertFalse(summary["profile_storage_persistence_claimed"])
        self.assertFalse(summary["native_ux_claimed"])
        self.assertFalse(summary["keychain_behavior_classified"])
        self.assertFalse(summary["final_e2e_claimed"])

    def test_command_shape_is_recorded_but_not_executed_or_launch_proof(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        command = packets["persistent_launcher_command_shape_packet.json"]

        self.assertTrue(command["command_shape_recorded"])
        self.assertFalse(command["command_executed"])
        self.assertFalse(command["native_launch_attempted"])
        self.assertFalse(command["custom_app_launch_attempted"])
        self.assertFalse(command["owner_input_required"])
        self.assertFalse(command["live_provider_request_attempted"])
        self.assertFalse(command["command_shape_counts_as_launch_proof"])
        self.assertEqual(command["env_shape"]["WBP_PROFILE_MODE"], "persistent_custom")
        self.assertEqual(command["env_shape"]["WBP_PERSISTENT_PROFILE_ID"], "wbp-custom-main")
        self.assertEqual(
            command["env_shape"]["TMPDIR"],
            command["env_shape"]["WBP_RUNTIME_TMPDIR"],
        )
        self.assertIn("/tmp/wbp-cdx-wbp-custom-main", command["env_shape"]["TMPDIR"])

    def test_profile_identity_and_path_authority_do_not_prove_history_or_storage(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        identity = packets["persistent_profile_identity_contract_packet.json"]
        path_authority = packets["persistent_profile_path_authority_packet.json"]

        self.assertEqual(identity["status"], "ok")
        self.assertEqual(identity["persistent_profile_id"], "wbp-custom-main")
        self.assertFalse(identity["identity_counts_as_thread_history_preservation"])
        self.assertFalse(identity["identity_counts_as_profile_storage_persistence"])
        self.assertFalse(path_authority["browser_client_path_authority"])
        self.assertFalse(path_authority["remote_client_path_authority"])
        self.assertFalse(path_authority["silent_profile_switching_allowed"])
        self.assertTrue(path_authority["profile_root_declared"])
        self.assertFalse(path_authority["profile_root_created"])
        self.assertFalse(path_authority["profile_root_exists_counted_as_state_write_proof"])
        self.assertFalse(path_authority["profile_storage_persistence_claimed"])

    def test_storage_modes_are_distinguishable_and_no_original_shortcut(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        modes = packets["custom_profile_storage_modes_packet.json"]

        self.assertTrue(modes["modes_distinguishable"])
        self.assertFalse(modes["silent_persistent_to_ephemeral_fallback_allowed"])
        self.assertFalse(modes["original_profile_shortcut_allowed"])
        self.assertEqual(modes["modes"]["ephemeral_custom"]["profile_lifetime"], "single_contour")
        self.assertEqual(modes["modes"]["persistent_custom"]["profile_lifetime"], "long_lived")
        self.assertEqual(modes["modes"]["original_codex"]["profile_lifetime"], "user_owned")

    def test_cleanup_backup_and_lock_policies_are_not_execution_or_enforcement(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        cleanup = packets["persistent_cleanup_retention_policy_packet.json"]
        backup = packets["persistent_backup_export_policy_packet.json"]
        concurrent = packets["persistent_concurrent_launch_policy_packet.json"]
        lock = packets["persistent_locking_enforcement_readiness_packet.json"]

        self.assertEqual(cleanup["status"], "ok")
        self.assertFalse(cleanup["cleanup_executed"])
        self.assertFalse(cleanup["persistent_history_delete_allowed_by_default"])
        self.assertTrue(cleanup["ordinary_cleanup_must_preserve_history"])
        self.assertFalse(cleanup["cleanup_policy_counts_as_cleanup_execution"])
        self.assertTrue(backup["backup_export_policy_recorded"])
        self.assertFalse(backup["backup_export_executed"])
        self.assertFalse(backup["backup_created"])
        self.assertFalse(backup["backup_policy_counts_as_backup_created"])
        self.assertEqual(concurrent["policy"], "single_writer_only")
        self.assertTrue(concurrent["launcher_enforces_policy"])
        self.assertTrue(lock["lock_enforcement_ready_to_test"])
        self.assertFalse(lock["lock_enforcement_claimed"])
        self.assertFalse(lock["lock_execution_proven"])
        self.assertFalse(lock["concurrent_policy_counts_as_lock_enforcement"])

    def test_migration_import_and_original_profile_are_non_claims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        migration = packets["persistent_migration_import_non_claim_packet.json"]
        original = packets["original_codex_profile_non_dependency_packet.json"]

        self.assertFalse(migration["migration_import_performed"])
        self.assertTrue(migration["migration_import_disabled_for_ordinary_launch"])
        self.assertTrue(migration["migration_requires_separate_explicit_contour"])
        self.assertFalse(migration["original_codex_profile_used_as_source"])
        self.assertFalse(migration["current_auth_json_copied"])
        self.assertFalse(migration["imported_history_claimed"])
        self.assertFalse(migration["migration_disabled_counts_as_migration_safety_proof"])
        self.assertFalse(original["original_codex_profile_dependency"])
        self.assertFalse(original["original_codex_profile_mutated"])
        self.assertFalse(original["original_codex_profile_used_as_custom_shortcut"])
        self.assertFalse(original["original_codex_history_copied"])
        self.assertFalse(original["original_codex_auth_copied"])

    def test_false_green_audit_blocks_core_overclaims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        command = dict(packets["persistent_launcher_command_shape_packet.json"])
        command["command_executed"] = True
        identity = dict(packets["persistent_profile_identity_contract_packet.json"])
        path_authority = dict(packets["persistent_profile_path_authority_packet.json"])
        path_authority["profile_storage_persistence_claimed"] = True
        cleanup = dict(packets["persistent_cleanup_retention_policy_packet.json"])
        cleanup["cleanup_executed"] = True
        backup = dict(packets["persistent_backup_export_policy_packet.json"])
        backup["backup_created"] = True
        lock = dict(packets["persistent_locking_enforcement_readiness_packet.json"])
        lock["lock_enforcement_claimed"] = True
        migration = dict(packets["persistent_migration_import_non_claim_packet.json"])
        migration["migration_import_performed"] = True
        original = dict(packets["original_codex_profile_non_dependency_packet.json"])
        original["original_codex_profile_dependency"] = True

        audit = build_persistent_launcher_false_green_audit(
            command_shape=command,
            identity=identity,
            path_authority=path_authority,
            cleanup=cleanup,
            backup=backup,
            lock=lock,
            migration=migration,
            original=original,
            non_substitution=packets["persistent_launcher_non_substitution_packet.json"],
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("command_executed", audit["findings"])
        self.assertIn("profile_storage_persistence_claimed", audit["findings"])
        self.assertIn("cleanup_executed", audit["findings"])
        self.assertIn("backup_created", audit["findings"])
        self.assertIn("lock_enforcement_claimed", audit["findings"])
        self.assertIn("migration_import_performed", audit["findings"])
        self.assertIn("original_codex_profile_dependency", audit["findings"])

    def test_independent_audit_blocks_forbidden_true_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["persistent_launcher_command_shape_packet.json"] = {
            **mutated["persistent_launcher_command_shape_packet.json"],
            "command_executed": True,
        }
        audit = build_independent_audit_packet(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_launcher_command_shape_packet.json.command_executed",
            audit["forbidden_true_fields"],
        )

    def test_summary_blocks_missing_or_blocked_gating_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        blocked_packets = dict(packets)
        blocked_packets["persistent_launcher_false_green_audit.json"] = {
            **blocked_packets["persistent_launcher_false_green_audit.json"],
            "status": "blocked",
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["persistent_launcher_command_shape_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn(
            "persistent_launcher_false_green_audit.json",
            blocked_summary["blocked_packets"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "persistent_launcher_command_shape_packet.json",
            missing_summary["missing_required_packets"],
        )

    def test_secret_audit_records_no_raw_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

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
