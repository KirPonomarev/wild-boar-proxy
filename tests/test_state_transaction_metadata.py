from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_store, state_transaction


class StateTransactionMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.metadata_path = self.root / "transaction.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def file_record(
        self,
        *,
        committed: bool = False,
        sha256_after: str | None = "after",
        target_path: Path | None = None,
    ) -> state_transaction.TransactionFileRecord:
        target = target_path or self.root / "state.json"
        return state_transaction.TransactionFileRecord(
            target_path=str(target),
            temp_path=str(self.root / ".wbp-tmp-state.json"),
            backup_path=str(self.root / "state.json.backup"),
            sha256_before="before",
            sha256_after=sha256_after,
            committed=committed,
        )

    def metadata(
        self,
        *,
        state: str = state_transaction.TRANSACTION_PREPARED,
        files: tuple[state_transaction.TransactionFileRecord, ...] | None = None,
        transaction_id: str = "txn-001",
        transaction_root: Path | None = None,
        schema_version: int = state_transaction.TRANSACTION_METADATA_SCHEMA_VERSION,
        error: str | None = None,
    ) -> state_transaction.TransactionMetadata:
        return state_transaction.TransactionMetadata(
            schema_version=schema_version,
            transaction_id=transaction_id,
            state=state,
            created_at_utc="2026-06-01T12:00:00+00:00",
            updated_at_utc="2026-06-01T12:01:00+00:00",
            transaction_root=str(transaction_root or self.root),
            files=(self.file_record(),) if files is None else files,
            error=error,
        )

    def write_store_metadata(
        self,
        transaction_id: str,
        *,
        state: str = state_transaction.TRANSACTION_COMMITTED,
        committed: bool = True,
        sha256_after: str | None = "after",
        error: str | None = None,
    ) -> Path:
        store_root = self.root / "transactions"
        metadata = self.metadata(
            state=state,
            files=(self.file_record(committed=committed, sha256_after=sha256_after),)
            if state != state_transaction.TRANSACTION_PREPARING
            else (),
            transaction_id=transaction_id,
            error=error,
        )
        metadata_path = state_transaction.transaction_metadata_path(store_root, transaction_id)
        state_transaction.write_transaction_metadata(metadata_path, metadata)
        return metadata_path

    def transaction_write(
        self,
        name: str,
        payload: bytes = b"new",
    ) -> state_transaction.TransactionWrite:
        return state_transaction.TransactionWrite(
            target_path=str(self.root / name),
            payload=payload,
        )

    def test_valid_metadata_roundtrip_through_state_store(self) -> None:
        metadata = self.metadata(state=state_transaction.TRANSACTION_COMMITTED, files=(self.file_record(committed=True),))

        write_result = state_transaction.write_transaction_metadata(self.metadata_path, metadata)
        read_back = state_transaction.read_transaction_metadata(self.metadata_path)

        self.assertTrue(write_result.committed)
        self.assertEqual(write_result.changed_files, (str(self.metadata_path),))
        self.assertEqual(read_back.transaction_id, metadata.transaction_id)
        self.assertEqual(read_back.files[0].target_path, metadata.files[0].target_path)

    def test_invalid_state_blocks(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.validate_transaction_metadata(self.metadata(state="done"))

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_missing_required_metadata_blocks(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.validate_transaction_metadata({"schema_version": 1})

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_unsupported_metadata_schema_blocks(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.validate_transaction_metadata(self.metadata(schema_version=2))

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_transaction_id_path_traversal_blocks(self) -> None:
        for transaction_id in ("../txn", "nested/txn", "nested\\txn", "txn..escape", ""):
            with self.assertRaises(state_transaction.StateTransactionError):
                state_transaction.validate_transaction_id(transaction_id)

    def test_transaction_metadata_path_rejects_relative_root_and_bad_id(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.transaction_metadata_path(Path("relative"), "txn-001")

        for transaction_id in ("../txn", "nested/txn", "nested\\txn", "txn\x00bad", ""):
            with self.assertRaises(state_transaction.StateTransactionError):
                state_transaction.transaction_metadata_path(self.root / "transactions", transaction_id)

    def test_transaction_metadata_path_uses_validated_transaction_id(self) -> None:
        path = state_transaction.transaction_metadata_path(self.root / "transactions", "txn-001")

        self.assertEqual(path, (self.root / "transactions" / "txn-001.transaction.json").resolve(strict=False))

    def test_nul_in_transaction_id_or_path_blocks(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.validate_transaction_id("txn\x00bad")

        bad_record = self.file_record(target_path=Path(str(self.root / "state.json") + "\x00"))
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.validate_transaction_metadata(self.metadata(files=(bad_record,)))

    def test_path_outside_transaction_root_blocks(self) -> None:
        outside = self.root.parent / "outside-state.json"
        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.validate_transaction_metadata(
                self.metadata(files=(self.file_record(target_path=outside),))
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_embedded_parent_segment_outside_transaction_root_blocks(self) -> None:
        escaped = self.root / ".." / "outside-state.json"
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.validate_transaction_metadata(
                self.metadata(files=(self.file_record(target_path=escaped),))
            )

    def test_incomplete_states_never_classify_clean(self) -> None:
        for state in (
            state_transaction.TRANSACTION_PREPARING,
            state_transaction.TRANSACTION_PREPARED,
            state_transaction.TRANSACTION_COMMITTING,
        ):
            files: tuple[state_transaction.TransactionFileRecord, ...] = ()
            if state != state_transaction.TRANSACTION_PREPARING:
                files = (self.file_record(),)

            classification = state_transaction.classify_transaction_metadata(
                self.metadata(state=state, files=files)
            )

            self.assertEqual(classification.classification, state_transaction.TRANSACTION_INCOMPLETE)
            self.assertEqual(
                classification.machine_error_code,
                state_transaction.STATE_TRANSACTION_INCOMPLETE,
            )

    def test_failed_recoverable_classifies_recoverable(self) -> None:
        classification = state_transaction.classify_transaction_metadata(
            self.metadata(state=state_transaction.TRANSACTION_FAILED_RECOVERABLE, error="publish failed")
        )

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_RECOVERABLE)
        self.assertEqual(
            classification.machine_error_code,
            state_transaction.STATE_TRANSACTION_FAILED_RECOVERABLE,
        )

    def test_failed_blocked_classifies_blocked(self) -> None:
        classification = state_transaction.classify_transaction_metadata(
            self.metadata(state=state_transaction.TRANSACTION_FAILED_BLOCKED, error="unsafe")
        )

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(
            classification.machine_error_code,
            state_transaction.STATE_TRANSACTION_FAILED_BLOCKED,
        )

    def test_committed_classifies_clean_only_when_all_records_committed(self) -> None:
        classification = state_transaction.classify_transaction_metadata(
            self.metadata(
                state=state_transaction.TRANSACTION_COMMITTED,
                files=(self.file_record(committed=True, sha256_after="after"),),
            )
        )

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_CLEAN)
        self.assertEqual(classification.machine_error_code, state_transaction.STATE_TRANSACTION_CLEAN)

    def test_committed_with_uncommitted_file_does_not_classify_clean(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.classify_transaction_metadata(
                self.metadata(
                    state=state_transaction.TRANSACTION_COMMITTED,
                    files=(self.file_record(committed=False),),
                )
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_committed_without_sha256_after_does_not_classify_clean(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.classify_transaction_metadata(
                self.metadata(
                    state=state_transaction.TRANSACTION_COMMITTED,
                    files=(self.file_record(committed=True, sha256_after=None),),
                )
            )

    def test_file_record_requires_target_temp_and_backup_paths(self) -> None:
        payload = {
            "target_path": str(self.root / "state.json"),
            "temp_path": str(self.root / ".tmp"),
            "sha256_before": "before",
            "sha256_after": "after",
            "committed": True,
        }

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.validate_transaction_metadata(
                {
                    "schema_version": state_transaction.TRANSACTION_METADATA_SCHEMA_VERSION,
                    "transaction_id": "txn-001",
                    "state": state_transaction.TRANSACTION_COMMITTED,
                    "created_at_utc": "2026-06-01T12:00:00+00:00",
                    "updated_at_utc": "2026-06-01T12:01:00+00:00",
                    "transaction_root": str(self.root),
                    "files": [payload],
                    "error": None,
                }
            )

    def test_metadata_read_rejects_corrupt_json(self) -> None:
        self.metadata_path.write_text("{not-json", encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_transaction.read_transaction_metadata(self.metadata_path)

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_CORRUPT)

    def test_metadata_writer_uses_state_store_only(self) -> None:
        calls: list[str] = []
        real_write_json = state_transaction.state_store.write_json

        def recording_write_json(*args: object, **kwargs: object) -> object:
            calls.append("write_json")
            return real_write_json(*args, **kwargs)

        with mock.patch.object(state_transaction.state_store, "write_json", recording_write_json):
            state_transaction.write_transaction_metadata(self.metadata_path, self.metadata())

        self.assertEqual(calls, ["write_json"])

    def test_missing_transaction_store_classifies_clean(self) -> None:
        classification = state_transaction.classify_transaction_store(self.root / "missing-transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_CLEAN)
        self.assertEqual(classification.machine_error_code, state_transaction.STATE_TRANSACTION_CLEAN)
        self.assertEqual(classification.transaction_ids, ())

    def test_transaction_store_relative_root_blocks_classification(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.classify_transaction_store(Path("relative-transactions"))

    def test_empty_transaction_store_classifies_clean(self) -> None:
        store_root = self.root / "transactions"
        store_root.mkdir()

        classification = state_transaction.classify_transaction_store(store_root)

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_CLEAN)
        self.assertEqual(classification.transaction_ids, ())

    def test_transaction_store_root_file_blocks_listing(self) -> None:
        store_root = self.root / "transactions"
        store_root.write_text("not a dir", encoding="utf-8")

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.list_transaction_metadata(store_root)

    def test_list_transaction_metadata_is_top_level_suffix_only_and_sorted(self) -> None:
        self.write_store_metadata("txn-b", state=state_transaction.TRANSACTION_COMMITTED)
        self.write_store_metadata("txn-a", state=state_transaction.TRANSACTION_COMMITTED)
        store_root = self.root / "transactions"
        (store_root / "txn-c.json").write_text("{}", encoding="utf-8")
        (store_root / "txn-d.transaction.json.backup").write_text("{}", encoding="utf-8")
        nested_root = store_root / "nested"
        nested_root.mkdir()
        (nested_root / "txn-nested.transaction.json").write_text("{}", encoding="utf-8")

        metadata_paths = state_transaction.list_transaction_metadata(store_root)

        self.assertEqual(
            tuple(path.name for path in metadata_paths),
            ("txn-a.transaction.json", "txn-b.transaction.json"),
        )

    def test_committed_only_transaction_store_classifies_clean(self) -> None:
        self.write_store_metadata("txn-001", state=state_transaction.TRANSACTION_COMMITTED)
        self.write_store_metadata("txn-002", state=state_transaction.TRANSACTION_COMMITTED)

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_CLEAN)
        self.assertEqual(classification.transaction_ids, ("txn-001", "txn-002"))

    def test_incomplete_transaction_store_classifies_incomplete(self) -> None:
        for state in (
            state_transaction.TRANSACTION_PREPARING,
            state_transaction.TRANSACTION_PREPARED,
            state_transaction.TRANSACTION_COMMITTING,
        ):
            with self.subTest(state=state):
                temp_dir = tempfile.TemporaryDirectory()
                self.addCleanup(temp_dir.cleanup)
                root = Path(temp_dir.name)
                store_root = root / "transactions"
                file_record = state_transaction.TransactionFileRecord(
                    target_path=str(root / "state.json"),
                    temp_path=str(root / ".tmp-state.json"),
                    backup_path=str(root / "state.json.backup"),
                    sha256_before="before",
                    sha256_after="after",
                    committed=False,
                )
                metadata = state_transaction.TransactionMetadata(
                    schema_version=state_transaction.TRANSACTION_METADATA_SCHEMA_VERSION,
                    transaction_id=f"txn-{state}",
                    state=state,
                    created_at_utc="2026-06-01T12:00:00+00:00",
                    updated_at_utc="2026-06-01T12:01:00+00:00",
                    transaction_root=str(root),
                    files=(file_record,) if state != state_transaction.TRANSACTION_PREPARING else (),
                    error=None,
                )
                state_transaction.write_transaction_metadata(
                    state_transaction.transaction_metadata_path(store_root, metadata.transaction_id),
                    metadata,
                )

                classification = state_transaction.classify_transaction_store(store_root)

                self.assertEqual(classification.classification, state_transaction.TRANSACTION_INCOMPLETE)
                self.assertEqual(classification.incomplete_transaction_ids, (metadata.transaction_id,))

    def test_failed_recoverable_transaction_store_classifies_recoverable(self) -> None:
        self.write_store_metadata(
            "txn-recoverable",
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            error="publish failed",
        )

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_RECOVERABLE)
        self.assertEqual(classification.recoverable_transaction_ids, ("txn-recoverable",))

    def test_failed_blocked_transaction_store_classifies_blocked(self) -> None:
        self.write_store_metadata(
            "txn-blocked",
            state=state_transaction.TRANSACTION_FAILED_BLOCKED,
            error="unsafe",
        )

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(classification.blocked_transaction_ids, ("txn-blocked",))

    def test_corrupt_canonical_metadata_blocks_store(self) -> None:
        metadata_path = state_transaction.transaction_metadata_path(self.root / "transactions", "txn-corrupt")
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text("{not-json", encoding="utf-8")

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(
            classification.invalid_metadata_paths,
            (str(metadata_path.parent.resolve(strict=False) / metadata_path.name),),
        )

    def test_invalid_canonical_metadata_blocks_store(self) -> None:
        metadata_path = state_transaction.transaction_metadata_path(self.root / "transactions", "txn-invalid")
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text(
            '{"schema_version": 1, "transaction_id": "txn-invalid", "state": "done"}',
            encoding="utf-8",
        )

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(
            classification.invalid_metadata_paths,
            (str(metadata_path.parent.resolve(strict=False) / metadata_path.name),),
        )

    def test_invalid_canonical_metadata_filename_blocks_store(self) -> None:
        metadata_path = self.root / "transactions" / ".transaction.json"
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text("{}", encoding="utf-8")

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(
            classification.invalid_metadata_paths,
            (str(metadata_path.parent.resolve(strict=False) / metadata_path.name),),
        )

    def test_directory_canonical_metadata_candidate_blocks_store(self) -> None:
        metadata_path = self.root / "transactions" / "txn-dir.transaction.json"
        metadata_path.mkdir(parents=True)

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(classification.invalid_metadata_paths, (str(metadata_path.resolve(strict=False)),))

    def test_symlink_canonical_metadata_candidate_blocks_store(self) -> None:
        outside = self.root / "outside.transaction.json"
        outside.write_text("{}", encoding="utf-8")
        metadata_path = self.root / "transactions" / "txn-link.transaction.json"
        metadata_path.parent.mkdir(parents=True)
        try:
            metadata_path.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(
            classification.invalid_metadata_paths,
            (str(metadata_path.parent.resolve(strict=False) / metadata_path.name),),
        )

    def test_foreign_non_metadata_files_are_ignored_by_store_classification(self) -> None:
        store_root = self.root / "transactions"
        store_root.mkdir()
        (store_root / ".DS_Store").write_text("foreign", encoding="utf-8")
        (store_root / "notes.txt").write_text("foreign", encoding="utf-8")

        classification = state_transaction.classify_transaction_store(store_root)

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_CLEAN)
        self.assertEqual(classification.invalid_metadata_paths, ())

    def test_blocked_store_precedence_beats_recoverable_and_incomplete(self) -> None:
        self.write_store_metadata("txn-incomplete", state=state_transaction.TRANSACTION_PREPARED)
        self.write_store_metadata(
            "txn-recoverable",
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            error="publish failed",
        )
        self.write_store_metadata(
            "txn-blocked",
            state=state_transaction.TRANSACTION_FAILED_BLOCKED,
            error="unsafe",
        )

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(classification.blocked_transaction_ids, ("txn-blocked",))
        self.assertEqual(classification.recoverable_transaction_ids, ("txn-recoverable",))
        self.assertEqual(classification.incomplete_transaction_ids, ("txn-incomplete",))

    def test_invalid_store_precedence_beats_clean_recoverable_and_incomplete(self) -> None:
        self.write_store_metadata("txn-clean", state=state_transaction.TRANSACTION_COMMITTED)
        self.write_store_metadata("txn-incomplete", state=state_transaction.TRANSACTION_PREPARED)
        self.write_store_metadata(
            "txn-recoverable",
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            error="publish failed",
        )
        invalid_path = state_transaction.transaction_metadata_path(self.root / "transactions", "txn-invalid")
        invalid_path.write_text("{not-json", encoding="utf-8")

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_BLOCKED)
        self.assertEqual(classification.transaction_ids, ("txn-clean", "txn-incomplete", "txn-recoverable"))
        self.assertEqual(classification.recoverable_transaction_ids, ("txn-recoverable",))
        self.assertEqual(classification.incomplete_transaction_ids, ("txn-incomplete",))
        self.assertEqual(
            classification.invalid_metadata_paths,
            (str(invalid_path.parent.resolve(strict=False) / invalid_path.name),),
        )

    def test_recoverable_store_precedence_beats_incomplete(self) -> None:
        self.write_store_metadata("txn-incomplete", state=state_transaction.TRANSACTION_PREPARED)
        self.write_store_metadata(
            "txn-recoverable",
            state=state_transaction.TRANSACTION_FAILED_RECOVERABLE,
            error="publish failed",
        )

        classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_RECOVERABLE)
        self.assertEqual(classification.recoverable_transaction_ids, ("txn-recoverable",))
        self.assertEqual(classification.incomplete_transaction_ids, ("txn-incomplete",))

    def test_store_classification_does_not_write(self) -> None:
        self.write_store_metadata("txn-001", state=state_transaction.TRANSACTION_COMMITTED)

        with (
            mock.patch.object(state_transaction.state_store, "write_json") as write_json,
            mock.patch.object(state_transaction.state_store, "write_text") as write_text,
        ):
            classification = state_transaction.classify_transaction_store(self.root / "transactions")

        self.assertEqual(classification.classification, state_transaction.TRANSACTION_CLEAN)
        write_json.assert_not_called()
        write_text.assert_not_called()

    def test_commit_state_transaction_writes_single_file_and_committed_metadata(self) -> None:
        target = self.root / "state.json"

        result = state_transaction.commit_state_transaction(
            self.root,
            "txn-commit",
            (self.transaction_write("state.json", b'{"ok": true}'),),
        )
        metadata = state_transaction.read_transaction_metadata(Path(result.metadata_path))

        self.assertEqual(target.read_bytes(), b'{"ok": true}')
        self.assertEqual(result.classification, state_transaction.TRANSACTION_CLEAN)
        self.assertEqual(metadata.state, state_transaction.TRANSACTION_COMMITTED)
        self.assertEqual(metadata.files[0].target_path, str(target.resolve(strict=False)))
        self.assertTrue(metadata.files[0].committed)
        self.assertIsNone(metadata.files[0].sha256_before)
        self.assertIsNotNone(metadata.files[0].sha256_after)
        self.assertEqual(
            state_transaction.classify_transaction_store(self.root / "transactions").classification,
            state_transaction.TRANSACTION_CLEAN,
        )

    def test_commit_state_transaction_writes_multi_file_in_input_order(self) -> None:
        state_transaction.commit_state_transaction(
            self.root,
            "txn-multi",
            (
                self.transaction_write("b.json", b"second"),
                self.transaction_write("a.json", b"first"),
            ),
        )
        metadata = state_transaction.read_transaction_metadata(
            state_transaction.transaction_metadata_path(self.root / "transactions", "txn-multi")
        )

        self.assertEqual((self.root / "a.json").read_bytes(), b"first")
        self.assertEqual((self.root / "b.json").read_bytes(), b"second")
        self.assertEqual(
            tuple(Path(record.target_path).name for record in metadata.files),
            ("b.json", "a.json"),
        )
        self.assertTrue(all(record.committed for record in metadata.files))

    def test_commit_state_transaction_records_backup_evidence_without_rollback_fields(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")

        result = state_transaction.commit_state_transaction(
            self.root,
            "txn-backup",
            (self.transaction_write("state.json", b"new"),),
        )
        metadata = state_transaction.read_transaction_metadata(Path(result.metadata_path))
        record = metadata.files[0]

        self.assertEqual(target.read_bytes(), b"new")
        self.assertIsNotNone(record.sha256_before)
        self.assertEqual(Path(record.backup_path).read_bytes(), b"old")
        self.assertFalse(metadata.rollback_eligible)
        self.assertIsNone(metadata.rollback_id)
        result_fields = set(state_transaction.TransactionCommitResult.__dataclass_fields__)
        self.assertNotIn("rollback_available", result_fields)
        self.assertNotIn("rollback_id", result_fields)

    def test_legacy_committed_metadata_without_rollback_fields_is_not_available(
        self,
    ) -> None:
        self.write_store_metadata("txn-clean", state=state_transaction.TRANSACTION_COMMITTED)

        metadata = state_transaction.read_transaction_metadata(
            state_transaction.transaction_metadata_path(self.root / "transactions", "txn-clean")
        )
        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertFalse(metadata.rollback_eligible)
        self.assertIsNone(metadata.rollback_id)
        self.assertFalse(result.rollback_available)
        self.assertIsNone(result.rollback_id)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_NOT_AVAILABLE)
        self.assertEqual(result.changed_files, ())

    def test_rollback_preflight_no_eligible_transaction_reports_not_available(
        self,
    ) -> None:
        self.write_store_metadata("txn-clean", state=state_transaction.TRANSACTION_COMMITTED)

        result = state_transaction.preflight_latest_state_transaction_rollback(self.root)

        self.assertFalse(result.rollback_available)
        self.assertIsNone(result.rollback_id)
        self.assertIsNone(result.transaction_id)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_NOT_AVAILABLE)
        self.assertEqual(
            result.machine_error_code,
            state_transaction.STATE_TRANSACTION_ROLLBACK_NOT_AVAILABLE,
        )
        self.assertEqual(result.would_change_files, ())
        self.assertEqual(result.files, ())

    def test_rollback_eligible_metadata_requires_truth_fields(self) -> None:
        metadata = self.metadata(
            state=state_transaction.TRANSACTION_COMMITTED,
            files=(self.file_record(committed=True),),
            error=None,
        )
        invalid_metadata = state_transaction.TransactionMetadata(
            schema_version=metadata.schema_version,
            transaction_id=metadata.transaction_id,
            state=metadata.state,
            created_at_utc=metadata.created_at_utc,
            updated_at_utc=metadata.updated_at_utc,
            transaction_root=metadata.transaction_root,
            files=metadata.files,
            error=metadata.error,
            rollback_eligible=True,
        )

        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.validate_transaction_metadata(invalid_metadata)

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_rollback_id_without_eligibility_is_invalid(self) -> None:
        metadata = self.metadata(
            state=state_transaction.TRANSACTION_COMMITTED,
            files=(self.file_record(committed=True),),
        )
        invalid_metadata = state_transaction.TransactionMetadata(
            schema_version=metadata.schema_version,
            transaction_id=metadata.transaction_id,
            state=metadata.state,
            created_at_utc=metadata.created_at_utc,
            updated_at_utc=metadata.updated_at_utc,
            transaction_root=metadata.transaction_root,
            files=metadata.files,
            error=metadata.error,
            rollback_id=state_transaction.rollback_id_for_transaction(
                metadata.transaction_id
            ),
        )

        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.validate_transaction_metadata(invalid_metadata)

        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_INVALID,
        )

    def test_rollback_latest_replace_transaction_restores_backup(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        commit_result = state_transaction.commit_state_transaction(
            self.root,
            "txn-replace",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-replace",
            rollback_eligible=True,
        )
        metadata = state_transaction.read_transaction_metadata(Path(commit_result.metadata_path))

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertTrue(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_COMPLETED)
        self.assertEqual(
            result.machine_error_code,
            state_transaction.STATE_TRANSACTION_ROLLBACK_COMPLETED,
        )
        self.assertEqual(result.rollback_id, metadata.rollback_id)
        self.assertEqual(result.transaction_id, "txn-replace")
        self.assertEqual(result.changed_files, (str(target.resolve(strict=False)),))
        self.assertEqual(target.read_bytes(), b"old")

    def test_successful_rollback_retires_transaction_from_latest_pool(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        commit_result = state_transaction.commit_state_transaction(
            self.root,
            "txn-retire-after-rollback",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-retire-after-rollback",
            rollback_eligible=True,
        )
        metadata_path = Path(commit_result.metadata_path)

        result = state_transaction.rollback_latest_state_transaction(self.root)
        metadata = state_transaction.read_transaction_metadata(metadata_path)
        target.write_bytes(b"new")
        preflight_after_thaw = state_transaction.preflight_latest_state_transaction_rollback(
            self.root
        )

        self.assertTrue(result.rollback_available)
        self.assertEqual(metadata.state, state_transaction.TRANSACTION_ROLLED_BACK)
        self.assertTrue(metadata.rollback_eligible)
        self.assertIsNotNone(metadata.rollback_id)
        self.assertFalse(preflight_after_thaw.rollback_available)
        self.assertEqual(
            preflight_after_thaw.status,
            state_transaction.TRANSACTION_ROLLBACK_NOT_AVAILABLE,
        )

    def test_rollback_preflight_reports_latest_ready_without_writes(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        commit_result = state_transaction.commit_state_transaction(
            self.root,
            "txn-preflight-ready",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-preflight-ready",
            rollback_eligible=True,
        )
        metadata_path = Path(commit_result.metadata_path)
        before_metadata = metadata_path.read_text(encoding="utf-8")

        result = state_transaction.preflight_latest_state_transaction_rollback(self.root)

        self.assertTrue(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_READY)
        self.assertEqual(
            result.machine_error_code,
            state_transaction.STATE_TRANSACTION_ROLLBACK_READY,
        )
        self.assertEqual(result.transaction_id, "txn-preflight-ready")
        self.assertEqual(result.mutation_id, "wbp-mut-preflight-ready")
        self.assertEqual(result.effect, "repair")
        self.assertEqual(result.scope, "state_transaction_test")
        self.assertEqual(result.would_change_files, (str(target.resolve(strict=False)),))
        self.assertEqual(result.files[0].target_path, str(target.resolve(strict=False)))
        self.assertEqual(result.files[0].sha256_before, state_transaction._sha256_bytes(b"old"))
        self.assertEqual(result.files[0].sha256_after, state_transaction._sha256_bytes(b"new"))
        self.assertEqual(target.read_bytes(), b"new")
        self.assertEqual(metadata_path.read_text(encoding="utf-8"), before_metadata)

    def test_rollback_latest_create_transaction_deletes_created_file(self) -> None:
        target = self.root / "created.json"
        state_transaction.commit_state_transaction(
            self.root,
            "txn-create",
            (self.transaction_write("created.json", b"created"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-create",
            rollback_eligible=True,
        )

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertTrue(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_COMPLETED)
        self.assertEqual(result.changed_files, (str(target.resolve(strict=False)),))
        self.assertFalse(target.exists())

    def test_rollback_blocks_target_drift_without_writes(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-drift",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-drift",
            rollback_eligible=True,
        )
        target.write_bytes(b"drift")

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertEqual(
            result.machine_error_code,
            state_transaction.STATE_TRANSACTION_ROLLBACK_BLOCKED,
        )
        self.assertIn("target_sha256_drift", result.blocked_reasons[0])
        self.assertEqual(result.changed_files, ())
        self.assertEqual(target.read_bytes(), b"drift")

    def test_rollback_preflight_blocks_target_drift_without_writes(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-preflight-drift",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-preflight-drift",
            rollback_eligible=True,
        )
        target.write_bytes(b"drift")

        result = state_transaction.preflight_latest_state_transaction_rollback(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertEqual(result.would_change_files, ())
        self.assertIn("target_sha256_drift", result.blocked_reasons[0])
        self.assertEqual(target.read_bytes(), b"drift")

    def test_rollback_multifile_drift_blocks_before_any_write(self) -> None:
        alpha = self.root / "alpha.json"
        beta = self.root / "beta.json"
        alpha.write_bytes(b"old-alpha")
        beta.write_bytes(b"old-beta")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-multifile-drift",
            (
                self.transaction_write("alpha.json", b"new-alpha"),
                self.transaction_write("beta.json", b"new-beta"),
            ),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-multifile-drift",
            rollback_eligible=True,
        )
        alpha.write_bytes(b"drift-alpha")

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertIn("target_sha256_drift", result.blocked_reasons[0])
        self.assertEqual(result.changed_files, ())
        self.assertEqual(alpha.read_bytes(), b"drift-alpha")
        self.assertEqual(beta.read_bytes(), b"new-beta")

    def test_rollback_blocks_missing_backup_without_writes(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        commit_result = state_transaction.commit_state_transaction(
            self.root,
            "txn-missing-backup",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-missing-backup",
            rollback_eligible=True,
        )
        metadata = state_transaction.read_transaction_metadata(Path(commit_result.metadata_path))
        Path(metadata.files[0].backup_path).unlink()

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertIn("backup_not_regular_file", result.blocked_reasons[0])
        self.assertEqual(result.changed_files, ())
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_blocks_existing_rollback_temp_without_writes(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        commit_result = state_transaction.commit_state_transaction(
            self.root,
            "txn-rollback-temp",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-rollback-temp",
            rollback_eligible=True,
        )
        metadata = state_transaction.read_transaction_metadata(Path(commit_result.metadata_path))
        rollback_temp_path = Path(metadata.files[0].backup_path).parent / "0000.rollback.tmp"
        rollback_temp_path.write_bytes(b"stale")

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertIn("rollback_temp_exists", result.blocked_reasons[0])
        self.assertEqual(result.changed_files, ())
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_time_failure_marks_transaction_failed_blocked(self) -> None:
        alpha = self.root / "alpha.json"
        beta = self.root / "beta.json"
        alpha.write_bytes(b"old-alpha")
        beta.write_bytes(b"old-beta")
        commit_result = state_transaction.commit_state_transaction(
            self.root,
            "txn-rollback-failure",
            (
                self.transaction_write("alpha.json", b"new-alpha"),
                self.transaction_write("beta.json", b"new-beta"),
            ),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-rollback-failure",
            rollback_eligible=True,
        )
        after_rollback_calls = 0

        def fail_after_first_apply(point: str) -> None:
            nonlocal after_rollback_calls
            if point != "after_rollback_file":
                return
            after_rollback_calls += 1
            if after_rollback_calls == 1:
                raise RuntimeError("rollback failure")

        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.rollback_latest_state_transaction(
                self.root,
                failure_hook=fail_after_first_apply,
            )

        metadata = state_transaction.read_transaction_metadata(Path(commit_result.metadata_path))
        self.assertEqual(
            raised.exception.machine_error_code,
            state_transaction.STATE_TRANSACTION_FAILED_BLOCKED,
        )
        self.assertEqual(metadata.state, state_transaction.TRANSACTION_FAILED_BLOCKED)
        self.assertEqual(metadata.error, "rollback failure")
        self.assertEqual(alpha.read_bytes(), b"new-alpha")
        self.assertEqual(beta.read_bytes(), b"old-beta")
        self.assertEqual(
            state_transaction.classify_transaction_store(
                self.root / "transactions"
            ).classification,
            state_transaction.TRANSACTION_BLOCKED,
        )

    def test_rollback_blocks_when_transaction_store_is_not_clean(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-eligible",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-store-block",
            rollback_eligible=True,
        )
        self.write_store_metadata("txn-incomplete", state=state_transaction.TRANSACTION_PREPARED)

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertEqual(result.machine_error_code, state_transaction.STATE_TRANSACTION_INCOMPLETE)
        self.assertEqual(result.changed_files, ())
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_preflight_blocks_when_transaction_store_is_not_clean(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-preflight-eligible",
            (self.transaction_write("state.json", b"new"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-preflight-store-block",
            rollback_eligible=True,
        )
        self.write_store_metadata("txn-preflight-incomplete", state=state_transaction.TRANSACTION_PREPARED)

        result = state_transaction.preflight_latest_state_transaction_rollback(self.root)

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertEqual(result.machine_error_code, state_transaction.STATE_TRANSACTION_INCOMPLETE)
        self.assertEqual(result.would_change_files, ())
        self.assertEqual(result.files, ())
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_latest_selection_uses_latest_eligible_committed_metadata(self) -> None:
        alpha = self.root / "alpha.json"
        beta = self.root / "beta.json"
        alpha.write_bytes(b"old-alpha")
        beta.write_bytes(b"old-beta")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-001",
            (self.transaction_write("alpha.json", b"new-alpha"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-alpha",
            rollback_eligible=True,
        )
        state_transaction.commit_state_transaction(
            self.root,
            "txn-002",
            (self.transaction_write("beta.json", b"new-beta"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-beta",
            rollback_eligible=True,
        )

        result = state_transaction.rollback_latest_state_transaction(self.root)

        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_COMPLETED)
        self.assertEqual(result.transaction_id, "txn-002")
        self.assertEqual(alpha.read_bytes(), b"new-alpha")
        self.assertEqual(beta.read_bytes(), b"old-beta")

    def test_rollback_latest_expected_guard_blocks_changed_latest_without_writes(
        self,
    ) -> None:
        alpha = self.root / "alpha.json"
        beta = self.root / "beta.json"
        alpha.write_bytes(b"old-alpha")
        beta.write_bytes(b"old-beta")
        state_transaction.commit_state_transaction(
            self.root,
            "txn-001",
            (self.transaction_write("alpha.json", b"new-alpha"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-alpha",
            rollback_eligible=True,
        )
        preflight = state_transaction.preflight_latest_state_transaction_rollback(
            self.root
        )
        state_transaction.commit_state_transaction(
            self.root,
            "txn-002",
            (self.transaction_write("beta.json", b"new-beta"),),
            effect="repair",
            scope="state_transaction_test",
            mutation_id="wbp-mut-beta",
            rollback_eligible=True,
        )

        result = state_transaction.rollback_latest_state_transaction(
            self.root,
            expected_transaction_id=preflight.transaction_id,
            expected_rollback_id=preflight.rollback_id,
        )

        self.assertFalse(result.rollback_available)
        self.assertEqual(result.status, state_transaction.TRANSACTION_ROLLBACK_BLOCKED)
        self.assertEqual(
            result.blocked_reasons,
            ("latest_transaction_changed_after_preflight",),
        )
        self.assertEqual(result.changed_files, ())
        self.assertEqual(alpha.read_bytes(), b"new-alpha")
        self.assertEqual(beta.read_bytes(), b"new-beta")

    def test_commit_state_transaction_rejects_relative_root_invalid_id_and_empty_writes(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(Path("relative"), "txn", (self.transaction_write("state.json"),))

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(self.root, "../txn", (self.transaction_write("state.json"),))

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(self.root, "txn-empty", ())

    def test_commit_state_transaction_rejects_target_outside_root_and_duplicate_targets(self) -> None:
        outside = self.root.parent / "outside.json"
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-outside",
                (state_transaction.TransactionWrite(target_path=str(outside), payload=b"bad"),),
            )
        self.assertFalse(outside.exists())

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-duplicate",
                (
                    self.transaction_write("state.json", b"one"),
                    self.transaction_write("state.json", b"two"),
                ),
            )

    def test_commit_state_transaction_rejects_target_inside_transaction_store(self) -> None:
        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-nested",
                (self.transaction_write("transactions/state.json", b"bad"),),
            )

    def test_commit_state_transaction_blocks_when_store_not_clean(self) -> None:
        self.write_store_metadata("txn-incomplete", state=state_transaction.TRANSACTION_PREPARED)

        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.commit_state_transaction(
                self.root,
                "txn-new",
                (self.transaction_write("state.json"),),
            )

        self.assertEqual(raised.exception.machine_error_code, state_transaction.STATE_TRANSACTION_INCOMPLETE)

    def test_commit_state_transaction_failure_before_metadata_write_leaves_no_metadata(self) -> None:
        def fail(point: str) -> None:
            if point == "before_metadata_write":
                raise RuntimeError("pre metadata failure")

        with self.assertRaises(RuntimeError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-no-metadata",
                (self.transaction_write("state.json"),),
                failure_hook=fail,
            )

        metadata_path = state_transaction.transaction_metadata_path(self.root / "transactions", "txn-no-metadata")
        self.assertFalse(metadata_path.exists())
        self.assertFalse((self.root / "state.json").exists())

    def test_commit_state_transaction_failure_between_staged_writes_leaves_no_metadata_or_targets(self) -> None:
        staged_count = 0

        def fail(point: str) -> None:
            nonlocal staged_count
            if point == "after_stage_temp":
                staged_count += 1
            if point == "before_stage_temp" and staged_count == 1:
                raise RuntimeError("second temp failure")

        with self.assertRaises(RuntimeError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-stage-failure",
                (
                    self.transaction_write("first.json", b"first"),
                    self.transaction_write("second.json", b"second"),
                ),
                failure_hook=fail,
            )

        metadata_path = state_transaction.transaction_metadata_path(self.root / "transactions", "txn-stage-failure")
        self.assertFalse(metadata_path.exists())
        self.assertFalse((self.root / "first.json").exists())
        self.assertFalse((self.root / "second.json").exists())

    def test_commit_state_transaction_failure_after_prepared_marks_failed_blocked(self) -> None:
        def fail(point: str) -> None:
            if point == "after_prepared":
                raise RuntimeError("prepared failure")

        with self.assertRaises(state_transaction.StateTransactionError) as raised:
            state_transaction.commit_state_transaction(
                self.root,
                "txn-fail-prepared",
                (self.transaction_write("state.json"),),
                failure_hook=fail,
            )

        self.assertEqual(raised.exception.machine_error_code, state_transaction.STATE_TRANSACTION_FAILED_BLOCKED)
        metadata = state_transaction.read_transaction_metadata(
            state_transaction.transaction_metadata_path(self.root / "transactions", "txn-fail-prepared")
        )
        self.assertEqual(metadata.state, state_transaction.TRANSACTION_FAILED_BLOCKED)
        self.assertFalse(metadata.files[0].committed)
        self.assertEqual(
            state_transaction.classify_transaction_store(self.root / "transactions").classification,
            state_transaction.TRANSACTION_BLOCKED,
        )
        self.assertFalse((self.root / "state.json").exists())

    def test_commit_state_transaction_failure_before_replace_marks_failed_blocked(self) -> None:
        target = self.root / "state.json"
        target.write_bytes(b"old")

        def fail(point: str) -> None:
            if point == "before_replace":
                raise RuntimeError("replace failure")

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-fail-replace",
                (self.transaction_write("state.json", b"new"),),
                failure_hook=fail,
            )

        metadata = state_transaction.read_transaction_metadata(
            state_transaction.transaction_metadata_path(self.root / "transactions", "txn-fail-replace")
        )
        self.assertEqual(metadata.state, state_transaction.TRANSACTION_FAILED_BLOCKED)
        self.assertFalse(metadata.files[0].committed)
        self.assertEqual(target.read_bytes(), b"old")
        self.assertEqual(
            state_transaction.classify_transaction_store(self.root / "transactions").classification,
            state_transaction.TRANSACTION_BLOCKED,
        )

    def test_commit_state_transaction_failure_after_replace_marks_failed_blocked(self) -> None:
        def fail(point: str) -> None:
            if point == "after_replace":
                raise RuntimeError("post replace failure")

        with self.assertRaises(state_transaction.StateTransactionError):
            state_transaction.commit_state_transaction(
                self.root,
                "txn-fail-after-replace",
                (self.transaction_write("state.json", b"new"),),
                failure_hook=fail,
            )

        metadata = state_transaction.read_transaction_metadata(
            state_transaction.transaction_metadata_path(self.root / "transactions", "txn-fail-after-replace")
        )
        self.assertEqual((self.root / "state.json").read_bytes(), b"new")
        self.assertEqual(metadata.state, state_transaction.TRANSACTION_FAILED_BLOCKED)
        self.assertFalse(metadata.files[0].committed)
        self.assertEqual(
            state_transaction.classify_transaction_store(self.root / "transactions").classification,
            state_transaction.TRANSACTION_BLOCKED,
        )

    def test_commit_state_transaction_does_not_cleanup_unrelated_stale_temp_files(self) -> None:
        stale_temp = self.root / ".wbp-tmp-unrelated"
        stale_temp.write_bytes(b"stale")

        state_transaction.commit_state_transaction(
            self.root,
            "txn-no-cleanup",
            (self.transaction_write("state.json", b"new"),),
        )

        self.assertEqual(stale_temp.read_bytes(), b"stale")

    def test_metadata_module_does_not_import_runtime_layers(self) -> None:
        source = Path(state_transaction.__file__).read_text(encoding="utf-8")
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

    def test_classification_and_result_are_not_command_packets(self) -> None:
        classification_fields = set(state_transaction.TransactionClassification.__dataclass_fields__)
        result_fields = set(state_transaction.TransactionMetadataWriteResult.__dataclass_fields__)
        store_classification_fields = set(state_transaction.TransactionStoreClassification.__dataclass_fields__)
        commit_result_fields = set(state_transaction.TransactionCommitResult.__dataclass_fields__)

        forbidden = {
            "changed_files",
            "committed",
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
            "schema_version",
            "status",
            "target",
        }
        packet_forbidden = forbidden - {"changed_files", "committed", "schema_version", "target"}
        self.assertTrue(packet_forbidden.isdisjoint(classification_fields))
        self.assertTrue(packet_forbidden.isdisjoint(result_fields))
        self.assertTrue(forbidden.isdisjoint(store_classification_fields))
        self.assertTrue(forbidden.isdisjoint(commit_result_fields))


if __name__ == "__main__":
    unittest.main()
