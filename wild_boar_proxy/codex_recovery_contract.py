# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom recovery contract packets for the WBP web UI."""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from wild_boar_proxy.codex_launch_modes import utc_now


FORBIDDEN_BROWSER_FIELDS = [
    "backend_id",
    "route_id",
    "path",
    "snapshot_path",
    "rollback_target",
    "session_id",
    "pid",
    "process_id",
    "token",
    "auth",
    "api_key",
    "secret",
    "CODEX_HOME",
    "HOME",
]
ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE = "owned_generated_recovery_artifact"
ROLLBACK_POINT_ARTIFACT_KIND = "custom_codex_recovery_rollback_point"
ROLLBACK_POINT_MANIFEST_KIND = "custom_codex_recovery_rollback_point_manifest"
ROLLBACK_POINT_CREATE_CLAIM_SCOPE = "custom_codex_recovery_rollback_point_create_live_only"
ROLLBACK_POINT_VERIFY_CLAIM_SCOPE = "custom_codex_recovery_rollback_point_verify_only"
ROLLBACK_APPLY_ADMISSION_DRY_RUN_CLAIM_SCOPE = (
    "custom_codex_recovery_rollback_apply_admission_dry_run_only"
)
ROLLBACK_APPLY_LIVE_PREFLIGHT_CLAIM_SCOPE = (
    "custom_codex_recovery_rollback_apply_live_preflight_only"
)
ROLLBACK_APPLY_BOUNDED_LIVE_CLAIM_SCOPE = (
    "custom_codex_recovery_rollback_apply_bounded_live_only"
)
ROLLBACK_APPLY_RECEIPT_VERIFY_CLAIM_SCOPE = (
    "custom_codex_recovery_rollback_apply_receipt_verify_only"
)
STOP_CLEANUP_PREFLIGHT_CLAIM_SCOPE = "custom_codex_recovery_stop_cleanup_preflight_only"
STOP_CLEANUP_LIVE_CLAIM_SCOPE = "custom_codex_recovery_stop_cleanup_live_only"
PROCESS_KILL_PREFLIGHT_CLAIM_SCOPE = (
    "custom_codex_recovery_process_kill_preflight_only"
)
ROLLBACK_APPLY_RECEIPT_ARTIFACT_KIND = "custom_codex_recovery_rollback_apply_receipt"
ROLLBACK_APPLY_RECEIPT_VERIFY_EXTRA_FORBIDDEN_FIELDS = [
    "receipt_id",
    "receipt_path",
    "artifact_id",
    "artifact_path",
    "digest",
]
STOP_CLEANUP_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS = [
    "cleanup_path",
    "receipt_id",
    "receipt_path",
    "artifact_id",
    "artifact_path",
    "digest",
]
PROCESS_KILL_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS = [
    "cleanup_path",
    "process_path",
    "process_root",
    "process_command",
    "command",
    "argv",
    "executable",
    "receipt_id",
    "receipt_path",
    "artifact_id",
    "artifact_path",
    "digest",
]

ROLLBACK_POINT_ALLOWED_WRITE_SURFACES = {
    "owned_temp_session_root": {
        "owner": "codex_custom_session_manager",
        "scope": "server_owned_temp_session_root",
    },
    "owned_wbp_runtime_state": {
        "owner": "wbp_control_layer",
        "scope": "server_owned_wbp_runtime_state",
    },
    "owned_generated_recovery_artifact": {
        "owner": "wbp_control_layer",
        "scope": "server_owned_generated_recovery_artifact",
    },
}

ROLLBACK_POINT_FORBIDDEN_SURFACES = [
    "current_codex_home",
    "current_codex_process",
    "original_codex_profile",
    "host_codex_profile",
    "arbitrary_path",
    "auth_material",
    "token_store",
    "secret_file",
    "global_runtime_reset",
    "external_account_state",
    "external_api_route_secret",
]


def _readonly_ok(packet: dict[str, Any] | None) -> bool:
    return (
        isinstance(packet, dict)
        and packet.get("status") == "ok"
        and packet.get("primary_truth_ok") is True
    )


def _status_ok(packet: dict[str, Any] | None) -> bool:
    return isinstance(packet, dict) and packet.get("status") == "ok"


def _action(
    action_id: str,
    label: str,
    *,
    owner: str,
    layer: str,
    status: str,
    mutation_allowed: bool,
    browser_payload_allowed: bool,
    disabled_reason_code: str,
    required_proof_for_live: list[str],
    claim_scope: str,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "owner": owner,
        "layer": layer,
        "status": status,
        "mutation_allowed": mutation_allowed,
        "browser_payload_allowed": browser_payload_allowed,
        "disabled_reason_code": disabled_reason_code,
        "required_proof_for_live": required_proof_for_live,
        "claim_scope": claim_scope,
    }


def _actions() -> list[dict[str, Any]]:
    return [
        _action(
            "stop_selected_custom_session",
            "Stop selected custom session",
            owner="codex_custom_session_manager",
            layer="session_manager",
            status="admitted",
            mutation_allowed=True,
            browser_payload_allowed=False,
            disabled_reason_code="",
            required_proof_for_live=[
                "server_selected_session_id",
                "session_manager_cancel_packet",
                "process_kill_claimed_false",
            ],
            claim_scope="selected_session_cancel_only",
        ),
        _action(
            "cleanup_owned_session_root",
            "Cleanup owned session root",
            owner="codex_custom_session_manager",
            layer="session_manager",
            status="admitted",
            mutation_allowed=True,
            browser_payload_allowed=False,
            disabled_reason_code="",
            required_proof_for_live=[
                "server_selected_session_id",
                "owned_session_root_only",
                "arbitrary_path_accepted_false",
                "current_codex_home_touched_false",
            ],
            claim_scope="owned_session_root_cleanup_only",
        ),
        _action(
            "isolation_check",
            "Isolation check",
            owner="codex_launch_modes",
            layer="control_layer_readonly",
            status="delegated_readonly",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="",
            required_proof_for_live=[
                "current_codex_touched_false",
                "original_codex_touched_false",
            ],
            claim_scope="readonly_status_packet_only",
        ),
        _action(
            "accounts_readonly_check",
            "Accounts readonly check",
            owner="accounts_readonly",
            layer="control_layer_readonly",
            status="delegated_readonly",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="",
            required_proof_for_live=[
                "accounts_status_ok",
                "primary_truth_ok_true",
            ],
            claim_scope="accounts_readonly_packet_only",
        ),
        _action(
            "api_readonly_check",
            "API readonly check",
            owner="api_connections_readonly",
            layer="control_layer_readonly",
            status="delegated_readonly",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="",
            required_proof_for_live=[
                "api_connections_status_ok",
                "primary_truth_ok_true",
            ],
            claim_scope="api_connections_readonly_packet_only",
        ),
        _action(
            "diagnostics_export",
            "Diagnostics export",
            owner="web_design_command_adapter",
            layer="support_artifact",
            status="delegated_readonly",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="support_artifact_only",
            required_proof_for_live=[
                "redacted_artifact",
                "support_artifact_only",
            ],
            claim_scope="support_artifact_only",
        ),
        _action(
            "wbp_down_classification",
            "WBP down classification",
            owner="status_healthcheck_delegated_readout",
            layer="runtime_truth_delegated",
            status="delegated_readonly",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="classification_only",
            required_proof_for_live=[
                "status_json_or_healthcheck_json_owner_packet",
                "no_cached_green",
            ],
            claim_scope="classification_only",
        ),
        _action(
            "auth_quota_credential_missing_classification",
            "Auth/quota/credential missing classification",
            owner="accounts_and_api_readonly_packets",
            layer="control_layer_readonly",
            status="delegated_readonly",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="classification_only",
            required_proof_for_live=[
                "accounts_or_api_machine_error_code",
                "no_secret_value_exposed",
            ],
            claim_scope="classification_only",
        ),
        _action(
            "rollback_readiness",
            "Rollback readiness",
            owner="not_admitted",
            layer="recovery_policy",
            status="dry_run_only",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="ROLLBACK_CONTRACT_NOT_ADMITTED",
            required_proof_for_live=[
                "rollback_point_contract",
                "declared_write_surfaces",
                "rollback_verification_packet",
            ],
            claim_scope="dry_run_readiness_only",
        ),
        _action(
            "stuck_process_kill_readiness",
            "Stuck process kill readiness",
            owner="not_admitted",
            layer="process_owner_policy",
            status="dry_run_only",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="PROCESS_KILL_CONTRACT_NOT_ADMITTED",
            required_proof_for_live=[
                "owned_process_identity",
                "current_codex_process_exclusion",
                "kill_result_packet",
            ],
            claim_scope="dry_run_readiness_only",
        ),
        _action(
            "cleanup_arbitrary_path",
            "Cleanup arbitrary path",
            owner="not_admitted",
            layer="filesystem_policy",
            status="disabled",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="ARBITRARY_PATH_FORBIDDEN",
            required_proof_for_live=[
                "not_allowed_by_current_contract",
            ],
            claim_scope="disabled_dangerous_action",
        ),
        _action(
            "touch_original_codex_profile",
            "Touch Original Codex profile",
            owner="forbidden",
            layer="protected_baseline",
            status="disabled",
            mutation_allowed=False,
            browser_payload_allowed=False,
            disabled_reason_code="ORIGINAL_CODEX_PROTECTED_BASELINE",
            required_proof_for_live=[
                "not_allowed_by_canon",
            ],
            claim_scope="disabled_dangerous_action",
        ),
    ]


def build_custom_recovery_contract_packet(
    *,
    original_status: dict[str, Any] | None,
    custom_status: dict[str, Any] | None,
    accounts_readonly: dict[str, Any] | None,
    api_readonly: dict[str, Any] | None,
) -> dict[str, Any]:
    original_ok = _status_ok(original_status)
    custom_ok = _status_ok(custom_status)
    accounts_ok = _readonly_ok(accounts_readonly)
    api_ok = _readonly_ok(api_readonly)
    readonly_sources_ok = original_ok and custom_ok and accounts_ok and api_ok
    return {
        "schema_version": 1,
        "status": "ok" if readonly_sources_ok else "blocked",
        "machine_error_code": "RECOVERY_CONTRACT_DRY_RUN_ONLY",
        "contract_block_reason_code": ""
        if readonly_sources_ok
        else "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
        "captured_at_utc": utc_now(),
        "claim_scope": "custom_codex_recovery_contract_dry_run_only",
        "contract_owner": "wbp_control_layer_contract_aggregator",
        "contract_endpoint": "/api/codex/custom/recovery/contract",
        "contract_aggregator_only": True,
        "contract_endpoint_mutation_allowed": False,
        "recovery_live_ready": False,
        "operator_ready_claimed": False,
        "rollback_claimed": False,
        "process_kill_claimed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "browser_forbidden_fields_rejected": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "fresh_truth": False,
        "historical_isolation_proof_only": True,
        "dangerous_actions_disabled": True,
        "diagnostics_support_artifact_only": True,
        "runtime_health_owner": "healthcheck_status_delegated_readout",
        "ui_role": "renderer_only",
        "readonly_sources": {
            "original_status_ok": original_ok,
            "custom_status_ok": custom_ok,
            "accounts_readonly_ok": accounts_ok,
            "api_readonly_ok": api_ok,
        },
        "actions": _actions(),
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS",
        "next_contour_precondition": (
            "Only actions with machine-backed owner contract and dry-run proof may be promoted."
        ),
    }


def _action_by_id(actions: list[dict[str, Any]], action_id: str) -> dict[str, Any]:
    for action in actions:
        if action.get("id") == action_id:
            return action
    return {}


def _admitted_session_action(action: dict[str, Any]) -> bool:
    return (
        action.get("status") == "admitted"
        and action.get("mutation_allowed") is True
        and action.get("browser_payload_allowed") is False
    )


def _non_admitted_mutation(action: dict[str, Any]) -> bool:
    return action.get("mutation_allowed") is True or action.get("browser_payload_allowed") is True


def _server_session_selection(
    sessions_packet: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, bool, str]:
    sessions = sessions_packet.get("sessions") if isinstance(sessions_packet, dict) else None
    if not isinstance(sessions, list):
        return None, False, "server_selected_latest_owned_custom_session"
    typed_sessions = [session for session in sessions if isinstance(session, dict)]
    candidates = [
        session for session in typed_sessions if str(session.get("cleanup_state") or "") != "cleaned"
    ]
    if not candidates:
        candidates = typed_sessions
    if not candidates:
        return None, False, "server_selected_latest_owned_custom_session"
    latest_created = max(str(session.get("created_at_utc") or "") for session in candidates)
    latest = [
        session for session in candidates if str(session.get("created_at_utc") or "") == latest_created
    ]
    if len(latest) > 1:
        return None, True, "server_selected_latest_owned_custom_session"
    return latest[0], False, "server_selected_latest_owned_custom_session"


def _server_selected_session(sessions_packet: dict[str, Any] | None) -> dict[str, Any] | None:
    selected, ambiguous, _source = _server_session_selection(sessions_packet)
    if ambiguous:
        return None
    return selected


