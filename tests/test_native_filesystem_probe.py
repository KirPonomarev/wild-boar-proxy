# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.native_filesystem_probe import (
    classify_fresh_context_entry,
    classify_quiescent_handoff_admission,
    classify_quiescent_current_codex_precondition,
    classify_current_codex_delta,
    classify_user_data_dir_respected,
    diff_scans,
    scan_tree,
    summarize_idle_baseline_windows,
)


class NativeFilesystemProbeTests(unittest.TestCase):
    def test_recursive_scan_and_diff_report_created_deleted_and_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            before_root = root / "before"
            after_root = root / "after"
            (before_root / "dir").mkdir(parents=True)
            (after_root / "dir").mkdir(parents=True)
            (before_root / "same.txt").write_text("same\n", encoding="utf-8")
            (after_root / "same.txt").write_text("same\n", encoding="utf-8")
            (before_root / "dir" / "changed.txt").write_text("old\n", encoding="utf-8")
            (after_root / "dir" / "changed.txt").write_text("new\n", encoding="utf-8")
            (before_root / "deleted.txt").write_text("gone\n", encoding="utf-8")
            (after_root / "created.txt").write_text("fresh\n", encoding="utf-8")

            diff = diff_scans(scan_tree(before_root), scan_tree(after_root))

        self.assertIn("created.txt", diff["created"])
        self.assertIn("deleted.txt", diff["deleted"])
        changed_paths = {entry["relative_path"] for entry in diff["changed"]}
        self.assertIn("dir/changed.txt", changed_paths)

    def test_user_data_dir_respected_requires_owned_writes_and_unchanged_defaults(self) -> None:
        blocked = classify_user_data_dir_respected(
            custom_process_observed=True,
            owned_writes_present=False,
            protected_surfaces_changed=False,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["reason_class"], "WRITE_ATTRIBUTION_AMBIGUOUS")
        self.assertFalse(blocked["user_data_dir_respected"])

        ok = classify_user_data_dir_respected(
            custom_process_observed=True,
            owned_writes_present=True,
            protected_surfaces_changed=False,
        )
        self.assertEqual(ok["status"], "ok")
        self.assertTrue(ok["user_data_dir_respected"])

    def test_default_surface_change_blocks_even_with_owned_writes(self) -> None:
        blocked = classify_user_data_dir_respected(
            custom_process_observed=True,
            owned_writes_present=True,
            protected_surfaces_changed=True,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["reason_class"], "DEFAULT_PROTECTED_SURFACES_CHANGED")
        self.assertFalse(blocked["user_data_dir_respected"])

    def test_current_codex_delta_marks_missing_root_pid_as_touched(self) -> None:
        packet = classify_current_codex_delta(
            {
                "root_app_pids": [100, 200],
                "default_process_lines": ["100 Codex", "gpu default"],
            },
            {
                "root_app_pids": [200],
                "default_process_lines": ["200 Codex", "gpu default"],
            },
        )
        self.assertTrue(packet["current_codex_touched"])
        self.assertEqual(packet["missing_root_app_pids"], [100])

    def test_idle_baseline_summary_marks_unstable_when_repeated_drift_present(self) -> None:
        windows = [
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {
                    "surfaces": {
                        "codex_dir": {
                            "diff": {
                                "changed": [{"relative_path": "logs_2.sqlite"}],
                                "created": [],
                                "deleted": [],
                            }
                        }
                    }
                },
            },
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {
                    "surfaces": {
                        "codex_dir": {
                            "diff": {
                                "changed": [{"relative_path": "logs_2.sqlite"}],
                                "created": [],
                                "deleted": [],
                            }
                        }
                    }
                },
            },
        ]
        summary = summarize_idle_baseline_windows(windows)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_verdict"], "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE")
        self.assertTrue(summary["quiescent_current_codex_precondition_required"])
        self.assertEqual(summary["drift_repeatability"], "repeated")

    def test_idle_baseline_summary_requires_quiescent_precondition_when_active_drift_present(
        self,
    ) -> None:
        windows = [
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {
                    "surfaces": {
                        "default_app_support_codex": {
                            "diff": {
                                "changed": [{"relative_path": "sentry/scope_v3.json"}],
                                "created": [],
                                "deleted": [],
                            }
                        }
                    }
                },
            },
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {"surfaces": {}},
            },
        ]
        summary = summarize_idle_baseline_windows(windows)
        self.assertEqual(summary["final_verdict"], "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE")
        self.assertTrue(summary["quiescent_current_codex_precondition_required"])
        self.assertEqual(summary["drift_repeatability"], "sporadic")

    def test_idle_baseline_contour_does_not_overclaim_filesystem_pass(self) -> None:
        summary = summarize_idle_baseline_windows(
            [
                {
                    "current_codex_delta": {"current_codex_touched": False},
                    "protected_surface_recursive_diff": {"surfaces": {}},
                }
            ]
        )
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["final_verdict"], "INSUFFICIENT_OBSERVATION")
        self.assertEqual(summary["drift_repeatability"], "insufficient")

    def test_quiescent_precondition_packet_blocks_when_default_codex_processes_present(
        self,
    ) -> None:
        packet = classify_quiescent_current_codex_precondition(
            {
                "root_app_pids": [41266],
                "default_process_count": 4,
                "custom_process_count": 0,
                "default_process_lines": ["gpu", "renderer"],
            }
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "CURRENT_CODEX_NOT_QUIESCENT")
        self.assertFalse(packet["quiescent_current_codex_precondition_satisfied"])
        self.assertIn("ROOT_APP_PID_PRESENT", packet["precondition_failures"])
        self.assertIn("DEFAULT_CODEX_PROCESS_PRESENT", packet["precondition_failures"])

    def test_quiescent_precondition_packet_passes_when_no_default_processes_present(
        self,
    ) -> None:
        packet = classify_quiescent_current_codex_precondition(
            {
                "root_app_pids": [],
                "default_process_count": 0,
                "custom_process_count": 0,
                "default_process_lines": [],
            }
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["reason_class"], "")
        self.assertTrue(packet["quiescent_current_codex_precondition_satisfied"])

    def test_quiescent_handoff_blocks_without_operator_admission(self) -> None:
        packet = classify_quiescent_handoff_admission(
            operator_action_performed=False,
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
            host_process_chain=[{"command": "/usr/bin/python3"}],
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "QUIESCENT_HANDOFF_NOT_ADMITTED")
        self.assertFalse(packet["same_thread_admissible"])
        self.assertFalse(packet["fresh_context_required"])

    def test_quiescent_handoff_classifies_fresh_context_requirement(self) -> None:
        packet = classify_quiescent_handoff_admission(
            operator_action_performed=False,
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
            host_process_chain=[
                {"command": "/Applications/Codex.app/Contents/Resources/codex app-server"},
                {"command": "/Applications/Codex.app/Contents/MacOS/Codex"},
            ],
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "QUIESCENT_HANDOFF_REQUIRES_FRESH_CONTEXT")
        self.assertFalse(packet["same_thread_admissible"])
        self.assertTrue(packet["fresh_context_required"])

    def test_quiescent_handoff_does_not_attempt_live_launch(self) -> None:
        packet = classify_quiescent_handoff_admission(
            operator_action_performed=True,
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": True
            },
            host_process_chain=[{"command": "/usr/bin/python3"}],
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "QUIESCENT_HANDOFF_ADMISSIBLE")
        self.assertTrue(packet["same_thread_admissible"])
        self.assertFalse(packet["fresh_context_required"])

    def test_fresh_context_entry_blocks_when_hosted_by_protected_codex(self) -> None:
        packet = classify_fresh_context_entry(
            host_process_chain=[
                {"command": "/Applications/Codex.app/Contents/Resources/codex app-server"},
                {"command": "/Applications/Codex.app/Contents/MacOS/Codex"},
            ],
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "FRESH_CONTEXT_NOT_ESTABLISHED")
        self.assertFalse(packet["fresh_context_verified"])
        self.assertFalse(packet["phase7_retry_admissible"])

    def test_fresh_context_entry_blocks_when_quiescent_precondition_fails(self) -> None:
        packet = classify_fresh_context_entry(
            host_process_chain=[{"command": "/usr/bin/python3"}],
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "QUIESCENT_PRECONDITION_STILL_FAILED")
        self.assertTrue(packet["fresh_context_verified"])
        self.assertFalse(packet["phase7_retry_admissible"])

    def test_fresh_context_entry_does_not_attempt_live_launch(self) -> None:
        packet = classify_fresh_context_entry(
            host_process_chain=[{"command": "/usr/bin/python3"}],
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": True
            },
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "FRESH_CONTEXT_ENTRY_ADMISSIBLE")
        self.assertTrue(packet["phase7_retry_admissible"])


if __name__ == "__main__":
    unittest.main()
