# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.stronger_integrity_recheck_r1_probe import build_packets


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "stronger_integrity_recheck_r1_probe.py"


def _live_fixture(
    *,
    current_drift_status: str,
    all_unchanged: bool,
    baseline_final_verdict: str,
    windows_with_any_drift: int,
    drift_repeatability: str,
) -> dict[str, object]:
    current_drift = {
        "status": current_drift_status,
        "all_protected_surfaces_unchanged": all_unchanged,
    }
    baseline_summary = {
        "status": "ok",
        "final_verdict": baseline_final_verdict,
        "windows_with_any_drift": windows_with_any_drift,
        "drift_repeatability": drift_repeatability,
    }
    return {
        "protected_read": {"status": "ok"},
        "original_surface_read": {"status": "ok"},
        "original_inventory": {"status": "ok"},
        "native_integrity": {"status": "ok"},
        "original_scope": {"status": "ok"},
        "current_drift": current_drift,
        "idle_windows": [],
        "baseline_summary": baseline_summary,
        "bundle_boundary": {
            "status": "ok",
            "bundle_hash_observation_is_scope_only": True,
            "dyld_insert_libraries_present": False,
            "codesign_recheck_performed": False,
            "app_binary_sha256_recorded": True,
            "app_asar_sha256_recorded": False,
        },
    }


class StrongerIntegrityRecheckR1ProbeTests(unittest.TestCase):
    def test_build_packets_marks_clean_recheck_as_stronger_but_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(
                repo_root=ROOT,
                evidence_dir=Path(temp_dir),
                live=_live_fixture(
                    current_drift_status="ok",
                    all_unchanged=True,
                    baseline_final_verdict="ACTIVE_CURRENT_CODEX_BASELINE_STABLE",
                    windows_with_any_drift=0,
                    drift_repeatability="sporadic",
                ),
                repo_dirty_snapshot={
                    "status": "ok",
                    "repo_dirty_entry_count": 7,
                    "repo_dirty_under_protected_surface": False,
                    "repo_dirty_protected_like_entries": [],
                    "repo_dirty_counts_as_protected_codex_drift": False,
                },
            )

        protected = packets["protected_surface_recheck_packet.json"]
        self.assertEqual(protected["status"], "ok")
        self.assertEqual(protected["classification"], "clean_recheck_with_limits")
        self.assertTrue(protected["all_protected_surfaces_unchanged_in_current_recheck"])
        self.assertEqual(protected["attribution_class"], "no_drift_observed")
        self.assertTrue(protected["stronger_clean_recheck_observed"])
        self.assertFalse(protected["repo_dirty_counts_as_protected_codex_drift"])

        untouched = packets["original_codex_untouched_packet.json"]
        self.assertEqual(untouched["status"], "ok")
        self.assertEqual(
            untouched["classification"],
            "inspection_only_untouched_with_clean_recheck",
        )
        self.assertTrue(untouched["current_contour_non_mutation_observed"])
        self.assertFalse(untouched["current_contour_non_mutation_equals_global_untouched"])
        self.assertTrue(untouched["original_codex_untouched_within_admitted_scope"])
        self.assertTrue(untouched["bundle_hash_observed_scope_only"])
        self.assertFalse(untouched["bundle_hash_counts_as_full_runtime_integrity"])

        integrity = packets["integrity_strengthening_packet.json"]
        self.assertEqual(integrity["status"], "ok")
        self.assertEqual(
            integrity["current_integrity_classification"],
            "integrity_strengthened_with_clean_recheck_limits",
        )
        self.assertTrue(integrity["prior_integrity_limiter_reduced"])
        self.assertFalse(integrity["known_blocker_localized"])
        self.assertFalse(integrity["unknown_blocker_remains"])
        self.assertFalse(integrity["imported_safety_reproven_here"])
        self.assertFalse(integrity["full_integrity_claimed"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertEqual(false_green["status"], "ok")
        self.assertFalse(false_green["repo_dirt_treated_as_protected_codex_drift"])
        self.assertFalse(false_green["imported_safety_treated_as_reproven"])
        self.assertFalse(false_green["clean_scan_treated_as_full_integrity"])
        self.assertFalse(false_green["current_contour_non_mutation_treated_as_global_untouched"])
        self.assertFalse(false_green["bundle_hash_treated_as_full_runtime_integrity"])
        self.assertFalse(false_green["unknown_attribution_upgraded_to_stronger_integrity"])

    def test_build_packets_localizes_ambient_external_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(
                repo_root=ROOT,
                evidence_dir=Path(temp_dir),
                live=_live_fixture(
                    current_drift_status="blocked",
                    all_unchanged=False,
                    baseline_final_verdict="ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE",
                    windows_with_any_drift=2,
                    drift_repeatability="repeated",
                ),
                repo_dirty_snapshot={
                    "status": "ok",
                    "repo_dirty_entry_count": 3,
                    "repo_dirty_under_protected_surface": False,
                    "repo_dirty_protected_like_entries": [],
                    "repo_dirty_counts_as_protected_codex_drift": False,
                },
            )

        protected = packets["protected_surface_recheck_packet.json"]
        self.assertEqual(protected["classification"], "attribution_localized_with_limits")
        self.assertEqual(protected["attribution_class"], "ambient_external")
        self.assertFalse(protected["stronger_clean_recheck_observed"])

        integrity = packets["integrity_strengthening_packet.json"]
        self.assertEqual(
            integrity["current_integrity_classification"],
            "integrity_blocker_localized_as_ambient_external",
        )
        self.assertFalse(integrity["prior_integrity_limiter_reduced"])
        self.assertTrue(integrity["known_blocker_localized"])
        self.assertFalse(integrity["unknown_blocker_remains"])

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    temp_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 6)
            self.assertIn(
                summary["integrity_classification"],
                {
                    "integrity_strengthened_with_clean_recheck_limits",
                    "integrity_blocker_localized_as_ambient_external",
                    "integrity_remains_blocked_unknown_attribution",
                },
            )

            integrity = json.loads(
                (Path(temp_dir) / "integrity_strengthening_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                integrity["final_status"],
                "STRONGER_INTEGRITY_RECHECK_CLASSIFIED_WITH_LIMITS",
            )


if __name__ == "__main__":
    unittest.main()
