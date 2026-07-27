# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from wild_boar_proxy import state_store


TRANSACTION_METADATA_SCHEMA_VERSION = 1

TRANSACTION_PREPARING = "preparing"
TRANSACTION_PREPARED = "prepared"
TRANSACTION_COMMITTING = "committing"
TRANSACTION_COMMITTED = "committed"
TRANSACTION_ROLLED_BACK = "rolled_back"
TRANSACTION_FAILED_RECOVERABLE = "failed_recoverable"
TRANSACTION_FAILED_BLOCKED = "failed_blocked"

TRANSACTION_CLEAN = "clean"
TRANSACTION_INCOMPLETE = "incomplete"
TRANSACTION_RECOVERABLE = "recoverable"
TRANSACTION_BLOCKED = "blocked"
TRANSACTION_METADATA_SUFFIX = ".transaction.json"
TRANSACTION_STORE_DIRNAME = "transactions"
TRANSACTION_WORK_DIR_SUFFIX = ".files"
TRANSACTION_ARTIFACT_STALE_TTL_SECONDS = 3600

STATE_TRANSACTION_INVALID = "STATE_TRANSACTION_INVALID"
STATE_TRANSACTION_INCOMPLETE = "STATE_TRANSACTION_INCOMPLETE"
STATE_TRANSACTION_CLEAN = "STATE_TRANSACTION_CLEAN"
STATE_TRANSACTION_FAILED_RECOVERABLE = "STATE_TRANSACTION_FAILED_RECOVERABLE"
STATE_TRANSACTION_FAILED_BLOCKED = "STATE_TRANSACTION_FAILED_BLOCKED"
STATE_TRANSACTION_ROLLBACK_COMPLETED = "STATE_TRANSACTION_ROLLBACK_COMPLETED"
STATE_TRANSACTION_ROLLBACK_NOT_AVAILABLE = "STATE_TRANSACTION_ROLLBACK_NOT_AVAILABLE"
STATE_TRANSACTION_ROLLBACK_READY = "STATE_TRANSACTION_ROLLBACK_READY"
STATE_TRANSACTION_ROLLBACK_BLOCKED = "STATE_TRANSACTION_ROLLBACK_BLOCKED"

TRANSACTION_ROLLBACK_COMPLETED = "rollback_completed"
TRANSACTION_ROLLBACK_NOT_AVAILABLE = "rollback_not_available"
TRANSACTION_ROLLBACK_READY = "rollback_ready"
TRANSACTION_ROLLBACK_BLOCKED = "rollback_blocked"
ROLLBACK_ID_PREFIX = "wbp-rb-"