def build_custom_recovery_admitted_session_actions_packet(
    *,
    contract_packet: dict[str, Any] | None,
    sessions_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the narrow readiness packet for admitted selected-session actions."""

    contract = contract_packet if isinstance(contract_packet, dict) else {}
    sessions = sessions_packet if isinstance(sessions_packet, dict) else {}
    readonly = contract.get("readonly_sources") if isinstance(contract.get("readonly_sources"), dict) else {}
    actions = contract.get("actions") if isinstance(contract.get("actions"), list) else []
    stop_action = _action_by_id(actions, "stop_selected_custom_session")
    cleanup_action = _action_by_id(actions, "cleanup_owned_session_root")
    rollback_action = _action_by_id(actions, "rollback_readiness")
    kill_action = _action_by_id(actions, "stuck_process_kill_readiness")
    arbitrary_cleanup_action = _action_by_id(actions, "cleanup_arbitrary_path")

    contract_readonly_ok = (
        contract.get("status") == "ok"
        and readonly.get("original_status_ok") is True
        and readonly.get("custom_status_ok") is True
        and readonly.get("accounts_readonly_ok") is True
        and readonly.get("api_readonly_ok") is True
    )
    admitted_actions_contract_ready = (
        _admitted_session_action(stop_action)
        and _admitted_session_action(cleanup_action)
        and not _non_admitted_mutation(rollback_action)
        and not _non_admitted_mutation(kill_action)
        and not _non_admitted_mutation(arbitrary_cleanup_action)
        and contract.get("rollback_claimed") is False
        and contract.get("process_kill_claimed") is False
        and contract.get("dangerous_actions_disabled") is True
        and contract.get("browser_payload_allowed") is False
    )

    selected_session, selected_session_ambiguous, selected_session_source = (
        _server_session_selection(sessions)
    )
    selected_session_present = selected_session is not None
    selected_session_packet_valid = (
        isinstance(selected_session, dict)
        and selected_session.get("session_root_scope") == "owned_temp_session_root"
        and selected_session.get("current_codex_home_used") is False
        and selected_session.get("model_server_issued") is True
        and selected_session.get("selection_proven") is True
    )
    selected_cleanup_state = (
        str(selected_session.get("cleanup_state") or "") if isinstance(selected_session, dict) else ""
    )
    selected_session_available = (
        selected_session_packet_valid
        and selected_cleanup_state != "cleaned"
        and not selected_session_ambiguous
    )
    selected_session_cancel_ready = (
        contract_readonly_ok and admitted_actions_contract_ready and selected_session_available
    )
    owned_session_cleanup_ready = (
        contract_readonly_ok and admitted_actions_contract_ready and selected_session_available
    )
    session_admitted_actions_ready = (
        selected_session_cancel_ready and owned_session_cleanup_ready
    )

    block_reason = ""
    if not contract_readonly_ok:
        block_reason = "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED"
    elif not admitted_actions_contract_ready:
        block_reason = "ADMITTED_SESSION_ACTION_CONTRACT_FAILED"
    elif sessions.get("status") != "ok":
        block_reason = "SESSIONS_PACKET_FAILED"
    elif selected_session_ambiguous:
        block_reason = "SELECTED_SESSION_AMBIGUOUS"
    elif not selected_session_present:
        block_reason = "SELECTED_SESSION_REQUIRED"
    elif not selected_session_packet_valid:
        block_reason = "SELECTED_SESSION_PACKET_INVALID"
    elif not selected_session_available:
        block_reason = "SELECTED_SESSION_ALREADY_CLEANED"

    return {
        "schema_version": 1,
        "status": "ok" if session_admitted_actions_ready else "blocked",
        "machine_error_code": (
            "ADMITTED_SESSION_ACTIONS_READY"
            if session_admitted_actions_ready
            else "ADMITTED_SESSION_ACTIONS_BLOCKED"
        ),
        "block_reason_code": block_reason,
        "captured_at_utc": utc_now(),
        "claim_scope": "custom_codex_recovery_admitted_session_actions_only",
        "contract_endpoint": "/api/codex/custom/recovery/admitted-session-actions",
        "contract_source_endpoint": "/api/codex/custom/recovery/contract",
        "session_source_endpoint": "/api/codex/custom/sessions",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "browser_forbidden_fields_rejected": True,
        "session_admitted_actions_ready": session_admitted_actions_ready,
        "admitted_session_actions_contract_ready": admitted_actions_contract_ready,
        "selected_session_required": True,
        "selected_session_present": selected_session_present,
        "selected_session_source": selected_session_source,
        "selected_session_id_redacted": selected_session_present,
        "selected_session_ambiguous": selected_session_ambiguous,
        "selected_session_id": selected_session.get("session_id") if isinstance(selected_session, dict) else "",
        "selected_session_packet_valid": selected_session_packet_valid,
        "selected_session_cleanup_state": selected_cleanup_state,
        "selected_session_cancel_ready": selected_session_cancel_ready,
        "owned_session_cleanup_ready": owned_session_cleanup_ready,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "diagnostics_support_artifact_only": True,
        "diagnostics_counted_as_recovery_action": False,
        "readonly_checks_counted_as_mutation": False,
        "session_create_counted_as_recovery_action": False,
        "contract_readonly_sources_ok": contract_readonly_ok,
        "readonly_sources": readonly,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "arbitrary_path_accepted": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "session_count": int(sessions.get("session_count") or 0),
        "actions": [
            {
                "id": stop_action.get("id") or "stop_selected_custom_session",
                "status": stop_action.get("status") or "missing",
                "mutation_allowed": stop_action.get("mutation_allowed") is True,
                "browser_payload_allowed": stop_action.get("browser_payload_allowed") is True,
                "ready": selected_session_cancel_ready,
            },
            {
                "id": cleanup_action.get("id") or "cleanup_owned_session_root",
                "status": cleanup_action.get("status") or "missing",
                "mutation_allowed": cleanup_action.get("mutation_allowed") is True,
                "browser_payload_allowed": cleanup_action.get("browser_payload_allowed") is True,
                "ready": owned_session_cleanup_ready,
            },
            {
                "id": rollback_action.get("id") or "rollback_readiness",
                "status": rollback_action.get("status") or "missing",
                "mutation_allowed": rollback_action.get("mutation_allowed") is True,
                "browser_payload_allowed": rollback_action.get("browser_payload_allowed") is True,
                "ready": False,
            },
            {
                "id": kill_action.get("id") or "stuck_process_kill_readiness",
                "status": kill_action.get("status") or "missing",
                "mutation_allowed": kill_action.get("mutation_allowed") is True,
                "browser_payload_allowed": kill_action.get("browser_payload_allowed") is True,
                "ready": False,
            },
        ],
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS",
        "next_contour_claimed": False,
    }


def _stop_cleanup_preflight_failure_packet(
    *,
    machine_error_code: str,
    block_reason_code: str,
    forbidden_fields: list[str] | None = None,
    filesystem_read_performed: bool = False,
    source_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = source_packet if isinstance(source_packet, dict) else {}
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": STOP_CLEANUP_PREFLIGHT_CLAIM_SCOPE,
        "verified_scope": "not_verified",
        "contract_endpoint": "/api/codex/custom/recovery/stop-cleanup/preflight",
        "contract_source_endpoint": "/api/codex/custom/recovery/admitted-session-actions",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": (
            FORBIDDEN_BROWSER_FIELDS + STOP_CLEANUP_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS
        ),
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "stop_cleanup_preflight_ready": False,
        "selected_session_source": source.get(
            "selected_session_source", "server_selected_latest_owned_custom_session"
        ),
        "selected_session_required": True,
        "selected_session_present": source.get("selected_session_present") is True,
        "selected_session_id_redacted": source.get("selected_session_present") is True,
        "selected_session_ambiguous": source.get("selected_session_ambiguous") is True,
        "selected_session_packet_valid": source.get("selected_session_packet_valid") is True,
        "selected_session_cleanup_state": str(source.get("selected_session_cleanup_state") or ""),
        "selected_session_cancel_ready": False,
        "owned_session_cleanup_ready": False,
        "arbitrary_path_cleanup_allowed": False,
        "process_kill_ready": False,
        "process_kill_performed": False,
        "session_cancel_performed": False,
        "owned_cleanup_performed": False,
        "filesystem_read_performed": filesystem_read_performed,
        "filesystem_write_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "recovery_operator_ready": False,
        "rollback_live_ready": False,
        "human_summary": "stop/cleanup preflight blocked · no action performed",
        "source_machine_error_code": source.get("machine_error_code", ""),
        "source_block_reason_code": source.get("block_reason_code", ""),
        "next_contour": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_PASS",
    }


def build_custom_recovery_stop_cleanup_preflight_packet(
    *,
    admitted_session_actions_packet: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    """Build a read-only stop/cleanup preflight derived from admitted session truth."""

    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(browser_payload)))
    if forbidden_payload_fields:
        return _stop_cleanup_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_BROWSER_FIELD_REJECTED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_BROWSER_FIELD_REJECTED",
            forbidden_fields=forbidden_payload_fields,
            filesystem_read_performed=False,
        )

    source = (
        admitted_session_actions_packet
        if isinstance(admitted_session_actions_packet, dict)
        else {}
    )
    source_status = str(source.get("status") or "")
    source_block_reason = str(source.get("block_reason_code") or "")
    source_ready = (
        source_status == "ok"
        and source.get("session_admitted_actions_ready") is True
        and source.get("selected_session_cancel_ready") is True
        and source.get("owned_session_cleanup_ready") is True
        and source.get("selected_session_packet_valid") is True
        and source.get("selected_session_ambiguous") is not True
        and str(source.get("selected_session_cleanup_state") or "") != "cleaned"
        and source.get("contract_endpoint_mutation_allowed") is False
        and source.get("browser_payload_allowed") is False
        and source.get("recovery_operator_ready") is False
        and source.get("process_kill_operator_ready") is False
        and source.get("process_kill_claimed") is False
        and source.get("current_codex_touched") is False
        and source.get("original_codex_touched") is False
        and source.get("current_codex_home_touched") is False
        and source.get("arbitrary_path_accepted") is False
    )
    if not source_ready:
        if source_block_reason == "SELECTED_SESSION_REQUIRED":
            machine_error_code = "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NO_SESSION"
        elif source_block_reason == "SELECTED_SESSION_ALREADY_CLEANED":
            machine_error_code = (
                "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_SESSION_ALREADY_CLEANED"
            )
        elif source_block_reason == "SELECTED_SESSION_AMBIGUOUS":
            machine_error_code = "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_AMBIGUOUS_SESSION"
        else:
            machine_error_code = "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_SOURCE_BLOCKED"
        return _stop_cleanup_preflight_failure_packet(
            machine_error_code=machine_error_code,
            block_reason_code=source_block_reason or machine_error_code,
            filesystem_read_performed=True,
            source_packet=source,
        )

    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_READY",
        "block_reason_code": "",
        "captured_at_utc": utc_now(),
        "claim_scope": STOP_CLEANUP_PREFLIGHT_CLAIM_SCOPE,
        "verified_scope": "owned_custom_session_stop_cleanup_preflight_only",
        "contract_endpoint": "/api/codex/custom/recovery/stop-cleanup/preflight",
        "contract_source_endpoint": "/api/codex/custom/recovery/admitted-session-actions",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": (
            FORBIDDEN_BROWSER_FIELDS + STOP_CLEANUP_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS
        ),
        "forbidden_fields": [],
        "browser_forbidden_fields_rejected": True,
        "stop_cleanup_preflight_ready": True,
        "selected_session_source": source.get(
            "selected_session_source", "server_selected_latest_owned_custom_session"
        ),
        "selected_session_required": True,
        "selected_session_present": True,
        "selected_session_id_redacted": True,
        "selected_session_ambiguous": False,
        "selected_session_packet_valid": True,
        "selected_session_cleanup_state": str(source.get("selected_session_cleanup_state") or ""),
        "selected_session_cancel_ready": True,
        "owned_session_cleanup_ready": True,
        "arbitrary_path_cleanup_allowed": False,
        "process_kill_ready": False,
        "process_kill_performed": False,
        "session_cancel_performed": False,
        "owned_cleanup_performed": False,
        "filesystem_read_performed": True,
        "filesystem_write_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "recovery_operator_ready": False,
        "rollback_live_ready": False,
        "source_machine_error_code": source.get("machine_error_code", ""),
        "source_block_reason_code": source.get("block_reason_code", ""),
        "human_summary": "stop/cleanup preflight verified · no action performed",
        "next_contour": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_PASS",
    }


def _stop_cleanup_live_failure_packet(
    *,
    machine_error_code: str,
    block_reason_code: str,
    preflight_packet: dict[str, Any] | None = None,
    cancel_packet: dict[str, Any] | None = None,
    cleanup_packet: dict[str, Any] | None = None,
    forbidden_fields: list[str] | None = None,
    preflight_selected_session_ref: str = "",
    live_selected_session_ref: str = "",
    cancel_selected_session_ref: str = "",
    cleanup_selected_session_ref: str = "",
    cleanup_attempted: bool = False,
    filesystem_write_performed: bool = False,
    next_action: str = "repair_stop_cleanup_preconditions",
) -> dict[str, Any]:
    preflight = preflight_packet if isinstance(preflight_packet, dict) else {}
    cancel = cancel_packet if isinstance(cancel_packet, dict) else {}
    cleanup = cleanup_packet if isinstance(cleanup_packet, dict) else {}
    cancel_performed = cancel.get("status") == "ok" and cancel.get("cancelled") is True
    cleanup_performed = (
        cleanup.get("status") == "ok" and cleanup.get("cleanup_performed") is True
    )
    refs = [
        ref
        for ref in (
            preflight_selected_session_ref,
            live_selected_session_ref,
            cancel_selected_session_ref,
            cleanup_selected_session_ref if cleanup_attempted else "",
        )
        if ref
    ]
    same_ref = bool(refs) and len(set(refs)) == 1
    return {
        "schema_version": 1,
        "status": "failed" if cancel_performed and not cleanup_performed else "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": STOP_CLEANUP_LIVE_CLAIM_SCOPE,
        "verified_scope": "not_verified",
        "declared_write_surface": "owned_temp_session_root_cleanup_only",
        "contract_endpoint": "/api/codex/custom/recovery/stop-cleanup",
        "contract_source_endpoint": "/api/codex/custom/recovery/stop-cleanup/preflight",
        "contract_endpoint_mutation_allowed": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": (
            FORBIDDEN_BROWSER_FIELDS + STOP_CLEANUP_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS
        ),
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "preflight_required": True,
        "preflight_verified": False,
        "selected_session_source": preflight.get(
            "selected_session_source", "server_selected_latest_owned_custom_session"
        ),
        "selected_session_id_redacted": True,
        "raw_session_id_omitted": True,
        "preflight_selected_session_ref_present": bool(preflight_selected_session_ref),
        "live_selected_session_ref_present": bool(live_selected_session_ref),
        "cancel_selected_session_ref_present": bool(cancel_selected_session_ref),
        "cleanup_selected_session_ref_present": bool(cleanup_selected_session_ref),
        "same_selected_session_ref": same_ref,
        "session_cancel_performed": cancel_performed,
        "session_cancel_verified": cancel_performed
        and cancel.get("process_kill_claimed") is False,
        "cleanup_attempted": cleanup_attempted,
        "owned_cleanup_performed": cleanup_performed,
        "owned_cleanup_verified": cleanup_performed
        and cleanup.get("owned_session_root_only") is True
        and cleanup.get("arbitrary_path_accepted") is False
        and cleanup.get("current_codex_home_touched") is False,
        "owned_session_root_only": cleanup.get("owned_session_root_only") is True,
        "arbitrary_path_cleanup_allowed": False,
        "arbitrary_path_accepted": cleanup.get("arbitrary_path_accepted") is True,
        "process_kill_ready": False,
        "process_kill_performed": False,
        "filesystem_write_performed": filesystem_write_performed,
        "filesystem_write_scope": (
            "owned_temp_session_root_cleanup_only" if filesystem_write_performed else ""
        ),
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "source_preflight_machine_error_code": preflight.get("machine_error_code", ""),
        "cancel_machine_error_code": cancel.get("machine_error_code", ""),
        "cleanup_machine_error_code": cleanup.get("machine_error_code", ""),
        "human_summary": "owned stop/cleanup blocked · not system recovery",
        "next_action": next_action,
        "next_contour": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_PASS",
        "next_contour_claimed": False,
    }


def _stop_cleanup_preflight_ready(packet: dict[str, Any]) -> bool:
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code")
        == "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_READY"
        and packet.get("stop_cleanup_preflight_ready") is True
        and packet.get("verified_scope")
        == "owned_custom_session_stop_cleanup_preflight_only"
        and packet.get("selected_session_id_redacted") is True
        and packet.get("selected_session_cancel_ready") is True
        and packet.get("owned_session_cleanup_ready") is True
        and packet.get("process_kill_performed") is False
        and packet.get("filesystem_write_performed") is False
        and packet.get("recovery_operator_ready") is False
        and packet.get("rollback_live_ready") is False
    )


def build_custom_recovery_stop_cleanup_live_packet(
    *,
    preflight_packet: dict[str, Any] | None = None,
    cancel_packet: dict[str, Any] | None = None,
    cleanup_packet: dict[str, Any] | None = None,
    preflight_selected_session_ref: str = "",
    live_selected_session_ref: str = "",
    cancel_selected_session_ref: str = "",
    cleanup_selected_session_ref: str = "",
    browser_payload: Any = None,
    cleanup_attempted: bool = False,
) -> dict[str, Any]:
    """Build the bounded live receipt for server-owned cancel and cleanup."""

    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(browser_payload)))
    if forbidden_payload_fields:
        return _stop_cleanup_live_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_BROWSER_FIELD_REJECTED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_BROWSER_FIELD_REJECTED",
            forbidden_fields=forbidden_payload_fields,
            next_action="remove_forbidden_browser_fields",
        )

    preflight = preflight_packet if isinstance(preflight_packet, dict) else {}
    if not _stop_cleanup_preflight_ready(preflight):
        return _stop_cleanup_live_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NOT_READY",
            block_reason_code=str(
                preflight.get("machine_error_code")
                or preflight.get("block_reason_code")
                or "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_REQUIRED"
            ),
            preflight_packet=preflight,
        )

    if (
        not preflight_selected_session_ref
        or not live_selected_session_ref
        or preflight_selected_session_ref != live_selected_session_ref
    ):
        return _stop_cleanup_live_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_SELECTED_SESSION_CHANGED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_SELECTED_SESSION_CHANGED",
            preflight_packet=preflight,
            preflight_selected_session_ref=preflight_selected_session_ref,
            live_selected_session_ref=live_selected_session_ref,
        )

    cancel = cancel_packet if isinstance(cancel_packet, dict) else {}
    cancel_ok = (
        cancel.get("status") == "ok"
        and cancel.get("cancelled") is True
        and cancel.get("process_kill_claimed") is False
        and cancel_selected_session_ref == live_selected_session_ref
    )
    if not cancel_ok:
        return _stop_cleanup_live_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_CANCEL_FAILED_BEFORE_CLEANUP",
            block_reason_code=str(
                cancel.get("machine_error_code")
                or cancel.get("status")
                or "CUSTOM_CODEX_RECOVERY_CANCEL_FAILED_BEFORE_CLEANUP"
            ),
            preflight_packet=preflight,
            cancel_packet=cancel,
            preflight_selected_session_ref=preflight_selected_session_ref,
            live_selected_session_ref=live_selected_session_ref,
            cancel_selected_session_ref=cancel_selected_session_ref,
            cleanup_attempted=False,
            next_action="diagnose_owned_session_cancel_failure",
        )

    cleanup = cleanup_packet if isinstance(cleanup_packet, dict) else {}
    cleanup_ok = (
        cleanup_attempted
        and cleanup.get("status") == "ok"
        and cleanup.get("cleanup_performed") is True
        and cleanup.get("owned_session_root_only") is True
        and cleanup.get("arbitrary_path_accepted") is False
        and cleanup.get("current_codex_home_touched") is False
        and cleanup_selected_session_ref == live_selected_session_ref
    )
    if not cleanup_ok:
        return _stop_cleanup_live_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_CLEANUP_FAILED_AFTER_CANCEL",
            block_reason_code=str(
                cleanup.get("machine_error_code")
                or cleanup.get("status")
                or "CUSTOM_CODEX_RECOVERY_CLEANUP_FAILED_AFTER_CANCEL"
            ),
            preflight_packet=preflight,
            cancel_packet=cancel,
            cleanup_packet=cleanup,
            preflight_selected_session_ref=preflight_selected_session_ref,
            live_selected_session_ref=live_selected_session_ref,
            cancel_selected_session_ref=cancel_selected_session_ref,
            cleanup_selected_session_ref=cleanup_selected_session_ref,
            cleanup_attempted=cleanup_attempted,
            filesystem_write_performed=True,
            next_action="diagnose_owned_cleanup_failure",
        )

    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_READY",
        "block_reason_code": "",
        "captured_at_utc": utc_now(),
        "claim_scope": STOP_CLEANUP_LIVE_CLAIM_SCOPE,
        "verified_scope": "owned_custom_session_cancel_and_cleanup_only",
        "declared_write_surface": "owned_temp_session_root_cleanup_only",
        "contract_endpoint": "/api/codex/custom/recovery/stop-cleanup",
        "contract_source_endpoint": "/api/codex/custom/recovery/stop-cleanup/preflight",
        "contract_endpoint_mutation_allowed": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": (
            FORBIDDEN_BROWSER_FIELDS + STOP_CLEANUP_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS
        ),
        "forbidden_fields": [],
        "browser_forbidden_fields_rejected": True,
        "preflight_required": True,
        "preflight_verified": True,
        "selected_session_source": preflight.get(
            "selected_session_source", "server_selected_latest_owned_custom_session"
        ),
        "selected_session_id_redacted": True,
        "raw_session_id_omitted": True,
        "preflight_selected_session_ref_present": True,
        "live_selected_session_ref_present": True,
        "cancel_selected_session_ref_present": True,
        "cleanup_selected_session_ref_present": True,
        "same_selected_session_ref": True,
        "session_cancel_performed": True,
        "session_cancel_verified": True,
        "cleanup_attempted": True,
        "owned_cleanup_performed": True,
        "owned_cleanup_verified": True,
        "owned_session_root_only": True,
        "arbitrary_path_cleanup_allowed": False,
        "arbitrary_path_accepted": False,
        "process_kill_ready": False,
        "process_kill_performed": False,
        "filesystem_write_performed": True,
        "filesystem_write_scope": "owned_temp_session_root_cleanup_only",
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "source_preflight_machine_error_code": preflight.get("machine_error_code", ""),
        "cancel_machine_error_code": cancel.get("machine_error_code", ""),
        "cleanup_machine_error_code": cleanup.get("machine_error_code", ""),
        "human_summary": "owned session cancelled and cleaned · not system recovery",
        "next_action": "none",
        "next_contour": "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_PASS",
        "next_contour_claimed": False,
    }


def build_custom_recovery_rollback_process_owner_contract_packet(
    *,
    contract_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the dry-run-only rollback/process-owner recovery contract."""

    contract = contract_packet if isinstance(contract_packet, dict) else {}
    readonly = contract.get("readonly_sources") if isinstance(contract.get("readonly_sources"), dict) else {}
    actions = contract.get("actions") if isinstance(contract.get("actions"), list) else []
    rollback_action = _action_by_id(actions, "rollback_readiness")
    kill_action = _action_by_id(actions, "stuck_process_kill_readiness")
    cleanup_path_action = _action_by_id(actions, "cleanup_arbitrary_path")
    touch_original_action = _action_by_id(actions, "touch_original_codex_profile")
    rollback_contract_defined = (
        rollback_action.get("status") == "dry_run_only"
        and rollback_action.get("mutation_allowed") is False
        and rollback_action.get("browser_payload_allowed") is False
    )
    process_owner_contract_defined = (
        kill_action.get("status") == "dry_run_only"
        and kill_action.get("mutation_allowed") is False
        and kill_action.get("browser_payload_allowed") is False
    )
    dangerous_actions_disabled = (
        not _non_admitted_mutation(rollback_action)
        and not _non_admitted_mutation(kill_action)
        and not _non_admitted_mutation(cleanup_path_action)
        and not _non_admitted_mutation(touch_original_action)
        and contract.get("rollback_claimed") is False
        and contract.get("process_kill_claimed") is False
        and contract.get("dangerous_actions_disabled") is True
    )
    contract_defined = rollback_contract_defined and process_owner_contract_defined
    machine_error_code = (
        "ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT"
        if contract_defined
        else "ROLLBACK_PROCESS_OWNER_CONTRACT_INCOMPLETE"
    )
    return {
        "schema_version": 1,
        "status": "ok" if contract_defined else "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": "" if contract_defined else "ROLLBACK_PROCESS_OWNER_ACTIONS_MISSING",
        "captured_at_utc": utc_now(),
        "claim_scope": "custom_codex_recovery_rollback_process_owner_dry_run_contract_only",
        "contract_endpoint": "/api/codex/custom/recovery/rollback-process-owner-contract",
        "contract_source_endpoint": "/api/codex/custom/recovery/contract",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "browser_forbidden_fields_rejected": True,
        "rollback_contract_defined": rollback_contract_defined,
        "rollback_live_ready": False,
        "rollback_apply_admitted": False,
        "rollback_point_required": True,
        "rollback_point_present": False,
        "rollback_write_surfaces_required": True,
        "rollback_write_surfaces_declared": False,
        "rollback_verification_packet_required": True,
        "rollback_verification_packet_present": False,
        "process_owner_contract_defined": process_owner_contract_defined,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "owned_process_identity_required": True,
        "owned_process_identity_present": False,
        "current_codex_process_exclusion_required": True,
        "current_codex_process_excluded": False,
        "current_codex_process_candidate": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "diagnostics_support_artifact_only": True,
        "diagnostics_counted_as_recovery_action": False,
        "readonly_checks_counted_as_mutation": False,
        "session_create_counted_as_recovery_action": False,
        "contract_readonly_sources_ok": contract.get("status") == "ok",
        "readonly_sources": readonly,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "arbitrary_path_accepted": False,
        "arbitrary_process_kill_allowed": False,
        "arbitrary_path_cleanup_allowed": False,
        "dangerous_actions_disabled": dangerous_actions_disabled,
        "dangerous_action_mutation_allowed": False,
        "prerequisites": [
            {
                "id": "rollback_point",
                "required": True,
                "present": False,
                "blocks_live_ready": True,
                "blocks_contract_definition": False,
            },
            {
                "id": "rollback_write_surfaces",
                "required": True,
                "present": False,
                "blocks_live_ready": True,
                "blocks_contract_definition": False,
            },
            {
                "id": "rollback_verification_packet",
                "required": True,
                "present": False,
                "blocks_live_ready": True,
                "blocks_contract_definition": False,
            },
            {
                "id": "owned_process_identity",
                "required": True,
                "present": False,
                "blocks_live_ready": True,
                "blocks_contract_definition": False,
            },
            {
                "id": "current_codex_process_exclusion",
                "required": True,
                "present": False,
                "blocks_live_ready": True,
                "blocks_contract_definition": False,
            },
        ],
        "actions": [
            {
                "id": rollback_action.get("id") or "rollback_readiness",
                "status": rollback_action.get("status") or "missing",
                "mutation_allowed": rollback_action.get("mutation_allowed") is True,
                "browser_payload_allowed": rollback_action.get("browser_payload_allowed") is True,
                "live_ready": False,
                "admitted": False,
            },
            {
                "id": kill_action.get("id") or "stuck_process_kill_readiness",
                "status": kill_action.get("status") or "missing",
                "mutation_allowed": kill_action.get("mutation_allowed") is True,
                "browser_payload_allowed": kill_action.get("browser_payload_allowed") is True,
                "live_ready": False,
                "admitted": False,
            },
            {
                "id": cleanup_path_action.get("id") or "cleanup_arbitrary_path",
                "status": cleanup_path_action.get("status") or "missing",
                "mutation_allowed": cleanup_path_action.get("mutation_allowed") is True,
                "browser_payload_allowed": cleanup_path_action.get("browser_payload_allowed") is True,
                "live_ready": False,
                "admitted": False,
            },
        ],
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS",
        "next_contour_claimed": False,
    }


def _rollback_process_owner_contract_ready(packet: dict[str, Any]) -> bool:
    required_false_fields = [
        "contract_endpoint_mutation_allowed",
        "browser_payload_allowed",
        "rollback_live_ready",
        "rollback_apply_admitted",
        "rollback_point_present",
        "rollback_write_surfaces_declared",
        "rollback_verification_packet_present",
        "process_kill_live_ready",
        "process_kill_admitted",
        "owned_process_identity_present",
        "current_codex_process_excluded",
        "current_codex_process_candidate",
        "recovery_operator_ready",
        "operator_ready_claimed",
        "rollback_operator_ready",
        "rollback_claimed",
        "process_kill_operator_ready",
        "process_kill_claimed",
        "diagnostics_counted_as_recovery_action",
        "readonly_checks_counted_as_mutation",
        "session_create_counted_as_recovery_action",
        "current_codex_touched",
        "original_codex_touched",
        "current_codex_home_touched",
        "arbitrary_path_accepted",
        "arbitrary_process_kill_allowed",
        "arbitrary_path_cleanup_allowed",
        "dangerous_action_mutation_allowed",
        "next_contour_claimed",
    ]
    required_true_fields = [
        "rollback_contract_defined",
        "rollback_point_required",
        "rollback_write_surfaces_required",
        "rollback_verification_packet_required",
        "process_owner_contract_defined",
        "owned_process_identity_required",
        "current_codex_process_exclusion_required",
        "diagnostics_support_artifact_only",
        "dangerous_actions_disabled",
    ]
    forbidden_fields = packet.get("forbidden_browser_fields")
    readonly = packet.get("readonly_sources")
    prerequisites = packet.get("prerequisites")
    actions = packet.get("actions")
    action_by_id = {
        action.get("id"): action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    } if isinstance(actions, list) else {}
    rollback_action = action_by_id.get("rollback_readiness", {})
    kill_action = action_by_id.get("stuck_process_kill_readiness", {})
    cleanup_path_action = action_by_id.get("cleanup_arbitrary_path", {})
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT"
        and packet.get("claim_scope")
        == "custom_codex_recovery_rollback_process_owner_dry_run_contract_only"
        and packet.get("browser_payload_allowed_keys") == []
        and all(packet.get(field) is False for field in required_false_fields)
        and all(packet.get(field) is True for field in required_true_fields)
        and packet.get("contract_readonly_sources_ok") is True
        and isinstance(readonly, dict)
        and readonly.get("original_status_ok") is True
        and readonly.get("custom_status_ok") is True
        and readonly.get("accounts_readonly_ok") is True
        and readonly.get("api_readonly_ok") is True
        and isinstance(forbidden_fields, list)
        and all(field in forbidden_fields for field in FORBIDDEN_BROWSER_FIELDS)
        and isinstance(prerequisites, list)
        and {
            item.get("id")
            for item in prerequisites
            if isinstance(item, dict)
            and item.get("required") is True
            and item.get("present") is False
            and item.get("blocks_live_ready") is True
        }
        >= {
            "rollback_point",
            "rollback_write_surfaces",
            "rollback_verification_packet",
            "owned_process_identity",
            "current_codex_process_exclusion",
        }
        and isinstance(actions, list)
        and rollback_action.get("status") == "dry_run_only"
        and kill_action.get("status") == "dry_run_only"
        and cleanup_path_action.get("status") == "disabled"
        and not any(
            isinstance(action, dict)
            and (
                action.get("mutation_allowed") is True
                or action.get("browser_payload_allowed") is True
                or action.get("live_ready") is True
                or action.get("admitted") is True
            )
            for action in actions
        )
    )


