"""Backend-side command adapter for the desktop HTML UI."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


REQUIRED_PACKET_FIELDS = (
    "status",
    "exit_code",
    "human_message",
    "machine_error_code",
    "changed_files",
    "next_action",
    "liveness",
    "severity",
    "operator_action",
)


class AdapterErrorCode:
    OK = "OK"
    COMMAND_FORBIDDEN = "COMMAND_FORBIDDEN"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    COMMAND_EXECUTION_FAILED = "COMMAND_EXECUTION_FAILED"
    INVALID_JSON = "INVALID_JSON"
    INVALID_PACKET = "INVALID_PACKET"


@dataclass(frozen=True)
class CommandSpec:
    command_id: str
    argv_tail: tuple[str, ...]
    command_class: str
    confirmation_level: str = "none"
    argument_names: tuple[str, ...] = ()

    def build_argv(self, args: Mapping[str, str] | None = None) -> list[str]:
        args = args or {}
        missing = [name for name in self.argument_names if not args.get(name)]
        if missing:
            raise ValueError(f"Missing required arguments: {', '.join(missing)}")

        rendered: list[str] = []
        for part in self.argv_tail:
            if part.startswith("{") and part.endswith("}"):
                name = part[1:-1]
                if name not in self.argument_names:
                    raise ValueError(f"Unknown command argument placeholder: {name}")
                rendered.append(args[name])
            else:
                rendered.append(part)
        return [sys.executable, "-m", "wild_boar_proxy", *rendered]


@dataclass(frozen=True)
class RunnerResult:
    returncode: int
    stdout: str
    stderr: str = ""


@dataclass(frozen=True)
class AdapterResult:
    command_id: str
    command_class: str | None
    allowed: bool
    adapter_status: str
    confirmation_level: str | None = None
    argv: tuple[str, ...] = ()
    raw_packet: dict[str, Any] | None = None
    support_stderr: str = ""
    error_code: str = AdapterErrorCode.OK
    error_message: str = ""
    timeout_seconds: float | None = None


Runner = Callable[[Sequence[str], float], RunnerResult]


def _command_specs() -> dict[str, CommandSpec]:
    specs = [
        CommandSpec("status", ("status", "--json"), "read"),
        CommandSpec("healthcheck", ("healthcheck", "--json"), "read"),
        CommandSpec("mode.get", ("mode", "get", "--json"), "read"),
        CommandSpec("accounts.list", ("accounts", "list", "--json"), "read"),
        CommandSpec("rollout.rotation.inspect", ("rollout", "rotation", "inspect", "--json"), "read"),
        CommandSpec("mode.set.stable", ("mode", "set", "stable", "--json"), "action", "high"),
        CommandSpec("mode.set.managed", ("mode", "set", "managed", "--json"), "action", "high"),
        CommandSpec("sync", ("sync", "--json"), "action", "high"),
        CommandSpec("launch.client", ("launch", "client", "--json"), "action", "high"),
        CommandSpec("launch.smoke", ("launch", "smoke", "--json"), "action", "high"),
        CommandSpec("stable.repair.dry_run", ("stable", "repair", "--dry-run", "--json"), "action"),
        CommandSpec("stable.repair.apply", ("stable", "repair", "--apply", "--json"), "action", "high"),
        CommandSpec("accounts.onboard", ("accounts", "onboard", "--json"), "action", "high"),
        CommandSpec("accounts.validate", ("accounts", "validate", "{id}", "--json"), "action", "none", ("id",)),
        CommandSpec("accounts.promote", ("accounts", "promote", "{id}", "--json"), "action", "high", ("id",)),
        CommandSpec("accounts.demote", ("accounts", "demote", "{id}", "--json"), "action", "high", ("id",)),
        CommandSpec("accounts.hold", ("accounts", "hold", "{id}", "--json"), "action", "high", ("id",)),
        CommandSpec("accounts.release", ("accounts", "release", "{id}", "--json"), "action", "high", ("id",)),
        CommandSpec("accounts.retire", ("accounts", "retire", "{id}", "--json"), "action", "high", ("id",)),
        CommandSpec("diagnostics.export", ("diagnostics", "export", "--json"), "action"),
    ]
    return {spec.command_id: spec for spec in specs}


COMMAND_SPECS = _command_specs()


def default_runner(argv: Sequence[str], timeout_seconds: float) -> RunnerResult:
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return RunnerResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def list_command_specs() -> dict[str, CommandSpec]:
    return dict(COMMAND_SPECS)


def run_command(
    command_id: str,
    *,
    args: Mapping[str, str] | None = None,
    timeout_seconds: float = 30.0,
    runner: Runner = default_runner,
) -> AdapterResult:
    spec = COMMAND_SPECS.get(command_id)
    if spec is None:
        return AdapterResult(
            command_id=command_id,
            command_class=None,
            allowed=False,
            adapter_status="integration_failure",
            error_code=AdapterErrorCode.COMMAND_FORBIDDEN,
            error_message="Command is not allowlisted.",
        )

    try:
        argv = spec.build_argv(args)
    except ValueError as exc:
        return AdapterResult(
            command_id=command_id,
            command_class=spec.command_class,
            allowed=True,
            adapter_status="integration_failure",
            confirmation_level=spec.confirmation_level,
            error_code=AdapterErrorCode.INVALID_PACKET,
            error_message=str(exc),
        )

    try:
        result = runner(argv, timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return AdapterResult(
            command_id=command_id,
            command_class=spec.command_class,
            allowed=True,
            adapter_status="integration_failure",
            confirmation_level=spec.confirmation_level,
            argv=tuple(argv),
            error_code=AdapterErrorCode.COMMAND_TIMEOUT,
            error_message="Command timed out.",
            timeout_seconds=exc.timeout,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary.
        return AdapterResult(
            command_id=command_id,
            command_class=spec.command_class,
            allowed=True,
            adapter_status="integration_failure",
            confirmation_level=spec.confirmation_level,
            argv=tuple(argv),
            error_code=AdapterErrorCode.COMMAND_EXECUTION_FAILED,
            error_message=str(exc),
        )

    packet_result = _parse_packet(result.stdout)
    if isinstance(packet_result, AdapterResult):
        return _with_execution_context(packet_result, spec, argv, result.stderr)

    validation_error = _validate_packet(packet_result)
    if validation_error:
        return AdapterResult(
            command_id=command_id,
            command_class=spec.command_class,
            allowed=True,
            adapter_status="integration_failure",
            confirmation_level=spec.confirmation_level,
            argv=tuple(argv),
            raw_packet=packet_result,
            support_stderr=result.stderr,
            error_code=AdapterErrorCode.INVALID_PACKET,
            error_message=validation_error,
        )

    adapter_status = "ok" if packet_result.get("status") == "ok" else "command_error"
    return AdapterResult(
        command_id=command_id,
        command_class=spec.command_class,
        allowed=True,
        adapter_status=adapter_status,
        confirmation_level=spec.confirmation_level,
        argv=tuple(argv),
        raw_packet=packet_result,
        support_stderr=result.stderr,
        error_code=AdapterErrorCode.OK,
    )


def _parse_packet(stdout: str) -> dict[str, Any] | AdapterResult:
    stripped = stdout.strip()
    if not stripped:
        return AdapterResult(
            command_id="",
            command_class=None,
            allowed=True,
            adapter_status="integration_failure",
            error_code=AdapterErrorCode.INVALID_JSON,
            error_message="Command stdout is empty.",
        )
    try:
        decoder = json.JSONDecoder()
        packet, index = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        return AdapterResult(
            command_id="",
            command_class=None,
            allowed=True,
            adapter_status="integration_failure",
            error_code=AdapterErrorCode.INVALID_JSON,
            error_message=f"Command stdout is not valid JSON: {exc.msg}",
        )
    if stripped[index:].strip():
        return AdapterResult(
            command_id="",
            command_class=None,
            allowed=True,
            adapter_status="integration_failure",
            error_code=AdapterErrorCode.INVALID_JSON,
            error_message="Command stdout contains extra data after the JSON object.",
        )
    if not isinstance(packet, dict):
        return AdapterResult(
            command_id="",
            command_class=None,
            allowed=True,
            adapter_status="integration_failure",
            error_code=AdapterErrorCode.INVALID_PACKET,
            error_message="Command stdout JSON must be an object.",
        )
    return packet


def _validate_packet(packet: Mapping[str, Any]) -> str:
    missing = [field for field in REQUIRED_PACKET_FIELDS if field not in packet]
    if missing:
        return f"Command packet is missing required fields: {', '.join(missing)}"
    if not isinstance(packet.get("machine_error_code"), str) or not packet.get("machine_error_code"):
        return "Command packet machine_error_code must be a non-empty string."
    if packet.get("status") not in {"ok", "error"}:
        return "Command packet status must be ok or error."
    if not isinstance(packet.get("changed_files"), list):
        return "Command packet changed_files must be a list."
    return ""


def _with_execution_context(
    result: AdapterResult,
    spec: CommandSpec,
    argv: Sequence[str],
    stderr: str,
) -> AdapterResult:
    return AdapterResult(
        command_id=spec.command_id,
        command_class=spec.command_class,
        allowed=True,
        adapter_status=result.adapter_status,
        confirmation_level=spec.confirmation_level,
        argv=tuple(argv),
        raw_packet=result.raw_packet,
        support_stderr=stderr,
        error_code=result.error_code,
        error_message=result.error_message,
        timeout_seconds=result.timeout_seconds,
    )
