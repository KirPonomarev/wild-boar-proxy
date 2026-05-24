# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex launch mode split packets for the WBP web UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PREVIOUS_OPERATOR_PROOF = (
    Path(__file__).resolve().parents[1]
    / "audit_results"
    / "codex_custom_app_operator_surface_main_web_integration_pass_2026-05-23"
    / "process_isolation_proof.json"
)
ORIGINAL_FORBIDDEN_BROWSER_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "path",
    "backend_id",
    "route_id",
    "model_id",
    "provider",
    "endpoint",
    "proxy",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "home",
    "codex_home",
    "runtime_config",
}
CUSTOM_LAUNCH_FORBIDDEN_BROWSER_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "path",
    "backend_id",
    "route_id",
    "model",
    "model_id",
    "openai_base_url",
    "base_url",
    "provider",
    "endpoint",
    "proxy",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "home",
    "codex_home",
    "runtime_config",
}
APP_COPY_FORBIDDEN_BROWSER_FIELDS = {
    "account_id",
    "api_key",
    "apikey",
    "app_path",
    "auth",
    "authorization",
    "backend_id",
    "codex_home",
    "data_dir",
    "endpoint",
    "env",
    "home",
    "model",
    "path",
    "pid",
    "port",
    "profile",
    "profile_root",
    "route_id",
    "secret",
    "token",
}
DEFAULT_CUSTOM_WBP_ENDPOINT = "http://127.0.0.1:8318/v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def forbidden_original_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in ORIGINAL_FORBIDDEN_BROWSER_FIELDS:
                findings.append(key_path)
            else:
                findings.append(key_path)
            findings.extend(forbidden_original_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_original_fields(value, f"{prefix}[{index}]"))
    return findings


def forbidden_custom_launch_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in CUSTOM_LAUNCH_FORBIDDEN_BROWSER_FIELDS:
                findings.append(key_path)
            else:
                findings.append(key_path)
            findings.extend(forbidden_custom_launch_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_custom_launch_fields(value, f"{prefix}[{index}]"))
    return findings


def forbidden_app_copy_launch_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in APP_COPY_FORBIDDEN_BROWSER_FIELDS:
                findings.append(key_path)
            else:
                findings.append(key_path)
            findings.extend(forbidden_app_copy_launch_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_app_copy_launch_fields(value, f"{prefix}[{index}]"))
    return findings


def claim_gate_status_from_operator_status(operator_status: dict[str, Any] | None) -> str:
    claim_gate = (operator_status or {}).get("claim_gate")
    if isinstance(claim_gate, dict):
        status = claim_gate.get("status")
        if isinstance(status, str) and status:
            return status
    return "not_reported"


def build_launch_modes_packet(operator_status: dict[str, Any] | None = None) -> dict[str, Any]:
    claim_gate_status = claim_gate_status_from_operator_status(operator_status)
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "OK",
        "captured_at_utc": utc_now(),
        "claim_gate_status": claim_gate_status,
        "modes": [
            {
                "id": "original_codex",
                "label": "Original Codex",
                "role": "protected_baseline",
                "proxy_allowed": False,
                "proxy_enabled": False,
                "custom_codex_home_allowed": False,
                "custom_home": False,
                "dispatch_available": True,
                "launch_claim_scope": "dry_run_guard_only",
            },
            {
                "id": "codex_custom",
                "label": "Codex Custom",
                "role": "proxy_enabled_workbench",
                "proxy_allowed": True,
                "proxy_enabled": True,
                "custom_codex_home_required": True,
                "current_codex_home_allowed": False,
                "custom_home": True,
                "custom_session_available": False,
                "availability_reason": "next_contour_required",
                "launch_dry_run_available": True,
                "live_prompt_requires_authorization": True,
                "launch_claim_scope": "readonly_readiness_only",
            },
            {
                "id": "safe_app_copy",
                "label": "Safe App Copy",
                "role": "separate_copy_launch_surface",
                "proxy_allowed": False,
                "proxy_enabled": False,
                "custom_home": True,
                "current_home_allowed": False,
                "current_codex_home_allowed": False,
                "launch_dry_run_available": True,
                "live_launch_available": False,
                "launch_claim_scope": "separate_app_copy_dry_run_only",
            },
        ],
    }


def build_original_status_packet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "OK",
        "captured_at_utc": utc_now(),
        "mode_id": "original_codex",
        "host_boundary": "protected_baseline",
        "proxy_injection_allowed": False,
        "proxy_allowed": False,
        "custom_home_allowed": False,
        "custom_codex_home_allowed": False,
        "mutation_allowed": False,
        "browser_payload_allowed_keys": [],
        "launch_claim_scope": "status_only",
    }


