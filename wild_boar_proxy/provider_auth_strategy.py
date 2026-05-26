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
) -> dict[str, Any]:
    auth_command_path_text = str(Path(auth_command_path).expanduser())
    native_surface = classify_native_config_auth_surface(
        native_config_text,
        explicit_bearer_contract=explicit_bearer_contract,
    )
    forbidden_browser_fields = forbidden_auth_browser_fields(browser_payload or {})
    failed_checks = list(native_surface["failed_checks"])
    if forbidden_browser_fields:
        failed_checks.append("browser_auth_authority_detected")
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
    return sorted(set(failures))
