# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Canonical multi-actor registry (schema v2) with legacy v1 projection.

B02 of the WBP Multi-Actor Master Plan: actor definitions, slot bindings,
role assignments, registry revisions, legacy ``agent_id`` projection,
migration with backup/rollback, and stale-route guards.

The canonical entity separation is non-negotiable:

    actor definition != slot binding != role assignment != permission grant
    != transport session

Credentials are never stored: ``credential_ref`` is a broker-owned reference
only, and secret-shaped fields are structurally rejected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import state_migration, state_store
from .custom_agent_bindings import (
    AGENT_BINDINGS_FILENAME,
    API_ROUTE_LANE,
    PRIMARY_CHATGPT_LANE,
    FORBIDDEN_STALE_ROUTE_IDS,
    agent_bindings_state_path,
    utc_now,
)

ACTOR_REGISTRY_SCHEMA_VERSION = 2
ACTOR_REGISTRY_PACKET_KIND = "codex_custom_actor_registry_state"
# The persisted state file keeps the legacy packet_kind for wire
# compatibility; both names identify the same canonical registry document.
ACCEPTED_STATE_PACKET_KINDS = {
    ACTOR_REGISTRY_PACKET_KIND,
    "codex_custom_agent_bindings_state",
}
ACTOR_REGISTRY_LIST_KIND = "codex_custom_actor_registry_list"
ACTOR_REGISTRY_MIGRATION_KIND = "codex_custom_actor_registry_migration"
MIGRATION_BACKUP_SUBDIR = "actor-registry-backups"

NATIVE_PRIMARY_ADAPTER = "native_primary"
API_ADAPTER = "api"
CLI_ONE_SHOT_ADAPTER = "cli_one_shot"
CLI_ACP_ADAPTER = "cli_acp"
ALLOWED_TRANSPORT_ADAPTERS = {
    NATIVE_PRIMARY_ADAPTER,
    API_ADAPTER,
    CLI_ONE_SHOT_ADAPTER,
    CLI_ACP_ADAPTER,
}

PERMISSION_NONE = "none"
PERMISSION_CONTEXT_ONLY = "context_only"
PERMISSION_REPO_READ = "repo_read"
PERMISSION_REPO_WRITE = "repo_write"
PERMISSION_BROWSER_READ = "browser_read"
PERMISSION_NETWORK_READ = "network_read"
ALLOWED_PERMISSION_CEILINGS = {
    PERMISSION_NONE,
    PERMISSION_CONTEXT_ONLY,
    PERMISSION_REPO_READ,
    PERMISSION_REPO_WRITE,
    PERMISSION_BROWSER_READ,
    PERMISSION_NETWORK_READ,
}

CONTEXT_POLICY_CONTINUE = "continue"
CONTEXT_POLICY_FRESH = "fresh"
CONTEXT_POLICY_FORK = "fork"
ALLOWED_CONTEXT_POLICIES = {CONTEXT_POLICY_CONTINUE, CONTEXT_POLICY_FRESH, CONTEXT_POLICY_FORK}

PRIMARY_SLOT_ID = "primary"
EXTERNAL_SLOT_PREFIX = "agent_"

FORBIDDEN_REGISTRY_FIELDS = {
    "auth",
    "auth_ref",
    "auth_file",
    "backend",
    "backend_id",
    "base_url",
    "credential_value",
    "endpoint",
    "endpoint_path",
    "key",
    "password",
    "provider_base_url",
    "raw_backend",
    "secret",
    "secret_ref",
    "token",
}

# Additive legacy carriers preserved from schema v1 (documented in
# STATE_SCHEMA.md): model_id on primary actors, route_id + allowed_actions on
# slot bindings. They keep the runtime-context wire projection lossless.
ACTOR_LEGACY_CARRIER_FIELDS = {"model_id"}
BINDING_LEGACY_CARRIER_FIELDS = {"route_id", "allowed_actions"}

