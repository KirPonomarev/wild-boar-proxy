# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any

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


def command_exit_code(ok: bool, exit_code: int | None = None) -> int:
    if ok:
        return COMMAND_EXIT_OK
    if exit_code is None:
        return COMMAND_EXIT_ERROR
    return exit_code


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
