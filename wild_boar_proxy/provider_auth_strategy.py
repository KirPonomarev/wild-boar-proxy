# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider auth strategy packets for Codex -> WBP integration."""

from __future__ import annotations

import re
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
AUTH_FORBIDDEN_BROWSER_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "auth_command",
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
        ],
        "failed_checks": failed_checks,
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
        "http_proxy_env_required": False,
        "https_proxy_env_required": False,
        "all_proxy_env_required": False,
        "current_codex_auth_json_runtime_input": False,
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
