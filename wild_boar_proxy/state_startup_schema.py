# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from wild_boar_proxy import state_migration, state_store


SCHEMA_SLICE_ABSENT = "schema_slice_absent"
SCHEMA_SLICE_CURRENT = "schema_slice_current"
SCHEMA_SLICE_MIGRATABLE = "schema_slice_migratable"
SCHEMA_SLICE_BLOCKED = "schema_slice_blocked"

STATE_STARTUP_SCHEMA_SLICE_ABSENT = "STATE_STARTUP_SCHEMA_SLICE_ABSENT"
STATE_STARTUP_SCHEMA_SLICE_CURRENT = "STATE_STARTUP_SCHEMA_SLICE_CURRENT"
STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE = "STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE"
STATE_STARTUP_SCHEMA_SLICE_BLOCKED = "STATE_STARTUP_SCHEMA_SLICE_BLOCKED"


@dataclass(frozen=True)
class StartupSchemaSliceAssessment:
    schema_slice_outcome: str
    machine_error_code: str
    reason: str
    from_schema_version: int | None
    target_schema_version: int
    migration_path_available: bool
    legacy_bootstrap_required: bool


def _assessment(
    schema_slice_outcome: str,
    machine_error_code: str,
    reason: str,
    *,
    from_schema_version: int | None,
    target_schema_version: int,
    migration_path_available: bool,
    legacy_bootstrap_required: bool,
) -> StartupSchemaSliceAssessment:
    return StartupSchemaSliceAssessment(
        schema_slice_outcome=schema_slice_outcome,
        machine_error_code=machine_error_code,
        reason=reason,
        from_schema_version=from_schema_version,
        target_schema_version=target_schema_version,
        migration_path_available=migration_path_available,
        legacy_bootstrap_required=legacy_bootstrap_required,
    )


def _absolute_path_no_follow(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _normalize_admitted_state_path(path: Path) -> Path | None:
    candidate = Path(path)
    if not candidate.is_absolute():
        return None
    return _absolute_path_no_follow(candidate)


def _has_complete_migration_path(
    from_schema_version: int,
    *,
    target_schema_version: int,
    migrations: tuple[state_migration.MigrationStep, ...],
) -> bool:
    steps = state_migration._steps_by_version(tuple(migrations))
    current_version = from_schema_version
    while current_version < target_schema_version:
        step = steps.get(current_version)
        if step is None:
            raise state_migration.StateMigrationError(
                "State migration step is missing.",
                machine_error_code=state_migration.STATE_MIGRATION_STEP_MISSING,
            )
        current_version = step.to_version
    return True


def assess_startup_schema_slice(
    admitted_control_owned_state_path: Path,
    *,
    target_schema_version: int,
    migrations: tuple[state_migration.MigrationStep, ...],
    legacy_bootstrap: bool = False,
) -> StartupSchemaSliceAssessment:
    admitted_path = _normalize_admitted_state_path(admitted_control_owned_state_path)
    if admitted_path is None:
        return _assessment(
            SCHEMA_SLICE_BLOCKED,
            STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
            "admitted control-owned state path must be absolute",
            from_schema_version=None,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=False,
        )

    if admitted_path.is_symlink():
        return _assessment(
            SCHEMA_SLICE_BLOCKED,
            STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
            "admitted control-owned state path must not be a symlink",
            from_schema_version=None,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=False,
        )

    if admitted_path.exists() and not admitted_path.is_file():
        return _assessment(
            SCHEMA_SLICE_BLOCKED,
            STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
            "admitted control-owned state path must be a regular file when present",
            from_schema_version=None,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=False,
        )

    if not admitted_path.exists():
        return _assessment(
            SCHEMA_SLICE_ABSENT,
            STATE_STARTUP_SCHEMA_SLICE_ABSENT,
            "admitted control-owned state file does not exist",
            from_schema_version=None,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=False,
        )

    try:
        payload = state_store.read_json(admitted_path)
        legacy_bootstrap_required = "schema_version" not in payload and legacy_bootstrap
        from_schema_version = state_migration._schema_version(
            payload,
            legacy_bootstrap=legacy_bootstrap,
        )
    except (state_store.StateStoreError, state_migration.StateMigrationError) as exc:
        return _assessment(
            SCHEMA_SLICE_BLOCKED,
            STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
            str(exc),
            from_schema_version=None,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=False,
        )

    if from_schema_version > target_schema_version:
        return _assessment(
            SCHEMA_SLICE_BLOCKED,
            STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
            "state schema version is newer than the admitted target schema version",
            from_schema_version=from_schema_version,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=legacy_bootstrap_required,
        )

    if legacy_bootstrap_required and from_schema_version == target_schema_version:
        return _assessment(
            SCHEMA_SLICE_MIGRATABLE,
            STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE,
            "legacy bootstrap is required before the schema can be published as current",
            from_schema_version=from_schema_version,
            target_schema_version=target_schema_version,
            migration_path_available=True,
            legacy_bootstrap_required=True,
        )

    if from_schema_version == target_schema_version:
        return _assessment(
            SCHEMA_SLICE_CURRENT,
            STATE_STARTUP_SCHEMA_SLICE_CURRENT,
            "state schema version already matches the admitted target schema version",
            from_schema_version=from_schema_version,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=legacy_bootstrap_required,
        )

    try:
        _has_complete_migration_path(
            from_schema_version,
            target_schema_version=target_schema_version,
            migrations=migrations,
        )
    except state_migration.StateMigrationError as exc:
        return _assessment(
            SCHEMA_SLICE_BLOCKED,
            STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
            str(exc),
            from_schema_version=from_schema_version,
            target_schema_version=target_schema_version,
            migration_path_available=False,
            legacy_bootstrap_required=legacy_bootstrap_required,
        )

    return _assessment(
        SCHEMA_SLICE_MIGRATABLE,
        STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE,
        "state schema migration path is available",
        from_schema_version=from_schema_version,
        target_schema_version=target_schema_version,
        migration_path_available=True,
        legacy_bootstrap_required=legacy_bootstrap_required,
    )
