# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from wild_boar_proxy import (
    state_startup_lock,
    state_startup_recovery,
    state_startup_schema,
    state_startup_truth,
)


STARTUP_CONTRACT_CLEAN = "startup_contract_clean"
STARTUP_CONTRACT_AUTO_RECOVERED = "startup_contract_auto_recovered"
STARTUP_CONTRACT_BLOCKED = "startup_contract_blocked"

STATE_STARTUP_CONTRACT_CLEAN = "STATE_STARTUP_CONTRACT_CLEAN"
STATE_STARTUP_CONTRACT_AUTO_RECOVERED = "STATE_STARTUP_CONTRACT_AUTO_RECOVERED"
STATE_STARTUP_CONTRACT_BLOCKED = "STATE_STARTUP_CONTRACT_BLOCKED"

REASON_TEMP_RECOVERY_BLOCKED = "temp_recovery_blocked"
REASON_LOCK_RECOVERY_BLOCKED = "lock_slice_recovery_blocked"


@dataclass(frozen=True)
class StartupContractCoreResult:
    startup_contract_outcome: str
    machine_error_code: str
    cleanup_performed: bool
    blocking_reasons: tuple[str, ...]
    temp_recovery: state_startup_recovery.StartupTempRecoveryResult
    lock_recovery: state_startup_lock.StartupLockSliceRecoveryResult
    schema_assessment: state_startup_schema.StartupSchemaSliceAssessment
    truth_assessment: state_startup_truth.StartupTruthSliceAssessment


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _temp_blocking_reasons(
    temp_recovery: state_startup_recovery.StartupTempRecoveryResult,
) -> tuple[str, ...]:
    if temp_recovery.temp_recovery_outcome != state_startup_recovery.TEMP_RECOVERY_BLOCKED:
        return ()
    if temp_recovery.blocking_reasons:
        return temp_recovery.blocking_reasons
    return (REASON_TEMP_RECOVERY_BLOCKED,)


def _lock_blocking_reasons(
    lock_recovery: state_startup_lock.StartupLockSliceRecoveryResult,
) -> tuple[str, ...]:
    if (
        lock_recovery.lock_slice_recovery_outcome
        != state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED
    ):
        return ()
    assessment = lock_recovery.assessment
    if assessment is None:
        return (REASON_LOCK_RECOVERY_BLOCKED,)
    if assessment.lock_slice_outcome == state_startup_lock.LOCK_SLICE_INVALID:
        return (state_startup_lock.LOCK_SLICE_INVALID,)
    if assessment.lock_slice_outcome == state_startup_lock.LOCK_SLICE_SUSPICIOUS:
        return (state_startup_lock.LOCK_SLICE_SUSPICIOUS,)
    return (REASON_LOCK_RECOVERY_BLOCKED,)


def _schema_blocking_reasons(
    schema_assessment: state_startup_schema.StartupSchemaSliceAssessment,
) -> tuple[str, ...]:
    if schema_assessment.schema_slice_outcome == state_startup_schema.SCHEMA_SLICE_CURRENT:
        return ()
    return (schema_assessment.schema_slice_outcome,)


def _truth_blocking_reasons(
    truth_assessment: state_startup_truth.StartupTruthSliceAssessment,
) -> tuple[str, ...]:
    if truth_assessment.truth_slice_outcome == state_startup_truth.TRUTH_SLICE_CONSISTENT:
        return ()
    return (truth_assessment.truth_slice_outcome,)


def aggregate_startup_contract_core(
    *,
    temp_recovery: state_startup_recovery.StartupTempRecoveryResult,
    lock_recovery: state_startup_lock.StartupLockSliceRecoveryResult,
    schema_assessment: state_startup_schema.StartupSchemaSliceAssessment,
    truth_assessment: state_startup_truth.StartupTruthSliceAssessment,
) -> StartupContractCoreResult:
    cleanup_performed = temp_recovery.cleanup_performed or lock_recovery.cleanup_performed

    blocking_reasons: list[str] = []
    for reason in _temp_blocking_reasons(temp_recovery):
        _append_unique(blocking_reasons, reason)
    for reason in _lock_blocking_reasons(lock_recovery):
        _append_unique(blocking_reasons, reason)
    for reason in _truth_blocking_reasons(truth_assessment):
        _append_unique(blocking_reasons, reason)
    for reason in _schema_blocking_reasons(schema_assessment):
        _append_unique(blocking_reasons, reason)

    if blocking_reasons:
        return StartupContractCoreResult(
            startup_contract_outcome=STARTUP_CONTRACT_BLOCKED,
            machine_error_code=STATE_STARTUP_CONTRACT_BLOCKED,
            cleanup_performed=cleanup_performed,
            blocking_reasons=tuple(blocking_reasons),
            temp_recovery=temp_recovery,
            lock_recovery=lock_recovery,
            schema_assessment=schema_assessment,
            truth_assessment=truth_assessment,
        )

    if cleanup_performed:
        return StartupContractCoreResult(
            startup_contract_outcome=STARTUP_CONTRACT_AUTO_RECOVERED,
            machine_error_code=STATE_STARTUP_CONTRACT_AUTO_RECOVERED,
            cleanup_performed=True,
            blocking_reasons=(),
            temp_recovery=temp_recovery,
            lock_recovery=lock_recovery,
            schema_assessment=schema_assessment,
            truth_assessment=truth_assessment,
        )

    return StartupContractCoreResult(
        startup_contract_outcome=STARTUP_CONTRACT_CLEAN,
        machine_error_code=STATE_STARTUP_CONTRACT_CLEAN,
        cleanup_performed=False,
        blocking_reasons=(),
        temp_recovery=temp_recovery,
        lock_recovery=lock_recovery,
        schema_assessment=schema_assessment,
        truth_assessment=truth_assessment,
    )
