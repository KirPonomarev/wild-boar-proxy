# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom recovery contract packets for the WBP web UI."""

from __future__ import annotations

from typing import Any

from wild_boar_proxy.codex_launch_modes import utc_now


FORBIDDEN_BROWSER_FIELDS = [
    "backend_id",
    "route_id",
    "path",
    "snapshot_path",
    "rollback_target",
    "pid",
    "process_id",
    "token",
    "auth",
    "api_key",
    "secret",
    "CODEX_HOME",
    "HOME",
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


def _server_selected_session(sessions_packet: dict[str, Any] | None) -> dict[str, Any] | None:
    sessions = sessions_packet.get("sessions") if isinstance(sessions_packet, dict) else None
    if not isinstance(sessions, list):
        return None
    for session in sessions:
        if isinstance(session, dict) and session.get("cleanup_state") != "cleaned":
            return session
    for session in sessions:
        if isinstance(session, dict):
            return session
    return None


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

    selected_session = _server_selected_session(sessions)
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
    selected_session_available = selected_session_packet_valid and selected_cleanup_state != "cleaned"
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