_VALID_STATES = frozenset(
    {
        TRANSACTION_PREPARING,
        TRANSACTION_PREPARED,
        TRANSACTION_COMMITTING,
        TRANSACTION_COMMITTED,
        TRANSACTION_ROLLED_BACK,
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
    effect: str | None = None
    scope: str | None = None
    mutation_id: str | None = None
    rollback_eligible: bool = False
    rollback_id: str | None = None


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


@dataclass(frozen=True)
class TransactionRollbackResult:
    rollback_available: bool
    rollback_id: str | None
    transaction_id: str | None
    status: str
    changed_files: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    machine_error_code: str


@dataclass(frozen=True)
class TransactionRollbackPreflightFile:
    target_path: str
    sha256_before: str | None
    sha256_after: str | None


@dataclass(frozen=True)
class TransactionRollbackPreflightResult:
    rollback_available: bool
    rollback_id: str | None
    transaction_id: str | None
    mutation_id: str | None
    effect: str | None
    scope: str | None
    status: str
    would_change_files: tuple[str, ...]
    files: tuple[TransactionRollbackPreflightFile, ...]
    blocked_reasons: tuple[str, ...]
    machine_error_code: str


@dataclass(frozen=True)
class TransactionTempArtifact:
    path: str
    transaction_id: str
    artifact_kind: str
    referenced: bool
    exists: bool
    stale: bool


@dataclass(frozen=True)
class TransactionTempInspection:
    artifacts: tuple[TransactionTempArtifact, ...]
    referenced_artifact_paths: tuple[str, ...]
    unreferenced_artifact_paths: tuple[str, ...]
    stale_artifact_paths: tuple[str, ...]
    incomplete_transaction_ids: tuple[str, ...]
    recoverable_transaction_ids: tuple[str, ...]
    blocked_transaction_ids: tuple[str, ...]
    invalid_metadata_paths: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return not (
            self.unreferenced_artifact_paths
            or self.stale_artifact_paths
            or self.incomplete_transaction_ids
            or self.recoverable_transaction_ids
            or self.blocked_transaction_ids
            or self.invalid_metadata_paths
        )


@dataclass(frozen=True)
class TransactionTempCleanupResult:
    deleted_artifact_paths: tuple[str, ...]
    skipped_artifact_paths: tuple[str, ...]
    stale_artifact_paths: tuple[str, ...]
    incomplete_transaction_ids: tuple[str, ...]
    recoverable_transaction_ids: tuple[str, ...]
    blocked_transaction_ids: tuple[str, ...]
    invalid_metadata_paths: tuple[str, ...]

    @property
    def cleanup_performed(self) -> bool:
        return bool(self.deleted_artifact_paths)

    @property
    def cleanup_blocked(self) -> bool:
        return bool(
            self.incomplete_transaction_ids
            or self.recoverable_transaction_ids
            or self.blocked_transaction_ids
            or self.invalid_metadata_paths
        )


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
    except OSError:
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


def _absolute_path_no_follow(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _path_str_no_follow(path: Path) -> str:
    return str(_absolute_path_no_follow(path))


def _path_is_under_no_follow(path: Path, root: Path) -> bool:
    candidate = _absolute_path_no_follow(path)
    transaction_root = _absolute_path_no_follow(root)
    try:
        candidate.relative_to(transaction_root)
    except ValueError:
        return False
    return True


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


def _optional_metadata_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or "\x00" in value:
        raise StateTransactionError(
            f"Transaction metadata {field_name} is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return value


def validate_rollback_id(rollback_id: str) -> str:
    if (
        not isinstance(rollback_id, str)
        or not rollback_id.startswith(ROLLBACK_ID_PREFIX)
        or "\x00" in rollback_id
        or "/" in rollback_id
        or "\\" in rollback_id
    ):
        raise StateTransactionError(
            "Rollback id is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return rollback_id


def rollback_id_for_transaction(transaction_id: str) -> str:
    validated_transaction_id = validate_transaction_id(transaction_id)
    digest = hashlib.sha256(validated_transaction_id.encode("utf-8")).hexdigest()
    return f"{ROLLBACK_ID_PREFIX}{digest[:20]}"


def _validate_metadata_rollback_fields(metadata: TransactionMetadata) -> None:
    if not isinstance(metadata.rollback_eligible, bool):
        raise StateTransactionError(
            "Transaction rollback eligibility flag is invalid.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    if metadata.effect is not None:
        _optional_metadata_text(metadata.effect, field_name="effect")
    if metadata.scope is not None:
        _optional_metadata_text(metadata.scope, field_name="scope")
    if metadata.mutation_id is not None:
        _optional_metadata_text(metadata.mutation_id, field_name="mutation_id")
    if metadata.rollback_id is not None:
        validate_rollback_id(metadata.rollback_id)
    if not metadata.rollback_eligible:
        if metadata.rollback_id is not None:
            raise StateTransactionError(
                "Rollback id requires rollback-eligible transaction metadata.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )
        return
    for field_name, value in (
        ("effect", metadata.effect),
        ("scope", metadata.scope),
        ("mutation_id", metadata.mutation_id),
        ("rollback_id", metadata.rollback_id),
    ):
        if value is None:
            raise StateTransactionError(
                f"Rollback-eligible transaction metadata is missing {field_name}.",
                machine_error_code=STATE_TRANSACTION_INVALID,
            )


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
    rollback_eligible = payload.get("rollback_eligible", False)
    if not isinstance(rollback_eligible, bool):
        raise StateTransactionError(
            "Transaction rollback eligibility flag is invalid.",
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
        effect=_optional_metadata_text(payload.get("effect"), field_name="effect"),
        scope=_optional_metadata_text(payload.get("scope"), field_name="scope"),
        mutation_id=_optional_metadata_text(
            payload.get("mutation_id"),
            field_name="mutation_id",
        ),
        rollback_eligible=rollback_eligible,
        rollback_id=_optional_metadata_text(
            payload.get("rollback_id"),
            field_name="rollback_id",
        ),
    )


def _metadata_to_payload(metadata: TransactionMetadata) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": metadata.schema_version,
        "transaction_id": metadata.transaction_id,
        "state": metadata.state,
        "created_at_utc": metadata.created_at_utc,
        "updated_at_utc": metadata.updated_at_utc,
        "transaction_root": metadata.transaction_root,
        "files": [_file_record_to_payload(file_record) for file_record in metadata.files],
        "error": metadata.error,
    }
    if metadata.effect is not None:
        payload["effect"] = metadata.effect
    if metadata.scope is not None:
        payload["scope"] = metadata.scope
    if metadata.mutation_id is not None:
        payload["mutation_id"] = metadata.mutation_id
    if metadata.rollback_eligible:
        payload["rollback_eligible"] = metadata.rollback_eligible
    if metadata.rollback_id is not None:
        payload["rollback_id"] = metadata.rollback_id
    return payload


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
    _validate_metadata_rollback_fields(parsed)
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
    if parsed.state == TRANSACTION_ROLLED_BACK:
        if all(file_record.committed and file_record.sha256_after for file_record in parsed.files):
            return TransactionClassification(
                classification=TRANSACTION_CLEAN,
                machine_error_code=STATE_TRANSACTION_CLEAN,
                reason="transaction has been rolled back",
            )
        raise StateTransactionError(
            "Rolled-back transaction metadata has uncommitted file records.",
            machine_error_code=STATE_TRANSACTION_INVALID,
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


def _transaction_work_root_for(store_root: Path, transaction_id: str) -> Path:
    return Path(store_root) / f"{transaction_id}{TRANSACTION_WORK_DIR_SUFFIX}"


def _artifact_kind_for_path(path: Path) -> str:
    if path.name.endswith(".tmp"):
        return "temp"
    if path.name.endswith(".backup"):
        return "backup"
    return "workfile"


def _normalize_inspection_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise StateTransactionError(
            "Inspection time must include timezone.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    return now.astimezone(timezone.utc)


def _artifact_is_stale(
    path: Path,
    *,
    now: datetime,
    stale_ttl_seconds: int,
) -> bool:
    modified_at = datetime.fromtimestamp(path.stat(follow_symlinks=False).st_mtime, timezone.utc)
    return modified_at <= now - timedelta(seconds=stale_ttl_seconds)


def _merge_temp_artifact(
    artifacts_by_path: dict[str, TransactionTempArtifact],
    *,
    path: str,
    transaction_id: str,
    artifact_kind: str,
    referenced: bool,
    exists: bool,
    stale: bool,
) -> None:
    existing = artifacts_by_path.get(path)
    if existing is None:
        artifacts_by_path[path] = TransactionTempArtifact(
            path=path,
            transaction_id=transaction_id,
            artifact_kind=artifact_kind,
            referenced=referenced,
            exists=exists,
            stale=stale,
        )
        return
    artifacts_by_path[path] = TransactionTempArtifact(
        path=path,
        transaction_id=existing.transaction_id,
        artifact_kind=existing.artifact_kind,
        referenced=existing.referenced or referenced,
        exists=existing.exists or exists,
        stale=existing.stale or stale,
    )


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def inspect_transaction_temp_artifacts(
    transaction_root: Path,
    *,
    now: datetime | None = None,
    stale_ttl_seconds: int = TRANSACTION_ARTIFACT_STALE_TTL_SECONDS,
) -> TransactionTempInspection:
    root = Path(transaction_root)
    if not root.is_absolute():
        raise StateTransactionError(
            "Transaction root must be absolute.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    if (
        isinstance(stale_ttl_seconds, bool)
        or not isinstance(stale_ttl_seconds, int)
        or stale_ttl_seconds < 0
    ):
        raise StateTransactionError(
            "Transaction artifact TTL must be a non-negative integer.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )

    normalized_root = root.resolve(strict=False)
    normalized_now = _normalize_inspection_now(now)
    store_root = _transaction_store_root_for(normalized_root)
    if not store_root.exists():
        return TransactionTempInspection(
            artifacts=(),
            referenced_artifact_paths=(),
            unreferenced_artifact_paths=(),
            stale_artifact_paths=(),
            incomplete_transaction_ids=(),
            recoverable_transaction_ids=(),
            blocked_transaction_ids=(),
            invalid_metadata_paths=(),
        )
    if not store_root.is_dir():
        raise StateTransactionError(
            "Transaction store root must be a directory.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )

    artifacts_by_path: dict[str, TransactionTempArtifact] = {}
    referenced_artifact_paths: list[str] = []
    unreferenced_artifact_paths: list[str] = []
    stale_artifact_paths: list[str] = []
    incomplete_transaction_ids: list[str] = []
    recoverable_transaction_ids: list[str] = []
    blocked_transaction_ids: list[str] = []
    invalid_metadata_paths: list[str] = []
    blocked_id_set: set[str] = set()
    referenced_path_set: set[str] = set()

    for metadata_path in list_transaction_metadata(store_root):
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
            _append_unique(invalid_metadata_paths, _path_str_no_follow(metadata_path))
            continue

        if classification.classification == TRANSACTION_BLOCKED:
            _append_unique(blocked_transaction_ids, transaction_id)
            blocked_id_set.add(transaction_id)
            continue

        work_root = _transaction_work_root_for(store_root, transaction_id)
        metadata_blocked = False
        for file_record in metadata.files:
            for artifact_path_text, artifact_kind in (
                (file_record.temp_path, "temp"),
                (file_record.backup_path, "backup"),
            ):
                artifact_path = Path(artifact_path_text)
                if not _path_is_under_no_follow(artifact_path, work_root):
                    metadata_blocked = True
                    break
                artifact_key = _path_str_no_follow(artifact_path)
                if artifact_path.is_symlink():
                    metadata_blocked = True
                    break
                if artifact_path.exists() and not artifact_path.is_file():
                    metadata_blocked = True
                    break
                referenced_path_set.add(artifact_key)
                _append_unique(referenced_artifact_paths, artifact_key)
                _merge_temp_artifact(
                    artifacts_by_path,
                    path=artifact_key,
                    transaction_id=transaction_id,
                    artifact_kind=artifact_kind,
                    referenced=True,
                    exists=artifact_path.exists(),
                    stale=False,
                )
            if metadata_blocked:
                break

        if metadata_blocked:
            _append_unique(blocked_transaction_ids, transaction_id)
            blocked_id_set.add(transaction_id)
            continue

        if classification.classification == TRANSACTION_RECOVERABLE:
            _append_unique(recoverable_transaction_ids, transaction_id)
        elif classification.classification == TRANSACTION_INCOMPLETE:
            _append_unique(incomplete_transaction_ids, transaction_id)

    for candidate in sorted(store_root.iterdir(), key=lambda item: item.name):
        if not candidate.name.endswith(TRANSACTION_WORK_DIR_SUFFIX):
            continue
        transaction_id = candidate.name[: -len(TRANSACTION_WORK_DIR_SUFFIX)]
        try:
            validate_transaction_id(transaction_id)
        except StateTransactionError:
            continue
        if transaction_id in blocked_id_set:
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            _append_unique(blocked_transaction_ids, transaction_id)
            blocked_id_set.add(transaction_id)
            continue

        for artifact_path in sorted(candidate.iterdir(), key=lambda item: item.name):
            artifact_key = _path_str_no_follow(artifact_path)
            if artifact_path.is_symlink() or artifact_path.is_dir():
                _append_unique(blocked_transaction_ids, transaction_id)
                blocked_id_set.add(transaction_id)
                break
            if artifact_key in referenced_path_set:
                _merge_temp_artifact(
                    artifacts_by_path,
                    path=artifact_key,
                    transaction_id=transaction_id,
                    artifact_kind=_artifact_kind_for_path(artifact_path),
                    referenced=True,
                    exists=True,
                    stale=False,
                )
                continue
            stale = _artifact_is_stale(
                artifact_path,
                now=normalized_now,
                stale_ttl_seconds=stale_ttl_seconds,
            )
            _append_unique(unreferenced_artifact_paths, artifact_key)
            if stale:
                _append_unique(stale_artifact_paths, artifact_key)
            _merge_temp_artifact(
                artifacts_by_path,
                path=artifact_key,
                transaction_id=transaction_id,
                artifact_kind=_artifact_kind_for_path(artifact_path),
                referenced=False,
                exists=True,
                stale=stale,
            )

    return TransactionTempInspection(
        artifacts=tuple(sorted(artifacts_by_path.values(), key=lambda artifact: artifact.path)),
        referenced_artifact_paths=tuple(referenced_artifact_paths),
        unreferenced_artifact_paths=tuple(unreferenced_artifact_paths),
        stale_artifact_paths=tuple(stale_artifact_paths),
        incomplete_transaction_ids=tuple(incomplete_transaction_ids),
        recoverable_transaction_ids=tuple(recoverable_transaction_ids),
        blocked_transaction_ids=tuple(blocked_transaction_ids),
        invalid_metadata_paths=tuple(invalid_metadata_paths),
    )


def cleanup_transaction_store_artifacts(
    transaction_root: Path,
    *,
    now: datetime | None = None,
    stale_ttl_seconds: int = TRANSACTION_ARTIFACT_STALE_TTL_SECONDS,
) -> TransactionTempCleanupResult:
    inspection = inspect_transaction_temp_artifacts(
        transaction_root,
        now=now,
        stale_ttl_seconds=stale_ttl_seconds,
    )
    if (
        inspection.incomplete_transaction_ids
        or inspection.recoverable_transaction_ids
        or inspection.blocked_transaction_ids
        or inspection.invalid_metadata_paths
    ):
        return TransactionTempCleanupResult(
            deleted_artifact_paths=(),
            skipped_artifact_paths=inspection.stale_artifact_paths,
            stale_artifact_paths=inspection.stale_artifact_paths,
            incomplete_transaction_ids=inspection.incomplete_transaction_ids,
            recoverable_transaction_ids=inspection.recoverable_transaction_ids,
            blocked_transaction_ids=inspection.blocked_transaction_ids,
            invalid_metadata_paths=inspection.invalid_metadata_paths,
        )

    root = Path(transaction_root).resolve(strict=False)
    store_root = _transaction_store_root_for(root)
    deleted_artifact_paths: list[str] = []
    skipped_artifact_paths: list[str] = []
    stale_path_set = set(inspection.stale_artifact_paths)

    for stale_path_text in inspection.stale_artifact_paths:
        stale_path = Path(stale_path_text)
        transaction_work_root = stale_path.parent
        try:
            transaction_id = transaction_work_root.name[: -len(TRANSACTION_WORK_DIR_SUFFIX)]
            validate_transaction_id(transaction_id)
        except StateTransactionError:
            _append_unique(skipped_artifact_paths, stale_path_text)
            continue
        if not transaction_work_root.name.endswith(TRANSACTION_WORK_DIR_SUFFIX):
            _append_unique(skipped_artifact_paths, stale_path_text)
            continue
        expected_work_root = _transaction_work_root_for(store_root, transaction_id)
        if not _path_is_under_no_follow(stale_path, expected_work_root):
            _append_unique(skipped_artifact_paths, stale_path_text)
            continue
        if not _path_is_under_no_follow(stale_path, store_root):
            _append_unique(skipped_artifact_paths, stale_path_text)
            continue
        if stale_path.is_symlink() or not stale_path.exists() or not stale_path.is_file():
            _append_unique(skipped_artifact_paths, stale_path_text)
            continue
        if stale_path_text not in stale_path_set:
            _append_unique(skipped_artifact_paths, stale_path_text)
            continue
        stale_path.unlink()
        _fsync_parent_best_effort(stale_path.parent)
        _append_unique(deleted_artifact_paths, stale_path_text)

    return TransactionTempCleanupResult(
        deleted_artifact_paths=tuple(deleted_artifact_paths),
        skipped_artifact_paths=tuple(skipped_artifact_paths),
        stale_artifact_paths=inspection.stale_artifact_paths,
        incomplete_transaction_ids=inspection.incomplete_transaction_ids,
        recoverable_transaction_ids=inspection.recoverable_transaction_ids,
        blocked_transaction_ids=inspection.blocked_transaction_ids,
        invalid_metadata_paths=inspection.invalid_metadata_paths,
    )


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
        effect=metadata.effect,
        scope=metadata.scope,
        mutation_id=metadata.mutation_id,
        rollback_eligible=metadata.rollback_eligible,
        rollback_id=metadata.rollback_id,
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
        effect=metadata.effect,
        scope=metadata.scope,
        mutation_id=metadata.mutation_id,
        rollback_eligible=metadata.rollback_eligible,
        rollback_id=metadata.rollback_id,
    )


def _call_failure_hook(
    failure_hook: Callable[[str], None] | None,
    point: str,
) -> None:
    if failure_hook is not None:
        failure_hook(point)


def _rollback_result(
    *,
    rollback_available: bool,
    rollback_id: str | None,
    transaction_id: str | None,
    status: str,
    changed_files: tuple[str, ...] = (),
    blocked_reasons: tuple[str, ...] = (),
    machine_error_code: str,
) -> TransactionRollbackResult:
    return TransactionRollbackResult(
        rollback_available=rollback_available,
        rollback_id=rollback_id,
        transaction_id=transaction_id,
        status=status,
        changed_files=changed_files,
        blocked_reasons=blocked_reasons,
        machine_error_code=machine_error_code,
    )


def _rollback_preflight_result(
    *,
    rollback_available: bool,
    rollback_id: str | None,
    transaction_id: str | None,
    mutation_id: str | None = None,
    effect: str | None = None,
    scope: str | None = None,
    status: str,
    would_change_files: tuple[str, ...] = (),
    files: tuple[TransactionRollbackPreflightFile, ...] = (),
    blocked_reasons: tuple[str, ...] = (),
    machine_error_code: str,
) -> TransactionRollbackPreflightResult:
    return TransactionRollbackPreflightResult(
        rollback_available=rollback_available,
        rollback_id=rollback_id,
        transaction_id=transaction_id,
        mutation_id=mutation_id,
        effect=effect,
        scope=scope,
        status=status,
        would_change_files=would_change_files,
        files=files,
        blocked_reasons=blocked_reasons,
        machine_error_code=machine_error_code,
    )


def _latest_rollback_eligible_metadata(
    store_root: Path,
) -> tuple[Path, TransactionMetadata] | None:
    candidates: list[tuple[datetime, str, Path, TransactionMetadata]] = []
    for metadata_path in list_transaction_metadata(store_root):
        metadata = read_transaction_metadata(metadata_path)
        if (
            metadata.state != TRANSACTION_COMMITTED
            or not metadata.rollback_eligible
            or metadata.rollback_id is None
        ):
            continue
        classification = classify_transaction_metadata(metadata)
        if classification.classification != TRANSACTION_CLEAN:
            continue
        candidates.append(
            (
                _parse_utc(metadata.updated_at_utc),
                metadata.transaction_id,
                metadata_path,
                metadata,
            )
        )
    if not candidates:
        return None
    _, _, metadata_path, metadata = max(candidates, key=lambda item: (item[0], item[1]))
    return metadata_path, metadata


def _rollback_preflight_blocked_reasons(metadata: TransactionMetadata) -> tuple[str, ...]:
    blocked_reasons: list[str] = []
    for index, record in enumerate(metadata.files):
        target = Path(record.target_path)
        target_label = f"file_{index}:{target}"
        if target.is_symlink() or not target.is_file():
            _append_unique(blocked_reasons, f"{target_label}:target_not_regular_file")
            continue
        if _sha256_file(target) != record.sha256_after:
            _append_unique(blocked_reasons, f"{target_label}:target_sha256_drift")
            continue
        if record.sha256_before is None:
            continue
        backup = Path(record.backup_path)
        rollback_temp_path = backup.parent / f"{index:04d}.rollback.tmp"
        if rollback_temp_path.exists() or rollback_temp_path.is_symlink():
            _append_unique(blocked_reasons, f"{target_label}:rollback_temp_exists")
            continue
        if backup.is_symlink() or not backup.is_file():
            _append_unique(blocked_reasons, f"{target_label}:backup_not_regular_file")
            continue
        if _sha256_file(backup) != record.sha256_before:
            _append_unique(blocked_reasons, f"{target_label}:backup_sha256_mismatch")
    return tuple(blocked_reasons)


def _rollback_preflight_files(
    metadata: TransactionMetadata,
) -> tuple[TransactionRollbackPreflightFile, ...]:
    return tuple(
        TransactionRollbackPreflightFile(
            target_path=record.target_path,
            sha256_before=record.sha256_before,
            sha256_after=record.sha256_after,
        )
        for record in metadata.files
    )


def _preflight_latest_state_transaction_rollback_with_metadata(
    transaction_root: Path,
) -> tuple[
    TransactionRollbackPreflightResult,
    tuple[Path, TransactionMetadata] | None,
]:
    root = Path(transaction_root)
    if not root.is_absolute():
        raise StateTransactionError(
            "Transaction root must be absolute.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    root = root.resolve(strict=False)
    store_root = _transaction_store_root_for(root)
    store_classification = classify_transaction_store(store_root)
    if store_classification.classification != TRANSACTION_CLEAN:
        return (
            _rollback_preflight_result(
                rollback_available=False,
                rollback_id=None,
                transaction_id=None,
                status=TRANSACTION_ROLLBACK_BLOCKED,
                blocked_reasons=(
                    f"transaction_store_{store_classification.classification}",
                ),
                machine_error_code=store_classification.machine_error_code,
            ),
            None,
        )

    latest = _latest_rollback_eligible_metadata(store_root)
    if latest is None:
        return (
            _rollback_preflight_result(
                rollback_available=False,
                rollback_id=None,
                transaction_id=None,
                status=TRANSACTION_ROLLBACK_NOT_AVAILABLE,
                machine_error_code=STATE_TRANSACTION_ROLLBACK_NOT_AVAILABLE,
            ),
            None,
        )

    _metadata_path, metadata = latest
    files = _rollback_preflight_files(metadata)
    blocked_reasons = _rollback_preflight_blocked_reasons(metadata)
    if blocked_reasons:
        return (
            _rollback_preflight_result(
                rollback_available=False,
                rollback_id=metadata.rollback_id,
                transaction_id=metadata.transaction_id,
                mutation_id=metadata.mutation_id,
                effect=metadata.effect,
                scope=metadata.scope,
                status=TRANSACTION_ROLLBACK_BLOCKED,
                files=files,
                blocked_reasons=blocked_reasons,
                machine_error_code=STATE_TRANSACTION_ROLLBACK_BLOCKED,
            ),
            None,
        )

    return (
        _rollback_preflight_result(
            rollback_available=True,
            rollback_id=metadata.rollback_id,
            transaction_id=metadata.transaction_id,
            mutation_id=metadata.mutation_id,
            effect=metadata.effect,
            scope=metadata.scope,
            status=TRANSACTION_ROLLBACK_READY,
            would_change_files=tuple(record.target_path for record in metadata.files),
            files=files,
            machine_error_code=STATE_TRANSACTION_ROLLBACK_READY,
        ),
        latest,
    )


def preflight_latest_state_transaction_rollback(
    transaction_root: Path,
) -> TransactionRollbackPreflightResult:
    preflight, _latest = _preflight_latest_state_transaction_rollback_with_metadata(
        transaction_root
    )
    return preflight


def rollback_latest_state_transaction(
    transaction_root: Path,
    *,
    expected_transaction_id: str | None = None,
    expected_rollback_id: str | None = None,
    failure_hook: Callable[[str], None] | None = None,
) -> TransactionRollbackResult:
    if expected_transaction_id is not None:
        validate_transaction_id(expected_transaction_id)
    if expected_rollback_id is not None:
        validate_rollback_id(expected_rollback_id)
    preflight, latest = _preflight_latest_state_transaction_rollback_with_metadata(
        transaction_root
    )
    if not preflight.rollback_available:
        return _rollback_result(
            rollback_available=False,
            rollback_id=preflight.rollback_id,
            transaction_id=preflight.transaction_id,
            status=preflight.status,
            blocked_reasons=preflight.blocked_reasons,
            machine_error_code=preflight.machine_error_code,
        )
    if latest is None:
        raise StateTransactionError(
            "Rollback preflight reported availability without transaction metadata.",
            machine_error_code=STATE_TRANSACTION_INVALID,
        )
    if (
        (expected_transaction_id is not None and preflight.transaction_id != expected_transaction_id)
        or (expected_rollback_id is not None and preflight.rollback_id != expected_rollback_id)
    ):
        return _rollback_result(
            rollback_available=False,
            rollback_id=preflight.rollback_id,
            transaction_id=preflight.transaction_id,
            status=TRANSACTION_ROLLBACK_BLOCKED,
            blocked_reasons=("latest_transaction_changed_after_preflight",),
            machine_error_code=STATE_TRANSACTION_ROLLBACK_BLOCKED,
        )
    metadata_path, metadata = latest

    changed_files: list[str] = []
    try:
        for index, record in reversed(tuple(enumerate(metadata.files))):
            target = Path(record.target_path)
            _call_failure_hook(failure_hook, "before_rollback_file")
            if record.sha256_before is None:
                target.unlink()
                _fsync_parent_best_effort(target.parent)
            else:
                backup = Path(record.backup_path)
                rollback_temp_path = backup.parent / f"{index:04d}.rollback.tmp"
                try:
                    _write_bytes_fsync(rollback_temp_path, backup.read_bytes())
                    os.replace(rollback_temp_path, target)
                    _fsync_parent_best_effort(target.parent)
                finally:
                    if rollback_temp_path.exists():
                        rollback_temp_path.unlink()
                        _fsync_parent_best_effort(rollback_temp_path.parent)
            _call_failure_hook(failure_hook, "after_rollback_file")
            _append_unique(changed_files, str(target))
        write_transaction_metadata(
            metadata_path,
            _metadata_with_state(metadata, state=TRANSACTION_ROLLED_BACK),
        )
    except Exception as exc:  # noqa: BLE001
        failed_metadata = _failed_metadata(
            metadata,
            state=TRANSACTION_FAILED_BLOCKED,
            files=metadata.files,
            error=str(exc) or exc.__class__.__name__,
        )
        write_transaction_metadata(metadata_path, failed_metadata)
        raise StateTransactionError(
            "Transaction rollback failed.",
            machine_error_code=STATE_TRANSACTION_FAILED_BLOCKED,
        ) from exc

    return _rollback_result(
        rollback_available=True,
        rollback_id=metadata.rollback_id,
        transaction_id=metadata.transaction_id,
        status=TRANSACTION_ROLLBACK_COMPLETED,
        changed_files=tuple(changed_files),
        machine_error_code=STATE_TRANSACTION_ROLLBACK_COMPLETED,
    )


def commit_state_transaction(
    transaction_root: Path,
    transaction_id: str,
    writes: tuple[TransactionWrite, ...],
    *,
    effect: str | None = None,
    scope: str | None = None,
    mutation_id: str | None = None,
    rollback_eligible: bool = False,
    rollback_id: str | None = None,
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
    rollback_id_value = (
        rollback_id_for_transaction(validated_transaction_id)
        if rollback_eligible and rollback_id is None
        else rollback_id
    )
    _validate_metadata_rollback_fields(
        TransactionMetadata(
            schema_version=TRANSACTION_METADATA_SCHEMA_VERSION,
            transaction_id=validated_transaction_id,
            state=TRANSACTION_PREPARING,
            created_at_utc="2026-01-01T00:00:00+00:00",
            updated_at_utc="2026-01-01T00:00:00+00:00",
            transaction_root=str(root),
            files=(),
            error=None,
            effect=effect,
            scope=scope,
            mutation_id=mutation_id,
            rollback_eligible=rollback_eligible,
            rollback_id=rollback_id_value,
        )
    )
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
        effect=effect,
        scope=scope,
        mutation_id=mutation_id,
        rollback_eligible=rollback_eligible,
        rollback_id=rollback_id_value,
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
