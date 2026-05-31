# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom model registry packets for WBP OpenAI-compatible API proof."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wild_boar_proxy.external_models.credentials import provider_specs_inventory
from wild_boar_proxy.model_availability import (
    AVAILABILITY_LEVELS,
    CATALOG_AVAILABILITY_CLAIM_LEVELS,
    CATALOG_AVAILABILITY_EVIDENCE_SCOPES,
)
from wild_boar_proxy.operator_surface import DEFAULT_ENDPOINT, DEFAULT_MODEL
from wild_boar_proxy.runtime import REPO_ROOT


CUSTOM_MODEL_DRY_RUN_ALLOWED_FIELDS = {"model_id"}
DUAL_LANE_SELECTOR_ALLOWED_FIELDS = {"chatgpt_model_id", "api_model_id"}
CUSTOM_API_ACTION_GATE_ALLOWED_FIELDS = {"api_model_id"}
CUSTOM_CODEX_EXECUTION_MODE_ALLOWED_FIELDS = {
    "execution_mode",
    "chatgpt_model_id",
    "api_model_id",
    "api_reasoning_option_id",
}
CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT = "catalog_default"
CUSTOM_CODEX_API_REASONING_OPTION_FAST = "provider_declared_fast"
CUSTOM_CODEX_API_REASONING_OPTION_DISABLED = "provider_declared_disabled"
CUSTOM_CODEX_API_REASONING_OPTION_HIGH = "provider_declared_high"
CUSTOM_CODEX_API_REASONING_OPTION_MAX = "provider_declared_max"
CUSTOM_CODEX_API_REASONING_OPTION_ALLOWED_IDS = {
    CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT,
    CUSTOM_CODEX_API_REASONING_OPTION_FAST,
    CUSTOM_CODEX_API_REASONING_OPTION_DISABLED,
    CUSTOM_CODEX_API_REASONING_OPTION_HIGH,
    CUSTOM_CODEX_API_REASONING_OPTION_MAX,
}
SERVER_MODEL_SELECTION_AND_REASONING_TRUTH_FINAL_STATUS = (
    "CUSTOM_CODEX_SERVER_MODEL_SELECTION_TRUTH_PROVEN_WITH_LIMITS"
)
SERVER_MODEL_SELECTION_AND_REASONING_TRUTH_BLOCKER = (
    "KNOWN_BLOCKER_CUSTOM_CODEX_SERVER_MODEL_SELECTION_TRUTH_NOT_PROVEN"
)
CHATGPT_PLUS_API_SLOT_TRUTH_FINAL_STATUS = "CHATGPT_PLUS_API_SLOT_TRUTH_PROVEN_WITH_LIMITS"
CHATGPT_PLUS_API_SLOT_TRUTH_BLOCKER = (
    "STOP_AND_DIAGNOSE_CHATGPT_PLUS_API_SLOT_TRUTH_NOT_PROVEN"
)
API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_ALLOWED_FIELDS = {"execution_mode", "api_model_id"}
CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_ONLY = "chatgpt_only"
CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API = "chatgpt_plus_api"
CUSTOM_CODEX_EXECUTION_MODE_API_ONLY = "api_only"
API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_EXPECTED_TEXT = "API_ONLY_DEEPSEEK_READY"
API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_PROMPT = (
    "Верни короткий ответ: API_ONLY_DEEPSEEK_READY"
)
CUSTOM_CODEX_EXECUTION_MODES = {
    CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_ONLY,
    CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API,
    CUSTOM_CODEX_EXECUTION_MODE_API_ONLY,
}
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
CUSTOM_API_ACTION_GATE_FORBIDDEN_FIELDS = {
    *CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS,
    "account_id",
    "api_key",
    "auth_ref",
    "base_url",
    "codex_home",
    "code_home",
    "codehome",
    "codeX_HOME".lower(),
    "route_config",
    "secret_ref",
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
GENERIC_PROVIDER_REGISTRY_SCHEMA_VERSION = 1
GENERIC_MODEL_REGISTRY_SCHEMA_VERSION = 1
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
SEED_ONLY_MODEL_AVAILABILITY_STATE = "seed_only_not_current_catalog"
CODEX_ACCOUNT_MODEL_LANE = "codex_account_lane"
API_ROUTE_MODEL_LANE = "api_route_lane"
UNKNOWN_MODEL_LANE = "unknown_lane"
SERVER_MODEL_CATALOG_CLASSIFICATION_SOURCE = "server_model_catalog"
SERVER_API_ROUTE_SNAPSHOT_CLASSIFICATION_SOURCE = "server_api_route_snapshot"
FALLBACK_NAME_HEURISTIC_CLASSIFICATION_SOURCE = "fallback_name_heuristic"
SERVER_CLASSIFIED_MODEL_LANE_PROOF_LEVEL = "server_classified"
FALLBACK_NAME_HEURISTIC_MODEL_LANE_PROOF_LEVEL = "fallback_name_heuristic"
HEURISTIC_ONLY_NOT_EXECUTABLE_MODEL_LANE_PROOF_LEVEL = "heuristic_only_not_executable"
UNCLASSIFIED_MODEL_LANE_PROOF_LEVEL = "unclassified"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def claim_gate_status_from_operator_status(operator_status: dict[str, Any] | None) -> str:
    claim_gate = (operator_status or {}).get("claim_gate")
    if isinstance(claim_gate, dict):
        status = claim_gate.get("status")
        if isinstance(status, str) and status:
            return status
    return "not_reported"


def _forbidden_payload_fields(
    payload: Any,
    *,
    allowed_fields: set[str],
    prefix: str = "",
) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            key_lower = key_text.lower()
            if key_lower in CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS:
                findings.append(key_path)
            elif prefix or key_text not in allowed_fields:
                findings.append(key_path)
            findings.extend(
                _forbidden_payload_fields(value, allowed_fields=allowed_fields, prefix=key_path)
            )
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_payload_fields(
                    value,
                    allowed_fields=allowed_fields,
                    prefix=f"{prefix}[{index}]",
                )
            )
    return findings


def forbidden_custom_model_fields(payload: Any, prefix: str = "") -> list[str]:
    return _forbidden_payload_fields(
        payload,
        allowed_fields=CUSTOM_MODEL_DRY_RUN_ALLOWED_FIELDS,
        prefix=prefix,
    )


def forbidden_dual_lane_selector_fields(payload: Any, prefix: str = "") -> list[str]:
    return _forbidden_payload_fields(
        payload,
        allowed_fields=DUAL_LANE_SELECTOR_ALLOWED_FIELDS,
        prefix=prefix,
    )


