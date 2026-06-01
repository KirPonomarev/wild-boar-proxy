# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class StartupLockSliceAssessment:
    lock_slice_outcome: str
    machine_error_code: str
    reason: str
    owner_classification: state_lock.LockOwnerClassification | None


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
