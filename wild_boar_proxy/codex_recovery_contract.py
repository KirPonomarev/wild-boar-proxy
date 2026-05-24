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
    "token",
    "auth",
    "api_key",
    "secret",
    "CODEX_HOME",
    "HOME",
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
        "next_contour": "CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS",
        "next_contour_precondition": (
            "Only actions with machine-backed owner contract and dry-run proof may be promoted."
        ),
    }