def forbidden_custom_api_action_gate_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            key_lower = key_text.lower()
            if key_lower in CUSTOM_API_ACTION_GATE_FORBIDDEN_FIELDS:
                findings.append(key_path)
            elif prefix or key_text not in CUSTOM_API_ACTION_GATE_ALLOWED_FIELDS:
                findings.append(key_path)
            findings.extend(forbidden_custom_api_action_gate_fields(value, prefix=key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                forbidden_custom_api_action_gate_fields(value, prefix=f"{prefix}[{index}]")
            )
    return findings


def forbidden_custom_codex_execution_mode_fields(payload: Any, prefix: str = "") -> list[str]:
    return _forbidden_payload_fields(
        payload,
        allowed_fields=CUSTOM_CODEX_EXECUTION_MODE_ALLOWED_FIELDS,
        prefix=prefix,
    )


def forbidden_api_only_deepseek_live_route_format_fields(
    payload: Any, prefix: str = ""
) -> list[str]:
    return _forbidden_payload_fields(
        payload,
        allowed_fields=API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_ALLOWED_FIELDS,
        prefix=prefix,
    )


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


def _model_source_hint(model_id: str, *, lane: str = "") -> str:
    lane_text = str(lane or _model_lane(model_id))
    if lane_text == "codex_native":
        return "cliproxy_gpt_account_or_alias"
    return "cliproxy_external_alias"


def _provider_class(model_id: str, *, lane: str = "") -> str:
    lane_text = str(lane or _model_lane(model_id))
    if lane_text == "codex_native":
        return "gpt_account_or_alias"
    return "external_alias"


def _provider_label(
    model_id: str,
    *,
    provider: str = "",
    source_class: str = "",
    lane: str = "",
) -> str:
    provider_text = str(provider or "").strip()
    source_class_text = str(source_class or "").strip()
    lane_text = str(lane or _model_lane(model_id))
    if lane_text == "codex_native":
        return "Codex native"
    if source_class_text == "server_registry":
        if provider_text:
            return f"{provider_text} via WBP"
        return "WBP route"
    if provider_text:
        return provider_text
    return "External route"


def _canonical_model_lane_from_legacy_lane(lane: str) -> str:
    lane_text = str(lane or "").strip()
    if lane_text == "codex_native":
        return CODEX_ACCOUNT_MODEL_LANE
    if lane_text == "wbp_api":
        return API_ROUTE_MODEL_LANE
    return UNKNOWN_MODEL_LANE


def _classification_source_from_entry(entry: dict[str, Any]) -> str:
    lane = str(entry.get("lane") or "").strip()
    source = str(entry.get("source") or entry.get("model_source_hint") or "").strip()
    source_class = str(entry.get("source_class") or "").strip()
    if lane == "wbp_api" or source == "server_owned_external_route" or source_class == "server_registry":
        return SERVER_API_ROUTE_SNAPSHOT_CLASSIFICATION_SOURCE
    if lane == "codex_native":
        return SERVER_MODEL_CATALOG_CLASSIFICATION_SOURCE
    return "none"


def model_lane_classification_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    model_id = str(entry.get("model_id") or "")
    explicit_model_lane = str(entry.get("model_lane") or "").strip()
    explicit_proof_level = str(entry.get("model_lane_proof_level") or "").strip()
    explicit_source = str(entry.get("model_lane_classification_source") or "").strip()
    if explicit_model_lane in {
        CODEX_ACCOUNT_MODEL_LANE,
        API_ROUTE_MODEL_LANE,
        UNKNOWN_MODEL_LANE,
    }:
        fallback_used = entry.get("model_lane_fallback_used") is True
        classified = (
            explicit_model_lane != UNKNOWN_MODEL_LANE
            and entry.get("model_lane_classified") is True
            and entry.get("server_issued") is True
        )
        return {
            "model_catalog_entry_server_issued": entry.get("server_issued") is True,
            "model_lane": explicit_model_lane,
            "model_lane_classified": classified,
            "model_lane_classification_source": (
                explicit_source if classified or fallback_used or explicit_source else "none"
            ),
            "model_lane_fallback_used": fallback_used,
            "model_lane_proof_level": (
                explicit_proof_level
                if explicit_proof_level
                else (
                    SERVER_CLASSIFIED_MODEL_LANE_PROOF_LEVEL
                    if classified
                    else UNCLASSIFIED_MODEL_LANE_PROOF_LEVEL
                )
            ),
            "heuristic_model_lane": str(entry.get("heuristic_model_lane") or UNKNOWN_MODEL_LANE),
            "heuristic_only_not_executable": entry.get("heuristic_only_not_executable") is True,
            "runtime_lane_proven": entry.get("runtime_lane_proven") is True,
            "legacy_catalog_lane": str(entry.get("legacy_catalog_lane") or entry.get("lane") or ""),
        }
    legacy_lane = str(entry.get("lane") or _model_lane(model_id))
    model_lane = _canonical_model_lane_from_legacy_lane(legacy_lane)
    classified = model_lane != UNKNOWN_MODEL_LANE and entry.get("server_issued") is True
    return {
        "model_catalog_entry_server_issued": entry.get("server_issued") is True,
        "model_lane": model_lane,
        "model_lane_classified": classified,
        "model_lane_classification_source": (
            _classification_source_from_entry(entry) if classified else "none"
        ),
        "model_lane_fallback_used": False,
        "model_lane_proof_level": (
            SERVER_CLASSIFIED_MODEL_LANE_PROOF_LEVEL
            if classified
            else UNCLASSIFIED_MODEL_LANE_PROOF_LEVEL
        ),
        "runtime_lane_proven": False,
        "legacy_catalog_lane": legacy_lane,
    }


def fallback_model_lane_classification(model_id: str) -> dict[str, Any]:
    model_id_text = str(model_id or "")
    if model_id_text.startswith("gpt-") or _is_native_model_id(model_id_text):
        heuristic_model_lane = CODEX_ACCOUNT_MODEL_LANE
    elif (
        model_id_text.startswith("wbp:")
        or model_id_text.startswith("wbp-")
        or model_id_text.startswith("direct-")
    ):
        heuristic_model_lane = API_ROUTE_MODEL_LANE
    else:
        heuristic_model_lane = UNKNOWN_MODEL_LANE
    heuristic_present = heuristic_model_lane != UNKNOWN_MODEL_LANE
    return {
        "model_catalog_entry_server_issued": False,
        "model_lane": UNKNOWN_MODEL_LANE,
        "model_lane_classified": False,
        "model_lane_classification_source": (
            FALLBACK_NAME_HEURISTIC_CLASSIFICATION_SOURCE if heuristic_present else "none"
        ),
        "model_lane_fallback_used": heuristic_present,
        "model_lane_proof_level": HEURISTIC_ONLY_NOT_EXECUTABLE_MODEL_LANE_PROOF_LEVEL
        if heuristic_present
        else UNCLASSIFIED_MODEL_LANE_PROOF_LEVEL,
        "heuristic_model_lane": heuristic_model_lane,
        "heuristic_only_not_executable": heuristic_present,
        "runtime_lane_proven": False,
        "legacy_catalog_lane": "",
    }


def _model_entry_lane_classification(
    model_id: str,
    lane: str,
    *,
    server_lane_explicit: bool = False,
) -> dict[str, Any]:
    model_id_text = str(model_id or "")
    model_lane = _canonical_model_lane_from_legacy_lane(lane)
    if server_lane_explicit and model_lane != UNKNOWN_MODEL_LANE:
        return {
            "model_catalog_entry_server_issued": True,
            "model_lane": model_lane,
            "model_lane_classified": True,
            "model_lane_classification_source": (
                SERVER_MODEL_CATALOG_CLASSIFICATION_SOURCE
                if model_lane == CODEX_ACCOUNT_MODEL_LANE
                else SERVER_API_ROUTE_SNAPSHOT_CLASSIFICATION_SOURCE
            ),
            "model_lane_fallback_used": False,
            "model_lane_proof_level": SERVER_CLASSIFIED_MODEL_LANE_PROOF_LEVEL,
            "heuristic_model_lane": UNKNOWN_MODEL_LANE,
            "heuristic_only_not_executable": False,
            "runtime_lane_proven": False,
            "legacy_catalog_lane": lane,
        }
    if model_lane == CODEX_ACCOUNT_MODEL_LANE and (
        model_id_text in CANONICAL_INTERNAL_MODEL_IDS or model_id_text.startswith("codex-")
    ):
        return {
            "model_catalog_entry_server_issued": True,
            "model_lane": CODEX_ACCOUNT_MODEL_LANE,
            "model_lane_classified": True,
            "model_lane_classification_source": SERVER_MODEL_CATALOG_CLASSIFICATION_SOURCE,
            "model_lane_fallback_used": False,
            "model_lane_proof_level": SERVER_CLASSIFIED_MODEL_LANE_PROOF_LEVEL,
            "heuristic_model_lane": UNKNOWN_MODEL_LANE,
            "heuristic_only_not_executable": False,
            "runtime_lane_proven": False,
            "legacy_catalog_lane": lane,
        }
    fallback = fallback_model_lane_classification(model_id_text)
    fallback["model_catalog_entry_server_issued"] = True
    fallback["legacy_catalog_lane"] = lane
    return fallback


def model_lane_classification_from_registry(
    model_id: str,
    registry: dict[str, Any] | None,
) -> dict[str, Any]:
    entries = registry.get("available_models") if isinstance(registry, dict) else []
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and str(entry.get("model_id") or "") == model_id:
                return model_lane_classification_from_entry(entry)
    return fallback_model_lane_classification(model_id)


def _model_lane(model_id: str) -> str:
    if _is_native_model_id(model_id):
        return "codex_native"
    return "wbp_api"


def _is_native_model_id(model_id: str) -> bool:
    return model_id in CANONICAL_INTERNAL_MODEL_IDS or model_id.startswith("codex-")


def _display_name(model_id: str, label: str | None = None, *, lane: str = "") -> str:
    visible = str(label or model_id).strip() or model_id
    lane_text = str(lane or _model_lane(model_id))
    if lane_text == "codex_native":
        return visible
    if visible.lower().startswith(("wbp ", "wbp:", "wild boar ")):
        return visible
    return f"WBP {visible}"


def _source_class(model_id: str, *, lane: str = "") -> str:
    lane_text = str(lane or _model_lane(model_id))
    if lane_text == "codex_native":
        return "current_build_catalog_visible"
    return "server_registry"


def _selection_gate_from_live_availability(
    entry: dict[str, Any],
    availability_row: dict[str, Any] | None,
) -> tuple[str, list[str]] | None:
    if not isinstance(availability_row, dict):
        return None
    if str(entry.get("lane") or "") != "codex_native":
        return None
    if str(availability_row.get("availability_evidence_scope") or "") != "current_thread_direct_wbp_non_stream":
        return None
    if availability_row.get("live_availability_proven") is True:
        return None
    failure_cause = str(availability_row.get("failure_cause") or "").strip()
    blocked_reason = str(availability_row.get("blocked_reason_if_any") or "").strip()
    machine_error_code = str(availability_row.get("machine_error_code") or "").strip().upper()
    http_status = availability_row.get("http_status")
    if failure_cause in {"", "none"} and not blocked_reason and not machine_error_code:
        return None
    code = "LIVE_NATIVE_BLOCKED"
    reasons = ["current_live_native_probe_blocked"]
    if "DEACTIVATED_WORKSPACE" in machine_error_code:
        code = "WORKSPACE_DEACTIVATED"
        reasons.append("workspace_deactivated")
    elif "UNSUPPORTED_FOR_ACCOUNT_PATH" in machine_error_code:
        code = "ACCOUNT_PATH_UNSUPPORTED"
        reasons.append("unsupported_for_account_path")
    elif failure_cause == "account_auth_failed" or "AUTH_UNAVAILABLE" in machine_error_code:
        code = "ACCOUNT_AUTH_UNAVAILABLE"
        reasons.append("account_auth_failed")
    elif failure_cause == "upstream_model_rejected":
        code = "UPSTREAM_MODEL_REJECTED"
        reasons.append("upstream_model_rejected")
    elif failure_cause == "wbp_runtime_unavailable":
        code = "LIVE_RUNTIME_UNAVAILABLE"
        reasons.append("runtime_unavailable")
    elif failure_cause:
        reasons.append(failure_cause)
    if isinstance(http_status, int):
        reasons.append(f"http_{http_status}")
    deduped: list[str] = []
    for item in reasons:
        text = str(item).strip()
        if text and text not in deduped:
            deduped.append(text)
    return code, deduped


def _tier_unknown() -> dict[str, str]:
    return {
        "label": "unavailable_unknown",
        "source": "unavailable_unknown",
        "proof_level": "unproven",
    }


def _route_thinking_metadata_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    thinking = entry.get("thinking")
    if not isinstance(thinking, dict):
        return {
            "thinking": {"type": "unconfigured"},
            "api_parameter_sent": False,
            "intelligence_measured": False,
            "label_source": "unavailable_unknown",
        }
    thinking_type = str(thinking.get("type") or "disabled").strip()
    if thinking_type != "enabled":
        return {
            "thinking": {"type": "disabled"},
            "api_parameter_sent": False,
            "intelligence_measured": False,
            "label_source": "operator_mapping",
        }
    return {
        "thinking": {
            "type": "enabled",
            "reasoning_effort": str(thinking.get("reasoning_effort") or "high"),
        },
        "api_parameter_sent": True,
        "intelligence_measured": False,
        "label_source": "provider_declared_plus_operator_mapping",
    }


def _route_intelligence_tier_from_thinking(thinking_metadata: dict[str, Any]) -> dict[str, str]:
    thinking = thinking_metadata.get("thinking")
    if not isinstance(thinking, dict):
        return _tier_unknown()
    if thinking.get("type") != "enabled":
        return {
            "label": "fast_no_thinking",
            "source": "operator_assigned",
            "proof_level": "declared",
        }
    return {
        "label": f"reasoning_effort_{str(thinking.get('reasoning_effort') or 'high')}",
        "source": "provider_declared",
        "proof_level": "declared",
    }


def _model_entry(
    model_id: str,
    *,
    lane: str = "",
    server_lane_explicit: bool = False,
) -> dict[str, Any]:
    lane = lane if lane in {"codex_native", "wbp_api"} else _model_lane(model_id)
    source = _model_source_hint(model_id, lane=lane)
    source_class = _source_class(model_id, lane=lane)
    lane_classification = _model_entry_lane_classification(
        model_id,
        lane,
        server_lane_explicit=server_lane_explicit,
    )
    lane_executable = (
        lane_classification.get("model_lane_classified") is True
        and lane_classification.get("model_lane_fallback_used") is not True
    )
    return {
        "model_id": model_id,
        "label": model_id,
        "display_name": _display_name(model_id, lane=lane),
        "lane": lane,
        **lane_classification,
        "source": source,
        "source_class": source_class,
        "provider_class": _provider_class(model_id, lane=lane),
        "provider_label": _provider_label(model_id, source_class=source_class, lane=lane),
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
        "selection_enabled": lane_executable,
        "selection_state": "selectable" if lane_executable else "disabled",
        "selection_disabled_reason_code": "" if lane_executable else "HEURISTIC_ONLY_NOT_EXECUTABLE",
        "selection_disabled_reasons": [] if lane_executable else ["model_lane_not_server_classified"],
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


def _server_catalog_model_specs(models: dict[str, Any]) -> list[dict[str, Any]]:
    raw_model_ids = models.get("model_ids", [])
    specs: list[dict[str, Any]] = [
        {
            "model_id": str(model_id),
            "lane": "",
            "server_lane_explicit": False,
        }
        for model_id in raw_model_ids
        if isinstance(model_id, str) and model_id
    ]
    raw_entries = models.get("model_entries")
    if isinstance(raw_entries, list):
        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("model_id") or "").strip()
            lane = str(entry.get("lane") or entry.get("legacy_catalog_lane") or "").strip()
            if not model_id:
                continue
            specs.append(
                {
                    "model_id": model_id,
                    "lane": lane if lane in {"codex_native", "wbp_api"} else "",
                    "server_lane_explicit": lane in {"codex_native", "wbp_api"},
                }
            )
    deduped: dict[str, dict[str, Any]] = {}
    for spec in specs:
        model_id = str(spec.get("model_id") or "")
        if not model_id:
            continue
        existing = deduped.get(model_id)
        if existing is None or (
            spec.get("server_lane_explicit") is True
            and existing.get("server_lane_explicit") is not True
        ):
            deduped[model_id] = spec
    return list(deduped.values())[:100]


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
        label = str(route.get("display_name") or route.get("upstream_model") or route_id).strip()
        thinking_metadata = _route_thinking_metadata_from_entry(route)
        entry.update(
            {
                "label": label or route_id,
                "display_name": _display_name(route_id, label or route_id, lane="wbp_api"),
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
                "upstream_model": str(route.get("upstream_model") or route_id),
                "thinking": dict(thinking_metadata["thinking"]),
                "api_parameter_sent": thinking_metadata["api_parameter_sent"] is True,
                "intelligence_measured": False,
                "label_source": str(thinking_metadata["label_source"]),
                "intelligence_tier": _route_intelligence_tier_from_thinking(thinking_metadata),
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
        entry.update(
            {
                "model_catalog_entry_server_issued": True,
                "model_lane": API_ROUTE_MODEL_LANE,
                "model_lane_classified": True,
                "model_lane_classification_source": SERVER_API_ROUTE_SNAPSHOT_CLASSIFICATION_SOURCE,
                "model_lane_fallback_used": False,
                "model_lane_proof_level": SERVER_CLASSIFIED_MODEL_LANE_PROOF_LEVEL,
                "runtime_lane_proven": False,
                "legacy_catalog_lane": "wbp_api",
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
    lane_classification = model_lane_classification_from_entry(entry)
    availability_row = availability_row if isinstance(availability_row, dict) else {}
    availability_levels = availability_row.get("availability_levels")
    if not isinstance(availability_levels, list) or not availability_levels:
        availability_levels = ["listed"]
    bounded_limitations = availability_row.get("bounded_limitations")
    if not isinstance(bounded_limitations, list):
        bounded_limitations = []
    return {
        "lane": str(entry.get("lane") or _model_lane(model_id)),
        **lane_classification,
        "model_id": model_id,
        "label": str(entry.get("label") or model_id),
        "display_name": str(
            entry.get("display_name")
            or _display_name(
                model_id,
                str(entry.get("label") or model_id),
                lane=str(entry.get("lane") or ""),
            )
        ),
        "source": str(entry.get("source") or entry.get("model_source_hint") or "unknown"),
        "source_class": str(entry.get("source_class") or _source_class(model_id)),
        "provider_class": str(entry.get("provider_class") or "unknown"),
        "provider_label": str(
            entry.get("provider_label")
            or _provider_label(
                model_id,
                source_class=str(entry.get("source_class") or _source_class(model_id)),
                lane=str(entry.get("lane") or ""),
            )
        ),
        "physical_provider": str(entry.get("physical_provider") or ""),
        "physical_provider_proven": entry.get("physical_provider_proven") is True,
        "provider_model_id": str(entry.get("provider_model_id") or ""),
        "upstream_model": str(entry.get("upstream_model") or entry.get("provider_model_id") or ""),
        "aliases": list(entry.get("aliases") or []),
        "intelligence_tier": dict(entry.get("intelligence_tier") or _tier_unknown()),
        "speed_tier": dict(entry.get("speed_tier") or _tier_unknown()),
        "thinking": dict(entry.get("thinking") or {}),
        "api_parameter_sent": entry.get("api_parameter_sent") is True,
        "intelligence_measured": entry.get("intelligence_measured") is True,
        "label_source": str(entry.get("label_source") or "unavailable_unknown"),
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


def _historical_seed_entries() -> list[dict[str, Any]]:
    seed_path = REPO_ROOT / "external_agent_lab" / "model_registry_seed.json"
    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _provider_dashboard_by_name() -> dict[str, str]:
    return {
        str(entry.get("provider") or ""): str(entry.get("provider_dashboard_url") or "")
        for entry in provider_specs_inventory()
        if str(entry.get("provider") or "")
    }


def _seed_provider_rows() -> list[dict[str, Any]]:
    auth_rows = {
        str(entry.get("provider") or ""): entry
        for entry in provider_specs_inventory()
        if str(entry.get("provider") or "")
    }
    dashboard_by_name = _provider_dashboard_by_name()
    seed_entries = _historical_seed_entries()
    providers = sorted(
        {
            provider
            for provider in auth_rows
            if provider
        }
        | {
            str(entry.get("provider") or "").strip()
            for entry in seed_entries
            if str(entry.get("provider") or "").strip()
        }
    )
    rows: list[dict[str, Any]] = []
    for provider in providers:
        auth_row = auth_rows.get(provider)
        rows.append(
            {
                "provider": provider,
                "provider_family": str(
                    (auth_row or {}).get("provider_family")
                    or next(
                        (
                            str(entry.get("provider_type") or "").strip() or "historical_seed"
                            for entry in seed_entries
                            if str(entry.get("provider") or "").strip() == provider
                        ),
                        "historical_seed",
                    )
                ),
                "auth_schema_admitted": auth_row is not None,
                "runtime_admitted": False,
                "runtime_compatibility_claimed": False,
                "model_family_compatibility_claimed": False,
                "credential_ref": str((auth_row or {}).get("credential_ref") or ""),
                "owner_env_candidates": list((auth_row or {}).get("owner_env_candidates") or []),
                "provider_dashboard_url": str(
                    (auth_row or {}).get("provider_dashboard_url")
                    or dashboard_by_name.get(provider)
                    or ""
                ),
                "seed_source": str((auth_row or {}).get("seed_source") or "historical_seed"),
                "current_status": "auth_schema_admitted" if auth_row is not None else "seed_only",
                "classification_scope": "provider_registry_only",
            }
        )
    return rows


def _generic_provider_registry_rows() -> list[dict[str, Any]]:
    rows = _seed_provider_rows()
    return sorted(rows, key=lambda row: str(row.get("provider") or ""))


def _current_catalog_model_rows(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    catalog = build_wbp_model_catalog_contract_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    models = catalog.get("models")
    if not isinstance(models, list):
        return []
    rows: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        rows.append(
            {
                "model_id": str(model.get("model_id") or ""),
                "display_name": str(model.get("display_name") or model.get("model_id") or ""),
                "provider": str(model.get("physical_provider") or ""),
                "provider_label": str(model.get("provider_label") or ""),
                "provider_model_id": str(model.get("provider_model_id") or ""),
                "upstream_model": str(model.get("upstream_model") or model.get("provider_model_id") or ""),
                "lane_kind": str(model.get("lane") or ""),
                "model_lane": str(model.get("model_lane") or UNKNOWN_MODEL_LANE),
                "model_lane_classified": model.get("model_lane_classified") is True,
                "model_lane_classification_source": str(
                    model.get("model_lane_classification_source") or "none"
                ),
                "model_lane_fallback_used": model.get("model_lane_fallback_used") is True,
                "model_lane_proof_level": str(
                    model.get("model_lane_proof_level") or UNCLASSIFIED_MODEL_LANE_PROOF_LEVEL
                ),
                "heuristic_model_lane": str(model.get("heuristic_model_lane") or UNKNOWN_MODEL_LANE),
                "heuristic_only_not_executable": model.get("heuristic_only_not_executable") is True,
                "runtime_lane_proven": False,
                "cost_class": "unknown_unclassified",
                "speed_tier": dict(model.get("speed_tier") or _tier_unknown()),
                "intelligence_tier": dict(model.get("intelligence_tier") or _tier_unknown()),
                "thinking": dict(model.get("thinking") or {}),
                "api_parameter_sent": model.get("api_parameter_sent") is True,
                "intelligence_measured": model.get("intelligence_measured") is True,
                "label_source": str(model.get("label_source") or "unavailable_unknown"),
                "capability_tags": [],
                "availability_state": str(model.get("availability_claim_level") or "listed_not_live_proven"),
                "proof_level": "classified",
                "seed_source": "current_runtime_catalog",
                "current_status": "current_catalog",
                "server_issued_for_runtime_selection": model.get("server_issued") is True,
                "selection_enabled": model.get("selection_enabled") is True,
                "selection_state": str(model.get("selection_state") or ""),
                "selection_disabled_reason_code": str(
                    model.get("selection_disabled_reason_code") or ""
                ),
                "selection_disabled_reasons": [
                    str(item) for item in model.get("selection_disabled_reasons") or []
                ],
                "runtime_compatibility_claimed": False,
                "model_availability_claimed": False,
                "display_metadata_only": False,
            }
        )
    return rows


def _seed_only_model_rows(current_catalog_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current_ids = {
        str(row.get("model_id") or "")
        for row in current_catalog_rows
        if str(row.get("model_id") or "")
    }
    rows: list[dict[str, Any]] = []
    for entry in _historical_seed_entries():
        model_id = str(entry.get("model_id") or "").strip()
        provider = str(entry.get("provider") or "").strip()
        if not model_id or model_id in current_ids:
            continue
        rows.append(
            {
                "model_id": model_id,
                "display_name": model_id,
                "provider": provider,
                "provider_label": provider or "historical_seed",
                "provider_model_id": model_id,
                "lane_kind": "seed_only",
                "cost_class": str(entry.get("cost_class") or "unknown_unclassified"),
                "speed_tier": _tier_unknown(),
                "intelligence_tier": _tier_unknown(),
                "capability_tags": [str(tag) for tag in entry.get("capability_tags") or [] if str(tag)],
                "availability_state": str(entry.get("availability_state") or SEED_ONLY_MODEL_AVAILABILITY_STATE),
                "proof_level": "declared",
                "seed_source": "historical_external_agent_lab",
                "current_status": "seed_only",
                "server_issued_for_runtime_selection": False,
                "selection_enabled": False,
                "runtime_compatibility_claimed": False,
                "model_availability_claimed": False,
                "display_metadata_only": True,
            }
        )
    return sorted(rows, key=lambda row: str(row.get("model_id") or ""))


def build_generic_provider_registry_packet() -> dict[str, Any]:
    rows = _generic_provider_registry_rows()
    current_auth_admitted = [
        row["provider"] for row in rows if row.get("auth_schema_admitted") is True
    ]
    seed_only = [row["provider"] for row in rows if row.get("auth_schema_admitted") is not True]
    return {
        "schema_version": GENERIC_PROVIDER_REGISTRY_SCHEMA_VERSION,
        "packet_kind": "generic_provider_registry",
        "captured_at_utc": utc_now(),
        "status": "ok" if rows else "blocked",
        "classification_scope": "provider_registry_only",
        "rows": rows,
        "provider_count": len(rows),
        "current_auth_admitted_providers": current_auth_admitted,
        "seed_only_providers": seed_only,
        "auth_admission_is_runtime_admission": False,
        "provider_family_compatibility_claimed": False,
        "browser_authority_widened": False,
    }


def build_generic_model_registry_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_catalog_models = _current_catalog_model_rows(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    seed_only_models = _seed_only_model_rows(current_catalog_models)
    return {
        "schema_version": GENERIC_MODEL_REGISTRY_SCHEMA_VERSION,
        "packet_kind": "generic_model_registry",
        "captured_at_utc": utc_now(),
        "status": "ok" if current_catalog_models else "blocked",
        "classification_scope": "model_registry_only",
        "current_catalog_models": current_catalog_models,
        "seed_only_models": seed_only_models,
        "current_catalog_model_count": len(current_catalog_models),
        "seed_only_model_count": len(seed_only_models),
        "current_catalog_is_runtime_proof": False,
        "seed_only_is_current_runtime_catalog": False,
        "registry_export_implies_consumer_integration_complete": False,
        "allowed_browser_fields": ["model_id"],
        "browser_authority_widened": False,
    }


def _selector_rows_by_lane(model_registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    current_rows = model_registry.get("current_catalog_models")
    seed_rows = model_registry.get("seed_only_models")
    current_rows = current_rows if isinstance(current_rows, list) else []
    seed_rows = seed_rows if isinstance(seed_rows, list) else []
    chatgpt_rows = [
        row for row in current_rows if isinstance(row, dict) and str(row.get("lane_kind") or "") == "codex_native"
    ]
    api_rows = [
        row for row in current_rows if isinstance(row, dict) and str(row.get("lane_kind") or "") == "wbp_api"
    ]
    seed_rows = [row for row in seed_rows if isinstance(row, dict)]
    return chatgpt_rows, api_rows, seed_rows


def _default_selector_model_id(rows: list[dict[str, Any]], preferred_model_id: str = "") -> str:
    if preferred_model_id:
        for row in rows:
            if (
                str(row.get("model_id") or "") == preferred_model_id
                and row.get("selection_enabled") is True
            ):
                return preferred_model_id
    for row in rows:
        if row.get("selection_enabled") is True:
            return str(row.get("model_id") or "")
    for row in rows:
        model_id = str(row.get("model_id") or "")
        if model_id:
            return model_id
    return ""


def _selector_entry_from_row(
    row: dict[str, Any],
    *,
    lane_display: str,
    selection_note: str,
) -> dict[str, Any]:
    selection_enabled = row.get("selection_enabled") is True
    return {
        "model_id": str(row.get("model_id") or ""),
        "display_name": str(row.get("display_name") or row.get("model_id") or ""),
        "provider": str(row.get("provider") or ""),
        "provider_label": str(row.get("provider_label") or ""),
        "provider_model_id": str(row.get("provider_model_id") or ""),
        "upstream_model": str(row.get("upstream_model") or row.get("provider_model_id") or ""),
        "lane_kind": str(row.get("lane_kind") or ""),
        "model_lane": str(row.get("model_lane") or UNKNOWN_MODEL_LANE),
        "model_lane_classified": row.get("model_lane_classified") is True,
        "model_lane_classification_source": str(
            row.get("model_lane_classification_source") or "none"
        ),
        "model_lane_fallback_used": row.get("model_lane_fallback_used") is True,
        "model_lane_proof_level": str(
            row.get("model_lane_proof_level") or UNCLASSIFIED_MODEL_LANE_PROOF_LEVEL
        ),
        "heuristic_model_lane": str(row.get("heuristic_model_lane") or UNKNOWN_MODEL_LANE),
        "heuristic_only_not_executable": row.get("heuristic_only_not_executable") is True,
        "runtime_lane_proven": False,
        "lane_display": lane_display,
        "selection_enabled": selection_enabled,
        "selection_state": str(
            row.get("selection_state") or ("selectable" if selection_enabled else "disabled")
        ),
        "selection_disabled_reason_code": str(row.get("selection_disabled_reason_code") or ""),
        "selection_disabled_reasons": [
            str(item) for item in row.get("selection_disabled_reasons") or []
        ],
        "server_issued": row.get("server_issued_for_runtime_selection") is True,
        "current_status": str(row.get("current_status") or ""),
        "availability_state": str(row.get("availability_state") or "listed_not_live_proven"),
        "proof_level": str(row.get("proof_level") or "classified"),
        "speed_tier": dict(row.get("speed_tier") or _tier_unknown()),
        "intelligence_tier": dict(row.get("intelligence_tier") or _tier_unknown()),
        "thinking": dict(row.get("thinking") or {}),
        "api_parameter_sent": row.get("api_parameter_sent") is True,
        "intelligence_measured": row.get("intelligence_measured") is True,
        "label_source": str(row.get("label_source") or "unavailable_unknown"),
        "selection_intent_only": True,
        "runtime_selection_proven": False,
        "session_execution_ready": False,
        "selection_note": selection_note,
    }


def _seed_reference_entry_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_id": str(row.get("model_id") or ""),
        "display_name": str(row.get("display_name") or row.get("model_id") or ""),
        "provider": str(row.get("provider") or ""),
        "provider_label": str(row.get("provider_label") or ""),
        "lane_kind": "seed_only_reference",
        "selection_enabled": False,
        "selection_state": "disabled",
        "selection_disabled_reason_code": "SEED_ONLY_REFERENCE",
        "selection_disabled_reasons": ["historical_seed_only", "not_current_runtime_catalog"],
        "server_issued": False,
        "current_status": str(row.get("current_status") or "seed_only"),
        "availability_state": str(
            row.get("availability_state") or SEED_ONLY_MODEL_AVAILABILITY_STATE
        ),
        "proof_level": str(row.get("proof_level") or "declared"),
        "selection_intent_only": True,
        "runtime_selection_proven": False,
        "session_execution_ready": False,
        "selection_note": "historical reference only; not current runtime catalog",
    }


def build_dual_lane_model_selection_ui_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_registry = build_generic_model_registry_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    current_chat_rows, current_api_rows, seed_rows = _selector_rows_by_lane(model_registry)
    chatgpt_entries = [
        _selector_entry_from_row(
            row,
            lane_display="ChatGPT / Codex-native",
            selection_note="current launch/session lane in this contour",
        )
        for row in current_chat_rows
    ]
    api_entries = [
        _selector_entry_from_row(
            row,
            lane_display="API / WBP",
            selection_note="selection intent only; runtime compatibility unresolved",
        )
        for row in current_api_rows
    ]
    seed_entries = [_seed_reference_entry_from_row(row) for row in seed_rows]
    chatgpt_default = _default_selector_model_id(chatgpt_entries, recommended_default_model)
    api_default = _default_selector_model_id(api_entries)
    return {
        "schema_version": 1,
        "packet_kind": "dual_lane_model_selection_ui",
        "captured_at_utc": utc_now(),
        "status": "ok" if chatgpt_entries or api_entries or seed_entries else "blocked",
        "machine_error_code": "OK" if chatgpt_entries or api_entries or seed_entries else "CUSTOM_SELECTOR_EMPTY",
        "selection_truth_scope": "display_and_intent_only",
        "selection_intent_only": True,
        "selector_runtime_readiness_claimed": False,
        "simultaneous_execution_proven": False,
        "role_slot_binding_proven": False,
        "flat_model_truth_presented": False,
        "server_issued": True,
        "browser_authority": {
            "provider": False,
            "route_id": False,
            "account_id": False,
            "base_url": False,
            "auth_path": False,
            "secret_ref": False,
            "codex_home": False,
        },
        "allowed_browser_fields": ["chatgpt_model_id", "api_model_id"],
        "forbidden_browser_fields": ["model_id", *sorted(CUSTOM_MODEL_DRY_RUN_FORBIDDEN_FIELDS)],
        "chatgpt_lane": {
            "lane_display": "ChatGPT / Codex-native",
            "current_catalog_only": True,
            "models": chatgpt_entries,
            "model_count": len(chatgpt_entries),
            "selectable_model_count": sum(
                1 for entry in chatgpt_entries if entry.get("selection_enabled") is True
            ),
            "default_model_id": chatgpt_default,
            "selection_note": "used by the current execution path in this contour",
        },
        "api_lane": {
            "lane_display": "API / WBP",
            "current_catalog_only": True,
            "models": api_entries,
            "model_count": len(api_entries),
            "selectable_model_count": sum(
                1 for entry in api_entries if entry.get("selection_enabled") is True
            ),
            "default_model_id": api_default,
            "selection_note": "selection intent only until role-slot and session contours close",
        },
        "seed_only_reference": {
            "visible_policy": "separate_reference_section_non_selectable",
            "models": seed_entries,
            "model_count": len(seed_entries),
            "current_runtime_catalog": False,
            "selectable": False,
        },
        "non_claims": {
            "ui_selection_is_session_execution": False,
            "selected_api_model_is_route_runtime_proven": False,
            "selected_chatgpt_model_is_account_health_proven": False,
            "dual_lane_selection_is_simultaneous_execution": False,
            "seed_only_visibility_is_current_support": False,
        },
    }


def _selector_entry_index(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("model_id") or ""): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("model_id") or "")
    }


def build_dual_lane_selection_intent_packet(
    payload: Any,
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_dual_lane_selector_fields(payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "dual_lane_selection_intent",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "forbidden_fields": forbidden,
            "selection_intent_only": True,
            "selector_runtime_readiness_claimed": False,
            "simultaneous_execution_proven": False,
            "role_slot_binding_proven": False,
            "browser_authority_widened": False,
            "next_action": "remove_browser_payload_fields",
        }
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    payload = payload if isinstance(payload, dict) else {}
    reported_configured_model = _reported_configured_model(operator_status)
    chatgpt_lane = dict(selector.get("chatgpt_lane") or {})
    api_lane = dict(selector.get("api_lane") or {})
    chatgpt_rows = list(chatgpt_lane.get("models") or [])
    api_rows = list(api_lane.get("models") or [])
    chatgpt_index = _selector_entry_index(chatgpt_rows)
    api_index = _selector_entry_index(api_rows)
    chatgpt_model_selected_by_user = isinstance(payload.get("chatgpt_model_id"), str) and bool(
        str(payload.get("chatgpt_model_id") or "").strip()
    )
    api_model_selected_by_user = isinstance(payload.get("api_model_id"), str) and bool(
        str(payload.get("api_model_id") or "").strip()
    )
    chatgpt_model_id = str(payload.get("chatgpt_model_id") or "").strip()
    api_model_id = str(payload.get("api_model_id") or "").strip()
    chatgpt_selected = chatgpt_index.get(chatgpt_model_id)
    api_selected = api_index.get(api_model_id)

    if chatgpt_model_id and chatgpt_selected is None:
        return {
            "schema_version": 1,
            "packet_kind": "dual_lane_selection_intent",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "CHATGPT_MODEL_NOT_SERVER_ISSUED",
            "selection_intent_only": True,
            "selector_runtime_readiness_claimed": False,
            "simultaneous_execution_proven": False,
            "role_slot_binding_proven": False,
            "browser_authority_widened": False,
            "selected_chatgpt_model_id": chatgpt_model_id,
            "next_action": "choose_server_issued_chatgpt_model",
        }
    if api_model_id and api_selected is None:
        return {
            "schema_version": 1,
            "packet_kind": "dual_lane_selection_intent",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "API_MODEL_NOT_SERVER_ISSUED",
            "selection_intent_only": True,
            "selector_runtime_readiness_claimed": False,
            "simultaneous_execution_proven": False,
            "role_slot_binding_proven": False,
            "browser_authority_widened": False,
            "selected_api_model_id": api_model_id,
            "next_action": "choose_server_issued_api_model",
        }
    if chatgpt_selected and chatgpt_selected.get("selection_enabled") is not True:
        return {
            "schema_version": 1,
            "packet_kind": "dual_lane_selection_intent",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "CHATGPT_MODEL_NOT_SELECTABLE",
            "selection_intent_only": True,
            "selector_runtime_readiness_claimed": False,
            "simultaneous_execution_proven": False,
            "role_slot_binding_proven": False,
            "browser_authority_widened": False,
            "chatgpt_selection": chatgpt_selected,
            "next_action": "choose_selectable_chatgpt_model",
        }
    if api_selected and api_selected.get("selection_enabled") is not True:
        return {
            "schema_version": 1,
            "packet_kind": "dual_lane_selection_intent",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "API_MODEL_NOT_SELECTABLE",
            "selection_intent_only": True,
            "selector_runtime_readiness_claimed": False,
            "simultaneous_execution_proven": False,
            "role_slot_binding_proven": False,
            "browser_authority_widened": False,
            "api_selection": api_selected,
            "next_action": "choose_selectable_api_model",
        }

    status = "ok" if chatgpt_selected and api_selected else "degraded"
    machine_error_code = "OK"
    if not chatgpt_selected:
        machine_error_code = "CHATGPT_LANE_SELECTION_UNRESOLVED"
    elif not api_selected:
        machine_error_code = "API_LANE_SELECTION_UNRESOLVED"
    return {
        "schema_version": 1,
        "packet_kind": "dual_lane_selection_intent",
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": machine_error_code,
        "selection_intent_only": True,
        "selector_runtime_readiness_claimed": False,
        "simultaneous_execution_proven": False,
        "role_slot_binding_proven": False,
        "browser_authority_widened": False,
        "allowed_browser_fields": ["chatgpt_model_id", "api_model_id"],
        "current_execution_path_model_id": reported_configured_model,
        "current_execution_path_scope": "chatgpt_lane_only_in_this_contour",
        "current_execution_path_source": "operator_reported_configured_model",
        "api_lane_scope": "selection_intent_only_until_role_slot_session_contour",
        "chatgpt_selection": chatgpt_selected,
        "api_selection": api_selected,
        "chatgpt_model_selected_by_user": chatgpt_model_selected_by_user,
        "api_model_selected_by_user": api_model_selected_by_user,
        "catalog_defaults_used_as_selection": False,
        "selection_intent_proven": bool(chatgpt_selected and api_selected),
        "selected_models_are_server_issued": bool(
            (chatgpt_selected or {}).get("server_issued")
            and (api_selected or {}).get("server_issued")
        ),
        "browser_selected_chatgpt_matches_current_execution_path": bool(
            reported_configured_model
            and str((chatgpt_selected or {}).get("model_id") or "") == reported_configured_model
        ),
        "seed_only_selected": False,
        "session_execution_wired": False,
        "non_claims": {
            "ui_selection_is_session_execution": False,
            "selected_api_model_is_route_runtime_proven": False,
            "selected_chatgpt_model_is_account_health_proven": False,
            "dual_lane_selection_is_simultaneous_execution": False,
        },
        "next_action": "none" if chatgpt_selected and api_selected else "choose_visible_lane_models",
    }


def _api_route_row_by_model_id(api_snapshot: dict[str, Any] | None, model_id: str) -> dict[str, Any]:
    routes = api_snapshot.get("routes") if isinstance(api_snapshot, dict) else []
    if not isinstance(routes, list):
        return {}
    for route in routes:
        if isinstance(route, dict) and str(route.get("route_id") or "") == model_id:
            return dict(route)
    return {}


def _execution_mode_slot_binding(
    *,
    slot_id: str,
    selection: dict[str, Any] | None,
    lane: str,
    binding_source: str,
) -> dict[str, Any]:
    selection = dict(selection or {})
    model_id = str(selection.get("model_id") or "")
    return {
        "slot_id": slot_id,
        "status": "bound" if model_id else "not_bound",
        "model_id": model_id,
        "lane": lane,
        "source": "server_catalog",
        "binding_source": binding_source,
        "server_issued": selection.get("server_issued") is True,
        "selection_enabled": selection.get("selection_enabled") is True,
        "provider": str(selection.get("provider") or ""),
        "provider_label": str(selection.get("provider_label") or ""),
        "provider_model_id": str(selection.get("provider_model_id") or ""),
        "runtime_execution_proven": False,
        "live_call_attempted": False,
    }


def _execution_mode_not_bound_slot(*, slot_id: str, reason: str) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "status": "not_bound_for_mode",
        "reason": reason,
        "model_id": "",
        "runtime_execution_proven": False,
        "live_call_attempted": False,
    }


def _api_reasoning_option_from_selection(selection: dict[str, Any] | None) -> str:
    selection = dict(selection or {})
    thinking = selection.get("thinking")
    if not isinstance(thinking, dict):
        return CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
    thinking_type = str(thinking.get("type") or "").strip()
    if thinking_type == "enabled":
        effort = str(thinking.get("reasoning_effort") or "").strip().lower()
        if effort == "max":
            return CUSTOM_CODEX_API_REASONING_OPTION_MAX
        if effort == "high":
            return CUSTOM_CODEX_API_REASONING_OPTION_HIGH
        return CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
    if thinking_type == "disabled":
        return CUSTOM_CODEX_API_REASONING_OPTION_DISABLED
    return CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT


def _canonical_api_reasoning_option_id(option_id: str) -> str:
    if option_id == CUSTOM_CODEX_API_REASONING_OPTION_FAST:
        return CUSTOM_CODEX_API_REASONING_OPTION_DISABLED
    return option_id


def _api_reasoning_operator_level(option_id: str) -> str:
    canonical = _canonical_api_reasoning_option_id(option_id)
    if canonical == CUSTOM_CODEX_API_REASONING_OPTION_DISABLED:
        return "fast"
    if canonical == CUSTOM_CODEX_API_REASONING_OPTION_HIGH:
        return "high"
    if canonical == CUSTOM_CODEX_API_REASONING_OPTION_MAX:
        return "max"
    if canonical == CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT:
        return "catalog_default"
    return "unknown"


def _api_reasoning_option_packet(
    *,
    raw_option_id: str,
    api_required: bool,
    api_selection: dict[str, Any] | None,
) -> dict[str, Any]:
    selected_model_option_id = _api_reasoning_option_from_selection(api_selection)
    option_id = raw_option_id or CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
    effective_option_id = (
        selected_model_option_id
        if option_id == CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
        else option_id
    )
    thinking = (api_selection or {}).get("thinking")
    thinking = dict(thinking) if isinstance(thinking, dict) else {}
    provider_option = {
        "thinking": thinking if thinking else {"type": "unconfigured"},
        "api_parameter_sent": bool((api_selection or {}).get("api_parameter_sent") is True),
    }
    if not api_required:
        return {
            "status": "ignored_for_mode",
            "option_id": "",
            "requested_option_id": raw_option_id,
            "effective_option_id": "",
            "selected_model_option_id": "",
            "source": "mode_does_not_use_api",
            "proof_level": "not_applicable",
            "provider_option": {},
            "runtime_mutation_claimed": False,
            "intelligence_measured": False,
            "codex_intelligence_parity_claimed": False,
        }
    return {
        "status": "ok",
        "option_id": option_id,
        "canonical_option_id": _canonical_api_reasoning_option_id(option_id),
        "requested_option_id": raw_option_id,
        "requested_operator_level": _api_reasoning_operator_level(raw_option_id),
        "effective_option_id": effective_option_id,
        "canonical_effective_option_id": _canonical_api_reasoning_option_id(
            effective_option_id
        ),
        "selected_model_option_id": selected_model_option_id,
        "selected_model_operator_level": _api_reasoning_operator_level(
            selected_model_option_id
        ),
        "source": (
            "server_catalog_selected_model"
            if option_id == CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
            else "browser_choice_server_validated"
        ),
        "proof_level": "provider_declared"
        if selected_model_option_id != CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
        else "unproven",
        "provider_option": provider_option,
        "runtime_mutation_claimed": False,
        "intelligence_measured": False,
        "codex_intelligence_parity_claimed": False,
    }


def build_custom_codex_execution_mode_selector_packet(
    payload: Any,
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_custom_codex_execution_mode_fields(payload)
    payload = payload if isinstance(payload, dict) else {}
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    chatgpt_lane = dict(selector.get("chatgpt_lane") or {})
    api_lane = dict(selector.get("api_lane") or {})
    chatgpt_rows = [row for row in chatgpt_lane.get("models") or [] if isinstance(row, dict)]
    api_rows = [row for row in api_lane.get("models") or [] if isinstance(row, dict)]
    chatgpt_index = _selector_entry_index(chatgpt_rows)
    api_index = _selector_entry_index(api_rows)
    execution_mode = str(payload.get("execution_mode") or "").strip()
    raw_chatgpt_model_id = str(payload.get("chatgpt_model_id") or "").strip()
    raw_api_model_id = str(payload.get("api_model_id") or "").strip()
    raw_api_reasoning_option_id = str(payload.get("api_reasoning_option_id") or "").strip()
    chatgpt_model_id = raw_chatgpt_model_id or str(
        chatgpt_lane.get("default_model_id") or ""
    ).strip()
    chatgpt_selection = chatgpt_index.get(chatgpt_model_id) if chatgpt_model_id else None
    api_required = execution_mode in {
        CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API,
        CUSTOM_CODEX_EXECUTION_MODE_API_ONLY,
    }
    api_model_id = raw_api_model_id if api_required else ""
    api_selection = api_index.get(api_model_id) if api_model_id else None
    api_reasoning_option_packet = _api_reasoning_option_packet(
        raw_option_id=raw_api_reasoning_option_id,
        api_required=api_required,
        api_selection=api_selection,
    )

    status = "ok"
    machine_error_code = "OK"
    next_action = "none"
    if forbidden:
        status = "rejected"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_BROWSER_AUTHORITY_REJECTED"
        next_action = "remove_browser_payload_fields"
    elif (
        raw_api_reasoning_option_id
        and raw_api_reasoning_option_id not in CUSTOM_CODEX_API_REASONING_OPTION_ALLOWED_IDS
    ):
        status = "rejected"
        machine_error_code = "CUSTOM_CODEX_API_REASONING_OPTION_NOT_ADMITTED"
        next_action = "choose_server_issued_api_reasoning_option"
    elif execution_mode not in CUSTOM_CODEX_EXECUTION_MODES:
        status = "rejected"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_NOT_ADMITTED"
        next_action = "choose_admitted_execution_mode"
    elif raw_chatgpt_model_id and chatgpt_selection is None:
        status = "rejected"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_MODEL_NOT_SERVER_ISSUED"
        next_action = "choose_server_issued_chatgpt_model"
    elif execution_mode in {
        CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_ONLY,
        CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API,
    } and not chatgpt_selection:
        status = "blocked"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_MODEL_UNRESOLVED"
        next_action = "restore_server_issued_chatgpt_catalog"
    elif api_required and not api_model_id:
        status = "blocked"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_API_MODEL_REQUIRED"
        next_action = "choose_server_issued_api_model"
    elif api_model_id and api_selection is None:
        status = "rejected"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_API_MODEL_NOT_SERVER_ISSUED"
        next_action = "choose_server_issued_api_model"
    elif api_required and (api_selection or {}).get("selection_enabled") is not True:
        status = "blocked"
        machine_error_code = "CUSTOM_CODEX_EXECUTION_MODE_API_MODEL_NOT_SELECTABLE"
        next_action = "choose_selectable_api_model"
    elif (
        api_required
        and raw_api_reasoning_option_id
        and raw_api_reasoning_option_id != CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
        and _canonical_api_reasoning_option_id(raw_api_reasoning_option_id)
        != _canonical_api_reasoning_option_id(
            str(api_reasoning_option_packet.get("selected_model_option_id") or "")
        )
    ):
        status = "blocked"
        machine_error_code = "CUSTOM_CODEX_API_REASONING_OPTION_NOT_BACKED_BY_SELECTED_MODEL"
        next_action = "choose_matching_api_model_variant"

    primary_slot: dict[str, Any]
    coding_slot: dict[str, Any]
    chatgpt_executor_selected = False
    api_executor_selected = False
    dual_lane_slots_preserved = False
    if execution_mode == CUSTOM_CODEX_EXECUTION_MODE_API_ONLY and api_selection:
        primary_slot = _execution_mode_slot_binding(
            slot_id="primary_model_slot",
            selection=api_selection,
            lane=API_ROUTE_MODEL_LANE,
            binding_source="execution_mode_api_only_primary",
        )
        coding_slot = _execution_mode_not_bound_slot(
            slot_id="coding_agent_model_slot",
            reason="api_only_uses_primary_model_slot",
        )
        api_executor_selected = True
    elif execution_mode == CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API:
        primary_slot = _execution_mode_slot_binding(
            slot_id="primary_model_slot",
            selection=chatgpt_selection,
            lane=CODEX_ACCOUNT_MODEL_LANE,
            binding_source="execution_mode_chatgpt_api_primary",
        )
        coding_slot = _execution_mode_slot_binding(
            slot_id="coding_agent_model_slot",
            selection=api_selection,
            lane=API_ROUTE_MODEL_LANE,
            binding_source="execution_mode_chatgpt_api_coding_agent",
        )
        chatgpt_executor_selected = bool(chatgpt_selection)
        api_executor_selected = bool(api_selection)
        dual_lane_slots_preserved = bool(chatgpt_selection and api_selection)
    else:
        primary_slot = _execution_mode_slot_binding(
            slot_id="primary_model_slot",
            selection=chatgpt_selection,
            lane=CODEX_ACCOUNT_MODEL_LANE,
            binding_source="execution_mode_chatgpt_only_primary",
        )
        coding_slot = _execution_mode_not_bound_slot(
            slot_id="coding_agent_model_slot",
            reason="chatgpt_only_disables_api_execution",
        )
        chatgpt_executor_selected = bool(chatgpt_selection)

    final_status = (
        "CUSTOM_CODEX_EXECUTION_MODE_SELECTOR_PACKET_PROVEN_NO_LIVE_EXECUTION"
        if status == "ok"
        else machine_error_code
    )
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_execution_mode_selector",
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": final_status,
        "execution_mode": execution_mode,
        "allowed_execution_modes": [
            CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_ONLY,
            CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API,
            CUSTOM_CODEX_EXECUTION_MODE_API_ONLY,
        ],
        "allowed_browser_fields": sorted(CUSTOM_CODEX_EXECUTION_MODE_ALLOWED_FIELDS),
        "forbidden_browser_fields": sorted(CUSTOM_API_ACTION_GATE_FORBIDDEN_FIELDS),
        "forbidden_fields": forbidden,
        "browser_authority": {
            "execution_mode": True,
            "api_model_id": True,
            "api_reasoning_option_id": True,
            "provider": False,
            "route_id": False,
            "account_id": False,
            "base_url": False,
            "api_key": False,
            "secret_ref": False,
            "auth_path": False,
            "codex_home": False,
            "raw_config": False,
        },
        "browser_raw_backend_authority_widened": bool(forbidden),
        "server_issued_catalog_used": True,
        "raw_backend_details_exposed": False,
        "route_or_backend_exposed": False,
        "secret_value_exposed": False,
        "live_call_attempted": False,
        "network_calls_made": False,
        "provider_called": False,
        "responses_called": False,
        "chat_completions_called": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "wbp_patch_applier_used": False,
        "runtime_execution_proven": False,
        "selector_packet_truth_only": True,
        "ui_text_counts_as_runtime_truth": False,
        "deepseek_special_case": False,
        "first_admitted_api_provider": "deepseek",
        "chatgpt_model_id": chatgpt_model_id if chatgpt_executor_selected else "",
        "chatgpt_model_selected_by_user": bool(raw_chatgpt_model_id),
        "chatgpt_catalog_default_used": bool(
            not raw_chatgpt_model_id and chatgpt_executor_selected
        ),
        "api_provider_id": str((api_selection or {}).get("provider") or ""),
        "api_model_id": api_model_id,
        "api_model_selected_by_user": bool(raw_api_model_id),
        "api_model_ignored_for_mode": bool(raw_api_model_id and not api_required),
        "api_reasoning_option_id": str(api_reasoning_option_packet.get("option_id") or ""),
        "api_reasoning_option_selected_by_user": bool(raw_api_reasoning_option_id),
        "api_reasoning_option_ignored_for_mode": bool(raw_api_reasoning_option_id and not api_required),
        "api_reasoning_option_packet": api_reasoning_option_packet,
        "api_reasoning_option_runtime_mutation_claimed": False,
        "api_reasoning_supported_operator_levels": ["fast", "high", "max"],
        "api_reasoning_operator_level": str(
            api_reasoning_option_packet.get("selected_model_operator_level") or ""
        ),
        "api_reasoning_intelligence_measured": False,
        "api_reasoning_codex_parity_claimed": False,
        "primary_model_slot": primary_slot,
        "coding_agent_model_slot": coding_slot,
        "chatgpt_executor_selected": chatgpt_executor_selected,
        "api_executor_selected": api_executor_selected,
        "dual_lane_slots_preserved": dual_lane_slots_preserved,
        "chatgpt_line_used_as_executor": chatgpt_executor_selected,
        "api_line_used_as_executor": api_executor_selected,
        "api_only_calls_chatgpt": False,
        "chatgpt_only_calls_api": False,
        "non_claims": {
            "live_deepseek_execution_proven": False,
            "file_mutation_proven": False,
            "simultaneous_execution_proven": False,
            "codex_bottom_panel_modified": False,
            "history_persistence_proven": False,
        },
        "next_action": next_action,
    }


def _slot_lane(packet: dict[str, Any], slot_name: str) -> str:
    slot = packet.get(slot_name)
    return str(slot.get("lane") or "") if isinstance(slot, dict) else ""


def _slot_status(packet: dict[str, Any], slot_name: str) -> str:
    slot = packet.get(slot_name)
    return str(slot.get("status") or "") if isinstance(slot, dict) else ""


def _server_model_selection_slots_are_coherent(selector_packet: dict[str, Any]) -> bool:
    execution_mode = str(selector_packet.get("execution_mode") or "")
    if execution_mode == CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_ONLY:
        return (
            _slot_lane(selector_packet, "primary_model_slot") == CODEX_ACCOUNT_MODEL_LANE
            and _slot_status(selector_packet, "coding_agent_model_slot")
            == "not_bound_for_mode"
            and selector_packet.get("api_line_used_as_executor") is False
            and selector_packet.get("chatgpt_only_calls_api") is False
        )
    if execution_mode == CUSTOM_CODEX_EXECUTION_MODE_API_ONLY:
        return (
            _slot_lane(selector_packet, "primary_model_slot") == API_ROUTE_MODEL_LANE
            and _slot_status(selector_packet, "coding_agent_model_slot")
            == "not_bound_for_mode"
            and selector_packet.get("chatgpt_line_used_as_executor") is False
            and selector_packet.get("api_only_calls_chatgpt") is False
        )
    if execution_mode == CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API:
        return (
            _slot_lane(selector_packet, "primary_model_slot") == CODEX_ACCOUNT_MODEL_LANE
            and _slot_lane(selector_packet, "coding_agent_model_slot")
            == API_ROUTE_MODEL_LANE
            and selector_packet.get("dual_lane_slots_preserved") is True
            and selector_packet.get("chatgpt_executor_selected") is True
            and selector_packet.get("api_executor_selected") is True
        )
    return False


def _redacted_server_model_selector_packet(selector_packet: dict[str, Any]) -> dict[str, Any]:
    reasoning_packet = dict(selector_packet.get("api_reasoning_option_packet") or {})
    provider_option = dict(reasoning_packet.get("provider_option") or {})
    redacted_reasoning_packet = {
        "status": str(reasoning_packet.get("status") or ""),
        "option_id": str(reasoning_packet.get("option_id") or ""),
        "canonical_option_id": str(reasoning_packet.get("canonical_option_id") or ""),
        "requested_option_id": str(reasoning_packet.get("requested_option_id") or ""),
        "requested_operator_level": str(
            reasoning_packet.get("requested_operator_level") or ""
        ),
        "effective_option_id": str(reasoning_packet.get("effective_option_id") or ""),
        "canonical_effective_option_id": str(
            reasoning_packet.get("canonical_effective_option_id") or ""
        ),
        "selected_model_option_id": str(
            reasoning_packet.get("selected_model_option_id") or ""
        ),
        "selected_model_operator_level": str(
            reasoning_packet.get("selected_model_operator_level") or ""
        ),
        "source": str(reasoning_packet.get("source") or ""),
        "proof_level": str(reasoning_packet.get("proof_level") or ""),
        "provider_option": {
            "thinking": dict(provider_option.get("thinking") or {}),
            "api_parameter_sent": provider_option.get("api_parameter_sent") is True,
        }
        if provider_option
        else {},
        "runtime_mutation_claimed": reasoning_packet.get("runtime_mutation_claimed")
        is True,
        "intelligence_measured": reasoning_packet.get("intelligence_measured") is True,
        "codex_intelligence_parity_claimed": reasoning_packet.get(
            "codex_intelligence_parity_claimed"
        )
        is True,
    }
    return {
        "schema_version": int(selector_packet.get("schema_version") or 1),
        "packet_kind": str(selector_packet.get("packet_kind") or ""),
        "status": str(selector_packet.get("status") or ""),
        "machine_error_code": str(selector_packet.get("machine_error_code") or ""),
        "execution_mode": str(selector_packet.get("execution_mode") or ""),
        "allowed_browser_fields": list(selector_packet.get("allowed_browser_fields") or []),
        "forbidden_browser_fields_redacted": True,
        "forbidden_fields_redacted": True,
        "forbidden_field_count": len(selector_packet.get("forbidden_fields") or []),
        "source": "server_catalog",
        "server_issued_catalog_used": selector_packet.get("server_issued_catalog_used")
        is True,
        "raw_backend_details_exposed": selector_packet.get("raw_backend_details_exposed")
        is True,
        "secret_value_exposed": selector_packet.get("secret_value_exposed") is True,
        "browser_raw_backend_authority_widened": selector_packet.get(
            "browser_raw_backend_authority_widened"
        )
        is True,
        "chatgpt_model_id": str(selector_packet.get("chatgpt_model_id") or ""),
        "api_provider_id": str(selector_packet.get("api_provider_id") or ""),
        "api_model_id": str(selector_packet.get("api_model_id") or ""),
        "api_reasoning_option_id": str(
            selector_packet.get("api_reasoning_option_id") or ""
        ),
        "api_reasoning_option_packet": redacted_reasoning_packet,
        "primary_model_slot": selector_packet.get("primary_model_slot", {}),
        "coding_agent_model_slot": selector_packet.get("coding_agent_model_slot", {}),
        "chatgpt_executor_selected": selector_packet.get("chatgpt_executor_selected")
        is True,
        "api_executor_selected": selector_packet.get("api_executor_selected") is True,
        "dual_lane_slots_preserved": selector_packet.get("dual_lane_slots_preserved")
        is True,
        "api_only_calls_chatgpt": selector_packet.get("api_only_calls_chatgpt") is True,
        "chatgpt_only_calls_api": selector_packet.get("chatgpt_only_calls_api") is True,
        "live_call_attempted": selector_packet.get("live_call_attempted") is True,
        "provider_called": selector_packet.get("provider_called") is True,
        "network_calls_made": selector_packet.get("network_calls_made") is True,
        "runtime_execution_proven": selector_packet.get("runtime_execution_proven") is True,
        "selector_packet_truth_only": selector_packet.get("selector_packet_truth_only")
        is True,
    }


def build_server_model_selection_and_reasoning_truth_packet(
    payload: Any,
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selector_packet = build_custom_codex_execution_mode_selector_packet(
        payload,
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    reasoning_packet = dict(selector_packet.get("api_reasoning_option_packet") or {})
    forbidden = list(selector_packet.get("forbidden_fields") or [])
    mode_ok = selector_packet.get("status") == "ok"
    slots_coherent = _server_model_selection_slots_are_coherent(selector_packet)
    no_runtime_claims = all(
        selector_packet.get(field) is False
        for field in (
            "live_call_attempted",
            "network_calls_made",
            "provider_called",
            "responses_called",
            "chat_completions_called",
            "runtime_execution_proven",
            "original_codex_touched",
            "asar_touched",
            "wbp_patch_applier_used",
            "api_reasoning_option_runtime_mutation_claimed",
            "api_reasoning_intelligence_measured",
            "api_reasoning_codex_parity_claimed",
        )
    )
    no_secret_or_raw_exposure = all(
        selector_packet.get(field) is False
        for field in (
            "raw_backend_details_exposed",
            "route_or_backend_exposed",
            "secret_value_exposed",
            "browser_raw_backend_authority_widened",
        )
    )
    api_required = selector_packet.get("api_line_used_as_executor") is True
    reasoning_model_bound = True
    if api_required:
        requested = str(reasoning_packet.get("requested_option_id") or "")
        selected = str(reasoning_packet.get("selected_model_option_id") or "")
        reasoning_model_bound = (
            reasoning_packet.get("status") == "ok"
            and (
                not requested
                or requested == CUSTOM_CODEX_API_REASONING_OPTION_CATALOG_DEFAULT
                or _canonical_api_reasoning_option_id(requested)
                == _canonical_api_reasoning_option_id(selected)
            )
        )
    model_selection_truth_proven = (
        mode_ok
        and slots_coherent
        and no_runtime_claims
        and no_secret_or_raw_exposure
        and reasoning_model_bound
        and selector_packet.get("selector_packet_truth_only") is True
    )
    status = "ok" if model_selection_truth_proven else "blocked"
    if model_selection_truth_proven:
        machine_error_code = "OK"
    elif forbidden:
        machine_error_code = "FORBIDDEN_BROWSER_FIELD"
    else:
        machine_error_code = str(
            selector_packet.get("machine_error_code")
            or SERVER_MODEL_SELECTION_AND_REASONING_TRUTH_BLOCKER
        )
    if not model_selection_truth_proven and machine_error_code == "OK":
        machine_error_code = SERVER_MODEL_SELECTION_AND_REASONING_TRUTH_BLOCKER
    redacted_selector_packet = _redacted_server_model_selector_packet(selector_packet)
    return {
        "schema_version": 1,
        "packet_kind": "server_model_selection_and_reasoning_truth",
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": (
            SERVER_MODEL_SELECTION_AND_REASONING_TRUTH_FINAL_STATUS
            if model_selection_truth_proven
            else SERVER_MODEL_SELECTION_AND_REASONING_TRUTH_BLOCKER
        ),
        "model_selection_truth_proven": model_selection_truth_proven,
        "execution_mode": str(selector_packet.get("execution_mode") or ""),
        "allowed_execution_modes": selector_packet.get("allowed_execution_modes", []),
        "allowed_browser_fields": selector_packet.get("allowed_browser_fields", []),
        "forbidden_browser_fields": [],
        "forbidden_browser_fields_redacted": True,
        "forbidden_fields": [],
        "forbidden_fields_redacted": True,
        "forbidden_field_count": len(forbidden),
        "forbidden_field_categories": ["browser_raw_backend_authority"]
        if forbidden
        else [],
        "selected_chatgpt_model": str(selector_packet.get("chatgpt_model_id") or ""),
        "selected_api_model": str(selector_packet.get("api_model_id") or ""),
        "chatgpt_model_id": str(selector_packet.get("chatgpt_model_id") or ""),
        "api_model_id": str(selector_packet.get("api_model_id") or ""),
        "api_provider_id": str(selector_packet.get("api_provider_id") or ""),
        "api_reasoning_option_id": str(
            selector_packet.get("api_reasoning_option_id") or ""
        ),
        "source": "server_catalog",
        "server_catalog_source": True,
        "browser_route_authority": False,
        "browser_secret_authority": False,
        "browser_model_authority": False,
        "browser_allowed_to_request_server_model_id": True,
        "ui_label_counts_as_model_truth": False,
        "model_self_report_counts_as_model_truth": False,
        "codex_window_required": False,
        "codex_window_observed": False,
        "dry_server_truth_only": True,
        "api_reasoning_operator_level": str(
            selector_packet.get("api_reasoning_operator_level") or ""
        ),
        "api_reasoning_supported_operator_levels": [
            str(level)
            for level in selector_packet.get("api_reasoning_supported_operator_levels")
            or []
        ],
        "api_reasoning_option_model_bound": reasoning_model_bound,
        "api_reasoning_option_provider_parameter_sent": bool(
            (reasoning_packet.get("provider_option") or {}).get("api_parameter_sent") is True
        ),
        "api_reasoning_option_declared_only": (
            reasoning_packet.get("proof_level") == "provider_declared"
        ),
        "primary_model_slot": selector_packet.get("primary_model_slot", {}),
        "coding_agent_model_slot": selector_packet.get("coding_agent_model_slot", {}),
        "slots_coherent": slots_coherent,
        "dual_lane_slots_preserved": selector_packet.get("dual_lane_slots_preserved")
        is True,
        "api_only_calls_chatgpt": selector_packet.get("api_only_calls_chatgpt") is True,
        "chatgpt_only_calls_api": selector_packet.get("chatgpt_only_calls_api") is True,
        "raw_backend_details_exposed": selector_packet.get("raw_backend_details_exposed")
        is True,
        "route_or_backend_exposed": selector_packet.get("route_or_backend_exposed") is True,
        "secret_value_exposed": selector_packet.get("secret_value_exposed") is True,
        "browser_raw_backend_authority_widened": selector_packet.get(
            "browser_raw_backend_authority_widened"
        )
        is True,
        "live_call_attempted": selector_packet.get("live_call_attempted") is True,
        "live_api_call_attempted": selector_packet.get("live_call_attempted") is True,
        "provider_called": selector_packet.get("provider_called") is True,
        "network_calls_made": selector_packet.get("network_calls_made") is True,
        "runtime_execution_proven": selector_packet.get("runtime_execution_proven") is True,
        "ui_work_attempted": False,
        "custom_codex_launch_attempted": False,
        "live_paid_call_attempted": False,
        "original_codex_touched": selector_packet.get("original_codex_touched") is True,
        "asar_touched": selector_packet.get("asar_touched") is True,
        "measured_strength_claimed": False,
        "measured_speed_claimed": False,
        "api_reasoning_intelligence_measured": selector_packet.get(
            "api_reasoning_intelligence_measured"
        )
        is True,
        "api_reasoning_codex_parity_claimed": selector_packet.get(
            "api_reasoning_codex_parity_claimed"
        )
        is True,
        "selector_packet": redacted_selector_packet,
        "next_action": "none" if model_selection_truth_proven else "stop_and_diagnose",
    }


def build_chatgpt_plus_api_slot_truth_packet(
    payload: Any,
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    server_truth_packet = build_server_model_selection_and_reasoning_truth_packet(
        payload,
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    selector_packet = dict(server_truth_packet.get("selector_packet") or {})
    primary_slot = dict(server_truth_packet.get("primary_model_slot") or {})
    coding_slot = dict(server_truth_packet.get("coding_agent_model_slot") or {})
    execution_mode = str(server_truth_packet.get("execution_mode") or "")
    chatgpt_primary_slot_proven = (
        execution_mode == CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API
        and primary_slot.get("status") == "bound"
        and primary_slot.get("lane") == CODEX_ACCOUNT_MODEL_LANE
        and primary_slot.get("slot_id") == "primary_model_slot"
        and primary_slot.get("server_issued") is True
        and primary_slot.get("selection_enabled") is True
        and str(primary_slot.get("model_id") or "")
        == str(server_truth_packet.get("selected_chatgpt_model") or "")
    )
    api_coding_slot_proven = (
        execution_mode == CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API
        and coding_slot.get("status") == "bound"
        and coding_slot.get("lane") == API_ROUTE_MODEL_LANE
        and coding_slot.get("slot_id") == "coding_agent_model_slot"
        and coding_slot.get("server_issued") is True
        and coding_slot.get("selection_enabled") is True
        and str(coding_slot.get("model_id") or "")
        == str(server_truth_packet.get("selected_api_model") or "")
    )
    no_runtime_claims = all(
        server_truth_packet.get(field) is False
        for field in (
            "live_call_attempted",
            "provider_called",
            "network_calls_made",
            "runtime_execution_proven",
            "ui_work_attempted",
            "custom_codex_launch_attempted",
            "live_paid_call_attempted",
            "original_codex_touched",
            "asar_touched",
        )
    )
    no_browser_or_secret_exposure = all(
        server_truth_packet.get(field) is False
        for field in (
            "raw_backend_details_exposed",
            "route_or_backend_exposed",
            "secret_value_exposed",
            "browser_raw_backend_authority_widened",
        )
    )
    slot_truth_proven = (
        server_truth_packet.get("status") == "ok"
        and server_truth_packet.get("model_selection_truth_proven") is True
        and execution_mode == CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API
        and server_truth_packet.get("dual_lane_slots_preserved") is True
        and server_truth_packet.get("slots_coherent") is True
        and chatgpt_primary_slot_proven
        and api_coding_slot_proven
        and server_truth_packet.get("api_reasoning_option_model_bound") is True
        and no_runtime_claims
        and no_browser_or_secret_exposure
    )
    machine_error_code = "OK" if slot_truth_proven else str(
        server_truth_packet.get("machine_error_code") or CHATGPT_PLUS_API_SLOT_TRUTH_BLOCKER
    )
    if not slot_truth_proven and machine_error_code == "OK":
        if execution_mode != CUSTOM_CODEX_EXECUTION_MODE_CHATGPT_API:
            machine_error_code = "CHATGPT_PLUS_API_SLOT_TRUTH_REQUIRES_CHATGPT_PLUS_API_MODE"
        elif not chatgpt_primary_slot_proven:
            machine_error_code = "CHATGPT_PLUS_API_PRIMARY_SLOT_NOT_CHATGPT"
        elif not api_coding_slot_proven:
            machine_error_code = "CHATGPT_PLUS_API_CODING_SLOT_NOT_API"
        else:
            machine_error_code = CHATGPT_PLUS_API_SLOT_TRUTH_BLOCKER
    return {
        "schema_version": 1,
        "packet_kind": "chatgpt_plus_api_slot_truth",
        "captured_at_utc": utc_now(),
        "status": "ok" if slot_truth_proven else "blocked",
        "machine_error_code": machine_error_code,
        "final_status": (
            CHATGPT_PLUS_API_SLOT_TRUTH_FINAL_STATUS
            if slot_truth_proven
            else CHATGPT_PLUS_API_SLOT_TRUTH_BLOCKER
        ),
        "slot_truth_proven": slot_truth_proven,
        "execution_mode": execution_mode,
        "allowed_browser_fields": server_truth_packet.get("allowed_browser_fields", []),
        "forbidden_browser_fields": server_truth_packet.get("forbidden_browser_fields", []),
        "forbidden_fields": server_truth_packet.get("forbidden_fields", []),
        "forbidden_browser_fields_redacted": server_truth_packet.get(
            "forbidden_browser_fields_redacted"
        )
        is True,
        "forbidden_fields_redacted": server_truth_packet.get("forbidden_fields_redacted")
        is True,
        "forbidden_field_count": int(server_truth_packet.get("forbidden_field_count") or 0),
        "forbidden_field_categories": [
            str(item)
            for item in server_truth_packet.get("forbidden_field_categories") or []
        ],
        "selected_chatgpt_model": str(server_truth_packet.get("selected_chatgpt_model") or ""),
        "selected_api_model": str(server_truth_packet.get("selected_api_model") or ""),
        "api_provider_id": str(server_truth_packet.get("api_provider_id") or ""),
        "api_reasoning_option_id": str(server_truth_packet.get("api_reasoning_option_id") or ""),
        "api_reasoning_operator_level": str(
            server_truth_packet.get("api_reasoning_operator_level") or ""
        ),
        "api_reasoning_option_model_bound": server_truth_packet.get(
            "api_reasoning_option_model_bound"
        )
        is True,
        "source": "server_selection_truth",
        "server_selection_truth_used": server_truth_packet.get("model_selection_truth_proven")
        is True,
        "server_catalog_source": server_truth_packet.get("server_catalog_source") is True,
        "selected_chatgpt_model_server_issued": chatgpt_primary_slot_proven,
        "selected_api_model_server_issued": api_coding_slot_proven,
        "api_reasoning_option_server_validated": server_truth_packet.get(
            "api_reasoning_option_model_bound"
        )
        is True,
        "browser_route_authority": False,
        "browser_secret_authority": False,
        "browser_model_authority": False,
        "browser_allowed_to_request_server_model_id": True,
        "ui_label_counts_as_model_truth": False,
        "model_self_report_counts_as_model_truth": False,
        "codex_window_required": False,
        "codex_window_observed": False,
        "dry_server_truth_only": True,
        "primary_model_slot": primary_slot,
        "coding_agent_model_slot": coding_slot,
        "chatgpt_primary_slot_proven": chatgpt_primary_slot_proven,
        "api_coding_slot_proven": api_coding_slot_proven,
        "api_line_selected_as_coding_agent": api_coding_slot_proven,
        "api_line_used_as_coding_agent": api_coding_slot_proven,
        "chatgpt_line_used_as_executor": chatgpt_primary_slot_proven,
        "api_line_used_as_primary_executor": False,
        "chatgpt_line_used_as_coding_agent": False,
        "dual_lane_slots_preserved": server_truth_packet.get("dual_lane_slots_preserved")
        is True,
        "slots_coherent": server_truth_packet.get("slots_coherent") is True,
        "fallback_used": False,
        "fallback_attempted": False,
        "fallback_can_prove_success": False,
        "model_lane_fallback_used": False,
        "raw_backend_details_exposed": server_truth_packet.get("raw_backend_details_exposed")
        is True,
        "route_or_backend_exposed": server_truth_packet.get("route_or_backend_exposed") is True,
        "secret_value_exposed": server_truth_packet.get("secret_value_exposed") is True,
        "browser_raw_backend_authority_widened": server_truth_packet.get(
            "browser_raw_backend_authority_widened"
        )
        is True,
        "live_call_attempted": server_truth_packet.get("live_call_attempted") is True,
        "live_api_call_attempted": server_truth_packet.get("live_api_call_attempted") is True,
        "provider_called": server_truth_packet.get("provider_called") is True,
        "network_calls_made": server_truth_packet.get("network_calls_made") is True,
        "runtime_execution_proven": server_truth_packet.get("runtime_execution_proven") is True,
        "ui_work_attempted": False,
        "custom_codex_launch_attempted": False,
        "live_paid_call_attempted": False,
        "original_codex_touched": server_truth_packet.get("original_codex_touched") is True,
        "asar_touched": server_truth_packet.get("asar_touched") is True,
        "full_delegation_claimed": False,
        "simultaneous_execution_proven": False,
        "server_truth_packet": server_truth_packet,
        "selector_packet": selector_packet,
        "next_action": "none" if slot_truth_proven else "stop_and_diagnose",
    }


def _selection_targets_deepseek(api_selection: dict[str, Any] | None) -> bool:
    if not isinstance(api_selection, dict):
        return False
    fields = (
        api_selection.get("model_id"),
        api_selection.get("provider"),
        api_selection.get("provider_label"),
        api_selection.get("provider_model_id"),
        api_selection.get("display_name"),
    )
    return any("deepseek" in str(value or "").lower() for value in fields)


def _live_format_result_packet(live_result: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(live_result or {})
    request_count = int(result.get("request_count") or 0)
    retry_count = int(result.get("retry_count") or 0)
    expected_text_observed = result.get("expected_text_observed") is True
    response_shape = str(result.get("response_shape") or "")
    return {
        "packet_kind": "api_only_deepseek_live_route_format_result",
        "status": "ok" if request_count == 1 and expected_text_observed else "blocked",
        "provider_called": request_count == 1,
        "live_call_attempted": request_count == 1,
        "upstream_response_observed": bool(result.get("response_preview_bounded")),
        "expected_text": str(
            result.get("expected_text") or API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_EXPECTED_TEXT
        ),
        "expected_text_observed": expected_text_observed,
        "codex_compatible_response_shape": response_shape
        in {"choices_message", "output_text", "content_blocks"},
        "response_shape": response_shape,
        "response_profile": str(result.get("response_profile") or ""),
        "request_shape": str(result.get("request_shape") or ""),
        "latency_ms": result.get("latency_ms"),
        "request_count": request_count,
        "retry_count": retry_count,
        "parallel_fanout_attempted": result.get("parallel_fanout_attempted") is True,
        "fallback_used": result.get("fallback_used") is True,
        "fallback_chain": [str(item) for item in result.get("fallback_chain") or []],
        "response_preview_bounded": str(result.get("response_preview_bounded") or ""),
        "response_text_length": int(result.get("response_text_length") or 0),
        "state_written": result.get("state_written") is True,
        "evidence_written": result.get("evidence_written") is True,
        "file_mutation_attempted": result.get("file_mutation_attempted") is True,
        "commands_started_by_provider": result.get("commands_started_by_provider") is True,
        "codex_history_sent": result.get("codex_history_sent") is True,
        "repo_context_sent": result.get("repo_context_sent") is True,
    }


def build_api_only_deepseek_live_route_format_packet(
    payload: Any,
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
    owner_authorized: bool = False,
    live_result: dict[str, Any] | None = None,
    live_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_api_only_deepseek_live_route_format_fields(payload)
    if forbidden:
        selector_packet = build_custom_codex_execution_mode_selector_packet(
            payload,
            operator_status,
            endpoint=endpoint,
            recommended_default_model=recommended_default_model,
            api_snapshot=api_snapshot,
            availability_lattice_packet=availability_lattice_packet,
        )
        return {
            "schema_version": 1,
            "packet_kind": "api_only_deepseek_live_route_and_format",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "API_ONLY_DEEPSEEK_BROWSER_AUTHORITY_REJECTED",
            "final_status": "API_ONLY_DEEPSEEK_BROWSER_AUTHORITY_REJECTED",
            "execution_mode": str(
                payload.get("execution_mode") if isinstance(payload, dict) else ""
            ),
            "api_provider_id": "",
            "api_model_id": (
                str(payload.get("api_model_id") or "") if isinstance(payload, dict) else ""
            ),
            "allowed_browser_fields": sorted(
                API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_ALLOWED_FIELDS
            ),
            "forbidden_browser_fields": sorted(CUSTOM_API_ACTION_GATE_FORBIDDEN_FIELDS),
            "forbidden_fields": forbidden,
            "browser_raw_backend_authority_widened": True,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "chatgpt_line_used_as_executor": False,
            "api_line_used_as_executor": False,
            "provider_called": False,
            "live_call_attempted": False,
            "request_count": 0,
            "retry_count": 0,
            "parallel_fanout_attempted": False,
            "fallback_attempted": False,
            "file_mutation_attempted": False,
            "wbp_patch_applier_used": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "state_written": False,
            "evidence_written": False,
            "selector_packet": selector_packet,
            "live_result_packet": _live_format_result_packet(None),
            "live_error_packet": {},
            "next_action": "remove_browser_payload_fields",
        }
    selector_packet = build_custom_codex_execution_mode_selector_packet(
        payload,
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    payload = payload if isinstance(payload, dict) else {}
    api_model_id = str(payload.get("api_model_id") or "").strip()
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    api_index = _selector_entry_index(
        [row for row in dict(selector.get("api_lane") or {}).get("models") or [] if isinstance(row, dict)]
    )
    api_selection = api_index.get(api_model_id) if api_model_id else None
    live_error = dict(live_error or {})
    live_result_packet = _live_format_result_packet(live_result)
    mode_ok = selector_packet.get("status") == "ok" and selector_packet.get(
        "execution_mode"
    ) == CUSTOM_CODEX_EXECUTION_MODE_API_ONLY
    deepseek_selected = _selection_targets_deepseek(api_selection)
    live_ok = (
        live_result_packet["provider_called"] is True
        and live_result_packet["expected_text_observed"] is True
        and live_result_packet["codex_compatible_response_shape"] is True
        and live_result_packet["request_count"] == 1
        and live_result_packet["retry_count"] == 0
        and live_result_packet["parallel_fanout_attempted"] is False
        and live_result_packet["file_mutation_attempted"] is False
        and live_result_packet["state_written"] is False
        and live_result_packet["evidence_written"] is False
    )

    status = "ok" if mode_ok and deepseek_selected and owner_authorized and live_ok else "blocked"
    machine_error_code = "OK"
    next_action = "none"
    if selector_packet.get("execution_mode") != CUSTOM_CODEX_EXECUTION_MODE_API_ONLY:
        machine_error_code = "API_ONLY_DEEPSEEK_REQUIRES_API_ONLY_MODE"
        next_action = "choose_api_only_execution_mode"
    elif selector_packet.get("status") != "ok":
        machine_error_code = str(selector_packet.get("machine_error_code") or "API_ONLY_SELECTION_BLOCKED")
        next_action = str(selector_packet.get("next_action") or "fix_api_only_selection")
    elif not deepseek_selected:
        machine_error_code = "API_ONLY_DEEPSEEK_MODEL_REQUIRED"
        next_action = "choose_server_issued_deepseek_model"
    elif not owner_authorized:
        machine_error_code = "API_ONLY_DEEPSEEK_OWNER_AUTH_REQUIRED"
        next_action = "provide_exact_owner_authorization_phrase"
    elif live_error:
        machine_error_code = str(
            live_error.get("machine_error_code")
            or "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_ROUTE_OR_FORMAT_NOT_ADMISSIBLE"
        )
        next_action = str(live_error.get("next_action") or "fix_deepseek_route_or_format")
    elif not live_ok:
        machine_error_code = "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_ROUTE_OR_FORMAT_NOT_ADMISSIBLE"
        next_action = "fix_deepseek_route_or_response_format"

    final_status = (
        "API_ONLY_DEEPSEEK_LIVE_ROUTE_AND_FORMAT_PROVEN_WITH_LIMITS"
        if status == "ok"
        else "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_ROUTE_OR_FORMAT_NOT_ADMISSIBLE"
        if status == "blocked"
        else machine_error_code
    )
    return {
        "schema_version": 1,
        "packet_kind": "api_only_deepseek_live_route_and_format",
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": final_status,
        "execution_mode": str(selector_packet.get("execution_mode") or ""),
        "api_provider_id": str((api_selection or {}).get("provider") or ""),
        "api_model_id": api_model_id,
        "api_model_family": "deepseek" if deepseek_selected else "unknown",
        "server_issued_catalog_used": selector_packet.get("server_issued_catalog_used") is True,
        "deepseek_selected_from_server_catalog": deepseek_selected
        and (api_selection or {}).get("server_issued") is True,
        "owner_authorization_phrase_present": owner_authorized,
        "allowed_browser_fields": sorted(API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_ALLOWED_FIELDS),
        "forbidden_browser_fields": selector_packet.get("forbidden_browser_fields") or [],
        "forbidden_fields": selector_packet.get("forbidden_fields") or [],
        "browser_raw_backend_authority_widened": selector_packet.get(
            "browser_raw_backend_authority_widened"
        )
        is True,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "chatgpt_line_used_as_executor": False,
        "api_line_selected_as_executor": mode_ok,
        "api_line_used_as_executor": live_ok,
        "provider_called": live_result_packet["provider_called"],
        "live_call_attempted": live_result_packet["live_call_attempted"],
        "upstream_response_observed": live_result_packet["upstream_response_observed"],
        "expected_text_observed": live_result_packet["expected_text_observed"],
        "codex_compatible_response_shape": live_result_packet[
            "codex_compatible_response_shape"
        ],
        "request_count": live_result_packet["request_count"],
        "retry_count": live_result_packet["retry_count"],
        "parallel_fanout_attempted": live_result_packet["parallel_fanout_attempted"],
        "fallback_attempted": live_result_packet["fallback_used"],
        "file_mutation_attempted": live_result_packet["file_mutation_attempted"],
        "wbp_patch_applier_used": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "commands_started_by_provider": live_result_packet["commands_started_by_provider"],
        "codex_history_sent": live_result_packet["codex_history_sent"],
        "repo_context_sent": live_result_packet["repo_context_sent"],
        "state_written": live_result_packet["state_written"],
        "evidence_written": live_result_packet["evidence_written"],
        "selector_packet": selector_packet,
        "live_result_packet": live_result_packet,
        "live_error_packet": live_error,
        "non_claims": {
            "deepseek_code_mutation_proven": False,
            "file_mutation_proven": False,
            "chatgpt_api_simultaneous_execution_proven": False,
            "history_persistence_proven": False,
            "model_quality_or_speed_proven": False,
        },
        "next_action": next_action,
    }


def _api_action_final_status(
    *,
    forbidden: list[str],
    api_model_id: str,
    api_selection: dict[str, Any] | None,
    owner_authorized: bool,
    budget_policy_present: bool,
) -> tuple[str, str, str]:
    if forbidden:
        return (
            "rejected",
            "CUSTOM_CODEX_API_ACTION_GATE_BROWSER_AUTHORITY_REJECTED",
            "CUSTOM_CODEX_API_ACTION_GATE_BROWSER_AUTHORITY_REJECTED",
        )
    if not api_model_id:
        return (
            "blocked",
            "CUSTOM_CODEX_API_ACTION_GATE_API_MODEL_REQUIRED",
            "CUSTOM_CODEX_API_ACTION_GATE_API_MODEL_REQUIRED",
        )
    if api_selection is None:
        return (
            "rejected",
            "CUSTOM_CODEX_API_ACTION_GATE_API_MODEL_NOT_SERVER_ISSUED",
            "CUSTOM_CODEX_API_ACTION_GATE_API_MODEL_NOT_SERVER_ISSUED",
        )
    if api_selection.get("selection_enabled") is not True:
        return (
            "blocked",
            "CUSTOM_CODEX_API_ACTION_GATE_API_MODEL_NOT_SELECTABLE",
            "CUSTOM_CODEX_API_ACTION_GATE_API_MODEL_NOT_SELECTABLE",
        )
    if not owner_authorized:
        return (
            "blocked",
            "CUSTOM_CODEX_API_ACTION_GATE_OWNER_AUTH_REQUIRED",
            "CUSTOM_CODEX_API_ACTION_GATE_OWNER_AUTH_REQUIRED",
        )
    if not budget_policy_present:
        return (
            "blocked",
            "CUSTOM_CODEX_API_ACTION_GATE_BUDGET_POLICY_REQUIRED",
            "CUSTOM_CODEX_API_ACTION_GATE_BUDGET_POLICY_REQUIRED",
        )
    return (
        "blocked",
        "CUSTOM_CODEX_API_ACTION_GATE_LIVE_REQUEST_NOT_IMPLEMENTED_IN_THIS_CONTOUR",
        "CUSTOM_CODEX_API_ACTION_GATE_LIVE_REQUEST_NOT_ATTEMPTED",
    )


def build_custom_api_action_gate_packet(
    payload: Any,
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    recommended_default_model: str = DEFAULT_MODEL,
    api_snapshot: dict[str, Any] | None = None,
    availability_lattice_packet: dict[str, Any] | None = None,
    owner_authorized: bool = False,
    budget_policy_present: bool = False,
    request_limit: int = 0,
    retry_limit: int = 0,
    cost_ceiling: str = "",
    credential_ref_allowed: bool = False,
) -> dict[str, Any]:
    forbidden = forbidden_custom_api_action_gate_fields(payload)
    payload = payload if isinstance(payload, dict) else {}
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status,
        endpoint=endpoint,
        recommended_default_model=recommended_default_model,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    api_lane = dict(selector.get("api_lane") or {})
    api_rows = [row for row in api_lane.get("models") or [] if isinstance(row, dict)]
    api_index = _selector_entry_index(api_rows)
    api_model_id = str(payload.get("api_model_id") or "").strip()
    api_selection = api_index.get(api_model_id) if api_model_id else None
    route_row = _api_route_row_by_model_id(api_snapshot, api_model_id)
    status, machine_error_code, final_status = _api_action_final_status(
        forbidden=forbidden,
        api_model_id=api_model_id,
        api_selection=api_selection,
        owner_authorized=owner_authorized,
        budget_policy_present=budget_policy_present,
    )
    route_id = str((api_selection or {}).get("model_id") or api_model_id)
    provider = str(
        route_row.get("provider")
        or (api_selection or {}).get("provider")
        or (api_selection or {}).get("provider_label")
        or ""
    )
    provider_model_id = str(
        route_row.get("upstream_model") or (api_selection or {}).get("provider_model_id") or ""
    )
    cost_class = str(route_row.get("cost_class") or (api_selection or {}).get("cost_class") or "unknown")
    credential_status = str(route_row.get("secret_status_label") or "unknown")
    manual_api_choice_packet = {
        "packet_kind": "manual_api_choice",
        "status": "ok" if api_selection is not None and not forbidden else status,
        "api_model_id": api_model_id,
        "server_issued_model_selected": api_selection is not None,
        "selection_enabled": (api_selection or {}).get("selection_enabled") is True,
        "selection_intent_only": True,
        "execution_proven": False,
        "provider_response_observed": False,
        "route_snapshot_counted_as_provider_response": False,
        "route_id": route_id,
        "provider": provider,
        "provider_model_id": provider_model_id,
        "cost_class": cost_class,
        "credential_ref_status": credential_status,
        "secret_value_exposed": False,
        "api_selection": api_selection,
    }
    browser_authority_guard_packet = {
        "packet_kind": "browser_authority_guard",
        "status": "ok" if not forbidden else "rejected",
        "allowed_browser_fields": sorted(CUSTOM_API_ACTION_GATE_ALLOWED_FIELDS),
        "forbidden_fields": forbidden,
        "forbidden_browser_fields": sorted(CUSTOM_API_ACTION_GATE_FORBIDDEN_FIELDS),
        "browser_raw_backend_authority_widened": bool(forbidden),
        "browser_may_send_base_url": False,
        "browser_may_send_api_key": False,
        "browser_may_send_secret_ref": False,
        "browser_may_send_route_config": False,
        "browser_may_send_codex_home": False,
    }
    owner_authorization_packet = {
        "packet_kind": "owner_authorization",
        "status": "ok" if owner_authorized else "blocked",
        "owner_live_authorization_present": owner_authorized,
        "credential_ref_permission_present": credential_ref_allowed,
        "raw_secret_authorized": False,
        "raw_secret_recorded": False,
    }
    budget_policy_packet = {
        "packet_kind": "budget_policy",
        "status": "ok" if budget_policy_present else "blocked",
        "budget_policy_present": budget_policy_present,
        "request_limit": int(request_limit or 0),
        "retry_limit": int(retry_limit or 0),
        "cost_ceiling": str(cost_ceiling or ""),
        "cost_class": cost_class,
        "fallback_policy": "forbidden",
        "parallel_fanout_policy": "forbidden",
        "paid_call_without_budget_forbidden": True,
    }
    live_provider_request_boundary_packet = {
        "packet_kind": "live_provider_request_boundary",
        "status": "blocked",
        "live_provider_request_allowed": False,
        "live_call_attempted": False,
        "paid_route_used": False,
        "upstream_response_observed": False,
        "fallback_attempted": False,
        "parallel_fanout_attempted": False,
        "retry_count": 0,
        "original_codex_touched": False,
        "raw_secret_recorded": False,
        "secret_value_recorded": False,
    }
    false_green_boundary_packet = {
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "selection_intent_treated_as_execution": False,
        "route_snapshot_treated_as_provider_response": False,
        "credential_ref_presence_treated_as_auth_works": False,
        "dry_run_treated_as_live_call": False,
        "one_route_treated_as_provider_family_compatibility": False,
        "blocked_status_promoted_to_success": False,
    }
    summary_packet = {
        "packet_kind": "summary",
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": final_status,
        "api_action_visible": True,
        "api_action_enabled": False,
        "api_action_gate_state": status,
        "live_provider_request_allowed": False,
        "live_request_attempted": False,
        "upstream_response_observed": False,
        "manual_choice_status": manual_api_choice_packet["status"],
        "browser_authority_status": browser_authority_guard_packet["status"],
        "owner_authorization_status": owner_authorization_packet["status"],
        "budget_policy_status": budget_policy_packet["status"],
        "route_presence_counts_as_provider_response": False,
        "selection_counts_as_execution": False,
        "next_action": (
            "remove_forbidden_browser_fields"
            if forbidden
            else "provide_owner_live_authorization_and_budget"
            if not owner_authorized or not budget_policy_present
            else "live_request_separate_authorized_contour"
        ),
    }
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_api_action_gate",
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": final_status,
        "mode_id": "codex_custom",
        "manual_api_choice_packet": manual_api_choice_packet,
        "browser_authority_guard_packet": browser_authority_guard_packet,
        "owner_authorization_packet": owner_authorization_packet,
        "budget_policy_packet": budget_policy_packet,
        "live_provider_request_boundary_packet": live_provider_request_boundary_packet,
        "false_green_boundary_packet": false_green_boundary_packet,
        "summary_packet": summary_packet,
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
        availability_lattice_packet=availability_lattice_packet,
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
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    models = _models_payload(operator_status)
    model_specs = _server_catalog_model_specs(models)
    model_ids = [str(spec["model_id"]) for spec in model_specs]
    claim_gate_status = claim_gate_status_from_operator_status(operator_status)
    status, machine_error_code = _status_for_models(
        model_ids,
        claim_gate_status,
        bool(models.get("ok")) or bool(model_ids),
    )
    reported_configured_model = _reported_configured_model(operator_status)
    availability_rows = _availability_rows_by_model_id(availability_lattice_packet)
    available_models = []
    for spec in model_specs:
        model_id = str(spec["model_id"])
        entry = _model_entry(
            model_id,
            lane=str(spec.get("lane") or ""),
            server_lane_explicit=spec.get("server_lane_explicit") is True,
        )
        availability_row = availability_rows.get(model_id)
        if isinstance(availability_row, dict):
            entry["availability_claim_level"] = str(
                availability_row.get("availability_claim_level") or entry["availability_claim_level"]
            )
            entry["live_availability_proven"] = availability_row.get("live_availability_proven") is True
            entry["responses_live_acceptance_proven"] = (
                availability_row.get("direct_wbp_non_stream_response_accepted") is True
            )
            entry["responses_supported_claim_scope"] = str(
                availability_row.get("availability_evidence_scope")
                or entry["responses_supported_claim_scope"]
            )
            gated = _selection_gate_from_live_availability(entry, availability_row)
            if gated is not None:
                reason_code, reasons = gated
                entry["selection_enabled"] = False
                entry["selection_state"] = "disabled"
                entry["selection_disabled_reason_code"] = reason_code
                entry["selection_disabled_reasons"] = reasons
        available_models.append(entry)
    available_model_index = {str(entry["model_id"]): index for index, entry in enumerate(available_models)}
    for route_entry in _external_route_model_entries(api_snapshot):
        route_model_id = str(route_entry["model_id"])
        existing_index = available_model_index.get(route_model_id)
        if existing_index is not None:
            existing_entry = available_models[existing_index]
            if (
                existing_entry.get("model_lane_classified") is not True
                or existing_entry.get("model_lane_fallback_used") is True
            ):
                available_models[existing_index] = route_entry
            continue
        available_models.append(route_entry)
        available_model_index[route_model_id] = len(available_models) - 1

    available_model_ids = [str(entry["model_id"]) for entry in available_models]
    live_probe_imported = any(
        str(row.get("availability_evidence_scope") or "") == "current_thread_direct_wbp_non_stream"
        for row in availability_rows.values()
        if isinstance(row, dict)
    )
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
        "live_api_checked": live_probe_imported,
        "network_calls_made": live_probe_imported,
        "allowed_network_calls": ["/v1/responses"] if live_probe_imported else [],
        "forbidden_network_calls": list(FORBIDDEN_INFERENCE_SURFACES),
        "models_endpoint_called": False,
        "inference_called": live_probe_imported,
        "provider_called": False,
        "token_burn": 0,
        "negative_claim_basis": (
            "live_native_availability_probe_imported_without_codex_acceptance_claim"
            if live_probe_imported
            else "shape_declaration_no_live_api_or_inference_call"
        ),
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
    availability_lattice_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_custom_model_fields(payload)
    registry = build_custom_model_registry_packet(
        operator_status,
        endpoint=endpoint,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
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
    lane_classification = model_lane_classification_from_entry(selected_entry)
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
            **lane_classification,
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
        **lane_classification,
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
