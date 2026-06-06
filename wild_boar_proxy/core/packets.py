# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
from typing import Any, Literal

from . import errors as core_errors
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
COMMAND_NEXT_ACTION_CORE_VALUES = ("none", "retry", "user_action", "stop")
# `next_action` is compatibility-wide: core generic values classify as "core";
# documented command-specific token-shaped values classify as "legacy".
COMMAND_NEXT_ACTION_VALUES = COMMAND_NEXT_ACTION_CORE_VALUES
COMMAND_NEXT_ACTION_RESERVED_VALUES = ("operator_action",)
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
    "token_status",
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


def _command_packet_violation(
    field: str, code: str, human_message: str
) -> dict[str, str]:
    return {"field": field, "code": code, "human_message": human_message}


def _inspect_string_token_field(
    packet: dict[str, Any],
    field: str,
    classifier: Any,
    violations: list[dict[str, str]],
    *,
    allow_legacy: bool = True,
    reserved_values: tuple[str, ...] = (),
) -> None:
    value = packet.get(field)
    if not isinstance(value, str):
        violations.append(
            _command_packet_violation(field, "type", f"{field} must be a string.")
        )
        return
    if value in reserved_values:
        violations.append(
            _command_packet_violation(
                field,
                "reserved_value",
                f"{field} must not use reserved placeholder token {value}.",
            )
        )
        return
    classification = classifier(value)
    if classification == "invalid_shape":
        violations.append(
            _command_packet_violation(
                field,
                "invalid_shape",
                f"{field} must use a machine-readable token shape.",
            )
        )
    elif classification == "legacy" and not allow_legacy:
        violations.append(
            _command_packet_violation(
                field,
                "invalid_value",
                f"{field} must use a documented core command value.",
            )
        )


def inspect_command_packet_semantics(
    packet: Any,
    *,
    required_fields: list[str] | tuple[str, ...] | None = None,
    secret_values: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, str]]:
    fields = list(required_fields or COMMAND_PACKET_REQUIRED_FIELDS)
    violations: list[dict[str, str]] = []
    if not isinstance(packet, dict):
        return [
            _command_packet_violation(
                "packet", "type", "Command packet must be a JSON object."
            )
        ]

    for field in missing_required_fields(packet, fields):
        violations.append(
            _command_packet_violation(field, "missing", f"{field} is required.")
        )

    if "status" in packet:
        _inspect_string_token_field(packet, "status", classify_command_status, violations)
    if "human_message" in packet and not isinstance(packet.get("human_message"), str):
        violations.append(
            _command_packet_violation(
                "human_message", "type", "human_message must be a string."
            )
        )
    if "machine_error_code" in packet:
        _inspect_string_token_field(
            packet,
            "machine_error_code",
            core_errors.classify_machine_error_code,
            violations,
        )
    if "next_action" in packet:
        _inspect_string_token_field(
            packet,
            "next_action",
            classify_command_next_action,
            violations,
            reserved_values=COMMAND_NEXT_ACTION_RESERVED_VALUES,
        )
    if "liveness" in packet:
        _inspect_string_token_field(
            packet, "liveness", classify_command_liveness, violations
        )
    if "severity" in packet:
        _inspect_string_token_field(
            packet, "severity", classify_command_severity, violations
        )
    if "operator_action" in packet:
        _inspect_string_token_field(
            packet,
            "operator_action",
            classify_command_operator_action,
            violations,
            allow_legacy=False,
        )

    if "exit_code" in packet:
        exit_code = packet.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            violations.append(
                _command_packet_violation(
                    "exit_code", "type", "exit_code must be an integer."
                )
            )
    if "changed_files" in packet:
        changed_files = packet.get("changed_files")
        if not isinstance(changed_files, list):
            violations.append(
                _command_packet_violation(
                    "changed_files", "type", "changed_files must be a list."
                )
            )
        elif not all(isinstance(path, str) for path in changed_files):
            violations.append(
                _command_packet_violation(
                    "changed_files",
                    "item_type",
                    "changed_files must contain only strings.",
                )
            )
    if "effect" in packet:
        effect = packet.get("effect")
        if not isinstance(effect, str):
            violations.append(
                _command_packet_violation("effect", "type", "effect must be a string.")
            )
        else:
            try:
                validate_effect(effect)
            except ValueError:
                violations.append(
                    _command_packet_violation(
                        "effect",
                        "invalid_value",
                        "effect must be a documented command effect.",
                    )
                )
    if command_packet_has_secret_leak(packet, secret_values=secret_values):
        violations.append(
            _command_packet_violation(
                "packet", "secret_leak", "Command packet contains secret material."
            )
        )
    return violations


def has_command_packet_semantic_violation(
    packet: Any,
    *,
    required_fields: list[str] | tuple[str, ...] | None = None,
    secret_values: tuple[str, ...] | list[str] | None = None,
) -> bool:
    return bool(
        inspect_command_packet_semantics(
            packet,
            required_fields=required_fields,
            secret_values=secret_values,
        )
    )


def _command_packet_redaction_failure_payload() -> dict[str, Any]:
    return {
        "status": "error",
        "exit_code": COMMAND_EXIT_ERROR,
        "human_message": "Command packet redaction failed; unsafe payload withheld.",
        "machine_error_code": "COMMAND_PACKET_MALFORMED",
        "changed_files": [],
        "next_action": "stop",
        "liveness": "unknown",
        "severity": "fatal",
        "operator_action": "stop",
        "packet_redaction_status": "failed",
    }


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
    secret_values: tuple[str, ...] | list[str] | None = None,
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
    redacted_payload = redact_command_packet(payload, secret_values=secret_values)
    if command_packet_has_secret_leak(redacted_payload, secret_values=secret_values):
        return _command_packet_redaction_failure_payload()
    return redacted_payload


def missing_required_fields(
    packet: dict[str, Any], required_fields: list[str]
) -> list[str]:
    return [field for field in required_fields if field not in packet]


def has_command_packet_shape(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(field in payload for field in COMMAND_PACKET_REQUIRED_FIELDS)
