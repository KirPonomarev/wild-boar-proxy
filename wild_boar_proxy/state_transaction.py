# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from wild_boar_proxy import state_store


TRANSACTION_METADATA_SCHEMA_VERSION = 1

TRANSACTION_PREPARING = "preparing"
TRANSACTION_PREPARED = "prepared"
TRANSACTION_COMMITTING = "committing"
TRANSACTION_COMMITTED = "committed"
TRANSACTION_FAILED_RECOVERABLE = "failed_recoverable"
TRANSACTION_FAILED_BLOCKED = "failed_blocked"

TRANSACTION_CLEAN = "clean"
TRANSACTION_INCOMPLETE = "incomplete"
TRANSACTION_RECOVERABLE = "recoverable"
TRANSACTION_BLOCKED = "blocked"
TRANSACTION_METADATA_SUFFIX = ".transaction.json"

STATE_TRANSACTION_INVALID = "STATE_TRANSACTION_INVALID"
STATE_TRANSACTION_INCOMPLETE = "STATE_TRANSACTION_INCOMPLETE"
STATE_TRANSACTION_CLEAN = "STATE_TRANSACTION_CLEAN"
STATE_TRANSACTION_FAILED_RECOVERABLE = "STATE_TRANSACTION_FAILED_RECOVERABLE"
STATE_TRANSACTION_FAILED_BLOCKED = "STATE_TRANSACTION_FAILED_BLOCKED"

_VALID_STATES = frozenset(
    {
        TRANSACTION_PREPARING,
        TRANSACTION_PREPARED,
        TRANSACTION_COMMITTING,
        TRANSACTION_COMMITTED,
        TRANSACTION_FAILED_RECOVERABLE,
        TRANSACTION_FAILED_BLOCKED,
    }
)
_INCOMPLETE_STATES = frozenset(
    {
        TRANSACTION_PREPARING,
        TRANSACTION_PREPARED,
        TRANSACTION_COMMITTING,
    }
)


@dataclass(frozen=True)
class TransactionFileRecord:
    target_path: str
    temp_path: str
    backup_path: str
    sha256_before: str | None
    sha256_after: str | None
    committed: bool


@dataclass(frozen=True)
class TransactionMetadata:
    schema_version: int
    transaction_id: str
    state: str
    created_at_utc: str
    updated_at_utc: str
    transaction_root: str
    files: tuple[TransactionFileRecord, ...]
    error: str | None = None


@dataclass(frozen=True)
class TransactionClassification:
    classification: str
    machine_error_code: str
    reason: str


@dataclass(frozen=True)
class TransactionMetadataWriteResult:
    committed: bool
    target: str
    changed_files: tuple[str, ...]
    schema_version: int


@dataclass(frozen=True)
class TransactionStoreClassification:
    classification: str
    machine_error_code: str
    transaction_ids: tuple[str, ...]
    incomplete_transaction_ids: tuple[str, ...]
    recoverable_transaction_ids: tuple[str, ...]
    blocked_transaction_ids: tuple[str, ...]
    invalid_metadata_paths: tuple[str, ...]