def _rollback_point_allowed_write_surfaces_metadata() -> list[dict[str, Any]]:
    return [
        {
            "id": surface_id,
            "owner": metadata["owner"],
            "status": "contract_metadata_only",
            "filesystem_write_admitted": False,
            "machine_checked": False,
        }
        for surface_id, metadata in ROLLBACK_POINT_ALLOWED_WRITE_SURFACES.items()
    ]


def _rollback_point_surface_admission_check(surface: dict[str, Any]) -> dict[str, Any]:
    surface_id = str(surface.get("id") or "")
    expected = ROLLBACK_POINT_ALLOWED_WRITE_SURFACES.get(surface_id)
    owner = str(surface.get("owner") or "")
    source_status = str(surface.get("status") or "")
    source_metadata_ok = (
        expected is not None
        and owner == expected["owner"]
        and source_status == "contract_metadata_only"
        and surface.get("filesystem_write_admitted") is False
        and surface.get("machine_checked") is False
    )
    forbidden_surface = surface_id in ROLLBACK_POINT_FORBIDDEN_SURFACES
    eligible = source_metadata_ok and not forbidden_surface
    return {
        "surface_id": surface_id,
        "owner": owner,
        "scope": expected["scope"] if expected else "unknown_or_forbidden",
        "source_status": source_status,
        "machine_check_performed": True,
        "exists_or_parent_exists": expected is not None,
        "under_controlled_root": expected is not None,
        "current_codex_excluded": surface_id != "current_codex_home",
        "original_codex_excluded": surface_id != "original_codex_profile",
        "auth_material_excluded": surface_id not in {"auth_material", "token_store", "secret_file"},
        "arbitrary_path_excluded": surface_id != "arbitrary_path",
        "filesystem_write_performed": False,
        "write_admitted_for_current_contour": False,
        "eligible_for_next_contour": eligible,
        "block_reason_code": "" if eligible else "WRITE_SURFACE_NOT_ELIGIBLE",
    }


def _stable_digest(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def custom_recovery_session_ref(session_id: str) -> str:
    return "custom-session:" + hashlib.sha256(
        f"wbp-custom-session:{session_id}".encode("utf-8")
    ).hexdigest()[:16]


def custom_recovery_process_ref(session_id: str, process_marker: str = "") -> str:
    marker = process_marker or "server-owned-process-candidate"
    return "custom-process:" + hashlib.sha256(
        f"wbp-custom-process:{session_id}:{marker}".encode("utf-8")
    ).hexdigest()[:16]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden_payload_fields(payload: Any, *, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            findings.append(key_path)
            findings.extend(_forbidden_payload_fields(value, prefix=key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_forbidden_payload_fields(value, prefix=f"{prefix}[{index}]"))
    return findings


def _process_kill_preflight_failure_packet(
    *,
    machine_error_code: str,
    block_reason_code: str,
    source_packet: dict[str, Any] | None = None,
    selected_session: dict[str, Any] | None = None,
    forbidden_fields: list[str] | None = None,
    filesystem_read_performed: bool = False,
) -> dict[str, Any]:
    source = source_packet if isinstance(source_packet, dict) else {}
    session = selected_session if isinstance(selected_session, dict) else {}
    session_id = str(session.get("session_id") or "")
    process_candidate_present = session.get("process_candidate_present") is True
    current_candidate = session.get("current_codex_process_candidate") is True
    original_candidate = session.get("original_codex_process_candidate") is True
    owned_candidate = session.get("process_owned_by_custom_session") is True
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": PROCESS_KILL_PREFLIGHT_CLAIM_SCOPE,
        "verified_scope": "not_verified",
        "contract_endpoint": "/api/codex/custom/recovery/process-kill/preflight",
        "contract_source_endpoint": "/api/codex/custom/recovery/admitted-session-actions",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": (
            FORBIDDEN_BROWSER_FIELDS + PROCESS_KILL_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS
        ),
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "selected_source": "server_owned_custom_session_observation",
        "selected_session_source": "server_selected_latest_owned_custom_session",
        "selected_session_required": True,
        "selected_session_present": bool(session),
        "selected_session_id_redacted": True,
        "selected_session_ambiguous": source.get("selected_session_ambiguous") is True,
        "selected_session_ref_present": bool(session_id),
        "raw_session_id_omitted": True,
        "selected_session_packet_valid": source.get("selected_session_packet_valid") is True,
        "selected_session_cleanup_state": str(session.get("cleanup_state") or ""),
        "selected_session_cancel_state": str(session.get("cancel_state") or ""),
        "owned_process_identity_required": True,
        "owned_process_identity_present": owned_candidate,
        "current_codex_process_exclusion_required": True,
        "original_codex_process_exclusion_required": True,
        "process_candidate_present": process_candidate_present,
        "process_candidate_ref_present": False,
        "raw_pid_omitted": True,
        "raw_process_id_omitted": True,
        "raw_process_path_omitted": True,
        "raw_process_command_omitted": True,
        "process_owned_by_custom_session": owned_candidate,
        "process_kill_eligible": False,
        "process_kill_preflight_evaluated": True,
        "process_kill_preflight_result": "blocked",
        "process_kill_preflight_ready": False,
        "process_kill_ready": False,
        "process_kill_performed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_claimed": False,
        "current_codex_process_candidate": current_candidate,
        "original_codex_process_candidate": original_candidate,
        "current_codex_process_excluded": not current_candidate,
        "original_codex_process_excluded": not original_candidate,
        "filesystem_read_performed": filesystem_read_performed,
        "filesystem_write_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "source_machine_error_code": source.get("machine_error_code", ""),
        "source_block_reason_code": source.get("block_reason_code", ""),
        "human_summary": "process kill preflight blocked · no kill performed",
        "next_action": "repair_process_kill_preconditions",
        "next_contour": "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_PASS",
        "next_contour_claimed": False,
    }


def build_custom_recovery_process_kill_preflight_packet(
    *,
    admitted_session_actions_packet: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    """Build the preflight-only process-kill packet without mutating processes."""

    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(browser_payload)))
    if forbidden_payload_fields:
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_BROWSER_FIELD_REJECTED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_BROWSER_FIELD_REJECTED",
            forbidden_fields=forbidden_payload_fields,
        )

    source = admitted_session_actions_packet if isinstance(admitted_session_actions_packet, dict) else {}
    selected_session = (
        source.get("selected_session_packet")
        if isinstance(source.get("selected_session_packet"), dict)
        else None
    )
    if source.get("status") != "ok" or source.get("session_admitted_actions_ready") is not True:
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SOURCE_NOT_READY",
            block_reason_code=str(
                source.get("block_reason_code")
                or source.get("machine_error_code")
                or "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SOURCE_NOT_READY"
            ),
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=bool(source),
        )

    if not isinstance(selected_session, dict):
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NO_SESSION",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NO_SESSION",
            source_packet=source,
            filesystem_read_performed=True,
        )

    cleanup_state = str(selected_session.get("cleanup_state") or "")
    cancel_state = str(selected_session.get("cancel_state") or "")
    if cleanup_state == "cleaned":
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SESSION_ALREADY_CLEANED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SESSION_ALREADY_CLEANED",
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=True,
        )
    if cancel_state and cancel_state != "not_cancelled":
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SESSION_ALREADY_CANCELLED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_SESSION_ALREADY_CANCELLED",
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=True,
        )

    session_id = str(selected_session.get("session_id") or "")
    process_candidate_present = selected_session.get("process_candidate_present") is True
    owned_candidate = selected_session.get("process_owned_by_custom_session") is True
    current_candidate = selected_session.get("current_codex_process_candidate") is True
    original_candidate = selected_session.get("original_codex_process_candidate") is True

    if not process_candidate_present:
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NO_PROCESS_CANDIDATE",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NO_PROCESS_CANDIDATE",
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=True,
        )
    if current_candidate:
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_CURRENT_CODEX_REJECTED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_CURRENT_CODEX_REJECTED",
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=True,
        )
    if original_candidate:
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_ORIGINAL_CODEX_REJECTED",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_ORIGINAL_CODEX_REJECTED",
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=True,
        )
    if not owned_candidate:
        return _process_kill_preflight_failure_packet(
            machine_error_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NOT_OWNED_CUSTOM_PROCESS",
            block_reason_code="CUSTOM_CODEX_RECOVERY_PROCESS_KILL_NOT_OWNED_CUSTOM_PROCESS",
            source_packet=source,
            selected_session=selected_session,
            filesystem_read_performed=True,
        )

    process_marker = str(selected_session.get("process_candidate_ref") or "")
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_ELIGIBLE",
        "block_reason_code": "",
        "captured_at_utc": utc_now(),
        "claim_scope": PROCESS_KILL_PREFLIGHT_CLAIM_SCOPE,
        "verified_scope": "custom_codex_owned_process_kill_preflight_only",
        "contract_endpoint": "/api/codex/custom/recovery/process-kill/preflight",
        "contract_source_endpoint": "/api/codex/custom/recovery/admitted-session-actions",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": (
            FORBIDDEN_BROWSER_FIELDS + PROCESS_KILL_PREFLIGHT_EXTRA_FORBIDDEN_FIELDS
        ),
        "forbidden_fields": [],
        "browser_forbidden_fields_rejected": True,
        "selected_source": "server_owned_custom_session_observation",
        "selected_session_source": "server_selected_latest_owned_custom_session",
        "selected_session_required": True,
        "selected_session_present": True,
        "selected_session_id_redacted": True,
        "selected_session_ambiguous": False,
        "selected_session_ref": custom_recovery_session_ref(session_id),
        "selected_session_ref_present": True,
        "raw_session_id_omitted": True,
        "selected_session_packet_valid": True,
        "selected_session_cleanup_state": cleanup_state,
        "selected_session_cancel_state": cancel_state,
        "owned_process_identity_required": True,
        "owned_process_identity_present": True,
        "current_codex_process_exclusion_required": True,
        "original_codex_process_exclusion_required": True,
        "process_candidate_present": True,
        "process_candidate_ref": custom_recovery_process_ref(session_id, process_marker),
        "process_candidate_ref_present": True,
        "raw_pid_omitted": True,
        "raw_process_id_omitted": True,
        "raw_process_path_omitted": True,
        "raw_process_command_omitted": True,
        "process_owned_by_custom_session": True,
        "process_kill_eligible": True,
        "process_kill_preflight_evaluated": True,
        "process_kill_preflight_result": "eligible",
        "process_kill_preflight_ready": True,
        "process_kill_ready": False,
        "process_kill_performed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_claimed": False,
        "current_codex_process_candidate": False,
        "original_codex_process_candidate": False,
        "current_codex_process_excluded": True,
        "original_codex_process_excluded": True,
        "filesystem_read_performed": True,
        "filesystem_write_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "source_machine_error_code": source.get("machine_error_code", ""),
        "source_block_reason_code": source.get("block_reason_code", ""),
        "human_summary": "owned custom process kill preflight eligible · no kill performed",
        "next_action": "process_kill_live_requires_separate_contour",
        "next_contour": "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_LIVE_PASS",
        "next_contour_claimed": False,
    }


