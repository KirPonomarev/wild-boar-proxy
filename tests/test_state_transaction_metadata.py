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

        forbidden = {
            "changed_files",
            "committed",
            "effect",
            "exit_code",
            "human_message",
            "liveness",
            "next_action",
            "operator_action",
            "rollback_available",
            "severity",
            "schema_version",
            "status",
            "target",
        }
        packet_forbidden = forbidden - {"changed_files", "committed", "schema_version", "target"}
        self.assertTrue(packet_forbidden.isdisjoint(classification_fields))
        self.assertTrue(packet_forbidden.isdisjoint(result_fields))
        self.assertTrue(forbidden.isdisjoint(store_classification_fields))


if __name__ == "__main__":
    unittest.main()
