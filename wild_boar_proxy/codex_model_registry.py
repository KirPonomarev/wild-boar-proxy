# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom model registry packets for WBP OpenAI-compatible API proof."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from wild_boar_proxy.operator_surface import DEFAULT_ENDPOINT, DEFAULT_MODEL


CUSTOM_MODEL_DRY_RUN_ALLOWED_FIELDS = {"model_id"}
CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "path",
    "backend_id",
    "route_id",
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
FORBIDDEN_INFERENCE_SURFACES = (
    "/v1/responses",
    "/v1/chat/completions",
    "provider_direct_calls",
)
ALLOWED_NETWORK_CALLS = ("/v1/models",)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def claim_gate_status_from_operator_status(operator_status: dict[str, Any] | None) -> str:
    claim_gate = (operator_status or {}).get("claim_gate")
    if isinstance(claim_gate, dict):
        status = claim_gate.get("status")
        if isinstance(status, str) and status:
            return status
    return "not_reported"


def forbidden_custom_model_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            key_lower = key_text.lower()
            if key_lower in CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS:
                findings.append(key_path)
            elif prefix or key_text not in CUSTOM_MODEL_DRY_RUN_ALLOWED_FIELDS:
                findings.append(key_path)
            findings.extend(forbidden_custom_model_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_custom_model_fields(value, f"{prefix}[{index}]"))
    return findings


def _models_payload(operator_status: dict[str, Any] | None) -> dict[str, Any]:
    models = (operator_status or {}).get("models")
    return models if isinstance(models, dict) else {}


def _reported_configured_model(operator_status: dict[str, Any] | None) -> str:
    status = (operator_status or {}).get("status")
    if isinstance(status, dict):
        configured = status.get("configured_model")
        if isinstance(configured, str) and configured:
            return configured
    return DEFAULT_MODEL


def _model_source_hint(model_id: str) -> str:
    if model_id.startswith("gpt-"):
        return "cliproxy_gpt_account_or_alias"
    return "cliproxy_external_alias"


def _status_for_models(model_ids: list[str], claim_gate_status: str, models_ok: bool) -> tuple[str, str]:
    if not model_ids or not models_ok:
        return "degraded", "CUSTOM_MODELS_NOT_VISIBLE"
    if "blocked" in claim_gate_status:
        return "degraded", "CLAIM_GATE_BLOCKED"
    return "ok", "OK"


def build_custom_model_registry_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    models = _models_payload(operator_status)
    raw_model_ids = models.get("model_ids", [])
    model_ids = [str(model_id) for model_id in raw_model_ids if isinstance(model_id, str) and model_id]
    model_ids = list(dict.fromkeys(model_ids))[:100]
    claim_gate_status = claim_gate_status_from_operator_status(operator_status)
    status, machine_error_code = _status_for_models(
        model_ids,
        claim_gate_status,
        bool(models.get("ok")) or bool(model_ids),
    )
    reported_configured_model = _reported_configured_model(operator_status)
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "endpoint": endpoint,
        "endpoint_scope": "local_wbp_openai_compat",
        "recommended_default_model": recommended_default_model,
        "reported_configured_model": reported_configured_model,
        "configured_model_visible": reported_configured_model in model_ids,
        "server_issued": True,
        "model_count": len(model_ids),
        "available_models": [
            {
                "model_id": model_id,
                "server_issued": True,
                "codex_config_compatible": True,
                "model_source_hint": _model_source_hint(model_id),
            }
            for model_id in model_ids
        ],
        "claim_gate_status": claim_gate_status,
        "allowed_browser_fields": ["model_id"],
        "forbidden_browser_fields": sorted(CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS),
        "route_or_backend_exposed": False,
        "allowed_network_calls": list(ALLOWED_NETWORK_CALLS),
        "forbidden_network_calls": list(FORBIDDEN_INFERENCE_SURFACES),
        "models_endpoint_called": True,
        "inference_called": False,
        "provider_called": False,
        "token_burn": 0,
        "negative_claim_basis": "dry_run_static_code_path_no_inference_adapter",
        "independent_runtime_meter_attached": False,
        "fresh_truth": True,
        "launch_claim_scope": "model_registry_only",
        "next_contour": "GPT_ACCOUNTS_POOL_TRUTH_AND_SELECTION_PASS",
    }


