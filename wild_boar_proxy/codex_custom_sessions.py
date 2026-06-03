# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Server-owned Codex Custom session lifecycle packets."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import shlex
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from wild_boar_proxy.operator_surface import redact_text
from wild_boar_proxy.process_runner import run_bounded_process

from wild_boar_proxy.codex_account_selection import (
    ACCOUNT_CANDIDATE_PROVENANCE_STATUS,
    ROUTE_CANDIDATE_PROVENANCE_STATUS,
    ROUTE_CANDIDATE_SOURCE,
    build_account_selection_packet,
)
from wild_boar_proxy.codex_model_registry import (
    API_ROUTE_MODEL_LANE,
    CODEX_ACCOUNT_MODEL_LANE,
    build_custom_model_registry_packet,
    build_dual_lane_model_selection_ui_packet,
    model_lane_classification_from_registry,
)

PRIMARY_MODEL_SLOT = "primary_model_slot"
CODING_AGENT_MODEL_SLOT = "coding_agent_model_slot"
REVIEWER_MODEL_SLOT = "reviewer_model_slot"
CHEAP_SCANNER_MODEL_SLOT = "cheap_scanner_model_slot"
DEEP_REASONING_MODEL_SLOT = "deep_reasoning_model_slot"
ROLE_SLOT_PAYLOAD_FIELDS = {
    PRIMARY_MODEL_SLOT: "primary_model_id",
    CODING_AGENT_MODEL_SLOT: "coding_agent_model_id",
    REVIEWER_MODEL_SLOT: "reviewer_model_id",
    CHEAP_SCANNER_MODEL_SLOT: "cheap_scanner_model_id",
    DEEP_REASONING_MODEL_SLOT: "deep_reasoning_model_id",
}
ROLE_SLOT_IDS = tuple(ROLE_SLOT_PAYLOAD_FIELDS)
SESSION_CREATE_ALLOWED_FIELDS = set(ROLE_SLOT_PAYLOAD_FIELDS.values())
PROMPT_DRY_RUN_ALLOWED_FIELDS = {"prompt"}
PROMPT_RUN_ALLOWED_FIELDS = {"prompt", "slot_id"}
TEMP_WRITE_PROBE_ALLOWED_FIELDS = {"api_model_id"}
SAFE_WORKTREE_EDIT_PROBE_ALLOWED_FIELDS = {"api_model_id"}
SAFE_WORKTREE_CODER_ALLOWED_FIELDS = {"api_model_id", "task"}
REPO_TMP_EDIT_PROBE_ALLOWED_FIELDS = {"api_model_id"}
MIXED_SLOT_DISPATCH_PROBE_ALLOWED_FIELDS: set[str] = set()
SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{7,80}$")
PROMPT_RUN_ALLOWED_STATUSES = {
    "ready",
    "prompt_admitted_dry_run",
    "prompt_completed_e2e",
    "prompt_failed_e2e",
}
BOUNDED_RESPONSE_PREVIEW_CHARS = 240
SESSION_SCHEMA_VERSION = 3
SESSION_GIT_RUNTIME_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SESSION_GIT_OUTPUT_CAP_BYTES = 64 * 1024
SESSION_CREATE_FORBIDDEN_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "profile_path",
    "path",
    "backend_id",
    "route_id",
    "provider",
    "endpoint",
    "base_url",
    "openai_base_url",
    "model_provider",
    "model_lane",
    "model_lane_classification_source",
    "wire_api",
    "proxy",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "home",
    "codex_home",
    "runtime_config",
    "account_id",
    "secret_ref",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_preview(value: str) -> str:
    return f"<prompt:{len(value)}:{_digest(value)[:8]}>"


def _forbidden_fields(payload: Any, allowed_fields: set[str], prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            key_lower = key_text.lower()
            if key_lower not in allowed_fields or prefix:
                findings.append(key_path)
            findings.extend(_forbidden_fields(value, allowed_fields, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_forbidden_fields(value, allowed_fields, f"{prefix}[{index}]"))
    return findings


def forbidden_session_create_fields(payload: Any) -> list[str]:
    findings = _forbidden_fields(payload, SESSION_CREATE_ALLOWED_FIELDS)
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = key_text
            if key_text.lower() in SESSION_CREATE_FORBIDDEN_FIELDS:
                findings.append(key_path)
            findings.extend(_session_create_forbidden_nested_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_session_create_forbidden_nested_fields(value, f"[{index}]"))
    return sorted(set(findings))


def _session_create_forbidden_nested_fields(payload: Any, prefix: str) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in SESSION_CREATE_FORBIDDEN_FIELDS:
                findings.append(key_path)
            else:
                findings.append(key_path)
            findings.extend(_session_create_forbidden_nested_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_session_create_forbidden_nested_fields(value, f"{prefix}[{index}]"))
    return findings


def forbidden_prompt_dry_run_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, PROMPT_DRY_RUN_ALLOWED_FIELDS)))


def forbidden_prompt_run_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, PROMPT_RUN_ALLOWED_FIELDS)))


def forbidden_temp_write_probe_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, TEMP_WRITE_PROBE_ALLOWED_FIELDS)))


def forbidden_safe_worktree_edit_probe_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, SAFE_WORKTREE_EDIT_PROBE_ALLOWED_FIELDS)))


def forbidden_safe_worktree_coder_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, SAFE_WORKTREE_CODER_ALLOWED_FIELDS)))


def forbidden_repo_tmp_edit_probe_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, REPO_TMP_EDIT_PROBE_ALLOWED_FIELDS)))


def forbidden_mixed_slot_dispatch_probe_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, MIXED_SLOT_DISPATCH_PROBE_ALLOWED_FIELDS)))


def _model_ids(
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None = None,
) -> list[str]:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    return [str(entry["model_id"]) for entry in registry.get("available_models", [])]


def _selector_entry_index(
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status,
        api_snapshot=api_snapshot,
    )
    entries: dict[str, dict[str, Any]] = {}
    for lane in ("chatgpt_lane", "api_lane"):
        for entry in selector.get(lane, {}).get("models", []):
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("model_id") or "")
            if model_id:
                entries[model_id] = entry
    return entries


def _unbound_slot(slot_id: str) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "model_id": "",
        "lane_kind": "unbound",
        "model_catalog_entry_server_issued": False,
        "model_lane": "unknown_lane",
        "model_lane_classified": False,
        "model_lane_classification_source": "none",
        "model_lane_fallback_used": False,
        "model_lane_proof_level": "unclassified",
        "runtime_lane_proven": False,
        "server_issued": False,
        "binding_status": "unbound",
        "binding_source": "none",
        "selection_intent_only": False,
        "runtime_dispatch_state": "unresolved_in_this_contour",
        "persisted": False,
        "persisted_source": "session_state_file",
        "selected_source_class": "none",
        "selected_backend_ref": "",
        "selected_backend_server_issued": False,
        "selected_route_ref": "",
        "selected_route_server_issued": False,
        "route_provenance_required": False,
        "route_provenance_proven": False,
        "source_provenance_status": "not_proven",
        "api_model_selected_by_user": False,
        "route_selected_by_user": False,
        "browser_selected_route": False,
        "route_candidate_source": "none",
        "route_candidate_classified": False,
        "route_static_readiness_classified": False,
        "route_execution_proven": False,
        "provider_response_proven": False,
        "secret_validity_proven": False,
        "raw_route_exposed": False,
        "raw_secret_ref_exposed": False,
        "model_selected_by_user": False,
        "role_slot_selected_by_user": False,
        "account_selected_by_user": False,
        "browser_selected_backend": False,
        "account_candidate_source": "none",
        "account_execution_proven": False,
        "runtime_execution_proven": False,
        "live_compatibility_proven": False,
        "raw_backend_exposed": False,
        "raw_backend_id_exposed": False,
        "selection_proven": False,
        "selection_dry_run_proven": False,
        "live_selection_proven": False,
    }


def _bound_slot(
    *,
    slot_id: str,
    model_id: str,
    lane_kind: str,
    binding_source: str,
    selection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "model_id": model_id,
        "lane_kind": lane_kind,
        "model_catalog_entry_server_issued": (
            selection.get("model_catalog_entry_server_issued") is True
        ),
        "model_lane": str(selection.get("model_lane") or "unknown_lane"),
        "model_lane_classified": selection.get("model_lane_classified") is True,
        "model_lane_classification_source": str(
            selection.get("model_lane_classification_source") or "none"
        ),
        "model_lane_fallback_used": selection.get("model_lane_fallback_used") is True,
        "model_lane_proof_level": str(selection.get("model_lane_proof_level") or "unclassified"),
        "runtime_lane_proven": selection.get("runtime_lane_proven") is True,
        "server_issued": True,
        "binding_status": "bound",
        "binding_source": binding_source,
        "selection_intent_only": False,
        "runtime_dispatch_state": "unresolved_in_this_contour",
        "persisted": True,
        "persisted_source": "session_state_file",
        "selected_source_class": str(selection.get("selected_source_class") or "none"),
        "selected_backend_ref": str(selection.get("selected_backend_ref") or ""),
        "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
        "selected_route_ref": str(selection.get("selected_route_ref") or ""),
        "selected_route_server_issued": selection.get("selected_route_server_issued") is True,
        "route_provenance_required": selection.get("route_provenance_required") is True,
        "route_provenance_proven": selection.get("route_provenance_proven") is True,
        "source_provenance_status": str(
            selection.get("source_provenance_status") or "not_proven"
        ),
        "api_model_selected_by_user": selection.get("api_model_selected_by_user") is True,
        "route_selected_by_user": selection.get("route_selected_by_user") is True,
        "browser_selected_route": selection.get("browser_selected_route") is True,
        "route_candidate_source": str(selection.get("route_candidate_source") or "none"),
        "route_candidate_classified": selection.get("route_candidate_classified") is True,
        "route_static_readiness_classified": (
            selection.get("route_static_readiness_classified") is True
            or (
                selection.get("selected_route_server_issued") is True
                and selection.get("route_provenance_required") is True
            )
        ),
        "route_execution_proven": selection.get("route_execution_proven") is True,
        "provider_response_proven": selection.get("provider_response_proven") is True,
        "secret_validity_proven": selection.get("secret_validity_proven") is True,
        "raw_route_exposed": selection.get("raw_route_exposed") is True,
        "raw_secret_ref_exposed": selection.get("raw_secret_ref_exposed") is True,
        "model_selected_by_user": True,
        "role_slot_selected_by_user": True,
        "account_selected_by_user": selection.get("account_selected_by_user") is True,
        "browser_selected_backend": selection.get("browser_selected_backend") is True,
        "account_candidate_source": str(selection.get("account_candidate_source") or "none"),
        "account_execution_proven": selection.get("account_execution_proven") is True,
        "runtime_execution_proven": selection.get("runtime_execution_proven") is True,
        "live_compatibility_proven": selection.get("live_compatibility_proven") is True,
        "raw_backend_exposed": selection.get("raw_backend_exposed") is True,
        "raw_backend_id_exposed": selection.get("raw_backend_id_exposed") is True,
        "selection_proven": selection.get("selection_proven") is True,
        "selection_dry_run_proven": selection.get("selection_dry_run_proven") is True,
        "live_selection_proven": selection.get("live_selection_proven") is True,
    }


def _slot_model_ids_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    slot_model_ids: dict[str, str] = {}
    primary_model_id = payload.get(ROLE_SLOT_PAYLOAD_FIELDS[PRIMARY_MODEL_SLOT])
    if isinstance(primary_model_id, str) and primary_model_id:
        slot_model_ids[PRIMARY_MODEL_SLOT] = primary_model_id
    for slot_id, field in ROLE_SLOT_PAYLOAD_FIELDS.items():
        if slot_id == PRIMARY_MODEL_SLOT:
            continue
        value = payload.get(field)
        if isinstance(value, str) and value:
            slot_model_ids[slot_id] = value
    return slot_model_ids


def _required_choice_fields() -> list[str]:
    return [
        ROLE_SLOT_PAYLOAD_FIELDS[PRIMARY_MODEL_SLOT],
    ]


def _canonical_role_slots(
    bound_slots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    bound_slots = bound_slots or {}
    role_slots: dict[str, dict[str, Any]] = {}
    for slot_id in ROLE_SLOT_IDS:
        role_slots[slot_id] = dict(bound_slots.get(slot_id) or _unbound_slot(slot_id))
    return role_slots


def _primary_model_id_from_role_slots(role_slots: dict[str, dict[str, Any]]) -> str:
    return str(role_slots.get(PRIMARY_MODEL_SLOT, {}).get("model_id") or "")


def _primary_model_lane_kind(role_slots: dict[str, dict[str, Any]]) -> str:
    return str(role_slots.get(PRIMARY_MODEL_SLOT, {}).get("lane_kind") or "unbound")


def _slot_id_from_prompt_payload(payload: dict[str, Any]) -> str | None:
    slot_id = payload.get("slot_id")
    if slot_id is None:
        return PRIMARY_MODEL_SLOT
    if isinstance(slot_id, str) and slot_id in ROLE_SLOT_IDS:
        return slot_id
    return None


def _response_preview(value: str) -> str:
    return redact_text(value)[:BOUNDED_RESPONSE_PREVIEW_CHARS]


def _token_usage(result: dict[str, Any]) -> tuple[bool, dict[str, Any], int | None]:
    raw_usage = result.get("token_usage") or result.get("usage")
    if not isinstance(raw_usage, dict):
        return False, {}, None
    usage = {
        str(key): value
        for key, value in raw_usage.items()
        if isinstance(key, str) and isinstance(value, (int, float, str, bool)) and key.lower() != "api_key"
    }
    total = usage.get("total_tokens") or usage.get("total")
    return True, usage, int(total) if isinstance(total, int) else None


def _safe_trace_observer_packet(packet: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "request_observed",
        "request_count",
        "response_observed",
        "forwarded_to_wbp",
        "forwarded_endpoint",
        "method",
        "path",
        "request_body_sha256",
        "response_body_sha256",
        "upstream_status",
        "prompt_body_recorded",
        "auth_header_recorded",
        "secret_value_recorded",
        "raw_account_id_recorded",
        "raw_backend_id_recorded",
        "response_error_code",
        "response_error_message_bounded",
        "response_error_param",
        "response_error_type",
        "machine_error_code",
        "observer_closed",
    }
    safe: dict[str, Any] = {}
    for key, value in packet.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, bool)) or value is None:
            safe[key] = value
    return safe


