# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom model registry packets for WBP OpenAI-compatible API proof."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from wild_boar_proxy.model_availability import (
    AVAILABILITY_LEVELS,
    CATALOG_AVAILABILITY_CLAIM_LEVELS,
    CATALOG_AVAILABILITY_EVIDENCE_SCOPES,
)
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
MODEL_CATALOG_FIDELITY_SCHEMA_VERSION = 1
CATALOG_METADATA_SOURCES = {
    "original_codex_label",
    "current_build_catalog_visible",
    "provider_declared",
    "operator_assigned",
    "server_registry",
    "unavailable_unknown",
}
CATALOG_PROOF_LEVELS = {
    "proven",
    "classified",
    "declared",
    "unproven",
    "blocked_by_host_environment",
}
MODEL_SELECTION_STATES = {"selectable", "disabled"}
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


def _provider_label(model_id: str, *, provider: str = "", source_class: str = "") -> str:
    provider_text = str(provider or "").strip()
    source_class_text = str(source_class or "").strip()
    if model_id.startswith("gpt-"):
        return "Codex native"
    if source_class_text == "server_registry":
        if provider_text:
            return f"{provider_text} via WBP"
        return "WBP route"
    if provider_text:
        return provider_text
    return "External route"


def _model_lane(model_id: str) -> str:
    if model_id.startswith("gpt-"):
        return "codex_native"
    return "wbp_api"


def _display_name(model_id: str, label: str | None = None) -> str:
    visible = str(label or model_id).strip() or model_id
    if _model_lane(model_id) == "codex_native":
        return visible
    if visible.lower().startswith(("wbp ", "wbp:", "wild boar ")):
        return visible
    return f"WBP {visible}"


def _source_class(model_id: str) -> str:
    if _model_lane(model_id) == "codex_native":
        return "current_build_catalog_visible"
    return "server_registry"


def _tier_unknown() -> dict[str, str]:
    return {
        "label": "unavailable_unknown",
        "source": "unavailable_unknown",
        "proof_level": "unproven",
    }


def _model_entry(model_id: str) -> dict[str, Any]:
    source = _model_source_hint(model_id)
    lane = _model_lane(model_id)
    source_class = _source_class(model_id)
    return {
        "model_id": model_id,
        "label": model_id,
        "display_name": _display_name(model_id),
        "lane": lane,
        "source": source,
        "source_class": source_class,
        "provider_class": _provider_class(model_id),
        "provider_label": _provider_label(model_id, source_class=source_class),
        "physical_provider": "",
        "physical_provider_proven": False,
        "provider_model_id": "" if lane == "codex_native" else model_id,
        "aliases": [],
        "intelligence_tier": _tier_unknown(),
        "speed_tier": _tier_unknown(),
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
        "selection_enabled": True,
        "selection_state": "selectable",
        "selection_disabled_reason_code": "",
        "selection_disabled_reasons": [],
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
        if not route_id:
            continue
        entry = _model_entry(route_id)
        enabled = route.get("enabled") is True
        secret_ref_present = bool(str(route.get("secret_ref") or "").strip())
        disabled_reasons: list[str] = []
        if not enabled:
            disabled_reasons.append("route_disabled")
        if not secret_ref_present:
            disabled_reasons.append("secret_ref_missing")
        selection_enabled = not disabled_reasons
        provider = str(route.get("provider") or "").strip()
        label = str(route.get("upstream_model") or route.get("display_name") or route_id).strip()
        entry.update(
            {
                "label": label or route_id,
                "display_name": _display_name(route_id, label or route_id),
                "lane": "wbp_api",
                "source": "server_owned_external_route",
                "source_class": "server_registry",
                "provider_class": "external_route",
                "provider_label": _provider_label(
                    route_id,
                    provider=provider,
                    source_class="server_registry",
                ),
                "physical_provider": "",
                "physical_provider_proven": False,
                "provider_model_id": str(route.get("upstream_model") or route_id),
                "model_source_hint": "server_owned_external_route",
                "selection_enabled": selection_enabled,
                "selection_state": "selectable" if selection_enabled else "disabled",
                "selection_disabled_reason_code": (
                    ""
                    if selection_enabled
                    else "_AND_".join(reason.upper() for reason in disabled_reasons)
                ),
                "selection_disabled_reasons": disabled_reasons,
            }
        )
        entries.append(entry)
    return entries


def _catalog_capabilities(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "responses": {
            "status": "shape_declared",
            "proof_level": "classified",
            "live_acceptance_proven_by_catalog": False,
        },
        "chat_completions": {
            "status": "shape_declared",
            "proof_level": "classified",
            "live_acceptance_proven_by_catalog": False,
        },
        "streaming": {
            "status": "classified_elsewhere",
            "proof_level": "classified",
            "live_acceptance_proven_by_catalog": False,
        },
        "tools": {
            "status": "unclassified",
            "proof_level": "unproven",
            "advertised": False,
        },
        "images": {
            "status": "unclassified",
            "proof_level": "unproven",
            "advertised": False,
        },
        "reasoning": {
            "status": "unclassified",
            "proof_level": "unproven",
            "advertised": False,
        },
        "context_window": {
            "status": "unclassified",
            "proof_level": "unproven",
            "value": None,
        },
        "provider_class": entry.get("provider_class", "unknown"),
    }


def _availability_rows_by_model_id(packet: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = packet.get("rows") if isinstance(packet, dict) else []
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("model_id") or ""): row
        for row in rows
        if isinstance(row, dict) and str(row.get("model_id") or "")
    }


