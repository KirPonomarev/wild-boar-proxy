# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from wild_boar_proxy import state_lock


LOCK_SLICE_CLEAR = "lock_slice_clear"
LOCK_SLICE_STALE = "lock_slice_stale"
LOCK_SLICE_SUSPICIOUS = "lock_slice_suspicious"
LOCK_SLICE_INVALID = "lock_slice_invalid"

STATE_STARTUP_LOCK_SLICE_CLEAR = "STATE_STARTUP_LOCK_SLICE_CLEAR"
STATE_STARTUP_LOCK_SLICE_STALE = "STATE_STARTUP_LOCK_SLICE_STALE"
STATE_STARTUP_LOCK_SLICE_SUSPICIOUS = "STATE_STARTUP_LOCK_SLICE_SUSPICIOUS"
STATE_STARTUP_LOCK_SLICE_INVALID = "STATE_STARTUP_LOCK_SLICE_INVALID"

LOCK_SLICE_RECOVERY_CLEAN = "lock_slice_recovery_clean"
LOCK_SLICE_RECOVERY_RECOVERED = "lock_slice_recovery_recovered"
LOCK_SLICE_RECOVERY_BLOCKED = "lock_slice_recovery_blocked"

STATE_STARTUP_LOCK_SLICE_RECOVERY_CLEAN = "STATE_STARTUP_LOCK_SLICE_RECOVERY_CLEAN"
STATE_STARTUP_LOCK_SLICE_RECOVERY_RECOVERED = "STATE_STARTUP_LOCK_SLICE_RECOVERY_RECOVERED"
STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED = "STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED"


@dataclass(frozen=True)
class StartupLockSliceAssessment:
    lock_slice_outcome: str
    machine_error_code: str
    reason: str
    owner_classification: state_lock.LockOwnerClassification | None


@dataclass(frozen=True)
class StartupLockSliceRecoveryResult:
    lock_slice_recovery_outcome: str
    machine_error_code: str
    cleanup_performed: bool
    reason: str
    assessment: StartupLockSliceAssessment | None
    deleted_lock_path: str | None


def _assessment(
    lock_slice_outcome: str,
    machine_error_code: str,
    reason: str,
    *,
    owner_classification: state_lock.LockOwnerClassification | None,
) -> StartupLockSliceAssessment:
    return StartupLockSliceAssessment(
        lock_slice_outcome=lock_slice_outcome,
        machine_error_code=machine_error_code,
        reason=reason,
        owner_classification=owner_classification,
    )


def _recovery_result(
    lock_slice_recovery_outcome: str,
    machine_error_code: str,
    reason: str,
    *,
    cleanup_performed: bool,
    assessment: StartupLockSliceAssessment | None,
    deleted_lock_path: str | None = None,
) -> StartupLockSliceRecoveryResult:
    return StartupLockSliceRecoveryResult(
        lock_slice_recovery_outcome=lock_slice_recovery_outcome,
        machine_error_code=machine_error_code,
        cleanup_performed=cleanup_performed,
        reason=reason,
        assessment=assessment,
        deleted_lock_path=deleted_lock_path,
    )


