from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_transaction


class StateTransactionTempInspectionTests(unittest.TestCase):
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

    def test_missing_store_is_clean_and_does_not_write(self) -> None:
        with (
            mock.patch.object(state_transaction.state_store, "write_json") as write_json,
            mock.patch.object(state_transaction.state_store, "write_text") as write_text,
            mock.patch.object(Path, "unlink") as unlink,
            mock.patch.object(Path, "rmdir") as rmdir,
            mock.patch.object(state_transaction.os, "replace") as replace,
        ):
            inspection = state_transaction.inspect_transaction_temp_artifacts(
                self.root,
                now=self.now,
                stale_ttl_seconds=60,
            )

        self.assertTrue(inspection.is_clean)
        self.assertFalse(self.store_root.exists())
        write_json.assert_not_called()
        write_text.assert_not_called()
        unlink.assert_not_called()
        rmdir.assert_not_called()
        replace.assert_not_called()

    def test_empty_store_is_clean(self) -> None:
        self.store_root.mkdir()

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(inspection.is_clean)
        self.assertEqual(inspection.artifacts, ())

    def test_root_level_temp_outside_store_is_ignored(self) -> None:
        orphan = self.write_file(self.root / ".wbp-tmp-orphan", b"stale")
        self.set_mtime(orphan, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(inspection.is_clean)
        self.assertNotIn(str(orphan.resolve(strict=False)), inspection.unreferenced_artifact_paths)
        self.assertNotIn(str(orphan.resolve(strict=False)), inspection.stale_artifact_paths)

    def test_unrelated_nested_dir_inside_store_is_ignored(self) -> None:
        extra_dir = self.store_root / "unrelated-dir"
        self.write_file(extra_dir / "old.tmp", b"extra")

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(inspection.is_clean)
        self.assertEqual(inspection.unreferenced_artifact_paths, ())

    def test_committed_backup_evidence_is_clean_and_referenced(self) -> None:
        transaction_id = "txn-clean"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        backup = self.write_file(Path(record.backup_path), b"old")
        self.set_mtime(backup, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertTrue(inspection.is_clean)
        self.assertEqual(
            inspection.referenced_artifact_paths,
            (record.temp_path, record.backup_path),
        )
        self.assertEqual(inspection.unreferenced_artifact_paths, ())
        artifacts = {artifact.path: artifact for artifact in inspection.artifacts}
        self.assertFalse(artifacts[record.temp_path].exists)
        self.assertTrue(artifacts[record.temp_path].referenced)
        self.assertTrue(artifacts[record.backup_path].exists)
        self.assertFalse(artifacts[record.backup_path].stale)

    def test_referenced_old_temp_is_not_stale(self) -> None:
        transaction_id = "txn-incomplete"
        record = self.file_record(transaction_id, committed=False)
        temp_path = self.write_file(Path(record.temp_path), b"temp")
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_PREPARED,
            files=(record,),
        )
        self.set_mtime(temp_path, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertIn(transaction_id, inspection.incomplete_transaction_ids)
        self.assertNotIn(record.temp_path, inspection.stale_artifact_paths)
        artifacts = {artifact.path: artifact for artifact in inspection.artifacts}
        self.assertTrue(artifacts[record.temp_path].referenced)
        self.assertFalse(artifacts[record.temp_path].stale)

    def test_unreferenced_old_artifact_becomes_stale(self) -> None:
        transaction_id = "txn-stale"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        extra = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old-temp")
        self.set_mtime(extra, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertFalse(inspection.is_clean)
        self.assertIn(str(extra.resolve(strict=False)), inspection.unreferenced_artifact_paths)
        self.assertIn(str(extra.resolve(strict=False)), inspection.stale_artifact_paths)

    def test_unreferenced_young_artifact_is_not_stale(self) -> None:
        transaction_id = "txn-young"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        extra = self.write_file(self.work_root(transaction_id) / "note.txt", b"recent")
        self.set_mtime(extra, self.now)

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertFalse(inspection.is_clean)
        self.assertIn(str(extra.resolve(strict=False)), inspection.unreferenced_artifact_paths)
        self.assertNotIn(str(extra.resolve(strict=False)), inspection.stale_artifact_paths)

    def test_failed_recoverable_metadata_surfaces_recoverable_id(self) -> None:
        transaction_id = "txn-recoverable"
        record = self.file_record(transaction_id, committed=False)
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            files=(record,),
            error="recoverable failure",
        )

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertFalse(inspection.is_clean)
        self.assertEqual(inspection.recoverable_transaction_ids, (transaction_id,))

    def test_invalid_metadata_path_blocks_inspection(self) -> None:
        self.store_root.mkdir()
        invalid_metadata_path = self.store_root / "txn-invalid.transaction.json"
        invalid_metadata_path.write_text("{not-json", encoding="utf-8")

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertFalse(inspection.is_clean)
        self.assertEqual(
            inspection.invalid_metadata_paths,
            (str(invalid_metadata_path.resolve(strict=False)),),
        )

    def test_metadata_reference_outside_transaction_work_root_blocks(self) -> None:
        transaction_id = "txn-outside"
        outside_temp = self.root / ".wbp-tmp-state.json"
        record = self.file_record(transaction_id, temp_path=outside_temp)
        self.write_metadata(transaction_id, files=(record,))

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertFalse(inspection.is_clean)
        self.assertEqual(inspection.blocked_transaction_ids, (transaction_id,))

    def test_symlink_artifact_blocks_without_following_target(self) -> None:
        transaction_id = "txn-symlink"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        outside_target = self.write_file(self.root / "outside-target.txt", b"outside")
        symlink_path = self.work_root(transaction_id) / "rogue.tmp"
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        symlink_path.symlink_to(outside_target)

        inspection = state_transaction.inspect_transaction_temp_artifacts(
            self.root,
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertFalse(inspection.is_clean)
        self.assertEqual(inspection.blocked_transaction_ids, (transaction_id,))
        self.assertNotIn(str(symlink_path.resolve(strict=False)), inspection.unreferenced_artifact_paths)

    def test_inspection_dataclasses_do_not_expose_packet_fields(self) -> None:
        inspection_fields = set(state_transaction.TransactionTempInspection.__dataclass_fields__)
        artifact_fields = set(state_transaction.TransactionTempArtifact.__dataclass_fields__)

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
        self.assertTrue(forbidden.isdisjoint(inspection_fields))
        self.assertTrue(forbidden.isdisjoint(artifact_fields))


if __name__ == "__main__":
    unittest.main()
