# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from wild_boar_proxy import state_store


TRUTH_SLICE_CONSISTENT = "truth_slice_consistent"
TRUTH_SLICE_PARTIAL = "truth_slice_partial"
TRUTH_SLICE_CONTRADICTED = "truth_slice_contradicted"
TRUTH_SLICE_BLOCKED = "truth_slice_blocked"

STATE_STARTUP_TRUTH_SLICE_CONSISTENT = "STATE_STARTUP_TRUTH_SLICE_CONSISTENT"
STATE_STARTUP_TRUTH_SLICE_PARTIAL = "STATE_STARTUP_TRUTH_SLICE_PARTIAL"
STATE_STARTUP_TRUTH_SLICE_CONTRADICTED = "STATE_STARTUP_TRUTH_SLICE_CONTRADICTED"
STATE_STARTUP_TRUTH_SLICE_BLOCKED = "STATE_STARTUP_TRUTH_SLICE_BLOCKED"

SELECTED_BACKEND_SNAPSHOT_SCHEMA_VERSION = 1
SELECTED_BACKEND_SNAPSHOT_KIND = "selected_backend_participation"
SELECTED_BACKEND_SNAPSHOT_CLAIM_SCOPE = "bounded_local_participation_evidence_only"
SELECTED_BACKEND_SNAPSHOT_ALLOWED_SOURCE_CLASSES = {
    "engine_observed",
    "runtime_observed",
    "supervisor_owner_observed",
    "external_owner_path_observed",
}


@dataclass(frozen=True)
class StartupRuntimeTruthPaths:
    registry_path: Path
    supervisor_state_path: Path
    runtime_effective_mode_path: Path


@dataclass(frozen=True)
class StartupTruthSliceAssessment:
    truth_slice_outcome: str
    machine_error_code: str
    reason: str
    registry_present: bool
    supervisor_state_present: bool
    effective_mode_artifact_present: bool
    selected_backend_snapshot_present: bool
    contradiction_fields: tuple[str, ...]


@dataclass(frozen=True)
class _SelectedBackendSnapshotValidation:
    present: bool
    blocked_reason: str | None
    contradiction_fields: tuple[str, ...]


def _assessment(
    truth_slice_outcome: str,
    machine_error_code: str,
    reason: str,
    *,
    registry_present: bool,
    supervisor_state_present: bool,
    effective_mode_artifact_present: bool,
    selected_backend_snapshot_present: bool,
    contradiction_fields: tuple[str, ...] = (),
) -> StartupTruthSliceAssessment:
    return StartupTruthSliceAssessment(
        truth_slice_outcome=truth_slice_outcome,
        machine_error_code=machine_error_code,
        reason=reason,
        registry_present=registry_present,
        supervisor_state_present=supervisor_state_present,
        effective_mode_artifact_present=effective_mode_artifact_present,
        selected_backend_snapshot_present=selected_backend_snapshot_present,
        contradiction_fields=contradiction_fields,
    )


def _absolute_path_no_follow(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _normalize_admitted_path(path: Path) -> Path | None:
    candidate = Path(path)
    if not candidate.is_absolute():
        return None
    return _absolute_path_no_follow(candidate)


def _validate_admitted_file_path(path: Path) -> str | None:
    if path.is_symlink():
        return "admitted runtime truth path must not be a symlink"
    if path.exists() and not path.is_file():
        return "admitted runtime truth path must be a regular file when present"
    return None


def _require_schema_version(payload: dict[str, Any], *, surface_name: str) -> int:
    if "schema_version" not in payload:
        raise state_store.StateStoreError(
            f"{surface_name} is missing schema_version.",
            machine_error_code=state_store.STATE_SCHEMA_MISSING,
        )
    version = payload["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise state_store.StateStoreError(
            f"{surface_name} schema_version is unsupported.",
            machine_error_code=state_store.STATE_SCHEMA_UNSUPPORTED,
        )
    return version


def _require_string_field(
    payload: dict[str, Any],
    field_name: str,
    *,
    surface_name: str,
    allow_empty: bool = False,
) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise state_store.StateStoreError(
            f"{surface_name} field {field_name} is missing or invalid.",
            machine_error_code=state_store.STATE_PAYLOAD_INVALID,
        )
    if not allow_empty and not value.strip():
        raise state_store.StateStoreError(
            f"{surface_name} field {field_name} is missing or invalid.",
            machine_error_code=state_store.STATE_PAYLOAD_INVALID,
        )
    return value.strip() if not allow_empty else value


def _read_required_json_surface(path: Path, *, surface_name: str) -> dict[str, Any]:
    payload = state_store.read_json(path)
    _require_schema_version(payload, surface_name=surface_name)
    return payload


def _normalize_selected_backend_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted(str(item) for item in value if isinstance(item, str) and item))