def _catalog_model_entry(
    entry: dict[str, Any],
    availability_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_id = str(entry.get("model_id") or "")
    availability_row = availability_row if isinstance(availability_row, dict) else {}
    availability_levels = availability_row.get("availability_levels")
    if not isinstance(availability_levels, list) or not availability_levels:
        availability_levels = ["listed"]
    bounded_limitations = availability_row.get("bounded_limitations")
    if not isinstance(bounded_limitations, list):
        bounded_limitations = []
    return {
        "lane": str(entry.get("lane") or _model_lane(model_id)),
        "model_id": model_id,
        "label": str(entry.get("label") or model_id),
        "display_name": str(entry.get("display_name") or _display_name(model_id, str(entry.get("label") or model_id))),
        "source": str(entry.get("source") or entry.get("model_source_hint") or "unknown"),
        "source_class": str(entry.get("source_class") or _source_class(model_id)),
        "provider_class": str(entry.get("provider_class") or "unknown"),
        "provider_label": str(
            entry.get("provider_label")
            or _provider_label(
                model_id,
                source_class=str(entry.get("source_class") or _source_class(model_id)),
            )
        ),
        "physical_provider": str(entry.get("physical_provider") or ""),
        "physical_provider_proven": entry.get("physical_provider_proven") is True,
        "provider_model_id": str(entry.get("provider_model_id") or ""),
        "aliases": list(entry.get("aliases") or []),
        "intelligence_tier": dict(entry.get("intelligence_tier") or _tier_unknown()),
        "speed_tier": dict(entry.get("speed_tier") or _tier_unknown()),
        "server_issued": entry.get("server_issued") is True,
        "model_id_authority": "server_issued",
        "selection_enabled": entry.get("selection_enabled") is True,
        "selection_state": str(
            entry.get("selection_state")
            or ("selectable" if entry.get("selection_enabled") is True else "disabled")
        ),
        "selection_disabled_reason_code": str(entry.get("selection_disabled_reason_code") or ""),
        "selection_disabled_reasons": [str(item) for item in entry.get("selection_disabled_reasons") or []],
        "availability_claim_level": str(
            availability_row.get("availability_claim_level") or "listed_not_live_proven"
        ),
        "availability_evidence_scope": str(
            availability_row.get("availability_evidence_scope") or "current_operator_catalog_only"
        ),
        "availability_levels": [str(level) for level in availability_levels],
        "live_availability_proven": availability_row.get("live_availability_proven") is True,
        "direct_wbp_non_stream_response_accepted": (
            availability_row.get("direct_wbp_non_stream_response_accepted") is True
        ),
        "request_reaches_wbp_proven": availability_row.get("request_reaches_wbp_proven") is True,
        "upstream_accepts_proven": availability_row.get("upstream_accepts_proven") is True,
        "current_stability_proven": availability_row.get("current_stability_proven") is True,
        "bounded_limitations": [str(item) for item in bounded_limitations],
        "account_health_proven": False,
        "route_proven_by_catalog": False,
        "native_proven_by_catalog": False,
        "direct_egress_proven_by_catalog": False,
        "capabilities": _catalog_capabilities(entry),
        "unsupported_capabilities_advertised": False,
    }


def _catalog_registry_row(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane": model.get("lane"),
        "model_id": model.get("model_id"),
        "label": model.get("label"),
        "display_name": model.get("display_name"),
        "source": model.get("source"),
        "source_class": model.get("source_class"),
        "provider_class": model.get("provider_class"),
        "provider_model_id": model.get("provider_model_id"),
        "aliases": list(model.get("aliases") or []),
        "server_issued": model.get("server_issued") is True,
        "model_id_authority": model.get("model_id_authority"),
        "availability_claim_level": model.get("availability_claim_level"),
        "display_metadata_is_catalog_registry_truth": False,
        "catalog_registry_truth_is_runtime_binding_truth": False,
    }


def _runtime_binding_row(model: dict[str, Any]) -> dict[str, Any]:
    lane = str(model.get("lane") or "")
    provider_model_id = str(model.get("provider_model_id") or "")
    return {
        "lane": lane,
        "model_id": model.get("model_id"),
        "source_class": model.get("source_class"),
        "provider_class": model.get("provider_class"),
        "provider_model_id": provider_model_id,
        "server_issued": model.get("server_issued") is True,
        "route_binding_statically_observable": lane == "wbp_api",
        "provider_binding_statically_observable": lane == "wbp_api" and bool(provider_model_id),
        "display_metadata_becomes_runtime_binding_truth": False,
        "catalog_registry_truth_becomes_runtime_binding_truth": False,
        "route_selected_proven": False,
        "upstream_accepts_proven": False,
        "response_accepted_by_codex_proven": False,
        "model_availability_proven": False,
    }


def build_wbp_model_catalog_contract_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = build_custom_model_registry_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
    )
    availability_rows = _availability_rows_by_model_id(availability_lattice_packet)
    catalog_models = [
        _catalog_model_entry(
            entry,
            availability_rows.get(str(entry.get("model_id") or "")),
        )
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
        "catalog_source": "server_owned_operator_status_plus_external_route_registry",
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
        "selectable_model_count": sum(1 for entry in catalog_models if entry["selection_enabled"] is True),
        "disabled_model_count": sum(1 for entry in catalog_models if entry["selection_enabled"] is not True),
        "models": catalog_models,
        "availability_lattice_imported": bool(availability_rows),
        "availability_lattice_status": (
            str(availability_lattice_packet.get("status") or "not_supplied")
            if isinstance(availability_lattice_packet, dict)
            else "not_supplied"
        ),
        "availability_lattice_model_count": len(availability_rows),
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
        if not isinstance(entry.get("provider_label"), str) or not str(entry.get("provider_label") or "").strip():
            findings.append(f"models[{index}].provider_label")
        selection_state = entry.get("selection_state")
        if selection_state not in MODEL_SELECTION_STATES:
            findings.append(f"models[{index}].selection_state")
        selection_enabled = entry.get("selection_enabled") is True
        if selection_enabled and selection_state != "selectable":
            findings.append(f"models[{index}].selection_enabled")
        if not selection_enabled and selection_state != "disabled":
            findings.append(f"models[{index}].selection_enabled")
        if selection_enabled:
            if entry.get("selection_disabled_reason_code") not in {"", None}:
                findings.append(f"models[{index}].selection_disabled_reason_code")
            if list(entry.get("selection_disabled_reasons") or []):
                findings.append(f"models[{index}].selection_disabled_reasons")
        else:
            if not str(entry.get("selection_disabled_reason_code") or "").strip():
                findings.append(f"models[{index}].selection_disabled_reason_code")
            if not list(entry.get("selection_disabled_reasons") or []):
                findings.append(f"models[{index}].selection_disabled_reasons")
        if entry.get("availability_claim_level") not in CATALOG_AVAILABILITY_CLAIM_LEVELS:
            findings.append(f"models[{index}].availability_claim_level")
        if entry.get("availability_evidence_scope") not in CATALOG_AVAILABILITY_EVIDENCE_SCOPES:
            findings.append(f"models[{index}].availability_evidence_scope")
        availability_levels = entry.get("availability_levels")
        if not isinstance(availability_levels, list) or not availability_levels:
            findings.append(f"models[{index}].availability_levels")
        elif any(str(level) not in AVAILABILITY_LEVELS for level in availability_levels):
            findings.append(f"models[{index}].availability_levels")
        lane = entry.get("lane")
        if lane not in {"codex_native", "wbp_api"}:
            findings.append(f"models[{index}].lane")
        if lane == "codex_native" and entry.get("physical_provider_proven") is not False:
            findings.append(f"models[{index}].physical_provider_proven")
        if lane == "wbp_api":
            display_name = str(entry.get("display_name") or "")
            if not display_name.lower().startswith(("wbp ", "wbp:")):
                findings.append(f"models[{index}].display_name")
        for tier_name in ("intelligence_tier", "speed_tier"):
            tier = entry.get(tier_name)
            if not isinstance(tier, dict):
                findings.append(f"models[{index}].{tier_name}")
                continue
            if tier.get("source") not in CATALOG_METADATA_SOURCES:
                findings.append(f"models[{index}].{tier_name}.source")
            if tier.get("proof_level") not in CATALOG_PROOF_LEVELS:
                findings.append(f"models[{index}].{tier_name}.proof_level")
            if tier.get("source") == "measured":
                findings.append(f"models[{index}].{tier_name}.measured_without_packet")
        for negative_field in (
            "account_health_proven",
            "route_proven_by_catalog",
            "native_proven_by_catalog",
            "direct_egress_proven_by_catalog",
            "unsupported_capabilities_advertised",
        ):
            if entry.get(negative_field) is not False:
                findings.append(f"models[{index}].{negative_field}")
        claim_level = entry.get("availability_claim_level")
        if claim_level == "listed_not_live_proven":
            for field in (
                "live_availability_proven",
                "direct_wbp_non_stream_response_accepted",
                "request_reaches_wbp_proven",
                "upstream_accepts_proven",
                "current_stability_proven",
            ):
                if entry.get(field) is not False:
                    findings.append(f"models[{index}].{field}")
            if entry.get("availability_evidence_scope") != "current_operator_catalog_only":
                findings.append(f"models[{index}].availability_evidence_scope")
        elif claim_level == "direct_wbp_non_stream_response_accepted":
            if entry.get("live_availability_proven") is not True:
                findings.append(f"models[{index}].live_availability_proven")
            if entry.get("direct_wbp_non_stream_response_accepted") is not True:
                findings.append(f"models[{index}].direct_wbp_non_stream_response_accepted")
            if entry.get("availability_evidence_scope") != "current_thread_direct_wbp_non_stream":
                findings.append(f"models[{index}].availability_evidence_scope")
        elif claim_level == "historically_direct_wbp_non_stream_response_accepted":
            if entry.get("live_availability_proven") is not False:
                findings.append(f"models[{index}].live_availability_proven")
            if entry.get("direct_wbp_non_stream_response_accepted") is not True:
                findings.append(f"models[{index}].direct_wbp_non_stream_response_accepted")
            if entry.get("availability_evidence_scope") != "pass2_selected_external_route_closed_truth":
                findings.append(f"models[{index}].availability_evidence_scope")
            if entry.get("current_stability_proven") is not False:
                findings.append(f"models[{index}].current_stability_proven")
        capabilities = entry.get("capabilities")
        if not isinstance(capabilities, dict):
            findings.append(f"models[{index}].capabilities")
            continue
        for capability in ("tools", "images", "reasoning"):
            value = capabilities.get(capability)
            if not isinstance(value, dict) or value.get("advertised") is not False:
                findings.append(f"models[{index}].capabilities.{capability}")
    return findings


def _catalog_fidelity_base(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_wbp_model_catalog_contract_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )


def _lane_models(catalog_packet: dict[str, Any], lane: str) -> list[dict[str, Any]]:
    models = catalog_packet.get("models")
    if not isinstance(models, list):
        return []
    return [model for model in models if isinstance(model, dict) and model.get("lane") == lane]


def build_model_catalog_fidelity_packets(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
    measurement_packet_present: bool = False,
) -> dict[str, dict[str, Any]]:
    catalog = _catalog_fidelity_base(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    findings = validate_wbp_model_catalog_contract(catalog)
    models = [model for model in catalog.get("models", []) if isinstance(model, dict)]
    codex_native_models = _lane_models(catalog, "codex_native")
    wbp_api_models = _lane_models(catalog, "wbp_api")
    non_prefixed_external = [
        {
            "model_id": str(model.get("model_id") or ""),
            "display_name": str(model.get("display_name") or ""),
            "exception_basis": "server_issued_model_id_with_wbp_prefixed_display_name",
        }
        for model in wbp_api_models
        if not str(model.get("model_id") or "").lower().startswith("wbp:")
        and str(model.get("display_name") or "").lower().startswith("wbp ")
    ]
    measured_tiers = [
        f"{model.get('model_id')}.{tier_name}"
        for model in models
        for tier_name in ("intelligence_tier", "speed_tier")
        if isinstance(model.get(tier_name), dict)
        and model[tier_name].get("source") == "measured"
    ]
    display_models = [
        {
            "lane": model.get("lane"),
            "model_id": model.get("model_id"),
            "display_name": model.get("display_name"),
            "intelligence_tier": model.get("intelligence_tier"),
            "speed_tier": model.get("speed_tier"),
            "availability_claim_level": model.get("availability_claim_level"),
        }
        for model in models
    ]
    catalog_registry_models = [_catalog_registry_row(model) for model in models]
    runtime_binding_models = [_runtime_binding_row(model) for model in models]
    runtime_binding_truth = {
        "display_metadata_becomes_runtime_binding_truth": False,
        "catalog_registry_truth_becomes_runtime_binding_truth": False,
        "route_selected_proven": False,
        "upstream_accepts_proven": False,
        "response_accepted_by_codex_proven": False,
        "native_codex_selected_model_proven": False,
        "model_availability_proven": False,
        "authority_owner": "server",
        "later_required_proof_levels": [
            "listed",
            "selectable",
            "request_reaches_wbp",
            "route_selected",
            "upstream_accepts",
            "response_accepted_by_codex",
            "streaming_classified",
            "tool_loop_classified",
        ],
        "rows": runtime_binding_models,
    }
    capability_models = [
        {
            "model_id": model.get("model_id"),
            "lane": model.get("lane"),
            "capabilities": model.get("capabilities"),
            "catalog_registry_counts_as_capability_proof": False,
            "runtime_binding_counts_as_capability_proof": False,
            "runtime_truth_counts_as_capability_proof": False,
        }
        for model in models
    ]
    packets: dict[str, dict[str, Any]] = {
        "model_registry_schema_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "model_registry_schema",
            "schema_version": MODEL_CATALOG_FIDELITY_SCHEMA_VERSION,
            "status": "ok" if not findings else "blocked",
            "registry_schema_validated": not findings,
            "validation_findings": findings,
            "model_count": len(models),
        },
        "codex_native_model_lane_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "codex_native_model_lane",
            "status": "ok" if codex_native_models else "blocked",
            "lane": "codex_native",
            "model_count": len(codex_native_models),
            "models": codex_native_models,
            "physical_provider_identity_assumed": False,
            "provider_class_or_source_class_only": True,
            "model_availability_proven": False,
        },
        "wbp_api_model_lane_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "wbp_api_model_lane",
            "status": "ok",
            "lane": "wbp_api",
            "model_count": len(wbp_api_models),
            "models": wbp_api_models,
            "external_provider_live_compatibility_proven": False,
            "provider_family_adapter_compatibility_proven": False,
        },
        "model_display_metadata_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "model_display_metadata",
            "status": "ok",
            "display_metadata_is_runtime_truth": False,
            "models": display_models,
        },
        "catalog_registry_truth_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "catalog_registry_truth",
            "status": "ok",
            "display_metadata_is_catalog_registry_truth": False,
            "catalog_registry_truth_is_runtime_binding_truth": False,
            "models": catalog_registry_models,
        },
        "runtime_binding_truth_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "runtime_binding_truth",
            "status": "ok",
            **runtime_binding_truth,
        },
        "runtime_truth_boundary_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "runtime_truth_boundary",
            "status": "ok",
            "packet_alias_of": "runtime_binding_truth_packet.json",
            "catalog_metadata_becomes_runtime_truth": False,
            **runtime_binding_truth,
        },
        "capability_claims_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "capability_claims",
            "status": "ok",
            "catalog_registry_truth_is_capability_proof": False,
            "runtime_binding_truth_is_capability_proof": False,
            "runtime_truth_boundary_is_capability_proof": False,
            "models": capability_models,
        },
        "metadata_source_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "metadata_source",
            "status": "ok"
            if measurement_packet_present or not measured_tiers
            else "blocked",
            "measurement_packet_present": measurement_packet_present,
            "measured_source_entries": measured_tiers,
            "measured_source_requires_measurement_packet": True,
            "allowed_sources": sorted(CATALOG_METADATA_SOURCES | {"measured"}),
            "proof_levels": sorted(CATALOG_PROOF_LEVELS),
        },
        "model_lane_separation_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "model_lane_separation",
            "status": "ok" if codex_native_models else "blocked",
            "codex_native_lane_present": bool(codex_native_models),
            "wbp_api_lane_present": True,
            "lanes_mixed": False,
            "external_provider_lane_is_codex_native_lane": False,
        },
        "model_catalog_authority_boundary_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "model_catalog_authority_boundary",
            "status": "ok",
            "browser_can_supply_catalog_path": False,
            "browser_can_supply_provider": False,
            "browser_can_supply_model_authority": False,
            "remote_can_supply_catalog_path": False,
            "remote_can_supply_provider": False,
            "remote_can_supply_model_authority": False,
            "allowed_browser_fields": ["model_id"],
            "forbidden_browser_fields": sorted(CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS),
        },
        "non_impersonation_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "non_impersonation",
            "status": "ok",
            "wbp_api_entries_must_not_impersonate_codex_native": True,
            "non_prefixed_external_model_id_exceptions": non_prefixed_external,
            "exception_requires_wbp_prefixed_display_name": True,
            "native_parity_claimed": False,
        },
    }
    matrix_blocked = [
        name for name, packet in packets.items() if packet.get("status") != "ok"
    ]
    packets["model_catalog_fidelity_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "model_catalog_fidelity_matrix",
        "status": "ok" if not matrix_blocked else "blocked",
        "target_status": "WBP_MODEL_CATALOG_FIDELITY_CLASSIFIED",
        "blocked_packets": matrix_blocked,
        "model_availability_proven": False,
        "route_selected_proven": False,
        "upstream_accepts_proven": False,
        "response_accepted_by_codex_proven": False,
        "native_app_proven": False,
        "external_provider_live_proven": False,
        "direct_egress_absence_proven": False,
        "final_e2e_proven": False,
    }
    packets["model_catalog_fidelity_false_green_audit.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "model_catalog_fidelity_false_green_audit",
        "status": "ok" if not matrix_blocked else "blocked",
        "model_listed_claimed_as_usable": False,
        "gpt_5_5_visibility_claimed_as_availability": False,
        "display_metadata_claimed_as_runtime_truth": False,
        "catalog_registry_truth_claimed_as_runtime_binding_truth": False,
        "runtime_binding_truth_claimed_as_capability_proof": False,
        "runtime_truth_boundary_claimed_as_capability_proof": False,
        "source_measured_without_measurement_packet": bool(measured_tiers)
        and not measurement_packet_present,
        "wbp_api_label_claimed_as_codex_native_parity": False,
        "native_physical_provider_identity_assumed": False,
        "route_selected_claimed": False,
        "upstream_accepts_claimed": False,
        "native_or_egress_or_final_claim_present": False,
    }
    packets["independent_catalog_audit.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_catalog_audit",
        "status": "ok" if not matrix_blocked else "blocked",
        "referenced_packets": sorted(packets),
        "text_only_audit": False,
        "lane_separation_checked": True,
        "catalog_registry_truth_checked": True,
        "runtime_binding_truth_checked": True,
        "authority_boundary_checked": True,
        "false_green_checked": True,
    }
    return packets


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

    available_model_ids = [str(entry["model_id"]) for entry in available_models]
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
        "configured_model_visible": reported_configured_model in available_model_ids,
        "server_issued": True,
        "canonical_internal_model_ids": list(CANONICAL_INTERNAL_MODEL_IDS),
        "canonical_internal_model_ids_visible": [
            model_id for model_id in CANONICAL_INTERNAL_MODEL_IDS if model_id in model_ids
        ],
        "model_count": len(available_models),
        "selectable_model_count": sum(1 for entry in available_models if entry["selection_enabled"] is True),
        "disabled_model_count": sum(1 for entry in available_models if entry["selection_enabled"] is not True),
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
    api_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_custom_model_fields(payload)
    registry = build_custom_model_registry_packet(
        operator_status,
        endpoint=endpoint,
        api_snapshot=api_snapshot,
    )
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
    if selected_entry.get("selection_enabled") is not True:
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": "MODEL_NOT_SELECTABLE",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "dry_run": True,
            "human_message": "Model is visible in the server-issued catalog but not selectable.",
            "selected_model": model_id,
            "model_server_issued": True,
            "selected_model_server_issued": True,
            "selected_model_selectable": False,
            "selection_state": selected_entry.get("selection_state", "disabled"),
            "selection_disabled_reason_code": selected_entry.get("selection_disabled_reason_code", ""),
            "selection_disabled_reasons": list(selected_entry.get("selection_disabled_reasons") or []),
            "codex_config_compatible": False,
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
            "negative_claim_basis": "catalog_visibility_without_selection_readiness",
            "independent_runtime_meter_attached": False,
            "refresh_packet": registry,
            "next_action": "select_enabled_model_from_server_registry",
        }
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
        "selected_model_selectable": True,
        "selection_state": selected_entry.get("selection_state", "selectable"),
        "selection_disabled_reason_code": "",
        "selection_disabled_reasons": [],
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