ALLOWED_ACTOR_FIELDS = {
    "actor_id",
    "display_name",
    "transport_adapter_id",
    "provider_id",
    "model_policy",
    "credential_ref",
    "capability_profile_id",
    "permission_ceiling",
    "enabled",
    "revision",
    *ACTOR_LEGACY_CARRIER_FIELDS,
}
ALLOWED_SLOT_BINDING_FIELDS = {
    "slot_id",
    "binding_id",
    "binding_revision",
    "actor_id",
    "aliases",
    "enabled",
    "created_at",
    "updated_at",
    *BINDING_LEGACY_CARRIER_FIELDS,
}
ALLOWED_ROLE_ASSIGNMENT_FIELDS = {
    "assignment_id",
    "assignment_revision",
    "slot_id",
    "role_label",
    "role_instruction",
    "assignment_context_policy",
    "scope",
    "expires_at",
}
ALLOWED_DOCUMENT_FIELDS = {
    "schema_version",
    "packet_kind",
    "updated_at_utc",
    "registry_revision",
    "actors",
    "slot_bindings",
    "role_assignments",
    "agent_bindings",
    "raw_backend_details_exposed",
    "secret_value_exposed",
}


def _packet(
    *,
    status: str,
    machine_error_code: str,
    human_message: str,
    changed_files: list[str],
    next_action: str,
    exit_code: int = 1,
    liveness: str = "degraded",
    severity: str = "recoverable",
    operator_action: str = "user_action",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "exit_code": exit_code,
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": changed_files,
        "next_action": next_action,
        "liveness": liveness,
        "severity": severity,
        "operator_action": operator_action,
        **(extra or {}),
    }


def _is_mapping(value: object) -> bool:
    return isinstance(value, Mapping)


def _safe_text(value: object, *, max_length: int = 96) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split()).strip()[:max_length]


def _safe_id(value: object) -> str:
    text = _safe_text(value, max_length=64).lower()
    return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_"})


def _safe_list(raw: object, *, max_items: int = 24, max_length: int = 96) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw[:max_items]:
        text = _safe_text(item, max_length=max_length)
        if text:
            values.append(text)
    return values


def _forbidden_fields_present(raw: Mapping[str, Any]) -> list[str]:
    return sorted(set(raw) & FORBIDDEN_REGISTRY_FIELDS)


def _adapter_for_lane(lane: str) -> str:
    return NATIVE_PRIMARY_ADAPTER if lane == PRIMARY_CHATGPT_LANE else API_ADAPTER


