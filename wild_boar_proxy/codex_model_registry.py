# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom model registry packets for WBP OpenAI-compatible API proof."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from wild_boar_proxy.operator_surface import DEFAULT_ENDPOINT, DEFAULT_MODEL


CUSTOM_MODEL_DRY_RUN_ALLOWED_FIELDS = {"model_id"}
CANONICAL_INTERNAL_MODEL_IDS = (
    "gpt-5.3-codex",
    "gpt-5.3-codex-spark",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.5",
)
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
    "base_url",
    "openai_base_url",
    "model_provider",
    "wire_api",
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
CONFIGURED_MODEL_PROVIDER = "cliproxy"
CONFIGURED_WIRE_API = "responses"
MODEL_CATALOG_CONTRACT_SCHEMA_VERSION = 1
CATALOG_ALLOWED_CLAIMS = (
    "catalog_generated_from_server_owned_sources",
    "catalog_schema_validated",
    "model_ids_are_server_issued",
    "default_model_is_explicit",
    "capability_claims_are_classified",
    "unsupported_capabilities_not_advertised",
    "browser_authority_blocked",
    "current_codex_auth_json_not_required",
)
CATALOG_FORBIDDEN_CLAIMS = (
    "live_model_availability_proven",
    "gpt_5_5_works",
    "all_models_work",
    "account_health_proven",
    "native_codex_proven",
    "cli_runner_proven",
    "direct_egress_absent",
    "final_e2e_proven",
)


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


def _provider_class(model_id: str) -> str:
    if model_id.startswith("gpt-"):
        return "gpt_account_or_alias"
    return "external_alias"


def _model_entry(model_id: str) -> dict[str, Any]:
    source = _model_source_hint(model_id)
    return {
        "model_id": model_id,
        "label": model_id,
        "source": source,
        "provider_class": _provider_class(model_id),
        "codex_compatible": True,
        "codex_config_compatible": True,
        "responses_supported": True,
        "responses_supported_claim_scope": "shape_declared_not_live_proven",
        "responses_live_acceptance_proven": False,
        "chat_completions_supported": True,
        "chat_completions_supported_claim_scope": "shape_declared_not_live_proven",
        "chat_completions_live_acceptance_proven": False,
        "server_issued": True,
        "model_source_hint": source,
        "availability_claim_level": "listed_not_live_proven",
        "live_availability_proven": False,
        "account_health_proven": False,
        "native_proven_by_registry": False,
        "direct_egress_proven_by_registry": False,
        "unsupported_capabilities_advertised": False,
    }


def _status_for_models(model_ids: list[str], claim_gate_status: str, models_ok: bool) -> tuple[str, str]:
    if not model_ids or not models_ok:
        return "degraded", "CUSTOM_MODELS_NOT_VISIBLE"
    if "blocked" in claim_gate_status:
        return "degraded", "CLAIM_GATE_BLOCKED"
    return "ok", "OK"


