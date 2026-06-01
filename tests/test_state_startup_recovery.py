from __future__ import annotations

import ast
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wild_boar_proxy import state_startup_recovery, state_transaction


class StateStartupTempRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store_root = self.root / "transactions"
        self.now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def no_follow(self, path: Path) -> str:
        return str(Path(os.path.abspath(os.path.normpath(os.fspath(path)))))

    def resolved(self, path: Path) -> str:
        return str(path.resolve(strict=False))

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

    def test_no_temp_issues_returns_clean_temp_outcome(self) -> None:
        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_CLEAN,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_recovery.STATE_STARTUP_TEMP_CLEAN,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertEqual(result.blocking_reasons, ())

    def test_stale_transaction_temp_cleanup_returns_recovered(self) -> None:
        transaction_id = "txn-stale"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)
        self.assertEqual(
            result.transaction_cleanup.deleted_artifact_paths,
            (self.resolved(stale),),
        )
        self.assertFalse(stale.exists())

    def test_stale_prefix_temp_cleanup_returns_recovered(self) -> None:
        stale = self.write_file(self.root / ".wbp-tmp-state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)
        self.assertEqual(result.prefix_cleanup.deleted_paths, (self.no_follow(stale),))
        self.assertFalse(stale.exists())

    def test_both_cleanup_paths_return_recovered(self) -> None:
        transaction_id = "txn-both"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        tx_stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        prefix_stale = self.write_file(self.root / ".wbp-tmp-state.json", b"old")
        self.set_mtime(tx_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.set_mtime(prefix_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)
        self.assertFalse(tx_stale.exists())
        self.assertFalse(prefix_stale.exists())

    def test_incomplete_transaction_blocks_without_partial_prefix_cleanup(self) -> None:
        transaction_id = "txn-incomplete"
        record = self.file_record(transaction_id, committed=False)
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_PREPARED,
            files=(record,),
        )
        prefix_stale = self.write_file(self.root / ".wbp-tmp-state.json", b"old")
        self.set_mtime(prefix_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_recovery.STATE_STARTUP_TEMP_BLOCKED,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertIn(
            state_startup_recovery.REASON_TRANSACTION_INCOMPLETE,
            result.blocking_reasons,
        )
        self.assertTrue(prefix_stale.exists())

    def test_recoverable_transaction_blocks(self) -> None:
        transaction_id = "txn-recoverable"
        record = self.file_record(transaction_id, committed=False)
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            files=(record,),
            error="recoverable failure",
        )

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_BLOCKED,
        )
        self.assertIn(
            state_startup_recovery.REASON_TRANSACTION_RECOVERABLE,
            result.blocking_reasons,
        )

    def test_blocked_transaction_blocks(self) -> None:
        transaction_id = "txn-blocked"
        record = self.file_record(transaction_id, committed=False)
        self.write_metadata(
            transaction_id,
            state=state_transaction.TRANSACTION_FAILED_BLOCKED,
            files=(record,),
            error="blocked failure",
        )

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_BLOCKED,
        )
        self.assertIn(
            state_startup_recovery.REASON_TRANSACTION_BLOCKED,
            result.blocking_reasons,
        )

    def test_invalid_prefix_root_blocks_without_partial_transaction_cleanup(self) -> None:
        transaction_id = "txn-stale"
        record = self.file_record(transaction_id)
        self.write_metadata(transaction_id, files=(record,))
        self.write_file(Path(record.backup_path), b"backup")
        tx_stale = self.write_file(self.work_root(transaction_id) / "leftover.tmp", b"old")
        invalid_root = self.write_file(self.root / "not-a-directory", b"{}")
        self.set_mtime(tx_stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (invalid_root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_BLOCKED,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertIn(
            state_startup_recovery.REASON_PREFIX_INVALID_ROOT,
            result.blocking_reasons,
        )
        self.assertTrue(tx_stale.exists())

    def test_blocked_prefix_child_blocks(self) -> None:
        outside_target = self.write_file(self.root / "outside.txt", b"outside")
        blocked = self.root / ".wbp-tmp-link.state.json"
        blocked.symlink_to(outside_target)

        result = state_startup_recovery.run_startup_temp_recovery(
            self.root,
            (self.root,),
            now=self.now,
            transaction_stale_ttl_seconds=60,
            prefix_stale_ttl_seconds=60,
        )

        self.assertEqual(
            result.temp_recovery_outcome,
            state_startup_recovery.TEMP_RECOVERY_BLOCKED,
        )
        self.assertIn(
            state_startup_recovery.REASON_PREFIX_BLOCKED_PATH,
            result.blocking_reasons,
        )

    def test_startup_temp_result_dataclass_does_not_expose_packet_fields(self) -> None:
        result_fields = set(state_startup_recovery.StartupTempRecoveryResult.__dataclass_fields__)
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
        self.assertTrue(forbidden.isdisjoint(result_fields))

    def test_module_does_not_import_runtime_layers(self) -> None:
        source = Path(state_startup_recovery.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {
            "wild_boar_proxy.runtime",
            "wild_boar_proxy.operator_surface",
            "wild_boar_proxy.cli",
            "wild_boar_proxy.web_design_live_server",
            "wild_boar_proxy.command_effects",
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
