# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.native_filesystem_probe import (
    classify_current_codex_delta,
    classify_user_data_dir_respected,
    diff_scans,
    scan_tree,
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


if __name__ == "__main__":
    unittest.main()
