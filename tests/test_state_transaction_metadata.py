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

        forbidden = {
            "effect",
            "exit_code",
            "human_message",
            "liveness",
            "next_action",
            "severity",
            "status",
        }
        self.assertTrue(forbidden.isdisjoint(classification_fields))
        self.assertTrue(forbidden.isdisjoint(result_fields))


if __name__ == "__main__":
    unittest.main()