def _selected_backend_ids_digest(ids: tuple[str, ...]) -> str:
    encoded = json.dumps(ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_utc_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _validate_selected_backend_snapshot(
    state: dict[str, Any],
) -> _SelectedBackendSnapshotValidation:
    snapshot = state.get("selected_backend_snapshot")
    if snapshot is None:
        return _SelectedBackendSnapshotValidation(
            present=False,
            blocked_reason=None,
            contradiction_fields=(),
        )
    if not isinstance(snapshot, dict):
        return _SelectedBackendSnapshotValidation(
            present=True,
            blocked_reason="selected_backend_snapshot must be an object when materialized",
            contradiction_fields=(),
        )
    try:
        _require_schema_version(snapshot, surface_name="selected_backend_snapshot")
        if snapshot["schema_version"] != SELECTED_BACKEND_SNAPSHOT_SCHEMA_VERSION:
            raise state_store.StateStoreError(
                "selected_backend_snapshot schema_version is unsupported.",
                machine_error_code=state_store.STATE_SCHEMA_UNSUPPORTED,
            )
        if snapshot.get("snapshot_kind") != SELECTED_BACKEND_SNAPSHOT_KIND:
            raise state_store.StateStoreError(
                "selected_backend_snapshot snapshot_kind is invalid.",
                machine_error_code=state_store.STATE_PAYLOAD_INVALID,
            )
        source_class = _require_string_field(
            snapshot,
            "source_class",
            surface_name="selected_backend_snapshot",
        )
        if source_class not in SELECTED_BACKEND_SNAPSHOT_ALLOWED_SOURCE_CLASSES:
            raise state_store.StateStoreError(
                "selected_backend_snapshot source_class is invalid.",
                machine_error_code=state_store.STATE_PAYLOAD_INVALID,
            )
        _require_string_field(
            snapshot,
            "source_name",
            surface_name="selected_backend_snapshot",
        )
        _require_string_field(
            snapshot,
            "source_run_id",
            surface_name="selected_backend_snapshot",
        )
        _require_string_field(
            snapshot,
            "producer_version",
            surface_name="selected_backend_snapshot",
        )
        if _parse_utc_datetime(snapshot.get("observed_at_utc")) is None:
            raise state_store.StateStoreError(
                "selected_backend_snapshot observed_at_utc is invalid.",
                machine_error_code=state_store.STATE_PAYLOAD_INVALID,
            )
        ids = _normalize_selected_backend_ids(snapshot.get("selected_backend_ids"))
        if not ids:
            raise state_store.StateStoreError(
                "selected_backend_snapshot selected_backend_ids are invalid.",
                machine_error_code=state_store.STATE_PAYLOAD_INVALID,
            )
        if snapshot.get("claim_scope") != SELECTED_BACKEND_SNAPSHOT_CLAIM_SCOPE:
            raise state_store.StateStoreError(
                "selected_backend_snapshot claim_scope is invalid.",
                machine_error_code=state_store.STATE_PAYLOAD_INVALID,
            )
    except state_store.StateStoreError as exc:
        return _SelectedBackendSnapshotValidation(
            present=True,
            blocked_reason=str(exc),
            contradiction_fields=(),
        )

    digest = snapshot.get("selected_backends_digest")
    if not isinstance(digest, str) or not digest.strip():
        return _SelectedBackendSnapshotValidation(
            present=True,
            blocked_reason="selected_backend_snapshot selected_backends_digest is invalid.",
            contradiction_fields=(),
        )
    expected_digest = _selected_backend_ids_digest(ids)
    if digest.strip() != expected_digest:
        return _SelectedBackendSnapshotValidation(
            present=True,
            blocked_reason=None,
            contradiction_fields=("selected_backend_snapshot_digest",),
        )
    return _SelectedBackendSnapshotValidation(
        present=True,
        blocked_reason=None,
        contradiction_fields=(),
    )


def assess_startup_truth_slice(
    paths: StartupRuntimeTruthPaths,
) -> StartupTruthSliceAssessment:
    normalized_registry_path = _normalize_admitted_path(paths.registry_path)
    if normalized_registry_path is None:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            "registry path must be absolute",
            registry_present=False,
            supervisor_state_present=False,
            effective_mode_artifact_present=False,
            selected_backend_snapshot_present=False,
        )
    normalized_state_path = _normalize_admitted_path(paths.supervisor_state_path)
    if normalized_state_path is None:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            "supervisor state path must be absolute",
            registry_present=normalized_registry_path.exists(),
            supervisor_state_present=False,
            effective_mode_artifact_present=False,
            selected_backend_snapshot_present=False,
        )
    normalized_effective_mode_path = _normalize_admitted_path(paths.runtime_effective_mode_path)
    if normalized_effective_mode_path is None:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            "runtime effective mode path must be absolute",
            registry_present=normalized_registry_path.exists(),
            supervisor_state_present=normalized_state_path.exists(),
            effective_mode_artifact_present=False,
            selected_backend_snapshot_present=False,
        )

    for path in (
        normalized_registry_path,
        normalized_state_path,
        normalized_effective_mode_path,
    ):
        path_error = _validate_admitted_file_path(path)
        if path_error:
            return _assessment(
                TRUTH_SLICE_BLOCKED,
                STATE_STARTUP_TRUTH_SLICE_BLOCKED,
                path_error,
                registry_present=normalized_registry_path.exists(),
                supervisor_state_present=normalized_state_path.exists(),
                effective_mode_artifact_present=normalized_effective_mode_path.exists(),
                selected_backend_snapshot_present=False,
            )

    registry_present = normalized_registry_path.exists()
    if not registry_present:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            "backend-registry.json is missing",
            registry_present=False,
            supervisor_state_present=normalized_state_path.exists(),
            effective_mode_artifact_present=normalized_effective_mode_path.exists(),
            selected_backend_snapshot_present=False,
        )

    supervisor_state_present = normalized_state_path.exists()
    if not supervisor_state_present:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            "supervisor-state.json is missing",
            registry_present=True,
            supervisor_state_present=False,
            effective_mode_artifact_present=normalized_effective_mode_path.exists(),
            selected_backend_snapshot_present=False,
        )

    try:
        registry = _read_required_json_surface(
            normalized_registry_path,
            surface_name="backend-registry.json",
        )
        state = _read_required_json_surface(
            normalized_state_path,
            surface_name="supervisor-state.json",
        )
        registry_stable_default_backend_id = _require_string_field(
            registry,
            "stable_default_backend_id",
            surface_name="backend-registry.json",
            allow_empty=True,
        )
        state_stable_default_backend_id = _require_string_field(
            state,
            "stable_default_backend_id",
            surface_name="supervisor-state.json",
            allow_empty=True,
        )
        state_effective_mode = _require_string_field(
            state,
            "effective_mode",
            surface_name="supervisor-state.json",
        )
    except state_store.StateStoreError as exc:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            str(exc),
            registry_present=True,
            supervisor_state_present=True,
            effective_mode_artifact_present=normalized_effective_mode_path.exists(),
            selected_backend_snapshot_present=isinstance(
                state.get("selected_backend_snapshot") if "state" in locals() else None,
                dict,
            ),
        )

    snapshot_validation = _validate_selected_backend_snapshot(state)
    if snapshot_validation.blocked_reason:
        return _assessment(
            TRUTH_SLICE_BLOCKED,
            STATE_STARTUP_TRUTH_SLICE_BLOCKED,
            snapshot_validation.blocked_reason,
            registry_present=True,
            supervisor_state_present=True,
            effective_mode_artifact_present=normalized_effective_mode_path.exists(),
            selected_backend_snapshot_present=snapshot_validation.present,
        )

    contradiction_fields: list[str] = list(snapshot_validation.contradiction_fields)
    if registry_stable_default_backend_id != state_stable_default_backend_id:
        contradiction_fields.append("stable_default_backend_id")

    effective_mode_artifact_present = normalized_effective_mode_path.exists()
    if effective_mode_artifact_present:
        try:
            effective_mode_artifact = normalized_effective_mode_path.read_text(
                encoding="utf-8"
            ).strip()
        except UnicodeDecodeError:
            return _assessment(
                TRUTH_SLICE_BLOCKED,
                STATE_STARTUP_TRUTH_SLICE_BLOCKED,
                "runtime-effective-mode.txt is not valid UTF-8 text",
                registry_present=True,
                supervisor_state_present=True,
                effective_mode_artifact_present=True,
                selected_backend_snapshot_present=snapshot_validation.present,
            )
        if not effective_mode_artifact:
            return _assessment(
                TRUTH_SLICE_BLOCKED,
                STATE_STARTUP_TRUTH_SLICE_BLOCKED,
                "runtime-effective-mode.txt is empty or invalid",
                registry_present=True,
                supervisor_state_present=True,
                effective_mode_artifact_present=True,
                selected_backend_snapshot_present=snapshot_validation.present,
            )
        if effective_mode_artifact != state_effective_mode:
            contradiction_fields.append("effective_mode")

    contradiction_tuple = tuple(dict.fromkeys(contradiction_fields))
    if contradiction_tuple:
        return _assessment(
            TRUTH_SLICE_CONTRADICTED,
            STATE_STARTUP_TRUTH_SLICE_CONTRADICTED,
            "startup runtime truth surfaces are contradicted",
            registry_present=True,
            supervisor_state_present=True,
            effective_mode_artifact_present=effective_mode_artifact_present,
            selected_backend_snapshot_present=snapshot_validation.present,
            contradiction_fields=contradiction_tuple,
        )

    if not effective_mode_artifact_present:
        return _assessment(
            TRUTH_SLICE_PARTIAL,
            STATE_STARTUP_TRUTH_SLICE_PARTIAL,
            "runtime-effective-mode.txt is missing",
            registry_present=True,
            supervisor_state_present=True,
            effective_mode_artifact_present=False,
            selected_backend_snapshot_present=snapshot_validation.present,
        )

    return _assessment(
        TRUTH_SLICE_CONSISTENT,
        STATE_STARTUP_TRUTH_SLICE_CONSISTENT,
        "startup runtime truth surfaces are consistent",
        registry_present=True,
        supervisor_state_present=True,
        effective_mode_artifact_present=True,
        selected_backend_snapshot_present=snapshot_validation.present,
    )
