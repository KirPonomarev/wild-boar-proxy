# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded isolated-HOME keychain preflight for Custom Codex native launch.

This helper prepares only the isolated HOME preference surface that macOS uses
to discover the current user's default keychain and search list. It never reads
keychain items, never mutates the real user keychain, and never performs hidden
owner actions.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REAL_HOME = Path.home().resolve()


def _packet(
    *,
    status: str,
    machine_error_code: str,
    next_action: str,
    real_default_keychain_found: bool = False,
    real_default_keychain_path_redacted: str = "",
    real_search_list_found: bool = False,
    isolated_home_keychain_preferences_written: bool = False,
    isolated_default_keychain_verified: bool = False,
    isolated_search_list_verified: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "machine_error_code": machine_error_code,
        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
        "real_default_keychain_found": real_default_keychain_found,
        "real_default_keychain_path_redacted": real_default_keychain_path_redacted,
        "real_search_list_found": real_search_list_found,
        "isolated_home_keychain_preferences_written": isolated_home_keychain_preferences_written,
        "isolated_default_keychain_verified": isolated_default_keychain_verified,
        "isolated_search_list_verified": isolated_search_list_verified,
        "real_user_keychain_modified": False,
        "keychain_item_read": False,
        "keychain_reset_performed": False,
        "keychain_created": False,
        "keychain_deleted": False,
        "hidden_owner_action_performed": False,
        "next_action": next_action,
    }


def _normalize_security_paths(stdout: str) -> list[str]:
    paths: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('"') and line.endswith('"') and len(line) >= 2:
            line = line[1:-1]
        paths.append(line)
    return paths


