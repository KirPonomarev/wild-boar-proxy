# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Packet-only helpers for describing filesystem mutations in command payloads."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

ROLLBACK_PHASE_LEDGER_ONLY = "ledger_only"
KIND_FILE = "file"
KIND_DIR = "dir"
KIND_MISSING = "missing"
KIND_OTHER = "other"

OPERATION_CREATE = "create"
OPERATION_DELETE = "delete"
OPERATION_REPLACE = "replace"
OPERATION_METADATA_CHANGE = "metadata_change"
OPERATION_UNKNOWN = "unknown"

Pathish = str | os.PathLike[str]


@dataclass(frozen=True)
class PathSnapshot:
    path: str
    kind: str
    mode: int | None
    mtime_ns: int | None
    size: int | None
    sha256: str | None

    def to_packet_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "mtime_ns": self.mtime_ns,
            "size": self.size,
            "sha256": self.sha256,
        }


def snapshot_path(path: Pathish) -> PathSnapshot:
    normalized = _normalize_path(path)
    candidate = Path(normalized)
    try:
        stat_result = candidate.lstat()
    except FileNotFoundError:
        return _missing_snapshot(normalized)
    except OSError:
        return PathSnapshot(
            path=normalized,
            kind=KIND_OTHER,
            mode=None,
            mtime_ns=None,
            size=None,
            sha256=None,
        )

    kind = classify_path_kind_from_mode(stat_result.st_mode)
    sha256 = _sha256_file(candidate) if kind == KIND_FILE else None
    size = stat_result.st_size if kind == KIND_FILE else None
    return PathSnapshot(
        path=normalized,
        kind=kind,
        mode=stat_result.st_mode,
        mtime_ns=stat_result.st_mtime_ns,
        size=size,
        sha256=sha256,
    )


def snapshot_paths(paths: Iterable[Pathish]) -> dict[str, PathSnapshot]:
    snapshots: dict[str, PathSnapshot] = {}
    for path in paths:
        snapshot = snapshot_path(path)
        snapshots[snapshot.path] = snapshot
    return snapshots


def build_mutation_record(
    path: Pathish,
    *,
    before: PathSnapshot | None,
    after: PathSnapshot | None,
) -> dict[str, Any]:
    normalized = _normalize_path(path)
    before_snapshot = before or _missing_snapshot(normalized)
    after_snapshot = after or _missing_snapshot(normalized)
    return {
        "path": normalized,
        "kind": after_snapshot.kind,
        "operation": derive_operation(before_snapshot, after_snapshot),
        "before_kind": before_snapshot.kind,
        "after_kind": after_snapshot.kind,
        "before_sha256": before_snapshot.sha256,
        "after_sha256": after_snapshot.sha256,
        "before": before_snapshot.to_packet_dict(),
        "after": after_snapshot.to_packet_dict(),
    }


def build_mutation_ledger_fields(
    *,
    effect: str,
    scope: str,
    changed_files: Iterable[Pathish],
    before: Mapping[str, PathSnapshot],
    after: Mapping[str, PathSnapshot],
) -> dict[str, Any]:
    normalized_paths = _normalize_changed_paths(changed_files)
    records = [
        build_mutation_record(
            path,
            before=before.get(path),
            after=after.get(path),
        )
        for path in normalized_paths
    ]
    mutation_id = (
        _build_mutation_id(effect=effect, scope=scope, records=records)
        if records
        else None
    )
    return {
        "mutation_id": mutation_id,
        "mutation_ledger": {
            "schema_version": 1,
            "status": "mutated" if records else "not_mutated",
            "effect": effect,
            "scope": scope,
            "changed_files": records,
            "rollback_available": False,
            "rollback_id": None,
            "rollback_phase": ROLLBACK_PHASE_LEDGER_ONLY,
        },
    }


def build_mutation_ledger(
    *,
    changed_files: Iterable[Pathish],
    before: Mapping[str, PathSnapshot],
    after: Mapping[str, PathSnapshot],
) -> dict[str, Any]:
    return build_mutation_ledger_fields(
        effect="repair",
        scope="healthcheck_repair",
        changed_files=changed_files,
        before=before,
        after=after,
    )


def classify_path_kind(path: Pathish) -> str:
    return snapshot_path(path).kind


def classify_path_kind_from_mode(mode: int) -> str:
    if stat.S_ISREG(mode):
        return KIND_FILE
    if stat.S_ISDIR(mode):
        return KIND_DIR
    return KIND_OTHER


def derive_operation(before: PathSnapshot, after: PathSnapshot) -> str:
    if before.kind == KIND_MISSING and after.kind != KIND_MISSING:
        return OPERATION_CREATE
    if before.kind != KIND_MISSING and after.kind == KIND_MISSING:
        return OPERATION_DELETE
    if before.kind == KIND_MISSING and after.kind == KIND_MISSING:
        return OPERATION_UNKNOWN
    if before.kind != after.kind:
        return OPERATION_REPLACE
    if before.kind == KIND_FILE and before.sha256 != after.sha256:
        return OPERATION_REPLACE
    if _metadata_fingerprint(before) != _metadata_fingerprint(after):
        return OPERATION_METADATA_CHANGE
    return OPERATION_UNKNOWN


def _build_mutation_id(
    *, effect: str, scope: str, records: list[dict[str, Any]]
) -> str:
    payload = json.dumps(
        {"effect": effect, "scope": scope, "records": records},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"wbp-mut-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _metadata_fingerprint(snapshot: PathSnapshot) -> tuple[Any, ...]:
    return (
        snapshot.kind,
        snapshot.mode,
        snapshot.mtime_ns,
        snapshot.size,
    )


def _normalize_changed_paths(paths: Iterable[Pathish]) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        value = _normalize_path(path)
        if value not in normalized:
            normalized.append(value)
    return normalized


def _normalize_path(path: Pathish) -> str:
    return os.path.abspath(os.path.normpath(os.fspath(path)))


def _missing_snapshot(path: str) -> PathSnapshot:
    return PathSnapshot(
        path=path,
        kind=KIND_MISSING,
        mode=None,
        mtime_ns=None,
        size=None,
        sha256=None,
    )


def _sha256_file(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


__all__ = [
    "KIND_DIR",
    "KIND_FILE",
    "KIND_MISSING",
    "KIND_OTHER",
    "OPERATION_CREATE",
    "OPERATION_DELETE",
    "OPERATION_METADATA_CHANGE",
    "OPERATION_REPLACE",
    "OPERATION_UNKNOWN",
    "PathSnapshot",
    "ROLLBACK_PHASE_LEDGER_ONLY",
    "build_mutation_ledger",
    "build_mutation_ledger_fields",
    "build_mutation_record",
    "classify_path_kind",
    "classify_path_kind_from_mode",
    "derive_operation",
    "snapshot_path",
    "snapshot_paths",
]
