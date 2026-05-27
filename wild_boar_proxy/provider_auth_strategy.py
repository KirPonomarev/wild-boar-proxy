# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider auth strategy packets for Codex -> WBP integration."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .token_command import TOKEN_OUTPUT_SHAPE, TOKEN_SCOPE, TOKEN_SOURCE_KIND


AUTH_STRATEGY_SCHEMA_VERSION = 1
PREFERRED_STRATEGY = "auth.command"
BOUNDED_BEARER_FALLBACK = "bounded_local_bearer"
FILE_AUTH_FALLBACK = "file_auth_separate_contour"
AUTH_COMMAND_OUTPUT_SHAPE = TOKEN_OUTPUT_SHAPE
AUTH_COMMAND_SCOPE = TOKEN_SCOPE
AUTH_COMMAND_SOURCE_KIND = TOKEN_SOURCE_KIND
AUTH_SOURCE_CLASSES = {
    "server_owned",
    "operator_configured",
    "ambient_host",
    "browser_supplied",
    "remote_client_supplied",
    "unknown",
}
AUTH_FORBIDDEN_BROWSER_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "auth_command",
    "account",
    "account_id",
    "provider_account",
    "credential",
    "credential_ref",
    "secret_ref",
    "command",
    "path",
    "provider",
    "model_provider",
    "model",
    "base_url",
    "wire_api",
    "experimental_bearer_token",
    "openai_api_key",
    "http_proxy",
    "https_proxy",
    "all_proxy",
}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
)
EXPERIMENTAL_BEARER_VALUE_PATTERN = re.compile(
    r"experimental_bearer_token\s*=\s*\"([^\"]+)\"",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact_provider_auth_text(text: str) -> str:
    redacted = text
    redacted = re.sub(
        r"(experimental_bearer_token\s*=\s*)\"[^\"]+\"",
        r'\1"<redacted>"',
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<redacted-token>", redacted)
    redacted = re.sub(
        r"Bearer\s+[A-Za-z0-9._-]{8,}",
        "Bearer <redacted-token>",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(OPENAI_API_KEY\s*[:=]\s*)[^\s\",}]{8,}",
        r"\1<redacted-token>",
        redacted,
        flags=re.IGNORECASE,
    )
    return redacted


def provider_auth_text_has_secret(text: str) -> bool:
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return True
    for match in EXPERIMENTAL_BEARER_VALUE_PATTERN.finditer(text):
        value = match.group(1).strip()
        if value and value != "<redacted>":
            return True
    return False


def forbidden_auth_browser_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in AUTH_FORBIDDEN_BROWSER_FIELDS:
                findings.append(key_path)
            findings.extend(forbidden_auth_browser_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_auth_browser_fields(value, f"{prefix}[{index}]"))
    return findings


def classify_native_config_auth_surface(
    config_text: str,
    *,
    explicit_bearer_contract: bool = False,
) -> dict[str, Any]:
    has_bearer = "experimental_bearer_token" in config_text
    has_auth_command = "[model_providers.wbp.auth]" in config_text and "command" in config_text
    redacted_config = redact_provider_auth_text(config_text)
    raw_secret_after_redaction = provider_auth_text_has_secret(redacted_config)
    failed_checks: list[str] = []
    if has_bearer and not explicit_bearer_contract:
        failed_checks.append("experimental_bearer_token_without_explicit_contract")
    if raw_secret_after_redaction:
        failed_checks.append("redacted_config_still_contains_secret")
    return {
        "packet_kind": "native_config_auth_surface",
        "classification_scope": "auth_surface_only",
        "native_launch_attempted": False,
        "native_safety_proven": False,
        "native_routing_proven": False,
        "native_ux_proven": False,
        "model_availability_proven": False,
        "account_pool_validity_proven": False,
        "auth_command_configured": has_auth_command,
        "experimental_bearer_token_configured": has_bearer,
        "bounded_bearer_contract_explicit": explicit_bearer_contract,
        "bounded_bearer_is_temporary_fallback": has_bearer and explicit_bearer_contract,
        "silent_bearer_fallback_allowed": False,
        "raw_secret_in_input_config": provider_auth_text_has_secret(config_text),
        "redacted_config": redacted_config,
        "raw_secret_after_redaction": raw_secret_after_redaction,
        "failed_checks": failed_checks,
        "status": "blocked" if failed_checks else "ok",
    }


def build_provider_auth_strategy_packet(
    *,
    auth_command_path: str | Path,
    native_config_text: str = "",
    explicit_bearer_contract: bool = False,
    browser_payload: Any | None = None,
    remote_payload: Any | None = None,
) -> dict[str, Any]:
    auth_command_path_text = str(Path(auth_command_path).expanduser())
    native_surface = classify_native_config_auth_surface(
        native_config_text,
        explicit_bearer_contract=explicit_bearer_contract,
    )
    forbidden_browser_fields = forbidden_auth_browser_fields(browser_payload or {})
    forbidden_remote_fields = forbidden_auth_browser_fields(remote_payload or {})
    failed_checks = list(native_surface["failed_checks"])
    if forbidden_browser_fields:
        failed_checks.append("browser_auth_authority_detected")
    if forbidden_remote_fields:
        failed_checks.append("remote_auth_authority_detected")
    return {
        "schema_version": AUTH_STRATEGY_SCHEMA_VERSION,
        "packet_kind": "provider_auth_strategy",
        "captured_at_utc": utc_now(),
        "status": "blocked" if failed_checks else "ok",
        "machine_error_code": "AUTH_STRATEGY_BLOCKED" if failed_checks else "OK",
        "target_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "selected_strategy": PREFERRED_STRATEGY,
        "preferred_strategy": PREFERRED_STRATEGY,
        "preferred_strategy_reason": "server_owned_local_token_command",
        "auth_command": {
            "path": auth_command_path_text,
            "server_owned_path": True,
            "output_shape": AUTH_COMMAND_OUTPUT_SHAPE,
            "token_source_kind": AUTH_COMMAND_SOURCE_KIND,
            "scope": AUTH_COMMAND_SCOPE,
            "plain_token_stdout": True,
            "json_access_token_stdout": False,
            "raw_upstream_secret": False,
            "browser_supplied": False,
        },
        "fallbacks": {
            BOUNDED_BEARER_FALLBACK: {
                "allowed": explicit_bearer_contract,
                "temporary": True,
                "requires_explicit_contract": True,
                "silent_fallback_allowed": False,
                "raw_value_redacted": True,
                "config_file_exposure_classified": bool(native_config_text),
            },
            FILE_AUTH_FALLBACK: {
                "allowed_in_this_contour": False,
                "requires_separate_contour": True,
                "can_satisfy_proxy_auth_contract": False,
            },
        },
        "native_config_auth_surface": native_surface,
        "browser_authority": {
            "browser_payload_checked": browser_payload is not None,
            "forbidden_fields": forbidden_browser_fields,
            "browser_can_supply_token": False,
            "browser_can_supply_auth_command": False,
            "browser_can_supply_provider": False,
            "browser_can_supply_model": False,
            "browser_authority_blocked": not forbidden_browser_fields,
        },
        "remote_authority": {
            "remote_payload_checked": remote_payload is not None,
            "forbidden_fields": forbidden_remote_fields,
            "remote_can_supply_token": False,
            "remote_can_supply_auth_command": False,
            "remote_can_supply_provider": False,
            "remote_can_supply_model": False,
            "remote_authority_blocked": not forbidden_remote_fields,
        },
        "runtime_dependency": {
            "current_codex_auth_json_dependency": False,
            "current_codex_auth_json_inspection_only_allowed": True,
            "file_auth_used_in_this_contour": False,
            "env_auth_used_in_this_contour": False,
            "ambient_host_auth_used_in_this_contour": False,
        },
        "claims": {
            "native_launch_attempted": False,
            "native_safety_proven": False,
            "native_routing_proven": False,
            "native_ux_proven": False,
            "model_availability_proven": False,
            "account_pool_validity_proven": False,
            "direct_egress_absence_proven": False,
            "final_e2e_proven": False,
        },
        "allowed_claims": [
            "auth.command_preferred_and_contract_classified",
            "bounded_bearer_fallback_classified_with_limits",
            "FILE_AUTH_not_used_in_this_contour",
            "native_config_auth_surface_classified",
            "native_launch_not_attempted",
            "model_availability_not_proven_by_this_contour",
            "account_pool_validity_not_proven_by_this_contour",
        ],
        "forbidden_claims": [
            "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_PROVEN",
            "native_safety_proven",
            "native_routing_proven",
            "native_UX_proven",
            "all_models_work",
            "GPT-5.5_works",
            "direct_egress_absent",
            "account_pool_valid",
            "experimental_bearer_token_preferred_strategy",
            "FILE_AUTH_equals_PROXY_AUTH",
            "selected_auth_equals_live_used_auth_without_trace",
        ],
        "failed_checks": failed_checks,
    }


def build_provider_auth_source_inventory_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    auth_command = (
        provider_auth_strategy_packet.get("auth_command")
        if isinstance(provider_auth_strategy_packet.get("auth_command"), dict)
        else {}
    )
    fallbacks = (
        provider_auth_strategy_packet.get("fallbacks")
        if isinstance(provider_auth_strategy_packet.get("fallbacks"), dict)
        else {}
    )
    bounded_bearer = (
        fallbacks.get(BOUNDED_BEARER_FALLBACK)
        if isinstance(fallbacks.get(BOUNDED_BEARER_FALLBACK), dict)
        else {}
    )
    file_auth = (
        fallbacks.get(FILE_AUTH_FALLBACK)
        if isinstance(fallbacks.get(FILE_AUTH_FALLBACK), dict)
        else {}
    )
    runtime_dependency = (
        provider_auth_strategy_packet.get("runtime_dependency")
        if isinstance(provider_auth_strategy_packet.get("runtime_dependency"), dict)
        else {}
    )
    rows = [
        {
            "source_id": PREFERRED_STRATEGY,
            "source_class": "server_owned",
            "available_by_contract": bool(auth_command.get("path")),
            "selected_by_contract": provider_auth_strategy_packet.get("selected_strategy")
            == PREFERRED_STRATEGY,
            "allowed_in_this_contour": True,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
        {
            "source_id": BOUNDED_BEARER_FALLBACK,
            "source_class": "server_owned",
            "available_by_contract": bounded_bearer.get("allowed") is True,
            "selected_by_contract": False,
            "allowed_in_this_contour": bounded_bearer.get("allowed") is True,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
        {
            "source_id": FILE_AUTH_FALLBACK,
            "source_class": "ambient_host",
            "available_by_contract": False,
            "selected_by_contract": False,
            "allowed_in_this_contour": file_auth.get("allowed_in_this_contour") is True,
            "requires_separate_contour": file_auth.get("requires_separate_contour") is True,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
        {
            "source_id": "env_openai_api_key",
            "source_class": "ambient_host",
            "available_by_contract": False,
            "selected_by_contract": False,
            "allowed_in_this_contour": runtime_dependency.get("env_auth_used_in_this_contour")
            is True,
            "forbidden_by_default": True,
            "requires_separate_contour": True,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
        {
            "source_id": "current_codex_auth_json",
            "source_class": "ambient_host",
            "available_by_contract": False,
            "selected_by_contract": False,
            "allowed_in_this_contour": runtime_dependency.get("current_codex_auth_json_dependency")
            is True,
            "forbidden_by_default": True,
            "requires_separate_contour": True,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
        {
            "source_id": "browser_supplied_auth",
            "source_class": "browser_supplied",
            "available_by_contract": False,
            "selected_by_contract": False,
            "allowed_in_this_contour": False,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
        {
            "source_id": "remote_client_supplied_auth",
            "source_class": "remote_client_supplied",
            "available_by_contract": False,
            "selected_by_contract": False,
            "allowed_in_this_contour": False,
            "runtime_usage_proven": False,
            "raw_secret_recorded": False,
        },
    ]
    unknown_rows = [row for row in rows if row["source_class"] not in AUTH_SOURCE_CLASSES]
    forbidden_selected = [
        row
        for row in rows
        if row["source_class"] in {"ambient_host", "browser_supplied", "remote_client_supplied"}
        and row.get("selected_by_contract") is True
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_source_inventory",
        "status": "ok" if not unknown_rows and not forbidden_selected else "blocked",
        "source_rows": rows,
        "source_count": len(rows),
        "unknown_source_count": len(unknown_rows),
        "forbidden_source_selected_count": len(forbidden_selected),
        "all_auth_sources_classified": not unknown_rows,
        "runtime_usage_proven": False,
        "raw_secret_recorded": False,
    }


def build_provider_auth_precedence_discovery_packet(
    provider_auth_strategy_packet: dict[str, Any],
    decision_matrix_packet: dict[str, Any],
) -> dict[str, Any]:
    strategy_rows = list(decision_matrix_packet.get("strategy_rows") or [])
    ambiguous_rows = [
        row
        for row in strategy_rows
        if row.get("selected") is not True and not row.get("rejection_reason")
    ]
    selected_rows = [row for row in strategy_rows if row.get("selected") is True]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_precedence_discovery",
        "status": "ok" if len(selected_rows) == 1 and not ambiguous_rows else "blocked",
        "discovery_method": "contract_packet_and_decision_matrix_inspection",
        "current_behavior_live_observed": False,
        "runtime_trace_present": False,
        "selected_strategy_from_contract": provider_auth_strategy_packet.get(
            "selected_strategy", ""
        ),
        "selected_strategy_count": len(selected_rows),
        "ambiguous_unselected_strategy_count": len(ambiguous_rows),
        "current_behavior_separated_from_declared_precedence": True,
        "selected_auth_claimed_as_live_used_auth": False,
    }


def build_provider_auth_precedence_contract_packet(
    provider_auth_strategy_packet: dict[str, Any],
    decision_matrix_packet: dict[str, Any],
) -> dict[str, Any]:
    selected_strategy = str(provider_auth_strategy_packet.get("selected_strategy") or "")
    failed_checks: list[str] = []
    if selected_strategy != PREFERRED_STRATEGY:
        failed_checks.append("selected_strategy_not_auth_command")
    if decision_matrix_packet.get("silent_fallback_detected") is not False:
        failed_checks.append("silent_fallback_detected")
    if decision_matrix_packet.get("all_unselected_strategies_have_rejection_reasons") is not True:
        failed_checks.append("unselected_strategy_missing_rejection_reason")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_precedence_contract",
        "status": "ok" if not failed_checks else "blocked",
        "declared_precedence_order": [
            PREFERRED_STRATEGY,
            BOUNDED_BEARER_FALLBACK,
            FILE_AUTH_FALLBACK,
            "env_openai_api_key",
            "current_codex_auth_json",
            "browser_supplied_auth",
            "remote_client_supplied_auth",
        ],
        "selected_strategy": selected_strategy,
        "selected_strategy_is_contract_only": True,
        "selected_strategy_runtime_usage_proven": False,
        "silent_fallback_allowed": False,
        "ambient_fallback_forbidden_by_default": True,
        "failed_checks": failed_checks,
    }


def build_provider_auth_fallback_matrix_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    fallbacks = (
        provider_auth_strategy_packet.get("fallbacks")
        if isinstance(provider_auth_strategy_packet.get("fallbacks"), dict)
        else {}
    )
    file_auth = (
        fallbacks.get(FILE_AUTH_FALLBACK)
        if isinstance(fallbacks.get(FILE_AUTH_FALLBACK), dict)
        else {}
    )
    bounded_bearer = (
        fallbacks.get(BOUNDED_BEARER_FALLBACK)
        if isinstance(fallbacks.get(BOUNDED_BEARER_FALLBACK), dict)
        else {}
    )
    rows = [
        {
            "fallback_id": BOUNDED_BEARER_FALLBACK,
            "allowed": bounded_bearer.get("allowed") is True,
            "requires_explicit_contract": bounded_bearer.get("requires_explicit_contract")
            is True,
            "silent_fallback_allowed": False,
            "raw_secret_recorded": False,
        },
        {
            "fallback_id": FILE_AUTH_FALLBACK,
            "allowed": file_auth.get("allowed_in_this_contour") is True,
            "requires_explicit_contract": True,
            "requires_separate_contour": file_auth.get("requires_separate_contour") is True,
            "silent_fallback_allowed": False,
            "raw_secret_recorded": False,
        },
        {
            "fallback_id": "env_openai_api_key",
            "allowed": False,
            "requires_explicit_contract": True,
            "requires_separate_contour": True,
            "silent_fallback_allowed": False,
            "raw_secret_recorded": False,
        },
        {
            "fallback_id": "current_codex_auth_json",
            "allowed": False,
            "requires_explicit_contract": True,
            "requires_separate_contour": True,
            "silent_fallback_allowed": False,
            "raw_secret_recorded": False,
        },
    ]
    bad = [
        row
        for row in rows
        if row.get("silent_fallback_allowed") is not False
        or (
            row["fallback_id"] in {FILE_AUTH_FALLBACK, "env_openai_api_key", "current_codex_auth_json"}
            and row.get("allowed") is True
        )
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_fallback_matrix",
        "status": "ok" if not bad else "blocked",
        "fallback_rows": rows,
        "ambient_fallback_forbidden_by_default": True,
        "silent_fallback_detected": bool(bad),
    }


def build_provider_auth_account_boundary_packet(
    *,
    account_validation_observed: bool = False,
    account_session_auth_selected: bool = False,
    provider_adapter_auth_selected: bool = False,
) -> dict[str, Any]:
    confused = account_session_auth_selected and provider_adapter_auth_selected
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_account_boundary",
        "status": "ok" if not confused else "blocked",
        "account_validation_observed": account_validation_observed,
        "account_session_auth_selected": account_session_auth_selected,
        "provider_adapter_auth_selected": provider_adapter_auth_selected,
        "account_session_auth_equals_provider_adapter_auth": False,
        "account_validation_counts_as_model_availability": False,
        "account_validation_counts_as_provider_compatibility": False,
        "reserve_account_promoted": False,
        "runtime_route_claimed": False,
    }


def build_provider_auth_runtime_claim_limits_packet(
    provider_auth_strategy_packet: dict[str, Any],
    *,
    runtime_trace_present: bool = False,
    selected_auth_live_used: bool = False,
) -> dict[str, Any]:
    invalid_live_claim = selected_auth_live_used and not runtime_trace_present
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_runtime_claim_limits",
        "status": "blocked" if invalid_live_claim else "ok",
        "selected_strategy": provider_auth_strategy_packet.get("selected_strategy", ""),
        "selected_auth_source_classified": True,
        "runtime_trace_present": runtime_trace_present,
        "selected_auth_live_used": selected_auth_live_used,
        "selected_auth_claimed_as_live_used_without_trace": invalid_live_claim,
        "provider_request_proven": False,
        "route_proof_claimed": False,
        "model_availability_claimed": False,
        "native_launch_claimed": False,
    }


def build_provider_auth_secret_boundary_packet(
    provider_auth_strategy_packet: dict[str, Any],
    auth_token_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    serialized = json.dumps(
        {
            "provider_auth_strategy_packet": provider_auth_strategy_packet,
            "auth_token_boundary_packet": auth_token_boundary_packet,
        },
        sort_keys=True,
    )
    raw_secret_found = provider_auth_text_has_secret(serialized)
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_secret_boundary",
        "status": "blocked" if raw_secret_found else "ok",
        "raw_secret_found": raw_secret_found,
        "raw_upstream_secret_in_evidence": False,
        "auth_header_recorded": False,
        "auth_command_output_recorded_raw": False,
        "browser_secret_intake": False,
        "remote_secret_intake": False,
    }


def build_provider_auth_browser_authority_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    authority = build_authority_boundary_packet(provider_auth_strategy_packet)
    return {
        **authority,
        "packet_kind": "provider_auth_browser_authority",
        "browser_client_supplied_token_authority": False,
        "browser_client_supplied_path_authority": False,
        "browser_client_supplied_provider_authority": False,
        "browser_client_supplied_account_authority": False,
        "remote_client_supplied_token_authority": False,
        "remote_client_supplied_path_authority": False,
        "remote_client_supplied_provider_authority": False,
        "remote_client_supplied_account_authority": False,
    }


def build_auth_strategy_decision_matrix(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    auth_command = (
        provider_auth_strategy_packet.get("auth_command")
        if isinstance(provider_auth_strategy_packet.get("auth_command"), dict)
        else {}
    )
    fallbacks = (
        provider_auth_strategy_packet.get("fallbacks")
        if isinstance(provider_auth_strategy_packet.get("fallbacks"), dict)
        else {}
    )
    bounded_bearer = (
        fallbacks.get(BOUNDED_BEARER_FALLBACK)
        if isinstance(fallbacks.get(BOUNDED_BEARER_FALLBACK), dict)
        else {}
    )
    file_auth = (
        fallbacks.get(FILE_AUTH_FALLBACK)
        if isinstance(fallbacks.get(FILE_AUTH_FALLBACK), dict)
        else {}
    )
    runtime_dependency = (
        provider_auth_strategy_packet.get("runtime_dependency")
        if isinstance(provider_auth_strategy_packet.get("runtime_dependency"), dict)
        else {}
    )
    browser_authority = (
        provider_auth_strategy_packet.get("browser_authority")
        if isinstance(provider_auth_strategy_packet.get("browser_authority"), dict)
        else {}
    )
    remote_authority = (
        provider_auth_strategy_packet.get("remote_authority")
        if isinstance(provider_auth_strategy_packet.get("remote_authority"), dict)
        else {}
    )
    native_surface = (
        provider_auth_strategy_packet.get("native_config_auth_surface")
        if isinstance(provider_auth_strategy_packet.get("native_config_auth_surface"), dict)
        else {}
    )
    selected_strategy = str(provider_auth_strategy_packet.get("selected_strategy") or "")
    silent_fallback_detected = (
        bounded_bearer.get("silent_fallback_allowed") is not False
        or (
            native_surface.get("experimental_bearer_token_configured") is True
            and native_surface.get("bounded_bearer_contract_explicit") is not True
        )
        or file_auth.get("allowed_in_this_contour") is True
    )
    failed_checks = list(provider_auth_strategy_packet.get("failed_checks") or [])
    if selected_strategy != PREFERRED_STRATEGY:
        failed_checks.append("selected_strategy_not_auth_command")
    if silent_fallback_detected:
        failed_checks.append("silent_fallback_detected")
    if runtime_dependency.get("current_codex_auth_json_dependency") is not False:
        failed_checks.append("current_codex_auth_json_dependency_detected")
    if browser_authority.get("browser_authority_blocked") is not True:
        failed_checks.append("browser_authority_not_blocked")
    if remote_authority.get("remote_authority_blocked") is not True:
        failed_checks.append("remote_authority_not_blocked")
    strategy_rows = [
        {
            "strategy_id": PREFERRED_STRATEGY,
            "available": bool(auth_command.get("path")),
            "selected": selected_strategy == PREFERRED_STRATEGY,
            "rejected": selected_strategy != PREFERRED_STRATEGY,
            "selection_reason": provider_auth_strategy_packet.get(
                "preferred_strategy_reason", ""
            ),
            "rejection_reason": "",
            "required_contract_present": bool(auth_command.get("path")),
            "runtime_secret_source": auth_command.get("token_source_kind", ""),
            "token_locality": auth_command.get("scope", ""),
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": auth_command.get("raw_upstream_secret") is True,
            "evidence_redaction_policy": "secret_value_not_recorded",
        },
        {
            "strategy_id": BOUNDED_BEARER_FALLBACK,
            "available": native_surface.get("experimental_bearer_token_configured") is True,
            "selected": selected_strategy == BOUNDED_BEARER_FALLBACK,
            "rejected": selected_strategy != BOUNDED_BEARER_FALLBACK,
            "selection_reason": "",
            "rejection_reason": "not_selected_preferred_auth_command_available",
            "required_contract_present": bounded_bearer.get("allowed") is True,
            "runtime_secret_source": "bounded_local_proxy_token",
            "token_locality": "local_wbp_listener_only",
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": False,
            "evidence_redaction_policy": "raw_value_redacted",
        },
        {
            "strategy_id": FILE_AUTH_FALLBACK,
            "available": False,
            "selected": selected_strategy == FILE_AUTH_FALLBACK,
            "rejected": True,
            "selection_reason": "",
            "rejection_reason": "separate_fallback_contour_required",
            "required_contract_present": False,
            "runtime_secret_source": "not_used",
            "token_locality": "not_used",
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": False,
            "evidence_redaction_policy": "not_applicable",
        },
        {
            "strategy_id": "experimental_bearer_token",
            "available": native_surface.get("experimental_bearer_token_configured") is True,
            "selected": False,
            "rejected": True,
            "selection_reason": "",
            "rejection_reason": "not_preferred_requires_explicit_contract",
            "required_contract_present": bounded_bearer.get("allowed") is True,
            "runtime_secret_source": "bounded_local_proxy_token_if_contract_present",
            "token_locality": "local_wbp_listener_only",
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": False,
            "evidence_redaction_policy": "raw_value_redacted",
        },
        {
            "strategy_id": "current_codex_auth_json",
            "available": False,
            "selected": False,
            "rejected": True,
            "selection_reason": "",
            "rejection_reason": "inspection_only_not_runtime_input",
            "required_contract_present": False,
            "runtime_secret_source": "forbidden",
            "token_locality": "not_used",
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": False,
            "evidence_redaction_policy": "not_recorded",
        },
        {
            "strategy_id": "browser_supplied_auth",
            "available": bool(browser_authority.get("forbidden_fields")),
            "selected": False,
            "rejected": True,
            "selection_reason": "",
            "rejection_reason": "browser_authority_forbidden",
            "required_contract_present": False,
            "runtime_secret_source": "forbidden",
            "token_locality": "not_used",
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": False,
            "evidence_redaction_policy": "not_recorded",
        },
        {
            "strategy_id": "remote_client_supplied_auth",
            "available": bool(remote_authority.get("forbidden_fields")),
            "selected": False,
            "rejected": True,
            "selection_reason": "",
            "rejection_reason": "remote_client_authority_forbidden",
            "required_contract_present": False,
            "runtime_secret_source": "forbidden",
            "token_locality": "not_used",
            "browser_authority_allowed": False,
            "remote_authority_allowed": False,
            "raw_upstream_secret_exposed": False,
            "evidence_redaction_policy": "not_recorded",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "auth_strategy_decision_matrix",
        "status": "blocked" if failed_checks else "ok",
        "auth_command_supported": True,
        "auth_command_available": bool(auth_command.get("path")),
        "auth_command_selected": selected_strategy == PREFERRED_STRATEGY,
        "auth_command_output_format": auth_command.get("output_shape", ""),
        "auth_command_token_scope": auth_command.get("scope", ""),
        "auth_command_secret_redacted": auth_command.get("raw_upstream_secret") is False,
        "bounded_bearer_available": native_surface.get("experimental_bearer_token_configured")
        is True,
        "bounded_bearer_selected": selected_strategy == BOUNDED_BEARER_FALLBACK,
        "bounded_bearer_scope": "owner_local_listener",
        "bounded_bearer_locality": "local_wbp_listener_only",
        "bounded_bearer_redaction": bounded_bearer.get("raw_value_redacted") is True,
        "bounded_bearer_rejection_reason": (
            "not_selected_preferred_auth_command_available"
            if selected_strategy == PREFERRED_STRATEGY
            else ""
        ),
        "file_auth_available": False,
        "file_auth_selected": selected_strategy == FILE_AUTH_FALLBACK,
        "file_auth_rejection_reason": "deferred_to_separate_contour",
        "file_auth_deferred_to_separate_contour": file_auth.get("requires_separate_contour")
        is True,
        "current_codex_auth_json_used": runtime_dependency.get(
            "current_codex_auth_json_dependency"
        )
        is True,
        "browser_authority_used": browser_authority.get("browser_authority_blocked")
        is not True,
        "remote_authority_used": remote_authority.get("remote_authority_blocked")
        is not True,
        "browser_authority_detected": browser_authority.get("browser_authority_blocked")
        is not True,
        "remote_client_authority_detected": remote_authority.get(
            "remote_authority_blocked"
        )
        is not True,
        "current_codex_auth_runtime_dependency_detected": runtime_dependency.get(
            "current_codex_auth_json_dependency"
        )
        is True,
        "silent_fallback_detected": silent_fallback_detected,
        "selected_strategy": selected_strategy,
        "selection_reason": provider_auth_strategy_packet.get(
            "preferred_strategy_reason", ""
        ),
        "rejection_reason_per_unselected_strategy": {
            BOUNDED_BEARER_FALLBACK: "fallback_only_requires_explicit_contract_not_selected",
            FILE_AUTH_FALLBACK: "separate_fallback_contour_required",
            "experimental_bearer_token": "not_preferred_requires_explicit_contract",
            "current_codex_auth_json": "inspection_only_not_runtime_input",
            "browser_supplied_auth": "browser_authority_forbidden",
            "remote_client_supplied_auth": "remote_client_authority_forbidden",
        },
        "rejected_strategies": [
            row["strategy_id"] for row in strategy_rows if row.get("selected") is not True
        ],
        "all_unselected_strategies_have_rejection_reasons": all(
            bool(row.get("rejection_reason"))
            for row in strategy_rows
            if row.get("selected") is not True
        ),
        "strategy_rows": strategy_rows,
        "failed_checks": sorted(set(str(item) for item in failed_checks)),
    }


def build_auth_command_output_format_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    auth_command = (
        provider_auth_strategy_packet.get("auth_command")
        if isinstance(provider_auth_strategy_packet.get("auth_command"), dict)
        else {}
    )
    output_shape = str(auth_command.get("output_shape") or "")
    plain_token_stdout = auth_command.get("plain_token_stdout") is True
    json_access_token_stdout = auth_command.get("json_access_token_stdout") is True
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "auth_command_output_format",
        "status": "ok" if output_shape == AUTH_COMMAND_OUTPUT_SHAPE else "blocked",
        "auth_command_path": auth_command.get("path", ""),
        "output_shape": output_shape,
        "expected_output_shape": AUTH_COMMAND_OUTPUT_SHAPE,
        "plain_token_stdout": plain_token_stdout,
        "json_access_token_stdout": json_access_token_stdout,
        "raw_upstream_secret": auth_command.get("raw_upstream_secret") is True,
        "browser_supplied": auth_command.get("browser_supplied") is True,
        "native_live_invocation_attempted": False,
        "secret_value_emitted_in_packet": False,
    }


def build_file_auth_fallback_deferred_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    fallbacks = (
        provider_auth_strategy_packet.get("fallbacks")
        if isinstance(provider_auth_strategy_packet.get("fallbacks"), dict)
        else {}
    )
    file_auth = (
        fallbacks.get(FILE_AUTH_FALLBACK)
        if isinstance(fallbacks.get(FILE_AUTH_FALLBACK), dict)
        else {}
    )
    deferred = (
        file_auth.get("allowed_in_this_contour") is False
        and file_auth.get("requires_separate_contour") is True
        and file_auth.get("can_satisfy_proxy_auth_contract") is False
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "file_auth_fallback_deferred",
        "status": "ok" if deferred else "blocked",
        "file_auth_available": False,
        "file_auth_selected": False,
        "allowed_in_this_contour": file_auth.get("allowed_in_this_contour") is True,
        "requires_separate_contour": file_auth.get("requires_separate_contour") is True,
        "can_satisfy_proxy_auth_contract": file_auth.get("can_satisfy_proxy_auth_contract")
        is True,
        "file_auth_silently_replaced_proxy_auth": False,
        "current_codex_auth_json_used": False,
        "copy_current_auth_json_allowed": False,
        "symlink_auth_json_allowed": False,
        "deferred_reason": "FILE_AUTH is a separate fallback contour and cannot satisfy PROXY_AUTH by implication.",
    }


def build_file_auth_non_substitution_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    deferred = build_file_auth_fallback_deferred_packet(provider_auth_strategy_packet)
    return {
        **deferred,
        "packet_kind": "file_auth_non_substitution",
        "file_auth_equals_proxy_auth": False,
        "file_auth_may_satisfy_proxy_auth": False,
        "file_auth_selected_as_provider_auth": False,
    }


def build_file_auth_fallback_exclusion_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    deferred = build_file_auth_fallback_deferred_packet(provider_auth_strategy_packet)
    return {
        **deferred,
        "packet_kind": "file_auth_fallback_exclusion",
        "status": deferred.get("status", "blocked"),
        "file_auth_excluded_from_proxy_auth_contour": True,
        "file_auth_silent_substitution_allowed": False,
        "file_auth_requires_separate_contour": deferred.get(
            "requires_separate_contour"
        )
        is True,
    }


def build_current_codex_auth_independence_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    runtime_dependency = (
        provider_auth_strategy_packet.get("runtime_dependency")
        if isinstance(provider_auth_strategy_packet.get("runtime_dependency"), dict)
        else {}
    )
    dependency = runtime_dependency.get("current_codex_auth_json_dependency") is True
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "current_codex_auth_independence",
        "status": "blocked" if dependency else "ok",
        "current_codex_auth_json_execution_dependency": dependency,
        "current_codex_auth_json_inspection_only_allowed": runtime_dependency.get(
            "current_codex_auth_json_inspection_only_allowed"
        )
        is True,
        "file_auth_used_in_this_contour": runtime_dependency.get(
            "file_auth_used_in_this_contour"
        )
        is True,
        "current_codex_auth_json_read_as_runtime_input": False,
        "current_codex_auth_json_copied": False,
        "current_codex_auth_json_symlinked": False,
        "native_filesystem_safety_claimed": False,
        "keychain_safety_claimed": False,
        "original_profile_safety_claimed": False,
    }


def build_authority_boundary_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    browser_authority = (
        provider_auth_strategy_packet.get("browser_authority")
        if isinstance(provider_auth_strategy_packet.get("browser_authority"), dict)
        else {}
    )
    remote_authority = (
        provider_auth_strategy_packet.get("remote_authority")
        if isinstance(provider_auth_strategy_packet.get("remote_authority"), dict)
        else {}
    )
    forbidden_browser_fields = list(browser_authority.get("forbidden_fields") or [])
    forbidden_remote_fields = list(remote_authority.get("forbidden_fields") or [])
    blocked = (
        browser_authority.get("browser_authority_blocked") is True
        and remote_authority.get("remote_authority_blocked") is True
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "authority_boundary",
        "status": "ok" if blocked else "blocked",
        "authority_filter_method": "recursive_key_name_match",
        "semantic_alias_coverage_proven": False,
        "authority_filter_limit": (
            "classification covers explicit forbidden field names and nested keys; "
            "semantic aliases require separate policy-engine proof"
        ),
        "browser_allowed_request_shape": [
            "server-approved profile",
            "server-approved alias",
            "server-approved task tag",
        ],
        "browser_forbidden_authority_fields": sorted(AUTH_FORBIDDEN_BROWSER_FIELDS),
        "browser_detected_forbidden_fields": forbidden_browser_fields,
        "remote_detected_forbidden_fields": forbidden_remote_fields,
        "browser_can_supply_token_path_model_provider_authority": False,
        "remote_can_supply_token_path_model_provider_authority": False,
        "server_owns_provider_endpoint_selection": True,
        "server_owns_token_command_path": True,
        "server_owns_bearer_fallback_admission": True,
        "server_owns_account_selection": True,
        "server_owns_model_route_selection": True,
        "server_owns_secret_redaction": True,
        "server_owns_trace_classification": True,
    }


def build_no_ambient_authority_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    runtime_dependency = (
        provider_auth_strategy_packet.get("runtime_dependency")
        if isinstance(provider_auth_strategy_packet.get("runtime_dependency"), dict)
        else {}
    )
    browser_authority = (
        provider_auth_strategy_packet.get("browser_authority")
        if isinstance(provider_auth_strategy_packet.get("browser_authority"), dict)
        else {}
    )
    remote_authority = (
        provider_auth_strategy_packet.get("remote_authority")
        if isinstance(provider_auth_strategy_packet.get("remote_authority"), dict)
        else {}
    )
    checks = [
        {
            "name": "current_codex_auth_json_not_runtime_input",
            "passed": runtime_dependency.get("current_codex_auth_json_dependency")
            is False,
        },
        {
            "name": "env_auth_not_runtime_input",
            "passed": runtime_dependency.get("env_auth_used_in_this_contour") is False,
        },
        {
            "name": "ambient_host_auth_not_runtime_input",
            "passed": runtime_dependency.get("ambient_host_auth_used_in_this_contour")
            is False,
        },
        {
            "name": "browser_authority_blocked",
            "passed": browser_authority.get("browser_authority_blocked") is True,
        },
        {
            "name": "remote_authority_blocked",
            "passed": remote_authority.get("remote_authority_blocked") is True,
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "no_ambient_authority",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "openai_api_key_env_required": False,
        "openai_api_key_env_allowed_in_this_contour": False,
        "http_proxy_env_required": False,
        "https_proxy_env_required": False,
        "all_proxy_env_required": False,
        "current_codex_auth_json_runtime_input": False,
        "env_auth_runtime_input": False,
        "ambient_host_auth_runtime_input": False,
        "browser_token_path_model_provider_authority": False,
        "remote_token_path_model_provider_authority": False,
    }


def build_secret_source_confusion_guard_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    auth_command = (
        provider_auth_strategy_packet.get("auth_command")
        if isinstance(provider_auth_strategy_packet.get("auth_command"), dict)
        else {}
    )
    fallbacks = (
        provider_auth_strategy_packet.get("fallbacks")
        if isinstance(provider_auth_strategy_packet.get("fallbacks"), dict)
        else {}
    )
    file_auth = (
        fallbacks.get(FILE_AUTH_FALLBACK)
        if isinstance(fallbacks.get(FILE_AUTH_FALLBACK), dict)
        else {}
    )
    remote_authority = (
        provider_auth_strategy_packet.get("remote_authority")
        if isinstance(provider_auth_strategy_packet.get("remote_authority"), dict)
        else {}
    )
    checks = [
        {
            "name": "local_wbp_bearer_not_upstream_provider_token",
            "passed": auth_command.get("scope") == AUTH_COMMAND_SCOPE,
        },
        {
            "name": "auth_command_output_not_raw_upstream_secret",
            "passed": auth_command.get("raw_upstream_secret") is False,
        },
        {
            "name": "file_auth_token_not_proxy_auth_token",
            "passed": file_auth.get("can_satisfy_proxy_auth_contract") is False,
        },
        {
            "name": "current_codex_auth_json_not_execution_input",
            "passed": provider_auth_strategy_packet.get("runtime_dependency", {}).get(
                "current_codex_auth_json_dependency"
            )
            is False,
        },
        {
            "name": "browser_hidden_field_not_server_authority",
            "passed": provider_auth_strategy_packet.get("browser_authority", {}).get(
                "browser_authority_blocked"
            )
            is True,
        },
        {
            "name": "remote_client_field_not_server_authority",
            "passed": remote_authority.get("remote_authority_blocked") is True,
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "secret_source_confusion_guard",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "local_wbp_bearer_equals_upstream_provider_token": False,
        "auth_command_output_equals_raw_upstream_secret": False,
        "file_auth_token_equals_proxy_auth_token": False,
        "current_codex_auth_json_allowed_execution_input": False,
        "browser_hidden_field_allowed_authority": False,
        "remote_client_allowed_authority": False,
        "model_catalog_allowed_auth_authority": False,
    }


def build_auth_token_boundary_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    auth_command = (
        provider_auth_strategy_packet.get("auth_command")
        if isinstance(provider_auth_strategy_packet.get("auth_command"), dict)
        else {}
    )
    native_surface = (
        provider_auth_strategy_packet.get("native_config_auth_surface")
        if isinstance(provider_auth_strategy_packet.get("native_config_auth_surface"), dict)
        else {}
    )
    checks = [
        {
            "name": "wbp_local_token_not_upstream_secret",
            "passed": auth_command.get("raw_upstream_secret") is False,
        },
        {
            "name": "auth_command_scope_local",
            "passed": auth_command.get("scope") == AUTH_COMMAND_SCOPE,
        },
        {
            "name": "redacted_config_has_no_secret",
            "passed": native_surface.get("raw_secret_after_redaction") is False,
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "auth_token_boundary",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "wbp_local_bearer_token_is_upstream_provider_secret": False,
        "auth_command_output_is_raw_upstream_secret": False,
        "upstream_provider_secret_in_codex_config": False,
        "upstream_provider_secret_in_browser_payload": False,
        "upstream_provider_secret_in_remote_payload": False,
        "upstream_provider_secret_in_evidence": False,
        "auth_command_output_recorded_raw": False,
    }


def build_auth_strategy_false_green_audit(
    *,
    provider_auth_strategy_packet: dict[str, Any],
    decision_matrix_packet: dict[str, Any],
    file_auth_fallback_deferred_packet: dict[str, Any],
    current_codex_auth_independence_packet: dict[str, Any],
    secret_source_confusion_guard_packet: dict[str, Any],
    runtime_claim_limits_packet: dict[str, Any] | None = None,
    account_boundary_packet: dict[str, Any] | None = None,
    fallback_matrix_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claims = (
        provider_auth_strategy_packet.get("claims")
        if isinstance(provider_auth_strategy_packet.get("claims"), dict)
        else {}
    )
    forbidden_claims_present = any(
        claims.get(key) is True
        for key in (
            "native_launch_attempted",
            "native_safety_proven",
            "native_routing_proven",
            "native_ux_proven",
            "model_availability_proven",
            "account_pool_validity_proven",
            "direct_egress_absence_proven",
            "final_e2e_proven",
        )
    )
    runtime_claim_limits_packet = runtime_claim_limits_packet or {}
    account_boundary_packet = account_boundary_packet or {}
    fallback_matrix_packet = fallback_matrix_packet or {}
    checks = [
        {
            "name": "auth_command_selected",
            "passed": decision_matrix_packet.get("auth_command_selected") is True,
        },
        {
            "name": "silent_fallback_absent",
            "passed": decision_matrix_packet.get("silent_fallback_detected") is False,
        },
        {
            "name": "file_auth_deferred",
            "passed": file_auth_fallback_deferred_packet.get("status") == "ok",
        },
        {
            "name": "current_codex_auth_independent",
            "passed": current_codex_auth_independence_packet.get("status") == "ok",
        },
        {
            "name": "secret_source_not_confused",
            "passed": secret_source_confusion_guard_packet.get("status") == "ok",
        },
        {
            "name": "no_cross_layer_claims",
            "passed": not forbidden_claims_present,
        },
        {
            "name": "selected_auth_not_live_used_without_trace",
            "passed": runtime_claim_limits_packet.get(
                "selected_auth_claimed_as_live_used_without_trace"
            )
            is not True,
        },
        {
            "name": "account_validation_not_model_availability",
            "passed": account_boundary_packet.get(
                "account_validation_counts_as_model_availability"
            )
            is not True,
        },
        {
            "name": "ambient_fallback_forbidden_by_default",
            "passed": fallback_matrix_packet.get(
                "ambient_fallback_forbidden_by_default", True
            )
            is True
            and fallback_matrix_packet.get("silent_fallback_detected", False) is False,
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "auth_strategy_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "allowed_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
        "native_launch_claimed": claims.get("native_launch_attempted") is True,
        "model_availability_claimed": claims.get("model_availability_proven") is True,
        "account_pool_validity_claimed": claims.get("account_pool_validity_proven") is True,
        "direct_egress_claimed": claims.get("direct_egress_absence_proven") is True,
        "file_auth_used": file_auth_fallback_deferred_packet.get("allowed_in_this_contour")
        is True,
        "experimental_bearer_preferred": decision_matrix_packet.get(
            "bounded_bearer_selected"
        )
        is True,
        "remote_authority_used": decision_matrix_packet.get("remote_authority_used")
        is True,
        "selected_auth_live_used_without_trace_claimed": runtime_claim_limits_packet.get(
            "selected_auth_claimed_as_live_used_without_trace"
        )
        is True,
        "account_validation_as_model_availability_claimed": account_boundary_packet.get(
            "account_validation_counts_as_model_availability"
        )
        is True,
    }


def validate_provider_auth_strategy_packet(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("preferred_strategy") != PREFERRED_STRATEGY:
        failures.append("preferred_strategy_not_auth_command")
    if packet.get("selected_strategy") != PREFERRED_STRATEGY:
        failures.append("selected_strategy_not_auth_command")
    fallbacks = packet.get("fallbacks") if isinstance(packet.get("fallbacks"), dict) else {}
    bearer = fallbacks.get(BOUNDED_BEARER_FALLBACK) if isinstance(fallbacks, dict) else {}
    if isinstance(bearer, dict) and bearer.get("silent_fallback_allowed") is not False:
        failures.append("silent_bearer_fallback_allowed")
    file_auth = fallbacks.get(FILE_AUTH_FALLBACK) if isinstance(fallbacks, dict) else {}
    if isinstance(file_auth, dict) and file_auth.get("can_satisfy_proxy_auth_contract") is not False:
        failures.append("file_auth_can_satisfy_proxy_auth")
    runtime_dependency = (
        packet.get("runtime_dependency") if isinstance(packet.get("runtime_dependency"), dict) else {}
    )
    if runtime_dependency.get("env_auth_used_in_this_contour") is not False:
        failures.append("env_auth_used_in_this_contour")
    if runtime_dependency.get("ambient_host_auth_used_in_this_contour") is not False:
        failures.append("ambient_host_auth_used_in_this_contour")
    native_surface = packet.get("native_config_auth_surface")
    if isinstance(native_surface, dict):
        redacted = str(native_surface.get("redacted_config") or "")
        if provider_auth_text_has_secret(redacted):
            failures.append("redacted_native_config_contains_secret")
    claims = packet.get("claims") if isinstance(packet.get("claims"), dict) else {}
    for forbidden_claim in (
        "native_launch_attempted",
        "model_availability_proven",
        "account_pool_validity_proven",
        "direct_egress_absence_proven",
    ):
        if claims.get(forbidden_claim) is not False:
            failures.append(f"{forbidden_claim}_overclaimed")
    failures.extend(str(item) for item in packet.get("failed_checks", []))
    remote_authority = packet.get("remote_authority")
    if isinstance(remote_authority, dict) and remote_authority.get(
        "remote_authority_blocked"
    ) is not True:
        failures.append("remote_authority_not_blocked")
    return sorted(set(failures))


def _redacted_reference_id(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()[:16]}"


def _walk_true_flags(value: Any, prefix: str = "") -> set[str]:
    findings: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if child is True:
                findings.add(path)
            findings.update(_walk_true_flags(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.update(_walk_true_flags(child, f"{prefix}[{index}]"))
    return findings


def build_provider_auth_strategy_contract_packet() -> dict[str, Any]:
    """Classify the server-owned auth precedence contract without live use."""

    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_strategy_contract",
        "status": "ok",
        "contract_scope": "provider_auth_precedence_only",
        "pass_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "precedence_order": [
            "explicit_wbp_route_policy_account_binding",
            "active_wbp_provider_account_registry_entry",
            "wbp_server_owned_configured_provider_credential_reference",
            "explicit_bounded_fallback_contour_auth",
            "reject",
        ],
        "server_owns_provider_account_selection": True,
        "server_owns_credential_reference_resolution": True,
        "client_supplied_auth_authority_allowed": False,
        "ambient_auth_authority_allowed": False,
        "file_auth_treated_as_proxy_auth": False,
        "raw_secret_value_allowed_in_evidence": False,
        "provider_reachability_claimed": False,
        "model_availability_claimed": False,
        "live_failure_semantics_claimed": False,
        "native_launch_attempted": False,
    }


def build_provider_auth_credential_reference_packet(
    *,
    provider: str = "openrouter",
    account_id: str = "provider-account-active",
    credential_reference: str = "credref:provider-account-active",
    raw_secret_value_present: bool = False,
    raw_secret_value_recorded: bool = False,
    provider_reachability_claimed: bool = False,
    account_validated: bool = False,
    model_availability_claimed: bool = False,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if raw_secret_value_recorded:
        failed_checks.append("raw_secret_value_recorded")
    if raw_secret_value_present and raw_secret_value_recorded:
        failed_checks.append("raw_secret_value_present_in_packet")
    if provider_reachability_claimed:
        failed_checks.append("credential_reference_treated_as_provider_reachability")
    if account_validated and model_availability_claimed:
        failed_checks.append("account_validation_treated_as_model_availability")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_credential_reference",
        "status": "blocked" if failed_checks else "ok",
        "provider": provider,
        "account_id": account_id,
        "credential_reference_kind": "server_owned_reference",
        "credential_reference_id": _redacted_reference_id(credential_reference),
        "credential_reference_recorded_raw": False,
        "raw_secret_value_present": raw_secret_value_present,
        "raw_secret_value_recorded": raw_secret_value_recorded,
        "credential_reference_is_runtime_secret": False,
        "credential_reference_proves_provider_reachability": provider_reachability_claimed,
        "account_validated": account_validated,
        "account_validation_counts_as_model_availability": model_availability_claimed,
        "provider_reachability_claimed": provider_reachability_claimed,
        "model_availability_claimed": model_availability_claimed,
        "failed_checks": failed_checks,
    }


def build_provider_auth_precedence_packet(
    *,
    route_policy_account_binding_present: bool = True,
    active_provider_account_present: bool = True,
    server_credential_reference_present: bool = True,
    bounded_fallback_contour_declared: bool = False,
    missing_auth: bool = False,
    ambiguous_same_precedence_sources: bool = False,
    silent_fallback_allowed: bool = False,
) -> dict[str, Any]:
    rows = [
        {
            "rank": 1,
            "source": "explicit_wbp_route_policy_account_binding",
            "present": route_policy_account_binding_present,
            "server_owned": True,
            "selected": False,
        },
        {
            "rank": 2,
            "source": "active_wbp_provider_account_registry_entry",
            "present": active_provider_account_present,
            "server_owned": True,
            "selected": False,
        },
        {
            "rank": 3,
            "source": "wbp_server_owned_configured_provider_credential_reference",
            "present": server_credential_reference_present,
            "server_owned": True,
            "selected": False,
        },
        {
            "rank": 4,
            "source": "explicit_bounded_fallback_contour_auth",
            "present": bounded_fallback_contour_declared,
            "server_owned": True,
            "selected": False,
        },
    ]
    failed_checks: list[str] = []
    if silent_fallback_allowed:
        failed_checks.append("silent_fallback_allowed")
    if ambiguous_same_precedence_sources:
        failed_checks.append("ambiguous_same_precedence_sources")
    selected_source = "reject"
    if not missing_auth and not ambiguous_same_precedence_sources:
        for row in rows:
            if row["present"]:
                row["selected"] = True
                selected_source = str(row["source"])
                break
    if selected_source == "reject":
        failed_checks.append("auth_source_rejected_or_missing")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_precedence",
        "status": "blocked" if failed_checks else "ok",
        "precedence_scope": "contract_only_no_live_provider_call",
        "precedence_rows": rows,
        "selected_source": selected_source,
        "reject_selected": selected_source == "reject",
        "silent_fallback_allowed": silent_fallback_allowed,
        "missing_auth_blocks_request": selected_source == "reject",
        "ambiguous_auth_blocks_request": ambiguous_same_precedence_sources,
        "route_policy_wins_over_registry": (
            route_policy_account_binding_present
            and active_provider_account_present
            and selected_source == "explicit_wbp_route_policy_account_binding"
        ),
        "registry_wins_over_server_credential_reference": (
            not route_policy_account_binding_present
            and active_provider_account_present
            and server_credential_reference_present
            and selected_source == "active_wbp_provider_account_registry_entry"
        ),
        "provider_reachability_claimed": False,
        "model_availability_claimed": False,
        "runtime_route_claimed": False,
        "failed_checks": failed_checks,
    }


def build_provider_auth_ambient_authority_guard_packet(
    *,
    current_codex_auth_json_runtime_input: bool = False,
    env_auth_runtime_input: bool = False,
    ambient_host_auth_runtime_input: bool = False,
    browser_client_auth_authority: bool = False,
    remote_client_auth_authority: bool = False,
) -> dict[str, Any]:
    failed_checks = [
        name
        for name, active in (
            ("current_codex_auth_json_runtime_input", current_codex_auth_json_runtime_input),
            ("env_auth_runtime_input", env_auth_runtime_input),
            ("ambient_host_auth_runtime_input", ambient_host_auth_runtime_input),
            ("browser_client_auth_authority", browser_client_auth_authority),
            ("remote_client_auth_authority", remote_client_auth_authority),
        )
        if active
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_ambient_authority_guard",
        "status": "blocked" if failed_checks else "ok",
        "current_codex_auth_json_runtime_input": current_codex_auth_json_runtime_input,
        "env_auth_runtime_input": env_auth_runtime_input,
        "ambient_host_auth_runtime_input": ambient_host_auth_runtime_input,
        "browser_client_auth_authority": browser_client_auth_authority,
        "remote_client_auth_authority": remote_client_auth_authority,
        "ambient_authority_allowed": False,
        "no_ambient_authority_gate_satisfied": not failed_checks,
        "failed_checks": failed_checks,
    }


def build_provider_auth_file_vs_proxy_boundary_packet(
    *,
    file_auth_available: bool = False,
    file_auth_selected_as_proxy_auth: bool = False,
    current_codex_auth_json_copied: bool = False,
    current_codex_auth_json_symlinked: bool = False,
) -> dict[str, Any]:
    failed_checks = [
        name
        for name, active in (
            ("file_auth_selected_as_proxy_auth", file_auth_selected_as_proxy_auth),
            ("current_codex_auth_json_copied", current_codex_auth_json_copied),
            ("current_codex_auth_json_symlinked", current_codex_auth_json_symlinked),
        )
        if active
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_file_vs_proxy_boundary",
        "status": "blocked" if failed_checks else "ok",
        "file_auth_available": file_auth_available,
        "file_auth_selected_as_proxy_auth": file_auth_selected_as_proxy_auth,
        "file_auth_equals_proxy_auth": False,
        "file_auth_may_satisfy_proxy_auth": False,
        "current_codex_auth_json_copied": current_codex_auth_json_copied,
        "current_codex_auth_json_symlinked": current_codex_auth_json_symlinked,
        "current_codex_auth_json_runtime_dependency": False,
        "failed_checks": failed_checks,
    }


def build_provider_auth_client_authority_rejection_packet(
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {
        "token": "redacted_fixture",
        "provider": "client-provider",
        "model": "client-model",
        "account_id": "client-account",
        "credential_ref": "client-credential",
        "path": "/tmp/client-auth",
    }
    forbidden_fields = sorted(forbidden_auth_browser_fields(payload))
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_client_authority_rejection",
        "status": "ok" if forbidden_fields else "blocked",
        "client_payload_recorded_raw": False,
        "client_forbidden_fields_detected": forbidden_fields,
        "client_supplied_token_authority_allowed": False,
        "client_supplied_provider_authority_allowed": False,
        "client_supplied_model_authority_allowed": False,
        "client_supplied_account_authority_allowed": False,
        "client_supplied_path_authority_allowed": False,
        "server_owns_provider_model_account_authority": True,
    }


def build_provider_auth_env_authority_limit_packet(
    *,
    env_source_declared: bool = False,
    env_auth_used: bool = False,
    server_side_only: bool = True,
    overrides_route_policy: bool = False,
    raw_env_value_recorded: bool = False,
    silent_env_fallback_allowed: bool = False,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if env_auth_used and not env_source_declared:
        failed_checks.append("env_auth_used_without_declaration")
    if not server_side_only:
        failed_checks.append("env_auth_not_server_side_only")
    if overrides_route_policy:
        failed_checks.append("env_auth_overrides_route_policy")
    if raw_env_value_recorded:
        failed_checks.append("raw_env_value_recorded")
    if silent_env_fallback_allowed:
        failed_checks.append("silent_env_fallback_allowed")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_env_authority_limit",
        "status": "blocked" if failed_checks else "ok",
        "env_source_declared": env_source_declared,
        "env_auth_used": env_auth_used,
        "server_side_only": server_side_only,
        "env_auth_overrides_route_policy": overrides_route_policy,
        "raw_env_value_recorded": raw_env_value_recorded,
        "silent_env_fallback_allowed": silent_env_fallback_allowed,
        "env_var_presence_proves_safe_runtime_auth": False,
        "env_auth_proves_provider_reachability": False,
        "failed_checks": failed_checks,
    }


def build_provider_auth_reserve_account_non_promotion_packet(
    *,
    reserve_account_present: bool = True,
    reserve_account_selected_as_active: bool = False,
    explicit_promotion_contour: bool = False,
    active_route_mutated: bool = False,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if reserve_account_selected_as_active and not explicit_promotion_contour:
        failed_checks.append("reserve_account_promoted_without_explicit_contour")
    if active_route_mutated:
        failed_checks.append("active_route_mutated_by_reserve_account")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_reserve_account_non_promotion",
        "status": "blocked" if failed_checks else "ok",
        "reserve_account_present": reserve_account_present,
        "reserve_account_selected_as_active": reserve_account_selected_as_active,
        "explicit_promotion_contour": explicit_promotion_contour,
        "active_route_mutated": active_route_mutated,
        "reserve_account_equals_active_route": False,
        "reserve_account_validates_model_availability": False,
        "failed_checks": failed_checks,
    }


def build_provider_auth_failure_semantics_packet(
    *,
    missing_auth_result: str = "reject",
    ambiguous_auth_result: str = "reject",
    silent_fallback_on_missing_auth: bool = False,
    silent_fallback_on_ambiguous_auth: bool = False,
    live_failure_semantics_claimed: bool = False,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if missing_auth_result != "reject":
        failed_checks.append("missing_auth_does_not_reject")
    if ambiguous_auth_result != "reject":
        failed_checks.append("ambiguous_auth_does_not_reject")
    if silent_fallback_on_missing_auth:
        failed_checks.append("silent_fallback_on_missing_auth")
    if silent_fallback_on_ambiguous_auth:
        failed_checks.append("silent_fallback_on_ambiguous_auth")
    if live_failure_semantics_claimed:
        failed_checks.append("auth_contract_claimed_live_failure_semantics")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_failure_semantics",
        "status": "blocked" if failed_checks else "ok",
        "missing_auth_result": missing_auth_result,
        "ambiguous_auth_result": ambiguous_auth_result,
        "missing_auth_blocks_request": missing_auth_result == "reject",
        "ambiguous_auth_blocks_request": ambiguous_auth_result == "reject",
        "silent_fallback_on_missing_auth": silent_fallback_on_missing_auth,
        "silent_fallback_on_ambiguous_auth": silent_fallback_on_ambiguous_auth,
        "live_failure_semantics_claimed": live_failure_semantics_claimed,
        "responses_live_failure_semantics_completed": False,
        "failed_checks": failed_checks,
    }


def build_provider_auth_secret_redaction_packet(
    packets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    raw_secret_found = provider_auth_text_has_secret(serialized)
    true_flags = _walk_true_flags(packets)
    forbidden_true_flags = sorted(
        flag
        for flag in true_flags
        if flag.endswith(
            (
                "raw_secret_value_recorded",
                "raw_env_value_recorded",
                "credential_reference_recorded_raw",
                "client_payload_recorded_raw",
                "current_codex_auth_json_copied",
                "current_codex_auth_json_symlinked",
            )
        )
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_secret_redaction",
        "status": "blocked" if raw_secret_found or forbidden_true_flags else "ok",
        "raw_secret_found": raw_secret_found,
        "forbidden_true_flags": forbidden_true_flags,
        "checked_packet_count": len(packets),
        "raw_upstream_secret_recorded": False,
        "credential_reference_recorded_raw": False,
        "raw_env_value_recorded": False,
        "client_payload_recorded_raw": False,
    }


def build_provider_auth_precedence_false_green_audit(
    packets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    true_flags = _walk_true_flags(packets)
    forbidden_suffixes = (
        "provider_reachability_claimed",
        "model_availability_claimed",
        "live_failure_semantics_claimed",
        "runtime_route_claimed",
        "file_auth_selected_as_proxy_auth",
        "file_auth_treated_as_proxy_auth",
        "client_supplied_auth_authority_allowed",
        "client_supplied_token_authority_allowed",
        "client_supplied_provider_authority_allowed",
        "client_supplied_model_authority_allowed",
        "client_supplied_account_authority_allowed",
        "client_supplied_path_authority_allowed",
        "ambient_auth_authority_allowed",
        "silent_fallback_allowed",
        "silent_env_fallback_allowed",
        "silent_fallback_on_missing_auth",
        "silent_fallback_on_ambiguous_auth",
        "reserve_account_selected_as_active",
        "active_route_mutated",
        "account_validation_counts_as_model_availability",
        "credential_reference_proves_provider_reachability",
        "raw_secret_value_recorded",
        "raw_env_value_recorded",
    )
    forbidden_true_flags = sorted(
        flag for flag in true_flags if flag.endswith(forbidden_suffixes)
    )
    blocked_packets = sorted(
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    )
    checks = [
        {
            "name": "all_contract_packets_ok",
            "passed": not blocked_packets,
        },
        {
            "name": "no_forbidden_cross_layer_true_flags",
            "passed": not forbidden_true_flags,
        },
        {
            "name": "auth_strategy_not_model_or_live_proof",
            "passed": not any(
                flag.endswith(
                    (
                        "provider_reachability_claimed",
                        "model_availability_claimed",
                        "live_failure_semantics_claimed",
                    )
                )
                for flag in true_flags
            ),
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "allowed_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "checks": checks,
        "blocked_packets": blocked_packets,
        "forbidden_true_flags": forbidden_true_flags,
    }


def build_provider_auth_summary_packet(
    packets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required = {
        "provider_auth_strategy_contract_packet.json",
        "provider_auth_source_inventory_packet.json",
        "provider_auth_credential_reference_packet.json",
        "provider_auth_precedence_packet.json",
        "provider_auth_ambient_authority_guard_packet.json",
        "provider_auth_file_vs_proxy_boundary_packet.json",
        "provider_auth_client_authority_rejection_packet.json",
        "provider_auth_env_authority_limit_packet.json",
        "provider_auth_reserve_account_non_promotion_packet.json",
        "provider_auth_failure_semantics_packet.json",
        "provider_auth_secret_redaction_packet.json",
        "provider_auth_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = sorted(
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_summary",
        "status": "blocked" if missing or blocked else "ok",
        "final_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": blocked,
        "provider_reachability_claimed": False,
        "account_usability_claimed": False,
        "model_availability_claimed": False,
        "responses_live_failure_semantics_claimed": False,
        "native_launch_attempted": False,
    }
