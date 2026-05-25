# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Contract-only validators for WBP native Codex launch claims.

This module intentionally does not launch Codex.app or mutate runtime state.
It defines the packet boundary that later live contours must satisfy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


NATIVE_LAUNCH_MODES = ("CODEX_CUSTOM_NATIVE_APP", "ORIGINAL_CODEX_VIA_WBP")
ADMISSION_TARGET_CANDIDATE_SOURCES = (
    "repo_or_server_owned_launcher_candidate",
    "owner_admitted_external_app_candidate",
)
ADMISSION_IDENTITY_FIELDS = (
    "wbp_action_id",
    "launch_mode",
    "process_id",
    "process_lineage",
    "window_id_or_title",
    "profile_dir",
    "codex_home",
    "route_endpoint",
    "trace_id",
    "cleanup_command",
)

CLIENT_ALLOWED_COMMAND_FIELDS = {
    "schema_version",
    "command_id",
    "launch_mode",
    "request_id",
    "operator_intent",
}

CLIENT_FORBIDDEN_AUTHORITY_FIELDS = {
    "api_key",
    "apikey",
    "auth",
    "auth_path",
    "authorization",
    "backend",
    "backend_id",
    "base_url",
    "codex_home",
    "command",
    "data_dir",
    "endpoint",
    "env",
    "executable",
    "home",
    "http_proxy",
    "https_proxy",
    "model",
    "model_id",
    "openai_base_url",
    "path",
    "pid",
    "port",
    "process_id",
    "profile",
    "profile_dir",
    "profile_root",
    "proxy",
    "route",
    "route_endpoint",
    "route_id",
    "secret",
    "token",
    "trace_id",
}

COMMON_PACKET_REQUIRED_FIELDS = {
    "schema_version",
    "claim_id",
    "launch_mode",
    "wbp_action_id",
    "process_id",
    "process_lineage",
    "window_id_or_title",
    "profile_dir",
    "codex_home",
    "route_endpoint",
    "trace_id",
    "cleanup_command",
    "current_codex_touched",
    "process_started",
    "window_observed",
    "native_window_usable",
    "prompt_surface_observed",
    "route_trace_bound",
    "workbench_ready",
    "protected_baseline_only",
}

CUSTOM_PACKET_REQUIRED_FIELDS = {
    "isolated_home",
    "isolated_codex_home",
    "isolated_profile_dir",
    "server_owned_route_configuration",
}

ORIGINAL_PACKET_REQUIRED_FIELDS = {
    "ordinary_codex_app_identity",
    "temporary_wbp_route_config",
    "permanent_user_config_mutated",
    "custom_home_present",
    "custom_codex_home_present",
    "before_profile_hash",
    "during_wbp_route_config",
    "after_cleanup_profile_hash",
    "restart_without_wbp_status",
}

CUSTOM_ADMISSION_REQUIRED_PLAN_FIELDS = {
    "target_candidate_source",
    "isolated_home_plan",
    "isolated_codex_home_plan",
    "isolated_profile_data_dir_plan",
    "server_planned_route_endpoint",
    "port_separation_plan",
    "cleanup_command_plan",
    "rollback_expectation_declared",
    "current_codex_snapshot_plan",
    "write_surfaces_declared",
}