def _rollback_point_artifact_root(root: Path | None) -> Path:
    base = root or Path(tempfile.gettempdir()) / "wbp-codex-custom-recovery" / "rollback-points"
    resolved = base.resolve()
    resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
    return resolved


def _rollback_point_artifact_root_readonly(root: Path | None) -> Path:
    base = root or Path(tempfile.gettempdir()) / "wbp-codex-custom-recovery" / "rollback-points"
    return base.resolve()


def _rollback_point_manifest_path(root: Path) -> Path:
    return (root / "_rollback_point_manifest.json").resolve()


def _path_under_root(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _rollback_point_create_failure_packet(
    *,
    admission_packet: dict[str, Any] | None,
    machine_error_code: str,
    block_reason_code: str,
    forbidden_fields: list[str] | None = None,
    write_attempted: bool = False,
    artifact_id: str = "",
    artifact_digest: str = "",
) -> dict[str, Any]:
    admission = admission_packet if isinstance(admission_packet, dict) else {}
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_POINT_CREATE_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-point",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-point-create-admission",
        "contract_endpoint_mutation_allowed": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "rollback_point_create_admission_valid": False,
        "rollback_point_create_admitted": False,
        "rollback_point_create_admitted_for_current_contour": False,
        "rollback_point_create_performed": write_attempted,
        "rollback_point_created": False,
        "rollback_point_artifact_id": artifact_id,
        "rollback_point_artifact_path_redacted": True,
        "rollback_point_artifact_ref": "",
        "rollback_point_artifact_digest_present": bool(artifact_digest),
        "rollback_point_artifact_sha256": artifact_digest,
        "snapshot_file_created": False,
        "filesystem_write_performed": write_attempted,
        "filesystem_write_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE if write_attempted else "",
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "write_surface_machine_check_performed": False,
        "write_surfaces_all_eligible": False,
        "allowed_write_surfaces": admission.get("allowed_write_surfaces")
        if isinstance(admission.get("allowed_write_surfaces"), list)
        else [],
        "allowed_write_surface_ids": admission.get("allowed_write_surface_ids")
        if isinstance(admission.get("allowed_write_surface_ids"), list)
        else list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES),
        "forbidden_surfaces": ROLLBACK_POINT_FORBIDDEN_SURFACES,
        "rollback_apply_admitted": False,
        "rollback_apply_performed": False,
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_point_create",
                "status": "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": write_attempted,
                "disabled_reason_code": block_reason_code,
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_NOT_ADMITTED",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_BLOCKED",
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_PASS",
        "next_contour_claimed": False,
    }


def _rollback_point_dry_run_contract_ready(packet: dict[str, Any]) -> bool:
    required_false_fields = [
        "contract_endpoint_mutation_allowed",
        "browser_payload_allowed",
        "rollback_point_present",
        "rollback_point_create_admitted",
        "rollback_apply_admitted",
        "rollback_live_ready",
        "rollback_write_surfaces_machine_checked",
        "rollback_verification_packet_present",
        "recovery_operator_ready",
        "operator_ready_claimed",
        "rollback_operator_ready",
        "rollback_claimed",
        "process_kill_operator_ready",
        "process_kill_claimed",
        "process_kill_live_ready",
        "process_kill_admitted",
        "filesystem_write_performed",
        "snapshot_file_created",
        "snapshot_create_admitted",
        "snapshot_target_browser_supplied",
        "diagnostics_counted_as_recovery_action",
        "readonly_checks_counted_as_mutation",
        "session_create_counted_as_recovery_action",
        "current_codex_touched",
        "original_codex_touched",
        "current_codex_home_touched",
        "current_codex_home_allowed_surface",
        "auth_material_allowed_surface",
        "arbitrary_path_accepted",
        "arbitrary_path_allowed_surface",
        "dangerous_action_mutation_allowed",
        "next_contour_claimed",
    ]
    required_true_fields = [
        "rollback_point_contract_defined",
        "rollback_write_surfaces_contract_defined",
        "rollback_write_surfaces_dry_run_checked",
        "rollback_verification_packet_defined",
        "diagnostics_support_artifact_only",
        "dangerous_actions_disabled",
    ]
    forbidden_fields = packet.get("forbidden_browser_fields")
    allowed_surface_ids = packet.get("allowed_write_surface_ids")
    allowed_surfaces = packet.get("allowed_write_surfaces")
    forbidden_surfaces = packet.get("forbidden_surfaces")
    actions = packet.get("actions")
    action_by_id = {
        action.get("id"): action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    } if isinstance(actions, list) else {}
    create_action = action_by_id.get("rollback_point_create", {})
    snapshot_action = action_by_id.get("rollback_snapshot_create", {})
    apply_action = action_by_id.get("rollback_apply", {})
    expected_surface_ids = list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES)
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "ROLLBACK_POINT_DRY_RUN_CONTRACT"
        and packet.get("claim_scope") == "custom_codex_recovery_rollback_point_dry_run_only"
        and packet.get("browser_payload_allowed_keys") == []
        and all(packet.get(field) is False for field in required_false_fields)
        and all(packet.get(field) is True for field in required_true_fields)
        and isinstance(forbidden_fields, list)
        and all(field in forbidden_fields for field in FORBIDDEN_BROWSER_FIELDS)
        and allowed_surface_ids == expected_surface_ids
        and isinstance(allowed_surfaces, list)
        and len(allowed_surfaces) == len(expected_surface_ids)
        and all(
            isinstance(surface, dict)
            and surface.get("id") in ROLLBACK_POINT_ALLOWED_WRITE_SURFACES
            and surface.get("owner")
            == ROLLBACK_POINT_ALLOWED_WRITE_SURFACES[str(surface.get("id"))]["owner"]
            and surface.get("status") == "contract_metadata_only"
            and surface.get("filesystem_write_admitted") is False
            and surface.get("machine_checked") is False
            for surface in allowed_surfaces
        )
        and isinstance(forbidden_surfaces, list)
        and all(surface in forbidden_surfaces for surface in ROLLBACK_POINT_FORBIDDEN_SURFACES)
        and isinstance(actions, list)
        and create_action.get("status") == "dry_run_only"
        and snapshot_action.get("status") == "dry_run_only"
        and apply_action.get("status") == "disabled"
        and not any(
            isinstance(action, dict)
            and (
                action.get("mutation_allowed") is True
                or action.get("browser_payload_allowed") is True
                or action.get("admitted") is True
            )
            for action in actions
        )
    )


def build_custom_recovery_rollback_point_dry_run_packet(
    *,
    rollback_process_owner_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the dry-run-only rollback point contract packet."""

    upstream = rollback_process_owner_contract if isinstance(rollback_process_owner_contract, dict) else {}
    upstream_ok = _rollback_process_owner_contract_ready(upstream)
    allowed_surfaces = _rollback_point_allowed_write_surfaces_metadata()
    return {
        "schema_version": 1,
        "status": "ok" if upstream_ok else "blocked",
        "machine_error_code": (
            "ROLLBACK_POINT_DRY_RUN_CONTRACT"
            if upstream_ok
            else "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED"
        ),
        "block_reason_code": "" if upstream_ok else "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED",
        "captured_at_utc": utc_now(),
        "claim_scope": "custom_codex_recovery_rollback_point_dry_run_only",
        "contract_endpoint": "/api/codex/custom/recovery/rollback-point-dry-run",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-process-owner-contract",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "browser_forbidden_fields_rejected": True,
        "rollback_point_contract_defined": upstream_ok,
        "rollback_point_present": False,
        "rollback_point_create_admitted": False,
        "rollback_apply_admitted": False,
        "rollback_live_ready": False,
        "rollback_write_surfaces_contract_defined": True,
        "rollback_write_surfaces_machine_checked": False,
        "rollback_write_surfaces_dry_run_checked": True,
        "rollback_verification_packet_defined": True,
        "rollback_verification_packet_present": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "filesystem_write_performed": False,
        "snapshot_file_created": False,
        "snapshot_create_admitted": False,
        "snapshot_target_browser_supplied": False,
        "diagnostics_support_artifact_only": True,
        "diagnostics_counted_as_recovery_action": False,
        "readonly_checks_counted_as_mutation": False,
        "session_create_counted_as_recovery_action": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "current_codex_home_allowed_surface": False,
        "auth_material_allowed_surface": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "allowed_write_surfaces": allowed_surfaces,
        "allowed_write_surface_ids": [surface["id"] for surface in allowed_surfaces],
        "forbidden_surfaces": ROLLBACK_POINT_FORBIDDEN_SURFACES,
        "missing_prerequisites": [
            "rollback_point_create_admission",
            "rollback_point_live_creation",
            "rollback_verification_packet_instance",
        ],
        "actions": [
            {
                "id": "rollback_point_create",
                "status": "dry_run_only",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "disabled_reason_code": "ROLLBACK_POINT_CREATE_NOT_ADMITTED",
            },
            {
                "id": "rollback_snapshot_create",
                "status": "dry_run_only",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "disabled_reason_code": "SNAPSHOT_CREATE_NOT_ADMITTED",
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "disabled_reason_code": "ROLLBACK_APPLY_NOT_ADMITTED",
            },
        ],
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS",
        "next_contour_claimed": False,
    }


def build_custom_recovery_rollback_point_create_admission_packet(
    *,
    rollback_point_dry_run_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the no-write admission packet for future rollback point creation."""

    dry_run = rollback_point_dry_run_contract if isinstance(rollback_point_dry_run_contract, dict) else {}
    dry_run_valid = _rollback_point_dry_run_contract_ready(dry_run)
    source_surfaces = dry_run.get("allowed_write_surfaces")
    source_surfaces = source_surfaces if isinstance(source_surfaces, list) else []
    checked_surfaces = [
        _rollback_point_surface_admission_check(surface if isinstance(surface, dict) else {})
        for surface in source_surfaces
    ]
    expected_surface_ids = list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES)
    observed_surface_ids = [surface["surface_id"] for surface in checked_surfaces]
    write_surface_machine_check_performed = bool(checked_surfaces) and all(
        surface["machine_check_performed"] is True for surface in checked_surfaces
    )
    write_surfaces_all_eligible = (
        dry_run_valid
        and observed_surface_ids == expected_surface_ids
        and all(surface["eligible_for_next_contour"] is True for surface in checked_surfaces)
    )
    admission_ready = dry_run_valid and write_surfaces_all_eligible
    block_reason = ""
    if not dry_run_valid:
        block_reason = "ROLLBACK_POINT_DRY_RUN_CONTRACT_REQUIRED"
    elif not write_surfaces_all_eligible:
        block_reason = "ROLLBACK_POINT_WRITE_SURFACES_NOT_ELIGIBLE"
    return {
        "schema_version": 1,
        "status": "ok" if admission_ready else "blocked",
        "machine_error_code": (
            "ROLLBACK_POINT_CREATE_ADMISSION_READY"
            if admission_ready
            else "ROLLBACK_POINT_CREATE_ADMISSION_BLOCKED"
        ),
        "block_reason_code": block_reason,
        "captured_at_utc": utc_now(),
        "claim_scope": "custom_codex_recovery_rollback_point_create_admission_only",
        "contract_endpoint": "/api/codex/custom/recovery/rollback-point-create-admission",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-point-dry-run",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "browser_forbidden_fields_rejected": True,
        "rollback_point_dry_run_contract_valid": dry_run_valid,
        "rollback_point_create_admission_defined": True,
        "rollback_point_create_admitted": admission_ready,
        "rollback_point_create_admitted_scope": (
            "next_contour_only" if admission_ready else "not_admitted"
        ),
        "rollback_point_create_admitted_for_current_contour": False,
        "rollback_point_create_performed": False,
        "rollback_point_created": False,
        "snapshot_file_created": False,
        "filesystem_write_performed": False,
        "write_surface_machine_check_performed": write_surface_machine_check_performed,
        "write_surfaces_all_eligible": write_surfaces_all_eligible,
        "allowed_write_surfaces": checked_surfaces,
        "allowed_write_surface_ids": expected_surface_ids,
        "forbidden_surfaces": ROLLBACK_POINT_FORBIDDEN_SURFACES,
        "rollback_apply_admitted": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "current_codex_home_allowed_surface": False,
        "auth_material_allowed_surface": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_point_create",
                "status": "admission_ready" if admission_ready else "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": admission_ready,
                "admitted_for_current_contour": False,
                "admitted_scope": "next_contour_only" if admission_ready else "not_admitted",
                "performed": False,
                "disabled_reason_code": "" if admission_ready else block_reason,
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_NOT_ADMITTED",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": (
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_READY"
            if admission_ready
            else "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_BLOCKED"
        ),
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_PASS",
        "next_contour_claimed": False,
    }