class StateTransactionError(Exception):
    def __init__(self, message: str, *, machine_error_code: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def validate_transaction_id(transaction_id: str) -> str:
    if (
        not isinstance(transaction_id, str)
        or not transaction_id
        or "\x00" in transaction_id
        or "/" in transaction_id
        or "\\" in transaction_id
        or ".." in transaction_id.split(".")
        or any(segment == "" for segment in transaction_id.split("."))
    ):
        raise StateTransactionError(
            "Transaction id is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return transaction_id


def _require_absolute_store_root(root: Path) -> Path:
    transaction_store_root = Path(root)
    if not transaction_store_root.is_absolute():
        raise StateTransactionError(
            "Transaction store root must be absolute.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return transaction_store_root.resolve(strict=False)


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty string")
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _require_path(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise StateTransactionError(
            f"Transaction file {field_name} is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return value


def _path_is_under(path: str, root: str) -> bool:
    candidate = Path(path)
    transaction_root = Path(root)
    if not candidate.is_absolute() or not transaction_root.is_absolute():
        return False
    candidate = candidate.resolve(strict=False)
    transaction_root = transaction_root.resolve(strict=False)
    try:
        candidate.relative_to(transaction_root)
    except ValueError:
        return False
    return True


def _file_record_from_payload(payload: Mapping[str, object]) -> TransactionFileRecord:
    required = {"target_path", "temp_path", "backup_path", "sha256_before", "sha256_after", "committed"}
    if not required.issubset(payload.keys()):
        raise StateTransactionError(
            "Transaction file record is missing required fields.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    committed = payload["committed"]
    if not isinstance(committed, bool):
        raise StateTransactionError(
            "Transaction file committed flag is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    sha256_before = payload["sha256_before"]
    sha256_after = payload["sha256_after"]
    if sha256_before is not None and not isinstance(sha256_before, str):
        raise StateTransactionError(
            "Transaction file sha256_before is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    if sha256_after is not None and not isinstance(sha256_after, str):
        raise StateTransactionError(
            "Transaction file sha256_after is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return TransactionFileRecord(
        target_path=_require_path(payload["target_path"], field_name="target_path"),
        temp_path=_require_path(payload["temp_path"], field_name="temp_path"),
        backup_path=_require_path(payload["backup_path"], field_name="backup_path"),
        sha256_before=sha256_before,
        sha256_after=sha256_after,
        committed=committed,
    )


def _file_record_to_payload(record: TransactionFileRecord) -> dict[str, object]:
    return {
        "target_path": record.target_path,
        "temp_path": record.temp_path,
        "backup_path": record.backup_path,
        "sha256_before": record.sha256_before,
        "sha256_after": record.sha256_after,
        "committed": record.committed,
    }


def _metadata_from_payload(payload: Mapping[str, object]) -> TransactionMetadata:
    required = {
        "schema_version",
        "transaction_id",
        "state",
        "created_at_utc",
        "updated_at_utc",
        "transaction_root",
        "files",
        "error",
    }
    if not required.issubset(payload.keys()):
        raise StateTransactionError(
            "Transaction metadata is missing required fields.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    files_payload = payload["files"]
    if not isinstance(files_payload, list):
        raise StateTransactionError(
            "Transaction metadata files must be a list.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    files: list[TransactionFileRecord] = []
    for file_payload in files_payload:
        if not isinstance(file_payload, Mapping):
            raise StateTransactionError(
                "Transaction file record must be an object.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        files.append(_file_record_from_payload(file_payload))
    error = payload["error"]
    if error is not None and not isinstance(error, str):
        raise StateTransactionError(
            "Transaction metadata error is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return TransactionMetadata(
        schema_version=payload["schema_version"],  # type: ignore[arg-type]
        transaction_id=payload["transaction_id"],  # type: ignore[arg-type]
        state=payload["state"],  # type: ignore[arg-type]
        created_at_utc=payload["created_at_utc"],  # type: ignore[arg-type]
        updated_at_utc=payload["updated_at_utc"],  # type: ignore[arg-type]
        transaction_root=payload["transaction_root"],  # type: ignore[arg-type]
        files=tuple(files),
        error=error,
    )


def _metadata_to_payload(metadata: TransactionMetadata) -> dict[str, object]:
    return {
        "schema_version": metadata.schema_version,
        "transaction_id": metadata.transaction_id,
        "state": metadata.state,
        "created_at_utc": metadata.created_at_utc,
        "updated_at_utc": metadata.updated_at_utc,
        "transaction_root": metadata.transaction_root,
        "files": [_file_record_to_payload(file_record) for file_record in metadata.files],
        "error": metadata.error,
    }


def validate_transaction_metadata(
    metadata: TransactionMetadata | Mapping[str, object],
) -> TransactionMetadata:
    parsed = metadata if isinstance(metadata, TransactionMetadata) else _metadata_from_payload(metadata)
    if (
        isinstance(parsed.schema_version, bool)
        or not isinstance(parsed.schema_version, int)
        or parsed.schema_version != TRANSACTION_METADATA_SCHEMA_VERSION
    ):
        raise StateTransactionError(
            "Transaction metadata schema_version is unsupported.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    validate_transaction_id(parsed.transaction_id)
    if parsed.state not in _VALID_STATES:
        raise StateTransactionError(
            "Transaction state is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    try:
        _parse_utc(parsed.created_at_utc)
        _parse_utc(parsed.updated_at_utc)
    except ValueError as exc:
        raise StateTransactionError(
            "Transaction metadata timestamp is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        ) from exc
    transaction_root = _require_path(parsed.transaction_root, field_name="transaction_root")
    if not Path(transaction_root).is_absolute():
        raise StateTransactionError(
            "Transaction root must be absolute.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    if parsed.state != TRANSACTION_PREPARING and not parsed.files:
        raise StateTransactionError(
            "Transaction state requires file records.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    for file_record in parsed.files:
        for path_value in (file_record.target_path, file_record.temp_path, file_record.backup_path):
            _require_path(path_value, field_name="path")
            if not _path_is_under(path_value, transaction_root):
                raise StateTransactionError(
                    "Transaction file path escapes transaction_root.",
                    machine_error_code=STATE_TRANSACTION_INVALID,
                )
        if not isinstance(file_record.committed, bool):
            raise StateTransactionError(
                "Transaction file committed flag is invalid.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
    return parsed


def classify_transaction_metadata(
    metadata: TransactionMetadata | Mapping[str, object],
) -> TransactionClassification:
    parsed = validate_transaction_metadata(metadata)
    if parsed.state in _INCOMPLETE_STATES:
        return TransactionClassification(
            classification=TRANSACTION_INCOMPLETE,
            machine_error_code=STATE_TRANSACTION_INCOMPLETE,
            reason="transaction is incomplete",
        )
    if parsed.state == TRANSACTION_FAILED_RECOVERABLE:
        return TransactionClassification(
            classification=TRANSACTION_RECOVERABLE,
            machine_error_code=STATE_TRANSACTION_FAILED_RECOVERABLE,
            reason="transaction failed but is recoverable",
        )
    if parsed.state == TRANSACTION_FAILED_BLOCKED:
        return TransactionClassification(
            classification=TRANSACTION_BLOCKED,
            machine_error_code=STATE_TRANSACTION_FAILED_BLOCKED,
            reason="transaction failed and is blocked",
        )
    if all(file_record.committed and file_record.sha256_after for file_record in parsed.files):
        return TransactionClassification(
            classification=TRANSACTION_CLEAN,
            machine_error_code=STATE_TRANSACTION_CLEAN,
            reason="transaction is committed",
        )
    raise StateTransactionError(
        "Committed transaction metadata has uncommitted file records.",
        machine_error_code=STATE_TRANSACTION_INVALID,
    )


def read_transaction_metadata(path: Path) -> TransactionMetadata:
    payload = state_store.read_json(
        Path(path),
        expected_schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
    )
    return validate_transaction_metadata(payload)


def write_transaction_metadata(
    path: Path,
    metadata: TransactionMetadata,
) -> TransactionMetadataWriteResult:
    validated = validate_transaction_metadata(metadata)
    result = state_store.write_json(
        Path(path),
        _metadata_to_payload(validated),
        expected_schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
    )
    return TransactionMetadataWriteResult(
        committed=result.committed,
        target=result.target,
        changed_files=result.changed_files,
        schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
    )


def transaction_metadata_path(root: Path, transaction_id: str) -> Path:
    store_root = _require_absolute_store_root(Path(root))
    validated_transaction_id = validate_transaction_id(transaction_id)
    return store_root / f"{validated_transaction_id}{TRANSACTION_METADATA_SUFFIX}"


def _transaction_id_from_metadata_path(path: Path) -> str:
    name = path.name
    if not name.endswith(TRANSACTION_METADATA_SUFFIX):
        raise StateTransactionError(
            "Transaction metadata path has invalid suffix.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    transaction_id = name[: -len(TRANSACTION_METADATA_SUFFIX)]
    return validate_transaction_id(transaction_id)


def list_transaction_metadata(root: Path) -> tuple[Path, ...]:
    store_root = _require_absolute_store_root(Path(root))
    if not store_root.exists():
        return ()
    if not store_root.is_dir():
        raise StateTransactionError(
            "Transaction store root must be a directory.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    metadata_paths: list[Path] = []
    for candidate in sorted(store_root.iterdir(), key=lambda item: item.name):
        if not candidate.name.endswith(TRANSACTION_METADATA_SUFFIX):
            continue
        metadata_paths.append(candidate)
    return tuple(metadata_paths)


def _store_classification(
    classification: str,
    machine_error_code: str,
    *,
    transaction_ids: tuple[str, ...],
    incomplete_transaction_ids: tuple[str, ...] = (),
    recoverable_transaction_ids: tuple[str, ...] = (),
    blocked_transaction_ids: tuple[str, ...] = (),
    invalid_metadata_paths: tuple[str, ...] = (),
) -> TransactionStoreClassification:
    return TransactionStoreClassification(
        classification=classification,
        machine_error_code=machine_error_code,
        transaction_ids=transaction_ids,
        incomplete_transaction_ids=incomplete_transaction_ids,
        recoverable_transaction_ids=recoverable_transaction_ids,
        blocked_transaction_ids=blocked_transaction_ids,
        invalid_metadata_paths=invalid_metadata_paths,
    )


def classify_transaction_store(root: Path) -> TransactionStoreClassification:
    metadata_paths = list_transaction_metadata(root)
    transaction_ids: list[str] = []
    incomplete_transaction_ids: list[str] = []
    recoverable_transaction_ids: list[str] = []
    blocked_transaction_ids: list[str] = []
    invalid_metadata_paths: list[str] = []

    for metadata_path in metadata_paths:
        try:
            transaction_id = _transaction_id_from_metadata_path(metadata_path)
            if metadata_path.is_symlink() or not metadata_path.is_file():
                raise StateTransactionError(
                    "Transaction metadata path must be a regular file.",
                    machine_error_code=STATE_TRANSACTION_INVALID,
                )
            metadata = read_transaction_metadata(metadata_path)
            classification = classify_transaction_metadata(metadata)
        except (OSError, StateTransactionError, state_store.StateStoreError):
            invalid_metadata_paths.append(str(metadata_path))
            continue

        transaction_ids.append(transaction_id)
        if classification.classification == TRANSACTION_BLOCKED:
            blocked_transaction_ids.append(transaction_id)
        elif classification.classification == TRANSACTION_RECOVERABLE:
            recoverable_transaction_ids.append(transaction_id)
        elif classification.classification == TRANSACTION_INCOMPLETE:
            incomplete_transaction_ids.append(transaction_id)

    transaction_ids_tuple = tuple(transaction_ids)
    invalid_metadata_paths_tuple = tuple(invalid_metadata_paths)
    if invalid_metadata_paths_tuple or blocked_transaction_ids:
        return _store_classification(
            TRANSACTION_BLOCKED,
            STATE_TRANSACTION_FAILED_BLOCKED,
            transaction_ids=transaction_ids_tuple,
            incomplete_transaction_ids=tuple(incomplete_transaction_ids),
            recoverable_transaction_ids=tuple(recoverable_transaction_ids),
            blocked_transaction_ids=tuple(blocked_transaction_ids),
            invalid_metadata_paths=invalid_metadata_paths_tuple,
        )
    if recoverable_transaction_ids:
        return _store_classification(
            TRANSACTION_RECOVERABLE,
            STATE_TRANSACTION_FAILED_RECOVERABLE,
            transaction_ids=transaction_ids_tuple,
            incomplete_transaction_ids=tuple(incomplete_transaction_ids),
            recoverable_transaction_ids=tuple(recoverable_transaction_ids),
        )
    if incomplete_transaction_ids:
        return _store_classification(
            TRANSACTION_INCOMPLETE,
            STATE_TRANSACTION_INCOMPLETE,
            transaction_ids=transaction_ids_tuple,
            incomplete_transaction_ids=tuple(incomplete_transaction_ids),
        )
    return _store_classification(
        TRANSACTION_CLEAN,
        STATE_TRANSACTION_CLEAN,
        transaction_ids=transaction_ids_tuple,
    )