def build_custom_api_compat_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
) -> dict[str, Any]:
    registry = build_custom_model_registry_packet(operator_status, endpoint=endpoint)
    models_ok = bool(registry["available_models"])
    return {
        "schema_version": 1,
        "status": "degraded" if registry["status"] == "degraded" else "ok",
        "machine_error_code": registry["machine_error_code"],
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "endpoint": endpoint,
        "compat_surfaces": {
            "/v1/models": {
                "called": True,
                "fresh_truth": True,
                "status": "ok" if models_ok else "degraded",
                "model_count": registry["model_count"],
            },
            "/v1/responses": {
                "called": False,
                "fresh_truth": False,
                "status": "not_called_in_this_contour",
            },
            "/v1/chat/completions": {
                "called": False,
                "fresh_truth": False,
                "status": "not_called_in_this_contour",
            },
        },
        "network_call_summary": {
            "allowed_calls_made": list(ALLOWED_NETWORK_CALLS),
            "forbidden_calls_made": [],
            "provider_direct_calls_made": False,
            "inference_called": False,
            "token_burn": 0,
            "negative_claim_basis": "dry_run_static_code_path_no_inference_adapter",
            "independent_runtime_meter_attached": False,
        },
        "route_or_backend_exposed": False,
        "claim_gate_status": registry["claim_gate_status"],
        "fresh_truth": True,
        "launch_claim_scope": "api_compat_models_only",
    }


def build_custom_model_dry_run_packet(
    payload: dict[str, Any],
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
) -> dict[str, Any]:
    forbidden = forbidden_custom_model_fields(payload)
    registry = build_custom_model_registry_packet(operator_status, endpoint=endpoint)
    if forbidden:
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "dry_run": True,
            "human_message": "Codex Custom model dry-run accepts only server-issued model_id.",
            "forbidden_fields": forbidden,
            "model_server_issued": False,
            "codex_config_compatible": False,
            "route_or_backend_exposed": False,
            "inference_called": False,
            "provider_called": False,
            "responses_called": False,
            "chat_completions_called": False,
            "token_burn": 0,
            "negative_claim_basis": "dry_run_rejected_before_inference_adapter",
            "independent_runtime_meter_attached": False,
            "refresh_packet": registry,
            "next_action": "remove_forbidden_browser_fields",
        }
    model_id = payload.get("model_id")
    model_ids = [entry["model_id"] for entry in registry["available_models"]]
    if not isinstance(model_id, str) or model_id not in model_ids:
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "dry_run": True,
            "human_message": "Model id was not present in the current server-issued list.",
            "selected_model": model_id if isinstance(model_id, str) else "",
            "model_server_issued": False,
            "codex_config_compatible": False,
            "route_or_backend_exposed": False,
            "inference_called": False,
            "provider_called": False,
            "responses_called": False,
            "chat_completions_called": False,
            "token_burn": 0,
            "negative_claim_basis": "dry_run_rejected_before_inference_adapter",
            "independent_runtime_meter_attached": False,
            "refresh_packet": registry,
            "next_action": "select_model_from_server_registry",
        }
    selected_entry = next(entry for entry in registry["available_models"] if entry["model_id"] == model_id)
    return {
        "schema_version": 1,
        "status": registry["status"],
        "machine_error_code": registry["machine_error_code"],
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "dry_run": True,
        "human_message": "Codex Custom model selection is config-compatible; no inference was called.",
        "selected_model": model_id,
        "model_server_issued": True,
        "codex_config_compatible": bool(selected_entry["codex_config_compatible"]),
        "model_source_hint": selected_entry["model_source_hint"],
        "claim_gate_status": registry["claim_gate_status"],
        "route_or_backend_exposed": False,
        "inference_called": False,
        "provider_called": False,
        "responses_called": False,
        "chat_completions_called": False,
        "token_burn": 0,
        "negative_claim_basis": "dry_run_static_code_path_no_inference_adapter",
        "independent_runtime_meter_attached": False,
        "refresh_packet": registry,
        "next_action": "custom_session_manager_contour",
    }
