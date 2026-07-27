# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping


STATE_LOCK_ACTIVE = "STATE_LOCK_ACTIVE"
STATE_LOCK_STALE = "STATE_LOCK_STALE"
STATE_LOCK_SUSPICIOUS = "STATE_LOCK_SUSPICIOUS"
STATE_LOCK_INVALID = "STATE_LOCK_INVALID"

LOCK_ACTIVE = "active"
LOCK_STALE = "stale"
LOCK_SUSPICIOUS = "suspicious"
LOCK_INVALID = "invalid"


@dataclass(frozen=True)
class LockMetadata:
    pid: int
    uid: int
    hostname: str
    process_create_time: float
    started_at_utc: str
    command: str


@dataclass(frozen=True)
class ProcessProbeResult:
    pid_exists: bool
    uid: int | None
    hostname: str | None
    process_create_time: float | None


@dataclass(frozen=True)
class LockOwnerClassification:
    status: str
    machine_error_code: str
    reason: str


def _classification(status: str, machine_error_code: str, reason: str) -> LockOwnerClassification:
    return LockOwnerClassification(
        status=status,
        machine_error_code=machine_error_code,
        reason=reason,
    )


def _coerce_metadata(
    metadata: LockMetadata | Mapping[str, object],
) -> LockMetadata | None:
    if isinstance(metadata, LockMetadata):
        candidate = metadata
    else:
        required = {
            "pid",
            "uid",
            "hostname",
            "process_create_time",
            "started_at_utc",
            "command",
        }
        if not required.issubset(metadata.keys()):
            return None
        candidate = LockMetadata(
            pid=metadata["pid"],  # type: ignore[arg-type]
            uid=metadata["uid"],  # type: ignore[arg-type]
            hostname=metadata["hostname"],  # type: ignore[arg-type]
            process_create_time=metadata["process_create_time"],  # type: ignore[arg-type]
            started_at_utc=metadata["started_at_utc"],  # type: ignore[arg-type]
            command=metadata["command"],  # type: ignore[arg-type]
        )
    if (
        not isinstance(candidate.pid, int)
        or isinstance(candidate.pid, bool)
        or candidate.pid <= 0
        or not isinstance(candidate.uid, int)
        or isinstance(candidate.uid, bool)
        or not isinstance(candidate.hostname, str)
        or not candidate.hostname
        or not isinstance(candidate.process_create_time, (int, float))
        or candidate.process_create_time < 0
        or not isinstance(candidate.started_at_utc, str)
        or not candidate.started_at_utc
        or not isinstance(candidate.command, str)
        or not candidate.command
    ):
        return None
    try:
        _parse_utc(candidate.started_at_utc)
    except ValueError:
        return None
    return candidate


def _parse_utc(value: str) -> datetime:
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("lock timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _is_old_lock(
    metadata: LockMetadata,
    *,
    now_utc: datetime,
    stale_after_seconds: float,
) -> bool:
    if stale_after_seconds < 0:
        return False
    started_at = _parse_utc(metadata.started_at_utc)
    return (now_utc.astimezone(timezone.utc) - started_at).total_seconds() >= stale_after_seconds


def classify_lock_owner(
    metadata: LockMetadata | Mapping[str, object],
    probe: ProcessProbeResult,
    *,
    now_utc: datetime,
    stale_after_seconds: float,
) -> LockOwnerClassification:
    parsed = _coerce_metadata(metadata)
    if parsed is None:
        return _classification(
            LOCK_INVALID,
            STATE_LOCK_INVALID,
            "lock metadata is missing required fields or has invalid values",
        )

    old_lock = _is_old_lock(
        parsed,
        now_utc=now_utc,
        stale_after_seconds=stale_after_seconds,
    )
    if not probe.pid_exists:
        return _classification(
            LOCK_STALE,
            STATE_LOCK_STALE,
            "lock owner process is not alive",
        )

    if probe.uid != parsed.uid:
        return _classification(
            LOCK_SUSPICIOUS,
            STATE_LOCK_SUSPICIOUS,
            "lock owner pid is alive with a different uid",
        )
    if probe.hostname != parsed.hostname:
        return _classification(
            LOCK_SUSPICIOUS,
            STATE_LOCK_SUSPICIOUS,
            "lock owner pid is alive on a different hostname",
        )
    if probe.process_create_time is None:
        return _classification(
            LOCK_SUSPICIOUS,
            STATE_LOCK_SUSPICIOUS,
            "lock owner pid is alive but create_time is unavailable",
        )
    if probe.process_create_time != parsed.process_create_time:
        return _classification(
            LOCK_STALE,
            STATE_LOCK_STALE,
            "lock owner pid was recycled",
        )

    if old_lock:
        return _classification(
            LOCK_ACTIVE,
            STATE_LOCK_ACTIVE,
            "lock owner is old but still matches the live same-owner process",
        )
    return _classification(
        LOCK_ACTIVE,
        STATE_LOCK_ACTIVE,
        "lock owner matches the live same-owner process",
    )