def _rollback_point_create_admission_ready(packet: dict[str, Any]) -> bool:
    required_false_fields = [
        "contract_endpoint_mutation_allowed",
        "browser_payload_allowed",
        "rollback_point_create_admitted_for_current_contour",
        "rollback_point_create_performed",
        "rollback_point_created",
        "snapshot_file_created",
        "filesystem_write_performed",
        "rollback_apply_admitted",
        "rollback_live_ready",
        "recovery_operator_ready",
        "operator_ready_claimed",
        "rollback_operator_ready",
        "rollback_claimed",
        "process_kill_operator_ready",
        "process_kill_claimed",
        "process_kill_live_ready",
        "process_kill_admitted",
        "current_codex_touched",
        "original_codex_touched",
        "current_codex_home_touched",
        "current_codex_home_allowed_surface",
        "auth_material_allowed_surface",
        "arbitrary_path_accepted",
        "arbitrary_path_allowed_surface",
        "dangerous_action_mutation_allowed",
        "next_contour_claimed",
    ]
    required_true_fields = [
        "rollback_point_dry_run_contract_valid",
        "rollback_point_create_admission_defined",
        "rollback_point_create_admitted",
        "write_surface_machine_check_performed",
        "write_surfaces_all_eligible",
        "dangerous_actions_disabled",
        "browser_forbidden_fields_rejected",
    ]
    forbidden_fields = packet.get("forbidden_browser_fields")
    actions = packet.get("actions")
    action_by_id = {
        action.get("id"): action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    } if isinstance(actions, list) else {}
    create_action = action_by_id.get("rollback_point_create", {})
    apply_action = action_by_id.get("rollback_apply", {})
    kill_action = action_by_id.get("process_kill", {})
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "ROLLBACK_POINT_CREATE_ADMISSION_READY"
        and packet.get("result_token")
        == "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_READY"
        and packet.get("claim_scope")
        == "custom_codex_recovery_rollback_point_create_admission_only"
        and packet.get("rollback_point_create_admitted_scope") == "next_contour_only"
        and packet.get("browser_payload_allowed_keys") == []
        and packet.get("allowed_write_surface_ids") == list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES)
        and all(packet.get(field) is False for field in required_false_fields)
        and all(packet.get(field) is True for field in required_true_fields)
        and isinstance(forbidden_fields, list)
        and all(field in forbidden_fields for field in FORBIDDEN_BROWSER_FIELDS)
        and isinstance(actions, list)
        and create_action.get("status") == "admission_ready"
        and create_action.get("admitted") is True
        and create_action.get("admitted_for_current_contour") is False
        and create_action.get("mutation_allowed") is False
        and create_action.get("browser_payload_allowed") is False
        and create_action.get("performed") is False
        and apply_action.get("status") == "disabled"
        and apply_action.get("admitted") is False
        and kill_action.get("status") == "disabled"
        and kill_action.get("admitted") is False
    )


def build_custom_recovery_rollback_point_create_live_packet(
    *,
    rollback_point_create_admission: dict[str, Any] | None,
    browser_payload: dict[str, Any] | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Create a bounded rollback point artifact and return a redacted proof packet."""

    if browser_payload is None:
        payload: dict[str, Any] = {}
    elif isinstance(browser_payload, dict):
        payload = browser_payload
    else:
        return _rollback_point_create_failure_packet(
            admission_packet=rollback_point_create_admission,
            machine_error_code="ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
            block_reason_code="ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
            forbidden_fields=["invalid_body"],
        )
    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(payload)))
    if forbidden_payload_fields:
        return _rollback_point_create_failure_packet(
            admission_packet=rollback_point_create_admission,
            machine_error_code="ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
            block_reason_code="ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
            forbidden_fields=forbidden_payload_fields,
        )

    admission = (
        rollback_point_create_admission
        if isinstance(rollback_point_create_admission, dict)
        else {}
    )
    admission_valid = _rollback_point_create_admission_ready(admission)
    if not admission_valid:
        return _rollback_point_create_failure_packet(
            admission_packet=admission,
            machine_error_code="ROLLBACK_POINT_CREATE_ADMISSION_INVALID",
            block_reason_code="ROLLBACK_POINT_CREATE_ADMISSION_INVALID",
        )

    selected_surface = ROLLBACK_POINT_ALLOWED_WRITE_SURFACES.get(
        ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
    )
    if selected_surface is None:
        return _rollback_point_create_failure_packet(
            admission_packet=admission,
            machine_error_code="ROLLBACK_POINT_CREATE_FORBIDDEN_WRITE_SURFACE",
            block_reason_code="ROLLBACK_POINT_CREATE_FORBIDDEN_WRITE_SURFACE",
        )

    root = _rollback_point_artifact_root(artifact_root)
    artifact_id = f"crp-{uuid.uuid4().hex}"
    artifact_path = (root / f"{artifact_id}.json").resolve()
    if not _path_under_root(artifact_path, root):
        return _rollback_point_create_failure_packet(
            admission_packet=admission,
            machine_error_code="ROLLBACK_POINT_CREATE_FORBIDDEN_WRITE_SURFACE",
            block_reason_code="ROLLBACK_POINT_CREATE_FORBIDDEN_WRITE_SURFACE",
            artifact_id=artifact_id,
        )

    now = utc_now()
    artifact_payload = {
        "schema_version": 1,
        "artifact_kind": ROLLBACK_POINT_ARTIFACT_KIND,
        "created_at_utc": now,
        "claim_scope": ROLLBACK_POINT_CREATE_CLAIM_SCOPE,
        "source_admission_sha256": _stable_digest(admission),
        "write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "write_surface_scope": selected_surface["scope"],
        "current_codex_touched": False,
        "original_codex_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "rollback_apply_admitted": False,
        "recovery_operator_ready": False,
    }
    artifact_payload = {
        **artifact_payload,
        "artifact_payload_sha256": _stable_digest(artifact_payload),
    }
    try:
        artifact_path.write_text(
            json.dumps(artifact_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact_path.chmod(0o600)
        artifact_digest = _sha256_file(artifact_path)
        readback = json.loads(artifact_path.read_text(encoding="utf-8"))
        manifest_path = _rollback_point_manifest_path(root)
        manifest_entries: list[dict[str, Any]] = []
        if manifest_path.exists():
            manifest_readback = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest_readback, dict):
                existing_entries = manifest_readback.get("entries")
                if isinstance(existing_entries, list):
                    manifest_entries = [
                        entry for entry in existing_entries if isinstance(entry, dict)
                    ]
        manifest_entries = [
            entry
            for entry in manifest_entries
            if entry.get("artifact_id") != artifact_id
        ]
        manifest_payload = {
            "schema_version": 1,
            "artifact_kind": ROLLBACK_POINT_MANIFEST_KIND,
            "claim_scope": ROLLBACK_POINT_CREATE_CLAIM_SCOPE,
            "updated_at_utc": now,
            "write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
            "write_surface_scope": selected_surface["scope"],
            "entries": manifest_entries
            + [
                {
                    "artifact_id": artifact_id,
                    "artifact_sha256": artifact_digest,
                    "artifact_payload_sha256": artifact_payload["artifact_payload_sha256"],
                    "source_admission_sha256": artifact_payload["source_admission_sha256"],
                    "created_at_utc": now,
                    "artifact_kind": ROLLBACK_POINT_ARTIFACT_KIND,
                    "write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
                    "write_surface_scope": selected_surface["scope"],
                }
            ],
        }
        manifest_payload = {
            **manifest_payload,
            "manifest_payload_sha256": _stable_digest(manifest_payload),
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_path.chmod(0o600)
        manifest_readback = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _rollback_point_create_failure_packet(
            admission_packet=admission,
            machine_error_code="ROLLBACK_POINT_CREATE_WRITE_FAILED",
            block_reason_code=str(type(exc).__name__),
            write_attempted=True,
            artifact_id=artifact_id,
        )

    verification_ok = (
        isinstance(readback, dict)
        and readback.get("artifact_kind") == ROLLBACK_POINT_ARTIFACT_KIND
        and readback.get("claim_scope") == ROLLBACK_POINT_CREATE_CLAIM_SCOPE
        and readback.get("write_surface_id") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and readback.get("source_admission_sha256") == _stable_digest(admission)
        and readback.get("current_codex_touched") is False
        and readback.get("original_codex_touched") is False
        and readback.get("auth_material_touched") is False
        and readback.get("secret_value_recorded") is False
        and isinstance(manifest_readback, dict)
        and manifest_readback.get("artifact_kind") == ROLLBACK_POINT_MANIFEST_KIND
        and manifest_readback.get("manifest_payload_sha256")
        == _stable_digest(
            {
                key: value
                for key, value in manifest_readback.items()
                if key != "manifest_payload_sha256"
            }
        )
        and any(
            isinstance(entry, dict)
            and entry.get("artifact_id") == artifact_id
            and entry.get("artifact_sha256") == artifact_digest
            and entry.get("artifact_payload_sha256")
            == artifact_payload["artifact_payload_sha256"]
            and entry.get("source_admission_sha256") == _stable_digest(admission)
            and entry.get("created_at_utc") == now
            for entry in manifest_readback.get("entries", [])
            if isinstance(manifest_readback.get("entries"), list)
        )
    )
    if not verification_ok:
        return _rollback_point_create_failure_packet(
            admission_packet=admission,
            machine_error_code="ROLLBACK_POINT_CREATE_VERIFICATION_FAILED",
            block_reason_code="ROLLBACK_POINT_CREATE_VERIFICATION_FAILED",
            write_attempted=True,
            artifact_id=artifact_id,
            artifact_digest=artifact_digest,
        )

    checked_surfaces: list[dict[str, Any]] = []
    source_surfaces = admission.get("allowed_write_surfaces")
    source_surfaces = source_surfaces if isinstance(source_surfaces, list) else []
    for source_surface in source_surfaces:
        source_surface = source_surface if isinstance(source_surface, dict) else {}
        checked = (
            dict(source_surface)
            if isinstance(source_surface.get("surface_id"), str)
            else _rollback_point_surface_admission_check(source_surface)
        )
        selected = checked["surface_id"] == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        checked_surfaces.append(
            {
                **checked,
                "source_status": "live_create_selected" if selected else checked["source_status"],
                "filesystem_write_performed": selected,
                "write_admitted_for_current_contour": selected,
                "artifact_path_redacted": True,
                "artifact_digest_present": selected and bool(artifact_digest),
            }
        )

    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "ROLLBACK_POINT_CREATE_LIVE_READY",
        "block_reason_code": "",
        "captured_at_utc": now,
        "claim_scope": ROLLBACK_POINT_CREATE_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-point",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-point-create-admission",
        "contract_endpoint_mutation_allowed": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS,
        "forbidden_fields": [],
        "browser_forbidden_fields_rejected": True,
        "rollback_point_create_admission_valid": True,
        "rollback_point_create_admitted": True,
        "rollback_point_create_admitted_for_current_contour": True,
        "rollback_point_create_performed": True,
        "rollback_point_created": True,
        "rollback_point_artifact_id": artifact_id,
        "rollback_point_artifact_path_redacted": True,
        "rollback_point_artifact_ref": f"rollback-point:{artifact_digest[:16]}",
        "rollback_point_artifact_digest_present": True,
        "rollback_point_artifact_sha256": artifact_digest,
        "snapshot_file_created": False,
        "filesystem_write_performed": True,
        "filesystem_write_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "write_surface_machine_check_performed": True,
        "write_surfaces_all_eligible": True,
        "allowed_write_surfaces": checked_surfaces,
        "allowed_write_surface_ids": list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES),
        "forbidden_surfaces": ROLLBACK_POINT_FORBIDDEN_SURFACES,
        "rollback_apply_admitted": False,
        "rollback_apply_performed": False,
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_point_create",
                "status": "live_created",
                "mutation_allowed": True,
                "browser_payload_allowed": False,
                "admitted": True,
                "admitted_for_current_contour": True,
                "performed": True,
                "disabled_reason_code": "",
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_NOT_ADMITTED",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "admitted_for_current_contour": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_READY",
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_PASS",
        "next_contour_claimed": False,
    }


def _rollback_point_verify_failure_packet(
    *,
    machine_error_code: str,
    block_reason_code: str,
    forbidden_fields: list[str] | None = None,
    artifact_id: str = "",
    artifact_sha256: str = "",
    filesystem_read_performed: bool = False,
    selection_ambiguous: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_POINT_VERIFY_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-point/verify",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-point",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ["artifact_id", "artifact_path", "digest"],
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "rollback_point_verify_performed": filesystem_read_performed,
        "rollback_point_verified": False,
        "rollback_point_present": bool(artifact_id),
        "rollback_point_selection_source": "server_owned_latest_valid_artifact",
        "rollback_point_selection_ambiguous": selection_ambiguous,
        "rollback_point_artifact_id": artifact_id,
        "rollback_point_artifact_id_present": bool(artifact_id),
        "rollback_point_artifact_path_redacted": True,
        "rollback_point_artifact_ref": f"rollback-point:{artifact_sha256[:16]}"
        if artifact_sha256
        else "",
        "rollback_point_artifact_sha256": artifact_sha256,
        "rollback_point_artifact_digest_present": bool(artifact_sha256),
        "rollback_point_digest_verified": False,
        "rollback_point_file_digest_present": bool(artifact_sha256),
        "rollback_point_source_admission_digest_present": False,
        "rollback_point_provenance_verified": False,
        "rollback_point_schema_valid": False,
        "rollback_point_kind_valid": False,
        "rollback_point_surface_verified": False,
        "filesystem_read_performed": filesystem_read_performed,
        "filesystem_read_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        if filesystem_read_performed
        else "",
        "filesystem_write_performed": False,
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "rollback_apply_admitted": False,
        "rollback_apply_ready": False,
        "rollback_apply_performed": False,
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_point_verify",
                "status": "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "performed": filesystem_read_performed,
                "verified": False,
                "disabled_reason_code": block_reason_code,
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "ready": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_BLOCKED",
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_PASS",
        "next_contour_claimed": False,
    }


def _read_rollback_point_artifact(path: Path, root: Path) -> tuple[dict[str, Any] | None, str]:
    if not _path_under_root(path, root):
        return None, "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID"
    if not isinstance(payload, dict):
        return None, "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID"
    return payload, ""


def _rollback_point_payload_digest_verified(payload: dict[str, Any]) -> bool:
    observed = payload.get("artifact_payload_sha256")
    if not isinstance(observed, str) or not observed:
        return False
    comparable = dict(payload)
    comparable.pop("artifact_payload_sha256", None)
    return observed == _stable_digest(comparable)


def _rollback_point_manifest_digest_verified(manifest: dict[str, Any]) -> bool:
    observed = manifest.get("manifest_payload_sha256")
    if not isinstance(observed, str) or not observed:
        return False
    comparable = dict(manifest)
    comparable.pop("manifest_payload_sha256", None)
    return observed == _stable_digest(comparable)


def _rollback_point_created_at_valid(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _read_rollback_point_manifest(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    path = _rollback_point_manifest_path(root)
    if not path.exists():
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if not _path_under_root(path, root):
        return {}, "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if not isinstance(manifest, dict):
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if manifest.get("schema_version") != 1:
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if manifest.get("artifact_kind") != ROLLBACK_POINT_MANIFEST_KIND:
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if manifest.get("claim_scope") != ROLLBACK_POINT_CREATE_CLAIM_SCOPE:
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if manifest.get("write_surface_id") != ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE:
        return {}, "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE"
    expected_scope = ROLLBACK_POINT_ALLOWED_WRITE_SURFACES[
        ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
    ]["scope"]
    if manifest.get("write_surface_scope") != expected_scope:
        return {}, "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE"
    if not _rollback_point_manifest_digest_verified(manifest):
        return {}, "ROLLBACK_POINT_VERIFY_DIGEST_MISMATCH"
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return {}, "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    by_artifact_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        artifact_id = entry.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id:
            by_artifact_id[artifact_id] = entry
    return by_artifact_id, ""


def _rollback_point_payload_error(payload: dict[str, Any]) -> str:
    if payload.get("schema_version") != 1:
        return "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID"
    if payload.get("artifact_kind") != ROLLBACK_POINT_ARTIFACT_KIND:
        return "ROLLBACK_POINT_VERIFY_KIND_INVALID"
    if payload.get("claim_scope") != ROLLBACK_POINT_CREATE_CLAIM_SCOPE:
        return "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID"
    if not _rollback_point_created_at_valid(payload.get("created_at_utc")):
        return "ROLLBACK_POINT_VERIFY_TIMESTAMP_INVALID"
    source_admission_sha = payload.get("source_admission_sha256")
    source_admission_sha_valid = (
        isinstance(source_admission_sha, str)
        and len(source_admission_sha) == 64
        and all(character in "0123456789abcdef" for character in source_admission_sha)
    )
    if not source_admission_sha_valid:
        return "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING"
    if payload.get("write_surface_id") != ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE:
        return "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE"
    expected_scope = ROLLBACK_POINT_ALLOWED_WRITE_SURFACES[
        ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
    ]["scope"]
    if payload.get("write_surface_scope") != expected_scope:
        return "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE"
    if payload.get("current_codex_touched") is not False:
        return "CURRENT_CODEX_TOUCHED"
    if payload.get("original_codex_touched") is not False:
        return "ORIGINAL_CODEX_TOUCHED"
    if payload.get("auth_material_touched") is not False:
        return "ROLLBACK_POINT_VERIFY_SECRET_LEAK_DETECTED"
    if payload.get("secret_value_recorded") is not False:
        return "ROLLBACK_POINT_VERIFY_SECRET_LEAK_DETECTED"
    if payload.get("rollback_apply_admitted") is not False:
        return "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID"
    if payload.get("recovery_operator_ready") is not False:
        return "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID"
    if not _rollback_point_payload_digest_verified(payload):
        return "ROLLBACK_POINT_VERIFY_DIGEST_MISMATCH"
    return ""


def build_custom_recovery_rollback_point_verify_packet(
    *,
    artifact_root: Path | None = None,
    browser_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify the newest server-owned rollback point artifact without writing."""

    payload = browser_payload if isinstance(browser_payload, dict) else {}
    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(payload)))
    if forbidden_payload_fields:
        return _rollback_point_verify_failure_packet(
            machine_error_code="ROLLBACK_POINT_VERIFY_BROWSER_FIELD_REJECTED",
            block_reason_code="ROLLBACK_POINT_VERIFY_BROWSER_FIELD_REJECTED",
            forbidden_fields=forbidden_payload_fields,
        )

    root = _rollback_point_artifact_root_readonly(artifact_root)
    if not root.exists() or not root.is_dir():
        return _rollback_point_verify_failure_packet(
            machine_error_code="ROLLBACK_POINT_VERIFY_NOT_FOUND",
            block_reason_code="ROLLBACK_POINT_VERIFY_NOT_FOUND",
        )

    paths = sorted(
        (path.resolve() for path in root.glob("crp-*.json") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    if not paths:
        return _rollback_point_verify_failure_packet(
            machine_error_code="ROLLBACK_POINT_VERIFY_NOT_FOUND",
            block_reason_code="ROLLBACK_POINT_VERIFY_NOT_FOUND",
        )

    candidates: list[tuple[Path, dict[str, Any], str]] = []
    first_error = ""
    first_artifact_id = ""
    first_artifact_sha = ""
    for path in paths:
        artifact_id = path.stem
        payload, read_error = _read_rollback_point_artifact(path, root)
        file_sha = _sha256_file(path) if path.exists() else ""
        if read_error:
            if not first_error:
                first_error = read_error
                first_artifact_id = artifact_id
                first_artifact_sha = file_sha
            continue
        assert payload is not None
        payload_error = _rollback_point_payload_error(payload)
        if payload_error:
            if not first_error:
                first_error = payload_error
                first_artifact_id = artifact_id
                first_artifact_sha = file_sha
            continue
        created_at = str(payload.get("created_at_utc") or "")
        candidates.append((path, payload, created_at))

    if not candidates:
        error = first_error or "ROLLBACK_POINT_VERIFY_NOT_FOUND"
        return _rollback_point_verify_failure_packet(
            machine_error_code=error,
            block_reason_code=error,
            artifact_id=first_artifact_id,
            artifact_sha256=first_artifact_sha,
            filesystem_read_performed=bool(first_artifact_id),
        )

    candidates.sort(key=lambda item: (item[2], item[0].name), reverse=True)
    newest_created_at = candidates[0][2]
    ambiguous = len([item for item in candidates if item[2] == newest_created_at]) > 1
    if ambiguous:
        return _rollback_point_verify_failure_packet(
            machine_error_code="ROLLBACK_POINT_VERIFY_AMBIGUOUS_SELECTION",
            block_reason_code="ROLLBACK_POINT_VERIFY_AMBIGUOUS_SELECTION",
            artifact_id=candidates[0][0].stem,
            artifact_sha256=_sha256_file(candidates[0][0]),
            filesystem_read_performed=True,
            selection_ambiguous=True,
        )

    selected_path, selected_payload, _created_at = candidates[0]
    artifact_sha = _sha256_file(selected_path)
    source_admission_sha = str(selected_payload.get("source_admission_sha256") or "")
    manifest_entries, manifest_error = _read_rollback_point_manifest(root)
    if manifest_error:
        return _rollback_point_verify_failure_packet(
            machine_error_code=manifest_error,
            block_reason_code=manifest_error,
            artifact_id=selected_path.stem,
            artifact_sha256=artifact_sha,
            filesystem_read_performed=True,
        )
    manifest_entry = manifest_entries.get(selected_path.stem)
    payload_digest = str(selected_payload.get("artifact_payload_sha256") or "")
    manifest_entry_valid = (
        isinstance(manifest_entry, dict)
        and manifest_entry.get("artifact_id") == selected_path.stem
        and manifest_entry.get("artifact_sha256") == artifact_sha
        and manifest_entry.get("artifact_payload_sha256") == payload_digest
        and manifest_entry.get("source_admission_sha256") == source_admission_sha
        and manifest_entry.get("created_at_utc") == selected_payload.get("created_at_utc")
        and manifest_entry.get("artifact_kind") == ROLLBACK_POINT_ARTIFACT_KIND
        and manifest_entry.get("write_surface_id") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and manifest_entry.get("write_surface_scope")
        == ROLLBACK_POINT_ALLOWED_WRITE_SURFACES[
            ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        ]["scope"]
    )
    if not manifest_entry_valid:
        return _rollback_point_verify_failure_packet(
            machine_error_code="ROLLBACK_POINT_VERIFY_PROVENANCE_MISMATCH",
            block_reason_code="ROLLBACK_POINT_VERIFY_PROVENANCE_MISMATCH",
            artifact_id=selected_path.stem,
            artifact_sha256=artifact_sha,
            filesystem_read_performed=True,
        )
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "ROLLBACK_POINT_VERIFY_READY",
        "block_reason_code": "",
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_POINT_VERIFY_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-point/verify",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-point",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ["artifact_id", "artifact_path", "digest"],
        "browser_forbidden_fields_rejected": True,
        "rollback_point_verify_performed": True,
        "rollback_point_verified": True,
        "rollback_point_present": True,
        "rollback_point_selection_source": "server_owned_latest_valid_artifact",
        "rollback_point_selection_ambiguous": False,
        "rollback_point_artifact_id": selected_path.stem,
        "rollback_point_artifact_id_present": True,
        "rollback_point_artifact_path_redacted": True,
        "rollback_point_artifact_ref": f"rollback-point:{artifact_sha[:16]}",
        "rollback_point_artifact_sha256": artifact_sha,
        "rollback_point_artifact_digest_present": True,
        "rollback_point_digest_verified": True,
        "rollback_point_file_digest_present": True,
        "rollback_point_payload_digest_verified": True,
        "rollback_point_source_admission_digest_present": bool(source_admission_sha),
        "rollback_point_source_admission_sha256_present": bool(source_admission_sha),
        "rollback_point_manifest_verified": True,
        "rollback_point_provenance_verified": True,
        "rollback_point_schema_valid": True,
        "rollback_point_kind_valid": True,
        "rollback_point_surface_verified": True,
        "filesystem_read_performed": True,
        "filesystem_read_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "filesystem_write_performed": False,
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "rollback_apply_admitted": False,
        "rollback_apply_ready": False,
        "rollback_apply_performed": False,
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_point_verify",
                "status": "verified",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "performed": True,
                "verified": True,
                "disabled_reason_code": "",
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "ready": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_READY",
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_PASS",
        "next_contour_claimed": False,
    }


def _rollback_point_verify_ready(packet: dict[str, Any]) -> bool:
    required_false_fields = [
        "contract_endpoint_mutation_allowed",
        "browser_payload_allowed",
        "rollback_point_selection_ambiguous",
        "filesystem_write_performed",
        "rollback_apply_admitted",
        "rollback_apply_ready",
        "rollback_apply_performed",
        "rollback_completed",
        "rollback_live_ready",
        "recovery_operator_ready",
        "operator_ready_claimed",
        "rollback_operator_ready",
        "rollback_claimed",
        "process_kill_operator_ready",
        "process_kill_claimed",
        "process_kill_live_ready",
        "process_kill_admitted",
        "current_codex_touched",
        "original_codex_touched",
        "current_codex_home_touched",
        "auth_material_touched",
        "auth_material_allowed_surface",
        "secret_value_recorded",
        "arbitrary_path_accepted",
        "arbitrary_path_allowed_surface",
        "dangerous_action_mutation_allowed",
        "next_contour_claimed",
    ]
    required_true_fields = [
        "browser_forbidden_fields_rejected",
        "rollback_point_verify_performed",
        "rollback_point_verified",
        "rollback_point_present",
        "rollback_point_artifact_id_present",
        "rollback_point_artifact_path_redacted",
        "rollback_point_artifact_digest_present",
        "rollback_point_digest_verified",
        "rollback_point_file_digest_present",
        "rollback_point_payload_digest_verified",
        "rollback_point_source_admission_digest_present",
        "rollback_point_source_admission_sha256_present",
        "rollback_point_manifest_verified",
        "rollback_point_provenance_verified",
        "rollback_point_schema_valid",
        "rollback_point_kind_valid",
        "rollback_point_surface_verified",
        "filesystem_read_performed",
        "dangerous_actions_disabled",
    ]
    forbidden_fields = packet.get("forbidden_browser_fields")
    actions = packet.get("actions")
    action_by_id = {
        action.get("id"): action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    } if isinstance(actions, list) else {}
    verify_action = action_by_id.get("rollback_point_verify", {})
    apply_action = action_by_id.get("rollback_apply", {})
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "ROLLBACK_POINT_VERIFY_READY"
        and packet.get("claim_scope") == ROLLBACK_POINT_VERIFY_CLAIM_SCOPE
        and packet.get("contract_endpoint") == "/api/codex/custom/recovery/rollback-point/verify"
        and packet.get("browser_payload_allowed_keys") == []
        and all(packet.get(field) is False for field in required_false_fields)
        and all(packet.get(field) is True for field in required_true_fields)
        and packet.get("rollback_point_selection_source") == "server_owned_latest_valid_artifact"
        and packet.get("filesystem_read_scope") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and packet.get("selected_write_surface_id") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and isinstance(packet.get("rollback_point_artifact_ref"), str)
        and bool(packet.get("rollback_point_artifact_ref"))
        and isinstance(forbidden_fields, list)
        and all(
            field in forbidden_fields
            for field in FORBIDDEN_BROWSER_FIELDS + ["artifact_id", "artifact_path", "digest"]
        )
        and isinstance(actions, list)
        and verify_action.get("status") == "verified"
        and verify_action.get("mutation_allowed") is False
        and verify_action.get("browser_payload_allowed") is False
        and verify_action.get("performed") is True
        and verify_action.get("verified") is True
        and apply_action.get("status") == "disabled"
        and apply_action.get("mutation_allowed") is False
        and apply_action.get("browser_payload_allowed") is False
        and apply_action.get("admitted") is False
        and apply_action.get("ready") is False
        and apply_action.get("performed") is False
    )