def _external_route_model_entries(api_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(api_snapshot, dict):
        return []
    routes = api_snapshot.get("routes")
    if not isinstance(routes, list):
        return []
    entries: list[dict[str, Any]] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        if not route_id or route.get("enabled") is not True:
            continue
        if not str(route.get("secret_ref") or "").strip():
            continue
        entry = _model_entry(route_id)
        label = str(route.get("upstream_model") or route.get("display_name") or route_id).strip()
        entry.update(
            {
                "label": label or route_id,
                "source": "server_owned_external_route",
                "provider_class": "external_route",
                "model_source_hint": "server_owned_external_route",
            }
        )
        entries.append(entry)
    return entries


def _catalog_capabilities(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "responses": {
            "status": "shape_declared",
            "live_acceptance_proven_by_catalog": False,
        },
        "chat_completions": {
            "status": "shape_declared",
            "live_acceptance_proven_by_catalog": False,
        },
        "streaming": {
            "status": "classified_elsewhere",
            "live_acceptance_proven_by_catalog": False,
        },
        "tools": {
            "status": "unclassified",
            "advertised": False,
        },
        "images": {
            "status": "unclassified",
            "advertised": False,
        },
        "reasoning": {
            "status": "unclassified",
            "advertised": False,
        },
        "context_window": {
            "status": "unclassified",
            "value": None,
        },
        "provider_class": entry.get("provider_class", "unknown"),
    }


def _catalog_model_entry(entry: dict[str, Any]) -> dict[str, Any]:
    model_id = str(entry.get("model_id") or "")
    return {
        "model_id": model_id,
        "label": str(entry.get("label") or model_id),
        "source": str(entry.get("source") or entry.get("model_source_hint") or "unknown"),
        "provider_class": str(entry.get("provider_class") or "unknown"),
        "server_issued": entry.get("server_issued") is True,
        "model_id_authority": "server_issued",
        "availability_claim_level": "listed_not_live_proven",
        "live_availability_proven": False,
        "account_health_proven": False,
        "route_proven_by_catalog": False,
        "native_proven_by_catalog": False,
        "direct_egress_proven_by_catalog": False,
        "capabilities": _catalog_capabilities(entry),
        "unsupported_capabilities_advertised": False,
    }


def build_wbp_model_catalog_contract_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = build_custom_model_registry_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
    )
    catalog_models = [
        _catalog_model_entry(entry)
        for entry in sorted(
            registry["available_models"],
            key=lambda item: str(item.get("model_id") or ""),
        )
    ]
    default_model = str(recommended_default_model or registry["recommended_default_model"])
    return {
        "schema_version": MODEL_CATALOG_CONTRACT_SCHEMA_VERSION,
        "status": registry["status"],
        "machine_error_code": registry["machine_error_code"],
        "captured_at_utc": utc_now(),
        "contract_scope": "provider_catalog_only",
        "model_provider": CONFIGURED_MODEL_PROVIDER,
        "base_url": endpoint,
        "wire_api": CONFIGURED_WIRE_API,
        "catalog_source": "server_owned_operator_status_plus_enabled_external_routes",
        "catalog_generated_by": "wbp_server",
        "catalog_deterministic_order": "model_id_ascending",
        "server_owned_source": True,
        "browser_authority": {
            "catalog_path": False,
            "model_provider": False,
            "base_url": False,
            "wire_api": False,
            "route_id": False,
            "backend_id": False,
            "auth_path": False,
            "token": False,
        },
        "default_model": default_model,
        "default_model_explicit": True,
        "default_model_in_catalog": any(entry["model_id"] == default_model for entry in catalog_models),
        "model_count": len(catalog_models),
        "models": catalog_models,
        "allowed_browser_fields": ["model_id"],
        "forbidden_browser_fields": sorted(CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS),
        "live_api_checked": False,
        "network_calls_made": False,
        "inference_called": False,
        "provider_called": False,
        "account_health_proven": False,
        "native_codex_proven": False,
        "cli_runner_proven": False,
        "direct_egress_absence_proven": False,
        "final_e2e_proven": False,
        "current_codex_auth_json_dependency": False,
        "keychain_dependency": False,
        "original_codex_mutation": False,
        "raw_upstream_secret_exposed": False,
        "allowed_claims": list(CATALOG_ALLOWED_CLAIMS),
        "forbidden_claims": list(CATALOG_FORBIDDEN_CLAIMS),
        "claim_limits": {
            "model_listed_means_usable": False,
            "catalog_proves_route": False,
            "catalog_proves_native": False,
            "catalog_proves_egress": False,
            "catalog_proves_account_health": False,
        },
        "negative_claim_basis": "catalog_contract_only_no_live_api_or_consumer_acceptance_call",
    }


