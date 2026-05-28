# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.persistent_custom_profile_safety_r2_probe import (
    TARGET_STATUS,
    build_false_green_audit,
    build_packets,
    build_persistent_backup_readiness_packet,
    build_persistent_cleanup_scope_boundary_packet,
    build_persistent_profile_lock_enforcement_packet,
    build_restore_target_safety_packet,
    build_source_inventory_packet,
    build_summary_packet,
    build_timestamped_backup_complete_marker_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_repair_fixture(root: Path) -> Path:
    repair = root / "repair"
    backup_root = root / "wbp-custom-main.backup.20260528T010203Z"
    backup_root.mkdir(parents=True, exist_ok=True)
    marker_path = backup_root / ".wbp_backup_complete"
    marker_path.write_text(
        json.dumps(
            {
                "created_at_utc": "2026-05-28T01:02:03Z",
                "profile_id": "wbp-custom-main",
                "backup_scope": "selective_state_backup",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    repair.mkdir(parents=True, exist_ok=True)
    fixture = {
        "backup_repair_summary_packet.json": {
            "status": "ok",
            "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
            "profile_id": "wbp-custom-main",
            "timestamped_backup_root": str(backup_root),
            "rollback_ready": True,
        },
        "rollback_readiness_packet.json": {
            "status": "ok",
            "rollback_ready": True,
            "state_backup": True,
            "cache_excluded": True,
            "existing_incomplete_backup_counted": False,
            "original_codex_write_performed_by_contour": False,
        },
        "state_backup_manifest_packet.json": {
            "status": "ok",
            "copied_file_count": 4,
            "raw_content_recorded": False,
        },
        "cache_exclusion_manifest_packet.json": {
            "status": "ok",
            "excluded_count": 3,
        },
        "timestamped_backup_complete_marker_packet.json": {
            "status": "ok",
            "marker_path": str(marker_path),
            "complete_marker_created": True,
            "complete_marker_created_after_manifest_success": True,
        },
        "backup_repair_policy_packet.json": {
            "status": "ok",
            "policy": "timestamped_selective_state_backup",
            "persistent_profile_deletion_allowed": False,
        },
        "backup_repair_false_green_audit.json": {
            "status": "ok",
        },
        "incomplete_backup_classification_packet.json": {
            "status": "ok",
            "existing_backup_counted_as_rollback_proof": False,
        },
    }
    for filename, payload in fixture.items():
        (repair / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return repair


class PersistentCustomProfileSafetyR2ProbeTests(unittest.TestCase):
    def test_source_inventory_blocks_missing_required_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repair = write_repair_fixture(Path(tmp))
            (repair / "backup_repair_false_green_audit.json").unlink()

            packet = build_source_inventory_packet(repair)

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("backup_repair_false_green_audit.json", packet["missing_packets"])

    def test_backup_readiness_requires_ready_reference_and_clean_source_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repair = write_repair_fixture(Path(tmp))

            packet = build_persistent_backup_readiness_packet(
                repair_evidence_dir=repair,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["rollback_ready"])
        self.assertFalse(packet["persistent_profile_deletion_allowed"])
        self.assertFalse(packet["incomplete_backup_counted_as_rollback_proof"])
        self.assertFalse(packet["backup_created_in_current_contour"])

    def test_timestamped_backup_complete_marker_blocks_mismatched_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repair = write_repair_fixture(Path(tmp))
            summary_path = repair / "backup_repair_summary_packet.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["timestamped_backup_root"] = str(Path(tmp) / "wrong-backup-root")
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

            packet = build_timestamped_backup_complete_marker_packet(
                repair_evidence_dir=repair,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["marker_matches_timestamped_backup_root"])

    def test_timestamped_backup_complete_marker_requires_expected_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repair = write_repair_fixture(Path(tmp))
            marker_packet = json.loads(
                (repair / "timestamped_backup_complete_marker_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            marker_path = Path(marker_packet["marker_path"])
            marker_path.write_text(
                json.dumps(
                    {
                        "created_at_utc": "2026-05-28T01:02:03Z",
                        "profile_id": "wrong-profile",
                        "backup_scope": "wrong-scope",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            packet = build_timestamped_backup_complete_marker_packet(
                repair_evidence_dir=repair,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["marker_payload_matches_summary"])

    def test_lock_enforcement_blocks_unusable_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "tools.persistent_custom_profile_safety_r2_probe.build_same_profile_process_gate_packet",
                return_value={
                    "status": "blocked",
                    "reason_class": "PROCESS_INVENTORY_UNUSABLE",
                    "inventory_usable": False,
                    "same_profile_process_present": False,
                    "custom_process_count": -1,
                },
            ):
                packet = build_persistent_profile_lock_enforcement_packet(
                    profile_id="wbp-custom-main",
                    base_dir=Path(tmp) / "profiles",
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "PROCESS_INVENTORY_UNUSABLE")
        self.assertFalse(packet["inventory_usable"])
        self.assertFalse(packet["lock_acquired"])

    def test_lock_enforcement_preserves_zero_process_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "tools.persistent_custom_profile_safety_r2_probe.build_same_profile_process_gate_packet",
                return_value={
                    "status": "ok",
                    "reason_class": "",
                    "inventory_usable": True,
                    "same_profile_process_present": False,
                    "custom_process_count": 0,
                },
            ):
                packet = build_persistent_profile_lock_enforcement_packet(
                    profile_id="wbp-custom-main",
                    base_dir=Path(tmp) / "profiles",
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["custom_process_count"], 0)

    def test_restore_target_safety_uses_actual_backup_root_and_no_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repair = write_repair_fixture(Path(tmp))
            base_dir = Path(tmp) / "profiles"
            backup_root = base_dir / "wbp-custom-main.backup.20260528T010203Z"
            backup_root.mkdir(parents=True, exist_ok=True)
            marker_path = backup_root / ".wbp_backup_complete"
            marker_path.write_text(
                json.dumps(
                    {
                        "created_at_utc": "2026-05-28T01:02:03Z",
                        "profile_id": "wbp-custom-main",
                        "backup_scope": "selective_state_backup",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            summary_path = repair / "backup_repair_summary_packet.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["timestamped_backup_root"] = str(backup_root)
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            marker_packet_path = repair / "timestamped_backup_complete_marker_packet.json"
            marker_packet = json.loads(marker_packet_path.read_text(encoding="utf-8"))
            marker_packet["marker_path"] = str(marker_path)
            marker_packet_path.write_text(json.dumps(marker_packet, indent=2), encoding="utf-8")
            backup_readiness = build_persistent_backup_readiness_packet(
                repair_evidence_dir=repair,
            )
            backup_root = Path(backup_readiness["timestamped_backup_root"])

            packet = build_restore_target_safety_packet(
                profile_id="wbp-custom-main",
                base_dir=base_dir,
                backup_root=backup_root,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["restore_target_is_persistent_profile_root"])
        self.assertFalse(packet["restore_target_overlaps_backup_root"])
        self.assertFalse(packet["restore_executed"])
        self.assertFalse(packet["restore_execution_allowed"])

    def test_restore_target_safety_blocks_backup_root_outside_profile_parent_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profiles"
            packet = build_restore_target_safety_packet(
                profile_id="wbp-custom-main",
                base_dir=base_dir,
                backup_root=Path(tmp) / "outside" / "wbp-custom-main.backup.20260528T010203Z",
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["backup_root_under_wbp_backup_root"])

    def test_cleanup_scope_boundary_keeps_tmp_subtree_separate_from_profile_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profiles"
            packet = build_persistent_cleanup_scope_boundary_packet(
                profile_id="wbp-custom-main",
                base_dir=base_dir,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["cleanup_target_is_persistent_profile_root"])
        self.assertTrue(packet["cleanup_target_under_persistent_profile_root"])
        self.assertFalse(packet["cleanup_attempted"])
        self.assertFalse(packet["cleanup_executed"])

    def test_false_green_audit_blocks_memory_and_auth_overclaims(self) -> None:
        packets = {
            "persistent_profile_lock_enforcement_packet.json": {"status": "ok"},
            "persistent_backup_readiness_packet.json": {"status": "ok", "thread_history_claimed": True},
            "timestamped_backup_complete_marker_packet.json": {"status": "ok"},
            "restore_target_safety_packet.json": {"status": "ok", "auth_proof_claimed": True},
            "persistent_cleanup_scope_boundary_packet.json": {"status": "ok"},
        }

        audit = build_false_green_audit(packets)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_backup_readiness_packet.json.thread_history_claimed",
            audit["findings"],
        )
        self.assertIn(
            "restore_target_safety_packet.json.auth_proof_claimed",
            audit["findings"],
        )

    def test_build_packets_closes_target_without_live_mutation_or_ui_claims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            repair = write_repair_fixture(Path(tmp))
            base_dir = Path(tmp) / "profiles"
            backup_root = base_dir / "wbp-custom-main.backup.20260528T010203Z"
            backup_root.mkdir(parents=True, exist_ok=True)
            marker_path = backup_root / ".wbp_backup_complete"
            marker_path.write_text(
                json.dumps(
                    {
                        "created_at_utc": "2026-05-28T01:02:03Z",
                        "profile_id": "wbp-custom-main",
                        "backup_scope": "selective_state_backup",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            summary_path = repair / "backup_repair_summary_packet.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["timestamped_backup_root"] = str(backup_root)
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            marker_packet_path = repair / "timestamped_backup_complete_marker_packet.json"
            marker_packet = json.loads(marker_packet_path.read_text(encoding="utf-8"))
            marker_packet["marker_path"] = str(marker_path)
            marker_packet_path.write_text(json.dumps(marker_packet, indent=2), encoding="utf-8")
            with mock.patch(
                "tools.persistent_custom_profile_safety_r2_probe.build_same_profile_process_gate_packet",
                return_value={
                    "status": "ok",
                    "reason_class": "",
                    "inventory_usable": True,
                    "same_profile_process_present": False,
                    "custom_process_count": 0,
                },
            ):
                packets = build_packets(
                    repo_root=REPO_ROOT,
                    evidence_dir=Path(tmp) / "evidence",
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=base_dir,
                    skip_git=True,
                )

        summary = packets["persistent_profile_safety_summary_packet.json"]
        independent = packets["independent_persistent_profile_safety_audit.json"]
        secret = packets["secret_redaction_audit.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["lock_acquired"])
        self.assertFalse(summary["backup_created_in_current_contour"])
        self.assertFalse(summary["restore_executed"])
        self.assertFalse(summary["cleanup_attempted"])
        self.assertFalse(summary["thread_history_claimed"])
        self.assertFalse(summary["auth_proof_claimed"])
        self.assertFalse(summary["final_e2e_claimed"])
        self.assertFalse(packets["sync_gate_packet.json"]["cross_contour_support_declared"])
        self.assertEqual(
            packets["persistent_profile_lock_enforcement_packet.json"]["custom_process_count"],
            0,
        )
        self.assertEqual(independent["status"], "ok")
        self.assertEqual(secret["status"], "ok")

    def test_summary_blocks_when_required_packet_missing(self) -> None:
        packets = {
            "sync_gate_packet.json": {"status": "ok"},
            "source_inventory_packet.json": {"status": "ok"},
            "persistent_profile_lock_enforcement_packet.json": {"status": "ok"},
            "persistent_backup_readiness_packet.json": {"status": "ok"},
            "timestamped_backup_complete_marker_packet.json": {"status": "ok"},
            "restore_target_safety_packet.json": {"status": "ok"},
            "persistent_cleanup_scope_boundary_packet.json": {"status": "ok"},
            "false_green_audit.json": {"status": "ok"},
            "secret_redaction_audit.json": {"status": "ok"},
        }

        summary = build_summary_packet(packets)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn(
            "independent_persistent_profile_safety_audit.json",
            summary["missing_required_packets"],
        )


if __name__ == "__main__":
    unittest.main()
