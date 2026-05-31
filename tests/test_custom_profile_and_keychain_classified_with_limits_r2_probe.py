# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.custom_profile_and_keychain_classified_with_limits_r2_probe import (
    DEFAULT_SOURCE_FILES,
    FINAL_STATUS_BLOCKED,
    FINAL_STATUS_OK,
    build_closeout,
    build_packets,
    overall_status,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CustomProfileAndKeychainClassifiedWithLimitsR2ProbeTests(unittest.TestCase):
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
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    def _source_paths(self, repo_root: Path) -> dict[str, str]:
        return {
            key: str((repo_root / relative_path).resolve())
            for key, relative_path in DEFAULT_SOURCE_FILES.items()
        }

    def _source_packets(self) -> dict[str, dict[str, object]]:
        return {
            "custom_profile_mode": {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "persistent_mode_is_contract_only": True,
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/profiles/wbp-custom-main",
                "profile_storage_persistence_claimed": False,
                "thread_history_preservation_claimed": False,
            },
            "profile_identity_contract": {
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/profiles/wbp-custom-main",
                "codex_home": "/profiles/wbp-custom-main",
                "user_data_dir": "/profiles/wbp-custom-main/electron-user-data",
                "same_profile_id_as_expected": True,
                "same_profile_root_as_expected": True,
                "silent_profile_switching_detected": False,
                "identity_counts_as_profile_storage_persistence": False,
                "identity_counts_as_thread_history_preservation": False,
            },
            "profile_path_authority": {
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/profiles/wbp-custom-main",
                "operator_explicit_profile_id_required": True,
                "profile_storage_persistence_claimed": False,
                "silent_profile_switching_allowed": False,
            },
            "profile_summary": {
                "status": "ok",
                "persistent_profile_identity_proven": True,
                "owner_visible_thread_continuity_classified": True,
                "profile_state_preservation_proven": False,
                "storage_level_thread_history_proven": False,
            },
            "profile_continuity": {
                "status": "ok",
                "persistent_profile_identity_proven": True,
                "original_codex_profile_non_dependency_proven": True,
                "owner_visible_thread_continuity_classified": True,
                "profile_state_preservation_proven": False,
                "storage_level_thread_history_proven": False,
                "relaunch_restoration_source_proven": False,
                "thread_history_preserved": False,
                "with_limits_required": True,
                "with_limits_reasons": [
                    "PROFILE_STATE_PRESERVATION_UNPROVEN",
                    "THREAD_HISTORY_STORAGE_PROVEN_FALSE",
                ],
            },
            "profile_identity_import": {
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/profiles/wbp-custom-main",
                "codex_home": "/profiles/wbp-custom-main",
                "user_data_dir": "/profiles/wbp-custom-main/electron-user-data",
                "same_profile_identity_across_relaunch": True,
                "same_profile_id_across_relaunch": True,
                "same_profile_root_across_relaunch": True,
                "same_codex_home_across_relaunch": True,
                "same_user_data_dir_across_relaunch": True,
                "silent_persistent_to_ephemeral_fallback_allowed": False,
                "silent_profile_switching_detected": False,
                "counts_as_daily_reliability_proof": False,
            },
            "storage_truth": {
                "status": "ok",
                "state_class_classified": True,
                "storage_surface_observed": True,
                "thread_history_candidate": True,
                "owner_visible_thread_counted_as_storage_proof": False,
                "storage_level_thread_history_proven": False,
                "thread_history_durable_proven": False,
                "relaunch_restoration_source_proven": False,
                "raw_thread_content_recorded": False,
            },
            "storage_inventory": {
                "status": "ok",
                "metadata_only": True,
                "observed_state_classes": ["thread_history", "user_settings"],
                "profile_root": "/profiles/wbp-custom-main",
                "profile_root_exists": True,
                "entry_count": 42,
                "raw_content_recorded": False,
                "raw_thread_content_recorded": False,
            },
            "profile_false_green": {"status": "ok"},
            "profile_independent_audit": {"status": "ok"},
            "keychain_behavior": {
                "status": "ok",
                "with_limits_required": True,
                "historical_pre_repair_prompt_observed": True,
                "current_live_prompt_behavior_proven": False,
                "auth_boundary_proven": False,
                "repaired_isolated_lane_repeated_prompt_observed": False,
                "persistent_profile_continuity_claimed": False,
                "with_limits_reasons": [
                    "CURRENT_LIVE_PROMPT_BEHAVIOR_NOT_REOBSERVED",
                ],
            },
            "keychain_summary": {
                "status": "ok",
                "current_live_prompt_behavior_proven": False,
                "auth_boundary_proven": False,
            },
            "keychain_owner_action": {
                "status": "ok",
                "owner_action_boundary_reference_only": True,
                "owner_action_performed_in_this_contour": False,
                "owner_allow_counted_as_auth_success": False,
                "owner_cancel_counted_as_machine_proof": False,
                "historical_destructive_dialog_interacted_with": False,
                "allowed_future_owner_actions": ["Cancel", "Allow", "Ignore", "Not Observed"],
            },
            "keychain_false_green": {"status": "ok"},
            "keychain_independent_audit": {"status": "ok"},
            "original_drift": {
                "status": "ok",
                "bounded_non_equivalence_explicit": True,
                "original_equivalence_claimed": False,
                "general_original_works_claimed": False,
                "broad_original_filesystem_innocence_claimed": False,
            },
            "original_reversibility": {
                "status": "ok",
                "reversibility_proven_on_declared_observed_surfaces_only": True,
                "route_observation_supporting_only": True,
                "general_original_works_claimed": False,
                "broad_original_filesystem_innocence_claimed": False,
            },
        }

    def test_build_packets_synthesizes_truthful_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass45"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=self._source_packets(),
                source_paths=self._source_paths(repo_root),
            )

            status, verdict = overall_status(packets)
            closeout = build_closeout(repo_root, evidence_dir, packets)

        self.assertEqual(status, "ok")
        self.assertEqual(verdict, FINAL_STATUS_OK)
        self.assertEqual(packets["custom_profile_identity_packet.json"]["classification"], "identity_path_only")
        self.assertTrue(
            packets["custom_profile_continuity_packet.json"][
                "owner_visible_thread_continuity_classified"
            ]
        )
        self.assertFalse(
            packets["custom_profile_storage_boundary_packet.json"][
                "thread_history_durable_proven"
            ]
        )
        self.assertTrue(
            packets["keychain_behavior_packet.json"]["current_keychain_behavior_unknown_bounded"]
        )
        self.assertFalse(
            packets["original_profile_non_equivalence_packet.json"][
                "original_equivalence_claimed"
            ]
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "ok")
        self.assertIn("final verdict: `WBP_CUSTOM_PROFILE_AND_KEYCHAIN_CLASSIFIED_WITH_LIMITS`", closeout)
        self.assertIn("resume from here: CLOSED", closeout)

    def test_build_packets_blocks_storage_keychain_and_original_overclaims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass45"
            sources = copy.deepcopy(self._source_packets())
            sources["profile_continuity"]["storage_level_thread_history_proven"] = True
            sources["keychain_behavior"]["current_live_prompt_behavior_proven"] = True
            sources["original_drift"]["original_equivalence_claimed"] = True
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        audit = packets["false_green_audit.json"]

        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(packets["custom_profile_continuity_packet.json"]["status"], "blocked")
        self.assertEqual(packets["keychain_behavior_packet.json"]["status"], "blocked")
        self.assertEqual(
            packets["original_profile_non_equivalence_packet.json"]["status"], "blocked"
        )
        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "custom_profile_continuity_packet.json.storage_level_thread_history_proven",
            audit["findings"],
        )
        self.assertIn(
            "keychain_behavior_packet.json.current_live_prompt_behavior_proven",
            audit["findings"],
        )
        self.assertIn(
            "original_profile_non_equivalence_packet.json.original_equivalence_claimed",
            audit["findings"],
        )

    def test_probe_reports_missing_source_packet(self) -> None:
        tool = REPO_ROOT / "tools" / "custom_profile_and_keychain_classified_with_limits_r2_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            for key, packet in self._source_packets().items():
                if key == "keychain_summary":
                    continue
                path = repo_root / DEFAULT_SOURCE_FILES[key]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(packet), encoding="utf-8")

            evidence_dir = (
                repo_root
                / "audit_results"
                / "wbp_custom_profile_and_keychain_classified_with_limits_r2_2026-05-27"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("required packet missing", result.stderr)
        self.assertFalse(evidence_dir.exists())


if __name__ == "__main__":
    unittest.main()
