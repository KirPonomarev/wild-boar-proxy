# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from wild_boar_proxy import state_store


STATE_MIGRATION_FAILED = "STATE_MIGRATION_FAILED"
STATE_MIGRATION_DOWNGRADE_BLOCKED = "STATE_MIGRATION_DOWNGRADE_BLOCKED"
STATE_MIGRATION_STEP_MISSING = "STATE_MIGRATION_STEP_MISSING"


@dataclass(frozen=True)
class MigrationStep:
    from_version: int
    to_version: int
    migrate: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MigrationResult:
    committed: bool
    from_schema_version: int
    to_schema_version: int
    backup_path: str
    changed_files: tuple[str, ...]


class StateMigrationError(Exception):
    def __init__(self, message: str, *, machine_error_code: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def _schema_version(payload: dict[str, Any], *, legacy_bootstrap: bool) -> int:
    if "schema_version" not in payload:
        if legacy_bootstrap:
            return 1
        raise state_store.StateStoreError(
            "State payload is missing schema_version.",
            machine_error_code=state_store.STATE_SCHEMA_MISSING,
        )
    version = payload["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise state_store.StateStoreError(
            "State payload schema_version is unsupported.",
            machine_error_code=state_store.STATE_SCHEMA_UNSUPPORTED,
        )
    return version


def _steps_by_version(migrations: tuple[MigrationStep, ...]) -> dict[int, MigrationStep]:
    steps: dict[int, MigrationStep] = {}
    for step in migrations:
        if step.to_version != step.from_version + 1:
            raise StateMigrationError(
                "State migration steps must be sequential.",
                machine_error_code=STATE_MIGRATION_STEP_MISSING,
            )
        if step.from_version in steps:
            raise StateMigrationError(
                "Duplicate state migration step.",
                machine_error_code=STATE_MIGRATION_STEP_MISSING,
            )
        steps[step.from_version] = step
    return steps


def _backup_path(path: Path, backup_dir: Path, from_version: int, target_version: int) -> Path:
    return backup_dir / f"{path.name}.v{from_version}-to-v{target_version}.backup"


def migrate_json_file(
    path: Path,
    *,
    target_schema_version: int,
    migrations: tuple[MigrationStep, ...],
    backup_dir: Path,
    legacy_bootstrap: bool = False,
) -> MigrationResult:
    target = Path(path)
    raw = target.read_bytes()
    try:
        original_text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise state_store.StateStoreError(
            f"State file is corrupt JSON: {target}",
            machine_error_code=state_store.STATE_CORRUPT,
        ) from exc

    payload = state_store.read_json(target)
    from_version = _schema_version(payload, legacy_bootstrap=legacy_bootstrap)
    if from_version > target_schema_version:
        raise StateMigrationError(
            "State migration downgrade is blocked.",
            machine_error_code=STATE_MIGRATION_DOWNGRADE_BLOCKED,
        )
    if from_version == target_schema_version:
        backup = _backup_path(target, Path(backup_dir), from_version, target_schema_version)
        return MigrationResult(
            committed=False,
            from_schema_version=from_version,
            to_schema_version=target_schema_version,
            backup_path=str(backup),
            changed_files=(),
        )

    steps = _steps_by_version(tuple(migrations))
    migrated = dict(payload)
    current_version = from_version
    while current_version < target_schema_version:
        step = steps.get(current_version)
        if step is None:
            raise StateMigrationError(
                "State migration step is missing.",
                machine_error_code=STATE_MIGRATION_STEP_MISSING,
            )
        try:
            migrated = step.migrate(dict(migrated))
        except Exception as exc:  # noqa: BLE001
            raise StateMigrationError(
                "State migration failed.",
                machine_error_code=STATE_MIGRATION_FAILED,
            ) from exc
        next_version = migrated.get("schema_version")
        if next_version != step.to_version:
            raise StateMigrationError(
                "State migration step did not produce the expected schema_version.",
                machine_error_code=STATE_MIGRATION_FAILED,
            )
        current_version = step.to_version

    backup = _backup_path(target, Path(backup_dir), from_version, target_schema_version)
    state_store.write_text(backup, original_text)
    write_result = state_store.write_json(
        target,
        migrated,
        expected_schema_version=target_schema_version,
    )
    return MigrationResult(
        committed=True,
        from_schema_version=from_version,
        to_schema_version=target_schema_version,
        backup_path=str(backup),
        changed_files=(str(backup), *write_result.changed_files),
    )
