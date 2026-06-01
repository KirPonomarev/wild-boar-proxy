from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_temp_prefix


class StateTempPrefixCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def no_follow(self, path: Path) -> str:
        return str(Path(os.path.abspath(os.path.normpath(os.fspath(path)))))

    def write_file(self, path: Path, payload: bytes = b"x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def set_mtime(self, path: Path, when: datetime) -> None:
        timestamp = when.timestamp()
        os.utime(path, (timestamp, timestamp), follow_symlinks=False)

    def test_missing_admitted_root_is_noop_and_does_not_create_dir(self) -> None:
        missing_root = self.root / "missing-root"

        with (
            mock.patch.object(Path, "mkdir") as mkdir,
            mock.patch.object(Path, "rmdir") as rmdir,
            mock.patch.object(state_temp_prefix.os, "replace") as replace,
        ):
            result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
                (missing_root,),
                now=self.now,
                stale_ttl_seconds=60,
            )

        self.assertEqual(result.deleted_paths, ())
        self.assertEqual(result.skipped_paths, ())
        self.assertEqual(result.stale_paths, ())
        self.assertEqual(result.fresh_paths, ())
        self.assertFalse(result.cleanup_performed)
        self.assertFalse(result.cleanup_blocked)
        self.assertFalse(missing_root.exists())
        mkdir.assert_not_called()
        rmdir.assert_not_called()
        replace.assert_not_called()

    def test_non_absolute_root_raises_invalid_error(self) -> None:
        with self.assertRaises(state_temp_prefix.StateTempPrefixError) as raised:
            state_temp_prefix.cleanup_prefixed_temp_artifacts(
                (Path("relative-root"),),
                now=self.now,
                stale_ttl_seconds=60,
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_temp_prefix.STATE_TEMP_PREFIX_INVALID,
        )

    def test_stale_direct_child_is_deleted_and_fresh_is_preserved(self) -> None:
        stale = self.write_file(self.root / ".wbp-tmp-stale.state.json", b"old")
        fresh = self.write_file(self.root / ".wbp-tmp-fresh.state.json", b"new")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.set_mtime(fresh, self.now)

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_paths, (self.no_follow(stale),))
        self.assertEqual(result.skipped_paths, ())
        self.assertEqual(result.stale_paths, (self.no_follow(stale),))
        self.assertEqual(result.fresh_paths, (self.no_follow(fresh),))
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())

    def test_duplicate_roots_are_deduped_for_cleanup(self) -> None:
        stale = self.write_file(self.root / ".wbp-tmp-stale.state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (self.root, self.root),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_paths, (self.no_follow(stale),))
        self.assertEqual(result.skipped_paths, ())
        self.assertFalse(stale.exists())

    def test_non_directory_root_blocks_all_mutation(self) -> None:
        file_root = self.write_file(self.root / "state.json", b"{}")
        valid_root = self.root / "valid-root"
        stale = self.write_file(valid_root / ".wbp-tmp-stale.state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (valid_root, file_root),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_paths, ())
        self.assertEqual(result.invalid_roots, (self.no_follow(file_root),))
        self.assertTrue(stale.exists())

    def test_symlink_root_blocks_all_mutation(self) -> None:
        valid_root = self.root / "valid-root"
        stale = self.write_file(valid_root / ".wbp-tmp-stale.state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        symlink_root = self.root / "symlink-root"
        symlink_root.symlink_to(valid_root, target_is_directory=True)

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (valid_root, symlink_root),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_paths, ())
        self.assertEqual(result.invalid_roots, (self.no_follow(symlink_root),))
        self.assertTrue(stale.exists())

    def test_matching_symlink_child_blocks_all_mutation(self) -> None:
        stale = self.write_file(self.root / ".wbp-tmp-stale.state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        outside_target = self.write_file(self.root / "outside.txt", b"outside")
        blocked = self.root / ".wbp-tmp-link.state.json"
        blocked.symlink_to(outside_target)

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_paths, ())
        self.assertEqual(result.skipped_paths, (self.no_follow(stale),))
        self.assertEqual(result.blocked_paths, (self.no_follow(blocked),))
        self.assertTrue(stale.exists())
        self.assertTrue(blocked.is_symlink())

    def test_matching_directory_child_blocks_all_mutation_without_rmdir(self) -> None:
        stale = self.write_file(self.root / ".wbp-tmp-stale.state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        blocked_dir = self.root / ".wbp-tmp-dir"
        blocked_dir.mkdir()

        with mock.patch.object(Path, "rmdir") as rmdir:
            result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
                (self.root,),
                now=self.now,
                stale_ttl_seconds=60,
            )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_paths, ())
        self.assertEqual(result.blocked_paths, (self.no_follow(blocked_dir),))
        self.assertTrue(stale.exists())
        self.assertTrue(blocked_dir.exists())
        rmdir.assert_not_called()

    def test_non_matching_siblings_and_nested_prefixed_entries_are_ignored(self) -> None:
        self.write_file(self.root / "ordinary.txt", b"ordinary")
        nested = self.root / "nested"
        nested_stale = self.write_file(nested / ".wbp-tmp-nested.state.json", b"nested")
        self.set_mtime(nested_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_paths, ())
        self.assertEqual(result.stale_paths, ())
        self.assertTrue(nested_stale.exists())

    def test_transactions_root_allows_metadata_sibling_cleanup_but_ignores_work_dir_internals(self) -> None:
        transactions_root = self.root / "transactions"
        metadata_stale = self.write_file(
            transactions_root / ".wbp-tmp-txn.transaction.json",
            b"metadata-temp",
        )
        nested_stale = self.write_file(
            transactions_root / "txn-1.files" / ".wbp-tmp-inside-workdir",
            b"nested-temp",
        )
        self.set_mtime(metadata_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.set_mtime(nested_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_temp_prefix.cleanup_prefixed_temp_artifacts(
            (transactions_root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_paths, (self.no_follow(metadata_stale),))
        self.assertFalse(metadata_stale.exists())
        self.assertTrue(nested_stale.exists())

    def test_cleanup_result_dataclass_does_not_expose_packet_fields(self) -> None:
        cleanup_fields = set(state_temp_prefix.PrefixedTempCleanupResult.__dataclass_fields__)
        forbidden = {
            "auto_recovered",
            "changed_files",
            "effect",
            "exit_code",
            "human_message",
            "liveness",
            "next_action",
            "operator_action",
            "repair_required",
            "rollback_available",
            "rollback_id",
            "severity",
            "startup_clean",
            "status",
        }
        self.assertTrue(forbidden.isdisjoint(cleanup_fields))


if __name__ == "__main__":
    unittest.main()