def build_actor_registry_document(
    raw_bindings: object,
    *,
    route_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a canonical schema-v2 registry document from schema-v1 bindings.

    ``raw_bindings`` is the legacy ``agent_bindings`` list (v1 shape). The
    conversion is deterministic and lossless via legacy carrier fields; the
    v1-shaped projection is stored in ``agent_bindings`` for wire
    compatibility.
    """
    route_records = route_records or []
    providers_by_route = {
        str(route.get("route_id") or ""): str(route.get("provider") or "")
        for route in route_records
        if _is_mapping(route) and str(route.get("route_id") or "")
    }
    bindings = [b for b in raw_bindings if _is_mapping(b)] if isinstance(raw_bindings, list) else []
    now = utc_now()

    actors: list[dict[str, Any]] = []
    slot_bindings: list[dict[str, Any]] = []
    role_assignments: list[dict[str, Any]] = []
    legacy_projection: list[dict[str, Any]] = []

    external_slot_index = 1
    for raw in bindings:
        agent_id = _safe_id(raw.get("agent_id"))
        if not agent_id:
            continue
        lane = _safe_text(raw.get("lane"), max_length=32)
        role = _safe_text(raw.get("role"), max_length=64)
        aliases = _safe_list(raw.get("aliases"))
        enabled = raw.get("enabled") is not False
        allowed_actions = _safe_list(raw.get("allowed_actions"), max_length=64)
        display_name = _safe_text(raw.get("display_name"), max_length=80)

        if lane == PRIMARY_CHATGPT_LANE:
            slot_id = PRIMARY_SLOT_ID
            adapter = NATIVE_PRIMARY_ADAPTER
            provider_id = "chatgpt"
            model_id = _safe_text(raw.get("model_id"), max_length=80)
            route_id = ""
            model_policy = {"model_id": model_id}
        elif lane == API_ROUTE_LANE:
            slot_id = f"{EXTERNAL_SLOT_PREFIX}{external_slot_index}"
            external_slot_index += 1
            adapter = API_ADAPTER
            route_id = _safe_text(raw.get("route_id"), max_length=80)
            provider_id = providers_by_route.get(route_id) or "api"
            model_id = ""
            model_policy = {}
        else:
            continue

        actor_id = agent_id
        actors.append({
            "actor_id": actor_id,
            "display_name": display_name,
            "transport_adapter_id": adapter,
            "provider_id": provider_id,
            "model_policy": model_policy,
            "credential_ref": None,
            "capability_profile_id": role or "coding_agent",
            "permission_ceiling": PERMISSION_CONTEXT_ONLY,
            "enabled": enabled,
            "revision": 1,
            "model_id": model_id,
        })
        binding: dict[str, Any] = {
            "slot_id": slot_id,
            "binding_id": f"binding-{slot_id}",
            "binding_revision": 1,
            "actor_id": actor_id,
            "aliases": aliases,
            "enabled": enabled,
            "created_at": now,
            "updated_at": now,
            "route_id": route_id,
            "allowed_actions": allowed_actions,
        }
        slot_bindings.append(binding)
        role_assignments.append({
            "assignment_id": f"assignment-{slot_id}",
            "assignment_revision": 1,
            "slot_id": slot_id,
            "role_label": role or "coding_agent",
            "role_instruction": "",
            "assignment_context_policy": CONTEXT_POLICY_FRESH,
            "scope": "slot",
            "expires_at": None,
        })
        legacy_projection.append({
            "agent_id": agent_id,
            "display_name": display_name,
            "role": role or "coding_agent",
            "aliases": aliases,
            "lane": lane,
            "enabled": enabled,
            "allowed_actions": allowed_actions,
            **({"model_id": model_id} if lane == PRIMARY_CHATGPT_LANE else {"route_id": route_id}),
        })

    return {
        "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
        "packet_kind": ACTOR_REGISTRY_PACKET_KIND,
        "updated_at_utc": now,
        "registry_revision": 1,
        "actors": actors,
        "slot_bindings": slot_bindings,
        "role_assignments": role_assignments,
        "agent_bindings": legacy_projection,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }


def project_legacy_agent_bindings(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project canonical registry sections back into v1-shaped bindings."""
    actors_by_id = {
        str(actor.get("actor_id") or ""): actor
        for actor in document.get("actors", [])
        if _is_mapping(actor)
    }
    role_by_slot = {
        str(assignment.get("slot_id") or ""): str(assignment.get("role_label") or "")
        for assignment in document.get("role_assignments", [])
        if _is_mapping(assignment)
    }
    projection: list[dict[str, Any]] = []
    for raw in document.get("slot_bindings", []):
        if not _is_mapping(raw):
            continue
        slot_id = str(raw.get("slot_id") or "")
        actor_id = str(raw.get("actor_id") or "")
        actor = actors_by_id.get(actor_id, {})
        lane = PRIMARY_CHATGPT_LANE if slot_id == PRIMARY_SLOT_ID else API_ROUTE_LANE
        binding: dict[str, Any] = {
            "agent_id": actor_id,
            "display_name": str(actor.get("display_name") or ""),
            "role": role_by_slot.get(slot_id) or str(actor.get("capability_profile_id") or ""),
            "aliases": _safe_list(raw.get("aliases")),
            "lane": lane,
            "enabled": raw.get("enabled") is True,
            "allowed_actions": _safe_list(raw.get("allowed_actions"), max_length=64),
        }
        if lane == PRIMARY_CHATGPT_LANE:
            binding["model_id"] = str(actor.get("model_id") or "")
        else:
            binding["route_id"] = str(raw.get("route_id") or "")
        projection.append(binding)
    return projection


def validate_actor_registry_document(document: object) -> dict[str, Any]:
    """Structural validation of a canonical registry document (schema v2)."""
    reasons: list[str] = []
    if not _is_mapping(document):
        return {"valid": False, "reasons": ["document_not_object"]}
    doc = dict(document)
    if doc.get("schema_version") != ACTOR_REGISTRY_SCHEMA_VERSION:
        reasons.append("schema_version_not_2")
    if doc.get("packet_kind") not in ACCEPTED_STATE_PACKET_KINDS:
        reasons.append("packet_kind_wrong")
    unknown_fields = sorted(set(doc) - ALLOWED_DOCUMENT_FIELDS)
    if unknown_fields:
        reasons.append("document_unknown_fields")
    forbidden_doc_fields = sorted(set(doc) & FORBIDDEN_REGISTRY_FIELDS)
    if forbidden_doc_fields:
        reasons.append("document_forbidden_fields")

    actors = doc.get("actors", [])
    slot_bindings = doc.get("slot_bindings", [])
    role_assignments = doc.get("role_assignments", [])
    if not isinstance(actors, list):
        reasons.append("actors_not_list")
    if not isinstance(slot_bindings, list):
        reasons.append("slot_bindings_not_list")
    if not isinstance(role_assignments, list):
        reasons.append("role_assignments_not_list")

    actor_ids: set[str] = set()
    if isinstance(actors, list):
        for index, actor in enumerate(actors):
            if not _is_mapping(actor):
                reasons.append(f"actor_{index}_not_object")
                continue
            forbidden = _forbidden_fields_present(actor)
            if forbidden:
                reasons.append(f"actor_{index}_forbidden_fields")
            unknown = sorted(set(actor) - ALLOWED_ACTOR_FIELDS)
            if unknown:
                reasons.append(f"actor_{index}_unknown_fields")
            actor_id = _safe_id(actor.get("actor_id"))
            if not actor_id:
                reasons.append(f"actor_{index}_actor_id_missing")
            elif actor_id in actor_ids:
                reasons.append(f"actor_{index}_actor_id_duplicate")
            actor_ids.add(actor_id)
            if actor.get("transport_adapter_id") not in ALLOWED_TRANSPORT_ADAPTERS:
                reasons.append(f"actor_{index}_adapter_unknown")
            if actor.get("permission_ceiling") not in ALLOWED_PERMISSION_CEILINGS:
                reasons.append(f"actor_{index}_permission_ceiling_unknown")
            revision = actor.get("revision")
            if not isinstance(revision, int) or revision < 1:
                reasons.append(f"actor_{index}_revision_invalid")
            if actor.get("enabled") is not True and actor.get("enabled") is not False:
                reasons.append(f"actor_{index}_enabled_not_bool")

    bound_slots: set[str] = set()
    seen_aliases: dict[str, str] = {}
    seen_binding_ids: dict[str, str] = {}
    if isinstance(slot_bindings, list):
        for index, binding in enumerate(slot_bindings):
            if not _is_mapping(binding):
                reasons.append(f"binding_{index}_not_object")
                continue
            forbidden = _forbidden_fields_present(binding)
            if forbidden:
                reasons.append(f"binding_{index}_forbidden_fields")
            unknown = sorted(set(binding) - ALLOWED_SLOT_BINDING_FIELDS)
            if unknown:
                reasons.append(f"binding_{index}_unknown_fields")
            slot_id = str(binding.get("slot_id") or "")
            if not slot_id:
                reasons.append(f"binding_{index}_slot_id_missing")
            elif slot_id in bound_slots:
                reasons.append(f"binding_{index}_slot_id_duplicate")
            bound_slots.add(slot_id)
            binding_id = str(binding.get("binding_id") or "")
            if not binding_id:
                reasons.append(f"binding_{index}_binding_id_missing")
            elif binding_id in seen_binding_ids:
                reasons.append(f"binding_{index}_binding_id_duplicate")
            else:
                seen_binding_ids[binding_id] = slot_id
            actor_id = str(binding.get("actor_id") or "")
            if actor_id and actor_id not in actor_ids:
                reasons.append(f"binding_{index}_actor_id_unknown")
            if binding.get("enabled") is not True and binding.get("enabled") is not False:
                reasons.append(f"binding_{index}_enabled_not_bool")
            revision = binding.get("binding_revision")
            if not isinstance(revision, int) or revision < 1:
                reasons.append(f"binding_{index}_binding_revision_invalid")
            aliases = binding.get("aliases") if isinstance(binding.get("aliases"), list) else []
            if not aliases:
                reasons.append(f"binding_{index}_aliases_missing")
            for alias in aliases:
                key = str(alias).strip().casefold()
                if not key:
                    reasons.append(f"binding_{index}_alias_empty")
                    continue
                if key in seen_aliases:
                    reasons.append(f"alias_duplicate:{alias}")
                else:
                    seen_aliases[key] = slot_id
            route_id = str(binding.get("route_id") or "")
            if slot_id != PRIMARY_SLOT_ID and route_id in FORBIDDEN_STALE_ROUTE_IDS:
                reasons.append(f"binding_{index}_route_id_stale")

    if isinstance(role_assignments, list):
        seen_assignments: set[str] = set()
        for index, assignment in enumerate(role_assignments):
            if not _is_mapping(assignment):
                reasons.append(f"assignment_{index}_not_object")
                continue
            forbidden = _forbidden_fields_present(assignment)
            if forbidden:
                reasons.append(f"assignment_{index}_forbidden_fields")
            unknown = sorted(set(assignment) - ALLOWED_ROLE_ASSIGNMENT_FIELDS)
            if unknown:
                reasons.append(f"assignment_{index}_unknown_fields")
            assignment_id = str(assignment.get("assignment_id") or "")
            if not assignment_id:
                reasons.append(f"assignment_{index}_assignment_id_missing")
            elif assignment_id in seen_assignments:
                reasons.append(f"assignment_{index}_assignment_id_duplicate")
            seen_assignments.add(assignment_id)
            slot_id = str(assignment.get("slot_id") or "")
            if slot_id and slot_id not in bound_slots:
                reasons.append(f"assignment_{index}_slot_id_unbound")
            if assignment.get("assignment_context_policy") not in ALLOWED_CONTEXT_POLICIES:
                reasons.append(f"assignment_{index}_context_policy_unknown")
            revision = assignment.get("assignment_revision")
            if not isinstance(revision, int) or revision < 1:
                reasons.append(f"assignment_{index}_assignment_revision_invalid")

    if not any(binding.get("slot_id") == PRIMARY_SLOT_ID and binding.get("enabled") is True
               for binding in slot_bindings if _is_mapping(binding)):
        reasons.append("primary_slot_enabled_binding_missing")

    # Round-trip: the persisted legacy projection must equal the canonical
    # projection, otherwise canonical and wire truth are split-brain.
    if isinstance(document, Mapping):
        stored_projection = document.get("agent_bindings")
        if isinstance(stored_projection, list):
            canonical_projection = project_legacy_agent_bindings(document)
            if stored_projection != canonical_projection:
                reasons.append("legacy_projection_mismatch")

    return {"valid": not reasons, "reasons": reasons}


def _migration_step_v1_to_v2(route_records: list[dict[str, Any]] | None = None):
    def migrate(payload: dict[str, Any]) -> dict[str, Any]:
        raw_bindings = payload.get("agent_bindings")
        return build_actor_registry_document(raw_bindings, route_records=route_records)
    return state_migration.MigrationStep(
        from_version=1,
        to_version=ACTOR_REGISTRY_SCHEMA_VERSION,
        migrate=migrate,
    )


def _migration_backup_dir(managed_dir: Path) -> Path:
    return managed_dir / MIGRATION_BACKUP_SUBDIR


def _invalid_packet(reason: str) -> dict[str, Any]:
    return _packet(
        status="blocked",
        machine_error_code="ACTOR_REGISTRY_STATE_INVALID",
        human_message="Actor registry state file is invalid.",
        changed_files=[],
        next_action="repair_or_remove_actor_registry_state",
        liveness="down",
        extra={
            "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
            "packet_kind": ACTOR_REGISTRY_LIST_KIND,
            "captured_at_utc": utc_now(),
            "state_file_present": True,
            "state_path_redacted": True,
            "registry_revision": None,
            "actors": [],
            "slot_bindings": [],
            "role_assignments": [],
            "agent_bindings": [],
            "migration_status": "invalid",
            "invalid_reason": reason,
            "secret_value_exposed": False,
        },
    )


def read_actor_registry_packet(path: Path) -> dict[str, Any]:
    """Read surface: report registry state without mutating anything."""
    state_file_present = path.is_file()
    if not state_file_present:
        return _packet(
            status="not_initialized",
            machine_error_code="ACTOR_REGISTRY_NOT_INITIALIZED",
            human_message="No actor registry state file exists yet.",
            changed_files=[],
            next_action="write_agent_bindings_or_migrate",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_LIST_KIND,
                "captured_at_utc": utc_now(),
                "state_file_present": False,
                "state_path_redacted": True,
                "registry_revision": None,
                "actors": [],
                "slot_bindings": [],
                "role_assignments": [],
                "agent_bindings": [],
                "migration_status": "not_applicable",
                "secret_value_exposed": False,
            },
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _invalid_packet("state_file_unreadable_or_invalid_json")
    if not isinstance(document, dict):
        return _invalid_packet("state_document_not_object")
    version = document.get("schema_version")
    if version == ACTOR_REGISTRY_SCHEMA_VERSION:
        validation = validate_actor_registry_document(document)
        if not validation["valid"]:
            return _invalid_packet(";".join(validation["reasons"]))
        return _packet(
            status="ok",
            machine_error_code="OK",
            human_message="Canonical actor registry is valid.",
            changed_files=[],
            next_action="none",
            liveness="healthy",
            exit_code=0,
            operator_action="none",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_LIST_KIND,
                "captured_at_utc": utc_now(),
                "state_file_present": True,
                "state_path_redacted": True,
                "registry_revision": document.get("registry_revision"),
                "actors": document.get("actors", []),
                "slot_bindings": document.get("slot_bindings", []),
                "role_assignments": document.get("role_assignments", []),
                "agent_bindings": document.get("agent_bindings", []),
                "migration_status": "current",
                "secret_value_exposed": False,
            },
        )
    if version == 1:
        return _packet(
            status="migration_pending",
            machine_error_code="ACTOR_REGISTRY_MIGRATION_PENDING",
            human_message="Actor registry is on schema v1; run actors migrate --json.",
            changed_files=[],
            next_action="actors_migrate",
            extra={
                "schema_version": 1,
                "packet_kind": ACTOR_REGISTRY_LIST_KIND,
                "captured_at_utc": utc_now(),
                "state_file_present": True,
                "state_path_redacted": True,
                "registry_revision": None,
                "actors": [],
                "slot_bindings": [],
                "role_assignments": [],
                "agent_bindings": document.get("agent_bindings", []),
                "migration_status": "v1_pending",
                "secret_value_exposed": False,
            },
        )
    return _invalid_packet("schema_version_unsupported")