ORIGINAL_ADMISSION_REQUIRED_PLAN_FIELDS = {
    "ordinary_codex_app_identity_candidate",
    "temporary_wbp_route_config_plan",
    "permanent_user_config_mutation_blocked",
    "custom_home_blocked",
    "custom_codex_home_blocked",
    "before_profile_config_hash_plan",
    "cleanup_command_plan",
    "restart_without_wbp_proof_plan",
    "rollback_expectation_declared",
    "write_surfaces_declared",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _field_paths(payload: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            paths.append(key_path)
            paths.extend(_field_paths(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            paths.extend(_field_paths(value, f"{prefix}[{index}]"))
    return paths


def forbidden_native_launch_command_fields(payload: Any) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = key_text
            if key_text not in CLIENT_ALLOWED_COMMAND_FIELDS:
                findings.append(key_path)
            if key_text.lower() in CLIENT_FORBIDDEN_AUTHORITY_FIELDS:
                findings.append(key_path)
            for nested in _field_paths(value, key_path):
                leaf = nested.split(".")[-1]
                if "[" in leaf:
                    leaf = leaf.split("[", 1)[0]
                if leaf.lower() in CLIENT_FORBIDDEN_AUTHORITY_FIELDS:
                    findings.append(nested)
                elif "." in nested or "[" in nested:
                    findings.append(nested)
    elif payload is not None:
        findings.append("<payload>")
    return sorted(set(findings))


def build_native_launch_contract_packet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "OK",
        "captured_at_utc": utc_now(),
        "contract_scope": "contract_only_no_runtime_launch",
        "live_launch_performed": False,
        "runtime_mutation_performed": False,
        "ui_mutation_performed": False,
        "allowed_launch_modes": list(NATIVE_LAUNCH_MODES),
        "client_allowed_command_fields": sorted(CLIENT_ALLOWED_COMMAND_FIELDS),
        "client_forbidden_authority_fields": sorted(CLIENT_FORBIDDEN_AUTHORITY_FIELDS),
        "common_packet_required_fields": sorted(COMMON_PACKET_REQUIRED_FIELDS),
        "mode_packet_required_fields": {
            "CODEX_CUSTOM_NATIVE_APP": sorted(CUSTOM_PACKET_REQUIRED_FIELDS),
            "ORIGINAL_CODEX_VIA_WBP": sorted(ORIGINAL_PACKET_REQUIRED_FIELDS),
        },
        "negative_substitution_checks": [
            "process_started_is_not_usable_native_window",
            "window_observed_is_not_routed_prompt_proof",
            "workbench_ready_is_not_native_app_launch",
            "protected_baseline_is_not_original_via_wbp",
        ],
    }


def build_native_launch_write_surface_packet(
    launch_mode: str,
    declared_write_surfaces: list[str] | None = None,
) -> dict[str, Any]:
    declared = [
        str(surface)
        for surface in (declared_write_surfaces or [])
        if isinstance(surface, str) and surface.strip()
    ]
    return {
        **_admission_common_packet(launch_mode=launch_mode),
        "packet_kind": "native_launch_write_surface",
        "status": "ok" if declared else "blocked",
        "machine_error_code": "OK" if declared else "NATIVE_LAUNCH_WRITE_SURFACES_MISSING",
        "declared_write_surfaces": declared,
        "write_surfaces_declared": bool(declared),
        "browser_supplied_write_surfaces_allowed": False,
    }


def build_native_launch_cleanup_contract_packet(
    launch_mode: str,
    *,
    cleanup_command_planned: bool,
    rollback_expectation_declared: bool,
) -> dict[str, Any]:
    cleanup_ready = cleanup_command_planned and rollback_expectation_declared
    return {
        **_admission_common_packet(launch_mode=launch_mode),
        "packet_kind": "native_launch_cleanup_contract",
        "status": "ok" if cleanup_ready else "blocked",
        "machine_error_code": "OK" if cleanup_ready else "NATIVE_LAUNCH_CLEANUP_ROLLBACK_MISSING",
        "cleanup_command_planned": cleanup_command_planned,
        "rollback_expectation_declared": rollback_expectation_declared,
        "cleanup_contract_required": True,
        "rollback_required": True,
    }


def build_native_launch_identity_fields_packet(launch_mode: str) -> dict[str, Any]:
    return {
        **_admission_common_packet(launch_mode=launch_mode),
        "packet_kind": "native_launch_identity_fields",
        "status": "ok",
        "machine_error_code": "OK",
        "identity_chain_required_fields": list(ADMISSION_IDENTITY_FIELDS),
        "identity_chain_fields_reserved": True,
        "identity_chain_proven": False,
        "live_process_observed": False,
        "native_window_observed": False,
        "route_trace_bound": False,
    }


def build_native_custom_preflight_packet(
    payload: dict[str, Any],
    server_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_native_launch_admission_packet(
        payload,
        server_plan,
        expected_mode="CODEX_CUSTOM_NATIVE_APP",
        required_plan_fields=CUSTOM_ADMISSION_REQUIRED_PLAN_FIELDS,
    )


def build_native_original_preflight_packet(
    payload: dict[str, Any],
    server_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_native_launch_admission_packet(
        payload,
        server_plan,
        expected_mode="ORIGINAL_CODEX_VIA_WBP",
        required_plan_fields=ORIGINAL_ADMISSION_REQUIRED_PLAN_FIELDS,
    )


def build_native_launch_admission_packet(
    payload: dict[str, Any],
    server_plan: dict[str, Any] | None = None,
    *,
    expected_mode: str | None = None,
    required_plan_fields: set[str] | None = None,
) -> dict[str, Any]:
    command = validate_native_launch_command(payload)
    mode = str(payload.get("launch_mode", "")) if isinstance(payload, dict) else ""
    base = _admission_common_packet(launch_mode=mode)
    if command.get("status") != "ok":
        return {
            **base,
            "status": "rejected",
            "machine_error_code": command.get("machine_error_code", "NATIVE_LAUNCH_COMMAND_REJECTED"),
            "admission_status": "rejected",
            "admitted": False,
            "command_validation_packet": command,
            "failed_checks": command.get("failed_checks", []),
            "missing_plan_fields": [],
        }
    if expected_mode and mode != expected_mode:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "NATIVE_LAUNCH_ADMISSION_MODE_MISMATCH",
            "admission_status": "rejected",
            "admitted": False,
            "command_validation_packet": command,
            "failed_checks": ["launch_mode_does_not_match_preflight_builder"],
            "missing_plan_fields": [],
        }

    server_plan = server_plan if isinstance(server_plan, dict) else {}
    required = set(required_plan_fields or ())
    failed_checks = _admission_failed_checks(mode, server_plan)
    missing_plan_fields = sorted(field for field in required if field not in server_plan)
    write_surfaces = _declared_write_surfaces(server_plan)
    admitted = not failed_checks and not missing_plan_fields
    return {
        **base,
        "status": "ok" if admitted else "blocked",
        "machine_error_code": "OK" if admitted else "NATIVE_LAUNCH_ADMISSION_BLOCKED",
        "packet_kind": "native_launch_admission",
        "admission_status": "admitted" if admitted else "blocked",
        "admitted": admitted,
        "command_validation_packet": command,
        "target_candidate_source": _safe_target_candidate_source(server_plan),
        "target_candidate_path_redacted": True,
        "route_endpoint_redacted": True,
        "declared_write_surfaces": write_surfaces,
        "write_surfaces_declared": bool(write_surfaces),
        "cleanup_command_planned": server_plan.get("cleanup_command_plan") is True,
        "rollback_expectation_declared": server_plan.get("rollback_expectation_declared") is True,
        "identity_chain_required_fields": list(ADMISSION_IDENTITY_FIELDS),
        "identity_chain_fields_reserved": True,
        "identity_chain_proven": False,
        "live_process_observed": False,
        "native_window_observed": False,
        "route_trace_bound": False,
        "process_proof_status": "not_attempted",
        "window_proof_status": "not_attempted",
        "route_inference_status": "not_attempted",
        "native_launch_complete": False,
        "missing_plan_fields": missing_plan_fields,
        "failed_checks": failed_checks,
    }


def validate_native_launch_command(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden = forbidden_native_launch_command_fields(payload)
    mode = payload.get("launch_mode") if isinstance(payload, dict) else None
    if forbidden:
        return _validation_packet(
            status="rejected",
            machine_error_code="NATIVE_LAUNCH_COMMAND_FORBIDDEN_FIELD",
            accepted=False,
            launch_mode=mode,
            forbidden_fields=forbidden,
            missing_fields=[],
            failed_checks=["client_may_not_supply_authority_fields"],
        )
    missing = [
        field
        for field in ("schema_version", "command_id", "launch_mode")
        if field not in payload
    ]
    if missing:
        return _validation_packet(
            status="rejected",
            machine_error_code="NATIVE_LAUNCH_COMMAND_MISSING_FIELD",
            accepted=False,
            launch_mode=mode,
            forbidden_fields=[],
            missing_fields=missing,
            failed_checks=["required_command_fields_missing"],
        )
    if mode not in NATIVE_LAUNCH_MODES:
        return _validation_packet(
            status="rejected",
            machine_error_code="NATIVE_LAUNCH_MODE_UNKNOWN",
            accepted=False,
            launch_mode=mode,
            forbidden_fields=[],
            missing_fields=[],
            failed_checks=["launch_mode_not_in_contract"],
        )
    return _validation_packet(
        status="ok",
        machine_error_code="OK",
        accepted=True,
        launch_mode=mode,
        forbidden_fields=[],
        missing_fields=[],
        failed_checks=[],
    )


def _admission_failed_checks(mode: str, server_plan: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if not _declared_write_surfaces(server_plan):
        failed.append("write_surfaces_required")
    if server_plan.get("cleanup_command_plan") is not True:
        failed.append("cleanup_command_plan_required")
    if server_plan.get("rollback_expectation_declared") is not True:
        failed.append("rollback_expectation_required")

    if mode == "CODEX_CUSTOM_NATIVE_APP":
        if _safe_target_candidate_source(server_plan) not in ADMISSION_TARGET_CANDIDATE_SOURCES:
            failed.append("custom_requires_classified_target_candidate_source")
        for field, check in (
            ("isolated_home_plan", "custom_requires_isolated_home_plan"),
            ("isolated_codex_home_plan", "custom_requires_isolated_codex_home_plan"),
            ("isolated_profile_data_dir_plan", "custom_requires_isolated_profile_data_dir_plan"),
            ("server_planned_route_endpoint", "custom_requires_server_planned_route_endpoint"),
            ("port_separation_plan", "custom_requires_port_separation_plan"),
            ("current_codex_snapshot_plan", "custom_requires_current_codex_snapshot_plan"),
        ):
            if server_plan.get(field) is not True:
                failed.append(check)
    elif mode == "ORIGINAL_CODEX_VIA_WBP":
        for field, check in (
            ("ordinary_codex_app_identity_candidate", "original_requires_identity_candidate"),
            ("temporary_wbp_route_config_plan", "original_requires_temporary_wbp_route_config_plan"),
            (
                "permanent_user_config_mutation_blocked",
                "original_requires_permanent_config_mutation_blocked",
            ),
            ("custom_home_blocked", "original_requires_custom_home_blocked"),
            ("custom_codex_home_blocked", "original_requires_custom_codex_home_blocked"),
            ("before_profile_config_hash_plan", "original_requires_before_profile_hash_plan"),
            ("restart_without_wbp_proof_plan", "original_requires_restart_without_wbp_proof_plan"),
        ):
            if server_plan.get(field) is not True:
                failed.append(check)
    else:
        failed.append("launch_mode_not_in_contract")
    return failed


def _safe_target_candidate_source(server_plan: dict[str, Any]) -> str:
    source = server_plan.get("target_candidate_source")
    if isinstance(source, str) and source in ADMISSION_TARGET_CANDIDATE_SOURCES:
        return source
    return ""


def _declared_write_surfaces(server_plan: dict[str, Any]) -> list[str]:
    raw = server_plan.get("declared_write_surfaces")
    if not isinstance(raw, list):
        return []
    return [str(surface) for surface in raw if isinstance(surface, str) and surface.strip()]


def _admission_common_packet(*, launch_mode: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "launch_mode": launch_mode if launch_mode in NATIVE_LAUNCH_MODES else "",
        "admission_scope": "admission_only_no_runtime_launch",
        "live_launch_performed": False,
        "runtime_mutation_performed": False,
        "ui_mutation_performed": False,
        "prompt_attempted": False,
        "token_burn": 0,
        "product_status_upgraded": False,
        "browser_authority_allowed": False,
    }


def validate_native_launch_packet(packet: dict[str, Any]) -> dict[str, Any]:
    mode = packet.get("launch_mode") if isinstance(packet, dict) else None
    if mode not in NATIVE_LAUNCH_MODES:
        return _validation_packet(
            status="rejected",
            machine_error_code="NATIVE_LAUNCH_MODE_UNKNOWN",
            accepted=False,
            launch_mode=mode,
            forbidden_fields=[],
            missing_fields=[],
            failed_checks=["launch_mode_not_in_contract"],
        )

    required = set(COMMON_PACKET_REQUIRED_FIELDS)
    if mode == "CODEX_CUSTOM_NATIVE_APP":
        required.update(CUSTOM_PACKET_REQUIRED_FIELDS)
    if mode == "ORIGINAL_CODEX_VIA_WBP":
        required.update(ORIGINAL_PACKET_REQUIRED_FIELDS)
    missing = sorted(field for field in required if field not in packet)
    failed_checks = _native_packet_failed_checks(packet)
    if missing or failed_checks:
        return _validation_packet(
            status="rejected",
            machine_error_code="NATIVE_LAUNCH_PACKET_CONTRACT_UNSATISFIED",
            accepted=False,
            launch_mode=mode,
            forbidden_fields=[],
            missing_fields=missing,
            failed_checks=failed_checks,
        )
    return _validation_packet(
        status="ok",
        machine_error_code="OK",
        accepted=True,
        launch_mode=mode,
        forbidden_fields=[],
        missing_fields=[],
        failed_checks=[],
    )


def _native_packet_failed_checks(packet: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    mode = packet.get("launch_mode")
    if packet.get("process_started") is not True:
        failed.append("process_started_required_but_not_sufficient")
    if packet.get("window_observed") is not True:
        failed.append("window_observed_required")
    if packet.get("native_window_usable") is not True:
        failed.append("native_window_usability_required")
    if packet.get("prompt_surface_observed") is not True:
        failed.append("prompt_surface_required")
    if packet.get("route_trace_bound") is not True:
        failed.append("route_trace_binding_required")
    if packet.get("workbench_ready") is True:
        failed.append("workbench_ready_cannot_satisfy_native_launch")
    if packet.get("current_codex_touched") is not False:
        failed.append("current_codex_must_remain_untouched")
    if mode == "CODEX_CUSTOM_NATIVE_APP":
        if packet.get("isolated_home") is not True:
            failed.append("custom_requires_isolated_home")
        if packet.get("isolated_codex_home") is not True:
            failed.append("custom_requires_isolated_codex_home")
        if packet.get("isolated_profile_dir") is not True:
            failed.append("custom_requires_isolated_profile_dir")
        if packet.get("server_owned_route_configuration") is not True:
            failed.append("custom_requires_server_owned_route_configuration")
    if mode == "ORIGINAL_CODEX_VIA_WBP":
        if packet.get("protected_baseline_only") is True:
            failed.append("protected_baseline_only_is_not_original_via_wbp")
        if packet.get("ordinary_codex_app_identity") is not True:
            failed.append("original_requires_ordinary_codex_identity")
        if packet.get("temporary_wbp_route_config") is not True:
            failed.append("original_requires_temporary_wbp_route_config")
        if packet.get("permanent_user_config_mutated") is not False:
            failed.append("original_forbids_permanent_user_config_mutation")
        if packet.get("custom_home_present") is not False:
            failed.append("original_forbids_custom_home")
        if packet.get("custom_codex_home_present") is not False:
            failed.append("original_forbids_custom_codex_home")
        if packet.get("before_profile_hash") != packet.get("after_cleanup_profile_hash"):
            failed.append("original_requires_profile_hash_restored")
        if packet.get("restart_without_wbp_status") != "ok":
            failed.append("original_requires_restart_without_wbp_ok")
    return failed


def _validation_packet(
    *,
    status: str,
    machine_error_code: str,
    accepted: bool,
    launch_mode: Any,
    forbidden_fields: list[str],
    missing_fields: list[str],
    failed_checks: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "contract_scope": "contract_only_no_runtime_launch",
        "accepted": accepted,
        "launch_mode": launch_mode if isinstance(launch_mode, str) else "",
        "forbidden_fields": forbidden_fields,
        "missing_fields": missing_fields,
        "failed_checks": failed_checks,
        "live_launch_performed": False,
        "runtime_mutation_performed": False,
        "ui_mutation_performed": False,
        "next_action": "none" if accepted else "stop_and_diagnose_contract_input",
    }
