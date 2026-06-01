from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wild_boar_proxy import state_transaction


class StateTransactionTempCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store_root = self.root / "transactions"
        self.now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def work_root(self, transaction_id: str) -> Path:
        return self.store_root / f"{transaction_id}{state_transaction.TRANSACTION_WORK_DIR_SUFFIX}"

    def target_path(self, name: str = "state.json") -> Path:
        return (self.root / name).resolve(strict=False)

    def file_record(
        self,
        transaction_id: str,
        *,
        index: int = 0,
        target_name: str = "state.json",
        temp_path: Path | None = None,
        backup_path: Path | None = None,
        committed: bool = True,
        sha256_before: str | None = "before",
        sha256_after: str | None = "after",
    ) -> state_transaction.TransactionFileRecord:
        work_root = self.work_root(transaction_id)
        return state_transaction.TransactionFileRecord(
            target_path=str(self.target_path(target_name)),
            temp_path=str((temp_path or work_root / f"{index:04d}.tmp").resolve(strict=False)),
            backup_path=str((backup_path or work_root / f"{index:04d}.backup").resolve(strict=False)),
            sha256_before=sha256_before,
            sha256_after=sha256_after,
            committed=committed,
        )

    def metadata(
        self,
        transaction_id: str,
        *,
        state: str = state_transaction.TRANSACTION_COMMITTED,
        files: tuple[state_transaction.TransactionFileRecord, ...] | None = None,
        error: str | None = None,
    ) -> state_transaction.TransactionMetadata:
        default_files = (self.file_record(transaction_id),)
        if state == state_transaction.TRANSACTION_PREPARING and files is None:
            default_files = ()
        return state_transaction.TransactionMetadata(
            schema_version=state_transaction.TRANSACTION_METADATA_SCHEMA_VERSION,
            transaction_id=transaction_id,
            state=state,
            created_at_utc="2026-06-01T12:00:00+00:00",
            updated_at_utc="2026-06-01T12:01:00+00:00",
            transaction_root=str(self.root),
            files=default_files if files is None else files,
            error=error,
        )

    def write_metadata(
        self,
        transaction_id: str,
        *,
        state: str = state_transaction.TRANSACTION_COMMITTED,
        files: tuple[state_transaction.TransactionFileRecord, ...] | None = None,
        error: str | None = None,
    ) -> Path:
        metadata = self.metadata(transaction_id, state=state, files=files, error=error)
        metadata_path = state_transaction.transaction_metadata_path(self.store_root, transaction_id)
        state_transaction.write_transaction_metadata(metadata_path, metadata)
        return metadata_path

    def write_file(self, path: Path, payload: bytes = b"x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def set_mtime(self, path: Path, when: datetime) -> None:
        timestamp = when.timestamp()
        os.utime(path, (timestamp, timestamp), follow_symlinks=False)

    def test_cleanup_removes_only_stale_unreferenced_regular_files(self) -> None:
        transaction_id = "txn-cleanup"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        referenced_backup = self.write_file(Path(record.backup_path), b"backup")
        stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        young = self.write_file(self.work_root(transaction_id) / "recent.txt", b"recent")
        self.set_mtime(referenced_backup, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.set_mtime(young, self.now)

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.deleted_artifact_paths,
            (str(stale.resolve(strict=False)),),
        )
        self.assertEqual(result.skipped_artifact_paths, ())
        self.assertFalse(stale.exists())
        self.assertTrue(young.exists())
        self.assertTrue(referenced_backup.exists())

    def test_cleanup_never_removes_referenced_old_temp(self) -> None:
        transaction_id = "txn-referenced-temp"
        record = self.file_record(transaction_id, committed=False)
        referenced_temp = self.write_file(Path(record.temp_path), b"temp")
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_PREPARED,
            files=(record,),
        )
        self.set_mtime(referenced_temp, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertTrue(referenced_temp.exists())

    def test_cleanup_ignores_root_level_temp_outside_store(self) -> None:
        orphan = self.write_file(self.root / ".wbp-tmp-orphan", b"stale")
        self.set_mtime(orphan, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertTrue(orphan.exists())

    def test_cleanup_ignores_unrelated_nested_dirs_inside_store(self) -> None:
        extra_dir = self.store_root / "unrelated-dir"
        orphan = self.write_file(extra_dir / "old.tmp", b"old")
        self.set_mtime(orphan, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertTrue(orphan.exists())

    def test_cleanup_blocks_when_incomplete_transaction_present(self) -> None:
        transaction_id = "txn-incomplete"
        record = self.file_record(transaction_id, committed=False)
        stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_PREPARED,
            files=(record,),
        )
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertIn(transaction_id, result.incomplete_transaction_ids)
        self.assertTrue(stale.exists())

    def test_cleanup_blocks_when_recoverable_transaction_present(self) -> None:
        transaction_id = "txn-recoverable"
        record = self.file_record(transaction_id, committed=False)
        stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            files=(record,),
            error="recoverable failure",
        )
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertIn(transaction_id, result.recoverable_transaction_ids)
        self.assertTrue(stale.exists())

    def test_cleanup_blocks_when_failed_blocked_transaction_present(self) -> None:
        transaction_id = "txn-blocked"
        record = self.file_record(transaction_id, committed=False)
        stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_FAILED_BLOCKED,
            files=(record,),
            error="blocked failure",
        )
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertIn(transaction_id, result.blocked_transaction_ids)
        self.assertTrue(stale.exists())

    def test_cleanup_blocks_when_invalid_metadata_present(self) -> None:
        self.store_root.mkdir()
        metadata_path = self.store_root / "txn-invalid.transaction.json"
        metadata_path.write_text("{not-json", encoding="utf-8")

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertEqual(
            result.invalid_metadata_paths,
            (str(metadata_path.resolve(strict=False)),),
        )

    def test_cleanup_blocks_when_symlink_artifact_present(self) -> None:
        transaction_id = "txn-symlink"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        outside_target = self.write_file(self.root / "outside.txt", b"outside")
        symlink_path = self.work_root(transaction_id) / "rogue.tmp"
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        symlink_path.symlink_to(outside_target)

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(result.cleanup_blocked)
        self.assertEqual(result.deleted_artifact_paths, ())
        self.assertIn(transaction_id, result.blocked_transaction_ids)
        self.assertTrue(symlink_path.is_symlink())

    def test_cleanup_never_deletes_metadata_files_or_directories(self) -> None:
        transaction_id = "txn-keep-metadata"
        record = self.file_record(transaction_id)
        metadata_path = self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_transaction.cleanup_transaction_store_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(result.deleted_artifact_paths, (str(stale.resolve(strict=False)),))
        self.assertTrue(metadata_path.exists())
        self.assertTrue(self.work_root(transaction_id).exists())
        self.assertTrue(self.work_root(transaction_id).is_dir())

    def test_cleanup_result_dataclass_is_not_command_packet(self) -> None:
        cleanup_fields = set(state_transaction.TransactionTempCleanupResult.__dataclass_fields__)
        forbidden = {
            "auto_recovered",
            "changed_files",
            "effect",
            "exit_code",
            "human_message",
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
