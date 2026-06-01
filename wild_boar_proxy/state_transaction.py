# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

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
TRANSACTION_STORE_DIRNAME = "transactions"

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


@dataclass(frozen=True)
class TransactionWrite:
    target_path: str
    payload: bytes


@dataclass(frozen=True)
class TransactionCommitResult:
    classification: str
    machine_error_code: str
    transaction_id: str
    transaction_root: str
    metadata_path: str
    file_count: int


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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        hasher = hashlib.sha256()
        with Path(path).open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return None


def _fsync_parent_best_effort(parent: Path) -> None:
    try:
        parent_fd = os.open(parent, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(parent_fd)
        except OSError:
            return
    finally:
        os.close(parent_fd)


def _write_bytes_fsync(path: Path, payload: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as file_obj:
        file_obj.write(payload)
        file_obj.flush()
        os.fsync(file_obj.fileno())
    _fsync_parent_best_effort(target.parent)


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


def _transaction_store_root_for(transaction_root: Path) -> Path:
    return Path(transaction_root) / TRANSACTION_STORE_DIRNAME


def _failed_metadata(
    metadata: TransactionMetadata,
    *,
    state: str,
    files: tuple[TransactionFileRecord, ...],
    error: str,
) -> TransactionMetadata:
    return TransactionMetadata(
        schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
        transaction_id=metadata.transaction_id,
        state=state,
        created_at_utc=metadata.created_at_utc,
        updated_at_utc=_utc_now_iso(),
        transaction_root=metadata.transaction_root,
        files=files,
        error=error,
    )


def _metadata_with_state(
    metadata: TransactionMetadata,
    *,
    state: str,
    files: tuple[TransactionFileRecord, ...] | None = None,
    error: str | None = None,
) -> TransactionMetadata:
    return TransactionMetadata(
        schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
        transaction_id=metadata.transaction_id,
        state=state,
        created_at_utc=metadata.created_at_utc,
        updated_at_utc=_utc_now_iso(),
        transaction_root=metadata.transaction_root,
        files=metadata.files if files is None else files,
        error=error,
    )


def _call_failure_hook(
    failure_hook: Callable[[str], None] | None,
    point: str,
) -> None:
    if failure_hook is not None:
        failure_hook(point)


def commit_state_transaction(
    transaction_root: Path,
    transaction_id: str,
    writes: tuple[TransactionWrite, ...],
    *,
    failure_hook: Callable[[str], None] | None = None,
) -> TransactionCommitResult:
    root = Path(transaction_root)
    if not root.is_absolute():
        raise StateTransactionError(
            "Transaction root must be absolute.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    root = root.resolve(strict=False)
    validated_transaction_id = validate_transaction_id(transaction_id)
    if not writes:
        raise StateTransactionError(
            "Transaction requires at least one write.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )

    store_root = _transaction_store_root_for(root)
    store_classification = classify_transaction_store(store_root)
    if store_classification.classification != TRANSACTION_CLEAN:
        raise StateTransactionError(
            "Transaction store is not clean.",
            machine_error_code=store_classification.machine_error_code,
        )

    transaction_work_root = store_root / f"{validated_transaction_id}.files"
    if transaction_work_root.exists():
        raise StateTransactionError(
            "Transaction work root already exists.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )

    target_paths: list[Path] = []
    target_path_keys: set[str] = set()
    for write in writes:
        if not isinstance(write, TransactionWrite):
            raise StateTransactionError(
                "Transaction write is invalid.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        if not isinstance(write.payload, bytes):
            raise StateTransactionError(
                "Transaction write payload must be bytes.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        target = Path(_require_path(write.target_path, field_name="target_path"))
        if not _path_is_under(str(target), str(root)):
            raise StateTransactionError(
                "Transaction target escapes transaction_root.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        target = target.resolve(strict=False)
        if _path_is_under(str(target), str(store_root)):
            raise StateTransactionError(
                "Transaction target must not be inside transaction store.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        target_key = str(target)
        if target_key in target_path_keys:
            raise StateTransactionError(
                "Transaction contains duplicate target paths.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        target_path_keys.add(target_key)
        target_paths.append(target)

    transaction_work_root.mkdir(parents=True, exist_ok=False)
    _fsync_parent_best_effort(transaction_work_root.parent)

    records: list[TransactionFileRecord] = []
    for index, (write, target) in enumerate(zip(writes, target_paths, strict=True)):
        temp_path = transaction_work_root / f"{index:04d}.tmp"
        backup_path = transaction_work_root / f"{index:04d}.backup"
        _call_failure_hook(failure_hook, "before_stage_temp")
        _write_bytes_fsync(temp_path, write.payload)
        _call_failure_hook(failure_hook, "after_stage_temp")
        records.append(
            TransactionFileRecord(
                target_path=str(target),
                temp_path=str(temp_path),
                backup_path=str(backup_path),
                sha256_before=_sha256_file(target),
                sha256_after=_sha256_bytes(write.payload),
                committed=False,
            )
        )

    metadata_path = transaction_metadata_path(store_root, validated_transaction_id)
    created_at = _utc_now_iso()
    metadata = TransactionMetadata(
        schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
        transaction_id=validated_transaction_id,
        state=TRANSACTION_PREPARING,
        created_at_utc=created_at,
        updated_at_utc=created_at,
        transaction_root=str(root),
        files=tuple(records),
        error=None,
    )

    _call_failure_hook(failure_hook, "before_metadata_write")
    write_transaction_metadata(metadata_path, metadata)

    try:
        _call_failure_hook(failure_hook, "after_preparing")
        metadata = _metadata_with_state(metadata, state=TRANSACTION_PREPARED)
        write_transaction_metadata(metadata_path, metadata)
        _call_failure_hook(failure_hook, "after_prepared")
        metadata = _metadata_with_state(metadata, state=TRANSACTION_COMMITTING)
        write_transaction_metadata(metadata_path, metadata)
        _call_failure_hook(failure_hook, "after_committing")

        committed_records: list[TransactionFileRecord] = []
        for write, target, record in zip(writes, target_paths, records, strict=True):
            backup_path = Path(record.backup_path)
            if target.exists():
                _call_failure_hook(failure_hook, "before_backup")
                _write_bytes_fsync(backup_path, target.read_bytes())
            _call_failure_hook(failure_hook, "before_replace")
            os.replace(record.temp_path, target)
            _fsync_parent_best_effort(target.parent)
            _call_failure_hook(failure_hook, "after_replace")
            committed_records.append(
                TransactionFileRecord(
                    target_path=record.target_path,
                    temp_path=record.temp_path,
                    backup_path=record.backup_path,
                    sha256_before=record.sha256_before,
                    sha256_after=_sha256_bytes(write.payload),
                    committed=True,
                )
            )
            records = committed_records + records[len(committed_records) :]

        metadata = _metadata_with_state(
            metadata,
            state=TRANSACTION_COMMITTED,
            files=tuple(records),
        )
        write_transaction_metadata(metadata_path, metadata)
    except Exception as exc:  # noqa: BLE001
        failed_metadata = _failed_metadata(
            metadata,
            state=TRANSACTION_FAILED_BLOCKED,
            files=tuple(records),
            error=str(exc) or exc.__class__.__name__,
        )
        write_transaction_metadata(metadata_path, failed_metadata)
        raise StateTransactionError(
            "Transaction commit failed.",
            machine_error_code=STATE_TRANSACTION_FAILED_BLOCKED,
        ) from exc

    return TransactionCommitResult(
        classification=TRANSACTION_CLEAN,
        machine_error_code=STATE_TRANSACTION_CLEAN,
        transaction_id=validated_transaction_id,
        transaction_root=str(root),
        metadata_path=str(metadata_path),
        file_count=len(records),
    )