def run_actor_registry_migrate(
    path: Path,
    *,
    dry_run: bool,
    route_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Owner surface: transactional v1 -> v2 migration with backup/rollback."""
    if not path.is_file():
        return _packet(
            status="blocked",
            machine_error_code="ACTOR_REGISTRY_MIGRATION_NO_STATE",
            human_message="No actor registry state file exists; nothing to migrate.",
            changed_files=[],
            next_action="write_agent_bindings_first",
            liveness="down",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_MIGRATION_KIND,
                "captured_at_utc": utc_now(),
                "state_path_redacted": True,
                "dry_run": dry_run,
                "from_schema_version": None,
                "to_schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "backup_path": None,
                "rollback_available": False,
            },
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _invalid_packet("state_file_unreadable_or_invalid_json")
    if not isinstance(document, dict):
        return _invalid_packet("state_document_not_object")
    from_version = document.get("schema_version")
    if from_version == ACTOR_REGISTRY_SCHEMA_VERSION:
        validation = validate_actor_registry_document(document)
        return _packet(
            status="ok" if validation["valid"] else "blocked",
            machine_error_code="ACTOR_REGISTRY_ALREADY_CURRENT" if validation["valid"] else "ACTOR_REGISTRY_STATE_INVALID",
            human_message="Actor registry is already on schema v2." if validation["valid"] else "Actor registry state is invalid.",
            changed_files=[],
            next_action="none" if validation["valid"] else "repair_or_remove_actor_registry_state",
            exit_code=0 if validation["valid"] else 1,
            liveness="healthy" if validation["valid"] else "down",
            operator_action="none" if validation["valid"] else "user_action",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_MIGRATION_KIND,
                "captured_at_utc": utc_now(),
                "state_path_redacted": True,
                "dry_run": dry_run,
                "from_schema_version": from_version,
                "to_schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "backup_path": None,
                "rollback_available": False,
                "invalid_reasons": validation.get("reasons", []),
            },
        )
    if from_version != 1:
        return _invalid_packet("schema_version_unsupported")
    # Preview the migrated document for dry-run and validation before any write.
    raw_bindings = document.get("agent_bindings")
    migrated_document = build_actor_registry_document(raw_bindings, route_records=route_records)
    validation = validate_actor_registry_document(migrated_document)
    if not validation["valid"]:
        return _packet(
            status="blocked",
            machine_error_code="ACTOR_REGISTRY_MIGRATION_VALIDATION_FAILED",
            human_message="Migrated registry document failed canonical validation.",
            changed_files=[],
            next_action="repair_agent_bindings_first",
            liveness="down",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_MIGRATION_KIND,
                "captured_at_utc": utc_now(),
                "state_path_redacted": True,
                "dry_run": dry_run,
                "from_schema_version": 1,
                "to_schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "backup_path": None,
                "rollback_available": False,
                "invalid_reasons": validation["reasons"],
            },
        )
    backup_dir = _migration_backup_dir(path.parent)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return _packet(
            status="ok",
            machine_error_code="ACTOR_REGISTRY_MIGRATION_DRY_RUN",
            human_message="Actor registry migration dry-run would migrate v1 -> v2.",
            changed_files=[],
            next_action="actors_migrate_apply",
            liveness="healthy",
            exit_code=0,
            operator_action="none",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_MIGRATION_KIND,
                "captured_at_utc": utc_now(),
                "state_path_redacted": True,
                "dry_run": True,
                "from_schema_version": 1,
                "to_schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "backup_path": None,
                "rollback_available": True,
                "migrated_registry_revision": migrated_document.get("registry_revision"),
                "migrated_actor_count": len(migrated_document.get("actors", [])),
            },
        )
    try:
        result = state_migration.migrate_json_file(
            path,
            target_schema_version=ACTOR_REGISTRY_SCHEMA_VERSION,
            migrations=(_migration_step_v1_to_v2(route_records),),
            backup_dir=backup_dir,
        )
    except state_migration.StateMigrationError as exc:
        return _packet(
            status="blocked",
            machine_error_code=exc.machine_error_code,
            human_message=f"Actor registry migration failed: {exc.message}",
            changed_files=[],
            next_action="restore_backup_or_repair",
            liveness="down",
            extra={
                "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "packet_kind": ACTOR_REGISTRY_MIGRATION_KIND,
                "captured_at_utc": utc_now(),
                "state_path_redacted": True,
                "dry_run": False,
                "from_schema_version": 1,
                "to_schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
                "backup_path": None,
                "rollback_available": True,
            },
        )
    return _packet(
        status="ok",
        machine_error_code="ACTOR_REGISTRY_MIGRATED" if result.committed else "ACTOR_REGISTRY_ALREADY_CURRENT",
        human_message="Actor registry migrated v1 -> v2 with backup." if result.committed else "Actor registry is already current.",
        changed_files=list(result.changed_files),
        next_action="none",
        liveness="healthy",
        exit_code=0,
        operator_action="none",
        extra={
            "schema_version": ACTOR_REGISTRY_SCHEMA_VERSION,
            "packet_kind": ACTOR_REGISTRY_MIGRATION_KIND,
            "captured_at_utc": utc_now(),
            "state_path_redacted": True,
            "dry_run": False,
            "from_schema_version": result.from_schema_version,
            "to_schema_version": result.to_schema_version,
            "backup_path": result.backup_path,
            "rollback_available": result.committed,
            "rollback_instruction": (
                "restore the backup file to the registry path to roll back"
                if result.committed
                else None
            ),
        },
    )


def resolve_binding_reference(
    document: Mapping[str, Any],
    *,
    slot_id: str = "",
    alias: str = "",
) -> dict[str, Any]:
    """Resolve the canonical binding/assignment reference for a slot or alias.

    Used by transport sessions (codex_custom_sessions reconciliation) to bind
    session state to canonical registry revisions instead of hardcoded agent
    ids.
    """
    bindings = [
        b for b in document.get("slot_bindings", [])
        if _is_mapping(b) and b.get("enabled") is True
    ]
    selected: dict[str, Any] | None = None
    if slot_id:
        selected = next((b for b in bindings if str(b.get("slot_id") or "") == slot_id), None)
    if selected is None and alias:
        key = str(alias).strip().casefold()
        selected = next(
            (
                b for b in bindings
                if key in {str(a).strip().casefold() for a in (b.get("aliases") or [])}
            ),
            None,
        )
    if selected is None:
        return {}
    assignments = [
        a for a in document.get("role_assignments", [])
        if _is_mapping(a) and str(a.get("slot_id") or "") == str(selected.get("slot_id") or "")
    ]
    assignment = assignments[0] if assignments else {}
    return {
        "registry_schema_version": document.get("schema_version"),
        "registry_revision": document.get("registry_revision"),
        "slot_id": selected.get("slot_id"),
        "binding_id": selected.get("binding_id"),
        "binding_revision": selected.get("binding_revision"),
        "actor_id": selected.get("actor_id"),
        "assignment_id": assignment.get("assignment_id"),
        "assignment_revision": assignment.get("assignment_revision"),
        "actor_registry_reference_present": True,
    }


def agent_bindings_path_or_default(managed_dir: Path) -> Path:
    """Canonical registry state path (same file as v1, schema v2 now)."""
    return agent_bindings_state_path(managed_dir)


__all__ = [
    "ACTOR_REGISTRY_SCHEMA_VERSION",
    "ACTOR_REGISTRY_PACKET_KIND",
    "ACTOR_REGISTRY_LIST_KIND",
    "ACTOR_REGISTRY_MIGRATION_KIND",
    "MIGRATION_BACKUP_SUBDIR",
    "NATIVE_PRIMARY_ADAPTER",
    "API_ADAPTER",
    "CLI_ONE_SHOT_ADAPTER",
    "CLI_ACP_ADAPTER",
    "PRIMARY_SLOT_ID",
    "CONTEXT_POLICY_CONTINUE",
    "CONTEXT_POLICY_FRESH",
    "CONTEXT_POLICY_FORK",
    "PERMISSION_NONE",
    "PERMISSION_CONTEXT_ONLY",
    "PERMISSION_REPO_READ",
    "PERMISSION_REPO_WRITE",
    "PERMISSION_BROWSER_READ",
    "PERMISSION_NETWORK_READ",
    "build_actor_registry_document",
    "project_legacy_agent_bindings",
    "validate_actor_registry_document",
    "read_actor_registry_packet",
    "run_actor_registry_migrate",
    "resolve_binding_reference",
    "agent_bindings_path_or_default",
]