def build_original_launch_dry_run_packet(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden = forbidden_original_fields(payload)
    if forbidden:
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "captured_at_utc": utc_now(),
            "mode_id": "original_codex",
            "dry_run": True,
            "dispatch_plan_safe": False,
            "human_message": "Original Codex dry-run accepts no browser-controlled fields.",
            "forbidden_fields": forbidden,
            "proxy_env_injected": False,
            "custom_home_injected": False,
            "model_override_injected": False,
            "route_or_backend_injected": False,
            "launch_claim_scope": "dry_run_guard_only",
            "next_action": "remove_browser_payload_fields",
        }
    return {
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "OK",
        "captured_at_utc": utc_now(),
        "mode_id": "original_codex",
        "dry_run": True,
        "dispatch_plan_safe": True,
        "human_message": "Original Codex dispatch plan is protected and contains no proxy/custom env injection.",
        "proxy_env_injected": False,
        "custom_home_injected": False,
        "model_override_injected": False,
        "route_or_backend_injected": False,
        "browser_payload_allowed_keys": [],
        "launch_claim_scope": "dry_run_guard_only",
        "next_action": "manual_live_dispatch_contour_if_needed",
    }


def _custom_isolation_plan() -> dict[str, Any]:
    return {
        "temp_codex_home_required": True,
        "current_codex_home_allowed": False,
        "isolated_state_required": True,
        "separate_process_required": True,
        "cleanup_required": True,
        "current_codex_mutation_allowed": False,
    }


def build_custom_launch_dry_run_packet(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden = forbidden_custom_launch_fields(payload)
    base: dict[str, Any] = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "dry_run": True,
        "launch_claim_scope": "dry_run_readiness_only",
        "isolation_plan": _custom_isolation_plan(),
        "wbp_endpoint_configured": DEFAULT_CUSTOM_WBP_ENDPOINT,
        "proxy_allowed": True,
        "custom_codex_home_required": True,
        "current_codex_home_allowed": False,
        "current_codex_touch_risk": "blocked_by_contract",
        "real_launch_attempted": False,
        "prompt_attempted": False,
        "token_burn": 0,
        "browser_payload_allowed_keys": [],
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Codex Custom launch dry-run accepts no browser-controlled route, model, auth, path, or home fields.",
            "custom_launch_plan_safe": False,
            "forbidden_fields": forbidden,
            "forbidden_fields_rejected": True,
            "next_action": "remove_browser_payload_fields",
        }
    return {
        **base,
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "Codex Custom launch dry-run is isolated and does not launch, prompt, or touch current Codex.",
        "custom_launch_plan_safe": True,
        "forbidden_fields": [],
        "forbidden_fields_rejected": False,
        "next_action": "live_launch_contour_with_owner_authorization",
    }


def _app_copy_plan_base() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "safe_app_copy",
        "launch_mode": "separate_app_copy",
        "launch_claim_scope": "separate_app_copy_dry_run_only",
        "server_issued_plan": True,
        "browser_payload_allowed": False,
        "browser_payload_allowed_keys": [],
        "browser_forbidden_field_policy_enforced": True,
        "app_path_source": "server_owned_default_app_copy_candidate",
        "app_path_redacted": True,
        "isolated_profile_root_redacted": True,
        "isolated_data_dir_redacted": True,
        "isolated_port_source": "server_allocated",
        "isolated_port_redacted": True,
        "separate_profile_required": True,
        "separate_data_dir_required": True,
        "separate_process_required": True,
        "current_codex_touched": False,
        "current_codex_home_touched": False,
        "uses_current_home": False,
        "uses_current_codex_home": False,
        "proxy_env_injected": False,
        "raw_path_exposed": False,
        "raw_pid_exposed": False,
        "raw_env_exposed": False,
        "pid_not_exposed_to_browser": True,
        "launch_performed": False,
    }


