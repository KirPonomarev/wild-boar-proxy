# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


OFFICIAL_CODEX_BUNDLE_ID = "com.openai.codex"
OFFICIAL_CODEX_TEAM_ID = "2DC432GLL2"
DEFAULT_OFFICIAL_CODEX_APP_PATHS = (
    Path("/Applications/ChatGPT.app"),
    Path.home() / "Applications/ChatGPT.app",
    Path("/Applications/Codex.app"),
    Path.home() / "Applications/Codex.app",
)
CODE_SIGN_TIMEOUT_SECONDS = 10.0


class OfficialCodexAppError(RuntimeError):
    def __init__(self, machine_error_code: str, message: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def app_root_for_path(path: Path) -> Path | None:
    candidate = path.expanduser().resolve(strict=False)
    for item in (candidate, *candidate.parents):
        if item.suffix == ".app" and (item / "Contents").is_dir():
            return item
    return None


def _codesign_team_id(app_path: Path) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["/usr/bin/codesign", "-dv", "--verbose=4", str(app_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=CODE_SIGN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", type(exc).__name__
    output = f"{result.stdout}\n{result.stderr}"
    team_id = next(
        (
            line.split("=", 1)[1].strip()
            for line in output.splitlines()
            if line.startswith("TeamIdentifier=")
        ),
        "",
    )
    return team_id, "" if result.returncode == 0 else "codesign_metadata_failed"


def _codesign_valid(app_path: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=CODE_SIGN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    return result.returncode == 0, "" if result.returncode == 0 else "codesign_verify_failed"


def attest_official_codex_app(app_path: Path) -> dict[str, Any]:
    app = app_path.expanduser().resolve(strict=False)
    packet: dict[str, Any] = {
        "packet_kind": "wbp_official_codex_app_attestation",
        "status": "blocked",
        "machine_error_code": "OFFICIAL_CODEX_APP_NOT_FOUND",
        "app_path": str(app),
        "app_present": app.is_dir(),
        "info_plist_present": False,
        "bundle_id": "",
        "bundle_id_proven": False,
        "team_id": "",
        "team_id_proven": False,
        "codesign_valid": False,
        "cli_path": "",
        "cli_executable": False,
        "version": "",
        "build": "",
    }
    plist_path = app / "Contents/Info.plist"
    packet["info_plist_present"] = plist_path.is_file()
    if not packet["app_present"] or not packet["info_plist_present"]:
        return packet
    try:
        with plist_path.open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        packet["machine_error_code"] = "OFFICIAL_CODEX_APP_INFO_INVALID"
        return packet
    bundle_id = str(info.get("CFBundleIdentifier") or "").strip()
    packet["bundle_id"] = bundle_id
    packet["bundle_id_proven"] = bundle_id == OFFICIAL_CODEX_BUNDLE_ID
    packet["version"] = str(info.get("CFBundleShortVersionString") or "").strip()
    packet["build"] = str(info.get("CFBundleVersion") or "").strip()
    executable_name = str(info.get("CFBundleExecutable") or "").strip()
    if not packet["bundle_id_proven"]:
        packet["machine_error_code"] = "OFFICIAL_CODEX_APP_BUNDLE_ID_MISMATCH"
        return packet
    team_id, metadata_error = _codesign_team_id(app)
    packet["team_id"] = team_id
    packet["team_id_proven"] = team_id == OFFICIAL_CODEX_TEAM_ID
    if metadata_error or not packet["team_id_proven"]:
        packet["machine_error_code"] = "OFFICIAL_CODEX_APP_TEAM_ID_MISMATCH"
        return packet
    codesign_valid, verify_error = _codesign_valid(app)
    packet["codesign_valid"] = codesign_valid
    if verify_error or not codesign_valid:
        packet["machine_error_code"] = "OFFICIAL_CODEX_APP_SIGNATURE_INVALID"
        return packet
    app_executable = app / "Contents/MacOS" / executable_name
    cli_path = app / "Contents/Resources/codex"
    packet["app_executable"] = str(app_executable)
    packet["app_executable_present"] = bool(
        executable_name and app_executable.is_file() and os.access(app_executable, os.X_OK)
    )
    packet["cli_path"] = str(cli_path)
    packet["cli_executable"] = cli_path.is_file() and os.access(cli_path, os.X_OK)
    if not packet["app_executable_present"] or not packet["cli_executable"]:
        packet["machine_error_code"] = "OFFICIAL_CODEX_APP_EXECUTABLE_MISSING"
        return packet
    packet["status"] = "ok"
    packet["machine_error_code"] = "OK"
    return packet


def official_codex_app_candidates(
    env: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    source = os.environ if env is None else env
    explicit_app = str(source.get("WBP_CODEX_APP_PATH") or "").strip()
    explicit_bin = str(source.get("WBP_CODEX_BIN") or "").strip()
    if explicit_app:
        return (Path(explicit_app).expanduser(),)
    if explicit_bin:
        app_root = app_root_for_path(Path(explicit_bin))
        return (app_root,) if app_root is not None else ()
    return DEFAULT_OFFICIAL_CODEX_APP_PATHS


def resolve_official_codex_app(
    env: Mapping[str, str] | None = None,
    *,
    candidates: Sequence[Path] | None = None,
) -> dict[str, Any]:
    attempted: list[dict[str, Any]] = []
    for app_path in candidates or official_codex_app_candidates(env):
        packet = attest_official_codex_app(Path(app_path))
        attempted.append(packet)
        if packet.get("status") == "ok":
            return {**packet, "candidate_count": len(attempted)}
    machine_error_code = (
        str(attempted[-1].get("machine_error_code"))
        if attempted
        else "OFFICIAL_CODEX_APP_PATH_INVALID"
    )
    return {
        "packet_kind": "wbp_official_codex_app_attestation",
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "candidate_count": len(attempted),
        "attempted_paths": [str(item.get("app_path") or "") for item in attempted],
        "cli_path": "",
    }


def resolve_official_codex_cli(env: Mapping[str, str] | None = None) -> Path:
    packet = resolve_official_codex_app(env)
    if packet.get("status") != "ok":
        raise OfficialCodexAppError(
            str(packet.get("machine_error_code") or "OFFICIAL_CODEX_APP_NOT_PROVEN"),
            "Signed official Codex/ChatGPT application was not proven.",
        )
    return Path(str(packet["cli_path"]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wbp-official-codex-app")
    parser.add_argument("--print-cli-path", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    packet = resolve_official_codex_app()
    if args.print_cli_path and packet.get("status") == "ok":
        print(packet["cli_path"])
    elif args.json or not args.print_cli_path:
        print(json.dumps(packet, sort_keys=True))
    return 0 if packet.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