def _run_git_command(
    repo_root: Path,
    args: list[str],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    try:
        result = run_bounded_process(
            ["git", *args],
            env={
                "PATH": SESSION_GIT_RUNTIME_PATH,
                "NO_PROXY": "127.0.0.1,localhost,::1",
                "no_proxy": "127.0.0.1,localhost,::1",
            },
            cwd=repo_root,
            timeout_seconds=timeout_seconds,
            output_cap_bytes=SESSION_GIT_OUTPUT_CAP_BYTES,
        )
    except Exception as exc:  # pragma: no cover - defensive host boundary
        return {
            "ok": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {str(exc)[:240]}",
            "timed_out": type(exc).__name__ == "TimeoutExpired",
        }
    return {
        "ok": result.exit_code == 0,
        "exit_code": result.exit_code if result.exit_code is not None else 127,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
    }


def _safe_process_network_observation_packet(packet: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "status",
        "machine_error_code",
        "process_tree_observed",
        "sample_count",
        "observed_process_count_max",
        "allowed_local_endpoints",
        "allowed_local_endpoint_observed",
        "peer_endpoints",
        "non_local_peer_endpoints_present",
        "classification",
        "direct_non_wbp_model_egress_absent_proven",
        "raw_pid_exposed",
        "pid_not_exposed_to_browser",
        "secret_value_recorded",
    }
    safe: dict[str, Any] = {}
    for key, value in packet.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = value
    return safe


def _source_provenance_status(session: dict[str, Any]) -> str:
    if session.get("route_provenance_required") is True:
        if (
            session.get("selected_route_server_issued") is True
            and session.get("route_provenance_proven") is True
        ):
            return "route_proven"
        if session.get("route_static_readiness_classified") is True:
            return ROUTE_CANDIDATE_PROVENANCE_STATUS
        return "route_provenance_missing"
    if session.get("selected_backend_server_issued") is True:
        return ACCOUNT_CANDIDATE_PROVENANCE_STATUS
    return "not_proven"


def _source_provenance_satisfied(session: dict[str, Any]) -> bool:
    return _source_provenance_status(session) in {
        ACCOUNT_CANDIDATE_PROVENANCE_STATUS,
        ROUTE_CANDIDATE_PROVENANCE_STATUS,
        "route_proven",
    }


def _source_candidate_classified(session: dict[str, Any]) -> bool:
    return _source_provenance_satisfied(session)


def _slot_source_provenance_status(slot: dict[str, Any], session: dict[str, Any]) -> str:
    if slot.get("selected_source_class") == "route_backed" or slot.get(
        "route_provenance_required"
    ) is True:
        if (
            slot.get("selected_route_server_issued") is True
            and slot.get("route_provenance_proven") is True
        ):
            return "route_proven"
        if slot.get("route_static_readiness_classified") is True:
            return ROUTE_CANDIDATE_PROVENANCE_STATUS
        return "route_provenance_missing"
    if slot.get("selected_backend_server_issued") is True:
        return ACCOUNT_CANDIDATE_PROVENANCE_STATUS
    if slot.get("slot_id") == PRIMARY_MODEL_SLOT:
        return _source_provenance_status(session)
    return "not_proven"


def _slot_source_provenance_satisfied(slot: dict[str, Any], session: dict[str, Any]) -> bool:
    return _slot_source_provenance_status(slot, session) in {
        ACCOUNT_CANDIDATE_PROVENANCE_STATUS,
        ROUTE_CANDIDATE_PROVENANCE_STATUS,
        "route_proven",
    }


def _slot_source_candidate_classified(slot: dict[str, Any], session: dict[str, Any]) -> bool:
    return _slot_source_provenance_satisfied(slot, session)


def _slot_dispatch_admission_packet(
    *,
    session: dict[str, Any],
    slot: dict[str, Any],
    requested_slot_id: str,
) -> dict[str, Any]:
    requested_slot_bound = slot.get("binding_status") == "bound"
    slot_catalog_revalidated = session.get("slot_catalog_revalidated") is True
    slot_model_server_issued = slot.get("server_issued") is True
    slot_lane_revalidated = (
        slot_catalog_revalidated and slot.get("model_lane_classified") is True
    )
    slot_source_revalidated = (
        slot_catalog_revalidated and _slot_source_candidate_classified(slot, session)
    )
    return {
        "requested_slot_bound": requested_slot_bound,
        "slot_catalog_revalidated": slot_catalog_revalidated,
        "slot_model_server_issued": slot_model_server_issued,
        "slot_lane_revalidated": slot_lane_revalidated,
        "slot_source_revalidated": slot_source_revalidated,
        "slot_admission_passed": bool(
            requested_slot_id in ROLE_SLOT_IDS
            and requested_slot_bound
            and slot_model_server_issued
            and slot_lane_revalidated
            and slot_source_revalidated
        ),
    }


def _runner_slot_echo(result: dict[str, Any]) -> str:
    for key in ("requested_slot_id", "slot_id"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    return ""


def _selection_packet_from_bound_slot(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "selection_dry_run_proven": slot.get("selection_dry_run_proven") is True,
        "live_selection_proven": slot.get("live_selection_proven") is True,
        "selection_proven": slot.get("selection_proven") is True,
        "model_catalog_entry_server_issued": slot.get("model_catalog_entry_server_issued")
        is True,
        "model_lane": str(slot.get("model_lane") or "unknown_lane"),
        "model_lane_classified": slot.get("model_lane_classified") is True,
        "model_lane_classification_source": str(
            slot.get("model_lane_classification_source") or "none"
        ),
        "model_lane_fallback_used": slot.get("model_lane_fallback_used") is True,
        "model_lane_proof_level": str(slot.get("model_lane_proof_level") or "unclassified"),
        "runtime_lane_proven": slot.get("runtime_lane_proven") is True,
        "selected_source_class": str(slot.get("selected_source_class") or "none"),
        "selected_backend_ref": str(slot.get("selected_backend_ref") or ""),
        "selected_backend_server_issued": slot.get("selected_backend_server_issued") is True,
        "selected_route_ref": str(slot.get("selected_route_ref") or ""),
        "selected_route_server_issued": slot.get("selected_route_server_issued") is True,
        "route_provenance_required": slot.get("route_provenance_required") is True,
        "route_provenance_proven": slot.get("route_provenance_proven") is True,
        "source_provenance_status": str(slot.get("source_provenance_status") or "not_proven"),
        "source_candidate_classified": slot.get("selection_proven") is True,
        "source_provenance_proven": False,
        "api_model_selected_by_user": slot.get("api_model_selected_by_user") is True,
        "route_selected_by_user": slot.get("route_selected_by_user") is True,
        "browser_selected_route": slot.get("browser_selected_route") is True,
        "route_candidate_source": str(slot.get("route_candidate_source") or "none"),
        "route_candidate_classified": slot.get("route_candidate_classified") is True,
        "route_static_readiness_classified": slot.get("route_static_readiness_classified") is True,
        "route_execution_proven": False,
        "provider_response_proven": False,
        "secret_validity_proven": False,
        "raw_route_exposed": False,
        "raw_secret_ref_exposed": False,
        "browser_selected_backend": False,
        "model_selected_by_user": slot.get("model_selected_by_user") is True,
        "role_slot_selected_by_user": slot.get("role_slot_selected_by_user") is True,
        "account_selected_by_user": slot.get("account_selected_by_user") is True,
        "account_candidate_source": str(slot.get("account_candidate_source") or "none"),
        "account_execution_proven": False,
        "runtime_execution_proven": False,
        "live_compatibility_proven": False,
        "raw_backend_exposed": False,
        "raw_backend_id_exposed": False,
        "machine_error_code": "OK" if slot.get("selection_proven") is True else "SELECTION_NOT_PROVEN",
    }


def _external_route_selection_packet(model_id: str, api_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    routes = api_snapshot.get("routes") if isinstance(api_snapshot, dict) else []
    route = None
    if isinstance(routes, list):
        for item in routes:
            if isinstance(item, dict) and str(item.get("route_id") or "").strip() == model_id:
                route = item
                break
    if not isinstance(route, dict):
        return {
            "selection_dry_run_proven": False,
            "live_selection_proven": False,
            "selection_proven": False,
            "selected_source_class": "none",
            "selected_backend_ref": "",
            "selected_backend_server_issued": False,
            "selected_route_ref": "",
            "selected_route_server_issued": False,
            "route_provenance_required": False,
            "route_provenance_proven": False,
            "source_provenance_status": "not_proven",
            "api_model_selected_by_user": True,
            "route_selected_by_user": False,
            "browser_selected_route": False,
            "route_candidate_source": "none",
            "route_candidate_classified": False,
            "route_static_readiness_classified": False,
            "route_execution_proven": False,
            "provider_response_proven": False,
            "secret_validity_proven": False,
            "raw_route_exposed": False,
            "raw_secret_ref_exposed": False,
            "model_selected_by_user": True,
            "role_slot_selected_by_user": True,
            "account_selected_by_user": False,
            "browser_selected_backend": False,
            "account_candidate_source": "none",
            "account_execution_proven": False,
            "runtime_execution_proven": False,
            "live_compatibility_proven": False,
            "raw_backend_exposed": False,
            "raw_backend_id_exposed": False,
            "machine_error_code": "EXTERNAL_API_ROUTE_NOT_VISIBLE",
        }
    route_id = str(route.get("route_id") or "").strip()
    secret_ref = str(route.get("secret_ref") or "").strip()
    enabled = route.get("enabled") is True
    ready = enabled and bool(secret_ref)
    return {
        "selection_dry_run_proven": ready,
        "live_selection_proven": False,
        "selection_proven": ready,
        "selected_source_class": "route_backed" if ready else "none",
        "selected_backend_ref": "",
        "selected_backend_server_issued": False,
        "selected_route_ref": _digest(route_id) if route_id else "",
        "selected_route_server_issued": ready,
        "route_provenance_required": ready,
        "route_provenance_proven": False,
        "source_provenance_status": (
            ROUTE_CANDIDATE_PROVENANCE_STATUS if ready else "route_static_candidate_missing"
        ),
        "api_model_selected_by_user": True,
        "route_selected_by_user": False,
        "browser_selected_route": False,
        "route_candidate_source": ROUTE_CANDIDATE_SOURCE if route_id else "none",
        "route_candidate_classified": bool(route_id),
        "route_static_readiness_classified": ready,
        "route_execution_proven": False,
        "provider_response_proven": False,
        "secret_validity_proven": False,
        "raw_route_exposed": False,
        "raw_secret_ref_exposed": False,
        "model_selected_by_user": True,
        "role_slot_selected_by_user": True,
        "account_selected_by_user": False,
        "browser_selected_backend": False,
        "account_candidate_source": "none",
        "account_execution_proven": False,
        "runtime_execution_proven": False,
        "live_compatibility_proven": False,
        "raw_backend_exposed": False,
        "raw_backend_id_exposed": False,
        "machine_error_code": "OK" if ready else "EXTERNAL_API_ROUTE_NOT_READY",
    }


def _selection_packet_for_slot(
    model_id: str,
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    lane_classification = model_lane_classification_from_registry(model_id, registry)
    if (
        lane_classification.get("model_lane_classified") is not True
        or lane_classification.get("model_lane_fallback_used") is True
    ):
        heuristic_only = lane_classification.get("heuristic_only_not_executable") is True
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": (
                "HEURISTIC_ONLY_NOT_EXECUTABLE"
                if heuristic_only
                else "UNCLASSIFIED_MODEL_ID"
            ),
            "selection_proven": False,
            "selection_dry_run_proven": False,
            "live_selection_proven": False,
            "selected_source_class": "none",
            "source_provenance_status": "not_proven",
            **lane_classification,
        }
    model_lane = str(lane_classification.get("model_lane") or "")
    if model_lane == CODEX_ACCOUNT_MODEL_LANE:
        return build_account_selection_packet(commands, operator_status) | lane_classification
    if model_lane == API_ROUTE_MODEL_LANE:
        return _external_route_selection_packet(model_id, api_snapshot) | lane_classification
    return {
        "schema_version": 1,
        "status": "rejected",
        "machine_error_code": "MODEL_LANE_NOT_CLASSIFIED",
        "selection_proven": False,
        "selection_dry_run_proven": False,
        "live_selection_proven": False,
        "selected_source_class": "none",
        "source_provenance_status": "not_proven",
        **lane_classification,
    }


class CodexCustomSessionManager:
    def __init__(self, root: Path | None = None) -> None:
        base = root or Path(tempfile.gettempdir()) / "wbp-codex-custom-sessions"
        self.root = base.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._product_worktrees: dict[str, dict[str, Any]] = {}
        self._active_prompt_sessions: set[str] = set()
        self._active_prompt_lock = threading.Lock()
        self._load_existing_sessions()

    def list_packet(self) -> dict[str, Any]:
        sessions = [self._public_session(session) for session in self._sessions.values()]
        return {
            "schema_version": 1,
            "status": "ok",
            "machine_error_code": "OK",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "session_schema_version": SESSION_SCHEMA_VERSION,
            "session_count": len(sessions),
            "sessions": sessions,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
        }

    def create_packet(
        self,
        payload: dict[str, Any],
        commands: dict[str, dict[str, Any]],
        operator_status: dict[str, Any] | None,
        *,
        selection: dict[str, Any] | None = None,
        api_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        forbidden = forbidden_session_create_fields(payload)
        if forbidden:
            return self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden)
        slot_model_ids = _slot_model_ids_from_payload(payload)
        primary_model_id = slot_model_ids.get(PRIMARY_MODEL_SLOT, "")
        if not primary_model_id:
            return {
                **self._base_packet("rejected", "MANUAL_MODEL_SELECTION_REQUIRED"),
                "human_message": "Codex Custom session creation requires an explicit server-issued model selection.",
                "session_created": False,
                "model_auto_selected": False,
                "fallback_used": False,
                "external_route_selected": False,
                "required_choice_fields": _required_choice_fields(),
                "next_action": "select_model_from_server_registry",
            }
        model_ids = _model_ids(operator_status, api_snapshot)
        if not primary_model_id or primary_model_id not in model_ids:
            return {
                **self._base_packet("rejected", "MODEL_NOT_SERVER_ISSUED"),
                "human_message": "Session create accepts only server-issued model_id.",
                "model_server_issued": False,
                "session_created": False,
                "model_auto_selected": False,
                "fallback_used": False,
                "external_route_selected": False,
                "next_action": "select_model_from_server_registry",
            }
        slot_bindings, slot_error = self._slot_bindings_from_payload(
            slot_model_ids,
            commands,
            operator_status,
            api_snapshot=api_snapshot,
        )
        if slot_error is not None:
            return slot_error
        primary_slot = slot_bindings[PRIMARY_MODEL_SLOT]
        selection = _selection_packet_from_bound_slot(primary_slot)
        if selection.get("selection_proven") is not True:
            return {
                **self._base_packet(
                    "rejected",
                    str(selection.get("machine_error_code") or "SELECTION_NOT_PROVEN"),
                ),
                "human_message": "Codex Custom session requires server-issued account selection proof.",
                "model_id": primary_model_id,
                "model_server_issued": True,
                "selection_proven": False,
                "selection_packet": self._selection_summary(selection),
                "session_created": False,
                "next_action": "repair_account_selection_truth",
            }
        session_id = f"ccs-{uuid.uuid4().hex[:20]}"
        session_root = (self.root / session_id).resolve()
        if not self._is_owned_session_path(session_root):
            return {
                **self._base_packet("failed", "SESSION_ROOT_OUTSIDE_APPROVED_ROOT"),
                "next_action": "stop_and_diagnose",
            }
        codex_home = session_root / "codex-home"
        workdir = session_root / "workdir"
        codex_home.mkdir(mode=0o700, parents=True, exist_ok=False)
        workdir.mkdir(mode=0o700, parents=True, exist_ok=False)
        now = utc_now()
        session = {
            "session_id": session_id,
            "created_at_utc": now,
            "updated_at_utc": now,
            "status": "ready",
            "session_schema_version": SESSION_SCHEMA_VERSION,
            "migration_status": "native_multi_slot_schema",
            "legacy_single_model_migrated": False,
            "role_slots": _canonical_role_slots(slot_bindings),
            "current_execution_slot_id": PRIMARY_MODEL_SLOT,
            "current_execution_path_source": "session_primary_model_slot",
            "model_id": primary_model_id,
            "model_server_issued": True,
            "model_catalog_entry_server_issued": selection.get("model_catalog_entry_server_issued")
            is True,
            "model_lane": str(selection.get("model_lane") or "unknown_lane"),
            "model_lane_classified": selection.get("model_lane_classified") is True,
            "model_lane_classification_source": str(
                selection.get("model_lane_classification_source") or "none"
            ),
            "model_lane_fallback_used": selection.get("model_lane_fallback_used") is True,
            "model_lane_proof_level": str(selection.get("model_lane_proof_level") or "unclassified"),
            "runtime_lane_proven": False,
            "role_slot_binding_proven": True,
            "slot_catalog_revalidated": True,
            "slot_binding_runtime_dispatch_claimed": False,
            "selected_source_class": selection.get("selected_source_class"),
            "selected_backend_ref": selection.get("selected_backend_ref"),
            "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
            "selected_route_ref": selection.get("selected_route_ref"),
            "selected_route_server_issued": selection.get("selected_route_server_issued") is True,
            "route_provenance_required": selection.get("route_provenance_required") is True,
            "route_provenance_proven": selection.get("route_provenance_proven") is True,
            "api_model_selected_by_user": selection.get("api_model_selected_by_user") is True,
            "route_selected_by_user": selection.get("route_selected_by_user") is True,
            "browser_selected_route": selection.get("browser_selected_route") is True,
            "route_candidate_source": str(selection.get("route_candidate_source") or "none"),
            "route_candidate_classified": selection.get("route_candidate_classified") is True,
            "route_static_readiness_classified": selection.get("route_static_readiness_classified")
            is True,
            "route_execution_proven": False,
            "provider_response_proven": False,
            "secret_validity_proven": False,
            "raw_route_exposed": False,
            "raw_secret_ref_exposed": False,
            "source_provenance_status": str(selection.get("source_provenance_status") or "not_proven"),
            "model_selected_by_user": selection.get("model_selected_by_user") is True,
            "role_slot_selected_by_user": selection.get("role_slot_selected_by_user") is True,
            "account_selected_by_user": selection.get("account_selected_by_user") is True,
            "browser_selected_backend": selection.get("browser_selected_backend") is True,
            "account_candidate_source": str(selection.get("account_candidate_source") or "none"),
            "account_execution_proven": False,
            "runtime_execution_proven": False,
            "live_compatibility_proven": False,
            "raw_backend_exposed": False,
            "raw_backend_id_exposed": False,
            "selection_dry_run_proven": selection.get("selection_dry_run_proven") is True,
            "live_selection_proven": selection.get("live_selection_proven") is True,
            "selection_proven": selection.get("selection_proven") is True,
            "selection_machine_error_code": selection.get("machine_error_code"),
            "session_root": str(session_root),
            "codex_home": str(codex_home),
            "workdir": str(workdir),
            "ledger": [],
            "prompt_admission_count": 0,
            "cleanup_state": "not_cleaned",
            "cancel_state": "not_cancelled",
        }
        self._append_ledger(session, "session_created")
        self._sessions[session_id] = session
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "human_message": "Codex Custom session created.",
            "session_created": True,
            "live_prompt_admitted": False,
            "current_codex_home_used": False,
            "selected_backend_id_redacted": True,
            "current_execution_slot_id": PRIMARY_MODEL_SLOT,
            "current_execution_path_model_id": primary_model_id,
            "current_execution_path_source": "session_primary_model_slot",
            "session": self._public_session(session),
            "selection_packet": self._selection_summary(selection),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "prompt_dry_run",
        }

    def get_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        return {
            **self._base_packet("ok", "OK"),
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "none",
        }

    def revalidate_packet(
        self,
        session_id: str,
        commands: dict[str, dict[str, Any]],
        operator_status: dict[str, Any] | None,
        *,
        api_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        if session.get("cleanup_state") == "cleaned":
            return {
                **self._base_packet("rejected", "SESSION_ALREADY_CLEANED"),
                "session_id": session_id,
                "slot_catalog_revalidated": False,
                "revalidated_bound_slot_count": 0,
                "next_action": "create_session",
            }
        role_slots = _canonical_role_slots(session.get("role_slots"))
        selector_index = _selector_entry_index(operator_status, api_snapshot=api_snapshot)
        slot_rows: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        backend_identity_matches: list[bool] = []
        for slot_id in ROLE_SLOT_IDS:
            slot = dict(role_slots.get(slot_id) or _unbound_slot(slot_id))
            if slot.get("binding_status") != "bound":
                continue
            model_id = str(slot.get("model_id") or "")
            entry = selector_index.get(model_id)
            if entry is None:
                failures.append(
                    {
                        "slot_id": slot_id,
                        "model_id": model_id,
                        "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
                    }
                )
                continue
            if entry.get("selection_enabled") is not True:
                failures.append(
                    {
                        "slot_id": slot_id,
                        "model_id": model_id,
                        "machine_error_code": "MODEL_NOT_SELECTABLE",
                    }
                )
                continue
            selection = _selection_packet_for_slot(
                model_id,
                commands,
                operator_status,
                api_snapshot,
            )
            source_class_matches_saved = str(selection.get("selected_source_class") or "") == str(
                slot.get("selected_source_class") or ""
            )
            lane_kind_matches_saved = str(entry.get("lane_kind") or "unknown") == str(
                slot.get("lane_kind") or "unknown"
            )
            route_required = slot.get("route_provenance_required") is True
            route_digest_matches_saved = str(selection.get("selected_route_ref") or "") == str(
                slot.get("selected_route_ref") or ""
            )
            backend_digest_matches_saved = str(selection.get("selected_backend_ref") or "") == str(
                slot.get("selected_backend_ref") or ""
            )
            if slot.get("selected_source_class") == "gpt_account":
                backend_identity_matches.append(backend_digest_matches_saved)
            slot_row = {
                "slot_id": slot_id,
                "model_id": model_id,
                "persisted_lane_kind": str(slot.get("lane_kind") or "unknown"),
                "current_lane_kind": str(entry.get("lane_kind") or "unknown"),
                "lane_kind_matches_saved": lane_kind_matches_saved,
                "persisted_selected_source_class": str(slot.get("selected_source_class") or "none"),
                "current_selected_source_class": str(
                    selection.get("selected_source_class") or "none"
                ),
                "source_class_matches_saved": source_class_matches_saved,
                "persisted_selected_backend_digest": str(slot.get("selected_backend_ref") or ""),
                "current_selected_backend_digest": str(selection.get("selected_backend_ref") or ""),
                "backend_digest_matches_saved": backend_digest_matches_saved,
                "persisted_selected_route_digest": str(slot.get("selected_route_ref") or ""),
                "current_selected_route_digest": str(selection.get("selected_route_ref") or ""),
                "route_digest_matches_saved": route_digest_matches_saved,
                "selection_proven": selection.get("selection_proven") is True,
                "selected_backend_server_issued": selection.get("selected_backend_server_issued")
                is True,
                "selected_route_server_issued": selection.get("selected_route_server_issued")
                is True,
                "route_provenance_required": selection.get("route_provenance_required") is True,
                "route_provenance_proven": selection.get("route_provenance_proven") is True,
                "route_candidate_classified": selection.get("route_candidate_classified") is True,
                "route_static_readiness_classified": selection.get("route_static_readiness_classified")
                is True,
                "machine_error_code": str(selection.get("machine_error_code") or "OK"),
            }
            slot_rows.append(slot_row)
            if selection.get("selection_proven") is not True:
                failures.append(
                    {
                        "slot_id": slot_id,
                        "model_id": model_id,
                        "machine_error_code": str(
                            selection.get("machine_error_code") or "SELECTION_NOT_PROVEN"
                        ),
                    }
                )
                continue
            if not lane_kind_matches_saved:
                failures.append(
                    {
                        "slot_id": slot_id,
                        "model_id": model_id,
                        "machine_error_code": "LANE_KIND_MISMATCH_AFTER_RELOAD",
                    }
                )
                continue
            if not source_class_matches_saved:
                failures.append(
                    {
                        "slot_id": slot_id,
                        "model_id": model_id,
                        "machine_error_code": "SOURCE_CLASS_MISMATCH_AFTER_RELOAD",
                    }
                )
                continue
            if route_required:
                if selection.get("selected_route_server_issued") is not True:
                    failures.append(
                        {
                            "slot_id": slot_id,
                            "model_id": model_id,
                            "machine_error_code": "ROUTE_NOT_SERVER_ISSUED",
                        }
                    )
                    continue
                if selection.get("route_static_readiness_classified") is not True:
                    failures.append(
                        {
                            "slot_id": slot_id,
                            "model_id": model_id,
                            "machine_error_code": "ROUTE_STATIC_READINESS_MISSING",
                        }
                    )
                    continue
                if not route_digest_matches_saved:
                    failures.append(
                        {
                            "slot_id": slot_id,
                            "model_id": model_id,
                            "machine_error_code": "ROUTE_IDENTITY_MISMATCH_AFTER_RELOAD",
                        }
                    )
                    continue
            elif selection.get("selected_backend_server_issued") is not True:
                failures.append(
                    {
                        "slot_id": slot_id,
                        "model_id": model_id,
                        "machine_error_code": "BACKEND_NOT_SERVER_ISSUED",
                    }
                )
                continue

        if failures:
            return {
                **self._base_packet("blocked", str(failures[0]["machine_error_code"])),
                "session_id": session_id,
                "slot_catalog_revalidated": False,
                "revalidated_bound_slot_count": len(slot_rows),
                "role_slot_rows": slot_rows,
                "revalidation_failures": failures,
                "provider_model_identity_persistence_proven": False,
                "same_provider_account_selection_proven": False,
                "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven": False,
                "counts_as_runtime_dispatch_proof": False,
                "session": self._public_session(session),
                "role_slot_binding_packet": self._role_slot_binding_packet(session),
                "next_action": "repair_session_preconditions",
            }

        session["slot_catalog_revalidated"] = True
        session["updated_at_utc"] = utc_now()
        self._append_ledger(
            session,
            "slot_catalog_revalidated",
            {
                "revalidated_bound_slot_count": len(slot_rows),
                "role_slot_rows": slot_rows,
                "provider_model_identity_persistence_proven": True,
                "same_provider_account_selection_proven": all(backend_identity_matches)
                if backend_identity_matches
                else False,
                "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven": True,
                "counts_as_runtime_dispatch_proof": False,
            },
        )
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "slot_catalog_revalidated": True,
            "revalidated_bound_slot_count": len(slot_rows),
            "role_slot_rows": slot_rows,
            "revalidation_failures": [],
            "provider_model_identity_persistence_proven": True,
            "same_provider_account_selection_proven": all(backend_identity_matches)
            if backend_identity_matches
            else False,
            "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven": True,
            "counts_as_runtime_dispatch_proof": False,
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "prompt",
        }

    def prompt_dry_run_packet(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        if session.get("cleanup_state") == "cleaned":
            return {
                **self._base_packet("rejected", "SESSION_ALREADY_CLEANED"),
                "session_id": session_id,
                "next_action": "create_session",
            }
        forbidden = forbidden_prompt_dry_run_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
            }
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return {
                **self._base_packet("rejected", "PROMPT_MISSING"),
                "session_id": session_id,
                "prompt_present": False,
                "next_action": "enter_prompt",
            }
        prompt_hash = _digest(prompt)
        prompt_entry = {
            "event": "prompt_admitted_dry_run",
            "prompt_present": True,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "prompt_preview_redacted": _safe_preview(prompt),
            "raw_prompt_not_stored": True,
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
        }
        session["prompt_admission_count"] = int(session.get("prompt_admission_count") or 0) + 1
        session["status"] = "prompt_admitted_dry_run"
        session["updated_at_utc"] = utc_now()
        self._append_ledger(session, "prompt_admitted_dry_run", prompt_entry)
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "dry_run": True,
            "prompt_admitted": True,
            "prompt_present": True,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "prompt_preview_redacted": _safe_preview(prompt),
            "raw_prompt_not_stored": True,
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
            "negative_claim_basis": "prompt_admission_dry_run_no_inference_adapter",
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "codex_custom_gpt_api_e2e_pass",
        }

    def prompt_not_admitted_packet(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_prompt_run_fields(payload)
        packet = {
            **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
            "human_message": "Live Codex Custom prompt requires exact owner authorization in the active thread.",
            "session_id": session_id,
            "authorization_status": "blocked_by_operator_authorization",
            "owner_authorization_phrase_present": False,
            "live_prompt_admitted": False,
            "live_prompt_executed": False,
            "prompt_runner_called": False,
            "raw_prompt_not_stored": True,
            "inference_proven": False,
            "model_response_present": False,
            "network_calls_made": False,
            "provider_called": False,
            "fallback_attempted": False,
            "token_burn": 0,
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "provide_exact_owner_authorization_phrase",
        }
        if forbidden:
            packet["status"] = "rejected"
            packet["machine_error_code"] = "FORBIDDEN_BROWSER_FIELD"
            packet["forbidden_fields"] = forbidden
            packet["next_action"] = "remove_forbidden_browser_fields"
        return packet

    def prompt_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        owner_authorized: bool = False,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_prompt_run_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "model_response_present": False,
                "fallback_attempted": False,
            }
        requested_slot_id = _slot_id_from_prompt_payload(payload)
        if requested_slot_id is None:
            return {
                **self._base_packet("rejected", "SLOT_ID_NOT_SERVER_ISSUED"),
                "session_id": session_id,
                "model_response_present": False,
                "fallback_attempted": False,
                "next_action": "choose_server_issued_slot_id",
            }
        precondition_failure = self._prompt_precondition_failure(session, requested_slot_id)
        if precondition_failure:
            return precondition_failure
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return {
                **self._base_packet("rejected", "PROMPT_MISSING"),
                "session_id": session_id,
                "prompt_present": False,
                "model_response_present": False,
                "fallback_attempted": False,
                "next_action": "enter_prompt",
            }
        if not owner_authorized:
            not_admitted_payload: dict[str, Any] = {"prompt": prompt}
            if payload.get("slot_id") is not None:
                not_admitted_payload["slot_id"] = payload.get("slot_id")
            return self.prompt_not_admitted_packet(session_id, not_admitted_payload)
        prompt_hash = _digest(prompt)
        role_slots = _canonical_role_slots(session.get("role_slots"))
        slot = dict(role_slots.get(requested_slot_id) or _unbound_slot(requested_slot_id))
        model_id = str(slot.get("model_id") or "")
        requested_slot_explicit = payload.get("slot_id") is not None
        requested_slot_defaulted_to_primary = (
            not requested_slot_explicit and requested_slot_id == PRIMARY_MODEL_SLOT
        )
        slot_dispatch_admission = _slot_dispatch_admission_packet(
            session=session,
            slot=slot,
            requested_slot_id=requested_slot_id,
        )
        runner_payload = {
            "prompt": prompt,
            "model_id": model_id,
            "slot_id": requested_slot_id,
        }
        if not requested_slot_explicit:
            runner_payload["slot_id_explicit"] = False
        wbp_runner_payload_slot_id = str(runner_payload.get("slot_id") or "")
        wbp_runner_payload_model_id = str(runner_payload.get("model_id") or "")
        wbp_runner_payload_slot_matches_requested = (
            wbp_runner_payload_slot_id == requested_slot_id
        )
        wbp_runner_payload_model_matches_slot = wbp_runner_payload_model_id == model_id
        wbp_session_manager_slot_dispatch_proven = bool(
            slot_dispatch_admission["slot_admission_passed"]
            and wbp_runner_payload_slot_matches_requested
            and wbp_runner_payload_model_matches_slot
        )
        with self._active_prompt_lock:
            if session_id in self._active_prompt_sessions:
                return {
                    **self._base_packet("blocked", "CONCURRENT_PROMPT_EXECUTION_NOT_ALLOWED"),
                    "session_id": session_id,
                    "current_execution_slot_id": requested_slot_id,
                    "requested_slot_id": requested_slot_id,
                    "requested_slot_explicit": requested_slot_explicit,
                    "requested_slot_defaulted_to_primary": requested_slot_defaulted_to_primary,
                    **slot_dispatch_admission,
                    "wbp_runner_payload_slot_id": "",
                    "wbp_runner_payload_model_id": "",
                    "wbp_runner_payload_slot_matches_requested": False,
                    "wbp_runner_payload_model_matches_slot": False,
                    "wbp_session_manager_slot_dispatch_proven": False,
                    "runtime_slot_dispatch_proof_scope": "not_attempted_concurrent_session_lock",
                    "downstream_runner_slot_echo_present": False,
                    "downstream_runner_slot_echo": "",
                    "downstream_runner_slot_echo_matches_requested": False,
                    "executed_slot_id": "",
                    "executed_slot_model_id": "",
                    "runtime_slot_dispatch_proven": False,
                    "slot_binding_runtime_dispatch_claimed": False,
                    "parallel_slot_execution_proven": False,
                    "fanout_execution_proven": False,
                    "authorization_status": "authorized_by_owner_gate",
                    "owner_authorization_phrase_present": True,
                    "prompt_runner_called": False,
                    "model_response_present": False,
                    "fallback_attempted": False,
                    "token_usage_present": False,
                    "next_action": "wait_for_current_prompt_completion",
                    "session": self._public_session(session),
                    "role_slot_binding_packet": self._role_slot_binding_packet(session),
                }
            self._active_prompt_sessions.add(session_id)
        try:
            result = prompt_runner(runner_payload)
        except Exception as exc:  # pragma: no cover - defensive live boundary
            result = {
                "status": "failed",
                "machine_error_code": "PROMPT_RUNNER_EXCEPTION",
                "error_class": type(exc).__name__,
                "human_message": "Codex Custom prompt runner failed before returning a packet.",
            }
        finally:
            with self._active_prompt_lock:
                self._active_prompt_sessions.discard(session_id)
        response_text = str(result.get("final_message") or result.get("response_text") or "")
        runner_slot_id_text = _runner_slot_echo(result)
        downstream_runner_slot_echo_present = bool(runner_slot_id_text)
        downstream_runner_slot_echo_matches_requested = (
            downstream_runner_slot_echo_present and runner_slot_id_text == requested_slot_id
        )
        runtime_slot_dispatch_proven = bool(
            wbp_session_manager_slot_dispatch_proven
            and downstream_runner_slot_echo_matches_requested
        )
        response_digest = _digest(response_text) if response_text else ""
        token_usage_present, token_usage, token_burn = _token_usage(result)
        secret_value_recorded = result.get("secret_value_recorded") is True
        status_ok = result.get("status") == "ok" and bool(response_text) and not secret_value_recorded
        isolated_engine_home_proven = (
            result.get("env_codex_home_is_temp") is True
            and result.get("env_home_is_temp") is True
            and result.get("workdir_is_temp") is True
            and result.get("command_workdir_is_temp") is True
            and result.get("command_output_file_is_temp") is True
            and result.get("current_codex_home_used") is False
        )
        route_backed_source = slot.get("selected_source_class") == "route_backed"
        allowed_providers = {"external_route", "wbp"} if route_backed_source else {"cliproxy", "wbp"}
        allowed_wire_apis = {"responses", "chat_completions"} if route_backed_source else {"responses"}
        path_config_proven = (
            result.get("configured_provider") in allowed_providers
            and result.get("configured_wire_api") in allowed_wire_apis
            and result.get("wbp_endpoint_configured") is True
            and result.get("config_endpoint_matches") is True
            and result.get("config_provider_matches") is True
            and result.get("config_wire_api_matches") is True
            and result.get("command_uses_stdin_dash") is True
            and result.get("command_json_mode") is True
        )
        independent_wbp_trace_observed = result.get("independent_wbp_trace_observed") is True
        raw_trace_observer_packet = result.get("trace_observer_packet") if isinstance(result.get("trace_observer_packet"), dict) else {}
        trace_observer_packet = _safe_trace_observer_packet(raw_trace_observer_packet)
        raw_process_network_observation = (
            result.get("process_network_observation_packet")
            if isinstance(result.get("process_network_observation_packet"), dict)
            else {}
        )
        process_network_observation_packet = _safe_process_network_observation_packet(
            raw_process_network_observation
        )
        trace_path = str(trace_observer_packet.get("path") or "")
        upstream_status = trace_observer_packet.get("upstream_status")
        forwarded_to_wbp = trace_observer_packet.get("forwarded_to_wbp") is True
        wbp_path_configured = status_ok and path_config_proven
        wbp_path_proven = wbp_path_configured and independent_wbp_trace_observed
        source_provenance_status = _slot_source_provenance_status(slot, session)
        source_candidate_classified = _slot_source_candidate_classified(slot, session)
        cli_proxy_api_path_configured = (
            wbp_path_configured and result.get("configured_provider") == "cliproxy"
        )
        cli_proxy_api_path_proven = (
            wbp_path_proven and result.get("configured_provider") == "cliproxy"
        )
        runtime_selected_model = str(
            result.get("runtime_model") or result.get("selected_model") or ""
        )
        runtime_selected_model_recorded = bool(runtime_selected_model)
        runtime_selected_model_matches_bound_model = (
            runtime_selected_model == model_id if runtime_selected_model_recorded else False
        )
        trace_missing_after_response = status_ok and not independent_wbp_trace_observed
        path_config_mismatch_after_response = (
            status_ok and independent_wbp_trace_observed and not path_config_proven
        )
        runtime_model_mismatch_after_response = (
            status_ok and runtime_selected_model_recorded and not runtime_selected_model_matches_bound_model
        )
        route_provenance_missing_after_response = status_ok and wbp_path_proven and not source_candidate_classified
        source_provenance_proven = status_ok and wbp_path_proven and source_candidate_classified
        live_source_provenance_status = (
            "backend_proven"
            if (
                source_provenance_proven
                and source_provenance_status == ACCOUNT_CANDIDATE_PROVENANCE_STATUS
            )
            else (
                "route_proven"
                if (
                    source_provenance_proven
                    and source_provenance_status == ROUTE_CANDIDATE_PROVENANCE_STATUS
                )
                else source_provenance_status
            )
        )
        current_codex_touched_after_response = status_ok and result.get("current_codex_home_used") is True
        isolation_missing_after_response = (
            status_ok and not current_codex_touched_after_response and not isolated_engine_home_proven
        )
        packet_status = (
            "ok"
            if (
                status_ok
                and wbp_path_proven
                and source_provenance_proven
                and isolated_engine_home_proven
                and not runtime_model_mismatch_after_response
            )
            else (
                "blocked"
                if trace_missing_after_response
                or path_config_mismatch_after_response
                or runtime_model_mismatch_after_response
                or route_provenance_missing_after_response
                or current_codex_touched_after_response
                or isolation_missing_after_response
                else str(result.get("status") or "failed")
            )
        )
        packet_machine_error_code = (
            "OK"
            if (
                status_ok
                and wbp_path_proven
                and source_provenance_proven
                and isolated_engine_home_proven
                and not runtime_model_mismatch_after_response
            )
            else (
                "WBP_TRACE_PROOF_MISSING"
                if trace_missing_after_response
                else (
                    "RUNTIME_SOURCE_PROVENANCE_MISMATCH"
                    if path_config_mismatch_after_response
                    else (
                        "RUNTIME_MODEL_ID_MISMATCH"
                        if runtime_model_mismatch_after_response
                        else (
                            "CURRENT_CODEX_TOUCHED"
                            if current_codex_touched_after_response
                            else (
                                "ISOLATION_PROOF_MISSING"
                                if isolation_missing_after_response
                                else (
                                    "ROUTE_PROVENANCE_MISSING"
                                    if route_provenance_missing_after_response
                                    else str(result.get("machine_error_code") or "ENGINE_PROMPT_FAILED")
                                )
                            )
                        )
                    )
                )
            )
        )
        latency_ms = None
        duration_seconds = result.get("duration_seconds")
        if isinstance(duration_seconds, (int, float)):
            latency_ms = int(float(duration_seconds) * 1000)
        packet = {
            "schema_version": 1,
            "status": packet_status,
            "machine_error_code": packet_machine_error_code,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "session_id": session_id,
            "session_schema_version": int(session.get("session_schema_version") or SESSION_SCHEMA_VERSION),
            "current_execution_slot_id": requested_slot_id,
            "requested_slot_id": requested_slot_id,
            "requested_slot_explicit": requested_slot_explicit,
            "requested_slot_defaulted_to_primary": requested_slot_defaulted_to_primary,
            **slot_dispatch_admission,
            "wbp_runner_payload_slot_id": wbp_runner_payload_slot_id,
            "wbp_runner_payload_model_id": wbp_runner_payload_model_id,
            "wbp_runner_payload_slot_matches_requested": (
                wbp_runner_payload_slot_matches_requested
            ),
            "wbp_runner_payload_model_matches_slot": (
                wbp_runner_payload_model_matches_slot
            ),
            "wbp_session_manager_slot_dispatch_proven": (
                wbp_session_manager_slot_dispatch_proven
            ),
            "runtime_slot_dispatch_proof_scope": "wbp_session_manager_payload_plus_downstream_echo",
            "downstream_runner_slot_echo_present": downstream_runner_slot_echo_present,
            "downstream_runner_slot_echo": runner_slot_id_text,
            "downstream_runner_slot_echo_matches_requested": (
                downstream_runner_slot_echo_matches_requested
            ),
            "executed_slot_id": requested_slot_id,
            "executed_slot_model_id": model_id,
            "runtime_slot_dispatch_proven": runtime_slot_dispatch_proven,
            "runner_slot_id_echo": runner_slot_id_text,
            "runner_slot_id_matches_requested": downstream_runner_slot_echo_matches_requested,
            "current_execution_path_source": "session_bound_slot_runtime",
            "model_id": model_id,
            "model_server_issued": True,
            "model_catalog_entry_server_issued": slot.get("model_catalog_entry_server_issued")
            is True,
            "model_lane": str(slot.get("model_lane") or "unknown_lane"),
            "model_lane_classified": slot.get("model_lane_classified") is True,
            "model_lane_classification_source": str(
                slot.get("model_lane_classification_source") or "none"
            ),
            "model_lane_fallback_used": slot.get("model_lane_fallback_used") is True,
            "model_lane_proof_level": str(slot.get("model_lane_proof_level") or "unclassified"),
            "runtime_lane_proven": bool(
                status_ok
                and wbp_path_proven
                and source_provenance_proven
                and not runtime_model_mismatch_after_response
            ),
            "role_slot_binding_proven": session.get("role_slot_binding_proven") is True,
            "slot_binding_runtime_dispatch_claimed": runtime_slot_dispatch_proven,
            "parallel_slot_execution_proven": False,
            "fanout_execution_proven": False,
            "selected_source_class": slot.get("selected_source_class"),
            "selected_backend_digest": str(slot.get("selected_backend_ref") or ""),
            "selected_backend_server_issued": slot.get("selected_backend_server_issued") is True,
            "selected_route_digest": str(slot.get("selected_route_ref") or ""),
            "selected_route_server_issued": slot.get("selected_route_server_issued") is True,
            "route_provenance_required": slot.get("route_provenance_required") is True,
            "route_provenance_proven": bool(
                source_provenance_proven and slot.get("route_provenance_required") is True
            ),
            "api_model_selected_by_user": slot.get("api_model_selected_by_user") is True,
            "route_selected_by_user": slot.get("route_selected_by_user") is True,
            "browser_selected_route": slot.get("browser_selected_route") is True,
            "route_candidate_source": str(slot.get("route_candidate_source") or "none"),
            "route_candidate_classified": slot.get("route_candidate_classified") is True,
            "route_static_readiness_classified": slot.get("route_static_readiness_classified") is True,
            "route_execution_proven": bool(
                source_provenance_proven and slot.get("route_provenance_required") is True
            ),
            "provider_response_proven": bool(
                status_ok and slot.get("route_provenance_required") is True
            ),
            "secret_validity_proven": False,
            "source_provenance_status": live_source_provenance_status,
            "source_candidate_classified": source_candidate_classified,
            "source_provenance_proven": source_provenance_proven,
            "selected_source_provenance": live_source_provenance_status,
            "selection_dry_run_proven": slot.get("selection_dry_run_proven") is True,
            "live_selection_proven": slot.get("live_selection_proven") is True,
            "browser_selected_backend": False,
            "model_selected_by_user": slot.get("model_selected_by_user") is True,
            "role_slot_selected_by_user": slot.get("role_slot_selected_by_user") is True,
            "account_selected_by_user": slot.get("account_selected_by_user") is True,
            "account_candidate_source": str(slot.get("account_candidate_source") or "none"),
            "account_execution_proven": False,
            "runtime_execution_proven": status_ok,
            "live_compatibility_proven": bool(
                status_ok
                and wbp_path_proven
                and source_provenance_proven
                and isolated_engine_home_proven
                and not runtime_model_mismatch_after_response
            ),
            "authorization_status": "authorized_by_owner_gate",
            "owner_authorization_phrase_present": True,
            "live_prompt_admitted": True,
            "live_prompt_executed": status_ok,
            "prompt_runner_called": True,
            "prompt_present": True,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "prompt_preview_redacted": _safe_preview(prompt),
            "model_response_present": status_ok,
            "inference_proven": status_ok,
            "live_prompt_full_success": (
                status_ok
                and wbp_path_proven
                and source_provenance_proven
                and isolated_engine_home_proven
                and not runtime_model_mismatch_after_response
            ),
            "response_digest": response_digest,
            "response_preview_bounded": _response_preview(response_text) if status_ok else "",
            "token_usage_present": token_usage_present,
            "token_usage": token_usage,
            "token_burn": token_burn,
            "latency_ms": latency_ms,
            "error_class": "" if status_ok else str(result.get("error_class") or result.get("machine_error_code") or "unknown"),
            "wbp_path_configured": wbp_path_configured,
            "cli_proxy_api_path_configured": cli_proxy_api_path_configured,
            "wbp_path_observed": independent_wbp_trace_observed,
            "cli_proxy_api_path_observed": independent_wbp_trace_observed,
            "wbp_path_proven": wbp_path_proven,
            "cli_proxy_api_path_proven": cli_proxy_api_path_proven,
            "independent_wbp_trace_observed": independent_wbp_trace_observed,
            "trace_path": trace_path,
            "upstream_status": upstream_status if isinstance(upstream_status, int) else None,
            "forwarded_to_wbp": forwarded_to_wbp,
            "trace_observer_packet": trace_observer_packet,
            "process_network_observation_packet": process_network_observation_packet,
            "isolated_engine_home_proven": isolated_engine_home_proven,
            "current_codex_touched": result.get("current_codex_home_used") is True,
            "configured_provider": str(result.get("configured_provider") or "") if status_ok else "",
            "runtime_selected_model": runtime_selected_model if status_ok else "",
            "runtime_selected_model_recorded": runtime_selected_model_recorded,
            "runtime_selected_model_matches_bound_model": (
                runtime_selected_model_matches_bound_model
                if runtime_selected_model_recorded
                else False
            ),
            "configured_wire_api": result.get("configured_wire_api") if status_ok else "",
            "path_proof_status": (
                "runtime_model_mismatch_after_observation"
                if runtime_model_mismatch_after_response
                else (
                    "independently_observed"
                    if wbp_path_proven
                    else (
                        "runtime_source_mismatch_after_observation"
                        if path_config_mismatch_after_response
                        else "configured_not_independently_observed"
                    )
                )
            ),
            "path_proof_basis": "operator_surface_isolated_codex_exec_config_requires_independent_trace",
            "fallback_attempted": False,
            "auth_command_invoked": result.get("auth_command_invoked") is True,
            "raw_backend_id_exposed": False,
            "raw_backend_exposed": False,
            "raw_auth_ref_exposed": False,
            "secret_value_recorded": secret_value_recorded,
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": (
                "inspect_transcript"
                if (
                    status_ok
                    and wbp_path_proven
                    and source_provenance_proven
                    and isolated_engine_home_proven
                    and not runtime_model_mismatch_after_response
                )
                else (
                    "inspect_trace_observer"
                    if trace_missing_after_response
                    else (
                        "repair_runtime_source_provenance"
                        if path_config_mismatch_after_response
                        else (
                            "repair_runtime_model_identity"
                            if runtime_model_mismatch_after_response
                            else (
                                "stop_and_diagnose_current_codex_touch"
                                if current_codex_touched_after_response
                                else (
                                    "repair_isolation_proof"
                                    if isolation_missing_after_response
                                    else (
                                        "repair_route_provenance"
                                        if route_provenance_missing_after_response
                                        else str(result.get("next_action") or "stop_and_diagnose")
                                    )
                                )
                            )
                        )
                    )
                )
            ),
        }
        persisted_success = packet_status == "ok"
        event = (
            "prompt_completed_e2e"
            if persisted_success
            else ("prompt_blocked_after_response_e2e" if status_ok else "prompt_failed_e2e")
        )
        session["status"] = event
        session["inference_proven"] = persisted_success
        session["model_response_present"] = status_ok
        session["token_burn"] = token_burn
        session["current_execution_slot_id"] = requested_slot_id
        session["current_execution_path_source"] = "session_bound_slot_runtime"
        session["runtime_lane_proven"] = packet.get("runtime_lane_proven") is True
        role_slots = _canonical_role_slots(session.get("role_slots"))
        if requested_slot_id in role_slots:
            role_slots[requested_slot_id]["runtime_lane_proven"] = (
                packet.get("runtime_lane_proven") is True
            )
            role_slots[requested_slot_id]["runtime_dispatch_state"] = (
                "wbp_session_manager_payload_proven"
                if runtime_slot_dispatch_proven
                else "not_proven"
            )
            session["role_slots"] = role_slots
        if persisted_success and slot.get("route_provenance_required") is True:
            session["route_provenance_proven"] = True
            session["route_execution_proven"] = True
            session["provider_response_proven"] = True
            session["source_provenance_status"] = "route_proven"
            session["live_compatibility_proven"] = True
            if requested_slot_id in role_slots:
                role_slots[requested_slot_id]["route_provenance_proven"] = True
                role_slots[requested_slot_id]["route_execution_proven"] = True
                role_slots[requested_slot_id]["provider_response_proven"] = True
                role_slots[requested_slot_id]["source_provenance_status"] = "route_proven"
                role_slots[requested_slot_id]["live_compatibility_proven"] = True
                session["role_slots"] = role_slots
        session["updated_at_utc"] = utc_now()
        self._append_ledger(
            session,
            event,
            {
                "current_execution_slot_id": requested_slot_id,
                "requested_slot_id": requested_slot_id,
                "requested_slot_explicit": requested_slot_explicit,
                "requested_slot_defaulted_to_primary": requested_slot_defaulted_to_primary,
                **slot_dispatch_admission,
                "wbp_runner_payload_slot_id": wbp_runner_payload_slot_id,
                "wbp_runner_payload_model_id": wbp_runner_payload_model_id,
                "wbp_runner_payload_slot_matches_requested": (
                    wbp_runner_payload_slot_matches_requested
                ),
                "wbp_runner_payload_model_matches_slot": (
                    wbp_runner_payload_model_matches_slot
                ),
                "wbp_session_manager_slot_dispatch_proven": (
                    wbp_session_manager_slot_dispatch_proven
                ),
                "runtime_slot_dispatch_proof_scope": "wbp_session_manager_payload_plus_downstream_echo",
                "downstream_runner_slot_echo_present": downstream_runner_slot_echo_present,
                "downstream_runner_slot_echo": runner_slot_id_text,
                "downstream_runner_slot_echo_matches_requested": (
                    downstream_runner_slot_echo_matches_requested
                ),
                "executed_slot_id": requested_slot_id,
                "executed_slot_model_id": model_id,
                "runtime_slot_dispatch_proven": runtime_slot_dispatch_proven,
                "slot_binding_runtime_dispatch_claimed": runtime_slot_dispatch_proven,
                "parallel_slot_execution_proven": False,
                "fanout_execution_proven": False,
                "runner_slot_id_echo": runner_slot_id_text,
                "runner_slot_id_matches_requested": downstream_runner_slot_echo_matches_requested,
                "current_execution_path_source": "session_bound_slot_runtime",
                "prompt_present": True,
                "prompt_length": len(prompt),
                "prompt_sha256": prompt_hash,
                "prompt_preview_redacted": _safe_preview(prompt),
                "model_response_present": status_ok,
                "inference_proven": persisted_success,
                "response_digest": response_digest,
                "response_preview_bounded": _response_preview(response_text) if status_ok else "",
                "selected_source_class": slot.get("selected_source_class"),
                "selected_backend_server_issued": slot.get("selected_backend_server_issued") is True,
                "selected_route_server_issued": slot.get("selected_route_server_issued") is True,
                "route_provenance_required": slot.get("route_provenance_required") is True,
                "route_provenance_proven": bool(
                    source_provenance_proven and slot.get("route_provenance_required") is True
                ),
                "route_candidate_classified": slot.get("route_candidate_classified") is True,
                "route_static_readiness_classified": slot.get("route_static_readiness_classified")
                is True,
                "route_execution_proven": bool(
                    source_provenance_proven and slot.get("route_provenance_required") is True
                ),
                "provider_response_proven": bool(
                    status_ok and slot.get("route_provenance_required") is True
                ),
                "secret_validity_proven": False,
                "source_provenance_status": live_source_provenance_status,
                "source_candidate_classified": source_candidate_classified,
                "source_provenance_proven": source_provenance_proven,
                "token_usage_present": token_usage_present,
                "token_usage": token_usage,
                "token_burn": token_burn,
                "latency_ms": latency_ms,
                "wbp_path_configured": wbp_path_configured,
                "cli_proxy_api_path_configured": cli_proxy_api_path_configured,
                "wbp_path_observed": independent_wbp_trace_observed,
                "cli_proxy_api_path_observed": independent_wbp_trace_observed,
                "wbp_path_proven": wbp_path_proven,
                "cli_proxy_api_path_proven": cli_proxy_api_path_proven,
                "independent_wbp_trace_observed": independent_wbp_trace_observed,
                "configured_provider": str(result.get("configured_provider") or "") if status_ok else "",
                "runtime_selected_model": runtime_selected_model if status_ok else "",
                "runtime_selected_model_recorded": runtime_selected_model_recorded,
                "runtime_selected_model_matches_bound_model": (
                    runtime_selected_model_matches_bound_model
                    if runtime_selected_model_recorded
                    else False
                ),
                "trace_observer_packet_present": bool(trace_observer_packet),
                "isolated_engine_home_proven": isolated_engine_home_proven,
                "fallback_attempted": False,
            },
        )
        self._write_session(session)
        packet["session"] = self._public_session(session)
        return packet

    def mixed_slot_dispatch_probe_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        owner_authorized: bool = False,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_mixed_slot_dispatch_probe_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "packet_kind": "chatgpt_plus_api_slot_dispatch_probe",
                "final_status": "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_DISPATCH_NOT_PROVEN",
                "execution_mode": "chatgpt_plus_api",
                "same_session_dispatch_proven": False,
                "primary_dispatch_proven": False,
                "coding_dispatch_proven": False,
                "fallback_used": False,
                "ui_label_counts_as_runtime_truth": False,
                "model_self_report_counts_as_runtime_truth": False,
                "browser_backend_intake": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }
        if not owner_authorized:
            return {
                **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
                "session_id": session_id,
                "packet_kind": "chatgpt_plus_api_slot_dispatch_probe",
                "final_status": "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_DISPATCH_NOT_PROVEN",
                "execution_mode": "chatgpt_plus_api",
                "same_session_dispatch_proven": False,
                "primary_dispatch_proven": False,
                "coding_dispatch_proven": False,
                "fallback_used": False,
                "prompt_runner_called": False,
                "next_action": "provide_exact_owner_authorization_phrase",
            }

        role_slots = _canonical_role_slots(session.get("role_slots"))
        primary_slot = dict(role_slots.get(PRIMARY_MODEL_SLOT) or _unbound_slot(PRIMARY_MODEL_SLOT))
        coding_slot = dict(
            role_slots.get(CODING_AGENT_MODEL_SLOT) or _unbound_slot(CODING_AGENT_MODEL_SLOT)
        )
        primary_model_id = str(primary_slot.get("model_id") or "")
        coding_model_id = str(coding_slot.get("model_id") or "")
        precondition_failures: list[str] = []
        if str(session.get("status") or "") not in PROMPT_RUN_ALLOWED_STATUSES:
            precondition_failures.append("SESSION_STATUS_NOT_RUNNABLE")
        if primary_slot.get("binding_status") != "bound":
            precondition_failures.append("PRIMARY_SLOT_NOT_BOUND")
        if coding_slot.get("binding_status") != "bound":
            precondition_failures.append("CODING_SLOT_NOT_BOUND")
        if primary_slot.get("selected_source_class") != "gpt_account":
            precondition_failures.append("PRIMARY_SLOT_NOT_CHATGPT_ACCOUNT")
        if coding_slot.get("selected_source_class") != "route_backed":
            precondition_failures.append("CODING_SLOT_NOT_API_ROUTE_BACKED")
        if primary_model_id and coding_model_id and primary_model_id == coding_model_id:
            precondition_failures.append("PRIMARY_AND_CODING_MODELS_COLLAPSED")
        for slot_id, slot in (
            (PRIMARY_MODEL_SLOT, primary_slot),
            (CODING_AGENT_MODEL_SLOT, coding_slot),
        ):
            admission = _slot_dispatch_admission_packet(
                session=session,
                slot=slot,
                requested_slot_id=slot_id,
            )
            if not admission["slot_admission_passed"]:
                precondition_failures.append(f"{slot_id.upper()}_ADMISSION_FAILED")
        if precondition_failures:
            return {
                **self._base_packet("blocked", precondition_failures[0]),
                "session_id": session_id,
                "packet_kind": "chatgpt_plus_api_slot_dispatch_probe",
                "final_status": "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_DISPATCH_NOT_PROVEN",
                "execution_mode": "chatgpt_plus_api",
                "precondition_failures": sorted(set(precondition_failures)),
                "primary_model_id": primary_model_id,
                "coding_agent_model_id": coding_model_id,
                "primary_selected_source_class": primary_slot.get("selected_source_class"),
                "coding_selected_source_class": coding_slot.get("selected_source_class"),
                "same_session_dispatch_proven": False,
                "primary_dispatch_proven": False,
                "coding_dispatch_proven": False,
                "chatgpt_only_calls_api": False,
                "api_only_calls_chatgpt": False,
                "fallback_used": False,
                "prompt_runner_called": False,
                "ui_label_counts_as_runtime_truth": False,
                "model_self_report_counts_as_runtime_truth": False,
                "role_slot_binding_packet": self._role_slot_binding_packet(session),
                "next_action": "repair_mixed_slot_binding",
            }

        primary_packet = self.prompt_packet(
            session_id,
            {
                "prompt": "Ответь одной строкой: WBP_MIXED_PRIMARY_SLOT_OK",
                "slot_id": PRIMARY_MODEL_SLOT,
            },
            prompt_runner,
            owner_authorized=True,
        )
        coding_packet: dict[str, Any] = {}
        if primary_packet.get("status") == "ok":
            coding_packet = self.prompt_packet(
                session_id,
                {
                    "prompt": "Ответь одной строкой: WBP_MIXED_DEEPSEEK_CODER_OK",
                    "slot_id": CODING_AGENT_MODEL_SLOT,
                },
                prompt_runner,
                owner_authorized=True,
            )

        primary_dispatch_proven = self._slot_dispatch_probe_success(
            primary_packet,
            requested_slot_id=PRIMARY_MODEL_SLOT,
            expected_model_id=primary_model_id,
            expected_provider="cliproxy",
            expected_source_provenance="backend_proven",
        )
        coding_dispatch_proven = self._slot_dispatch_probe_success(
            coding_packet,
            requested_slot_id=CODING_AGENT_MODEL_SLOT,
            expected_model_id=coding_model_id,
            expected_provider="external_route",
            expected_source_provenance="route_proven",
        )
        fallback_used = (
            primary_packet.get("fallback_attempted") is True
            or coding_packet.get("fallback_attempted") is True
        )
        same_session_dispatch_proven = bool(
            primary_dispatch_proven
            and coding_dispatch_proven
            and primary_packet.get("session_id") == session_id
            and coding_packet.get("session_id") == session_id
            and primary_model_id != coding_model_id
            and not fallback_used
        )
        success = same_session_dispatch_proven
        machine_error_code = "OK" if success else "MIXED_SLOT_DISPATCH_NOT_PROVEN"
        final_status = (
            "CHATGPT_PLUS_API_SLOT_DISPATCH_PROVEN_WITH_LIMITS"
            if success
            else "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_DISPATCH_NOT_PROVEN"
        )
        return {
            **self._base_packet("ok" if success else "blocked", machine_error_code),
            "packet_kind": "chatgpt_plus_api_slot_dispatch_probe",
            "final_status": final_status,
            "execution_mode": "chatgpt_plus_api",
            "session_id": session_id,
            "same_session_dispatch_proven": same_session_dispatch_proven,
            "primary_dispatch_proven": primary_dispatch_proven,
            "coding_dispatch_proven": coding_dispatch_proven,
            "primary_model_id": primary_model_id,
            "coding_agent_model_id": coding_model_id,
            "primary_requested_slot_id": PRIMARY_MODEL_SLOT,
            "coding_requested_slot_id": CODING_AGENT_MODEL_SLOT,
            "primary_executed_slot_id": str(primary_packet.get("executed_slot_id") or ""),
            "coding_executed_slot_id": str(coding_packet.get("executed_slot_id") or ""),
            "primary_runtime_model": str(primary_packet.get("runtime_selected_model") or ""),
            "coding_runtime_model": str(coding_packet.get("runtime_selected_model") or ""),
            "primary_configured_provider": str(primary_packet.get("configured_provider") or ""),
            "coding_configured_provider": str(coding_packet.get("configured_provider") or ""),
            "primary_selected_source_provenance": str(
                primary_packet.get("selected_source_provenance") or ""
            ),
            "coding_selected_source_provenance": str(
                coding_packet.get("selected_source_provenance") or ""
            ),
            "primary_runner_payload_slot_id": str(
                primary_packet.get("wbp_runner_payload_slot_id") or ""
            ),
            "coding_runner_payload_slot_id": str(
                coding_packet.get("wbp_runner_payload_slot_id") or ""
            ),
            "primary_runner_payload_model_id": str(
                primary_packet.get("wbp_runner_payload_model_id") or ""
            ),
            "coding_runner_payload_model_id": str(
                coding_packet.get("wbp_runner_payload_model_id") or ""
            ),
            "primary_runtime_slot_dispatch_proven": primary_packet.get(
                "runtime_slot_dispatch_proven"
            )
            is True,
            "coding_runtime_slot_dispatch_proven": coding_packet.get(
                "runtime_slot_dispatch_proven"
            )
            is True,
            "primary_live_prompt_full_success": primary_packet.get("live_prompt_full_success")
            is True,
            "coding_live_prompt_full_success": coding_packet.get("live_prompt_full_success")
            is True,
            "chatgpt_only_calls_api": False,
            "api_only_calls_chatgpt": False,
            "fallback_used": fallback_used,
            "fallback_attempted": fallback_used,
            "parallel_slot_execution_proven": False,
            "fanout_execution_proven": False,
            "live_file_mutation_claimed": False,
            "wbp_patch_applier_used": False,
            "commit_attempted": False,
            "push_attempted": False,
            "merge_attempted": False,
            "ui_label_counts_as_runtime_truth": False,
            "model_self_report_counts_as_runtime_truth": False,
            "model_lane_proof_level_counts_as_runtime_truth": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "primary_packet_summary": self._slot_dispatch_probe_summary(primary_packet),
            "coding_packet_summary": self._slot_dispatch_probe_summary(coding_packet),
            "role_slot_binding_packet": self._role_slot_binding_packet(
                self._sessions.get(session_id) or session
            ),
            "next_action": "none" if success else "stop_and_diagnose_mixed_slot_dispatch",
        }

    def temp_write_probe_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any], Path], dict[str, Any]],
        *,
        owner_authorized: bool = False,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_temp_write_probe_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_TEMP_WRITE_NOT_ADMITTED",
                "browser_path_intake": False,
                "browser_backend_intake": False,
                "repo_mutation_attempted": False,
                "fallback_attempted": False,
            }
        if not owner_authorized:
            return {
                **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_TEMP_WRITE_NOT_ADMITTED",
                "next_action": "provide_exact_owner_authorization_phrase",
                "fallback_attempted": False,
                "repo_mutation_attempted": False,
                "file_existed_after_tool": False,
                "file_removed_after_probe": False,
            }

        requested_slot_id = PRIMARY_MODEL_SLOT
        precondition_failure = self._prompt_precondition_failure(session, requested_slot_id)
        if precondition_failure:
            return {
                **precondition_failure,
                "final_status": "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_TEMP_WRITE_NOT_ADMITTED",
                "fallback_attempted": False,
                "repo_mutation_attempted": False,
            }
        role_slots = _canonical_role_slots(session.get("role_slots"))
        slot = dict(role_slots[PRIMARY_MODEL_SLOT])
        model_id = str(slot.get("model_id") or "")
        api_model_id = str(payload.get("api_model_id") or model_id).strip()
        if api_model_id != model_id:
            return {
                **self._base_packet("rejected", "MODEL_ID_DOES_NOT_MATCH_BOUND_PRIMARY_SLOT"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_TEMP_WRITE_NOT_ADMITTED",
                "model_id": model_id,
                "api_model_id": api_model_id,
                "fallback_attempted": False,
                "repo_mutation_attempted": False,
            }
        if slot.get("selected_source_class") != "route_backed":
            return {
                **self._base_packet("blocked", "API_ONLY_ROUTE_BACKED_PRIMARY_SLOT_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_TEMP_WRITE_NOT_ADMITTED",
                "model_id": model_id,
                "current_execution_slot_id": PRIMARY_MODEL_SLOT,
                "fallback_attempted": False,
                "repo_mutation_attempted": False,
            }

        probe_dir = Path(tempfile.mkdtemp(prefix="wbp-api-only-write-probe-")).resolve()
        probe_file = probe_dir / "deepseek-temp-write-proof.txt"
        expected_text = "WBP_DEEPSEEK_TEMP_WRITE_OK"
        prompt = (
            "Use the available command execution tool. Run exactly this shell command, "
            "then answer with exactly the file content and nothing else:\n"
            f"printf {expected_text} > {probe_file} && cat {probe_file}"
        )
        runner_payload = {
            "prompt": prompt,
            "model_id": model_id,
            "slot_id": PRIMARY_MODEL_SLOT,
            "slot_id_explicit": False,
        }
        try:
            result = prompt_runner(runner_payload, probe_dir)
        except Exception as exc:  # pragma: no cover - defensive live boundary
            result = {
                "status": "failed",
                "machine_error_code": "TEMP_WRITE_PROMPT_RUNNER_EXCEPTION",
                "error_class": type(exc).__name__,
            }

        file_existed_after_tool = probe_file.exists()
        file_content = ""
        if file_existed_after_tool:
            file_content = probe_file.read_text(encoding="utf-8", errors="replace")
        file_content_matches = file_content == expected_text
        file_within_probe_dir = probe_dir in probe_file.resolve().parents
        cleanup_error = ""
        try:
            if probe_file.exists():
                probe_file.unlink()
            probe_dir.rmdir()
        except OSError as exc:
            cleanup_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        file_removed_after_probe = not probe_file.exists() and not probe_dir.exists()

        raw_trace = result.get("trace_observer_packet") if isinstance(result.get("trace_observer_packet"), dict) else {}
        trace_packet = _safe_trace_observer_packet(raw_trace)
        request_count = trace_packet.get("request_count")
        tool_loop_proven = isinstance(request_count, int) and request_count >= 2
        response_text = str(result.get("final_message") or result.get("response_text") or "")
        provider_response_proven = result.get("status") == "ok" and bool(response_text)
        success = (
            provider_response_proven
            and tool_loop_proven
            and result.get("configured_provider") == "external_route"
            and result.get("runtime_model") == model_id
            and file_existed_after_tool
            and file_content_matches
            and file_within_probe_dir
            and file_removed_after_probe
            and result.get("current_codex_home_used") is False
            and result.get("secret_value_recorded") is False
        )
        return {
            **self._base_packet("ok" if success else "blocked", "OK" if success else "TEMP_WRITE_PROBE_NOT_PROVEN"),
            "final_status": (
                "API_ONLY_DEEPSEEK_TEMP_WRITE_PROVEN_WITH_LIMITS"
                if success
                else "KNOWN_BLOCKER_CODEX_CUSTOM_WRITE_SANDBOX_NOT_ADMISSIBLE"
            ),
            "execution_mode": "api_only",
            "session_id": session_id,
            "model_id": model_id,
            "current_execution_slot_id": PRIMARY_MODEL_SLOT,
            "selected_source_class": slot.get("selected_source_class"),
            "provider_response_proven": provider_response_proven,
            "fallback_attempted": False,
            "tool_loop_proven": tool_loop_proven,
            "request_count": request_count if isinstance(request_count, int) else 0,
            "write_surface": "temp_only",
            "browser_path_intake": False,
            "browser_backend_intake": False,
            "file_existed_after_tool": file_existed_after_tool,
            "file_content_matches": file_content_matches,
            "file_removed_after_probe": file_removed_after_probe,
            "file_within_probe_dir": file_within_probe_dir,
            "repo_mutation_attempted": False,
            "original_codex_touched": False,
            "wbp_patch_applier_used": False,
            "live_product_code_edit_claimed": False,
            "workspace_write_admitted": result.get("workspace_write_admitted") is True,
            "danger_full_access_admitted": False,
            "current_codex_touched": result.get("current_codex_home_used") is True,
            "secret_value_recorded": result.get("secret_value_recorded") is True,
            "response_preview_bounded": _response_preview(response_text),
            "trace_observer_packet": trace_packet,
            "cleanup_error": cleanup_error,
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
        }

    def safe_worktree_edit_probe_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any], Path], dict[str, Any]],
        *,
        owner_authorized: bool = False,
        repo_root: Path | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_safe_worktree_edit_probe_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
                "browser_worktree_path_intake": False,
                "browser_backend_intake": False,
                "main_worktree_mutated_by_probe": False,
                "fallback_attempted": False,
            }
        if not owner_authorized:
            return {
                **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
                "next_action": "provide_exact_owner_authorization_phrase",
                "fallback_attempted": False,
                "main_worktree_mutated_by_probe": False,
                "safe_worktree_used": False,
            }

        requested_slot_id = PRIMARY_MODEL_SLOT
        precondition_failure = self._prompt_precondition_failure(session, requested_slot_id)
        if precondition_failure:
            return {
                **precondition_failure,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
                "fallback_attempted": False,
                "main_worktree_mutated_by_probe": False,
            }
        role_slots = _canonical_role_slots(session.get("role_slots"))
        slot = dict(role_slots[PRIMARY_MODEL_SLOT])
        model_id = str(slot.get("model_id") or "")
        api_model_id = str(payload.get("api_model_id") or model_id).strip()
        if api_model_id != model_id:
            return {
                **self._base_packet("rejected", "MODEL_ID_DOES_NOT_MATCH_BOUND_PRIMARY_SLOT"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
                "model_id": model_id,
                "api_model_id": api_model_id,
                "fallback_attempted": False,
                "main_worktree_mutated_by_probe": False,
            }
        if slot.get("selected_source_class") != "route_backed":
            return {
                **self._base_packet("blocked", "API_ONLY_ROUTE_BACKED_PRIMARY_SLOT_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
                "model_id": model_id,
                "current_execution_slot_id": PRIMARY_MODEL_SLOT,
                "fallback_attempted": False,
                "main_worktree_mutated_by_probe": False,
            }

        repo = (repo_root or Path.cwd()).resolve()
        git_root = _run_git_command(repo, ["rev-parse", "--show-toplevel"])
        if not git_root["ok"]:
            return {
                **self._base_packet("blocked", "SAFE_WORKTREE_REPO_ROOT_NOT_GIT"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
                "fallback_attempted": False,
                "main_worktree_mutated_by_probe": False,
            }
        repo = Path(str(git_root["stdout"]).strip()).resolve()
        status_before = _run_git_command(repo, ["status", "--short", "--branch"])
        main_status_before = str(status_before.get("stdout") or "")
        probe_parent = Path(tempfile.mkdtemp(prefix="wbp-api-only-safe-worktree-")).resolve()
        worktree_dir = probe_parent / "worktree"
        control_rel = Path("tmp_wbp_deepseek_safe_worktree_edit_proof.txt")
        control_file = worktree_dir / control_rel
        before_text = "WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_BEFORE\n"
        expected_text = "WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK"
        setup_error = ""
        cleanup_error = ""
        result: dict[str, Any] = {
            "status": "failed",
            "machine_error_code": "SAFE_WORKTREE_PROMPT_NOT_RUN",
        }
        safe_worktree_used = False
        git_diff = ""
        file_existed_after_tool = False
        file_content = ""
        worktree_removed_after_probe = False
        try:
            add_worktree = _run_git_command(
                repo,
                ["worktree", "add", "--detach", str(worktree_dir), "HEAD"],
                timeout_seconds=60,
            )
            if not add_worktree["ok"]:
                setup_error = str(add_worktree.get("stderr") or add_worktree.get("stdout") or "")[:240]
            else:
                safe_worktree_used = True
                control_file.write_text(before_text, encoding="utf-8")
                add_control = _run_git_command(worktree_dir, ["add", str(control_rel)])
                if not add_control["ok"]:
                    setup_error = str(add_control.get("stderr") or add_control.get("stdout") or "")[:240]
                else:
                    prompt = (
                        "Use the available command execution tool. Run exactly this shell command, "
                        "then answer with exactly the file content and nothing else:\n"
                        f"printf {expected_text} > {control_file} && cat {control_file}"
                    )
                    runner_payload = {
                        "prompt": prompt,
                        "model_id": model_id,
                        "slot_id": PRIMARY_MODEL_SLOT,
                        "slot_id_explicit": False,
                    }
                    try:
                        result = prompt_runner(runner_payload, worktree_dir)
                    except Exception as exc:  # pragma: no cover - defensive live boundary
                        result = {
                            "status": "failed",
                            "machine_error_code": "SAFE_WORKTREE_PROMPT_RUNNER_EXCEPTION",
                            "error_class": type(exc).__name__,
                        }
                    file_existed_after_tool = control_file.exists()
                    if file_existed_after_tool:
                        file_content = control_file.read_text(encoding="utf-8", errors="replace")
                    diff_result = _run_git_command(worktree_dir, ["diff", "--", str(control_rel)])
                    git_diff = str(diff_result.get("stdout") or "") if diff_result["ok"] else ""
        finally:
            if worktree_dir.exists():
                removed = _run_git_command(repo, ["worktree", "remove", "--force", str(worktree_dir)], timeout_seconds=60)
                if not removed["ok"]:
                    cleanup_error = str(removed.get("stderr") or removed.get("stdout") or "")[:240]
            try:
                shutil.rmtree(probe_parent)
            except OSError as exc:
                cleanup_error = cleanup_error or f"{type(exc).__name__}: {str(exc)[:160]}"
            worktree_list = _run_git_command(repo, ["worktree", "list", "--porcelain"])
            worktree_removed_after_probe = (
                not worktree_dir.exists()
                and str(worktree_dir) not in str(worktree_list.get("stdout") or "")
            )

        file_content_matches = file_content == expected_text
        git_diff_observed = bool(git_diff.strip())
        expected_diff_observed = (
            f"-{before_text.strip()}" in git_diff and f"+{expected_text}" in git_diff
        )
        secret_in_diff = bool(re.search(r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,})", git_diff))
        status_after = _run_git_command(repo, ["status", "--short", "--branch"])
        main_status_after = str(status_after.get("stdout") or "")
        main_worktree_mutated_by_probe = main_status_before != main_status_after
        raw_trace = result.get("trace_observer_packet") if isinstance(result.get("trace_observer_packet"), dict) else {}
        trace_packet = _safe_trace_observer_packet(raw_trace)
        request_count = trace_packet.get("request_count")
        tool_loop_proven = isinstance(request_count, int) and request_count >= 2
        response_text = str(result.get("final_message") or result.get("response_text") or "")
        provider_response_proven = result.get("status") == "ok" and bool(response_text)
        success = (
            provider_response_proven
            and tool_loop_proven
            and result.get("configured_provider") == "external_route"
            and result.get("runtime_model") == model_id
            and result.get("workspace_write_admitted") is True
            and safe_worktree_used
            and file_existed_after_tool
            and file_content_matches
            and git_diff_observed
            and expected_diff_observed
            and not main_worktree_mutated_by_probe
            and not secret_in_diff
            and worktree_removed_after_probe
            and result.get("current_codex_home_used") is False
            and result.get("secret_value_recorded") is False
            and not setup_error
            and not cleanup_error
        )
        if success:
            final_status = "API_ONLY_DEEPSEEK_SAFE_WORKTREE_EDIT_PROVEN_WITH_LIMITS"
            machine_error_code = "OK"
        elif cleanup_error or not worktree_removed_after_probe:
            final_status = "KNOWN_BLOCKER_SAFE_WORKTREE_CLEANUP_FAILED"
            machine_error_code = "SAFE_WORKTREE_CLEANUP_FAILED"
        elif not safe_worktree_used or setup_error or result.get("workspace_write_admitted") is not True:
            final_status = "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE"
            machine_error_code = "SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE"
        elif not git_diff_observed or not expected_diff_observed:
            final_status = "KNOWN_BLOCKER_SAFE_WORKTREE_DIFF_NOT_PROVEN"
            machine_error_code = "SAFE_WORKTREE_DIFF_NOT_PROVEN"
        else:
            final_status = "KNOWN_BLOCKER_DEEPSEEK_REPO_EDIT_TOOL_CALL_FAILED"
            machine_error_code = "DEEPSEEK_REPO_EDIT_TOOL_CALL_FAILED"
        return {
            **self._base_packet("ok" if success else "blocked", machine_error_code),
            "final_status": final_status,
            "execution_mode": "api_only",
            "session_id": session_id,
            "model_id": model_id,
            "provider_id": "deepseek" if "deepseek" in model_id else "external_route",
            "current_execution_slot_id": PRIMARY_MODEL_SLOT,
            "selected_source_class": slot.get("selected_source_class"),
            "selected_from_server_catalog": slot.get("server_issued") is True,
            "provider_response_proven": provider_response_proven,
            "fallback_attempted": False,
            "tool_loop_proven": tool_loop_proven,
            "request_count": request_count if isinstance(request_count, int) else 0,
            "safe_worktree_used": safe_worktree_used,
            "browser_worktree_path_intake": False,
            "browser_backend_intake": False,
            "write_surface": "safe_worktree_only",
            "danger_full_access_admitted": False,
            "file_changed_by_codex_tool": file_existed_after_tool and file_content_matches,
            "file_content_matches": file_content_matches,
            "git_diff_observed": git_diff_observed,
            "expected_diff_observed": expected_diff_observed,
            "main_worktree_mutated_by_probe": main_worktree_mutated_by_probe,
            "secret_value_recorded": result.get("secret_value_recorded") is True,
            "secret_in_diff": secret_in_diff,
            "original_codex_touched": False,
            "original_codex_profile_touched": False,
            "current_codex_touched": result.get("current_codex_home_used") is True,
            "wbp_patch_applier_used": False,
            "commit_attempted": False,
            "push_attempted": False,
            "merge_attempted": False,
            "worktree_removed_after_probe": worktree_removed_after_probe,
            "workspace_write_admitted": result.get("workspace_write_admitted") is True,
            "live_product_code_edit_claimed": False,
            "response_preview_bounded": _response_preview(response_text),
            "git_diff_sha256": _digest(git_diff) if git_diff else "",
            "setup_error_bounded": setup_error,
            "cleanup_error": cleanup_error,
            "trace_observer_packet": trace_packet,
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
        }

    def repo_tmp_edit_probe_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any], Path], dict[str, Any]],
        *,
        owner_authorized: bool = False,
        repo_root: Path | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_repo_tmp_edit_probe_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "browser_path_intake": False,
                "browser_backend_intake": False,
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
                "fallback_attempted": False,
            }
        if not owner_authorized:
            return {
                **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
                "session_id": session_id,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "next_action": "provide_exact_owner_authorization_phrase",
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
                "fallback_attempted": False,
            }

        requested_slot_id = PRIMARY_MODEL_SLOT
        precondition_failure = self._prompt_precondition_failure(session, requested_slot_id)
        if precondition_failure:
            return {
                **precondition_failure,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
                "fallback_attempted": False,
            }
        role_slots = _canonical_role_slots(session.get("role_slots"))
        slot = dict(role_slots[PRIMARY_MODEL_SLOT])
        model_id = str(slot.get("model_id") or "")
        api_model_id = str(payload.get("api_model_id") or model_id).strip()
        if api_model_id != model_id:
            return {
                **self._base_packet("rejected", "MODEL_ID_DOES_NOT_MATCH_BOUND_PRIMARY_SLOT"),
                "session_id": session_id,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "model_id": model_id,
                "api_model_id": api_model_id,
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
                "fallback_attempted": False,
            }
        if slot.get("selected_source_class") != "route_backed":
            return {
                **self._base_packet("blocked", "API_ONLY_ROUTE_BACKED_PRIMARY_SLOT_REQUIRED"),
                "session_id": session_id,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "model_id": model_id,
                "current_execution_slot_id": PRIMARY_MODEL_SLOT,
                "api_only_calls_chatgpt": False,
                "chatgpt_only_calls_api": False,
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
                "fallback_attempted": False,
            }
        if "deepseek" not in model_id.lower():
            return {
                **self._base_packet("rejected", "DEEPSEEK_ROUTE_MODEL_REQUIRED"),
                "session_id": session_id,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "model_id": model_id,
                "current_execution_slot_id": PRIMARY_MODEL_SLOT,
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
                "fallback_attempted": False,
            }

        repo = (repo_root or Path.cwd()).resolve()
        git_root = _run_git_command(repo, ["rev-parse", "--show-toplevel"])
        if not git_root["ok"]:
            return {
                **self._base_packet("blocked", "REPO_TMP_EDIT_REPO_ROOT_NOT_GIT"),
                "session_id": session_id,
                "final_status": "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN",
                "fallback_attempted": False,
                "main_tree_mutation_admitted": False,
                "outside_write_surface_changed": False,
            }
        repo = Path(str(git_root["stdout"]).strip()).resolve()
        status_before = _run_git_command(repo, ["status", "--porcelain=v1", "-uall"])
        status_before_lines = str(status_before.get("stdout") or "").splitlines()
        tmp_dir = repo / ".tmp"
        target_rel = Path(".tmp/deepseek_api_only_live_edit_probe.txt")
        target = repo / target_rel
        tmp_dir.mkdir(parents=True, exist_ok=True)
        before_text = "WBP_API_ONLY_DEEPSEEK_EDIT_BEFORE"
        target.write_text(before_text, encoding="utf-8")
        before_existed = target.exists()
        before_content = target.read_text(encoding="utf-8", errors="replace") if before_existed else ""
        expected_text = "WBP_API_ONLY_DEEPSEEK_EDIT_OK"
        result: dict[str, Any] = {
            "status": "failed",
            "machine_error_code": "REPO_TMP_EDIT_PROMPT_NOT_RUN",
        }
        try:
            prompt = (
                "Use the available command execution tool. Run exactly this shell command, "
                "then answer with exactly the file content and nothing else:\n"
                f"printf {shlex.quote(expected_text)} > {shlex.quote(str(target))} && "
                f"cat {shlex.quote(str(target))}"
            )
            runner_payload = {
                "prompt": prompt,
                "model_id": model_id,
                "slot_id": PRIMARY_MODEL_SLOT,
                "slot_id_explicit": False,
                "declared_write_surface": ".tmp_only",
                "target_relative_path": str(target_rel),
            }
            result = prompt_runner(runner_payload, tmp_dir)
        except Exception as exc:  # pragma: no cover - defensive live boundary
            result = {
                "status": "failed",
                "machine_error_code": "REPO_TMP_EDIT_PROMPT_RUNNER_EXCEPTION",
                "error_class": type(exc).__name__,
            }

        after_existed = target.exists()
        after_content = target.read_text(encoding="utf-8", errors="replace") if after_existed else ""
        status_after = _run_git_command(repo, ["status", "--porcelain=v1", "-uall"])
        status_after_lines = str(status_after.get("stdout") or "").splitlines()

        def outside_tmp(lines: list[str]) -> list[str]:
            outside: list[str] = []
            for line in lines:
                path_text = line[3:] if len(line) > 3 else line
                if path_text.startswith(".tmp/") or " -> .tmp/" in path_text:
                    continue
                outside.append(line)
            return outside

        outside_write_surface_changed = outside_tmp(status_before_lines) != outside_tmp(status_after_lines)
        raw_trace = result.get("trace_observer_packet") if isinstance(result.get("trace_observer_packet"), dict) else {}
        trace_packet = _safe_trace_observer_packet(raw_trace)
        request_count = trace_packet.get("request_count")
        tool_loop_proven = isinstance(request_count, int) and request_count >= 2
        response_text = str(result.get("final_message") or result.get("response_text") or "")
        provider_response_proven = result.get("status") == "ok" and bool(response_text)
        file_content_matches = after_content == expected_text
        file_changed_by_codex_tool = after_existed and file_content_matches and (
            not before_existed or before_content != after_content
        )
        success = (
            provider_response_proven
            and tool_loop_proven
            and result.get("configured_provider") == "external_route"
            and result.get("runtime_model") == model_id
            and result.get("workspace_write_admitted") is True
            and result.get("additional_writable_dir_admitted") is True
            and after_existed
            and file_content_matches
            and file_changed_by_codex_tool
            and not outside_write_surface_changed
            and result.get("current_codex_home_used") is False
            and result.get("secret_value_recorded") is False
        )
        return {
            **self._base_packet("ok" if success else "blocked", "OK" if success else "REPO_TMP_EDIT_NOT_PROVEN"),
            "final_status": (
                "API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_PROVEN_WITH_LIMITS"
                if success
                else "STOP_AND_DIAGNOSE_API_ONLY_DEEPSEEK_CODEX_TOOL_EDIT_NOT_PROVEN"
            ),
            "execution_mode": "api_only",
            "session_id": session_id,
            "model_id": model_id,
            "provider_id": "deepseek",
            "current_execution_slot_id": PRIMARY_MODEL_SLOT,
            "selected_source_class": slot.get("selected_source_class"),
            "selected_from_server_catalog": slot.get("server_issued") is True,
            "provider_called": provider_response_proven,
            "provider_response_proven": provider_response_proven,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "fallback_attempted": False,
            "fallback_used": False,
            "tool_loop_proven": tool_loop_proven,
            "request_count": request_count if isinstance(request_count, int) else 0,
            "main_tree_mutation_admitted": True,
            "write_surface": ".tmp_only",
            "write_surface_path_redacted": str(target_rel),
            "browser_path_intake": False,
            "browser_backend_intake": False,
            "file_relative_path": str(target_rel),
            "file_existed_before_tool": before_existed,
            "setup_probe_file_seeded_by_wbp": True,
            "file_existed_after_tool": after_existed,
            "file_changed_by_codex_tool": file_changed_by_codex_tool,
            "file_content_matches": file_content_matches,
            "file_sha256": _digest(after_content) if after_existed else "",
            "outside_write_surface_changed": outside_write_surface_changed,
            "secret_value_recorded": result.get("secret_value_recorded") is True,
            "secret_in_probe_file": bool(
                re.search(r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,})", after_content)
            ),
            "original_codex_touched": False,
            "original_codex_profile_touched": False,
            "current_codex_touched": result.get("current_codex_home_used") is True,
            "wbp_patch_applier_used": False,
            "commit_attempted": False,
            "push_attempted": False,
            "merge_attempted": False,
            "workspace_write_admitted": result.get("workspace_write_admitted") is True,
            "additional_writable_dir_admitted": result.get("additional_writable_dir_admitted") is True,
            "additional_writable_dir_scope": str(result.get("additional_writable_dir_scope") or ""),
            "danger_full_access_admitted": result.get("danger_full_access_admitted") is True,
            "response_preview_bounded": _response_preview(response_text),
            "trace_observer_packet": trace_packet,
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "manual_review_packet" if success else "inspect_repo_tmp_edit_packet",
        }

    def safe_worktree_coder_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any], Path], dict[str, Any]],
        *,
        owner_authorized: bool = False,
        repo_root: Path | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_safe_worktree_coder_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "browser_worktree_path_intake": False,
                "browser_backend_intake": False,
                "main_worktree_mutated_by_run": False,
                "fallback_attempted": False,
            }
        if not owner_authorized:
            return {
                **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "next_action": "provide_exact_owner_authorization_phrase",
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
                "safe_worktree_status": "not_created",
            }
        task = str(payload.get("task") or "").strip()
        if not task:
            return {
                **self._base_packet("rejected", "TASK_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
            }
        if len(task) > 6000:
            return {
                **self._base_packet("rejected", "TASK_TOO_LONG"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
            }

        requested_slot_id = PRIMARY_MODEL_SLOT
        precondition_failure = self._prompt_precondition_failure(session, requested_slot_id)
        if precondition_failure:
            return {
                **precondition_failure,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
            }
        role_slots = _canonical_role_slots(session.get("role_slots"))
        slot = dict(role_slots[PRIMARY_MODEL_SLOT])
        model_id = str(slot.get("model_id") or "")
        api_model_id = str(payload.get("api_model_id") or model_id).strip()
        if api_model_id != model_id:
            return {
                **self._base_packet("rejected", "MODEL_ID_DOES_NOT_MATCH_BOUND_PRIMARY_SLOT"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "model_id": model_id,
                "api_model_id": api_model_id,
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
            }
        if slot.get("selected_source_class") != "route_backed":
            return {
                **self._base_packet("blocked", "API_ONLY_ROUTE_BACKED_PRIMARY_SLOT_REQUIRED"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "model_id": model_id,
                "current_execution_slot_id": PRIMARY_MODEL_SLOT,
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
            }

        repo = (repo_root or Path.cwd()).resolve()
        git_root = _run_git_command(repo, ["rev-parse", "--show-toplevel"])
        if not git_root["ok"]:
            return {
                **self._base_packet("blocked", "SAFE_WORKTREE_REPO_ROOT_NOT_GIT"),
                "session_id": session_id,
                "final_status": "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE",
                "fallback_attempted": False,
                "main_worktree_mutated_by_run": False,
            }
        repo = Path(str(git_root["stdout"]).strip()).resolve()
        status_before = _run_git_command(repo, ["status", "--short", "--branch"])
        main_status_before = str(status_before.get("stdout") or "")
        parent_dir = Path(tempfile.mkdtemp(prefix="wbp-product-safe-worktree-")).resolve()
        worktree_dir = parent_dir / "worktree"
        worktree_id = f"wbt-{uuid.uuid4().hex[:20]}"
        setup_error = ""
        result: dict[str, Any] = {
            "status": "failed",
            "machine_error_code": "PRODUCT_CODER_PROMPT_NOT_RUN",
        }
        safe_worktree_used = False
        diff_text = ""
        changed_files: list[str] = []
        head_before = ""
        head_after = ""
        merge_head_present = False
        try:
            add_worktree = _run_git_command(
                repo,
                ["worktree", "add", "--detach", str(worktree_dir), "HEAD"],
                timeout_seconds=60,
            )
            if not add_worktree["ok"]:
                setup_error = str(add_worktree.get("stderr") or add_worktree.get("stdout") or "")[:240]
            else:
                safe_worktree_used = True
                head_before_result = _run_git_command(worktree_dir, ["rev-parse", "HEAD"])
                head_before = str(head_before_result.get("stdout") or "").strip()
                prompt = (
                    "You are the API-only coding model for Wild Boar Proxy. "
                    "Work only in the current repository worktree. Do not commit, push, merge, "
                    "read secrets, edit credentials, or touch Codex profiles. "
                    "Make the requested code change using the available tools, then briefly report "
                    "changed files and tests/checks you ran.\n\n"
                    f"Task:\n{task}"
                )
                runner_payload = {
                    "prompt": prompt,
                    "model_id": model_id,
                    "slot_id": PRIMARY_MODEL_SLOT,
                    "slot_id_explicit": False,
                }
                try:
                    result = prompt_runner(runner_payload, worktree_dir)
                except Exception as exc:  # pragma: no cover - defensive live boundary
                    result = {
                        "status": "failed",
                        "machine_error_code": "PRODUCT_CODER_PROMPT_RUNNER_EXCEPTION",
                        "error_class": type(exc).__name__,
                    }
                head_after_result = _run_git_command(worktree_dir, ["rev-parse", "HEAD"])
                head_after = str(head_after_result.get("stdout") or "").strip()
                diff_result = _run_git_command(worktree_dir, ["diff", "--"])
                diff_text = str(diff_result.get("stdout") or "") if diff_result["ok"] else ""
                names_result = _run_git_command(worktree_dir, ["diff", "--name-only", "--"])
                if names_result["ok"]:
                    changed_files = [
                        line.strip()
                        for line in str(names_result.get("stdout") or "").splitlines()
                        if line.strip()
                    ]
                merge_head_result = _run_git_command(worktree_dir, ["rev-parse", "--git-path", "MERGE_HEAD"])
                if merge_head_result["ok"]:
                    merge_head_present = Path(str(merge_head_result.get("stdout") or "").strip()).exists()
        except Exception as exc:  # pragma: no cover - defensive host boundary
            setup_error = setup_error or f"{type(exc).__name__}: {str(exc)[:240]}"

        status_after = _run_git_command(repo, ["status", "--short", "--branch"])
        main_status_after = str(status_after.get("stdout") or "")
        main_worktree_mutated_by_run = main_status_before != main_status_after
        raw_trace = result.get("trace_observer_packet") if isinstance(result.get("trace_observer_packet"), dict) else {}
        trace_packet = _safe_trace_observer_packet(raw_trace)
        request_count = trace_packet.get("request_count")
        tool_loop_proven = isinstance(request_count, int) and request_count >= 2
        response_text = str(result.get("final_message") or result.get("response_text") or "")
        provider_response_proven = result.get("status") == "ok" and bool(response_text)
        diff_present = bool(diff_text.strip())
        secret_in_diff = bool(re.search(r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,})", diff_text))
        commit_attempted = bool(head_before and head_after and head_before != head_after)
        push_attempt_absent_proven = result.get("direct_non_wbp_model_egress_absent_proven") is True
        success = (
            provider_response_proven
            and tool_loop_proven
            and result.get("configured_provider") == "external_route"
            and result.get("runtime_model") == model_id
            and result.get("workspace_write_admitted") is True
            and result.get("working_dir_override_admitted") is True
            and result.get("working_dir_scope") == "safe_worktree_only"
            and safe_worktree_used
            and diff_present
            and bool(changed_files)
            and not main_worktree_mutated_by_run
            and not secret_in_diff
            and not commit_attempted
            and not merge_head_present
            and result.get("current_codex_home_used") is False
            and result.get("secret_value_recorded") is False
            and not setup_error
        )
        if success:
            final_status = "API_ONLY_DEEPSEEK_PRODUCT_SAFE_WORKTREE_CODER_READY_WITH_LIMITS"
            machine_error_code = "OK"
            safe_worktree_status = "active"
        elif not safe_worktree_used or setup_error or result.get("workspace_write_admitted") is not True:
            final_status = "KNOWN_BLOCKER_SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE"
            machine_error_code = "SAFE_WORKTREE_PRODUCT_WRITE_NOT_ADMISSIBLE"
            safe_worktree_status = "blocked"
        elif not diff_present or not changed_files:
            final_status = "KNOWN_BLOCKER_PRODUCT_CODER_DIFF_NOT_PROVEN"
            machine_error_code = "PRODUCT_CODER_DIFF_NOT_PROVEN"
            safe_worktree_status = "active"
        else:
            final_status = "KNOWN_BLOCKER_DEEPSEEK_PRODUCT_CODER_TOOL_CALL_FAILED"
            machine_error_code = "DEEPSEEK_PRODUCT_CODER_TOOL_CALL_FAILED"
            safe_worktree_status = "active" if safe_worktree_used else "blocked"

        if safe_worktree_used:
            self._product_worktrees[worktree_id] = {
                "worktree_id": worktree_id,
                "owner": "wbp",
                "session_id": session_id,
                "model_id": model_id,
                "created_at_utc": utc_now(),
                "status": safe_worktree_status,
                "path": str(worktree_dir),
                "parent_path": str(parent_dir),
                "repo_root": str(repo),
                "path_redacted": True,
            }
        return {
            **self._base_packet("ok" if success else "blocked", machine_error_code),
            "final_status": final_status,
            "execution_mode": "api_only",
            "session_id": session_id,
            "worktree_id": worktree_id if safe_worktree_used else "",
            "worktree_owner": "wbp" if safe_worktree_used else "none",
            "path_redacted": True,
            "model_id": model_id,
            "provider_id": "deepseek" if "deepseek" in model_id else "external_route",
            "current_execution_slot_id": PRIMARY_MODEL_SLOT,
            "selected_source_class": slot.get("selected_source_class"),
            "selected_from_server_catalog": slot.get("server_issued") is True,
            "task_preview": _safe_preview(task),
            "provider_response_proven": provider_response_proven,
            "fallback_attempted": False,
            "tool_loop_proven": tool_loop_proven,
            "request_count": request_count if isinstance(request_count, int) else 0,
            "safe_worktree_used": safe_worktree_used,
            "safe_worktree_status": safe_worktree_status,
            "cleanup_required": safe_worktree_used and safe_worktree_status != "cleaned",
            "browser_worktree_path_intake": False,
            "browser_backend_intake": False,
            "write_surface": "safe_worktree_only",
            "danger_full_access_admitted": False,
            "diff_present": diff_present,
            "changed_files": changed_files[:50],
            "changed_file_count": len(changed_files),
            "diff_text_bounded": redact_text(diff_text)[:20000],
            "git_diff_sha256": _digest(diff_text) if diff_text else "",
            "main_worktree_mutated_by_run": main_worktree_mutated_by_run,
            "secret_value_recorded": result.get("secret_value_recorded") is True,
            "secret_in_diff": secret_in_diff,
            "original_codex_touched": False,
            "original_codex_profile_touched": False,
            "current_codex_touched": result.get("current_codex_home_used") is True,
            "wbp_patch_applier_used": False,
            "commit_attempted": commit_attempted,
            "push_attempted": False if push_attempt_absent_proven else "not_proven",
            "push_attempt_absent_proven": push_attempt_absent_proven,
            "merge_attempted": merge_head_present,
            "workspace_write_admitted": result.get("workspace_write_admitted") is True,
            "working_dir_override_admitted": result.get("working_dir_override_admitted") is True,
            "working_dir_scope": str(result.get("working_dir_scope") or ""),
            "live_product_code_edit_claimed": success,
            "response_preview_bounded": _response_preview(response_text),
            "setup_error_bounded": setup_error,
            "trace_observer_packet": trace_packet,
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
        }

    def safe_worktree_cleanup_packet(
        self,
        worktree_id: str,
    ) -> dict[str, Any]:
        if not SESSION_ID_RE.match(str(worktree_id or "")):
            return {
                **self._base_packet("rejected", "WORKTREE_ID_INVALID"),
                "worktree_id": worktree_id,
                "path_intake": False,
                "cleanup_performed": False,
            }
        record = self._product_worktrees.get(worktree_id)
        if not record:
            return {
                **self._base_packet("rejected", "WORKTREE_NOT_FOUND"),
                "worktree_id": worktree_id,
                "path_intake": False,
                "cleanup_performed": False,
            }
        repo = Path(str(record.get("repo_root") or "")).resolve()
        worktree_dir = Path(str(record.get("path") or "")).resolve()
        parent_dir = Path(str(record.get("parent_path") or "")).resolve()
        temp_root_parent = Path(tempfile.gettempdir()).resolve()
        if temp_root_parent not in worktree_dir.parents or temp_root_parent not in parent_dir.parents:
            return {
                **self._base_packet("blocked", "WORKTREE_PATH_NOT_OWNED_BY_WBP"),
                "worktree_id": worktree_id,
                "path_intake": False,
                "cleanup_performed": False,
            }
        cleanup_error = ""
        if worktree_dir.exists():
            removed = _run_git_command(repo, ["worktree", "remove", "--force", str(worktree_dir)], timeout_seconds=60)
            if not removed["ok"]:
                cleanup_error = str(removed.get("stderr") or removed.get("stdout") or "")[:240]
        try:
            shutil.rmtree(parent_dir)
        except OSError as exc:
            cleanup_error = cleanup_error or f"{type(exc).__name__}: {str(exc)[:160]}"
        worktree_list = _run_git_command(repo, ["worktree", "list", "--porcelain"])
        removed_after_cleanup = (
            not worktree_dir.exists()
            and str(worktree_dir) not in str(worktree_list.get("stdout") or "")
            and not cleanup_error
        )
        record["status"] = "cleaned" if removed_after_cleanup else "cleanup_failed"
        return {
            **self._base_packet("ok" if removed_after_cleanup else "blocked", "OK" if removed_after_cleanup else "PRODUCT_CODER_CLEANUP_FAILED"),
            "final_status": (
                "API_ONLY_DEEPSEEK_PRODUCT_SAFE_WORKTREE_CODER_CLEANED"
                if removed_after_cleanup
                else "KNOWN_BLOCKER_PRODUCT_CODER_CLEANUP_FAILED"
            ),
            "worktree_id": worktree_id,
            "worktree_owner": "wbp",
            "path_intake": False,
            "path_redacted": True,
            "cleanup_performed": removed_after_cleanup,
            "safe_worktree_status": record["status"],
            "worktree_removed_after_cleanup": removed_after_cleanup,
            "cleanup_error": cleanup_error,
        }

    def transcript_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        entries = list(session.get("ledger") or [])
        model_response_present = any(entry.get("model_response_present") is True for entry in entries)
        inference_proven = any(entry.get("inference_proven") is True for entry in entries)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "transcript_kind": "service_ledger_only",
            "model_response_present": model_response_present,
            "inference_proven": inference_proven,
            "raw_prompt_not_stored": True,
            "raw_response_not_stored": True,
            "raw_backend_id_exposed": False,
            "raw_auth_ref_exposed": False,
            "network_calls_made": inference_proven,
            "provider_called": inference_proven,
            "token_burn": session.get("token_burn") if session.get("token_burn") is not None else 0,
            "entries": entries,
            "next_action": "none",
        }

    def cancel_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        if session.get("cleanup_state") == "cleaned":
            return {
                **self._base_packet("rejected", "SESSION_ALREADY_CLEANED"),
                "session_id": session_id,
                "process_kill_claimed": False,
                "next_action": "create_session",
            }
        session["cancel_state"] = "cancelled_dry_run_session"
        session["status"] = "cancelled"
        session["updated_at_utc"] = utc_now()
        self._append_ledger(session, "cancel_requested", {"process_kill_claimed": False})
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "cancelled": True,
            "process_kill_claimed": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "cleanup_session",
        }

    def cleanup_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        session_root = Path(str(session.get("session_root") or "")).resolve()
        if not self._is_owned_session_path(session_root):
            return {
                **self._base_packet("failed", "SESSION_ROOT_OUTSIDE_APPROVED_ROOT"),
                "session_id": session_id,
                "cleanup_performed": False,
                "next_action": "stop_and_diagnose",
            }
        existed_before = session_root.exists()
        if existed_before:
            shutil.rmtree(session_root)
        session["cleanup_state"] = "cleaned"
        session["status"] = "cleaned"
        session["updated_at_utc"] = utc_now()
        self._append_ledger(
            session,
            "cleanup_completed",
            {"session_root_existed_before": existed_before, "session_root_exists_after": False},
        )
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "cleanup_performed": True,
            "session_root_existed_before": existed_before,
            "session_root_exists_after": session_root.exists(),
            "session_root_removed_or_marked_cleaned": True,
            "owned_session_root_only": True,
            "deleted_path_scope": "owned_temp_session_root",
            "arbitrary_path_accepted": False,
            "current_codex_home_touched": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "none",
        }

    def _slot_bindings_from_payload(
        self,
        slot_model_ids: dict[str, str],
        commands: dict[str, dict[str, Any]],
        operator_status: dict[str, Any] | None,
        *,
        api_snapshot: dict[str, Any] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
        selector_index = _selector_entry_index(operator_status, api_snapshot=api_snapshot)
        bound_slots: dict[str, dict[str, Any]] = {}
        for slot_id, model_id in slot_model_ids.items():
            entry = selector_index.get(model_id)
            if entry is None:
                return {}, {
                    **self._base_packet("rejected", "MODEL_NOT_SERVER_ISSUED"),
                    "human_message": "Session slot binding accepts only server-issued current-catalog model ids.",
                    "slot_id": slot_id,
                    "model_id": model_id,
                    "session_created": False,
                    "next_action": "choose_server_issued_slot_model",
                }
            if entry.get("selection_enabled") is not True:
                disabled_reason_code = str(entry.get("selection_disabled_reason_code") or "")
                return {}, {
                    **self._base_packet(
                        "rejected",
                        "HEURISTIC_ONLY_NOT_EXECUTABLE"
                        if disabled_reason_code == "HEURISTIC_ONLY_NOT_EXECUTABLE"
                        else "MODEL_NOT_SELECTABLE",
                    ),
                    "human_message": "Session slot binding accepts only selectable current-catalog model ids.",
                    "slot_id": slot_id,
                    "model_id": model_id,
                    "selection_disabled_reason_code": disabled_reason_code,
                    "selection_packet": entry,
                    "session_created": False,
                    "next_action": "choose_selectable_slot_model",
                }
            selection = _selection_packet_for_slot(
                model_id,
                commands,
                operator_status,
                api_snapshot,
            )
            if selection.get("selection_proven") is not True:
                next_action = (
                    "repair_account_selection_truth"
                    if selection.get("model_lane") == CODEX_ACCOUNT_MODEL_LANE
                    else "repair_slot_selection_truth"
                )
                return {}, {
                    **self._base_packet(
                        "rejected",
                        str(selection.get("machine_error_code") or "SLOT_SELECTION_NOT_PROVEN"),
                    ),
                    "human_message": "Session slot binding requires server-issued slot selection proof.",
                    "slot_id": slot_id,
                    "model_id": model_id,
                    "selection_proven": False,
                    "session_created": False,
                    "selection_packet": self._selection_summary(selection),
                    "next_action": next_action,
                }
            bound_slots[slot_id] = _bound_slot(
                slot_id=slot_id,
                model_id=model_id,
                lane_kind=str(entry.get("lane_kind") or "unknown"),
                binding_source="browser_payload_server_validated",
                selection=selection,
            )
        return bound_slots, None

    def _load_existing_sessions(self) -> None:
        for session_root in sorted(self.root.iterdir()):
            if not session_root.is_dir():
                continue
            session_file = session_root / "session.json"
            if not session_file.exists():
                continue
            try:
                session = self._load_session_state(session_root)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            session_id = str(session.get("session_id") or "")
            if session_id:
                self._sessions[session_id] = session

    def _load_session_state(self, session_root: Path) -> dict[str, Any]:
        payload = json.loads((session_root / "session.json").read_text(encoding="utf-8"))
        public_session = payload.get("session") if isinstance(payload, dict) else None
        if not isinstance(public_session, dict):
            raise ValueError("session payload missing public session")
        ledger = payload.get("ledger") if isinstance(payload.get("ledger"), list) else []
        public_role_slots = (
            public_session.get("role_slots")
            if isinstance(public_session.get("role_slots"), dict)
            else None
        )
        migrated = public_role_slots is None
        bound_slots: dict[str, dict[str, Any]] = {}
        if isinstance(public_role_slots, dict):
            for slot_id in ROLE_SLOT_IDS:
                raw_slot = public_role_slots.get(slot_id)
                if not isinstance(raw_slot, dict):
                    continue
                model_id = str(raw_slot.get("model_id") or "")
                if model_id:
                    bound_slots[slot_id] = {
                        **_bound_slot(
                            slot_id=slot_id,
                            model_id=model_id,
                            lane_kind=str(raw_slot.get("lane_kind") or "unknown"),
                            binding_source=str(
                                raw_slot.get("binding_source") or "persisted_session_state"
                            ),
                            selection=raw_slot,
                        ),
                        "runtime_dispatch_state": str(
                            raw_slot.get("runtime_dispatch_state")
                            or "unresolved_in_this_contour"
                        ),
                        "persisted": raw_slot.get("persisted") is not False,
                        "persisted_source": str(
                            raw_slot.get("persisted_source") or "session_state_file"
                        ),
                    }
        else:
            legacy_model_id = str(public_session.get("model_id") or "")
            if legacy_model_id:
                bound_slots[PRIMARY_MODEL_SLOT] = _bound_slot(
                    slot_id=PRIMARY_MODEL_SLOT,
                    model_id=legacy_model_id,
                    lane_kind=str(public_session.get("selected_source_class") or "unknown"),
                    binding_source="legacy_single_model_migration",
                    selection=public_session,
                )
        role_slots = _canonical_role_slots(bound_slots)
        primary_model_id = _primary_model_id_from_role_slots(role_slots)
        session = {
            "session_id": str(public_session.get("session_id") or session_root.name),
            "created_at_utc": public_session.get("created_at_utc"),
            "updated_at_utc": public_session.get("updated_at_utc"),
            "status": public_session.get("status"),
            "session_schema_version": SESSION_SCHEMA_VERSION,
            "migration_status": (
                "legacy_single_model_migrated" if migrated else str(public_session.get("migration_status") or "native_multi_slot_schema")
            ),
            "legacy_single_model_migrated": migrated,
            "role_slots": role_slots,
            "current_execution_slot_id": str(
                public_session.get("current_execution_slot_id") or PRIMARY_MODEL_SLOT
            ),
            "current_execution_path_source": str(
                public_session.get("current_execution_path_source")
                or "session_primary_model_slot"
            ),
            "model_id": primary_model_id,
            "model_server_issued": public_session.get("model_server_issued") is True or bool(primary_model_id),
            "role_slot_binding_proven": True,
            "slot_catalog_revalidated": False,
            "slot_binding_runtime_dispatch_claimed": False,
            "selected_source_class": public_session.get("selected_source_class"),
            "selected_backend_ref": str(public_session.get("selected_backend_digest") or ""),
            "selected_backend_server_issued": public_session.get("selected_backend_server_issued") is True,
            "selected_route_ref": str(public_session.get("selected_route_digest") or ""),
            "selected_route_server_issued": public_session.get("selected_route_server_issued") is True,
            "route_provenance_required": public_session.get("route_provenance_required") is True,
            "route_provenance_proven": public_session.get("route_provenance_proven") is True,
            "api_model_selected_by_user": public_session.get("api_model_selected_by_user") is True,
            "route_selected_by_user": public_session.get("route_selected_by_user") is True,
            "browser_selected_route": public_session.get("browser_selected_route") is True,
            "route_candidate_source": str(public_session.get("route_candidate_source") or "none"),
            "route_candidate_classified": public_session.get("route_candidate_classified") is True,
            "route_static_readiness_classified": (
                public_session.get("route_static_readiness_classified") is True
                or (
                    public_session.get("selected_route_server_issued") is True
                    and public_session.get("route_provenance_required") is True
                )
            ),
            "route_execution_proven": public_session.get("route_execution_proven") is True,
            "provider_response_proven": public_session.get("provider_response_proven") is True,
            "secret_validity_proven": public_session.get("secret_validity_proven") is True,
            "raw_route_exposed": public_session.get("raw_route_exposed") is True,
            "raw_secret_ref_exposed": public_session.get("raw_secret_ref_exposed") is True,
            "source_provenance_status": str(public_session.get("source_provenance_status") or "not_proven"),
            "model_selected_by_user": public_session.get("model_selected_by_user") is True,
            "role_slot_selected_by_user": public_session.get("role_slot_selected_by_user") is True,
            "account_selected_by_user": public_session.get("account_selected_by_user") is True,
            "browser_selected_backend": public_session.get("browser_selected_backend") is True,
            "account_candidate_source": str(public_session.get("account_candidate_source") or "none"),
            "account_execution_proven": public_session.get("account_execution_proven") is True,
            "runtime_execution_proven": public_session.get("runtime_execution_proven") is True,
            "live_compatibility_proven": public_session.get("live_compatibility_proven") is True,
            "raw_backend_exposed": public_session.get("raw_backend_exposed") is True,
            "raw_backend_id_exposed": public_session.get("raw_backend_id_exposed") is True,
            "selection_dry_run_proven": public_session.get("selection_dry_run_proven") is True,
            "live_selection_proven": public_session.get("live_selection_proven") is True,
            "selection_proven": public_session.get("selection_proven") is True,
            "selection_machine_error_code": public_session.get("selection_machine_error_code"),
            "session_root": str(session_root.resolve()),
            "codex_home": str((session_root / "codex-home").resolve()),
            "workdir": str((session_root / "workdir").resolve()),
            "ledger": ledger,
            "prompt_admission_count": int(public_session.get("prompt_admission_count") or 0),
            "cleanup_state": public_session.get("cleanup_state") or "not_cleaned",
            "cancel_state": public_session.get("cancel_state") or "not_cancelled",
            "model_response_present": public_session.get("model_response_present") is True,
            "inference_proven": public_session.get("inference_proven") is True,
            "token_burn": public_session.get("token_burn"),
        }
        if migrated:
            self._write_session(session)
        return session

    def _role_slot_binding_packet(self, session: dict[str, Any]) -> dict[str, Any]:
        role_slots = _canonical_role_slots(session.get("role_slots"))
        bound_count = sum(1 for slot in role_slots.values() if slot.get("binding_status") == "bound")
        return {
            "session_schema_version": int(session.get("session_schema_version") or SESSION_SCHEMA_VERSION),
            "role_slot_binding_present": bound_count > 0,
            "role_slot_binding_count": bound_count,
            "slot_catalog_revalidated": session.get("slot_catalog_revalidated") is True,
            "current_execution_slot_id": str(
                session.get("current_execution_slot_id") or PRIMARY_MODEL_SLOT
            ),
            "current_execution_path_source": str(
                session.get("current_execution_path_source") or "session_primary_model_slot"
            ),
            "runtime_execution_truth_closed_here": False,
            "role_slots": role_slots,
        }

    def _append_ledger(
        self,
        session: dict[str, Any],
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "event": event,
            "captured_at_utc": utc_now(),
            "session_id": session["session_id"],
        }
        if payload:
            entry.update(payload)
        session.setdefault("ledger", []).append(entry)

    def _write_session(self, session: dict[str, Any]) -> None:
        root = Path(str(session["session_root"])).resolve()
        if not self._is_owned_session_path(root):
            raise ValueError("session root outside approved root")
        payload = {
            "session_schema_version": int(session.get("session_schema_version") or SESSION_SCHEMA_VERSION),
            "session": self._public_session(session),
            "ledger": session.get("ledger", []),
        }
        (root / "session.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (root / "ledger.jsonl").write_text(
            "".join(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n" for entry in session.get("ledger", [])),
            encoding="utf-8",
        )
        (root / "transcript.jsonl").write_text(
            "".join(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n" for entry in session.get("ledger", [])),
            encoding="utf-8",
        )

    def _public_session(self, session: dict[str, Any]) -> dict[str, Any]:
        session_id = str(session["session_id"])
        selected_backend_ref = str(session.get("selected_backend_ref") or "")
        session_root = str(session.get("session_root") or "")
        codex_home = str(session.get("codex_home") or "")
        role_slots = _canonical_role_slots(session.get("role_slots"))
        primary_model_id = _primary_model_id_from_role_slots(role_slots)
        bound_slot_count = sum(
            1 for slot in role_slots.values() if slot.get("binding_status") == "bound"
        )
        return {
            "session_schema_version": int(session.get("session_schema_version") or SESSION_SCHEMA_VERSION),
            "session_id": session_id,
            "created_at_utc": session.get("created_at_utc"),
            "updated_at_utc": session.get("updated_at_utc"),
            "status": session.get("status"),
            "migration_status": str(session.get("migration_status") or "native_multi_slot_schema"),
            "legacy_single_model_migrated": session.get("legacy_single_model_migrated") is True,
            "current_execution_slot_id": str(
                session.get("current_execution_slot_id") or PRIMARY_MODEL_SLOT
            ),
            "current_execution_path_source": str(
                session.get("current_execution_path_source") or "session_primary_model_slot"
            ),
            "model_id": primary_model_id,
            "model_server_issued": session.get("model_server_issued") is True,
            "model_catalog_entry_server_issued": session.get("model_catalog_entry_server_issued")
            is True,
            "model_lane": str(session.get("model_lane") or "unknown_lane"),
            "model_lane_classified": session.get("model_lane_classified") is True,
            "model_lane_classification_source": str(
                session.get("model_lane_classification_source") or "none"
            ),
            "model_lane_fallback_used": session.get("model_lane_fallback_used") is True,
            "model_lane_proof_level": str(session.get("model_lane_proof_level") or "unclassified"),
            "runtime_lane_proven": session.get("runtime_lane_proven") is True,
            "role_slot_binding_proven": session.get("role_slot_binding_proven") is True,
            "slot_catalog_revalidated": session.get("slot_catalog_revalidated") is True,
            "slot_binding_runtime_dispatch_claimed": False,
            "role_slot_binding_count": bound_slot_count,
            "role_slots": role_slots,
            "selected_source_class": session.get("selected_source_class"),
            "selected_backend_digest": selected_backend_ref,
            "selected_backend_id_redacted": True,
            "selected_backend_server_issued": session.get("selected_backend_server_issued") is True,
            "selected_route_digest": str(session.get("selected_route_ref") or ""),
            "selected_route_server_issued": session.get("selected_route_server_issued") is True,
            "route_provenance_required": session.get("route_provenance_required") is True,
            "route_provenance_proven": session.get("route_provenance_proven") is True,
            "api_model_selected_by_user": session.get("api_model_selected_by_user") is True,
            "route_selected_by_user": session.get("route_selected_by_user") is True,
            "browser_selected_route": session.get("browser_selected_route") is True,
            "route_candidate_source": str(session.get("route_candidate_source") or "none"),
            "route_candidate_classified": session.get("route_candidate_classified") is True,
            "route_static_readiness_classified": session.get("route_static_readiness_classified")
            is True,
            "route_execution_proven": session.get("route_execution_proven") is True,
            "provider_response_proven": session.get("provider_response_proven") is True,
            "secret_validity_proven": session.get("secret_validity_proven") is True,
            "raw_route_exposed": False,
            "raw_secret_ref_exposed": False,
            "source_provenance_status": _source_provenance_status(session),
            "source_candidate_classified": _source_candidate_classified(session),
            "source_provenance_proven": session.get("inference_proven") is True,
            "model_selected_by_user": session.get("model_selected_by_user") is True,
            "role_slot_selected_by_user": session.get("role_slot_selected_by_user") is True,
            "account_selected_by_user": session.get("account_selected_by_user") is True,
            "browser_selected_backend": session.get("browser_selected_backend") is True,
            "account_candidate_source": str(session.get("account_candidate_source") or "none"),
            "account_execution_proven": session.get("account_execution_proven") is True,
            "runtime_execution_proven": session.get("runtime_execution_proven") is True,
            "live_compatibility_proven": session.get("live_compatibility_proven") is True,
            "raw_backend_exposed": False,
            "raw_backend_id_exposed": False,
            "selection_dry_run_proven": session.get("selection_dry_run_proven") is True,
            "live_selection_proven": session.get("live_selection_proven") is True,
            "selection_proven": session.get("selection_proven") is True,
            "selection_machine_error_code": session.get("selection_machine_error_code"),
            "session_root_digest": _digest(session_root) if session_root else "",
            "codex_home_digest": _digest(codex_home) if codex_home else "",
            "session_root_scope": "owned_temp_session_root",
            "current_codex_home_used": False,
            "prompt_admission_count": int(session.get("prompt_admission_count") or 0),
            "cleanup_state": session.get("cleanup_state"),
            "cancel_state": session.get("cancel_state"),
            "ledger_entry_count": len(session.get("ledger") or []),
            "model_response_present": session.get("model_response_present") is True,
            "inference_proven": session.get("inference_proven") is True,
            "runtime_meter_attached": False,
            "network_calls_made": session.get("inference_proven") is True,
            "provider_called": session.get("inference_proven") is True,
            "token_burn": session.get("token_burn") if session.get("token_burn") is not None else 0,
        }

    def _prompt_precondition_failure(
        self,
        session: dict[str, Any],
        requested_slot_id: str,
    ) -> dict[str, Any] | None:
        session_id = str(session.get("session_id") or "")
        failures: list[str] = []
        role_slots = _canonical_role_slots(session.get("role_slots"))
        target_slot = dict(role_slots.get(requested_slot_id) or _unbound_slot(requested_slot_id))
        slot_dispatch_admission = _slot_dispatch_admission_packet(
            session=session,
            slot=target_slot,
            requested_slot_id=requested_slot_id,
        )
        if session.get("cleanup_state") == "cleaned":
            failures.append("SESSION_ALREADY_CLEANED")
        if str(session.get("status") or "") not in PROMPT_RUN_ALLOWED_STATUSES:
            failures.append("SESSION_STATUS_NOT_RUNNABLE")
        if target_slot.get("binding_status") != "bound":
            failures.append("SLOT_NOT_BOUND")
        if target_slot.get("server_issued") is not True:
            failures.append("MODEL_NOT_SERVER_ISSUED")
        if session.get("slot_catalog_revalidated") is not True:
            failures.append("SLOT_CATALOG_REVALIDATION_REQUIRED")
        if target_slot.get("selection_proven") is not True:
            failures.append("SELECTION_NOT_PROVEN")
        route_required = target_slot.get("route_provenance_required") is True
        if route_required:
            if target_slot.get("selected_route_server_issued") is not True:
                failures.append("ROUTE_NOT_SERVER_ISSUED")
            if target_slot.get("route_static_readiness_classified") is not True:
                failures.append("ROUTE_STATIC_READINESS_MISSING")
        elif target_slot.get("selected_backend_server_issued") is not True:
            failures.append("BACKEND_NOT_SERVER_ISSUED")
        if not failures:
            return None
        return {
            **self._base_packet("rejected", failures[0]),
            "session_id": session_id,
            "requested_slot_id": requested_slot_id,
            "current_execution_slot_id": str(
                session.get("current_execution_slot_id") or PRIMARY_MODEL_SLOT
            ),
            "current_execution_path_source": str(
                session.get("current_execution_path_source") or "session_primary_model_slot"
            ),
            "precondition_failures": failures,
            **slot_dispatch_admission,
            "wbp_runner_payload_slot_id": "",
            "wbp_runner_payload_model_id": "",
            "wbp_runner_payload_slot_matches_requested": False,
            "wbp_runner_payload_model_matches_slot": False,
            "wbp_session_manager_slot_dispatch_proven": False,
            "runtime_slot_dispatch_proof_scope": "not_attempted_precondition_failed",
            "downstream_runner_slot_echo_present": False,
            "downstream_runner_slot_echo": "",
            "downstream_runner_slot_echo_matches_requested": False,
            "executed_slot_id": "",
            "executed_slot_model_id": "",
            "runtime_slot_dispatch_proven": False,
            "slot_binding_runtime_dispatch_claimed": False,
            "parallel_slot_execution_proven": False,
            "fanout_execution_proven": False,
            "model_response_present": False,
            "token_usage_present": False,
            "fallback_attempted": False,
            "session": self._public_session(session),
            "role_slot_binding_packet": self._role_slot_binding_packet(session),
            "next_action": "repair_session_preconditions",
        }

    def _selection_summary(self, selection: dict[str, Any]) -> dict[str, Any]:
        return {
            "selection_dry_run_proven": selection.get("selection_dry_run_proven") is True,
            "live_selection_proven": selection.get("live_selection_proven") is True,
            "selection_proven": selection.get("selection_proven") is True,
            "model_catalog_entry_server_issued": selection.get("model_catalog_entry_server_issued")
            is True,
            "model_lane": str(selection.get("model_lane") or "unknown_lane"),
            "model_lane_classified": selection.get("model_lane_classified") is True,
            "model_lane_classification_source": str(
                selection.get("model_lane_classification_source") or "none"
            ),
            "model_lane_fallback_used": selection.get("model_lane_fallback_used") is True,
            "model_lane_proof_level": str(selection.get("model_lane_proof_level") or "unclassified"),
            "runtime_lane_proven": selection.get("runtime_lane_proven") is True,
            "selected_source_class": selection.get("selected_source_class"),
            "selected_backend_digest": str(selection.get("selected_backend_ref") or ""),
            "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
            "selected_route_digest": str(selection.get("selected_route_ref") or ""),
            "selected_route_server_issued": selection.get("selected_route_server_issued") is True,
            "route_provenance_required": selection.get("route_provenance_required") is True,
            "route_provenance_proven": selection.get("route_provenance_proven") is True,
            "api_model_selected_by_user": selection.get("api_model_selected_by_user") is True,
            "route_selected_by_user": selection.get("route_selected_by_user") is True,
            "browser_selected_route": selection.get("browser_selected_route") is True,
            "route_candidate_source": str(selection.get("route_candidate_source") or "none"),
            "route_candidate_classified": selection.get("route_candidate_classified") is True,
            "route_static_readiness_classified": selection.get("route_static_readiness_classified")
            is True,
            "route_execution_proven": False,
            "provider_response_proven": False,
            "secret_validity_proven": False,
            "raw_route_exposed": False,
            "raw_secret_ref_exposed": False,
            "source_provenance_status": str(selection.get("source_provenance_status") or "not_proven"),
            "source_candidate_classified": selection.get("selection_proven") is True,
            "source_provenance_proven": False,
            "browser_selected_backend": selection.get("browser_selected_backend") is True,
            "model_selected_by_user": selection.get("model_selected_by_user") is True,
            "role_slot_selected_by_user": selection.get("role_slot_selected_by_user") is True,
            "account_selected_by_user": selection.get("account_selected_by_user") is True,
            "account_candidate_source": str(selection.get("account_candidate_source") or "none"),
            "account_execution_proven": False,
            "runtime_execution_proven": False,
            "live_compatibility_proven": False,
            "raw_backend_exposed": False,
            "raw_backend_id_exposed": False,
            "machine_error_code": selection.get("machine_error_code"),
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
        }

    def _slot_dispatch_probe_success(
        self,
        packet: dict[str, Any],
        *,
        requested_slot_id: str,
        expected_model_id: str,
        expected_provider: str,
        expected_source_provenance: str,
    ) -> bool:
        return bool(
            packet
            and packet.get("status") == "ok"
            and packet.get("session_id")
            and packet.get("requested_slot_id") == requested_slot_id
            and packet.get("executed_slot_id") == requested_slot_id
            and packet.get("wbp_runner_payload_slot_id") == requested_slot_id
            and packet.get("wbp_runner_payload_model_id") == expected_model_id
            and packet.get("runtime_selected_model") == expected_model_id
            and packet.get("configured_provider") == expected_provider
            and packet.get("selected_source_provenance") == expected_source_provenance
            and packet.get("runtime_slot_dispatch_proven") is True
            and packet.get("wbp_session_manager_slot_dispatch_proven") is True
            and packet.get("live_prompt_full_success") is True
            and packet.get("fallback_attempted") is False
        )

    def _slot_dispatch_probe_summary(self, packet: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": str(packet.get("status") or ""),
            "machine_error_code": str(packet.get("machine_error_code") or ""),
            "session_id": str(packet.get("session_id") or ""),
            "requested_slot_id": str(packet.get("requested_slot_id") or ""),
            "executed_slot_id": str(packet.get("executed_slot_id") or ""),
            "model_id": str(packet.get("model_id") or ""),
            "runtime_selected_model": str(packet.get("runtime_selected_model") or ""),
            "configured_provider": str(packet.get("configured_provider") or ""),
            "selected_source_provenance": str(packet.get("selected_source_provenance") or ""),
            "wbp_runner_payload_slot_id": str(packet.get("wbp_runner_payload_slot_id") or ""),
            "wbp_runner_payload_model_id": str(packet.get("wbp_runner_payload_model_id") or ""),
            "runtime_slot_dispatch_proven": packet.get("runtime_slot_dispatch_proven") is True,
            "live_prompt_full_success": packet.get("live_prompt_full_success") is True,
            "fallback_attempted": packet.get("fallback_attempted") is True,
        }

    def _is_owned_session_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            resolved.relative_to(self.root)
        except ValueError:
            return False
        return resolved != self.root

    def _base_packet(self, status: str, machine_error_code: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": status,
            "machine_error_code": machine_error_code,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
        }

    def _rejected(self, machine_error_code: str, forbidden: list[str]) -> dict[str, Any]:
        return {
            **self._base_packet("rejected", machine_error_code),
            "human_message": "Codex Custom session payload contains forbidden browser fields.",
            "forbidden_fields": forbidden,
            "session_created": False,
            "model_auto_selected": False,
            "fallback_used": False,
            "external_route_selected": False,
            "next_action": "remove_forbidden_browser_fields",
        }

    def _unknown_session(self) -> dict[str, Any]:
        return {
            **self._base_packet("rejected", "SESSION_NOT_FOUND"),
            "human_message": "Codex Custom session id is not known to the server registry.",
            "next_action": "create_session",
        }


__all__ = [
    "CodexCustomSessionManager",
    "forbidden_prompt_dry_run_fields",
    "forbidden_session_create_fields",
]
