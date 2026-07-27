# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.truth_tree_harness import (
    assert_declared_mutations_match,
    assert_no_truth_mutation,
    changed_truth_paths,
    snapshot_truth_tree,
)


class TruthTreeHarnessTests(unittest.TestCase):
    def test_snapshot_records_sha256_for_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "state.json"
            truth_file.write_text('{"ok": true}\n', encoding="utf-8")

            snapshot = snapshot_truth_tree({"state": truth_file})

        entry = snapshot["state"]
        self.assertTrue(entry["exists"])
        self.assertEqual(entry["kind"], "file")
        self.assertEqual(entry["size"], len('{"ok": true}\n'))
        self.assertIsInstance(entry["mtime_ns"], int)
        self.assertRegex(str(entry["sha256"]), r"^[0-9a-f]{64}$")

    def test_no_truth_mutation_passes_when_same(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "runtime-mode.txt"
            truth_file.write_text("managed\n", encoding="utf-8")

            before = snapshot_truth_tree({"mode": truth_file})
            after = snapshot_truth_tree({"mode": truth_file})

        assert_no_truth_mutation(before, after)
        self.assertEqual(changed_truth_paths(before, after), set())

    def test_mtime_only_change_is_advisory_not_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "runtime-mode.txt"
            truth_file.write_text("managed\n", encoding="utf-8")

            before = snapshot_truth_tree({"mode": truth_file})
            truth_file.touch()
            after = snapshot_truth_tree({"mode": truth_file})

        assert_no_truth_mutation(before, after)

    def test_no_truth_mutation_fails_on_same_size_content_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "runtime-mode.txt"
            truth_file.write_text("stable\n", encoding="utf-8")
            before = snapshot_truth_tree({"mode": truth_file})

            truth_file.write_text("mutate\n", encoding="utf-8")
            after = snapshot_truth_tree({"mode": truth_file})

        with self.assertRaisesRegex(AssertionError, "Unexpected truth-tree mutation"):
            assert_no_truth_mutation(before, after)

    def test_no_truth_mutation_fails_on_created_truth_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "supervisor-state.json"
            before = snapshot_truth_tree({"state": truth_file})

            truth_file.write_text("{}\n", encoding="utf-8")
            after = snapshot_truth_tree({"state": truth_file})

        with self.assertRaisesRegex(AssertionError, "Unexpected truth-tree mutation"):
            assert_no_truth_mutation(before, after)

    def test_no_truth_mutation_fails_on_deleted_truth_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "supervisor-state.json"
            truth_file.write_text("{}\n", encoding="utf-8")
            before = snapshot_truth_tree({"state": truth_file})

            truth_file.unlink()
            after = snapshot_truth_tree({"state": truth_file})

        with self.assertRaisesRegex(AssertionError, "Unexpected truth-tree mutation"):
            assert_no_truth_mutation(before, after)

    def test_declared_mutations_match_accepts_declared_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "config.toml"
            truth_file.write_text('base_url = "one"\n', encoding="utf-8")
            before = snapshot_truth_tree({"config": truth_file})

            truth_file.write_text('base_url = "two"\n', encoding="utf-8")
            after = snapshot_truth_tree({"config": truth_file})

            assert_declared_mutations_match(before, after, [str(truth_file)])

    def test_declared_mutations_match_rejects_undeclared_truth_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "config.toml"
            truth_file.write_text('base_url = "one"\n', encoding="utf-8")
            before = snapshot_truth_tree({"config": truth_file})

            truth_file.write_text('base_url = "two"\n', encoding="utf-8")
            after = snapshot_truth_tree({"config": truth_file})

        with self.assertRaisesRegex(
            AssertionError, "changed_files does not match truth-tree mutations"
        ):
            assert_declared_mutations_match(before, after, [])

    def test_declared_mutations_match_rejects_changed_file_outside_truth_scope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "config.toml"
            outside_file = root / "runtime.log"
            truth_file.write_text('base_url = "one"\n', encoding="utf-8")

            before = snapshot_truth_tree({"config": truth_file})
            after = snapshot_truth_tree({"config": truth_file})

        with self.assertRaisesRegex(AssertionError, "outside truth-tree scope"):
            assert_declared_mutations_match(before, after, [str(outside_file)])

    def test_directory_entry_change_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_dir = root / "stable"
            truth_dir.mkdir()
            before = snapshot_truth_tree({"stable_dir": truth_dir})

            (truth_dir / "codex-a.json").write_text("{}\n", encoding="utf-8")
            after = snapshot_truth_tree({"stable_dir": truth_dir})

        with self.assertRaisesRegex(AssertionError, "Unexpected truth-tree mutation"):
            assert_no_truth_mutation(before, after)

    def test_paths_outside_declared_truth_scope_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            truth_file = root / "config.toml"
            outside_file = root / "runtime.log"
            truth_file.write_text('base_url = "one"\n', encoding="utf-8")
            outside_file.write_text("before\n", encoding="utf-8")

            before = snapshot_truth_tree({"config": truth_file})
            outside_file.write_text("after\n", encoding="utf-8")
            after = snapshot_truth_tree({"config": truth_file})

        assert_no_truth_mutation(before, after)


if __name__ == "__main__":
    unittest.main()
