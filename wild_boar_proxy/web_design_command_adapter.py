# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Bounded command adapter for the fixture-backed web design UI.

This module is the only planned Python-side bridge between the HTML renderer
path and Wild Boar Proxy command packets. It intentionally does not interpret
runtime truth beyond the canonical packet envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import Any, Protocol

from wild_boar_proxy.ui_shell import CommandResult, UiShellError, require_fields


REQUIRED_COMMAND_FIELDS = (
    "status",
    "exit_code",
    "human_message",
    "machine_error_code",
    "changed_files",
    "next_action",
)


class CommandRunner(Protocol):
    def run(self, *args: str) -> CommandResult:
        """Run a strict JSON command and return its parsed packet."""


@dataclass(frozen=True)
class CommandSpec:
    command_id: str
    argv_template: tuple[str, ...]
    category: str
    ui_enabled: bool = True
    confirmation_required: bool = False
    required_args: tuple[str, ...] = ()
    allowed_args: tuple[str, ...] = ()


ALLOWLIST: dict[str, CommandSpec] = {
    "status": CommandSpec(
        command_id="status",
        argv_template=("status", "--json"),
        category="truth",
    ),
    "healthcheck": CommandSpec(
        command_id="healthcheck",
        argv_template=("healthcheck", "--json"),
        category="truth",
    ),
    "mode_get": CommandSpec(
        command_id="mode_get",
        argv_template=("mode", "get", "--json"),
        category="truth",
    ),
    "accounts_list": CommandSpec(
        command_id="accounts_list",
        argv_template=("accounts", "list", "--json"),
        category="truth",
    ),
    "accounts_validate": CommandSpec(
        command_id="accounts_validate",
        argv_template=("accounts", "validate", "{account_id}", "--json"),
        category="verification",
        confirmation_required=True,
        required_args=("account_id",),
        allowed_args=("account_id",),
    ),
    "rollout_rotation_inspect": CommandSpec(
        command_id="rollout_rotation_inspect",
        argv_template=("rollout", "rotation", "inspect", "--json"),
        category="truth",
    ),
    "mode_stable": CommandSpec(
        command_id="mode_stable",
        argv_template=("mode", "set", "stable", "--json"),
        category="action",
        confirmation_required=True,
    ),
    "mode_managed": CommandSpec(
        command_id="mode_managed",
        argv_template=("mode", "set", "managed", "--json"),
        category="action",
        confirmation_required=True,
    ),
    "sync": CommandSpec(
        command_id="sync",
        argv_template=("sync", "--json"),
        category="action",
        confirmation_required=True,
    ),
    "smoke": CommandSpec(
        command_id="smoke",
        argv_template=("launch", "smoke", "--json"),
        category="action",
        confirmation_required=False,
    ),
    "stable_repair_dry_run": CommandSpec(
        command_id="stable_repair_dry_run",
        argv_template=("stable", "repair", "--dry-run", "--json"),
        category="action",
    ),
    "stable_repair_apply": CommandSpec(
        command_id="stable_repair_apply",
        argv_template=("stable", "repair", "--apply", "--json"),
        category="action",
        confirmation_required=True,
    ),
    "diagnostics_export": CommandSpec(
        command_id="diagnostics_export",
        argv_template=("diagnostics", "export", "--json"),
        category="support",
    ),
    "launch_client": CommandSpec(
        command_id="launch_client",
        argv_template=("launch", "client", "--client-path", "{client_path}", "--json"),
        category="action",
        ui_enabled=False,
        confirmation_required=True,
        required_args=("client_path",),
        allowed_args=("client_path",),
    ),
}


def allowlist_metadata() -> list[dict[str, Any]]:
    return [
        {
            "command_id": spec.command_id,
            "category": spec.category,
            "ui_enabled": spec.ui_enabled,
            "confirmation_required": spec.confirmation_required,
            "required_args": list(spec.required_args),
            "allowed_args": list(spec.allowed_args),
            "argv": list(spec.argv_template),
        }
        for spec in sorted(ALLOWLIST.values(), key=lambda item: item.command_id)
    ]


def execute_command(
    runner: CommandRunner,
    command_id: str,
    *,
    structured_args: dict[str, str] | None = None,
    allow_disabled: bool = False,
) -> dict[str, Any]:
    try:
        spec = _require_spec(command_id)
        if not spec.ui_enabled and not allow_disabled:
            raise UiShellError(f"command is disabled for this UI contour: {command_id}")
        argv = _render_argv(spec, structured_args or {})
        result = runner.run(*argv)
        return _normalize_packet(command_id=command_id, argv=argv, payload=result.payload)
    except subprocess.TimeoutExpired as exc:
        return _integration_failure(
            command_id=command_id,
            machine_error_code="UI_COMMAND_TIMEOUT",
            human_message=f"Command timed out after {exc.timeout} seconds.",
        )
    except (UiShellError, subprocess.SubprocessError, OSError, ValueError) as exc:
        return _integration_failure(
            command_id=command_id,
            machine_error_code="UI_COMMAND_INTEGRATION_FAILURE",
            human_message=str(exc),
        )


def _require_spec(command_id: str) -> CommandSpec:
    try:
        return ALLOWLIST[command_id]
    except KeyError as exc:
        raise UiShellError(f"command is not allowlisted: {command_id}") from exc


def _render_argv(spec: CommandSpec, structured_args: dict[str, str]) -> tuple[str, ...]:
    unknown_args = sorted(set(structured_args) - set(spec.allowed_args))
    if unknown_args:
        raise UiShellError(f"{spec.command_id} got unsupported args: {', '.join(unknown_args)}")

    non_string_args = sorted(key for key, value in structured_args.items() if not isinstance(value, str))
    if non_string_args:
        raise UiShellError(f"{spec.command_id} got non-string args: {', '.join(non_string_args)}")

    missing_args = [arg for arg in spec.required_args if arg not in structured_args]
    if missing_args:
        raise UiShellError(f"{spec.command_id} missing required args: {', '.join(missing_args)}")

    if "client_path" in structured_args:
        client_path = structured_args["client_path"]
        if not os.path.isabs(client_path):
            raise UiShellError("launch_client client_path must be absolute")

    return tuple(part.format(**structured_args) for part in spec.argv_template)


def _normalize_packet(command_id: str, argv: tuple[str, ...], payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, REQUIRED_COMMAND_FIELDS, "command payload")
    if not isinstance(payload["changed_files"], list):
        raise UiShellError("command payload changed_files must be a list")

    ok = (
        payload.get("status") == "ok"
        and payload.get("exit_code") == 0
        and payload.get("machine_error_code") == "OK"
    )
    return {
        "status": "ok" if ok else "command_error",
        "ui_state": "success" if ok else "error",
        "command_id": command_id,
        "argv": list(argv),
        "machine_error_code": payload["machine_error_code"],
        "human_message": payload["human_message"],
        "exit_code": payload["exit_code"],
        "changed_files": payload["changed_files"],
        "next_action": payload["next_action"],
        "packet": payload,
    }


def _integration_failure(
    *,
    command_id: str,
    machine_error_code: str,
    human_message: str,
) -> dict[str, Any]:
    packet = {
        "status": "integration_failure",
        "exit_code": 1,
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": [],
        "next_action": "retry",
        "liveness": "unknown",
        "severity": "recoverable",
        "operator_action": "retry",
        "data": {
            "command_id": command_id,
        },
    }
    return {
        "status": "integration_failure",
        "ui_state": "integration_failure",
        "command_id": command_id,
        "argv": [],
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "exit_code": 1,
        "changed_files": [],
        "next_action": "retry",
        "packet": packet,
    }