def _rollback_apply_admission_dry_run_session_summary(
    sessions_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    packet = sessions_packet if isinstance(sessions_packet, dict) else {}
    sessions = packet.get("sessions")
    sessions = sessions if isinstance(sessions, list) else []
    owned_sessions = [
        session
        for session in sessions
        if isinstance(session, dict)
        and session.get("session_root_scope") == "owned_temp_session_root"
        and session.get("current_codex_home_used") is False
    ]
    active_sessions = [
        session
        for session in owned_sessions
        if session.get("cleanup_state") != "cleaned"
    ]
    return {
        "session_state_read_performed": True,
        "session_state_status": packet.get("status") if isinstance(packet.get("status"), str) else "missing",
        "session_count": len(sessions),
        "owned_session_count": len(owned_sessions),
        "active_owned_session_count": len(active_sessions),
        "session_state_all_owned": len(sessions) == len(owned_sessions),
        "session_state_blocks_apply_admission": False,
    }


def build_custom_recovery_rollback_apply_admission_dry_run_packet(
    *,
    rollback_point_verify: dict[str, Any] | None = None,
    recovery_contract: dict[str, Any] | None = None,
    rollback_process_owner_contract: dict[str, Any] | None = None,
    sessions_packet: dict[str, Any] | None = None,
    browser_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate future rollback-apply admission without admitting or performing it."""

    payload = browser_payload if isinstance(browser_payload, dict) else {}
    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(payload)))
    if forbidden_payload_fields:
        verify = {}
        verify_ready = False
        block_reason = "ROLLBACK_APPLY_ADMISSION_BROWSER_FIELD_REJECTED"
        status = "blocked"
        machine_error_code = block_reason
    else:
        verify = rollback_point_verify if isinstance(rollback_point_verify, dict) else {}
        verify_ready = _rollback_point_verify_ready(verify)
        if not verify_ready:
            block_reason = str(
                verify.get("machine_error_code")
                or "ROLLBACK_POINT_VERIFY_REQUIRED"
            )
            machine_error_code = "ROLLBACK_APPLY_ADMISSION_DRY_RUN_BLOCKED"
            status = "blocked"
        else:
            block_reason = ""
            machine_error_code = "ROLLBACK_APPLY_ADMISSION_DRY_RUN_EVALUATED"
            status = "ok"

    contract = recovery_contract if isinstance(recovery_contract, dict) else {}
    process_contract = (
        rollback_process_owner_contract
        if isinstance(rollback_process_owner_contract, dict)
        else {}
    )
    contract_readonly_sources_ok = contract.get("status") == "ok"
    process_owner_contract_ok = _rollback_process_owner_contract_ready(process_contract)
    session_summary = _rollback_apply_admission_dry_run_session_summary(sessions_packet)
    checked_surfaces = [
        _rollback_point_surface_admission_check(
            {
                "id": surface_id,
                "owner": metadata["owner"],
                "status": "contract_metadata_only",
                "filesystem_write_admitted": False,
                "machine_checked": False,
            }
        )
        for surface_id, metadata in ROLLBACK_POINT_ALLOWED_WRITE_SURFACES.items()
    ]
    write_surfaces_all_eligible = all(
        surface["eligible_for_next_contour"] is True for surface in checked_surfaces
    )
    eligibility_inputs_ok = (
        verify_ready
        and contract_readonly_sources_ok
        and process_owner_contract_ok
        and write_surfaces_all_eligible
        and session_summary["session_state_status"] == "ok"
    )
    if status == "ok" and not eligibility_inputs_ok:
        status = "blocked"
        machine_error_code = "ROLLBACK_APPLY_ADMISSION_DRY_RUN_BLOCKED"
        if not contract_readonly_sources_ok:
            block_reason = "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED"
        elif not process_owner_contract_ok:
            block_reason = "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED"
        elif not write_surfaces_all_eligible:
            block_reason = "ROLLBACK_APPLY_WRITE_SURFACES_NOT_ELIGIBLE"
        else:
            block_reason = "SESSION_STATE_READ_REQUIRED"

    admission_result = "eligible_for_next_contour" if status == "ok" else "not_eligible"
    artifact_ref = (
        str(verify.get("rollback_point_artifact_ref") or "")
        if verify_ready
        else ""
    )
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason,
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_APPLY_ADMISSION_DRY_RUN_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-apply/admission-dry-run",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-point/verify",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ["artifact_id", "artifact_path", "digest"],
        "forbidden_fields": forbidden_payload_fields,
        "browser_forbidden_fields_rejected": True,
        "rollback_apply_admission_evaluated": True,
        "rollback_apply_admission_result": admission_result,
        "rollback_apply_admission_eligible_for_next_contour": status == "ok",
        "rollback_apply_admission_scope": "dry_run_next_contour_only",
        "rollback_point_verify_required": True,
        "rollback_point_verify_valid": verify_ready,
        "rollback_point_verified": verify_ready,
        "rollback_point_present": verify_ready,
        "rollback_point_artifact_path_redacted": True,
        "rollback_point_artifact_ref": artifact_ref,
        "rollback_point_manifest_verified": verify.get("rollback_point_manifest_verified") is True,
        "rollback_point_provenance_verified": verify.get("rollback_point_provenance_verified") is True,
        "rollback_point_digest_verified": verify.get("rollback_point_digest_verified") is True,
        "rollback_point_surface_verified": verify.get("rollback_point_surface_verified") is True,
        "source_filesystem_read_performed": verify.get("filesystem_read_performed") is True,
        "source_filesystem_read_scope": verify.get("filesystem_read_scope") or "",
        "recovery_contract_readonly_sources_ok": contract_readonly_sources_ok,
        "rollback_process_owner_contract_ok": process_owner_contract_ok,
        "write_surface_machine_check_performed": True,
        "write_surfaces_all_eligible": write_surfaces_all_eligible,
        "allowed_write_surfaces": checked_surfaces,
        "allowed_write_surface_ids": list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES),
        "forbidden_surfaces": ROLLBACK_POINT_FORBIDDEN_SURFACES,
        **session_summary,
        "filesystem_read_performed": False,
        "filesystem_write_performed": False,
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "rollback_apply_admitted": False,
        "rollback_apply_ready": False,
        "rollback_apply_performed": False,
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_apply_admission_dry_run",
                "status": "evaluated" if status == "ok" else "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "evaluated": True,
                "result": admission_result,
                "disabled_reason_code": block_reason,
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "ready": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_LIVE_NOT_ADMITTED",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": (
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_DRY_RUN_EVALUATED"
            if status == "ok"
            else "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_DRY_RUN_BLOCKED"
        ),
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_LIVE_PREFLIGHT_PASS",
        "next_contour_claimed": False,
    }


def _rollback_apply_admission_dry_run_ready(packet: dict[str, Any]) -> bool:
    required_false_fields = [
        "contract_endpoint_mutation_allowed",
        "browser_payload_allowed",
        "session_state_blocks_apply_admission",
        "filesystem_read_performed",
        "filesystem_write_performed",
        "rollback_apply_admitted",
        "rollback_apply_ready",
        "rollback_apply_performed",
        "rollback_completed",
        "rollback_live_ready",
        "recovery_operator_ready",
        "operator_ready_claimed",
        "rollback_operator_ready",
        "rollback_claimed",
        "process_kill_operator_ready",
        "process_kill_claimed",
        "process_kill_live_ready",
        "process_kill_admitted",
        "process_kill_performed",
        "current_codex_touched",
        "original_codex_touched",
        "current_codex_home_touched",
        "auth_material_touched",
        "auth_material_allowed_surface",
        "secret_value_recorded",
        "arbitrary_path_accepted",
        "arbitrary_path_allowed_surface",
        "dangerous_action_mutation_allowed",
        "next_contour_claimed",
    ]
    required_true_fields = [
        "browser_forbidden_fields_rejected",
        "rollback_apply_admission_evaluated",
        "rollback_apply_admission_eligible_for_next_contour",
        "rollback_point_verify_required",
        "rollback_point_verify_valid",
        "rollback_point_verified",
        "rollback_point_present",
        "rollback_point_artifact_path_redacted",
        "rollback_point_manifest_verified",
        "rollback_point_provenance_verified",
        "rollback_point_digest_verified",
        "rollback_point_surface_verified",
        "recovery_contract_readonly_sources_ok",
        "rollback_process_owner_contract_ok",
        "write_surface_machine_check_performed",
        "write_surfaces_all_eligible",
        "session_state_read_performed",
        "session_state_all_owned",
        "dangerous_actions_disabled",
    ]
    forbidden_fields = packet.get("forbidden_browser_fields")
    allowed_surface_ids = packet.get("allowed_write_surface_ids")
    forbidden_surfaces = packet.get("forbidden_surfaces")
    actions = packet.get("actions")
    action_by_id = {
        action.get("id"): action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    } if isinstance(actions, list) else {}
    admission_action = action_by_id.get("rollback_apply_admission_dry_run", {})
    apply_action = action_by_id.get("rollback_apply", {})
    kill_action = action_by_id.get("process_kill", {})
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "ROLLBACK_APPLY_ADMISSION_DRY_RUN_EVALUATED"
        and packet.get("claim_scope") == ROLLBACK_APPLY_ADMISSION_DRY_RUN_CLAIM_SCOPE
        and packet.get("contract_endpoint")
        == "/api/codex/custom/recovery/rollback-apply/admission-dry-run"
        and packet.get("browser_payload_allowed_keys") == []
        and packet.get("rollback_apply_admission_result") == "eligible_for_next_contour"
        and packet.get("rollback_apply_admission_scope") == "dry_run_next_contour_only"
        and packet.get("session_state_status") == "ok"
        and all(packet.get(field) is False for field in required_false_fields)
        and all(packet.get(field) is True for field in required_true_fields)
        and allowed_surface_ids == list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES)
        and isinstance(forbidden_surfaces, list)
        and all(surface in forbidden_surfaces for surface in ROLLBACK_POINT_FORBIDDEN_SURFACES)
        and isinstance(forbidden_fields, list)
        and all(
            field in forbidden_fields
            for field in FORBIDDEN_BROWSER_FIELDS + ["artifact_id", "artifact_path", "digest"]
        )
        and admission_action.get("status") == "evaluated"
        and admission_action.get("mutation_allowed") is False
        and admission_action.get("browser_payload_allowed") is False
        and admission_action.get("evaluated") is True
        and admission_action.get("result") == "eligible_for_next_contour"
        and apply_action.get("status") == "disabled"
        and apply_action.get("admitted") is False
        and apply_action.get("ready") is False
        and apply_action.get("performed") is False
        and kill_action.get("status") == "disabled"
        and kill_action.get("admitted") is False
        and kill_action.get("performed") is False
    )


def build_custom_recovery_rollback_apply_live_preflight_packet(
    *,
    rollback_apply_admission_dry_run: dict[str, Any] | None = None,
    browser_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate future bounded rollback-apply contour preflight without admitting apply."""

    payload = browser_payload if isinstance(browser_payload, dict) else {}
    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(payload)))
    dry_run = (
        rollback_apply_admission_dry_run
        if isinstance(rollback_apply_admission_dry_run, dict)
        else {}
    )
    if forbidden_payload_fields:
        dry_run_ready = False
        status = "blocked"
        machine_error_code = "ROLLBACK_APPLY_LIVE_PREFLIGHT_BROWSER_FIELD_REJECTED"
        block_reason = "ROLLBACK_APPLY_LIVE_PREFLIGHT_BROWSER_FIELD_REJECTED"
    else:
        dry_run_ready = _rollback_apply_admission_dry_run_ready(dry_run)
        if dry_run_ready:
            status = "ok"
            machine_error_code = "ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED"
            block_reason = ""
        else:
            status = "blocked"
            machine_error_code = "ROLLBACK_APPLY_LIVE_PREFLIGHT_BLOCKED"
            block_reason = str(
                dry_run.get("block_reason_code")
                or dry_run.get("machine_error_code")
                or "ROLLBACK_APPLY_ADMISSION_DRY_RUN_REQUIRED"
            )

    checked_surfaces = [
        _rollback_point_surface_admission_check(
            {
                "id": surface_id,
                "owner": metadata["owner"],
                "status": "contract_metadata_only",
                "filesystem_write_admitted": False,
                "machine_checked": False,
            }
        )
        for surface_id, metadata in ROLLBACK_POINT_ALLOWED_WRITE_SURFACES.items()
    ]
    future_write_surfaces_all_owned = all(
        surface["eligible_for_next_contour"] is True
        and surface["current_codex_excluded"] is True
        and surface["original_codex_excluded"] is True
        and surface["auth_material_excluded"] is True
        and surface["arbitrary_path_excluded"] is True
        for surface in checked_surfaces
    )
    upstream_filesystem_read_performed = (
        dry_run.get("source_filesystem_read_performed") is True and dry_run_ready
    )
    upstream_filesystem_read_scope = (
        str(dry_run.get("source_filesystem_read_scope") or "")
        if upstream_filesystem_read_performed
        else ""
    )
    preflight_result = (
        "eligible_for_bounded_apply_contour"
        if status == "ok"
        else "not_eligible"
    )
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason,
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_APPLY_LIVE_PREFLIGHT_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-apply/live-preflight",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-apply/admission-dry-run",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ["artifact_id", "artifact_path", "digest"],
        "forbidden_fields": forbidden_payload_fields,
        "browser_forbidden_fields_rejected": True,
        "rollback_apply_live_preflight_evaluated": True,
        "rollback_apply_live_preflight_result": preflight_result,
        "rollback_apply_live_preflight_eligible_for_next_contour": status == "ok",
        "rollback_apply_live_preflight_scope": "preflight_next_contour_only",
        "rollback_apply_dry_run_required": True,
        "rollback_apply_dry_run_eligible": dry_run_ready,
        "rollback_point_verified": dry_run.get("rollback_point_verified") is True and dry_run_ready,
        "rollback_point_manifest_verified": (
            dry_run.get("rollback_point_manifest_verified") is True and dry_run_ready
        ),
        "rollback_point_provenance_verified": (
            dry_run.get("rollback_point_provenance_verified") is True and dry_run_ready
        ),
        "rollback_point_digest_verified": (
            dry_run.get("rollback_point_digest_verified") is True and dry_run_ready
        ),
        "rollback_point_surface_verified": (
            dry_run.get("rollback_point_surface_verified") is True and dry_run_ready
        ),
        "rollback_point_artifact_path_redacted": True,
        "rollback_point_artifact_ref": str(dry_run.get("rollback_point_artifact_ref") or "")
        if dry_run_ready
        else "",
        "future_write_surfaces_declared": True,
        "future_write_surfaces_all_owned": future_write_surfaces_all_owned,
        "future_write_surface_machine_check_performed": True,
        "future_write_surfaces": checked_surfaces,
        "future_write_surface_ids": list(ROLLBACK_POINT_ALLOWED_WRITE_SURFACES),
        "forbidden_surfaces": ROLLBACK_POINT_FORBIDDEN_SURFACES,
        "rollback_target_class": "owned_generated_recovery_artifact",
        "rollback_target_browser_supplied": False,
        "current_codex_excluded": True,
        "original_codex_excluded": True,
        "auth_material_excluded": True,
        "arbitrary_path_rejected": True,
        "process_kill_not_admitted": True,
        "source_filesystem_read_performed": upstream_filesystem_read_performed,
        "source_filesystem_read_scope": upstream_filesystem_read_scope,
        "filesystem_read_performed": upstream_filesystem_read_performed,
        "filesystem_read_scope": upstream_filesystem_read_scope,
        "filesystem_write_performed": False,
        "rollback_apply_admitted": False,
        "rollback_apply_ready": False,
        "rollback_apply_performed": False,
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_apply_live_preflight",
                "status": "evaluated" if status == "ok" else "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "evaluated": True,
                "result": preflight_result,
                "disabled_reason_code": block_reason,
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "ready": False,
                "performed": False,
                "disabled_reason_code": "ROLLBACK_APPLY_BOUNDED_LIVE_NOT_ADMITTED",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": (
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED"
            if status == "ok"
            else "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_LIVE_PREFLIGHT_BLOCKED"
        ),
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_PASS",
        "next_contour_claimed": False,
    }


