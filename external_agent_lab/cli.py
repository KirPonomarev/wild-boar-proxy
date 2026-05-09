"""Shared CLI entrypoint for the isolated External Agent Lab."""

from __future__ import annotations

import argparse
import json
import sys


class LabError(Exception):
    """Machine-readable lab command error."""

    def __init__(
        self,
        human_message: str,
        machine_error_code: str = "invalid_request",
        exit_code: int = 1,
    ) -> None:
        super().__init__(human_message)
        self.human_message = human_message
        self.machine_error_code = machine_error_code
        self.exit_code = exit_code


def ensure_supported_python() -> None:
    if sys.version_info < (3, 9):
        raise LabError("External Agent Lab requires Python >= 3.9.")


def build_error_packet(error: LabError) -> dict[str, object]:
    return {
        "status": "error",
        "exit_code": error.exit_code,
        "machine_error_code": error.machine_error_code,
        "human_message": error.human_message,
        "lab_mode": True,
    }


def emit_json_packet(packet: dict[str, object], pretty: bool = False) -> None:
    if pretty:
        print(json.dumps(packet, ensure_ascii=False, indent=2))
        return
    print(json.dumps(packet, ensure_ascii=False))


def parse_preflight_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?")
    parser.add_argument("--pretty", action="store_true")
    args, _ = parser.parse_known_args(argv)
    return args


def resolve_dispatch(argv: list[str], default_command: str | None) -> tuple[str, list[str]]:
    if argv and argv[0] in {"run", "eval"}:
        return argv[0], argv[1:]
    return default_command or "run", argv


def dispatch(command: str, argv: list[str]) -> int | None:
    if command == "run":
        from external_agent_lab.legacy import run_lab as legacy_run_lab

        return legacy_run_lab.main(argv)
    if command == "eval":
        from external_agent_lab.legacy import agent_eval as legacy_agent_eval

        return legacy_agent_eval.main(argv)
    raise LabError(f"Unsupported lab command: {command}.")


def main(argv: list[str] | None = None, default_command: str | None = None) -> int | None:
    if argv is None:
        argv = sys.argv[1:]

    args = None
    try:
        args = parse_preflight_args(argv)
        ensure_supported_python()
        command, dispatch_argv = resolve_dispatch(argv, default_command)
        return dispatch(command, dispatch_argv)
    except LabError as error:
        pretty = getattr(args, "pretty", False) if args is not None else False
        emit_json_packet(build_error_packet(error), pretty=pretty)
        return error.exit_code
