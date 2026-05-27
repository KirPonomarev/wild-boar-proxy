# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PersistentProfileMigrationImportR1ProbeTests(unittest.TestCase):
    def _init_repo(self, repo_root: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
        (repo_root / "audit_results").mkdir()
        (repo_root / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    def _write_json(self, root: Path, rel: str, packet: dict) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet), encoding="utf-8")

    def _write_sources(self, root: Path) -> dict[str, Path]:
        dirs = {
            "r1_contract": root / "audit_results" / "r1",
            "r4_dry_run": root / "audit_results" / "r4",
            "backup_repair": root / "audit_results" / "repair",
            "history_import": root / "audit_results" / "history",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        r1_packets = {
            "persistent_launcher_readiness_summary_packet.json": {"status": "ok"},
            "persistent_launcher_false_green_audit.json": {"status": "ok"},
            "persistent_profile_identity_contract_packet.json": {
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/tmp/wbp-custom-main",
            },
            "persistent_backup_export_policy_packet.json": {
                "status": "ok",
                "backup_export_required_before_first_persistent_write": True,
                "rollback_expectation_declared": True,
            },
            "persistent_migration_import_non_claim_packet.json": {
                "status": "ok",
                "migration_import_performed": False,
                "migration_import_disabled_for_ordinary_launch": True,
                "migration_requires_separate_explicit_contour": True,
                "original_codex_profile_used_as_source": False,
                "current_auth_json_copied": False,
            },
            "original_codex_profile_non_dependency_packet.json": {
                "status": "ok",
                "original_codex_profile_dependency": False,
                "original_codex_profile_used_as_custom_shortcut": False,
            },
        }
        for name, packet in r1_packets.items():
            self._write_json(root, f"audit_results/r1/{name}", packet)

        r4_packets = {
            "persistent_backup_restore_summary_packet.json": {
                "status": "ok",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_RESTORE_DRY_RUN_READINESS_R4_CLASSIFIED",
            },
            "persistent_backup_restore_contract_packet.json": {
                "status": "ok",
                "contour_scope": "dry_run_backup_restore_readiness_only",
                "backup_execution_allowed": False,
                "restore_execution_allowed": False,
            },
            "persistent_backup_path_authority_packet.json": {
                "status": "ok",
                "backup_root_under_wbp_backup_root": True,
            },
            "persistent_restore_path_authority_packet.json": {
                "status": "ok",
                "restore_target_root": "/tmp/wbp-custom-main",
                "restore_target_is_persistent_profile_root": True,
            },
            "persistent_backup_manifest_schema_packet.json": {"status": "ok"},
            "persistent_restore_manifest_schema_packet.json": {"status": "ok"},
            "persistent_original_profile_backup_restore_guard_packet.json": {
                "status": "ok",
                "original_codex_used_as_source": False,
                "original_codex_used_as_target": False,
            },
            "persistent_backup_restore_equivalence_non_claim_packet.json": {
                "status": "ok",
                "restored_state_equivalence_proven": False,
            },
            "persistent_backup_restore_non_claim_packet.json": {
                "status": "ok",
                "restore_executed": False,
            },
            "persistent_backup_restore_false_green_audit.json": {"status": "ok"},
            "independent_persistent_backup_restore_dry_run_audit.json": {"status": "ok"},
        }
        for name, packet in r4_packets.items():
            self._write_json(root, f"audit_results/r4/{name}", packet)

        repair_packets = {
            "backup_repair_summary_packet.json": {
                "status": "ok",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                "rollback_ready": True,
                "profile_id": "wbp-custom-main",
                "timestamped_backup_root": "/tmp/wbp-custom-main.backup.1",
            },
            "state_backup_manifest_packet.json": {
                "status": "ok",
                "copied_file_count": 10,
                "copied_dir_count": 5,
                "copy_failures": [],
            },
            "backup_surface_classification_packet.json": {
                "status": "ok",
                "copied_classes": [
                    "thread_history",
                    "session_state",
                    "integration_state_unclassified",
                ],
                "excluded_classes": [
                    "cache_or_incidental_state",
                    "secret_or_auth_surface",
                ],
            },
            "backup_repair_policy_packet.json": {
                "status": "ok",
                "policy": "timestamped_selective_state_backup",
                "persistent_profile_deletion_allowed": False,
            },
            "backup_repair_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in repair_packets.items():
            self._write_json(root, f"audit_results/repair/{name}", packet)

        history_packets = {
            "persistent_profile_continuity_classification_packet.json": {
                "status": "ok",
                "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED_WITH_LIMITS",
                "with_limits_required": True,
                "route_proof_claimed": False,
                "final_e2e_claimed": False,
            },
            "persistent_profile_summary_packet.json": {"status": "ok"},
            "persistent_profile_false_green_audit.json": {"status": "ok"},
            "independent_persistent_profile_audit.json": {"status": "ok"},
        }
        for name, packet in history_packets.items():
            self._write_json(root, f"audit_results/history/{name}", packet)

        return dirs

    def test_probe_classifies_migration_with_limits_from_boundary_chain(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "persistent_profile_migration_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "migration_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--r1-contract-dir",
                    str(dirs["r1_contract"]),
                    "--r4-dry-run-dir",
                    str(dirs["r4_dry_run"]),
                    "--backup-repair-dir",
                    str(dirs["backup_repair"]),
                    "--history-import-dir",
                    str(dirs["history_import"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "persistent_profile_migration_summary_packet.json").read_text()
            )
            classification = json.loads(
                (evidence_dir / "persistent_profile_migration_classification_packet.json").read_text()
            )
            scanner = json.loads(
                (evidence_dir / "scanner_agent_fact_report_packet.json").read_text()
            )
            independent = json.loads(
                (evidence_dir / "independent_persistent_profile_migration_audit.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "WBP_CUSTOM_PERSISTENT_PROFILE_MIGRATION_CLASSIFIED_WITH_LIMITS",
            )
            self.assertFalse(classification["migration_execution_proven"])
            self.assertFalse(classification["restored_state_equivalence_proven"])
            self.assertTrue(classification["with_limits_required"])
            self.assertEqual(scanner["status"], "ok")
            self.assertIn(
                "integration_state_unclassified",
                scanner["facts"]["unknown_or_unclassified_state_classes"],
            )
            self.assertEqual(independent["status"], "ok")
            self.assertFalse(independent["current_live_migration_execution_collected"])

    def test_probe_blocks_when_migration_is_hidden_in_ordinary_launch(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "persistent_profile_migration_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            bad_packet = dirs["r1_contract"] / "persistent_migration_import_non_claim_packet.json"
            bad_packet.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "migration_import_performed": True,
                        "migration_import_disabled_for_ordinary_launch": False,
                        "migration_requires_separate_explicit_contour": False,
                        "original_codex_profile_used_as_source": False,
                        "current_auth_json_copied": False,
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "migration_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--r1-contract-dir",
                    str(dirs["r1_contract"]),
                    "--r4-dry-run-dir",
                    str(dirs["r4_dry_run"]),
                    "--backup-repair-dir",
                    str(dirs["backup_repair"]),
                    "--history-import-dir",
                    str(dirs["history_import"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads(
                (evidence_dir / "persistent_profile_migration_summary_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "blocked")

    def test_probe_blocks_when_original_is_used_as_source(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "persistent_profile_migration_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            bad_guard = dirs["r4_dry_run"] / "persistent_original_profile_backup_restore_guard_packet.json"
            bad_guard.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "original_codex_used_as_source": True,
                        "original_codex_used_as_target": False,
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "migration_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--r1-contract-dir",
                    str(dirs["r1_contract"]),
                    "--r4-dry-run-dir",
                    str(dirs["r4_dry_run"]),
                    "--backup-repair-dir",
                    str(dirs["backup_repair"]),
                    "--history-import-dir",
                    str(dirs["history_import"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            false_green = json.loads(
                (evidence_dir / "persistent_profile_migration_false_green_audit.json").read_text()
            )
            independent = json.loads(
                (evidence_dir / "independent_persistent_profile_migration_audit.json").read_text()
            )
            self.assertEqual(false_green["status"], "blocked")
            self.assertEqual(independent["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