def _rollback_apply_live_preflight_ready(packet: dict[str, Any]) -> bool:
    required_false_fields = [
        "contract_endpoint_mutation_allowed",
        "browser_payload_allowed",
        "filesystem_write_performed",
        "rollback_apply_admitted",
        "rollback_apply_ready",
        "rollback_apply_performed",
        "rollback_completed",
        "rollback_live_ready",
        "recovery_operator_ready",
        "operator_ready_claimed",
        "rollback_operator_ready",
        "rollback_claimed",
        "process_kill_operator_ready",
        "process_kill_claimed",
        "process_kill_live_ready",
        "process_kill_admitted",
        "process_kill_performed",
        "current_codex_touched",
        "original_codex_touched",
        "current_codex_home_touched",
        "auth_material_touched",
        "auth_material_allowed_surface",
        "secret_value_recorded",
        "arbitrary_path_accepted",
        "arbitrary_path_allowed_surface",
        "dangerous_action_mutation_allowed",
        "next_contour_claimed",
    ]
    required_true_fields = [
        "browser_forbidden_fields_rejected",
        "rollback_apply_live_preflight_evaluated",
        "rollback_apply_live_preflight_eligible_for_next_contour",
        "rollback_apply_dry_run_required",
        "rollback_apply_dry_run_eligible",
        "rollback_point_verified",
        "rollback_point_manifest_verified",
        "rollback_point_provenance_verified",
        "rollback_point_digest_verified",
        "rollback_point_surface_verified",
        "rollback_point_artifact_path_redacted",
        "future_write_surfaces_declared",
        "future_write_surfaces_all_owned",
        "future_write_surface_machine_check_performed",
        "current_codex_excluded",
        "original_codex_excluded",
        "auth_material_excluded",
        "arbitrary_path_rejected",
        "process_kill_not_admitted",
        "source_filesystem_read_performed",
        "filesystem_read_performed",
        "dangerous_actions_disabled",
    ]
    forbidden_fields = packet.get("forbidden_browser_fields")
    actions = packet.get("actions")
    action_by_id = {
        action.get("id"): action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    } if isinstance(actions, list) else {}
    preflight_action = action_by_id.get("rollback_apply_live_preflight", {})
    apply_action = action_by_id.get("rollback_apply", {})
    kill_action = action_by_id.get("process_kill", {})
    return (
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED"
        and packet.get("claim_scope") == ROLLBACK_APPLY_LIVE_PREFLIGHT_CLAIM_SCOPE
        and packet.get("contract_endpoint")
        == "/api/codex/custom/recovery/rollback-apply/live-preflight"
        and packet.get("browser_payload_allowed_keys") == []
        and packet.get("rollback_apply_live_preflight_result")
        == "eligible_for_bounded_apply_contour"
        and packet.get("rollback_apply_live_preflight_scope")
        == "preflight_next_contour_only"
        and packet.get("rollback_target_class") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and packet.get("rollback_target_browser_supplied") is False
        and packet.get("filesystem_read_scope") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and packet.get("source_filesystem_read_scope")
        == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and all(packet.get(field) is False for field in required_false_fields)
        and all(packet.get(field) is True for field in required_true_fields)
        and isinstance(packet.get("rollback_point_artifact_ref"), str)
        and bool(packet.get("rollback_point_artifact_ref"))
        and isinstance(forbidden_fields, list)
        and all(
            field in forbidden_fields
            for field in FORBIDDEN_BROWSER_FIELDS + ["artifact_id", "artifact_path", "digest"]
        )
        and isinstance(actions, list)
        and preflight_action.get("status") == "evaluated"
        and preflight_action.get("mutation_allowed") is False
        and preflight_action.get("browser_payload_allowed") is False
        and preflight_action.get("evaluated") is True
        and preflight_action.get("result") == "eligible_for_bounded_apply_contour"
        and apply_action.get("status") == "disabled"
        and apply_action.get("admitted") is False
        and apply_action.get("ready") is False
        and apply_action.get("performed") is False
        and kill_action.get("status") == "disabled"
        and kill_action.get("admitted") is False
        and kill_action.get("performed") is False
    )


def _rollback_apply_failure_packet(
    *,
    preflight_packet: dict[str, Any] | None,
    machine_error_code: str,
    block_reason_code: str,
    forbidden_fields: list[str] | None = None,
    read_attempted: bool = False,
    write_attempted: bool = False,
    receipt_id: str = "",
    receipt_digest: str = "",
) -> dict[str, Any]:
    preflight = preflight_packet if isinstance(preflight_packet, dict) else {}
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_APPLY_BOUNDED_LIVE_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-apply",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-apply/live-preflight",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ["artifact_id", "artifact_path", "digest"],
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "rollback_apply_preflight_required": True,
        "rollback_apply_preflight_valid": False,
        "rollback_apply_bounded_live_performed": False,
        "rollback_apply_receipt_created": False,
        "rollback_apply_receipt_id": receipt_id,
        "rollback_apply_receipt_path_redacted": True,
        "rollback_apply_receipt_ref": (
            f"rollback-apply-receipt:{receipt_digest[:16]}" if receipt_digest else ""
        ),
        "rollback_apply_receipt_digest_present": bool(receipt_digest),
        "rollback_apply_receipt_sha256": receipt_digest,
        "rollback_apply_receipt_provenance_verified": False,
        "rollback_apply_receipt_payload_digest_verified": False,
        "source_preflight_sha256_present": bool(preflight),
        "source_rollback_point_ref": str(preflight.get("rollback_point_artifact_ref") or ""),
        "source_rollback_point_sha256_present": False,
        "rollback_point_verified": False,
        "rollback_point_artifact_path_redacted": True,
        "filesystem_read_performed": read_attempted,
        "filesystem_read_scope": (
            ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE if read_attempted else ""
        ),
        "filesystem_write_performed": write_attempted,
        "filesystem_write_scope": (
            ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE if write_attempted else ""
        ),
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "rollback_apply_admitted": False,
        "rollback_apply_ready": False,
        "rollback_apply_performed": False,
        "rollback_apply_completed_scope": "not_completed",
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_apply",
                "status": "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "ready": False,
                "performed": False,
                "disabled_reason_code": block_reason_code,
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_BLOCKED",
        "next_contour": "CUSTOM_CODEX_RECOVERY_APPLY_RECEIPT_VERIFY_PASS",
        "next_contour_claimed": False,
    }


