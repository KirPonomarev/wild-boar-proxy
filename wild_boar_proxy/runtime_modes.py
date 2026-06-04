# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any, Callable, Protocol

from .command_effects import EFFECT_READ
from .core import packets as command_packets
from .runtime_errors import RuntimeErrorInfo


class RuntimeModePaths(Protocol):
    runtime_mode_file: Path
    runtime_effective_mode_file: Path
    state_file: Path
    managed_config_file: Path
    stable_config: Path


JsonObjectReader = Callable[[Path], dict[str, Any]]
CommandPayloadBuilder = Callable[..., dict[str, Any]]


def _read_optional_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            f"Invalid JSON in {path}: {exc}",
            machine_error_code="INVALID_JSON_FILE",
            operator_action="stop",
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeErrorInfo(
            f"Expected JSON object in {path}",
            machine_error_code="INVALID_JSON_SHAPE",
            operator_action="stop",
        )
    return data


def _read_text(path: Path, *, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8").strip()


def _read_simple_key_value(path: Path, key: str, separator: str) -> str:
    if not path.exists():
        return ""
    prefix = f"{key}{separator}"
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if value.startswith('"') and value.endswith('"'):
                return value[1:-1]
            return value
    return ""


def _read_yaml_value(path: Path, key: str) -> str:
    return _read_simple_key_value(path, key, ":")


def _build_command_payload(
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
    return command_packets.build_command_packet(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=liveness,
        severity=severity,
        operator_action=operator_action,
        changed_files=changed_files,
        extra=extra,
        exit_code=exit_code,
        effect=effect,
        secret_values=secret_values,
    )


def get_desired_mode(paths: RuntimeModePaths) -> str:
    mode = _read_text(paths.runtime_mode_file, default="stable")
    return mode if mode in {"stable", "managed"} else "stable"


def get_effective_mode(paths: RuntimeModePaths, state: dict[str, Any]) -> str:
    mode = _read_text(paths.runtime_effective_mode_file)
    if mode in {"stable", "managed"}:
        return mode
    state_mode = state.get("effective_mode")
    if state_mode in {"stable", "managed"}:
        return str(state_mode)
    return "stable"


def reconcile_effective_mode_for_reporting(
    effective_mode: str, *, listener_ok: bool
) -> str:
    if effective_mode == "managed" and not listener_ok:
        return "stable"
    return effective_mode


def get_endpoint(
    paths: RuntimeModePaths, effective_mode: str
) -> tuple[str, int, str]:
    if effective_mode == "managed":
        host = _read_yaml_value(paths.managed_config_file, "host") or "127.0.0.1"
        port = int(_read_yaml_value(paths.managed_config_file, "port") or "8320")
    else:
        host = _read_yaml_value(paths.stable_config, "host") or "127.0.0.1"
        port = int(_read_yaml_value(paths.stable_config, "port") or "8318")
    return host, port, f"http://{host}:{port}/v1"


def socket_is_listening(host: str, port: int) -> bool:
    sock = socket.socket()
    sock.settimeout(1)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def mode_get(
    paths: RuntimeModePaths,
    *,
    read_optional_json_object: JsonObjectReader = _read_optional_json_object,
    build_payload: CommandPayloadBuilder = _build_command_payload,
) -> dict[str, Any]:
    state = read_optional_json_object(paths.state_file)
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
    host, port, _ = get_endpoint(paths, effective_mode)
    listener_ok = socket_is_listening(host, port)
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    return build_payload(
        ok=True,
        human_message="Mode values are available.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect=EFFECT_READ,
        extra={
            "desired_mode": desired_mode,
            "effective_mode": reported_effective_mode,
        },
    )
