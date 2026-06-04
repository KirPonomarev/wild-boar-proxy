# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

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

CommandPacketValueClass = Literal["core", "legacy", "invalid_shape"]

_COMMAND_VALUE_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


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
