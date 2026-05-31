# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools.persistent_profile_backup_restore_dry_run_readiness_r4_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_independent_audit_packet,
    build_packets,
    build_secret_redaction_audit,
)
from wild_boar_proxy.persistent_profile_backup_restore_dry_run import (
    build_backup_manifest_schema_packet,
    build_backup_path_authority_packet,
    build_destructive_action_guard_packet,
    build_equivalence_non_claim_packet,
    build_false_green_audit,
    build_readiness_packets,
    build_restore_manifest_schema_packet,
    build_restore_path_authority_packet,
    build_summary_packet,
    default_dry_run_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def temp_config(tmp: str):
    root = Path(tmp)
    return default_dry_run_config(
        profile_id="unit-profile",
        base_dir=root / "profiles",
        backup_base_dir=root / "backups",
    )


class PersistentProfileBackupRestoreDryRunReadinessR4Tests(unittest.TestCase):
    def test_default_config_validates_path_authority_without_execution_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            backup = build_backup_path_authority_packet(config)
            restore = build_restore_path_authority_packet(config)

        self.assertEqual(backup["status"], "ok")
        self.assertTrue(backup["backup_root_under_wbp_backup_root"])
        self.assertFalse(backup["backup_root_overlaps_persistent_profile"])
        self.assertFalse(backup["backup_root_overlaps_original_codex"])
        self.assertFalse(backup["backup_created"])
        self.assertEqual(restore["status"], "ok")
        self.assertTrue(restore["restore_target_is_persistent_profile_root"])
        self.assertFalse(restore["restore_target_escapes_persistent_profile"])
        self.assertFalse(restore["restore_executed"])

    def test_backup_path_inside_profile_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            unsafe = replace(
                config,
                backup_root=config.persistent_profile_root / "Backups" / "unit-profile",
                wbp_backup_root=config.persistent_profile_root / "Backups",
            )
            packet = build_backup_path_authority_packet(unsafe)

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["backup_root_overlaps_persistent_profile"])
        self.assertFalse(packet["backup_created"])

    def test_restore_target_escape_is_blocked_without_restore_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            unsafe = replace(config, restore_target_root=Path(tmp) / "outside-profile")
            packet = build_restore_path_authority_packet(unsafe)

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["restore_target_escapes_persistent_profile"])
        self.assertFalse(packet["restore_executed"])
        self.assertFalse(packet["restore_execution_allowed"])

    def test_manifest_schemas_record_hashes_only_and_do_not_create_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            backup_manifest = build_backup_manifest_schema_packet(config)
            restore_manifest = build_restore_manifest_schema_packet(
                config,
                backup_manifest_packet=backup_manifest,
            )

        self.assertEqual(backup_manifest["status"], "ok")
        self.assertGreaterEqual(backup_manifest["entry_count"], 1)
        self.assertTrue(backup_manifest["manifest_records_hashes_only"])
        self.assertFalse(backup_manifest["manifest_materialized_from_real_profile"])
        self.assertFalse(backup_manifest["backup_created"])
        self.assertFalse(backup_manifest["path_hash_inventory_is_restorable_backup"])
        self.assertFalse(backup_manifest["planned_entries"][0]["content_recorded"])
        self.assertEqual(restore_manifest["status"], "ok")
        self.assertFalse(restore_manifest["restore_executed"])
        self.assertFalse(restore_manifest["restored_state_equivalence_proven"])
        self.assertFalse(restore_manifest["planned_entries"][0]["content_restored"])

    def test_destructive_action_guard_blocks_any_execution_flag_even_with_owner_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            requested = replace(
                config,
                owner_authorized_destructive_action=True,
                restore_execution_allowed=True,
            )
            packet = build_destructive_action_guard_packet(requested)

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["dry_run_only"])
        self.assertTrue(packet["execution_flags"]["restore_execution_allowed"])
        self.assertFalse(packet["restore_execution_attempted"])
        self.assertFalse(packet["destructive_action_performed"])

    def test_original_codex_surface_cannot_be_backup_or_restore_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            unsafe_backup = replace(config, backup_root=config.original_codex_home / "wbp")
            unsafe_restore = replace(config, restore_target_root=config.original_app_support_dir)

            backup_packet = build_backup_path_authority_packet(unsafe_backup)
            restore_packet = build_restore_path_authority_packet(unsafe_restore)

        self.assertEqual(backup_packet["status"], "blocked")
        self.assertTrue(backup_packet["backup_root_overlaps_original_codex"])
        self.assertEqual(restore_packet["status"], "blocked")
        self.assertTrue(restore_packet["restore_target_overlaps_original_codex"])

    def test_equivalence_and_non_claim_packets_do_not_close_parent_or_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            packets = build_readiness_packets(config)

        summary = packets["persistent_backup_restore_summary_packet.json"]
        equivalence = packets["persistent_backup_restore_equivalence_non_claim_packet.json"]
        non_claim = packets["persistent_backup_restore_non_claim_packet.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertTrue(summary["this_target_closed"])
        self.assertFalse(equivalence["backup_created"])
        self.assertFalse(equivalence["restore_executed"])
        self.assertFalse(equivalence["rollback_proven"])
        self.assertFalse(equivalence["restored_state_equivalence_proven"])
        self.assertFalse(non_claim["thread_history_preservation_claimed"])
        self.assertFalse(non_claim["native_ux_claimed"])
        self.assertFalse(non_claim["original_reversibility_proven"])

    def test_false_green_audit_blocks_backup_restore_and_equivalence_overclaims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            packets = build_readiness_packets(config)

        mutated = dict(packets)
        mutated["persistent_backup_manifest_schema_packet.json"] = {
            **mutated["persistent_backup_manifest_schema_packet.json"],
            "backup_created": True,
        }
        mutated["persistent_restore_manifest_schema_packet.json"] = {
            **mutated["persistent_restore_manifest_schema_packet.json"],
            "restore_executed": True,
            "restored_state_equivalence_proven": True,
        }
        audit = build_false_green_audit(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_backup_manifest_schema_packet.json.backup_created",
            audit["findings"],
        )
        self.assertIn(
            "persistent_restore_manifest_schema_packet.json.restore_executed",
            audit["findings"],
        )
        self.assertIn(
            "persistent_restore_manifest_schema_packet.json.restored_state_equivalence_proven",
            audit["findings"],
        )

    def test_independent_audit_and_summary_block_forbidden_or_missing_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = temp_config(tmp)
            packets = build_readiness_packets(config)

        mutated = dict(packets)
        mutated["persistent_backup_restore_non_claim_packet.json"] = {
            **mutated["persistent_backup_restore_non_claim_packet.json"],
            "native_ux_claimed": True,
        }
        audit = build_independent_audit_packet(mutated)

        missing_packets = dict(packets)
        del missing_packets["persistent_restore_manifest_schema_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_backup_restore_non_claim_packet.json.native_ux_claimed",
            audit["forbidden_true_fields"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "persistent_restore_manifest_schema_packet.json",
            missing_summary["missing_required_packets"],
        )

    def test_probe_packets_secret_audit_and_sync_gate_close_r4_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            config = temp_config(tmp)
            packets = build_packets(
                repo_root=REPO_ROOT,
                evidence_dir=Path(tmp),
                config=config,
            )

        summary = packets["persistent_backup_restore_summary_packet.json"]
        secret = packets["secret_redaction_audit.json"]
        sync = packets["sync_gate_packet.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertFalse(summary["backup_created"])
        self.assertFalse(summary["restore_executed"])
        self.assertFalse(summary["thread_history_preservation_claimed"])
        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_prompt_found"])
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["exhaustive_dlp_claimed"])
        self.assertEqual(sync["status"], "ok")

    def test_equivalence_overclaim_blocks_packet_before_false_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = replace(
                temp_config(tmp),
                rollback_proof_claimed=True,
                restored_state_equivalence_claimed=True,
            )
            packet = build_equivalence_non_claim_packet(config)

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["restored_state_equivalence_claimed"])
        self.assertFalse(packet["backup_created"])
        self.assertFalse(packet["restore_executed"])


if __name__ == "__main__":
    unittest.main()
