# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wild_boar_proxy import state_temp_prefix, state_transaction


TEMP_RECOVERY_CLEAN = "temp_recovery_clean"
TEMP_RECOVERY_RECOVERED = "temp_recovery_recovered"
TEMP_RECOVERY_BLOCKED = "temp_recovery_blocked"

STATE_STARTUP_TEMP_CLEAN = "STATE_STARTUP_TEMP_CLEAN"
STATE_STARTUP_TEMP_RECOVERED = "STATE_STARTUP_TEMP_RECOVERED"
STATE_STARTUP_TEMP_BLOCKED = "STATE_STARTUP_TEMP_BLOCKED"

REASON_TRANSACTION_INCOMPLETE = "transaction_incomplete"
REASON_TRANSACTION_RECOVERABLE = "transaction_recoverable"
REASON_TRANSACTION_BLOCKED = "transaction_blocked"
REASON_TRANSACTION_INVALID_METADATA = "transaction_invalid_metadata"
REASON_TRANSACTION_CLEANUP_SKIPPED = "transaction_cleanup_skipped"
REASON_PREFIX_INVALID_ROOT = "prefix_invalid_root"
REASON_PREFIX_BLOCKED_PATH = "prefix_blocked_path"
REASON_PREFIX_CLEANUP_SKIPPED = "prefix_cleanup_skipped"


@dataclass(frozen=True)
class StartupTempRecoveryResult:
    temp_recovery_outcome: str
    machine_error_code: str
    cleanup_performed: bool
    blocking_reasons: tuple[str, ...]
    transaction_cleanup: state_transaction.TransactionTempCleanupResult
    prefix_cleanup: state_temp_prefix.PrefixedTempCleanupResult


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _transaction_cleanup_from_inspection(
    inspection: state_transaction.TransactionTempInspection,
) -> state_transaction.TransactionTempCleanupResult:
    blocked = bool(
        inspection.incomplete_transaction_ids
        or inspection.recoverable_transaction_ids
        or inspection.blocked_transaction_ids
        or inspection.invalid_metadata_paths
    )
    return state_transaction.TransactionTempCleanupResult(
        deleted_artifact_paths=(),
        skipped_artifact_paths=inspection.stale_artifact_paths if blocked else (),
        stale_artifact_paths=inspection.stale_artifact_paths,
        incomplete_transaction_ids=inspection.incomplete_transaction_ids,
        recoverable_transaction_ids=inspection.recoverable_transaction_ids,
        blocked_transaction_ids=inspection.blocked_transaction_ids,
        invalid_metadata_paths=inspection.invalid_metadata_paths,
    )


def _prefix_cleanup_from_inspection(
    inspection: state_temp_prefix.PrefixedTempInspection,
) -> state_temp_prefix.PrefixedTempCleanupResult:
    blocked = bool(inspection.invalid_roots or inspection.blocked_paths)
    return state_temp_prefix.PrefixedTempCleanupResult(
        deleted_paths=(),
        skipped_paths=inspection.stale_paths if blocked else (),
        stale_paths=inspection.stale_paths,
        fresh_paths=inspection.fresh_paths,
        blocked_paths=inspection.blocked_paths,
        invalid_roots=inspection.invalid_roots,
    )


