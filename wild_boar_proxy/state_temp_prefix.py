# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


STATE_TEMP_PREFIX_INVALID = "STATE_TEMP_PREFIX_INVALID"

DEFAULT_TEMP_PREFIX = ".wbp-tmp-"
DEFAULT_STALE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class PrefixedTempArtifact:
    path: str
    root: str
    stale: bool
    blocked: bool


@dataclass(frozen=True)
class PrefixedTempInspection:
    candidate_paths: tuple[str, ...]
    fresh_paths: tuple[str, ...]
    stale_paths: tuple[str, ...]
    blocked_paths: tuple[str, ...]
    invalid_roots: tuple[str, ...]
    artifacts: tuple[PrefixedTempArtifact, ...]


@dataclass(frozen=True)
class PrefixedTempCleanupResult:
    deleted_paths: tuple[str, ...]
    skipped_paths: tuple[str, ...]
    stale_paths: tuple[str, ...]
    fresh_paths: tuple[str, ...]
    blocked_paths: tuple[str, ...]
    invalid_roots: tuple[str, ...]

    @property
    def cleanup_performed(self) -> bool:
        return bool(self.deleted_paths)

    @property
    def cleanup_blocked(self) -> bool:
        return bool(self.blocked_paths or self.invalid_roots)


class StateTempPrefixError(Exception):
    def __init__(self, message: str, *, machine_error_code: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def _absolute_path_no_follow(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _path_str_no_follow(path: Path) -> str:
    return str(_absolute_path_no_follow(path))


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise StateTempPrefixError(
            "Inspection time must include timezone.",
            machine_error_code=STATE_TEMP_PREFIX_INVALID,
        )
    return now.astimezone(timezone.utc)


def _normalize_prefix(prefix: str) -> str:
    if not isinstance(prefix, str) or not prefix or "\x00" in prefix:
        raise StateTempPrefixError(
            "Temp prefix must be a non-empty string.",
            machine_error_code=STATE_TEMP_PREFIX_INVALID,
        )
    return prefix


def _normalize_ttl(stale_ttl_seconds: int) -> int:
    if (
        isinstance(stale_ttl_seconds, bool)
        or not isinstance(stale_ttl_seconds, int)
        or stale_ttl_seconds < 0
    ):
        raise StateTempPrefixError(
            "Temp prefix TTL must be a non-negative integer.",
            machine_error_code=STATE_TEMP_PREFIX_INVALID,
        )
    return stale_ttl_seconds


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


def _normalize_roots(admitted_control_owned_parent_roots: tuple[Path, ...]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[str] = set()
    for root in admitted_control_owned_parent_roots:
        candidate = Path(root)
        if not candidate.is_absolute():
            raise StateTempPrefixError(
                "Admitted control-owned parent roots must be absolute.",
                machine_error_code=STATE_TEMP_PREFIX_INVALID,
            )
        normalized_candidate = _absolute_path_no_follow(candidate)
        key = str(normalized_candidate)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(normalized_candidate)
    return tuple(normalized)


def _artifact_is_stale(path: Path, *, now: datetime, stale_ttl_seconds: int) -> bool:
    modified_at = datetime.fromtimestamp(path.stat(follow_symlinks=False).st_mtime, timezone.utc)
    return modified_at <= now - timedelta(seconds=stale_ttl_seconds)


def _append_artifact(
    artifacts_by_path: dict[str, PrefixedTempArtifact],
    *,
    path: str,
    root: str,
    stale: bool,
    blocked: bool,
) -> None:
    artifacts_by_path[path] = PrefixedTempArtifact(
        path=path,
        root=root,
        stale=stale,
        blocked=blocked,
    )


def inspect_prefixed_temp_artifacts(
    admitted_control_owned_parent_roots: tuple[Path, ...],
    *,
    prefix: str = DEFAULT_TEMP_PREFIX,
    now: datetime | None = None,
    stale_ttl_seconds: int = DEFAULT_STALE_TTL_SECONDS,
) -> PrefixedTempInspection:
    normalized_roots = _normalize_roots(admitted_control_owned_parent_roots)
    normalized_prefix = _normalize_prefix(prefix)
    normalized_now = _normalize_now(now)
    normalized_ttl = _normalize_ttl(stale_ttl_seconds)

    candidate_paths: list[str] = []
    fresh_paths: list[str] = []
    stale_paths: list[str] = []
    blocked_paths: list[str] = []
    invalid_roots: list[str] = []
    artifacts_by_path: dict[str, PrefixedTempArtifact] = {}

    for root in normalized_roots:
        root_key = str(root)
        if root.is_symlink():
            _append_unique(invalid_roots, root_key)
            continue
        if not root.exists():
            continue
        if not root.is_dir():
            _append_unique(invalid_roots, root_key)
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            if not child.name.startswith(normalized_prefix):
                continue
            child_key = _path_str_no_follow(child)
            if child.is_symlink() or not child.is_file():
                _append_unique(blocked_paths, child_key)
                _append_artifact(
                    artifacts_by_path,
                    path=child_key,
                    root=root_key,
                    stale=False,
                    blocked=True,
                )
                continue
            _append_unique(candidate_paths, child_key)
            stale = _artifact_is_stale(
                child,
                now=normalized_now,
                stale_ttl_seconds=normalized_ttl,
            )
            if stale:
                _append_unique(stale_paths, child_key)
            else:
                _append_unique(fresh_paths, child_key)
            _append_artifact(
                artifacts_by_path,
                path=child_key,
                root=root_key,
                stale=stale,
                blocked=False,
            )

    return PrefixedTempInspection(
        candidate_paths=tuple(candidate_paths),
        fresh_paths=tuple(fresh_paths),
        stale_paths=tuple(stale_paths),
        blocked_paths=tuple(blocked_paths),
        invalid_roots=tuple(invalid_roots),
        artifacts=tuple(sorted(artifacts_by_path.values(), key=lambda artifact: artifact.path)),
    )


def cleanup_prefixed_temp_artifacts(
    admitted_control_owned_parent_roots: tuple[Path, ...],
    *,
    prefix: str = DEFAULT_TEMP_PREFIX,
    now: datetime | None = None,
    stale_ttl_seconds: int = DEFAULT_STALE_TTL_SECONDS,
) -> PrefixedTempCleanupResult:
    inspection = inspect_prefixed_temp_artifacts(
        admitted_control_owned_parent_roots,
        prefix=prefix,
        now=now,
        stale_ttl_seconds=stale_ttl_seconds,
    )
    if inspection.invalid_roots or inspection.blocked_paths:
        return PrefixedTempCleanupResult(
            deleted_paths=(),
            skipped_paths=inspection.stale_paths,
            stale_paths=inspection.stale_paths,
            fresh_paths=inspection.fresh_paths,
            blocked_paths=inspection.blocked_paths,
            invalid_roots=inspection.invalid_roots,
        )

    artifacts_by_path = {artifact.path: artifact for artifact in inspection.artifacts}
    admitted_root_keys = {
        str(root)
        for root in _normalize_roots(admitted_control_owned_parent_roots)
    }
    deleted_paths: list[str] = []
    skipped_paths: list[str] = []

    for stale_path_text in inspection.stale_paths:
        artifact = artifacts_by_path.get(stale_path_text)
        if artifact is None or artifact.blocked or not artifact.stale:
            _append_unique(skipped_paths, stale_path_text)
            continue
        if artifact.root not in admitted_root_keys:
            _append_unique(skipped_paths, stale_path_text)
            continue

        stale_path = Path(stale_path_text)
        parent_key = _path_str_no_follow(stale_path.parent)
        if parent_key != artifact.root:
            _append_unique(skipped_paths, stale_path_text)
            continue
        if stale_path.is_symlink() or not stale_path.exists() or not stale_path.is_file():
            _append_unique(skipped_paths, stale_path_text)
            continue

        stale_path.unlink()
        _fsync_parent_best_effort(stale_path.parent)
        _append_unique(deleted_paths, stale_path_text)

    return PrefixedTempCleanupResult(
        deleted_paths=tuple(deleted_paths),
        skipped_paths=tuple(skipped_paths),
        stale_paths=inspection.stale_paths,
        fresh_paths=inspection.fresh_paths,
        blocked_paths=inspection.blocked_paths,
        invalid_roots=inspection.invalid_roots,
    )
