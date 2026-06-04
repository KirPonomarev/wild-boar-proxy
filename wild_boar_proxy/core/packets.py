# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
from typing import Any, Literal

from ..command_effects import validate_effect


COMMAND_PACKET_REQUIRED_FIELDS = [
    "status",
    "exit_code",
    "human_message",
    "machine_error_code",
    "changed_files",
    "next_action",
    "liveness",
    "severity",
    "operator_action",
]
COMMAND_EXIT_OK = 0
COMMAND_EXIT_ERROR = 1
COMMAND_STATUS_VALUES = ("ok", "error")
COMMAND_LIVENESS_VALUES = (
    "healthy",
    "degraded",
    "down",
    "unknown",
    "not_applicable",
)
COMMAND_SEVERITY_VALUES = ("recoverable", "fatal", "high")
COMMAND_OPERATOR_ACTION_VALUES = ("none", "retry", "user_action", "stop")
COMMAND_NEXT_ACTION_VALUES = ("none", "retry", "user_action", "stop")
COMMAND_PACKET_REDACTION_PLACEHOLDER = "<redacted>"
COMMAND_PACKET_SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "passwd",
    "private_key",
    "secret",
    "token",
)
COMMAND_PACKET_SAFE_REFERENCE_KEYS = (
    "api_key_source",
    "available_secret_refs",
    "credential_ref",
    "credential_refs",
    "secret_ref",
    "secret_refs",
    "secret_value_exposed",
    "secret_value_recorded",
    "token_output_shape",
    "token_source_kind",
    "token_ref",
    "token_refs",
)
COMMAND_PACKET_SAFE_METADATA_KEY_SUFFIXES = (
    "_emitted",
    "_exposed",
    "_omitted",
    "_present",
    "_recorded",
    "_redacted",
)

CommandPacketValueClass = Literal["core", "legacy", "invalid_shape"]

_COMMAND_VALUE_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_COMMAND_PACKET_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)\bauthorization:\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|password|secret|token)\b\s*[:=]\s*"
        r"[A-Za-z0-9._~+/=-]{8,}"
    ),
    re.compile(
        r"(?i)\b[A-Z0-9_]*(API[_-]?KEY|BEARER[_-]?TOKEN)\b\s*[:=]\s*"
        r"[A-Za-z0-9._~+/=-]{8,}"
    ),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
)


def command_exit_code(ok: bool, exit_code: int | None = None) -> int:
    if ok:
        return COMMAND_EXIT_OK
    if exit_code is None:
        return COMMAND_EXIT_ERROR
    return exit_code


def is_command_value_token(value: object) -> bool:
    return isinstance(value, str) and bool(_COMMAND_VALUE_TOKEN_RE.fullmatch(value))


def _classify_command_value(
    value: object, core_values: tuple[str, ...]
) -> CommandPacketValueClass:
    if isinstance(value, str) and value in core_values:
        return "core"
    if is_command_value_token(value):
        return "legacy"
    return "invalid_shape"


def classify_command_status(value: object) -> CommandPacketValueClass:
    return _classify_command_value(value, COMMAND_STATUS_VALUES)


def classify_command_liveness(value: object) -> CommandPacketValueClass:
    return _classify_command_value(value, COMMAND_LIVENESS_VALUES)


def classify_command_severity(value: object) -> CommandPacketValueClass:
    return _classify_command_value(value, COMMAND_SEVERITY_VALUES)


def classify_command_operator_action(value: object) -> CommandPacketValueClass:
    return _classify_command_value(value, COMMAND_OPERATOR_ACTION_VALUES)


def classify_command_next_action(value: object) -> CommandPacketValueClass:
    return _classify_command_value(value, COMMAND_NEXT_ACTION_VALUES)


def _normalize_command_packet_key(key: object) -> str:
    return str(key).strip().lower()


def _is_safe_reference_key(key: object) -> bool:
    normalized_key = _normalize_command_packet_key(key)
    if normalized_key in COMMAND_PACKET_SAFE_REFERENCE_KEYS:
        return True
    return any(
        normalized_key.endswith(suffix)
        for suffix in COMMAND_PACKET_SAFE_METADATA_KEY_SUFFIXES
    )


def _is_sensitive_key(key: object) -> bool:
    normalized_key = _normalize_command_packet_key(key)
    if _is_safe_reference_key(normalized_key):
        return False
    return any(token in normalized_key for token in COMMAND_PACKET_SENSITIVE_KEY_TOKENS)