def _absolute_path_no_follow(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _path_str_no_follow(path: Path) -> str:
    return str(_absolute_path_no_follow(path))


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


def _normalize_admitted_lock_path(path: Path) -> Path | None:
    candidate = Path(path)
    if not candidate.is_absolute():
        return None
    return _absolute_path_no_follow(candidate)


def _classification_to_assessment(
    classification: state_lock.LockOwnerClassification,
) -> StartupLockSliceAssessment:
    status_map = {
        state_lock.LOCK_ACTIVE: LOCK_SLICE_CLEAR,
        state_lock.LOCK_STALE: LOCK_SLICE_STALE,
        state_lock.LOCK_SUSPICIOUS: LOCK_SLICE_SUSPICIOUS,
        state_lock.LOCK_INVALID: LOCK_SLICE_INVALID,
    }
    machine_error_code_map = {
        state_lock.LOCK_ACTIVE: STATE_STARTUP_LOCK_SLICE_CLEAR,
        state_lock.LOCK_STALE: STATE_STARTUP_LOCK_SLICE_STALE,
        state_lock.LOCK_SUSPICIOUS: STATE_STARTUP_LOCK_SLICE_SUSPICIOUS,
        state_lock.LOCK_INVALID: STATE_STARTUP_LOCK_SLICE_INVALID,
    }
    outcome = status_map[classification.status]
    machine_error_code = machine_error_code_map[classification.status]
    return _assessment(
        outcome,
        machine_error_code,
        classification.reason,
        owner_classification=classification,
    )


def assess_startup_lock_slice(
    lock_metadata: state_lock.LockMetadata | Mapping[str, object] | None,
    probe: state_lock.ProcessProbeResult | None,
    *,
    now_utc: datetime,
    stale_after_seconds: float,
) -> StartupLockSliceAssessment:
    if lock_metadata is None and probe is None:
        return _assessment(
            LOCK_SLICE_CLEAR,
            STATE_STARTUP_LOCK_SLICE_CLEAR,
            "no lock owner metadata or process probe was provided",
            owner_classification=None,
        )
    if lock_metadata is None or probe is None:
        return _assessment(
            LOCK_SLICE_INVALID,
            STATE_STARTUP_LOCK_SLICE_INVALID,
            "lock metadata and process probe must both be provided or both be omitted",
            owner_classification=None,
        )
    classification = state_lock.classify_lock_owner(
        lock_metadata,
        probe,
        now_utc=now_utc,
        stale_after_seconds=stale_after_seconds,
    )
    return _classification_to_assessment(classification)


def run_startup_lock_slice_recovery(
    admitted_control_owned_lock_path: Path,
    lock_metadata: state_lock.LockMetadata | Mapping[str, object] | None,
    probe: state_lock.ProcessProbeResult | None,
    *,
    assessment_source_lock_path: Path | None = None,
    now_utc: datetime,
    stale_after_seconds: float,
) -> StartupLockSliceRecoveryResult:
    admitted_lock_path = _normalize_admitted_lock_path(admitted_control_owned_lock_path)
    if admitted_lock_path is None:
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            "admitted control-owned lock path must be absolute",
            cleanup_performed=False,
            assessment=None,
        )

    has_assessment_facts = lock_metadata is not None or probe is not None
    if has_assessment_facts and assessment_source_lock_path is None:
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            "same-source lock assessment path is required when lock facts are provided",
            cleanup_performed=False,
            assessment=None,
        )

    normalized_assessment_source: Path | None = None
    if assessment_source_lock_path is not None:
        normalized_assessment_source = _normalize_admitted_lock_path(assessment_source_lock_path)
        if normalized_assessment_source is None:
            return _recovery_result(
                LOCK_SLICE_RECOVERY_BLOCKED,
                STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
                "assessment source lock path must be absolute",
                cleanup_performed=False,
                assessment=None,
            )
        if normalized_assessment_source != admitted_lock_path:
            return _recovery_result(
                LOCK_SLICE_RECOVERY_BLOCKED,
                STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
                "assessment source lock path must match the admitted control-owned lock path",
                cleanup_performed=False,
                assessment=None,
            )

    if admitted_lock_path.is_symlink():
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            "admitted control-owned lock path must not be a symlink",
            cleanup_performed=False,
            assessment=None,
        )

    if admitted_lock_path.exists() and not admitted_lock_path.is_file():
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            "admitted control-owned lock path must be a regular file when present",
            cleanup_performed=False,
            assessment=None,
        )

    assessment = assess_startup_lock_slice(
        lock_metadata,
        probe,
        now_utc=now_utc,
        stale_after_seconds=stale_after_seconds,
    )

    if assessment.lock_slice_outcome == LOCK_SLICE_INVALID:
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            assessment.reason,
            cleanup_performed=False,
            assessment=assessment,
        )

    if assessment.lock_slice_outcome == LOCK_SLICE_SUSPICIOUS:
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            assessment.reason,
            cleanup_performed=False,
            assessment=assessment,
        )

    if assessment.lock_slice_outcome == LOCK_SLICE_CLEAR:
        if assessment.owner_classification is None and admitted_lock_path.exists():
            return _recovery_result(
                LOCK_SLICE_RECOVERY_BLOCKED,
                STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
                "existing admitted control-owned lock file requires same-source assessment facts",
                cleanup_performed=False,
                assessment=assessment,
            )
        return _recovery_result(
            LOCK_SLICE_RECOVERY_CLEAN,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_CLEAN,
            assessment.reason,
            cleanup_performed=False,
            assessment=assessment,
        )

    if not admitted_lock_path.exists():
        return _recovery_result(
            LOCK_SLICE_RECOVERY_CLEAN,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_CLEAN,
            "stale admitted control-owned lock file was already absent",
            cleanup_performed=False,
            assessment=assessment,
        )

    if admitted_lock_path.is_symlink() or not admitted_lock_path.is_file():
        return _recovery_result(
            LOCK_SLICE_RECOVERY_BLOCKED,
            STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED,
            "stale admitted control-owned lock path must be a regular file",
            cleanup_performed=False,
            assessment=assessment,
        )

    deleted_lock_path = _path_str_no_follow(admitted_lock_path)
    admitted_lock_path.unlink()
    _fsync_parent_best_effort(admitted_lock_path.parent)
    return _recovery_result(
        LOCK_SLICE_RECOVERY_RECOVERED,
        STATE_STARTUP_LOCK_SLICE_RECOVERY_RECOVERED,
        "stale admitted control-owned lock file was deleted",
        cleanup_performed=True,
        assessment=assessment,
        deleted_lock_path=deleted_lock_path,
    )