def _run_security(args: list[str], *, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _resolve_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def prepare_isolated_home_keychain(*, isolated_home: Path) -> dict[str, Any]:
    if sys.platform != "darwin":
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_UNSUPPORTED_PLATFORM",
            next_action="continue_native_launch_without_keychain_preflight",
        )

    security_bin = shutil.which("security")
    if not security_bin:
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_SECURITY_COMMAND_UNAVAILABLE",
            next_action="continue_native_launch_without_keychain_preflight",
        )

    isolated_home = isolated_home.expanduser()
    if not isolated_home.is_absolute():
        return _packet(
            status="blocked",
            machine_error_code="KEYCHAIN_PREFLIGHT_HOME_NOT_ABSOLUTE",
            next_action="stop_and_diagnose_keychain_preflight",
        )
    if isolated_home.resolve() == REAL_HOME:
        return _packet(
            status="blocked",
            machine_error_code="KEYCHAIN_PREFLIGHT_REAL_HOME_FORBIDDEN",
            next_action="stop_and_diagnose_keychain_preflight",
        )

    default_result = _run_security([security_bin, "default-keychain", "-d", "user"])
    if default_result.returncode != 0:
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_NO_DEFAULT_KEYCHAIN",
            next_action="continue_native_launch_without_keychain_preflight",
        )
    default_paths = _normalize_security_paths(default_result.stdout)
    if not default_paths:
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_DEFAULT_KEYCHAIN_UNPARSEABLE",
            next_action="continue_native_launch_without_keychain_preflight",
        )
    real_default_keychain = Path(default_paths[0]).expanduser()
    if not real_default_keychain.is_file():
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_DEFAULT_KEYCHAIN_MISSING",
            next_action="continue_native_launch_without_keychain_preflight",
        )

    search_result = _run_security([security_bin, "list-keychains", "-d", "user"])
    if search_result.returncode != 0:
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_NO_SEARCH_LIST",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
        )
    search_paths = [Path(item).expanduser() for item in _normalize_security_paths(search_result.stdout)]
    if not search_paths:
        return _packet(
            status="skipped",
            machine_error_code="KEYCHAIN_PREFLIGHT_SEARCH_LIST_UNPARSEABLE",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
        )
    if any(not path.exists() for path in search_paths):
        return _packet(
            status="blocked",
            machine_error_code="KEYCHAIN_PREFLIGHT_SEARCH_LIST_UNTRUTHFUL",
            next_action="stop_and_diagnose_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
        )

    library_dir = isolated_home / "Library"
    prefs_dir = library_dir / "Preferences"
    keychains_dir = library_dir / "Keychains"
    for existing_path in (library_dir, prefs_dir, keychains_dir):
        if existing_path.exists() and not _resolve_within(isolated_home, existing_path):
            return _packet(
                status="blocked",
                machine_error_code="KEYCHAIN_PREFLIGHT_WRITE_SURFACE_BLOCKED",
                next_action="stop_and_diagnose_keychain_preflight",
                real_default_keychain_found=True,
                real_default_keychain_path_redacted="<redacted>",
                real_search_list_found=True,
            )
    prefs_dir.mkdir(parents=True, exist_ok=True)
    keychains_dir.mkdir(parents=True, exist_ok=True)
    if not _resolve_within(isolated_home, prefs_dir) or not _resolve_within(isolated_home, keychains_dir):
        return _packet(
            status="blocked",
            machine_error_code="KEYCHAIN_PREFLIGHT_WRITE_SURFACE_BLOCKED",
            next_action="stop_and_diagnose_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
        )

    set_default = _run_security(
        [security_bin, "default-keychain", "-d", "user", "-s", str(real_default_keychain)],
        home=isolated_home,
    )
    if set_default.returncode != 0:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_SET_DEFAULT_FAILED",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
        )

    set_search = _run_security(
        [security_bin, "list-keychains", "-d", "user", "-s", *[str(path) for path in search_paths]],
        home=isolated_home,
    )
    if set_search.returncode != 0:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_SET_SEARCH_LIST_FAILED",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
        )

    prefs_file = prefs_dir / "com.apple.security.plist"
    prefs_written = prefs_file.exists()
    if not prefs_written:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_PREFERENCES_MISSING",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
        )

    verify_default = _run_security(
        [security_bin, "default-keychain", "-d", "user"],
        home=isolated_home,
    )
    if verify_default.returncode != 0:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_VERIFY_DEFAULT_FAILED",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
            isolated_home_keychain_preferences_written=True,
        )
    verified_default_paths = _normalize_security_paths(verify_default.stdout)
    verified_default = (
        bool(verified_default_paths)
        and Path(verified_default_paths[0]).expanduser() == real_default_keychain
    )
    if not verified_default:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_VERIFY_DEFAULT_MISMATCH",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
            isolated_home_keychain_preferences_written=True,
        )

    verify_search = _run_security(
        [security_bin, "list-keychains", "-d", "user"],
        home=isolated_home,
    )
    if verify_search.returncode != 0:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_VERIFY_SEARCH_LIST_FAILED",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
            isolated_home_keychain_preferences_written=True,
            isolated_default_keychain_verified=True,
        )
    verified_search_paths = [Path(item).expanduser() for item in _normalize_security_paths(verify_search.stdout)]
    verified_search = verified_search_paths == search_paths
    if not verified_search:
        return _packet(
            status="failed",
            machine_error_code="KEYCHAIN_PREFLIGHT_VERIFY_SEARCH_LIST_MISMATCH",
            next_action="continue_native_launch_without_keychain_preflight",
            real_default_keychain_found=True,
            real_default_keychain_path_redacted="<redacted>",
            real_search_list_found=True,
            isolated_home_keychain_preferences_written=True,
            isolated_default_keychain_verified=True,
        )

    return _packet(
        status="ok",
        machine_error_code="OK",
        next_action="continue_native_launch",
        real_default_keychain_found=True,
        real_default_keychain_path_redacted="<redacted>",
        real_search_list_found=True,
        isolated_home_keychain_preferences_written=True,
        isolated_default_keychain_verified=True,
        isolated_search_list_verified=True,
    )
