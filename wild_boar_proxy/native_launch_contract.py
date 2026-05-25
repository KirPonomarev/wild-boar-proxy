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