def _blocking_reasons_from_inspections(
    transaction_inspection: state_transaction.TransactionTempInspection,
    prefix_inspection: state_temp_prefix.PrefixedTempInspection,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if transaction_inspection.incomplete_transaction_ids:
        _append_unique(reasons, REASON_TRANSACTION_INCOMPLETE)
    if transaction_inspection.recoverable_transaction_ids:
        _append_unique(reasons, REASON_TRANSACTION_RECOVERABLE)
    if transaction_inspection.blocked_transaction_ids:
        _append_unique(reasons, REASON_TRANSACTION_BLOCKED)
    if transaction_inspection.invalid_metadata_paths:
        _append_unique(reasons, REASON_TRANSACTION_INVALID_METADATA)
    if prefix_inspection.invalid_roots:
        _append_unique(reasons, REASON_PREFIX_INVALID_ROOT)
    if prefix_inspection.blocked_paths:
        _append_unique(reasons, REASON_PREFIX_BLOCKED_PATH)
    return tuple(reasons)


def _blocking_reasons_from_cleanups(
    transaction_cleanup: state_transaction.TransactionTempCleanupResult,
    prefix_cleanup: state_temp_prefix.PrefixedTempCleanupResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if transaction_cleanup.incomplete_transaction_ids:
        _append_unique(reasons, REASON_TRANSACTION_INCOMPLETE)
    if transaction_cleanup.recoverable_transaction_ids:
        _append_unique(reasons, REASON_TRANSACTION_RECOVERABLE)
    if transaction_cleanup.blocked_transaction_ids:
        _append_unique(reasons, REASON_TRANSACTION_BLOCKED)
    if transaction_cleanup.invalid_metadata_paths:
        _append_unique(reasons, REASON_TRANSACTION_INVALID_METADATA)
    if transaction_cleanup.skipped_artifact_paths:
        _append_unique(reasons, REASON_TRANSACTION_CLEANUP_SKIPPED)
    if prefix_cleanup.invalid_roots:
        _append_unique(reasons, REASON_PREFIX_INVALID_ROOT)
    if prefix_cleanup.blocked_paths:
        _append_unique(reasons, REASON_PREFIX_BLOCKED_PATH)
    if prefix_cleanup.skipped_paths:
        _append_unique(reasons, REASON_PREFIX_CLEANUP_SKIPPED)
    return tuple(reasons)


def run_startup_temp_recovery(
    transaction_root: Path,
    admitted_control_owned_parent_roots: tuple[Path, ...],
    *,
    now: datetime | None = None,
    transaction_stale_ttl_seconds: int = state_transaction.TRANSACTION_ARTIFACT_STALE_TTL_SECONDS,
    prefix_stale_ttl_seconds: int = state_temp_prefix.DEFAULT_STALE_TTL_SECONDS,
) -> StartupTempRecoveryResult:
    transaction_inspection = state_transaction.inspect_transaction_temp_artifacts(
        transaction_root,
        now=now,
        stale_ttl_seconds=transaction_stale_ttl_seconds,
    )
    prefix_inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
        admitted_control_owned_parent_roots,
        now=now,
        stale_ttl_seconds=prefix_stale_ttl_seconds,
    )
    preflight_reasons = _blocking_reasons_from_inspections(
        transaction_inspection,
        prefix_inspection,
    )
    if preflight_reasons:
        return StartupTempRecoveryResult(
            temp_recovery_outcome=TEMP_RECOVERY_BLOCKED,
            machine_error_code=STATE_STARTUP_TEMP_BLOCKED,
            cleanup_performed=False,
            blocking_reasons=preflight_reasons,
            transaction_cleanup=_transaction_cleanup_from_inspection(transaction_inspection),
            prefix_cleanup=_prefix_cleanup_from_inspection(prefix_inspection),
        )

    transaction_cleanup = state_transaction.cleanup_transaction_store_artifacts(
        transaction_root,
        now=now,
        stale_ttl_seconds=transaction_stale_ttl_seconds,
    )
    prefix_cleanup = state_temp_prefix.cleanup_prefixed_temp_artifacts(
        admitted_control_owned_parent_roots,
        now=now,
        stale_ttl_seconds=prefix_stale_ttl_seconds,
    )
    cleanup_performed = (
        transaction_cleanup.cleanup_performed or prefix_cleanup.cleanup_performed
    )
    blocking_reasons = _blocking_reasons_from_cleanups(
        transaction_cleanup,
        prefix_cleanup,
    )
    if blocking_reasons:
        return StartupTempRecoveryResult(
            temp_recovery_outcome=TEMP_RECOVERY_BLOCKED,
            machine_error_code=STATE_STARTUP_TEMP_BLOCKED,
            cleanup_performed=cleanup_performed,
            blocking_reasons=blocking_reasons,
            transaction_cleanup=transaction_cleanup,
            prefix_cleanup=prefix_cleanup,
        )
    if cleanup_performed:
        return StartupTempRecoveryResult(
            temp_recovery_outcome=TEMP_RECOVERY_RECOVERED,
            machine_error_code=STATE_STARTUP_TEMP_RECOVERED,
            cleanup_performed=True,
            blocking_reasons=(),
            transaction_cleanup=transaction_cleanup,
            prefix_cleanup=prefix_cleanup,
        )
    return StartupTempRecoveryResult(
        temp_recovery_outcome=TEMP_RECOVERY_CLEAN,
        machine_error_code=STATE_STARTUP_TEMP_CLEAN,
        cleanup_performed=False,
        blocking_reasons=(),
        transaction_cleanup=transaction_cleanup,
        prefix_cleanup=prefix_cleanup,
    )