def build_safe_app_copy_launch_dry_run_packet(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden = forbidden_app_copy_launch_fields(payload)
    base = {
        **_app_copy_plan_base(),
        "dry_run": True,
        "live_launch_admitted": False,
        "block_reason_code": "LIVE_LAUNCH_REQUIRES_APP_COPY_OWNER_CONTRACT",
        "final_verdict": "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY",
    }
    if forbidden:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
            "browser_forbidden_fields_rejected": True,
            "browser_forbidden_fields_absent": False,
            "forbidden_fields": forbidden,
            "server_issued_plan": False,
            "final_verdict": "WEB_SAFE_APP_COPY_LAUNCH_BLOCKED",
            "next_action": "remove_browser_payload_fields",
        }
    return {
        **base,
        "status": "ok",
        "machine_error_code": "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY",
        "browser_forbidden_fields_rejected": False,
        "browser_forbidden_fields_absent": True,
        "forbidden_fields": [],
        "human_message": "Safe app copy launch dry-run is server-issued and did not launch or touch current Codex.",
        "next_action": "add_app_copy_owner_contract_before_live_launch",
    }


def build_safe_app_copy_launch_live_packet(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden = forbidden_app_copy_launch_fields(payload)
    base = {
        **_app_copy_plan_base(),
        "dry_run": False,
        "live_launch_admitted": False,
        "block_reason_code": "WEB_SAFE_APP_COPY_LAUNCH_NOT_ADMITTED",
        "final_verdict": "WEB_SAFE_APP_COPY_LAUNCH_LIVE_BLOCKED",
        "dry_run_final_verdict": "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY",
        "cleanup_or_stop_instruction": "no_process_launched",
    }
    if forbidden:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
            "browser_forbidden_fields_rejected": True,
            "browser_forbidden_fields_absent": False,
            "forbidden_fields": forbidden,
            "final_verdict": "WEB_SAFE_APP_COPY_LAUNCH_BLOCKED",
            "next_action": "remove_browser_payload_fields",
        }
    return {
        **base,
        "status": "blocked",
        "machine_error_code": "WEB_SAFE_APP_COPY_LAUNCH_NOT_ADMITTED",
        "browser_forbidden_fields_rejected": True,
        "browser_forbidden_fields_absent": True,
        "forbidden_fields": [],
        "human_message": "Live app copy launch is blocked until a server-owned app copy contract is proven.",
        "next_action": "prove_app_copy_owner_contract",
    }


def load_last_process_isolation_proof(
    proof_path: Path = DEFAULT_PREVIOUS_OPERATOR_PROOF,
) -> dict[str, Any]:
    if not proof_path.exists():
        return {
            "status": "missing",
            "fresh_truth": False,
            "source": "previous_contour_artifact",
            "artifact_present": False,
        }
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "unreadable",
            "fresh_truth": False,
            "source": "previous_contour_artifact",
            "artifact_present": True,
        }
    passed = bool(
        proof.get("protected_surfaces_unchanged")
        and proof.get("tmp_root_removed")
        and proof.get("run_result", {}).get("status") == "ok"
    )
    return {
        "status": "passed" if passed else "failed",
        "fresh_truth": False,
        "source": "previous_contour_artifact",
        "artifact_present": True,
        "protected_surfaces_unchanged": proof.get("protected_surfaces_unchanged"),
        "tmp_root_removed": proof.get("tmp_root_removed"),
        "final_message_present": bool(proof.get("run_result", {}).get("final_message")),
    }


def build_custom_status_packet(
    operator_status: dict[str, Any] | None = None,
    *,
    proof_path: Path = DEFAULT_PREVIOUS_OPERATOR_PROOF,
) -> dict[str, Any]:
    models = (operator_status or {}).get("models")
    model_ids = models.get("model_ids", []) if isinstance(models, dict) else []
    server_issued_models_visible = bool(model_ids)
    claim_gate_status = claim_gate_status_from_operator_status(operator_status)
    claim_gate_blocked = "blocked" in claim_gate_status
    status = "ok" if server_issued_models_visible and not claim_gate_blocked else "degraded"
    machine_error_code = (
        "OK"
        if status == "ok"
        else ("CLAIM_GATE_BLOCKED" if claim_gate_blocked else "CUSTOM_MODELS_NOT_VISIBLE")
    )
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "operator_surface_ready": bool(operator_status),
        "server_issued_models_visible": server_issued_models_visible,
        "last_process_isolation_proof": load_last_process_isolation_proof(proof_path),
        "claim_gate_status": claim_gate_status,
        "isolation_plan": _custom_isolation_plan(),
        "wbp_endpoint_configured": DEFAULT_CUSTOM_WBP_ENDPOINT,
        "current_codex_home_allowed": False,
        "current_codex_touch_risk": "blocked_by_contract",
        "custom_session_available": False,
        "availability_reason": "session_manager_next_contour",
        "launch_claim_scope": "readonly_readiness_only",
        "next_contour": "WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS",
    }