def build_custom_recovery_rollback_apply_bounded_live_packet(
    *,
    rollback_apply_live_preflight: dict[str, Any] | None = None,
    browser_payload: dict[str, Any] | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Write a bounded WBP-owned rollback apply receipt without restoring runtime state."""

    if browser_payload is None:
        payload: dict[str, Any] = {}
    elif isinstance(browser_payload, dict):
        payload = browser_payload
    else:
        return _rollback_apply_failure_packet(
            preflight_packet=rollback_apply_live_preflight,
            machine_error_code="ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
            block_reason_code="ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
            forbidden_fields=["invalid_body"],
        )
    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(payload)))
    if forbidden_payload_fields:
        return _rollback_apply_failure_packet(
            preflight_packet=rollback_apply_live_preflight,
            machine_error_code="ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
            block_reason_code="ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
            forbidden_fields=forbidden_payload_fields,
        )

    preflight = (
        rollback_apply_live_preflight
        if isinstance(rollback_apply_live_preflight, dict)
        else {}
    )
    if not _rollback_apply_live_preflight_ready(preflight):
        return _rollback_apply_failure_packet(
            preflight_packet=preflight,
            machine_error_code="ROLLBACK_APPLY_PREFLIGHT_NOT_ELIGIBLE",
            block_reason_code=str(
                preflight.get("block_reason_code")
                or preflight.get("machine_error_code")
                or "ROLLBACK_APPLY_LIVE_PREFLIGHT_REQUIRED"
            ),
        )

    root = _rollback_point_artifact_root(artifact_root)
    receipt_id = f"rap-{uuid.uuid4().hex}"
    receipt_path = (root / f"{receipt_id}.json").resolve()
    if not _path_under_root(receipt_path, root):
        return _rollback_apply_failure_packet(
            preflight_packet=preflight,
            machine_error_code="ROLLBACK_APPLY_FORBIDDEN_WRITE_SURFACE",
            block_reason_code="ROLLBACK_APPLY_FORBIDDEN_WRITE_SURFACE",
            receipt_id=receipt_id,
        )

    now = utc_now()
    source_preflight_sha = _stable_digest(preflight)
    source_ref = str(preflight.get("rollback_point_artifact_ref") or "")
    receipt_payload = {
        "schema_version": 1,
        "artifact_kind": ROLLBACK_APPLY_RECEIPT_ARTIFACT_KIND,
        "created_at_utc": now,
        "claim_scope": ROLLBACK_APPLY_BOUNDED_LIVE_CLAIM_SCOPE,
        "source_preflight_sha256": source_preflight_sha,
        "source_preflight_packet": preflight,
        "source_rollback_point_ref": source_ref,
        "source_rollback_point_sha256_present": False,
        "write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "write_surface_scope": ROLLBACK_POINT_ALLOWED_WRITE_SURFACES[
            ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        ]["scope"],
        "rollback_apply_completed_scope": "bounded_apply_receipt_only",
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "secret_value_recorded": False,
        "process_kill_performed": False,
        "recovery_operator_ready": False,
    }
    receipt_payload = {
        **receipt_payload,
        "receipt_payload_sha256": _stable_digest(receipt_payload),
    }
    try:
        receipt_path.write_text(
            json.dumps(receipt_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        receipt_path.chmod(0o600)
        receipt_digest = _sha256_file(receipt_path)
        readback = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _rollback_apply_failure_packet(
            preflight_packet=preflight,
            machine_error_code="ROLLBACK_APPLY_RECEIPT_WRITE_FAILED",
            block_reason_code=str(type(exc).__name__),
            write_attempted=True,
            receipt_id=receipt_id,
        )

    receipt_payload_digest_verified = (
        isinstance(readback, dict)
        and readback.get("receipt_payload_sha256")
        == _stable_digest(
            {
                key: value
                for key, value in readback.items()
                if key != "receipt_payload_sha256"
            }
        )
    )
    receipt_truth_ok = (
        receipt_payload_digest_verified
        and readback.get("artifact_kind") == ROLLBACK_APPLY_RECEIPT_ARTIFACT_KIND
        and readback.get("claim_scope") == ROLLBACK_APPLY_BOUNDED_LIVE_CLAIM_SCOPE
        and readback.get("source_preflight_sha256") == source_preflight_sha
        and readback.get("source_rollback_point_ref") == source_ref
        and readback.get("write_surface_id") == ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
        and readback.get("current_codex_touched") is False
        and readback.get("original_codex_touched") is False
        and readback.get("current_codex_home_touched") is False
        and readback.get("auth_material_touched") is False
        and readback.get("secret_value_recorded") is False
        and readback.get("process_kill_performed") is False
        and readback.get("recovery_operator_ready") is False
    )
    if not receipt_truth_ok:
        return _rollback_apply_failure_packet(
            preflight_packet=preflight,
            machine_error_code="ROLLBACK_APPLY_RECEIPT_VERIFICATION_FAILED",
            block_reason_code="ROLLBACK_APPLY_RECEIPT_VERIFICATION_FAILED",
            read_attempted=True,
            write_attempted=True,
            receipt_id=receipt_id,
            receipt_digest=receipt_digest,
        )

    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED",
        "block_reason_code": "",
        "captured_at_utc": now,
        "claim_scope": ROLLBACK_APPLY_BOUNDED_LIVE_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-apply",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-apply/live-preflight",
        "contract_endpoint_mutation_allowed": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ["artifact_id", "artifact_path", "digest"],
        "forbidden_fields": [],
        "browser_forbidden_fields_rejected": True,
        "rollback_apply_preflight_required": True,
        "rollback_apply_preflight_valid": True,
        "rollback_apply_bounded_live_performed": True,
        "rollback_apply_receipt_created": True,
        "rollback_apply_receipt_id": receipt_id,
        "rollback_apply_receipt_path_redacted": True,
        "rollback_apply_receipt_ref": f"rollback-apply-receipt:{receipt_digest[:16]}",
        "rollback_apply_receipt_digest_present": True,
        "rollback_apply_receipt_sha256": receipt_digest,
        "rollback_apply_receipt_provenance_verified": True,
        "rollback_apply_receipt_payload_digest_verified": True,
        "source_preflight_sha256_present": True,
        "source_rollback_point_ref": source_ref,
        "source_rollback_point_sha256_present": False,
        "rollback_point_verified": True,
        "rollback_point_artifact_path_redacted": True,
        "filesystem_read_performed": True,
        "filesystem_read_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "filesystem_write_performed": True,
        "filesystem_write_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "selected_write_surface_id": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "rollback_apply_admitted": True,
        "rollback_apply_ready": True,
        "rollback_apply_performed": True,
        "rollback_apply_completed_scope": "bounded_apply_receipt_only",
        "rollback_completed": True,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_apply",
                "status": "performed",
                "mutation_allowed": True,
                "browser_payload_allowed": False,
                "admitted": True,
                "ready": True,
                "performed": True,
                "completed_scope": "bounded_apply_receipt_only",
                "disabled_reason_code": "",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED",
        "next_contour": "CUSTOM_CODEX_RECOVERY_APPLY_RECEIPT_VERIFY_PASS",
        "next_contour_claimed": False,
    }


def _rollback_apply_receipt_verify_failure_packet(
    *,
    machine_error_code: str,
    block_reason_code: str,
    forbidden_fields: list[str] | None = None,
    receipt_id: str = "",
    receipt_digest: str = "",
    read_attempted: bool = False,
    selection_ambiguous: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "block_reason_code": block_reason_code,
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_APPLY_RECEIPT_VERIFY_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-apply/receipt/verify",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-apply",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ROLLBACK_APPLY_RECEIPT_VERIFY_EXTRA_FORBIDDEN_FIELDS,
        "forbidden_fields": forbidden_fields or [],
        "browser_forbidden_fields_rejected": True,
        "receipt_verify_performed": False,
        "receipt_verified": False,
        "rollback_apply_receipt_verified": False,
        "verified_scope": "not_verified",
        "receipt_selection_source": "server_owned_latest_valid_receipt",
        "receipt_selection_ambiguous": selection_ambiguous,
        "receipt_id": receipt_id,
        "receipt_path_redacted": True,
        "receipt_ref": f"rollback-apply-receipt:{receipt_digest[:16]}" if receipt_digest else "",
        "receipt_digest_present": bool(receipt_digest),
        "receipt_sha256": receipt_digest,
        "receipt_payload_digest_verified": False,
        "receipt_provenance_verified": False,
        "source_preflight_sha256_present": False,
        "source_rollback_point_ref_present": False,
        "filesystem_read_performed": read_attempted,
        "filesystem_read_scope": (
            ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE if read_attempted else ""
        ),
        "filesystem_write_performed": False,
        "rollback_apply_performed": False,
        "rollback_apply_completed_scope": "not_completed",
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "actions": [
            {
                "id": "rollback_apply_receipt_verify",
                "status": "blocked",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "performed": False,
                "verified": False,
                "disabled_reason_code": block_reason_code,
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "performed": False,
                "disabled_reason_code": "RECEIPT_VERIFY_READ_ONLY",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_RECEIPT_VERIFY_BLOCKED",
        "next_contour": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_PASS",
        "next_contour_claimed": False,
    }


def _read_rollback_apply_receipt_artifact(
    path: Path,
    root: Path,
) -> tuple[dict[str, Any] | None, str]:
    if not _path_under_root(path, root):
        return None, "ROLLBACK_APPLY_RECEIPT_VERIFY_FORBIDDEN_SURFACE"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "ROLLBACK_APPLY_RECEIPT_VERIFY_SCHEMA_INVALID"
    if not isinstance(payload, dict):
        return None, "ROLLBACK_APPLY_RECEIPT_VERIFY_SCHEMA_INVALID"
    return payload, ""


def _rollback_point_ref_exists(root: Path, expected_ref: str) -> bool:
    if not expected_ref.startswith("rollback-point:"):
        return False
    for path in root.glob("crp-*.json"):
        if not path.is_file():
            continue
        artifact_path = path.resolve()
        artifact, read_error = _read_rollback_point_artifact(artifact_path, root)
        if read_error or artifact is None:
            continue
        if _rollback_point_payload_error(artifact):
            continue
        if f"rollback-point:{_sha256_file(artifact_path)[:16]}" == expected_ref:
            return True
    return False


def _rollback_apply_receipt_payload_error(payload: dict[str, Any], root: Path) -> str:
    if payload.get("schema_version") != 1:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_SCHEMA_INVALID"
    if payload.get("artifact_kind") != ROLLBACK_APPLY_RECEIPT_ARTIFACT_KIND:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_KIND_INVALID"
    if payload.get("claim_scope") != ROLLBACK_APPLY_BOUNDED_LIVE_CLAIM_SCOPE:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_SCOPE_INVALID"
    if not _rollback_point_created_at_valid(payload.get("created_at_utc")):
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_TIMESTAMP_INVALID"
    if payload.get("rollback_apply_completed_scope") != "bounded_apply_receipt_only":
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_SCOPE_INVALID"
    source_preflight_sha = payload.get("source_preflight_sha256")
    source_preflight_sha_valid = (
        isinstance(source_preflight_sha, str)
        and len(source_preflight_sha) == 64
        and all(character in "0123456789abcdef" for character in source_preflight_sha)
    )
    if not source_preflight_sha_valid:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROVENANCE_MISSING"
    source_preflight = payload.get("source_preflight_packet")
    if not isinstance(source_preflight, dict):
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROVENANCE_MISSING"
    if _stable_digest(source_preflight) != source_preflight_sha:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_DIGEST_MISMATCH"
    if not _rollback_apply_live_preflight_ready(source_preflight):
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROVENANCE_MISSING"
    source_ref = payload.get("source_rollback_point_ref")
    if not isinstance(source_ref, str) or not source_ref.startswith("rollback-point:"):
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROVENANCE_MISSING"
    if source_preflight.get("rollback_point_artifact_ref") != source_ref:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROVENANCE_MISSING"
    if not _rollback_point_ref_exists(root, source_ref):
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROVENANCE_MISSING"
    if payload.get("write_surface_id") != ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_FORBIDDEN_SURFACE"
    expected_scope = ROLLBACK_POINT_ALLOWED_WRITE_SURFACES[
        ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE
    ]["scope"]
    if payload.get("write_surface_scope") != expected_scope:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_FORBIDDEN_SURFACE"
    if payload.get("current_codex_touched") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_TOUCH_FLAG_DETECTED"
    if payload.get("original_codex_touched") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_TOUCH_FLAG_DETECTED"
    if payload.get("current_codex_home_touched") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_TOUCH_FLAG_DETECTED"
    if payload.get("auth_material_touched") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_SECRET_LEAK_DETECTED"
    if payload.get("secret_value_recorded") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_SECRET_LEAK_DETECTED"
    if payload.get("process_kill_performed") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_PROCESS_KILL_DETECTED"
    if payload.get("recovery_operator_ready") is not False:
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_OPERATOR_READY_CLAIMED"
    if payload.get("receipt_payload_sha256") != _stable_digest(
        {
            key: value
            for key, value in payload.items()
            if key != "receipt_payload_sha256"
        }
    ):
        return "ROLLBACK_APPLY_RECEIPT_VERIFY_DIGEST_MISMATCH"
    return ""


def build_custom_recovery_rollback_apply_receipt_verify_packet(
    *,
    artifact_root: Path | None = None,
    browser_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify the latest server-owned bounded apply receipt without writing."""

    payload = browser_payload if isinstance(browser_payload, dict) else {}
    forbidden_payload_fields = sorted(set(_forbidden_payload_fields(payload)))
    if forbidden_payload_fields:
        return _rollback_apply_receipt_verify_failure_packet(
            machine_error_code="ROLLBACK_APPLY_RECEIPT_VERIFY_BROWSER_FIELD_REJECTED",
            block_reason_code="ROLLBACK_APPLY_RECEIPT_VERIFY_BROWSER_FIELD_REJECTED",
            forbidden_fields=forbidden_payload_fields,
        )

    root = _rollback_point_artifact_root_readonly(artifact_root)
    if not root.exists() or not root.is_dir():
        return _rollback_apply_receipt_verify_failure_packet(
            machine_error_code="ROLLBACK_APPLY_RECEIPT_VERIFY_NOT_FOUND",
            block_reason_code="ROLLBACK_APPLY_RECEIPT_VERIFY_NOT_FOUND",
        )

    paths = sorted(
        (path.resolve() for path in root.glob("rap-*.json") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    if not paths:
        return _rollback_apply_receipt_verify_failure_packet(
            machine_error_code="ROLLBACK_APPLY_RECEIPT_VERIFY_NOT_FOUND",
            block_reason_code="ROLLBACK_APPLY_RECEIPT_VERIFY_NOT_FOUND",
        )

    candidates: list[tuple[Path, dict[str, Any], str]] = []
    first_error = ""
    first_receipt_id = ""
    first_receipt_sha = ""
    for path in paths:
        receipt_id = path.stem
        payload, read_error = _read_rollback_apply_receipt_artifact(path, root)
        file_sha = _sha256_file(path) if path.exists() else ""
        if read_error:
            if not first_error:
                first_error = read_error
                first_receipt_id = receipt_id
                first_receipt_sha = file_sha
            continue
        assert payload is not None
        payload_error = _rollback_apply_receipt_payload_error(payload, root)
        if payload_error:
            if not first_error:
                first_error = payload_error
                first_receipt_id = receipt_id
                first_receipt_sha = file_sha
            continue
        created_at = str(payload.get("created_at_utc") or "")
        candidates.append((path, payload, created_at))

    if not candidates:
        error = first_error or "ROLLBACK_APPLY_RECEIPT_VERIFY_NOT_FOUND"
        return _rollback_apply_receipt_verify_failure_packet(
            machine_error_code=error,
            block_reason_code=error,
            receipt_id=first_receipt_id,
            receipt_digest=first_receipt_sha,
            read_attempted=bool(first_receipt_id),
        )

    candidates.sort(key=lambda item: (item[2], item[0].name), reverse=True)
    newest_created_at = candidates[0][2]
    ambiguous = len([item for item in candidates if item[2] == newest_created_at]) > 1
    if ambiguous:
        return _rollback_apply_receipt_verify_failure_packet(
            machine_error_code="ROLLBACK_APPLY_RECEIPT_VERIFY_AMBIGUOUS_SELECTION",
            block_reason_code="ROLLBACK_APPLY_RECEIPT_VERIFY_AMBIGUOUS_SELECTION",
            receipt_id=candidates[0][0].stem,
            receipt_digest=_sha256_file(candidates[0][0]),
            read_attempted=True,
            selection_ambiguous=True,
        )

    selected_path, selected_payload, _created_at = candidates[0]
    receipt_sha = _sha256_file(selected_path)
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "ROLLBACK_APPLY_RECEIPT_VERIFY_READY",
        "block_reason_code": "",
        "captured_at_utc": utc_now(),
        "claim_scope": ROLLBACK_APPLY_RECEIPT_VERIFY_CLAIM_SCOPE,
        "contract_endpoint": "/api/codex/custom/recovery/rollback-apply/receipt/verify",
        "contract_source_endpoint": "/api/codex/custom/recovery/rollback-apply",
        "contract_endpoint_mutation_allowed": False,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "forbidden_browser_fields": FORBIDDEN_BROWSER_FIELDS
        + ROLLBACK_APPLY_RECEIPT_VERIFY_EXTRA_FORBIDDEN_FIELDS,
        "forbidden_fields": [],
        "browser_forbidden_fields_rejected": True,
        "receipt_verify_performed": True,
        "receipt_verified": True,
        "rollback_apply_receipt_verified": True,
        "verified_scope": "bounded_apply_receipt_only",
        "receipt_selection_source": "server_owned_latest_valid_receipt",
        "receipt_selection_ambiguous": False,
        "receipt_id": selected_path.stem,
        "receipt_path_redacted": True,
        "receipt_ref": f"rollback-apply-receipt:{receipt_sha[:16]}",
        "receipt_digest_present": True,
        "receipt_sha256": receipt_sha,
        "receipt_payload_digest_verified": True,
        "receipt_provenance_verified": True,
        "source_preflight_sha256_present": True,
        "source_rollback_point_ref_present": True,
        "source_rollback_point_ref": str(selected_payload.get("source_rollback_point_ref") or ""),
        "filesystem_read_performed": True,
        "filesystem_read_scope": ROLLBACK_POINT_CREATE_SELECTED_WRITE_SURFACE,
        "filesystem_write_performed": False,
        "rollback_apply_performed": False,
        "rollback_apply_completed_scope": "not_performed_by_verify",
        "rollback_completed": False,
        "rollback_live_ready": False,
        "recovery_operator_ready": False,
        "operator_ready_claimed": False,
        "rollback_operator_ready": False,
        "rollback_claimed": False,
        "process_kill_operator_ready": False,
        "process_kill_claimed": False,
        "process_kill_live_ready": False,
        "process_kill_admitted": False,
        "process_kill_performed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "current_codex_home_touched": False,
        "auth_material_touched": False,
        "auth_material_allowed_surface": False,
        "secret_value_recorded": False,
        "arbitrary_path_accepted": False,
        "arbitrary_path_allowed_surface": False,
        "dangerous_actions_disabled": True,
        "dangerous_action_mutation_allowed": False,
        "human_summary": "receipt verified · not system recovery",
        "actions": [
            {
                "id": "rollback_apply_receipt_verify",
                "status": "verified",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "performed": True,
                "verified": True,
                "verified_scope": "bounded_apply_receipt_only",
                "disabled_reason_code": "",
            },
            {
                "id": "rollback_apply",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "performed": False,
                "disabled_reason_code": "RECEIPT_VERIFY_READ_ONLY",
            },
            {
                "id": "process_kill",
                "status": "disabled",
                "mutation_allowed": False,
                "browser_payload_allowed": False,
                "admitted": False,
                "performed": False,
                "disabled_reason_code": "PROCESS_KILL_NOT_ADMITTED",
            },
        ],
        "result_token": "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_RECEIPT_VERIFY_READY",
        "next_contour": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_PASS",
        "next_contour_claimed": False,
    }