def _effective_secret_values(
    secret_values: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    if not secret_values:
        return ()
    return tuple(secret for secret in secret_values if secret)


def _redact_command_packet_string(
    value: str,
    *,
    secret_values: tuple[str, ...],
    placeholder: str,
) -> str:
    redacted = value
    for secret in secret_values:
        redacted = redacted.replace(secret, placeholder)
    for pattern in _COMMAND_PACKET_SECRET_PATTERNS:
        redacted = pattern.sub(placeholder, redacted)
    return redacted


def _redact_command_packet_value(
    value: Any,
    *,
    key: str = "",
    secret_values: tuple[str, ...],
    placeholder: str = COMMAND_PACKET_REDACTION_PLACEHOLDER,
    sensitive_context: bool = False,
) -> Any:
    safe_reference_key = _is_safe_reference_key(key)
    current_sensitive_context = (
        sensitive_context or _is_sensitive_key(key)
    ) and not safe_reference_key

    if isinstance(value, dict):
        return {
            _redact_command_packet_string(
                str(item_key),
                secret_values=secret_values,
                placeholder=placeholder,
            ): _redact_command_packet_value(
                item_value,
                key=str(item_key),
                secret_values=secret_values,
                placeholder=placeholder,
                sensitive_context=current_sensitive_context,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_command_packet_value(
                item,
                key=key,
                secret_values=secret_values,
                placeholder=placeholder,
                sensitive_context=current_sensitive_context,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _redact_command_packet_value(
                item,
                key=key,
                secret_values=secret_values,
                placeholder=placeholder,
                sensitive_context=current_sensitive_context,
            )
            for item in value
        )
    if isinstance(value, str):
        if current_sensitive_context:
            return placeholder
        redacted = _redact_command_packet_string(
            value,
            secret_values=secret_values,
            placeholder=placeholder,
        )
        return redacted
    return value


def redact_command_packet_value(
    value: Any,
    *,
    key: str = "",
    secret_values: tuple[str, ...] | list[str] | None = None,
    placeholder: str = COMMAND_PACKET_REDACTION_PLACEHOLDER,
) -> Any:
    return _redact_command_packet_value(
        value,
        key=key,
        secret_values=_effective_secret_values(secret_values),
        placeholder=placeholder,
    )


def redact_command_packet(
    packet: dict[str, Any],
    *,
    secret_values: tuple[str, ...] | list[str] | None = None,
    placeholder: str = COMMAND_PACKET_REDACTION_PLACEHOLDER,
) -> dict[str, Any]:
    return redact_command_packet_value(
        packet,
        secret_values=secret_values,
        placeholder=placeholder,
    )


def _json_for_secret_scan(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)
    except (TypeError, ValueError):
        return repr(payload)


def _sensitive_key_leak_present(
    value: Any,
    *,
    key: str = "",
    sensitive_context: bool = False,
) -> bool:
    safe_reference_key = _is_safe_reference_key(key)
    current_sensitive_context = (
        sensitive_context or _is_sensitive_key(key)
    ) and not safe_reference_key
    if isinstance(value, dict):
        return any(
            _sensitive_key_leak_present(
                item_value,
                key=str(item_key),
                sensitive_context=current_sensitive_context,
            )
            for item_key, item_value in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(
            _sensitive_key_leak_present(
                item,
                key=key,
                sensitive_context=current_sensitive_context,
            )
            for item in value
        )
    return (
        current_sensitive_context
        and isinstance(value, str)
        and value != COMMAND_PACKET_REDACTION_PLACEHOLDER
    )


def command_packet_has_secret_leak(
    packet: Any,
    *,
    secret_values: tuple[str, ...] | list[str] | None = None,
) -> bool:
    encoded = _json_for_secret_scan(packet)
    if any(secret in encoded for secret in _effective_secret_values(secret_values)):
        return True
    if any(pattern.search(encoded) for pattern in _COMMAND_PACKET_SECRET_PATTERNS):
        return True
    return _sensitive_key_leak_present(packet)


def build_command_packet(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    liveness: str,
    severity: str,
    operator_action: str,
    changed_files: list[str],
    extra: dict[str, Any] | None = None,
    exit_code: int | None = None,
    effect: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok" if ok else "error",
        "exit_code": command_exit_code(ok, exit_code),
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": changed_files,
        "next_action": operator_action,
        "liveness": liveness,
        "severity": severity,
        "operator_action": operator_action,
    }
    if effect is not None:
        payload["effect"] = validate_effect(effect)
    if extra:
        payload.update(extra)
    return payload


def missing_required_fields(
    packet: dict[str, Any], required_fields: list[str]
) -> list[str]:
    return [field for field in required_fields if field not in packet]


def has_command_packet_shape(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(field in payload for field in COMMAND_PACKET_REQUIRED_FIELDS)