def validate_wbp_model_catalog_contract(packet: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if packet.get("schema_version") != MODEL_CATALOG_CONTRACT_SCHEMA_VERSION:
        findings.append("schema_version")
    if packet.get("contract_scope") != "provider_catalog_only":
        findings.append("contract_scope")
    if packet.get("server_owned_source") is not True:
        findings.append("server_owned_source")
    if packet.get("default_model_explicit") is not True or not packet.get("default_model"):
        findings.append("default_model")
    browser_authority = packet.get("browser_authority")
    if not isinstance(browser_authority, dict) or any(value is not False for value in browser_authority.values()):
        findings.append("browser_authority")
    for negative_field in (
        "live_api_checked",
        "network_calls_made",
        "inference_called",
        "provider_called",
        "account_health_proven",
        "native_codex_proven",
        "cli_runner_proven",
        "direct_egress_absence_proven",
        "final_e2e_proven",
        "current_codex_auth_json_dependency",
        "keychain_dependency",
        "original_codex_mutation",
        "raw_upstream_secret_exposed",
    ):
        if packet.get(negative_field) is not False:
            findings.append(negative_field)
    models = packet.get("models")
    if not isinstance(models, list):
        findings.append("models")
        return findings
    model_ids = [entry.get("model_id") for entry in models if isinstance(entry, dict)]
    if model_ids != sorted(model_ids):
        findings.append("catalog_deterministic_order")
    for index, entry in enumerate(models):
        if not isinstance(entry, dict):
            findings.append(f"models[{index}]")
            continue
        if not isinstance(entry.get("model_id"), str) or not entry["model_id"]:
            findings.append(f"models[{index}].model_id")
        if entry.get("server_issued") is not True:
            findings.append(f"models[{index}].server_issued")
        if entry.get("availability_claim_level") != "listed_not_live_proven":
            findings.append(f"models[{index}].availability_claim_level")
        for negative_field in (
            "live_availability_proven",
            "account_health_proven",
            "route_proven_by_catalog",
            "native_proven_by_catalog",
            "direct_egress_proven_by_catalog",
            "unsupported_capabilities_advertised",
        ):
            if entry.get(negative_field) is not False:
                findings.append(f"models[{index}].{negative_field}")
        capabilities = entry.get("capabilities")
        if not isinstance(capabilities, dict):
            findings.append(f"models[{index}].capabilities")
            continue
        for capability in ("tools", "images", "reasoning"):
            value = capabilities.get(capability)
            if not isinstance(value, dict) or value.get("advertised") is not False:
                findings.append(f"models[{index}].capabilities.{capability}")
    return findings


def build_custom_model_registry_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
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
    available_models = [_model_entry(model_id) for model_id in model_ids]
    seen_model_ids = {str(entry["model_id"]) for entry in available_models}
    for route_entry in _external_route_model_entries(api_snapshot):
        route_model_id = str(route_entry["model_id"])
        if route_model_id in seen_model_ids:
            continue
        available_models.append(route_entry)
        seen_model_ids.add(route_model_id)

    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "endpoint": endpoint,
        "endpoint_scope": "local_wbp_openai_compat",
        "model_provider": CONFIGURED_MODEL_PROVIDER,
        "base_url": endpoint,
        "wire_api": CONFIGURED_WIRE_API,
        "configured_wire_api": CONFIGURED_WIRE_API,
        "recommended_default_model": recommended_default_model,
        "recommended_model": recommended_default_model,
        "reported_configured_model": reported_configured_model,
        "configured_model": reported_configured_model,
        "configured_model_visible": reported_configured_model in model_ids,
        "server_issued": True,
        "canonical_internal_model_ids": list(CANONICAL_INTERNAL_MODEL_IDS),
        "canonical_internal_model_ids_visible": [
            model_id for model_id in CANONICAL_INTERNAL_MODEL_IDS if model_id in model_ids
        ],
        "model_count": len(available_models),
        "available_models": available_models,
        "claim_gate_status": claim_gate_status,
        "allowed_browser_fields": ["model_id"],
        "forbidden_browser_fields": sorted(CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS),
        "route_or_backend_exposed": False,
        "openai_compatible_shape_declared": True,
        "models_endpoint_shape_declared": True,
        "responses_shape_declared": True,
        "chat_completions_shape_declared": True,
        "codex_config_compatible": True,
        "live_api_checked": False,
        "network_calls_made": False,
        "allowed_network_calls": [],
        "forbidden_network_calls": list(FORBIDDEN_INFERENCE_SURFACES),
        "models_endpoint_called": False,
        "inference_called": False,
        "provider_called": False,
        "token_burn": 0,
        "negative_claim_basis": "shape_declaration_no_live_api_or_inference_call",
        "independent_runtime_meter_attached": False,
        "fresh_truth": True,
        "launch_claim_scope": "model_registry_only",
        "claim_limits": {
            "model_listed_means_usable": False,
            "registry_proves_live_availability": False,
            "registry_proves_native": False,
            "registry_proves_egress": False,
            "registry_proves_account_health": False,
        },
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
        "model_provider": CONFIGURED_MODEL_PROVIDER,
        "base_url": endpoint,
        "wire_api": CONFIGURED_WIRE_API,
        "configured_wire_api": CONFIGURED_WIRE_API,
        "openai_compatible_shape_declared": True,
        "models_endpoint_shape_declared": True,
        "responses_shape_declared": True,
        "chat_completions_shape_declared": True,
        "codex_config_compatible": True,
        "live_api_checked": False,
        "token_burn": 0,
        "compat_surfaces": {
            "/v1/models": {
                "called": False,
                "fresh_truth": False,
                "status": "shape_declared" if models_ok else "shape_declared_models_not_visible",
                "model_count": registry["model_count"],
                "shape_declared": True,
            },
            "/v1/responses": {
                "called": False,
                "fresh_truth": False,
                "status": "shape_declared_not_called",
                "shape_declared": True,
            },
            "/v1/chat/completions": {
                "called": False,
                "fresh_truth": False,
                "status": "shape_declared_not_called",
                "shape_declared": True,
            },
        },
        "network_call_summary": {
            "network_calls_made": False,
            "allowed_calls_made": [],
            "forbidden_calls_made": [],
            "provider_direct_calls_made": False,
            "inference_called": False,
            "token_burn": 0,
            "negative_claim_basis": "shape_declaration_no_live_api_or_inference_call",
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
            "selected_model_server_issued": False,
            "codex_config_compatible": False,
            "model_provider": CONFIGURED_MODEL_PROVIDER,
            "base_url": endpoint,
            "wire_api": CONFIGURED_WIRE_API,
            "route_or_backend_exposed": False,
            "inference_called": False,
            "provider_called": False,
            "responses_called": False,
            "chat_completions_called": False,
            "network_call_summary": {
                "network_calls_made": False,
                "allowed_calls_made": [],
                "forbidden_calls_made": [],
                "provider_direct_calls_made": False,
            },
            "token_burn": 0,
            "negative_claim_basis": "dry_run_rejected_before_network_or_inference_adapter",
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
            "selected_model_server_issued": False,
            "codex_config_compatible": False,
            "model_provider": CONFIGURED_MODEL_PROVIDER,
            "base_url": endpoint,
            "wire_api": CONFIGURED_WIRE_API,
            "route_or_backend_exposed": False,
            "inference_called": False,
            "provider_called": False,
            "responses_called": False,
            "chat_completions_called": False,
            "network_call_summary": {
                "network_calls_made": False,
                "allowed_calls_made": [],
                "forbidden_calls_made": [],
                "provider_direct_calls_made": False,
            },
            "token_burn": 0,
            "negative_claim_basis": "dry_run_rejected_before_network_or_inference_adapter",
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
        "selected_model_server_issued": True,
        "codex_config_compatible": bool(selected_entry["codex_config_compatible"]),
        "model_provider": CONFIGURED_MODEL_PROVIDER,
        "base_url": endpoint,
        "wire_api": CONFIGURED_WIRE_API,
        "model_source_hint": selected_entry["model_source_hint"],
        "claim_gate_status": registry["claim_gate_status"],
        "route_or_backend_exposed": False,
        "inference_called": False,
        "provider_called": False,
        "responses_called": False,
        "chat_completions_called": False,
        "network_call_summary": {
            "network_calls_made": False,
            "allowed_calls_made": [],
            "forbidden_calls_made": [],
            "provider_direct_calls_made": False,
        },
        "token_burn": 0,
        "negative_claim_basis": "shape_declaration_no_live_api_or_inference_call",
        "independent_runtime_meter_attached": False,
        "refresh_packet": registry,
        "next_action": "custom_session_manager_contour",
    }
