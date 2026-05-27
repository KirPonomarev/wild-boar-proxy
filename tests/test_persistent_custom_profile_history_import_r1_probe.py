# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PersistentCustomProfileHistoryImportR1ProbeTests(unittest.TestCase):
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
            "r2_enforcement": root / "audit_results" / "r2",
            "r2b_live": root / "audit_results" / "r2b",
            "r2c_continuity": root / "audit_results" / "r2c",
            "r3_storage": root / "audit_results" / "r3",
            "r4_schema": root / "audit_results" / "r4",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        base_identity = {
            "status": "ok",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": "/tmp/wbp-custom-main",
            "codex_home": "/tmp/wbp-custom-main",
            "user_data_dir": "/tmp/wbp-custom-main/electron-user-data",
            "same_profile_id_as_expected": True,
            "same_profile_root_as_expected": True,
            "silent_profile_switching_detected": False,
        }
        self._write_json(
            root,
            "audit_results/r1/persistent_profile_identity_contract_packet.json",
            {
                **base_identity,
                "phase": "launcher_contract_readiness",
            },
        )
        self._write_json(
            root,
            "audit_results/r1/persistent_cleanup_retention_policy_packet.json",
            {
                "status": "ok",
                "persistent_history_delete_allowed_by_default": False,
                "ordinary_cleanup_must_preserve_history": True,
                "explicit_owner_delete_authorization_required": True,
            },
        )
        self._write_json(
            root,
            "audit_results/r1/persistent_concurrent_launch_policy_packet.json",
            {
                "status": "ok",
                "policy": "single_writer_only",
                "launcher_enforces_policy": True,
                "same_profile_multi_writer_allowed": False,
                "state_consistency_risk_classified": True,
                "lock_path": "/tmp/wbp-custom-main/.wbp-profile.lock",
            },
        )
        self._write_json(
            root,
            "audit_results/r1/original_codex_profile_non_dependency_packet.json",
            {
                "status": "ok",
                "original_codex_profile_dependency": False,
                "original_codex_profile_used_as_custom_shortcut": False,
                "original_codex_profile_mutated": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r1/persistent_launcher_contract_packet.json",
            {
                "status": "ok",
                "persistent_profile_state_write_allowed": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r1/persistent_launcher_readiness_summary_packet.json",
            {"status": "ok"},
        )

        self._write_json(
            root,
            "audit_results/r2/persistent_no_silent_fallback_packet.json",
            {
                "status": "ok",
                "silent_persistent_to_ephemeral_fallback_allowed": False,
                "fallback_rejected": True,
            },
        )
        self._write_json(
            root,
            "audit_results/r2/persistent_launcher_enforcement_contract_packet.json",
            {"status": "ok"},
        )
        self._write_json(
            root,
            "audit_results/r2/persistent_launcher_enforcement_summary_packet.json",
            {"status": "ok"},
        )

        self._write_json(
            root,
            "audit_results/r2b/persistent_custom_profile_contract_packet.json",
            {
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/tmp/wbp-custom-main",
                "codex_home": "/tmp/wbp-custom-main",
                "user_data_dir": "/tmp/wbp-custom-main/electron-user-data",
                "profile_mode": "persistent_custom",
                "history_persistence_expected": True,
                "original_codex_profile_runtime_dependency": False,
                "browser_client_path_authority": False,
                "remote_client_path_authority": False,
                "cleanup_deletes_persistent_profile_by_default": False,
            },
        )
        for rel, phase in (
            ("persistent_custom_profile_before_bounded_manifest.json", "before"),
            ("persistent_custom_profile_after_owner_action_bounded_manifest.json", "after_owner_action"),
            ("persistent_custom_profile_after_relaunch_bounded_manifest.json", "after_relaunch"),
        ):
            self._write_json(
                root,
                f"audit_results/r2b/{rel}",
                {
                    "status": "ok",
                    "phase": phase,
                    "root": "/tmp/wbp-custom-main",
                    "profile_fingerprint_sha256": f"sha-{phase}",
                    "entry_count": 10,
                    "state_class_counts": {"thread_history": 1},
                    "counts": {"files": 10},
                    "max_mtime_ns": 1,
                    "total_file_bytes": 10,
                    "exists": True,
                    "full_entry_list_recorded": False,
                    "raw_content_recorded": False,
                },
            )
        self._write_json(
            root,
            "audit_results/r2b/persistent_r2b_profile_state_preservation_packet.json",
            {
                "status": "blocked",
                "profile_state_preserved": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r2b/persistent_r2b_thread_history_preservation_packet.json",
            {
                "status": "blocked",
                "thread_history_preserved": False,
                "visible_thread_context_only": True,
            },
        )
        self._write_json(
            root,
            "audit_results/r2b/persistent_cleanup_policy_packet.json",
            {
                "status": "ok",
                "cleanup_deletes_persistent_profile_by_default": False,
                "profile_exists_after_cleanup": True,
            },
        )
        self._write_json(
            root,
            "audit_results/r2b/integration_ownership_baseline_packet.json",
            {
                "status": "ok",
                "classification_scope": "baseline_only",
                "integration_classes": ["unclassified"],
                "integration_persistence_proven": False,
                "integration_parity_claimed": False,
                "original_codex_integration_state_runtime_dependency": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r2b/original_codex_profile_drift_packet.json",
            {
                "status": "blocked",
                "reason_class": "ORIGINAL_CODEX_PROTECTED_SURFACE_DRIFT",
                "all_protected_surfaces_unchanged": False,
                "original_codex_write_performed_by_contour": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r2b/persistent_custom_profile_history_r2b_summary_packet.json",
            {
                "status": "blocked",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN",
            },
        )
        self._write_json(
            root,
            "audit_results/r2b/r2b_owner_action_boundary_packet.json",
            {"status": "ok"},
        )

        self._write_json(
            root,
            "audit_results/r2c/r2c_profile_identity_before_packet.json",
            {**base_identity, "phase": "r2c_before"},
        )
        self._write_json(
            root,
            "audit_results/r2c/r2c_profile_identity_relaunch_packet.json",
            {**base_identity, "phase": "r2c_relaunch"},
        )
        self._write_json(
            root,
            "audit_results/r2c/r2c_thread_continuity_classification_packet.json",
            {
                "status": "ok",
                "owner_visible_thread_continuity_classified": True,
                "same_nonce_thread_visible": True,
                "same_persistent_profile_identity": True,
                "storage_level_thread_history_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r2c/r2c_storage_context_packet.json",
            {
                "status": "ok",
                "storage_level_thread_history_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r2c/r2c_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_CLASSIFIED_WITH_STORAGE_UNPROVEN",
            },
        )
        self._write_json(
            root,
            "audit_results/r2c/r2c_prior_r2b_reference_packet.json",
            {
                "status": "ok",
                "prior_final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN",
                "prior_profile_state_preserved": False,
                "prior_thread_history_preserved": False,
            },
        )
        for rel, phase in (
            ("r2c_bounded_profile_manifest_before_packet.json", "r2c_before"),
            ("r2c_bounded_profile_manifest_after_first_action_packet.json", "r2c_after_first_action"),
            ("r2c_bounded_profile_manifest_relaunch_packet.json", "r2c_after_relaunch"),
        ):
            self._write_json(
                root,
                f"audit_results/r2c/{rel}",
                {
                    "status": "ok",
                    "phase": phase,
                    "root": "/tmp/wbp-custom-main",
                    "profile_fingerprint_sha256": f"sha-{phase}",
                    "entry_count": 20,
                    "state_class_counts": {"thread_history": 2, "session_state": 1},
                    "counts": {"files": 20},
                    "max_mtime_ns": 2,
                    "total_file_bytes": 20,
                    "exists": True,
                    "full_entry_list_recorded": False,
                    "raw_content_recorded": False,
                },
            )

        self._write_json(
            root,
            "audit_results/r3/persistent_storage_truth_classification_packet.json",
            {
                "status": "ok",
                "state_class_classified": True,
                "storage_level_thread_history_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r3/persistent_relaunch_restoration_source_packet.json",
            {
                "status": "ok",
                "local_storage_restoration_source_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r3/persistent_storage_r3_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_STORAGE_TRUTH_CLASSIFIED_WITH_LIMITS",
            },
        )

        self._write_json(
            root,
            "audit_results/r4/persistent_storage_restoration_hypothesis_packet.json",
            {
                "status": "ok",
                "durable_restoration_proven": False,
                "storage_level_thread_history_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/r4/persistent_storage_candidate_selection_packet.json",
            {
                "status": "ok",
                "metadata_only": True,
            },
        )
        self._write_json(
            root,
            "audit_results/r4/persistent_storage_r4_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_HYPOTHESES_CLASSIFIED_WITH_LIMITS",
            },
        )
        return dirs

    def test_probe_classifies_with_limits_from_consistent_source_chain(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "persistent_custom_profile_history_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "persistent_profile_import"

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
                    "--r2-enforcement-dir",
                    str(dirs["r2_enforcement"]),
                    "--r2b-live-dir",
                    str(dirs["r2b_live"]),
                    "--r2c-continuity-dir",
                    str(dirs["r2c_continuity"]),
                    "--r3-storage-dir",
                    str(dirs["r3_storage"]),
                    "--r4-schema-dir",
                    str(dirs["r4_schema"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "persistent_profile_summary_packet.json").read_text()
            )
            classification = json.loads(
                (
                    evidence_dir
                    / "persistent_profile_continuity_classification_packet.json"
                ).read_text()
            )
            drift = json.loads(
                (evidence_dir / "original_codex_profile_drift_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED_WITH_LIMITS",
            )
            self.assertTrue(classification["bounded_persistent_profile_continuity_classified"])
            self.assertFalse(classification["storage_level_thread_history_proven"])
            self.assertEqual(drift["status"], "ok")
            self.assertFalse(drift["declared_observed_surface_drift_clean"])

    def test_probe_blocks_when_identity_chain_is_inconsistent(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "persistent_custom_profile_history_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            bad_identity = dirs["r2c_continuity"] / "r2c_profile_identity_relaunch_packet.json"
            bad_identity.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "persistent_profile_id": "other-profile",
                        "persistent_profile_root": "/tmp/other-profile",
                        "codex_home": "/tmp/other-profile",
                        "user_data_dir": "/tmp/other-profile/electron-user-data",
                        "same_profile_id_as_expected": False,
                        "same_profile_root_as_expected": False,
                        "silent_profile_switching_detected": True,
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "persistent_profile_import"

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
                    "--r2-enforcement-dir",
                    str(dirs["r2_enforcement"]),
                    "--r2b-live-dir",
                    str(dirs["r2b_live"]),
                    "--r2c-continuity-dir",
                    str(dirs["r2c_continuity"]),
                    "--r3-storage-dir",
                    str(dirs["r3_storage"]),
                    "--r4-schema-dir",
                    str(dirs["r4_schema"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads(
                (evidence_dir / "persistent_profile_summary_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "blocked")

    def test_probe_blocks_when_relaunch_codex_home_diverges(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "persistent_custom_profile_history_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            relaunch = dirs["r2c_continuity"] / "r2c_profile_identity_relaunch_packet.json"
            packet = json.loads(relaunch.read_text())
            packet["codex_home"] = "/tmp/wbp-custom-main-diverged"
            relaunch.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "persistent_profile_import"

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
                    "--r2-enforcement-dir",
                    str(dirs["r2_enforcement"]),
                    "--r2b-live-dir",
                    str(dirs["r2b_live"]),
                    "--r2c-continuity-dir",
                    str(dirs["r2c_continuity"]),
                    "--r3-storage-dir",
                    str(dirs["r3_storage"]),
                    "--r4-schema-dir",
                    str(dirs["r4_schema"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            identity = json.loads(
                (evidence_dir / "persistent_custom_profile_identity_packet.json").read_text()
            )
            self.assertEqual(identity["status"], "blocked")
            self.assertFalse(identity["same_codex_home_across_relaunch"])


if __name__ == "__main__":
    unittest.main()
