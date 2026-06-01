# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


STATE_SCHEMA_MISSING = "STATE_SCHEMA_MISSING"
STATE_SCHEMA_UNSUPPORTED = "STATE_SCHEMA_UNSUPPORTED"
STATE_PAYLOAD_INVALID = "STATE_PAYLOAD_INVALID"
STATE_NOT_FOUND = "STATE_NOT_FOUND"
STATE_CORRUPT = "STATE_CORRUPT"
STATE_VALIDATION_FAILED = "STATE_VALIDATION_FAILED"
STATE_WRITE_FAILED = "STATE_WRITE_FAILED"

_NO_DEFAULT = object()


@dataclass(frozen=True)
class StateStoreWriteResult:
    target: str
    committed: bool
    changed_files: tuple[str, ...]
    schema_version: int | None


class StateStoreError(Exception):
    def __init__(self, message: str, *, machine_error_code: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def _schema_version(
    payload: dict[str, Any], expected_schema_version: int | None
) -> int | None:
    version = payload.get("schema_version")
    if "schema_version" in payload and isinstance(version, bool):
        raise StateStoreError(
            "State payload schema_version is unsupported.",
            machine_error_code=STATE_SCHEMA_UNSUPPORTED,
        )
    if expected_schema_version is None:
        return version if isinstance(version, int) else None
    if "schema_version" not in payload:
        raise StateStoreError(
            "State payload is missing schema_version.",
            machine_error_code=STATE_SCHEMA_MISSING,
        )
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != expected_schema_version
    ):
        raise StateStoreError(
            "State payload schema_version is unsupported.",
            machine_error_code=STATE_SCHEMA_UNSUPPORTED,
        )
    return version


def _ensure_json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StateStoreError(
            "State JSON payload must be an object.",
            machine_error_code=STATE_PAYLOAD_INVALID,
        )
    return value


def _validate_payload(
    payload: dict[str, Any],
    validator: Callable[[dict[str, Any]], object] | None,
) -> None:
    if validator is None:
        return
    try:
        result = validator(payload)
    except StateStoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise StateStoreError(
            "State payload validation failed.",
            machine_error_code=STATE_VALIDATION_FAILED,
        ) from exc
    if result is False:
        raise StateStoreError(
            "State payload validation failed.",
            machine_error_code=STATE_VALIDATION_FAILED,
        )


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


def _atomic_write_bytes(path: Path, data: bytes, *, mode: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = ""
    fd = -1
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=target.parent,
            prefix=".wbp-tmp-",
            suffix=f".{target.name}",
        )
        with os.fdopen(fd, "wb") as file_obj:
            fd = -1
            file_obj.write(data)
            file_obj.flush()
            if mode is not None:
                os.fchmod(file_obj.fileno(), mode)
            os.fsync(file_obj.fileno())
        os.replace(temp_path, target)
        temp_path = ""
        _fsync_parent_best_effort(target.parent)
    except Exception as exc:  # noqa: BLE001
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, StateStoreError):
            raise
        raise StateStoreError(
            f"Failed to write state file: {target}",
            machine_error_code=STATE_WRITE_FAILED,
        ) from exc


def read_json(
    path: Path,
    *,
    expected_schema_version: int | None = None,
    default: dict[str, Any] | object = _NO_DEFAULT,
) -> dict[str, Any]:
    target = Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        if default is _NO_DEFAULT:
            raise StateStoreError(
                f"State file does not exist: {target}",
                machine_error_code=STATE_NOT_FOUND,
            ) from None
        default_payload = dict(_ensure_json_object(default))
        _schema_version(default_payload, expected_schema_version)
        return default_payload
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateStoreError(
            f"State file is corrupt JSON: {target}",
            machine_error_code=STATE_CORRUPT,
        ) from exc
    payload = _ensure_json_object(payload)
    _schema_version(payload, expected_schema_version)
    return payload


def write_json(
    path: Path,
    payload: dict[str, Any],
    *,
    expected_schema_version: int | None = None,
    validator: Callable[[dict[str, Any]], object] | None = None,
) -> StateStoreWriteResult:
    payload = _ensure_json_object(payload)
    schema_version = _schema_version(payload, expected_schema_version)
    _validate_payload(payload, validator)
    data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    _atomic_write_bytes(Path(path), data)
    return StateStoreWriteResult(
        target=str(path),
        committed=True,
        changed_files=(str(path),),
        schema_version=schema_version,
    )


def write_text(
    path: Path,
    value: str,
    *,
    mode: int | None = None,
) -> StateStoreWriteResult:
    _atomic_write_bytes(Path(path), value.encode("utf-8"), mode=mode)
    return StateStoreWriteResult(
        target=str(path),
        committed=True,
        changed_files=(str(path),),
        schema_version=None,
    )
