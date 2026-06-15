# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-owned bounded runner surface for native window proof contours.

This module normalizes a repeatable Phase 9 runner surface without changing
launch semantics. It reuses the existing custom native launch lane, packet
builders, and bounded cleanup model.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .native_filesystem_probe import (
    NativeProbeLayout,
    clean_env,
    collect_codex_process_inventory,
    create_persistent_custom_profile_layout,
    create_native_probe_layout,
    default_persistent_custom_profile_paths,
    json_write,
    launch_native_candidate,
    materialize_probe_profile,
    remove_tree_with_retry,
    terminate_custom_processes,
    utc_now,
)
from .keychain_preflight import prepare_isolated_home_keychain
from .native_launch_contract import build_native_custom_preflight_packet
from .native_launch_dispatch import (
    CUSTOM_LAUNCH_MODE,
    build_native_cleanup_rollback_execution_packet,
    build_native_current_codex_protection_packet,
    build_native_custom_dispatch_packet,
    build_native_dispatch_authorization_packet,
    build_native_dispatch_false_green_audit,
    build_native_original_dispatch_deferred_packet,
    build_native_process_observation_packet,
    build_native_window_observation_packet,
    build_native_window_usability_packet,
)
from .runtime import CODEX_REMOTE_DEBUGGING_PORT
from .runtime import RuntimePaths
from .token_command import emit_local_token


OWNER_STANDING_AUTHORIZATION_PHRASE = "разрешаю тебе любые законные действия в рамках разработки проекта"
WINDOW_OBSERVATION_WAIT_SECONDS = 12.0
WINDOW_OBSERVATION_POLL_SECONDS = 0.5
CODEX_RENDERER_RECOVERY_WAIT_SECONDS = 2.0
POST_LAUNCH_USABILITY_RECHECK_SECONDS = 8.0
POST_LAUNCH_USABILITY_RECHECK_POLL_SECONDS = 0.5
CODEX_DESKTOP_AUTH_BLOCKER_RECHECK_SECONDS = 20.0
CODEX_DESKTOP_AUTH_BLOCKER_RECHECK_POLL_SECONDS = 0.25
DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID = "wbp-custom-main"
RUNTIME_READY_STDOUT_MARKERS = (
    "Handled 'ready' message",
    "method=model/list",
    "browser_use_iab_backend_startup_ready",
)
CODEX_DESKTOP_SIGN_IN_REQUIRED_MARKER = (
    "Sign in to ChatGPT in Codex Desktop to check remote control authorization."
)
CODEX_DESKTOP_NO_TOKEN_AUTH_MARKERS = (
    "desktop_fetch_auth_401",
    "hadToken=false",
    "no_token_attached",
)
CUSTOM_NATIVE_PROMPT_SUBMIT_MAX_CHARS = 12000
CODEX_DESKTOP_AUTH_BLOCKER_REFINABLE_REASONS = frozenset(
    {
        "cdp_renderer_input_surface_not_observed",
        "input_capable_window_not_proven_for_pid",
    }
)


def owner_authorization_phrase_present(value: str | None) -> bool:
    return isinstance(value, str) and value.strip() == OWNER_STANDING_AUTHORIZATION_PHRASE


def native_window_probe_command() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "command_id": "cmd-native-window-proof",
        "launch_mode": CUSTOM_LAUNCH_MODE,
        "operator_intent": "bounded_native_window_proof",
    }


def native_window_probe_server_plan() -> dict[str, Any]:
    return {
        "target_candidate_source": "repo_or_server_owned_launcher_candidate",
        "isolated_home_plan": True,
        "isolated_codex_home_plan": True,
        "isolated_profile_data_dir_plan": True,
        "isolated_app_support_dir_plan": True,
        "isolated_cache_dir_plan": True,
        "isolated_runtime_dir_plan": True,
        "keychain_reset_prompt_blocker_plan": True,
        "server_planned_route_endpoint": True,
        "port_separation_plan": True,
        "cleanup_command_plan": True,
        "rollback_expectation_declared": True,
        "current_codex_snapshot_plan": True,
        "write_surfaces_declared": True,
        "declared_write_surfaces": [
            "server_owned_temp_home",
            "server_owned_temp_codex_home",
            "server_owned_profile_dir",
            "server_owned_app_support_dir",
            "server_owned_cache_dir",
            "server_owned_runtime_dir",
            "launch_receipt",
        ],
    }


def _pid_from_process_line(line: str) -> int | None:
    prefix = line.split(" ", 1)[0].strip()
    return int(prefix) if prefix.isdigit() else None


def _custom_root_app_pids(process_inventory: dict[str, Any]) -> list[int]:
    custom_lines = process_inventory.get("custom_process_lines", [])
    if not isinstance(custom_lines, list):
        custom_lines = []
    custom_root_pids = sorted(
        {
            pid
            for line in custom_lines
            if isinstance(line, str) and "/Contents/MacOS/Codex" in line
            for pid in [_pid_from_process_line(line)]
            if pid is not None
        }
    )
    return custom_root_pids


def _parse_ax_point(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    parsed: list[int] = []
    for part in parts:
        try:
            parsed.append(int(float(part)))
        except ValueError:
            return []
    return parsed


def _window_bounds_from_ax(position: str, size: str) -> dict[str, int]:
    parsed_position = _parse_ax_point(position)
    parsed_size = _parse_ax_point(size)
    if len(parsed_position) != 2 or len(parsed_size) != 2:
        return {}
    return {
        "x": parsed_position[0],
        "y": parsed_position[1],
        "width": parsed_size[0],
        "height": parsed_size[1],
    }


def _window_observation_via_ax(process_inventory: dict[str, Any]) -> dict[str, Any]:
    root_pids = _custom_root_app_pids(process_inventory)
    if not root_pids:
        return build_native_window_observation_packet(
            window_observed=False,
            blocked_reason_class="custom_process_pid_not_observed",
        )
    observed_pid = int(root_pids[0])
    script = (
        'tell application "System Events"\n'
        f'  set p to first process whose unix id is {observed_pid}\n'
        '  set windowCount to count of windows of p\n'
        '  set windowPosition to ""\n'
        '  set windowSize to ""\n'
        '  if windowCount > 0 then\n'
        '    set w to window 1 of p\n'
        '    set {windowX, windowY} to position of w\n'
        '    set {windowWidth, windowHeight} to size of w\n'
        '    set windowPosition to (windowX as text) & "," & (windowY as text)\n'
        '    set windowSize to (windowWidth as text) & "," & (windowHeight as text)\n'
        '  end if\n'
        '  return (name of p as text) & tab & (visible of p as text) & tab & (frontmost of p as text) & tab & (background only of p as text) & tab & (windowCount as text) & tab & windowPosition & tab & windowSize\n'
        'end tell\n'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    parts = stdout.split("\t") if stdout else []
    visible = len(parts) >= 2 and parts[1].strip().lower() == "true"
    frontmost = len(parts) >= 3 and parts[2].strip().lower() == "true"
    background_only = len(parts) >= 4 and parts[3].strip().lower() == "true"
    try:
        window_count = int(parts[4].strip()) if len(parts) >= 5 else 0
    except ValueError:
        window_count = 0
    window_position = parts[5].strip() if len(parts) >= 6 else ""
    window_size = parts[6].strip() if len(parts) >= 7 else ""
    window_bounds = _window_bounds_from_ax(window_position, window_size)
    window_observed = (
        result.returncode == 0
        and bool(stdout)
        and window_count > 0
        and visible
        and not background_only
    )
    if window_observed:
        packet = build_native_window_observation_packet(window_observed=True)
        packet.update(
            {
                "observed_pid": observed_pid,
                "window_query": stdout,
                "window_query_method": "AX/System Events process window count",
                "window_query_rc": result.returncode,
                "window_query_error_class": "",
                "window_count": window_count,
                "window_frontmost": frontmost,
                "window_visible": visible,
                "window_background_only": background_only,
                "window_bounds": window_bounds,
                "window_position": window_position,
                "window_size": window_size,
            }
        )
        return packet
    cg_observed, cg_result = _cg_window_presence(observed_pid)
    if cg_observed:
        packet = build_native_window_observation_packet(window_observed=True)
        packet.update(
            {
                "observed_pid": observed_pid,
                "window_query": cg_result,
                "window_query_method": "CGWindowList pid-bound on-screen window",
                "window_query_rc": result.returncode,
                "window_query_error_class": "",
                "window_count": 1,
                "window_frontmost": frontmost,
                "window_visible": True,
                "window_background_only": background_only,
                "window_bounds": window_bounds,
                "window_position": window_position,
                "window_size": window_size,
                "ax_window_query": stdout,
                "ax_window_query_error_class": "SystemEventsInvalidIndex" if result.returncode else "",
                "ax_window_count": window_count,
            }
        )
        return packet
    packet = build_native_window_observation_packet(
        window_observed=False,
        blocked_reason_class="pid_visible_but_accessible_window_absent",
    )
    packet.update(
        {
            "observed_pid": observed_pid,
            "window_query": stdout,
            "window_query_method": "AX/System Events process window count",
            "window_query_rc": result.returncode,
            "window_query_error_class": "SystemEventsInvalidIndex" if result.returncode else "",
            "window_count": window_count,
            "window_frontmost": frontmost,
            "window_visible": visible,
            "window_background_only": background_only,
            "window_bounds": window_bounds,
            "window_position": window_position,
            "window_size": window_size,
        }
    )
    return packet


def _focus_custom_window_by_pid(
    observed_pid: int,
    *,
    target_position: tuple[int, int] = (120, 80),
    target_size: tuple[int, int] = (1320, 820),
) -> dict[str, Any]:
    script = (
        'tell application "System Events"\n'
        f'  set p to first process whose unix id is {observed_pid}\n'
        '  set visible of p to true\n'
        '  set frontmost of p to true\n'
        '  set windowCount to count of windows of p\n'
        '  set windowPosition to ""\n'
        '  set windowSize to ""\n'
        '  if windowCount > 0 then\n'
        '    set w to window 1 of p\n'
        f'    set position of w to {{{target_position[0]}, {target_position[1]}}}\n'
        f'    set size of w to {{{target_size[0]}, {target_size[1]}}}\n'
        '    set {windowX, windowY} to position of w\n'
        '    set {windowWidth, windowHeight} to size of w\n'
        '    set windowPosition to (windowX as text) & "," & (windowY as text)\n'
        '    set windowSize to (windowWidth as text) & "," & (windowHeight as text)\n'
        '  end if\n'
        '  return (name of p as text) & tab & (visible of p as text) & tab & (frontmost of p as text) & tab & (windowCount as text) & tab & windowPosition & tab & windowSize\n'
        'end tell\n'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.strip()
    parts = stdout.split("\t") if stdout else []
    visible = len(parts) >= 2 and parts[1].strip().lower() == "true"
    frontmost = len(parts) >= 3 and parts[2].strip().lower() == "true"
    try:
        window_count = int(parts[3].strip()) if len(parts) >= 4 else 0
    except ValueError:
        window_count = 0
    window_position = parts[4].strip() if len(parts) >= 5 else ""
    window_size = parts[5].strip() if len(parts) >= 6 else ""
    bounds = _window_bounds_from_ax(window_position, window_size)
    succeeded = result.returncode == 0 and visible and frontmost and window_count > 0
    return {
        "window_focus_action_attempted": True,
        "window_focus_action_succeeded": succeeded,
        "window_focus_query": stdout,
        "window_focus_query_rc": result.returncode,
        "window_focus_query_error_class": "" if result.returncode == 0 else "SystemEventsFocusFailed",
        "window_focus_stderr_bounded": result.stderr.strip()[:240],
        "window_focus_observed_pid": observed_pid,
        "window_focus_visible": visible,
        "window_focus_frontmost": frontmost,
        "window_focus_window_count": window_count,
        "window_focus_bounds": bounds,
    }


def show_custom_native_window_packet(
    *,
    persistent_profile_id: str = DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    persistent_profile_base_dir: Path | None = None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(
        profile_id=persistent_profile_id,
        base_dir=persistent_profile_base_dir,
    )
    user_data_dir = str(paths["user_data_dir"])
    inventory = collect_codex_process_inventory(custom_user_data_dir=user_data_dir)
    root_pids = _custom_root_app_pids(inventory)
    if not root_pids:
        return {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "packet_kind": "custom_codex_show_window",
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND",
            "human_message": "No Custom Codex process using the WBP profile was found.",
            "persistent_profile_id": persistent_profile_id,
            "persistent_user_data_dir": user_data_dir,
            "custom_process_observed": False,
            "custom_process_pid": None,
            "custom_window_observed": False,
            "custom_window_visible": False,
            "custom_window_frontmost": False,
            "window_focus_action_attempted": False,
            "window_focus_action_succeeded": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "next_action": "launch_custom_codex_first",
        }

    observed_pid = int(root_pids[0])
    before = _window_observation_via_ax(inventory)
    focus = _focus_custom_window_by_pid(observed_pid)
    after_inventory = collect_codex_process_inventory(custom_user_data_dir=user_data_dir)
    after = _window_observation_via_ax(after_inventory)
    usability_packet = _window_usability_from_observation(after)
    usability_packet = _apply_codex_desktop_auth_blocker(
        usability_packet,
        profile_dir=Path(str(paths["persistent_profile_root"])),
    )
    usability_packet, renderer_recovery_packet, recovered_after = _recover_startup_loader_if_needed(
        usability_packet,
        observed_pid=observed_pid,
        profile_dir=Path(str(paths["persistent_profile_root"])),
        custom_user_data_dir=user_data_dir,
    )
    if recovered_after is not None:
        after = recovered_after
    visible = after.get("window_observed") is True and after.get("window_visible") is True
    frontmost = after.get("window_frontmost") is True
    native_app_usable = usability_packet.get("native_window_usable") is True
    native_app_usability_source = (
        str(usability_packet.get("native_app_usability_source") or "input_capable_ui")
        if native_app_usable
        else "not_proven"
    )
    window_focused = focus.get("window_focus_action_succeeded") is True
    status_ok = visible and window_focused and native_app_usable
    window_visible_but_unusable = visible and window_focused and not native_app_usable
    desktop_auth_blocker = usability_packet.get("codex_desktop_auth_blocker_observed") is True
    usability_blocked_reason = str(usability_packet.get("blocked_reason_class") or "")
    renderer_surface_blocked_reason = str(
        usability_packet.get("renderer_surface_blocked_reason_class") or usability_blocked_reason
    )
    renderer_startup_loader_stuck = (
        renderer_surface_blocked_reason == "cdp_renderer_startup_loader_stuck"
    )
    return {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_show_window",
        "status": "ok" if status_ok else "blocked",
        "machine_error_code": (
            "OK"
            if status_ok
            else (
                "CUSTOM_CODEX_RENDERER_STARTUP_LOADER_STUCK"
                if window_visible_but_unusable and renderer_startup_loader_stuck
                else
                "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN"
                if window_visible_but_unusable
                else "CUSTOM_CODEX_WINDOW_VISIBILITY_NOT_PROVEN"
            )
        ),
        "human_message": (
            "Custom Codex window is visible, frontmost, and input-capable UI was proven."
            if status_ok
            else (
                "Custom Codex window is visible and frontmost, but Codex Desktop sign-in is required before input-capable UI can be proven."
                if window_visible_but_unusable and desktop_auth_blocker
                else "Custom Codex window is visible and frontmost, but the renderer is still on the startup loader."
                if window_visible_but_unusable and renderer_startup_loader_stuck
                else "Custom Codex window is visible and frontmost, but input-capable UI was not proven."
                if window_visible_but_unusable
                else "Custom Codex window could not be proven visible and frontmost."
            )
        ),
        "persistent_profile_id": persistent_profile_id,
        "persistent_user_data_dir": user_data_dir,
        "custom_process_observed": True,
        "custom_process_pid": observed_pid,
        "custom_window_observed": after.get("window_observed") is True,
        "custom_window_visible": visible,
        "custom_window_frontmost": frontmost,
        "custom_window_bounds": after.get("window_bounds", {}),
        "window_focus_action_attempted": focus.get("window_focus_action_attempted") is True,
        "window_focus_action_succeeded": focus.get("window_focus_action_succeeded") is True,
        "window_focus_packet": focus,
        "native_app_usable": native_app_usable,
        "input_capable_ui_observed": usability_packet.get("input_capable_ui_observed") is True,
        "native_app_usability_source": native_app_usability_source,
        "native_app_usability_blocked_reason_class": str(
            "" if native_app_usable else usability_packet.get("blocked_reason_class") or ""
        ),
        "cdp_localhost_only": usability_packet.get("cdp_localhost_only") is True,
        "cdp_endpoint_redacted": usability_packet.get("cdp_endpoint_redacted") is True,
        "cdp_target_bound_to_custom_launch": usability_packet.get("cdp_target_bound_to_custom_launch") is True,
        "cdp_editable_surface_observed": usability_packet.get("cdp_editable_surface_observed") is True,
        "raw_dom_exposed": usability_packet.get("raw_dom_exposed") is True,
        "raw_ax_tree_exposed": usability_packet.get("raw_ax_tree_exposed") is True,
        "browser_cdp_authority_widened": usability_packet.get("browser_cdp_authority_widened") is True,
        "codex_desktop_auth_blocker_observed": desktop_auth_blocker,
        "codex_desktop_auth_blocked_reason_class": str(
            usability_packet.get("codex_desktop_auth_blocked_reason_class") or ""
        ),
        "codex_desktop_auth_error_class": str(
            usability_packet.get("codex_desktop_auth_error_class") or ""
        ),
        "renderer_surface_blocked_reason_class": str(
            renderer_surface_blocked_reason if not native_app_usable else ""
        ),
        "renderer_startup_loader_observed": (
            usability_packet.get("renderer_startup_loader_observed") is True
        ),
        "renderer_mounted": usability_packet.get("renderer_mounted") is True,
        "renderer_recovery_attempted": renderer_recovery_packet.get("attempted") is True,
        "renderer_recovery_status": str(renderer_recovery_packet.get("status") or ""),
        "renderer_recovery_action": str(renderer_recovery_packet.get("action") or ""),
        "renderer_recovery_packet": renderer_recovery_packet,
        "native_window_usability_packet": usability_packet,
        "window_observation_before_focus": before,
        "window_observation_after_focus": after,
        "original_codex_touched": False,
        "asar_touched": False,
        "next_action": (
            "none"
            if status_ok
            else (
                "stop_and_diagnose_window_usability"
                if window_visible_but_unusable
                else "stop_and_diagnose_window_visibility"
            )
        ),
    }


def _wait_for_window_observation_via_ax(
    process_inventory: dict[str, Any],
    *,
    timeout_seconds: float = WINDOW_OBSERVATION_WAIT_SECONDS,
    poll_seconds: float = WINDOW_OBSERVATION_POLL_SECONDS,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_packet = _window_observation_via_ax(process_inventory)
    attempt_count = 1
    while last_packet.get("window_observed") is not True and time.time() < deadline:
        time.sleep(poll_seconds)
        last_packet = _window_observation_via_ax(process_inventory)
        attempt_count += 1
    last_packet["window_observation_attempt_count"] = attempt_count
    last_packet["window_observation_wait_seconds"] = timeout_seconds
    return last_packet


def _ax_input_capable(observed_pid: int) -> tuple[bool, str]:
    """Mechanism 0 (kept as fallback): pid-based AX front-window query."""
    script = (
        'tell application "System Events"\n'
        f'  set p to first process whose unix id is {observed_pid}\n'
        '  set w to front window of p\n'
        '  set hasField to false\n'
        '  try\n'
        '    set hasField to exists (first UI element of (entire contents of w) whose role is "AXTextField" or role is "AXTextArea")\n'
        '  end try\n'
        '  return {name of w, hasField}\n'
        'end tell\n'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.strip()
    if result.returncode != 0 or not stdout:
        return False, str(result.stderr.strip() or "ax_query_failed")
    parts = stdout.split(", ", 1)
    input_capable = len(parts) == 2 and parts[1].strip().lower() == "true"
    return input_capable, stdout


def _ax_input_capable_by_name(
    observed_pid: int, process_name: str = "Codex"
) -> tuple[bool, str]:
    """Mechanism 1: pid-bound AppleScript UI scripting with process-name guard."""
    script = (
        'tell application "System Events"\n'
        f'  set p to first process whose unix id is {observed_pid}\n'
        f'  if (name of p as text) is not "{process_name}" then error "pid_process_name_mismatch"\n'
        '  set w to front window of p\n'
        '  set hasField to false\n'
        '  try\n'
        '    set hasField to exists (first UI element of (entire contents of w) whose role is "AXTextField" or role is "AXTextArea")\n'
        '  end try\n'
        '  return (name of p as text) & tab & (name of w as text) & tab & (hasField as text)\n'
        'end tell\n'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.strip()
    if result.returncode != 0 or not stdout:
        return False, str(result.stderr.strip() or "ax_query_by_name_failed")
    parts = stdout.split("\t")
    input_capable = len(parts) >= 3 and parts[2].strip().lower() == "true"
    return input_capable, stdout


def _cg_input_capable(observed_pid: int) -> tuple[bool, str]:
    """Mechanism 2: CoreGraphics window list inspection.

    Uses CGWindowListCopyWindowInfo to find on-screen windows owned by the
    target pid. May expose windows that System Events does not report as
    accessible.
    """
    try:
        import Quartz  # type: ignore[import-untyped]
    except ImportError:
        return False, "cg_query_unavailable_pyobjc_framework_quartz_not_installed"
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    owned_windows = []
    for window in window_list:
        owner_pid = window.get("kCGWindowOwnerPID", 0)
        if owner_pid == observed_pid:
            owned_windows.append({
                "window_name": window.get("kCGWindowName", ""),
                "window_number": window.get("kCGWindowNumber", 0),
                "window_layer": window.get("kCGWindowLayer", 0),
                "window_owner_name": window.get("kCGWindowOwnerName", ""),
                "window_bounds": window.get("kCGWindowBounds", {}),
            })
    if owned_windows:
        return True, str(owned_windows[:5])
    return False, "cg_query_no_windows_found_for_pid"


def _cg_window_presence(observed_pid: int) -> tuple[bool, str]:
    """Pid-bound on-screen window proof when Accessibility window counts are unavailable."""
    cg_observed, cg_result = _cg_input_capable(observed_pid)
    if cg_observed:
        return True, cg_result
    return False, cg_result


def _read_exact(sock: socket.socket, byte_count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise OSError("websocket_closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _websocket_send_text(sock: socket.socket, payload: str) -> None:
    data = payload.encode("utf-8")
    if len(data) < 126:
        header = bytes([0x81, 0x80 | len(data)])
    elif len(data) < 65536:
        header = bytes([0x81, 0x80 | 126]) + len(data).to_bytes(2, "big")
    else:
        header = bytes([0x81, 0x80 | 127]) + len(data).to_bytes(8, "big")
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
    sock.sendall(header + mask + masked)


def _websocket_read_text(sock: socket.socket) -> str:
    first = _read_exact(sock, 2)
    opcode = first[0] & 0x0F
    length = first[1] & 0x7F
    if length == 126:
        length = int.from_bytes(_read_exact(sock, 2), "big")
    elif length == 127:
        length = int.from_bytes(_read_exact(sock, 8), "big")
    masked = bool(first[1] & 0x80)
    mask = _read_exact(sock, 4) if masked else b""
    payload = bytearray(_read_exact(sock, length))
    if masked:
        for index, byte in enumerate(payload):
            payload[index] = byte ^ mask[index % 4]
    if opcode == 8:
        raise OSError("websocket_closed")
    if opcode not in {1, 0}:
        return ""
    return payload.decode("utf-8", errors="replace")


def _cdp_command(ws_url: str, message: dict[str, Any], *, timeout_seconds: float = 2.0) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(ws_url)
    if parsed.scheme != "ws" or parsed.hostname != "127.0.0.1" or parsed.port is None:
        return {"status": "blocked", "error": "cdp_websocket_url_not_loopback"}
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    with socket.create_connection(("127.0.0.1", int(parsed.port)), timeout=timeout_seconds) as sock:
        sock.settimeout(timeout_seconds)
        sock.sendall(
            (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{parsed.port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            ).encode("ascii")
        )
        header = b""
        while b"\r\n\r\n" not in header:
            header += sock.recv(4096)
            if not header:
                raise OSError("cdp_websocket_handshake_empty")
        if b" 101 " not in header.split(b"\r\n", 1)[0]:
            return {"status": "blocked", "error": "cdp_websocket_handshake_not_upgraded"}
        _websocket_send_text(sock, json.dumps(message, separators=(",", ":")))
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            text = _websocket_read_text(sock)
            if not text:
                continue
            packet = json.loads(text)
            if packet.get("id") == message.get("id"):
                return packet
    return {"status": "blocked", "error": "cdp_response_timeout"}


def _devtools_port_owned_by_pid(observed_pid: int, port: int) -> tuple[bool, str]:
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        text=True,
        capture_output=True,
        check=False,
    )
    pids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not pids:
        return False, str(result.stderr.strip() or "cdp_port_not_listening")
    return str(observed_pid) in pids, ",".join(pids)


def _cdp_app_page_targets(port: int) -> tuple[list[dict[str, Any]], str]:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/list",
            timeout=1.5,
        ) as response:
            targets = json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"cdp_target_list_failed:{type(exc).__name__}"
    if not isinstance(targets, list):
        return [], "cdp_target_list_not_array"
    pages = [
        target
        for target in targets
        if isinstance(target, dict)
        and target.get("type") == "page"
        and str(target.get("url") or "").startswith("app://-/")
        and isinstance(target.get("webSocketDebuggerUrl"), str)
    ]
    if not pages:
        return [], "cdp_app_page_target_not_found"
    return pages, ""


def _cdp_input_capable(
    observed_pid: int,
    *,
    port: int = int(CODEX_REMOTE_DEBUGGING_PORT),
) -> tuple[bool, str]:
    port_owned, owner_result = _devtools_port_owned_by_pid(observed_pid, port)
    if not port_owned:
        return False, f"cdp_port_owner_mismatch_or_absent:{owner_result}"
    pages, page_error = _cdp_app_page_targets(port)
    if page_error:
        return False, page_error
    expression = """
(() => {
  const selector = 'textarea,input:not([type="hidden"]),[contenteditable="true"],[role="textbox"]';
  const visible = (node, minWidth = 1, minHeight = 1) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width >= minWidth && rect.height >= minHeight &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      node.getAttribute('aria-hidden') !== 'true';
  };
  const nodes = Array.from(document.querySelectorAll(selector));
  const visibleNodes = nodes.filter((node) => visible(node, 80, 20) && node.disabled !== true);
  const root = document.getElementById('root');
  const startupLoaders = Array.from(document.querySelectorAll('.startup-loader'));
  const visibleStartupLoaders = startupLoaders.filter((node) => visible(node));
  return {
    readyState: document.readyState,
    url: location.href,
    title: document.title,
    inputCandidateCount: nodes.length,
    visibleInputCandidateCount: visibleNodes.length,
    bodyTextLength: (document.body?.innerText || '').trim().length,
    rootChildCount: root ? root.children.length : 0,
    startupLoaderCount: startupLoaders.length,
    visibleStartupLoaderCount: visibleStartupLoaders.length,
    textValueCaptured: false,
    selector
  };
})()
""".strip()
    blocked_result: dict[str, Any] | None = None
    last_error = ""
    for index, page in enumerate(pages, start=1):
        try:
            cdp_result = _cdp_command(
                str(page["webSocketDebuggerUrl"]),
                {
                    "id": index,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                },
            )
        except (OSError, json.JSONDecodeError) as exc:
            last_error = f"cdp_runtime_evaluate_failed:{type(exc).__name__}"
            continue
        value = (
            (cdp_result.get("result") or {})
            .get("result", {})
            .get("value", {})
        )
        if not isinstance(value, dict):
            last_error = "cdp_runtime_evaluate_missing_value"
            continue
        input_capable = (
            value.get("url") == "app://-/index.html"
            and value.get("readyState") in {"interactive", "complete"}
            and int(value.get("visibleInputCandidateCount") or 0) > 0
            and value.get("textValueCaptured") is False
        )
        bounded = {
            "cdp_port": port,
            "cdp_port_owner_pids": owner_result,
            "cdp_page_target_count": len(pages),
            "cdp_target_url": page.get("url"),
            "cdp_target_type": page.get("type"),
            "cdp_ready_state": value.get("readyState"),
            "cdp_input_candidate_count": value.get("inputCandidateCount"),
            "cdp_visible_input_candidate_count": value.get("visibleInputCandidateCount"),
            "cdp_body_text_length": value.get("bodyTextLength"),
            "cdp_root_child_count": value.get("rootChildCount"),
            "cdp_startup_loader_count": value.get("startupLoaderCount"),
            "cdp_visible_startup_loader_count": value.get("visibleStartupLoaderCount"),
            "cdp_text_value_captured": value.get("textValueCaptured") is True,
            "cdp_prompt_attempted": False,
            "cdp_route_trace_bound": False,
            "browser_cdp_authority_widened": False,
        }
        if input_capable:
            return True, json.dumps(bounded, sort_keys=True)
        if blocked_result is None or value.get("url") == "app://-/index.html":
            blocked_result = bounded
    if blocked_result is not None:
        return False, json.dumps(blocked_result, sort_keys=True)
    return False, last_error or "cdp_runtime_evaluate_missing_value"


def _cdp_prompt_submit_blocked_packet(
    *,
    machine_error_code: str,
    human_message: str,
    prompt: str,
    request_id: str = "",
    blocking_reasons: list[str] | None = None,
    observed_pid: int | None = None,
    cdp_port: int = int(CODEX_REMOTE_DEBUGGING_PORT),
    cdp_result: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_native_prompt_submit",
        "captured_at_utc": utc_now(),
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "request_id": request_id,
        "blocking_reasons": blocking_reasons or [machine_error_code],
        "custom_process_pid": observed_pid,
        "cdp_port": cdp_port,
        "cdp_localhost_only": True,
        "cdp_endpoint_redacted": True,
        "cdp_target_bound_to_custom_launch": False,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if prompt
        else "",
        "prompt_length": len(prompt),
        "prompt_text_recorded": False,
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "browser_cdp_authority_widened": False,
        "input_text_insert_attempted": False,
        "input_text_insert_succeeded": False,
        "prompt_submitted": False,
        "submit_mechanism": "none",
        "cdp_result": cdp_result[:512],
        "secret_value_exposed": False,
        "next_action": "stop_and_diagnose_native_input_blocked",
    }


def _cdp_result_value(packet: dict[str, Any]) -> dict[str, Any]:
    value = (packet.get("result") or {}).get("result", {}).get("value", {})
    return value if isinstance(value, dict) else {}


def _cdp_submit_prompt_to_app_page(
    observed_pid: int,
    prompt: str,
    *,
    request_id: str,
    port: int = int(CODEX_REMOTE_DEBUGGING_PORT),
) -> dict[str, Any]:
    if not prompt:
        return _cdp_prompt_submit_blocked_packet(
            machine_error_code="CUSTOM_NATIVE_PROMPT_EMPTY",
            human_message="Native prompt submit requires a non-empty prompt.",
            prompt=prompt,
            request_id=request_id,
            observed_pid=observed_pid,
            cdp_port=port,
            blocking_reasons=["prompt_empty"],
        )
    if len(prompt) > CUSTOM_NATIVE_PROMPT_SUBMIT_MAX_CHARS:
        return _cdp_prompt_submit_blocked_packet(
            machine_error_code="CUSTOM_NATIVE_PROMPT_TOO_LONG",
            human_message="Native prompt submit refused an oversized prompt.",
            prompt=prompt,
            request_id=request_id,
            observed_pid=observed_pid,
            cdp_port=port,
            blocking_reasons=["prompt_too_long"],
        )
    port_owned, owner_result = _devtools_port_owned_by_pid(observed_pid, port)
    if not port_owned:
        return _cdp_prompt_submit_blocked_packet(
            machine_error_code="CDP_PORT_OWNER_MISMATCH_OR_ABSENT",
            human_message="Native prompt submit requires the Custom Codex renderer CDP port to be pid-bound.",
            prompt=prompt,
            request_id=request_id,
            observed_pid=observed_pid,
            cdp_port=port,
            blocking_reasons=["cdp_port_owner_mismatch_or_absent"],
            cdp_result=owner_result,
        )
    pages, page_error = _cdp_app_page_targets(port)
    if page_error:
        return _cdp_prompt_submit_blocked_packet(
            machine_error_code=page_error.upper(),
            human_message="Native prompt submit could not find a Custom Codex app page target.",
            prompt=prompt,
            request_id=request_id,
            observed_pid=observed_pid,
            cdp_port=port,
            blocking_reasons=[page_error],
            cdp_result=page_error,
        )

    focus_expression = """
(() => {
  const selector = 'textarea,input:not([type="hidden"]),[contenteditable="true"],[role="textbox"]';
  const visible = (node, minWidth = 80, minHeight = 20) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width >= minWidth && rect.height >= minHeight &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      node.getAttribute('aria-hidden') !== 'true';
  };
  const nodes = Array.from(document.querySelectorAll(selector));
  const node = nodes.find((candidate) => visible(candidate) && candidate.disabled !== true);
  if (!node) {
    return {
      focused: false,
      readyState: document.readyState,
      url: location.href,
      inputCandidateCount: nodes.length,
      visibleInputCandidateCount: nodes.filter((candidate) => visible(candidate)).length,
      textValueCaptured: false
    };
  }
  node.focus();
  if ('value' in node) {
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node), 'value');
    if (descriptor && descriptor.set) {
      descriptor.set.call(node, '');
    } else {
      node.value = '';
    }
  } else {
    node.textContent = '';
  }
  node.dispatchEvent(new InputEvent('input', {inputType: 'deleteContentBackward', bubbles: true, composed: true}));
  return {
    focused: document.activeElement === node,
    readyState: document.readyState,
    url: location.href,
    inputCandidateCount: nodes.length,
    visibleInputCandidateCount: nodes.filter((candidate) => visible(candidate)).length,
    textValueCaptured: false
  };
})()
""".strip()
    verify_expression = f"""
(() => {{
  const selector = 'textarea,input:not([type="hidden"]),[contenteditable="true"],[role="textbox"]';
  const visible = (node, minWidth = 80, minHeight = 20) => {{
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width >= minWidth && rect.height >= minHeight &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      node.getAttribute('aria-hidden') !== 'true';
  }};
  const nodes = Array.from(document.querySelectorAll(selector));
  const node = document.activeElement && visible(document.activeElement)
    ? document.activeElement
    : nodes.find((candidate) => visible(candidate) && candidate.disabled !== true);
  const text = node ? (('value' in node ? node.value : node.innerText) || '') : '';
  return {{
    inputFocused: !!node,
    insertedLengthMatches: text.length === {len(prompt)},
    insertedLength: text.length,
    expectedLength: {len(prompt)},
    textValueCaptured: false
  }};
}})()
""".strip()
    submit_expression = """
(() => {
  const selector = 'textarea,input:not([type="hidden"]),[contenteditable="true"],[role="textbox"]';
  const visible = (node, minWidth = 1, minHeight = 1) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width >= minWidth && rect.height >= minHeight &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      node.getAttribute('aria-hidden') !== 'true';
  };
  const textNode = document.activeElement || document.querySelector(selector);
  const buttons = Array.from(document.querySelectorAll('button'));
  const submitButton = buttons.find((button) => {
    if (!visible(button) || button.disabled) return false;
    const label = [
      button.getAttribute('aria-label') || '',
      button.getAttribute('title') || '',
      button.innerText || '',
      button.textContent || ''
    ].join(' ').toLowerCase();
    return button.type === 'submit' ||
      label.includes('send') ||
      label.includes('submit') ||
      label.includes('отправ') ||
      label.includes('arrow');
  });
  if (submitButton) {
    submitButton.click();
    return {
      submitted: true,
      submitButtonObserved: true,
      submitMechanism: 'cdp_button_click',
      textValueCaptured: false
    };
  }
  if (textNode) {
    textNode.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true}));
    textNode.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true}));
    return {
      submitted: true,
      submitButtonObserved: false,
      submitMechanism: 'cdp_keyboard_event_enter',
      textValueCaptured: false
    };
  }
  return {
    submitted: false,
    submitButtonObserved: false,
    submitMechanism: 'none',
    textValueCaptured: false
  };
})()
""".strip()

    last_error = ""
    for index, page in enumerate(pages, start=1):
        ws_url = str(page["webSocketDebuggerUrl"])
        try:
            focus_packet = _cdp_command(
                ws_url,
                {
                    "id": 3000 + index,
                    "method": "Runtime.evaluate",
                    "params": {"expression": focus_expression, "returnByValue": True},
                },
            )
            focus_value = _cdp_result_value(focus_packet)
            if focus_value.get("url") != "app://-/index.html":
                last_error = "cdp_target_url_mismatch"
                continue
            if focus_value.get("focused") is not True:
                last_error = "cdp_editable_focus_failed"
                continue
            insert_packet = _cdp_command(
                ws_url,
                {
                    "id": 3100 + index,
                    "method": "Input.insertText",
                    "params": {"text": prompt},
                },
            )
            if insert_packet.get("status") == "blocked" or "error" in insert_packet:
                last_error = "cdp_insert_text_failed"
                continue
            verify_packet = _cdp_command(
                ws_url,
                {
                    "id": 3200 + index,
                    "method": "Runtime.evaluate",
                    "params": {"expression": verify_expression, "returnByValue": True},
                },
            )
            verify_value = _cdp_result_value(verify_packet)
            if verify_value.get("insertedLengthMatches") is not True:
                last_error = "cdp_insert_text_verification_failed"
                continue
            submit_packet = _cdp_command(
                ws_url,
                {
                    "id": 3300 + index,
                    "method": "Runtime.evaluate",
                    "params": {"expression": submit_expression, "returnByValue": True},
                },
            )
            submit_value = _cdp_result_value(submit_packet)
            if submit_value.get("submitted") is not True:
                last_error = "cdp_submit_event_failed"
                continue
        except (OSError, json.JSONDecodeError) as exc:
            last_error = f"cdp_prompt_submit_failed:{type(exc).__name__}"
            continue
        return {
            "schema_version": 1,
            "packet_kind": "custom_codex_native_prompt_submit",
            "captured_at_utc": utc_now(),
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex native prompt text was inserted into the input-capable renderer and submitted.",
            "request_id": request_id,
            "custom_process_pid": observed_pid,
            "cdp_port": port,
            "cdp_port_owner_pids": owner_result,
            "cdp_page_target_count": len(pages),
            "cdp_target_url": str(page.get("url") or ""),
            "cdp_target_type": str(page.get("type") or ""),
            "cdp_localhost_only": True,
            "cdp_endpoint_redacted": True,
            "cdp_target_bound_to_custom_launch": True,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_length": len(prompt),
            "prompt_text_recorded": False,
            "raw_dom_exposed": False,
            "raw_ax_tree_exposed": False,
            "browser_cdp_authority_widened": False,
            "input_text_insert_attempted": True,
            "input_text_insert_succeeded": True,
            "prompt_submitted": True,
            "submit_button_observed": submit_value.get("submitButtonObserved") is True,
            "submit_mechanism": str(submit_value.get("submitMechanism") or ""),
            "secret_value_exposed": False,
            "next_action": "none",
        }
    return _cdp_prompt_submit_blocked_packet(
        machine_error_code="CUSTOM_NATIVE_CDP_PROMPT_SUBMIT_FAILED",
        human_message="Custom Codex native prompt submit could not prove insert and submit through the pid-bound renderer.",
        prompt=prompt,
        request_id=request_id,
        observed_pid=observed_pid,
        cdp_port=port,
        blocking_reasons=[last_error or "cdp_prompt_submit_failed"],
        cdp_result=last_error,
    )


def submit_custom_native_window_prompt_packet(
    *,
    prompt: str,
    request_id: str,
    persistent_profile_id: str = DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    persistent_profile_base_dir: Path | None = None,
) -> dict[str, Any]:
    show_packet = show_custom_native_window_packet(
        persistent_profile_id=persistent_profile_id,
        persistent_profile_base_dir=persistent_profile_base_dir,
    )
    observed_pid = show_packet.get("custom_process_pid")
    if (
        show_packet.get("status") != "ok"
        or show_packet.get("native_app_usable") is not True
        or not isinstance(observed_pid, int)
    ):
        return _cdp_prompt_submit_blocked_packet(
            machine_error_code=str(
                show_packet.get("machine_error_code")
                or "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN"
            ),
            human_message="Native prompt submit requires a visible, input-capable Custom Codex window.",
            prompt=prompt,
            request_id=request_id,
            blocking_reasons=["native_window_not_input_capable"],
            observed_pid=observed_pid if isinstance(observed_pid, int) else None,
            cdp_result=str(show_packet.get("native_app_usability_blocked_reason_class") or ""),
        ) | {
            "native_window_observed": show_packet.get("custom_window_observed") is True,
            "input_capable_ui_observed": show_packet.get("input_capable_ui_observed") is True,
            "show_window_packet": show_packet,
        }
    packet = _cdp_submit_prompt_to_app_page(
        int(observed_pid),
        prompt,
        request_id=request_id,
    )
    packet["native_window_observed"] = show_packet.get("custom_window_observed") is True
    packet["input_capable_ui_observed"] = show_packet.get("input_capable_ui_observed") is True
    packet["native_app_usable"] = show_packet.get("native_app_usable") is True
    packet["show_window_packet"] = show_packet
    return packet


def _renderer_recovery_packet(
    *,
    status: str,
    machine_error_code: str,
    reason_class: str = "",
    attempted: bool = True,
    action: str = "cdp_page_reload",
    port: int = int(CODEX_REMOTE_DEBUGGING_PORT),
    owner_pids: str = "",
    reload_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = reload_targets or []
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_renderer_recovery",
        "status": status,
        "machine_error_code": machine_error_code,
        "reason_class": reason_class,
        "attempted": attempted,
        "action": action if attempted else "none",
        "cdp_port": port,
        "cdp_port_owner_pids": owner_pids,
        "cdp_localhost_only": True,
        "cdp_endpoint_redacted": True,
        "cdp_target_bound_to_custom_launch": True,
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "browser_cdp_authority_widened": False,
        "browser_route_injection": False,
        "reload_attempt_count": len(targets),
        "reload_targets": targets,
    }


def _renderer_recovery_not_required_packet() -> dict[str, Any]:
    return _renderer_recovery_packet(
        status="not_required",
        machine_error_code="NOT_REQUIRED",
        reason_class="",
        attempted=False,
    )


def _renderer_startup_loader_stuck(usability_packet: dict[str, Any]) -> bool:
    reason = str(
        usability_packet.get("renderer_surface_blocked_reason_class")
        or usability_packet.get("blocked_reason_class")
        or ""
    )
    return reason == "cdp_renderer_startup_loader_stuck"


def _cdp_reload_app_page_for_pid(
    observed_pid: int,
    *,
    port: int = int(CODEX_REMOTE_DEBUGGING_PORT),
) -> dict[str, Any]:
    port_owned, owner_result = _devtools_port_owned_by_pid(observed_pid, port)
    if not port_owned:
        return _renderer_recovery_packet(
            status="blocked",
            machine_error_code="CDP_PORT_OWNER_MISMATCH_OR_ABSENT",
            reason_class="cdp_port_owner_mismatch_or_absent",
            port=port,
            owner_pids=owner_result,
            reload_targets=[],
        )
    pages, page_error = _cdp_app_page_targets(port)
    if page_error:
        return _renderer_recovery_packet(
            status="blocked",
            machine_error_code=page_error.upper(),
            reason_class=page_error,
            port=port,
            owner_pids=owner_result,
            reload_targets=[],
        )
    reload_targets: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        attempt = {
            "target_url": str(page.get("url") or ""),
            "target_type": str(page.get("type") or ""),
            "reload_ok": False,
            "error_class": "",
        }
        try:
            reload_result = _cdp_command(
                str(page["webSocketDebuggerUrl"]),
                {
                    "id": 100 + index,
                    "method": "Page.reload",
                    "params": {"ignoreCache": True},
                },
            )
        except (OSError, json.JSONDecodeError) as exc:
            attempt["error_class"] = f"cdp_page_reload_failed:{type(exc).__name__}"
            reload_targets.append(attempt)
            continue
        if reload_result.get("status") == "blocked":
            attempt["error_class"] = str(reload_result.get("error") or "cdp_page_reload_blocked")
        elif "error" in reload_result:
            attempt["error_class"] = "cdp_page_reload_protocol_error"
        else:
            attempt["reload_ok"] = True
        reload_targets.append(attempt)
    if any(target.get("reload_ok") is True for target in reload_targets):
        return _renderer_recovery_packet(
            status="ok",
            machine_error_code="OK",
            reason_class="",
            port=port,
            owner_pids=owner_result,
            reload_targets=reload_targets,
        )
    return _renderer_recovery_packet(
        status="blocked",
        machine_error_code="CDP_PAGE_RELOAD_FAILED",
        reason_class="cdp_page_reload_failed",
        port=port,
        owner_pids=owner_result,
        reload_targets=reload_targets,
    )


def _recover_startup_loader_if_needed(
    usability_packet: dict[str, Any],
    *,
    observed_pid: int,
    profile_dir: Path,
    custom_user_data_dir: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    if not _renderer_startup_loader_stuck(usability_packet):
        return usability_packet, _renderer_recovery_not_required_packet(), None
    recovery_packet = _cdp_reload_app_page_for_pid(observed_pid)
    if recovery_packet.get("status") != "ok":
        return usability_packet, recovery_packet, None
    time.sleep(CODEX_RENDERER_RECOVERY_WAIT_SECONDS)
    recovered_inventory = collect_codex_process_inventory(
        custom_user_data_dir=custom_user_data_dir
    )
    recovered_observation = _window_observation_via_ax(recovered_inventory)
    recovered_usability = _window_usability_from_observation(recovered_observation)
    recovered_usability = _apply_codex_desktop_auth_blocker(
        recovered_usability,
        profile_dir=profile_dir,
    )
    return recovered_usability, recovery_packet, recovered_observation


def _post_launch_usability_recheck_packet(
    *,
    attempted: bool,
    status: str,
    machine_error_code: str,
    attempt_count: int = 0,
    timeout_seconds: float = 0.0,
    reason_class: str = "",
    usability_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    usability = usability_packet if isinstance(usability_packet, dict) else {}
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_post_launch_usability_recheck",
        "captured_at_utc": utc_now(),
        "attempted": attempted,
        "status": status,
        "machine_error_code": machine_error_code,
        "attempt_count": attempt_count,
        "timeout_seconds": timeout_seconds,
        "reason_class": reason_class,
        "native_app_usable": usability.get("native_window_usable") is True,
        "input_capable_ui_observed": usability.get("input_capable_ui_observed") is True,
        "native_app_usability_source": str(
            usability.get("native_app_usability_source") or ""
        ),
        "native_app_usability_blocked_reason_class": str(
            usability.get("blocked_reason_class") or ""
        ),
        "cdp_localhost_only": usability.get("cdp_localhost_only") is True,
        "cdp_target_bound_to_custom_launch": (
            usability.get("cdp_target_bound_to_custom_launch") is True
        ),
        "cdp_editable_surface_observed": (
            usability.get("cdp_editable_surface_observed") is True
        ),
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "browser_cdp_authority_widened": False,
    }


def _post_launch_usability_recheck_candidate(
    usability_packet: dict[str, Any],
) -> bool:
    blocked_reason = str(usability_packet.get("blocked_reason_class") or "")
    renderer_reason = str(
        usability_packet.get("renderer_surface_blocked_reason_class")
        or blocked_reason
    )
    return bool(
        usability_packet.get("native_window_usable") is not True
        and (
            usability_packet.get("cdp_target_bound_to_custom_launch") is True
            or renderer_reason.startswith("cdp_renderer_")
            or blocked_reason.startswith("cdp_renderer_")
        )
    )


def _wait_for_post_launch_window_usability(
    *,
    initial_window_packet: dict[str, Any],
    profile_dir: Path,
    custom_user_data_dir: str,
    timeout_seconds: float = POST_LAUNCH_USABILITY_RECHECK_SECONDS,
    poll_seconds: float = POST_LAUNCH_USABILITY_RECHECK_POLL_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    attempt_count = 0
    window_packet = initial_window_packet
    usability_packet: dict[str, Any] = {}
    while True:
        attempt_count += 1
        inventory = collect_codex_process_inventory(
            custom_user_data_dir=custom_user_data_dir
        )
        window_packet = _window_observation_via_ax(inventory)
        usability_packet = _window_usability_from_observation(window_packet)
        usability_packet = _apply_codex_desktop_auth_blocker(
            usability_packet,
            profile_dir=profile_dir,
        )
        if usability_packet.get("native_window_usable") is True:
            return (
                _post_launch_usability_recheck_packet(
                    attempted=True,
                    status="ok",
                    machine_error_code="OK",
                    attempt_count=attempt_count,
                    timeout_seconds=timeout_seconds,
                    usability_packet=usability_packet,
                ),
                window_packet,
                usability_packet,
            )
        if time.time() >= deadline:
            return (
                _post_launch_usability_recheck_packet(
                    attempted=True,
                    status="blocked",
                    machine_error_code="POST_LAUNCH_WINDOW_USABILITY_RECHECK_NOT_PROVEN",
                    attempt_count=attempt_count,
                    timeout_seconds=timeout_seconds,
                    reason_class=str(usability_packet.get("blocked_reason_class") or ""),
                    usability_packet=usability_packet,
                ),
                window_packet,
                usability_packet,
            )
        time.sleep(poll_seconds)


def _cdp_blocked_surface_details(result: str) -> dict[str, Any]:
    try:
        packet = json.loads(result)
    except json.JSONDecodeError:
        return {}
    if not isinstance(packet, dict):
        return {}
    target_url = str(packet.get("cdp_target_url") or "")
    ready_state = str(packet.get("cdp_ready_state") or "")
    try:
        visible_count = int(packet.get("cdp_visible_input_candidate_count") or 0)
    except (TypeError, ValueError):
        visible_count = -1
    try:
        startup_loader_count = int(packet.get("cdp_startup_loader_count") or 0)
    except (TypeError, ValueError):
        startup_loader_count = 0
    try:
        visible_startup_loader_count = int(packet.get("cdp_visible_startup_loader_count") or 0)
    except (TypeError, ValueError):
        visible_startup_loader_count = 0
    if target_url == "app://-/index.html" and ready_state in {"interactive", "complete"} and visible_count <= 0:
        startup_loader_observed = startup_loader_count > 0 or visible_startup_loader_count > 0
        reason_class = (
            "cdp_renderer_startup_loader_stuck"
            if startup_loader_observed
            else "cdp_renderer_input_surface_not_observed"
        )
        usability_source = (
            "cdp_renderer_startup_loader_without_editable_surface"
            if startup_loader_observed
            else "cdp_renderer_target_without_editable_surface"
        )
        return {
            "blocked_reason_class": reason_class,
            "renderer_surface_blocked_reason_class": reason_class,
            "native_app_usability_source": usability_source,
            "cdp_localhost_only": True,
            "cdp_endpoint_redacted": True,
            "cdp_target_bound_to_custom_launch": True,
            "cdp_editable_surface_observed": False,
            "renderer_startup_loader_observed": startup_loader_observed,
            "renderer_mounted": not startup_loader_observed,
            "raw_dom_exposed": False,
            "raw_ax_tree_exposed": False,
            "browser_cdp_authority_widened": False,
        }
    return {}


def _latest_launch_stderr_segment(text: str) -> str:
    marker = "DevTools listening"
    index = text.rfind(marker)
    return text[index:] if index >= 0 else text


def _codex_desktop_auth_blocker_from_profile(
    profile_dir: Path,
    *,
    launcher_stderr_path: Path | str | None = None,
) -> dict[str, Any]:
    stderr_path = (
        Path(launcher_stderr_path)
        if launcher_stderr_path is not None
        else profile_dir / "tmp" / "launcher.stderr.log"
    )
    try:
        text = stderr_path.read_text(errors="replace")
    except OSError:
        return {
            "codex_desktop_auth_blocker_observed": False,
            "codex_desktop_auth_blocked_reason_class": "",
            "codex_desktop_auth_diagnostic_source": "launcher_stderr_missing",
        }
    segment = _latest_launch_stderr_segment(text)
    sign_in_required = CODEX_DESKTOP_SIGN_IN_REQUIRED_MARKER in segment
    no_token_auth_401 = all(marker in segment for marker in CODEX_DESKTOP_NO_TOKEN_AUTH_MARKERS)
    if not sign_in_required and not no_token_auth_401:
        return {
            "codex_desktop_auth_blocker_observed": False,
            "codex_desktop_auth_blocked_reason_class": "",
            "codex_desktop_auth_diagnostic_source": "launcher_stderr_latest_segment",
        }
    return {
        "codex_desktop_auth_blocker_observed": True,
        "codex_desktop_auth_blocked_reason_class": (
            "codex_desktop_sign_in_required_for_renderer_surface"
        ),
        "codex_desktop_auth_error_class": (
            "codex_desktop_remote_control_authorization_sign_in_required"
            if sign_in_required
            else "codex_desktop_chatgpt_auth_token_missing"
        ),
        "codex_desktop_auth_diagnostic_source": "launcher_stderr_latest_segment",
        "launcher_stderr_redacted": True,
    }


def _codex_desktop_profile_auth_state_blocker(profile_dir: Path) -> dict[str, Any]:
    custom_home_dir = profile_dir / "home"
    if not custom_home_dir.exists():
        return {
            "codex_desktop_auth_blocker_observed": False,
            "codex_desktop_auth_blocked_reason_class": "",
            "codex_desktop_auth_error_class": "",
            "codex_desktop_auth_diagnostic_source": "custom_profile_home_missing",
        }
    desktop_auth_json = (
        custom_home_dir
        / "Library"
        / "Application Support"
        / "Codex"
        / "auth.json"
    )
    if desktop_auth_json.is_file():
        return {
            "codex_desktop_auth_blocker_observed": False,
            "codex_desktop_auth_blocked_reason_class": "",
            "codex_desktop_auth_error_class": "",
            "codex_desktop_auth_diagnostic_source": "custom_profile_chatgpt_auth_state_present",
            "desktop_auth_state_path_redacted": True,
        }
    return {
        "codex_desktop_auth_blocker_observed": True,
        "codex_desktop_auth_blocked_reason_class": (
            "codex_desktop_sign_in_required_for_renderer_surface"
        ),
        "codex_desktop_auth_error_class": (
            "codex_desktop_custom_profile_chatgpt_auth_state_missing"
        ),
        "codex_desktop_auth_diagnostic_source": (
            "custom_profile_chatgpt_auth_state_missing"
        ),
        "desktop_auth_state_path_redacted": True,
    }


def _apply_codex_desktop_auth_blocker(
    usability_packet: dict[str, Any],
    *,
    profile_dir: Path,
    launcher_stderr_path: Path | str | None = None,
    allow_profile_auth_state_fallback: bool = False,
    profile_auth_state_fallback_allowed_by_current_launch: bool = False,
) -> dict[str, Any]:
    blocked_reason_class = str(usability_packet.get("blocked_reason_class") or "")
    if blocked_reason_class not in CODEX_DESKTOP_AUTH_BLOCKER_REFINABLE_REASONS:
        return usability_packet
    if launcher_stderr_path is None:
        return usability_packet
    auth_blocker = _codex_desktop_auth_blocker_from_profile(
        profile_dir,
        launcher_stderr_path=launcher_stderr_path,
    )
    if (
        auth_blocker.get("codex_desktop_auth_blocker_observed") is not True
        and allow_profile_auth_state_fallback
        and profile_auth_state_fallback_allowed_by_current_launch
    ):
        auth_blocker = _codex_desktop_profile_auth_state_blocker(profile_dir)
    if auth_blocker.get("codex_desktop_auth_blocker_observed") is not True:
        return usability_packet
    packet = dict(usability_packet)
    packet.update(auth_blocker)
    packet["renderer_surface_blocked_reason_class"] = str(
        usability_packet.get("renderer_surface_blocked_reason_class")
        or blocked_reason_class
    )
    packet["blocked_reason_class"] = str(
        auth_blocker["codex_desktop_auth_blocked_reason_class"]
    )
    packet["native_app_usability_source"] = "codex_desktop_auth_blocker"
    return packet


def _bounded_recheck_codex_desktop_auth_blocker(
    usability_packet: dict[str, Any],
    *,
    profile_dir: Path,
    launcher_stderr_path: Path | str | None,
    allow_profile_auth_state_fallback: bool = False,
    profile_auth_state_fallback_allowed_by_current_launch: bool = False,
) -> dict[str, Any]:
    if usability_packet.get("codex_desktop_auth_blocker_observed") is True:
        return usability_packet
    if usability_packet.get("native_window_usable") is True:
        return usability_packet
    if launcher_stderr_path is None:
        return usability_packet
    deadline = time.time() + CODEX_DESKTOP_AUTH_BLOCKER_RECHECK_SECONDS
    current_packet = usability_packet
    while time.time() < deadline:
        time.sleep(CODEX_DESKTOP_AUTH_BLOCKER_RECHECK_POLL_SECONDS)
        current_packet = _apply_codex_desktop_auth_blocker(
            current_packet,
            profile_dir=profile_dir,
            launcher_stderr_path=launcher_stderr_path,
            allow_profile_auth_state_fallback=allow_profile_auth_state_fallback,
            profile_auth_state_fallback_allowed_by_current_launch=(
                profile_auth_state_fallback_allowed_by_current_launch
            ),
        )
        if current_packet.get("codex_desktop_auth_blocker_observed") is True:
            return current_packet
    return current_packet


def _custom_native_launch_blocked_machine_error(
    *,
    launcher_failed_before_process: bool,
    process_started: bool,
    process_still_alive: bool,
    custom_window_visible: bool,
    native_app_usable: bool,
    desktop_auth_blocker: bool,
    renderer_surface_blocked_reason: str,
) -> str:
    if launcher_failed_before_process:
        return "CUSTOM_NATIVE_LAUNCHER_EXIT_NONZERO"
    if process_started and not process_still_alive:
        return "CUSTOM_NATIVE_PROCESS_EXITED_AFTER_START"
    if desktop_auth_blocker:
        return "CUSTOM_NATIVE_CODEX_DESKTOP_AUTH_REQUIRED"
    if custom_window_visible and not native_app_usable:
        if renderer_surface_blocked_reason == "cdp_renderer_startup_loader_stuck":
            return "CUSTOM_NATIVE_RENDERER_STARTUP_LOADER_STUCK"
        return "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN"
    return "CUSTOM_NATIVE_WINDOW_NOT_PROVEN"


def _custom_native_launch_blocked_human_message(
    *,
    launcher_failed_before_process: bool,
    process_started: bool,
    process_still_alive: bool,
    custom_window_visible: bool,
    native_app_usable: bool,
    desktop_auth_blocker: bool,
    renderer_surface_blocked_reason: str,
) -> str:
    if launcher_failed_before_process:
        return "Custom Codex launcher exited before a Custom process was observed."
    if process_started and not process_still_alive:
        return "Custom Codex process was observed after launch, then exited before proof completed."
    if desktop_auth_blocker:
        return "Custom Codex native launch reached Codex Desktop, but Codex Desktop sign-in is required before input-capable UI can be proven."
    if (
        custom_window_visible
        and not native_app_usable
        and renderer_surface_blocked_reason == "cdp_renderer_startup_loader_stuck"
    ):
        return "Custom Codex native window was observed, but the renderer is still on the startup loader."
    if custom_window_visible and not native_app_usable:
        return "Custom Codex native window was observed, but input-capable UI was not proven."
    return "Custom Codex native launch did not satisfy process/window proof."


def _window_usability_from_observation(window_observation: dict[str, Any]) -> dict[str, Any]:
    window_observed = window_observation.get("window_observed") is True
    if not window_observed:
        return build_native_window_usability_packet(
            window_observed=False,
            input_capable_ui_observed=False,
            blocked_reason_class="input_capable_window_not_proven_for_pid",
        )
    observed_pid = window_observation.get("observed_pid")
    if not isinstance(observed_pid, int):
        return build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=False,
            blocked_reason_class="observed_pid_missing_for_input_capable_query",
        )
    input_capable_m1, result_m1 = _ax_input_capable_by_name(observed_pid)
    if input_capable_m1:
        packet = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=True,
            blocked_reason_class="",
        )
        packet.update({
            "ax_query_result": result_m1,
            "input_capable_query_method": "AX/System Events process-name UI scripting (Mechanism 1)",
        })
        return packet
    input_capable_m0, result_m0 = _ax_input_capable(observed_pid)
    if input_capable_m0:
        packet = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=True,
            blocked_reason_class="",
        )
        packet.update({
            "ax_query_result": f"mechanism_1_pid_guarded: {result_m1}; mechanism_0_pid_fallback: {result_m0}",
            "input_capable_query_method": "AX/System Events pid-bound UI scripting fallback (Mechanism 0)",
        })
        return packet
    input_capable_cdp, result_cdp = _cdp_input_capable(observed_pid)
    if input_capable_cdp:
        packet = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=True,
            blocked_reason_class="",
        )
        packet.update({
            "ax_query_result": (
                f"mechanism_1_pid_guarded: {result_m1}; "
                f"mechanism_0_pid_fallback: {result_m0}; "
                f"mechanism_cdp_pid_bound_dom_input: {result_cdp}"
            ),
            "input_capable_query_method": "CDP localhost launched-renderer DOM/AX editable-surface proof",
            "native_app_usability_source": "cdp_renderer_input_capable_ui",
            "cdp_localhost_only": True,
            "cdp_endpoint_redacted": True,
            "cdp_target_bound_to_custom_launch": True,
            "cdp_editable_surface_observed": True,
            "raw_dom_exposed": False,
            "raw_ax_tree_exposed": False,
            "browser_cdp_authority_widened": False,
        })
        return packet
    cdp_blocked_surface = _cdp_blocked_surface_details(result_cdp)
    if cdp_blocked_surface:
        packet = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=False,
            blocked_reason_class=str(cdp_blocked_surface["blocked_reason_class"]),
        )
        packet.update({
            "ax_query_result": (
                f"mechanism_1_pid_guarded: {result_m1}; "
                f"mechanism_0_pid_fallback: {result_m0}; "
                f"mechanism_cdp_pid_bound_dom_input: {result_cdp}"
            ),
            "input_capable_query_method": (
                "CDP localhost launched-renderer target observed, editable surface not proven"
            ),
            **cdp_blocked_surface,
        })
        return packet
    input_capable_m2, result_m2 = _cg_input_capable(observed_pid)
    query_result = (
        f"mechanism_1_pid_guarded: {result_m1}; "
        f"mechanism_0_pid_fallback: {result_m0}; "
        f"mechanism_cdp_pid_bound_dom_input: {result_cdp}; "
        f"mechanism_2_cg_pid_window_only: {result_m2}"
    )
    query_method = (
        "CGWindowList inspection (pid-bound window present, input-capable UI not proven)"
        if input_capable_m2
        else "all mechanisms blocked"
    )
    packet = build_native_window_usability_packet(
        window_observed=True,
        input_capable_ui_observed=False,
        blocked_reason_class=(
            "input_capable_ui_not_proven_for_pid_window_present"
            if input_capable_m2
            else "input_capable_window_not_proven_for_pid"
        ),
    )
    packet.update({
        "ax_query_result": query_result,
        "input_capable_query_method": query_method,
    })
    return packet


def _runtime_ready_stdout_paths(
    launch_result: dict[str, Any],
    layout: NativeProbeLayout,
) -> list[Path]:
    paths: list[Path] = []
    stdout_path_value = launch_result.get("launcher_stdout_path")
    if not isinstance(stdout_path_value, str) or not stdout_path_value:
        return []
    paths.append(Path(stdout_path_value))
    paths.append(layout.profile_dir / "tmp" / "launcher.stdout.log")
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _latest_launch_stdout_segment(text: str) -> str:
    marker = "wbp launch app path:"
    index = text.rfind(marker)
    return text[index:] if index >= 0 else text


def _runtime_ready_from_launcher_stdout(
    launch_result: dict[str, Any],
    layout: NativeProbeLayout,
    *,
    timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    stdout_paths = _runtime_ready_stdout_paths(launch_result, layout)
    if not stdout_paths:
        return {
            "runtime_ready_observed": False,
            "runtime_ready_source": "launcher_stdout_unavailable",
            "runtime_ready_stdout_paths_checked": [],
            "runtime_ready_markers": list(RUNTIME_READY_STDOUT_MARKERS),
            "runtime_ready_missing_markers": list(RUNTIME_READY_STDOUT_MARKERS),
        }

    deadline = time.time() + timeout_seconds
    text = ""
    while time.time() <= deadline:
        for stdout_path in stdout_paths:
            try:
                text = _latest_launch_stdout_segment(
                    stdout_path.read_text(encoding="utf-8", errors="replace")
                )
            except FileNotFoundError:
                text = ""
            missing = [marker for marker in RUNTIME_READY_STDOUT_MARKERS if marker not in text]
            if not missing:
                return {
                    "runtime_ready_observed": True,
                    "runtime_ready_source": "launcher_stdout_markers",
                    "runtime_ready_stdout_paths_checked": [str(path) for path in stdout_paths],
                    "runtime_ready_markers": list(RUNTIME_READY_STDOUT_MARKERS),
                    "runtime_ready_missing_markers": [],
                }
        time.sleep(0.5)

    return {
        "runtime_ready_observed": False,
        "runtime_ready_source": "launcher_stdout_markers",
        "runtime_ready_stdout_paths_checked": [str(path) for path in stdout_paths],
        "runtime_ready_markers": list(RUNTIME_READY_STDOUT_MARKERS),
        "runtime_ready_missing_markers": missing,
    }


def _build_identity_binding(
    window_packet: dict[str, Any],
    layout: NativeProbeLayout,
    launch_result: dict[str, Any],
) -> dict[str, Any]:
    window_observed = window_packet.get("window_observed") is True
    window_name = window_packet.get("window_query", "")
    observed_pid = window_packet.get("observed_pid")
    startup_inventory = launch_result.get("startup_inventory", {})
    custom_root_pids = _custom_root_app_pids(startup_inventory) if isinstance(startup_inventory, dict) else []
    bound = (
        window_observed
        and isinstance(window_name, str)
        and len(window_name) > 0
        and isinstance(observed_pid, int)
        and observed_pid in custom_root_pids
    )
    distinguishable = bound and "/Applications/Codex.app/Contents/MacOS/Codex" in str(
        launch_result.get("startup_inventory", {}).get("sample", [])
    )
    identity_chain = [
        "repo_canonical_custom_proxy_auth_isolated_home",
        str(layout.launcher_path),
        "/Applications/Codex.app/Contents/MacOS/Codex",
        f"process_group_or_pid:{launch_result['launcher_pid']}",
        f"window_binding:{'proven' if bound else 'unproven'}",
    ]
    if bound and window_name:
        identity_chain.append(f"window_ax_visible:{window_name}")
    return {
        "captured_at_utc": utc_now(),
        "status": "ok" if bound else "blocked",
        "machine_error_code": "OK" if bound else "NATIVE_WINDOW_IDENTITY_NOT_PROVEN",
        "window_bound_to_custom_launch": bound,
        "window_distinguishable_from_original_codex": distinguishable,
        "identity_chain": identity_chain,
    }


def launch_custom_native_app_packet(
    *,
    repo_root: Path,
    endpoint: str,
    model: str,
    owner_authorization_phrase: str | None = None,
    persistent_profile_id: str = DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    persistent_profile_base_dir: Path | None = None,
    keep_running_on_window_observed: bool = False,
    reuse_existing_window_if_present: bool = False,
    agent_runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    admission = build_native_custom_preflight_packet(
        native_window_probe_command(),
        native_window_probe_server_plan(),
    )
    auth = build_native_dispatch_authorization_packet(
        owner_authorized=owner_authorization_phrase_present(owner_authorization_phrase),
        admission_packet=admission,
    )
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "dry_run": False,
        "launch_source": "wbp_web_ui",
        "owner_authorization_phrase_present": auth["owner_authorized"],
        "running_status": False,
        "process_started": False,
        "expected_custom_identity_observed": False,
        "native_window_observed": False,
        "native_app_usable": False,
        "real_codex_app_launched": False,
        "isolated_home": False,
        "isolated_codex_home": False,
        "isolated_profile_dir": False,
        "isolated_app_support_dir": False,
        "isolated_cache_dir": False,
        "isolated_runtime_dir": False,
        "server_owned_route_configuration": False,
        "browser_route_injection": False,
        "browser_backend_injection": False,
        "current_original_profile_shortcut_used": False,
        "current_codex_touched": False,
        "keychain_reset_prompt_observed": False,
        "prompt_surface_observed": False,
        "route_trace_bound": False,
        "workbench_ready": False,
        "native_launch_complete": False,
        "cleanup_deferred_while_running": False,
        "cleanup_command_planned": True,
        "launch_claim_scope": "custom_native_app_window_launch_only",
        "keychain_preflight_attempted": False,
        "keychain_preflight_status": "",
        "keychain_preflight_reason_code": "",
        "isolated_default_keychain_verified": False,
        "isolated_search_list_verified": False,
        "real_user_keychain_modified": False,
        "keychain_item_read": False,
        "keychain_reset_performed": False,
        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
        "profile_mode": "persistent_custom",
        "persistent_profile_id": persistent_profile_id,
        "persistent_profile_root": "",
        "persistent_codex_home": "",
        "persistent_home_dir": "",
        "persistent_user_data_dir": "",
        "persistent_runtime_tmp_dir": "",
        "temp_profile_used": False,
        "history_persistence_expected": True,
        "visible_thread_history_restored_proven": False,
        "cleanup_deletes_persistent_profile_by_default": False,
        "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
        "browser_client_path_authority": False,
        "original_codex_profile_runtime_dependency": False,
        "prelaunch_existing_custom_process_stop_attempted": False,
        "prelaunch_existing_custom_processes_gone": True,
        "prelaunch_existing_custom_process_stop_scope": "none",
        "reuse_existing_window_if_present": reuse_existing_window_if_present,
        "existing_custom_window_detected": False,
        "existing_custom_window_reused": False,
        "reused_existing_window": False,
        "new_launch_started": False,
        "fresh_launch_started": False,
        "launch_origin": "not_started",
        "launcher_exit_code_early": None,
        "launcher_failed_before_custom_process": False,
        "agent_runtime_context_written": False,
        "native_alias_context_written": False,
        "context_file_present": False,
        "context_file_sha256_present": False,
        "agent_runtime_context_profile_relative_path": "",
        "agent_runtime_context_sha256": "",
        "agent_runtime_context_path_redacted": True,
    }
    if auth["status"] != "ok":
        return {
            **base,
            "status": "blocked",
            "machine_error_code": auth["machine_error_code"],
            "human_message": "Custom native launch requires exact owner authorization in the active thread.",
            "next_action": "provide_exact_owner_authorization_phrase",
        }

    tmp_root: Path | None = None
    layout: NativeProbeLayout | None = None
    termination: dict[str, Any] | None = None
    cleanup_error = ""
    try:
        real_runtime_paths = RuntimePaths.from_env()
        local_token = emit_local_token(real_runtime_paths)
        paths = default_persistent_custom_profile_paths(
            profile_id=persistent_profile_id,
            base_dir=persistent_profile_base_dir,
        )
        layout = create_persistent_custom_profile_layout(
            profile_id=persistent_profile_id,
            base_dir=persistent_profile_base_dir,
        )
        tmp_root = layout.tmp_root
        materialized_profile = materialize_probe_profile(
            layout=layout,
            endpoint=endpoint,
            model=model,
            auth_command_path=repo_root / "wbp_codex_auth_command.py",
            local_token=local_token,
            agent_runtime_context=agent_runtime_context,
        )
        persistent_fields = {
            "profile_mode": "persistent_custom",
            "persistent_profile_id": str(paths["persistent_profile_id"]),
            "persistent_profile_root": str(paths["persistent_profile_root"]),
            "persistent_codex_home": str(paths["codex_home"]),
            "persistent_home_dir": str(paths["home_dir"]),
            "persistent_user_data_dir": str(paths["user_data_dir"]),
            "persistent_runtime_tmp_dir": str(paths["runtime_tmp_dir"]),
            "temp_profile_used": False,
            "history_persistence_expected": True,
            "cleanup_deletes_persistent_profile_by_default": False,
            "cleanup_scope": "runtime_tmp_only_or_deferred_running_process",
            "browser_client_path_authority": False,
            "original_codex_profile_runtime_dependency": False,
            "agent_runtime_context_written": materialized_profile.get(
                "agent_runtime_context_written"
            )
            is True,
            "native_alias_context_written": materialized_profile.get(
                "native_alias_context_written"
            )
            is True,
            "context_file_present": materialized_profile.get("context_file_present")
            is True,
            "context_file_sha256_present": materialized_profile.get(
                "context_file_sha256_present"
            )
            is True,
            "agent_runtime_context_profile_relative_path": str(
                materialized_profile.get("agent_runtime_context_profile_relative_path")
                or ""
            ),
            "agent_runtime_context_sha256": str(
                materialized_profile.get("agent_runtime_context_sha256") or ""
            ),
            "agent_runtime_context_path_redacted": True,
        }
        keychain_preflight = prepare_isolated_home_keychain(
            isolated_home=layout.custom_home_dir,
        )
        keychain_fields = {
            "keychain_preflight_attempted": True,
            "keychain_preflight_status": str(keychain_preflight.get("status") or ""),
            "keychain_preflight_reason_code": str(
                keychain_preflight.get("machine_error_code") or ""
            ),
            "isolated_default_keychain_verified": keychain_preflight.get(
                "isolated_default_keychain_verified"
            )
            is True,
            "isolated_search_list_verified": keychain_preflight.get(
                "isolated_search_list_verified"
            )
            is True,
            "real_user_keychain_modified": False,
            "keychain_item_read": False,
            "keychain_reset_performed": False,
            "prompt_avoidance_claim_scope": str(
                keychain_preflight.get("prompt_avoidance_claim_scope")
                or "keychain_not_found_prompt_only"
            ),
        }
        if keychain_preflight.get("status") == "blocked":
            cleanup_error = remove_tree_with_retry(tmp_root)
            return {
                **base,
                **persistent_fields,
                **keychain_fields,
                "status": "blocked",
                "machine_error_code": str(
                    keychain_preflight.get("machine_error_code")
                    or "KEYCHAIN_PREFLIGHT_BLOCKED"
                ),
                "human_message": "Custom native launch stopped before launch because keychain preflight was blocked.",
                "next_action": "stop_and_diagnose_keychain_preflight",
                "cleanup_result": {
                    "attempted": True,
                    "status": "ok" if not cleanup_error else "blocked",
                    "termination": {},
                    "cleanup_error_class": cleanup_error,
                },
            }
        if reuse_existing_window_if_present:
            existing_inventory = collect_codex_process_inventory(
                custom_user_data_dir=str(layout.custom_user_data_dir)
            )
            existing_custom_process = existing_inventory.get("custom_process_count", 0) > 0
            if existing_custom_process:
                show_packet = show_custom_native_window_packet(
                    persistent_profile_id=persistent_profile_id,
                    persistent_profile_base_dir=persistent_profile_base_dir,
                )
                existing_window_visible = show_packet.get("status") == "ok"
                existing_window_usable = show_packet.get("native_app_usable") is True
                existing_machine_error = (
                    "OK"
                    if existing_window_usable
                    else (
                        "CUSTOM_NATIVE_EXISTING_WINDOW_USABILITY_NOT_PROVEN"
                        if existing_window_visible
                        else "CUSTOM_CODEX_EXISTING_WINDOW_VISIBILITY_NOT_PROVEN"
                    )
                )
                return {
                    **base,
                    **persistent_fields,
                    **keychain_fields,
                    "status": "ok" if existing_window_usable else "blocked",
                    "machine_error_code": existing_machine_error,
                    "human_message": (
                        "Existing Custom Codex window was reused; no new launch was started."
                        if existing_window_usable
                        else (
                            "Existing Custom Codex window is visible, but input-capable UI was not proven."
                            if existing_window_visible
                            else "Existing Custom Codex process was found, but window visibility was not proven."
                        )
                    ),
                    "next_action": (
                        "none"
                        if existing_window_usable
                        else "show_existing_custom_codex_window_or_stop_same_profile_process"
                    ),
                    "running_status": existing_window_visible,
                    "process_started": False,
                    "custom_process_observed": True,
                    "custom_process_pid": show_packet.get("custom_process_pid"),
                    "process_still_observed_after_wait": True,
                    "expected_custom_identity_observed": existing_window_visible,
                    "native_window_observed": show_packet.get("custom_window_observed") is True,
                    "custom_window_observed": show_packet.get("custom_window_observed") is True,
                    "custom_window_visible": show_packet.get("custom_window_visible") is True,
                    "custom_window_frontmost": show_packet.get("custom_window_frontmost") is True,
                    "custom_window_bounds": show_packet.get("custom_window_bounds", {}),
                    "window_focus_action_attempted": show_packet.get("window_focus_action_attempted") is True,
                    "window_focus_action_succeeded": show_packet.get("window_focus_action_succeeded") is True,
                    "native_app_usable": existing_window_usable,
                    "native_app_usability_source": (
                        str(show_packet.get("native_app_usability_source") or "")
                        if existing_window_usable
                        else "not_proven"
                    ),
                    "native_app_usability_blocked_reason_class": str(
                        show_packet.get("native_app_usability_blocked_reason_class") or ""
                    ),
                    "renderer_recovery_attempted": (
                        show_packet.get("renderer_recovery_attempted") is True
                    ),
                    "renderer_recovery_status": str(
                        show_packet.get("renderer_recovery_status") or ""
                    ),
                    "renderer_recovery_action": str(
                        show_packet.get("renderer_recovery_action") or ""
                    ),
                    "renderer_recovery_packet": show_packet.get(
                        "renderer_recovery_packet",
                        _renderer_recovery_not_required_packet(),
                    ),
                    "cdp_localhost_only": show_packet.get("cdp_localhost_only") is True,
                    "cdp_endpoint_redacted": show_packet.get("cdp_endpoint_redacted") is True,
                    "cdp_target_bound_to_custom_launch": show_packet.get("cdp_target_bound_to_custom_launch") is True,
                    "cdp_editable_surface_observed": show_packet.get("cdp_editable_surface_observed") is True,
                    "raw_dom_exposed": show_packet.get("raw_dom_exposed") is True,
                    "raw_ax_tree_exposed": show_packet.get("raw_ax_tree_exposed") is True,
                    "browser_cdp_authority_widened": show_packet.get("browser_cdp_authority_widened") is True,
                    "input_capable_ui_observed": show_packet.get("input_capable_ui_observed") is True,
                    "real_codex_app_launched": False,
                    "isolated_home": True,
                    "isolated_codex_home": True,
                    "isolated_profile_dir": True,
                    "isolated_app_support_dir": True,
                    "isolated_cache_dir": True,
                    "isolated_runtime_dir": True,
                    "server_owned_route_configuration": True,
                    "current_original_profile_shortcut_used": False,
                    "current_codex_touched": False,
                    "cleanup_deferred_while_running": existing_window_visible,
                    "keep_running_on_window_observed": keep_running_on_window_observed,
                    "existing_custom_window_detected": True,
                    "existing_custom_window_reused": existing_window_usable,
                    "reused_existing_window": existing_window_usable,
                    "new_launch_started": False,
                    "fresh_launch_started": False,
                    "launch_origin": (
                        "existing_window"
                        if existing_window_usable
                        else "existing_window_unproven"
                    ),
                    "show_existing_window_packet": show_packet,
                    "cleanup_result": {
                        "attempted": False,
                        "status": "existing_window_reused" if existing_window_visible else "existing_process_left_running",
                        "termination": {},
                        "cleanup_error_class": "",
                    },
                }
        prelaunch_termination = terminate_custom_processes(str(layout.custom_user_data_dir))
        prelaunch_processes_gone = prelaunch_termination.get("custom_processes_gone") is True
        prelaunch_fields = {
            "prelaunch_existing_custom_process_stop_attempted": True,
            "prelaunch_existing_custom_processes_gone": prelaunch_processes_gone,
            "prelaunch_existing_custom_process_stop_scope": "same_custom_user_data_dir_only",
            "prelaunch_existing_custom_process_initial_pids": prelaunch_termination.get(
                "initial_custom_pids",
                [],
            ),
        }
        if not prelaunch_processes_gone:
            cleanup_error = remove_tree_with_retry(tmp_root)
            return {
                **base,
                **persistent_fields,
                **keychain_fields,
                **prelaunch_fields,
                "status": "blocked",
                "machine_error_code": "CUSTOM_NATIVE_PRELAUNCH_PROCESS_STOP_FAILED",
                "human_message": "Custom Codex native launch stopped because existing same-profile Custom processes could not be stopped safely.",
                "next_action": "stop_and_diagnose_existing_custom_processes",
                "running_status": False,
                "process_started": False,
                "real_codex_app_launched": False,
                "current_codex_touched": False,
                "cleanup_result": {
                    "attempted": True,
                    "status": "ok" if not cleanup_error else "blocked",
                    "termination": prelaunch_termination,
                    "cleanup_error_class": cleanup_error,
                },
            }
        launch_result = launch_native_candidate(
            repo_root=repo_root,
            layout=layout,
            real_runtime_paths=real_runtime_paths,
        )
        process_started = launch_result.get("custom_process_observed") is True
        launcher_exit_code_early = launch_result.get("launcher_exit_code_early")
        launcher_failed_before_process = (
            not process_started
            and isinstance(launcher_exit_code_early, int)
            and launcher_exit_code_early != 0
        )
        process_still_alive = (
            launch_result.get("custom_process_still_observed_after_wait") is True
        )
        window_packet = _wait_for_window_observation_via_ax(launch_result["startup_inventory"])
        focus_packet: dict[str, Any] = {
            "window_focus_action_attempted": False,
            "window_focus_action_succeeded": False,
        }
        observed_pid_for_focus = window_packet.get("observed_pid")
        if isinstance(observed_pid_for_focus, int) and (
            window_packet.get("window_observed") is not True
            or window_packet.get("window_visible") is not True
            or window_packet.get("window_frontmost") is not True
        ):
            focus_packet = _focus_custom_window_by_pid(observed_pid_for_focus)
            window_packet = _window_observation_via_ax(
                collect_codex_process_inventory(
                    custom_user_data_dir=str(layout.custom_user_data_dir)
                )
            )
        usability_packet = _window_usability_from_observation(window_packet)
        usability_packet = _apply_codex_desktop_auth_blocker(
            usability_packet,
            profile_dir=layout.profile_dir,
            launcher_stderr_path=launch_result.get("launcher_stderr_path"),
        )
        usability_packet = _bounded_recheck_codex_desktop_auth_blocker(
            usability_packet,
            profile_dir=layout.profile_dir,
            launcher_stderr_path=launch_result.get("launcher_stderr_path"),
        )
        renderer_recovery_packet = _renderer_recovery_not_required_packet()
        observed_pid_for_recovery = window_packet.get("observed_pid")
        if isinstance(observed_pid_for_recovery, int):
            (
                usability_packet,
                renderer_recovery_packet,
                recovered_window_packet,
            ) = _recover_startup_loader_if_needed(
                usability_packet,
                observed_pid=observed_pid_for_recovery,
                profile_dir=layout.profile_dir,
                custom_user_data_dir=str(layout.custom_user_data_dir),
            )
            if recovered_window_packet is not None:
                window_packet = recovered_window_packet
        elif _renderer_startup_loader_stuck(usability_packet):
            renderer_recovery_packet = _renderer_recovery_packet(
                status="blocked",
                machine_error_code="OBSERVED_PID_MISSING_FOR_RENDERER_RECOVERY",
                reason_class="observed_pid_missing_for_renderer_recovery",
                reload_targets=[],
            )
        post_launch_usability_recheck_packet = _post_launch_usability_recheck_packet(
            attempted=False,
            status="not_required",
            machine_error_code="NOT_REQUIRED",
        )
        if (
            process_started
            and process_still_alive
            and window_packet.get("window_observed") is True
            and _post_launch_usability_recheck_candidate(usability_packet)
        ):
            (
                post_launch_usability_recheck_packet,
                rechecked_window_packet,
                rechecked_usability_packet,
            ) = _wait_for_post_launch_window_usability(
                initial_window_packet=window_packet,
                profile_dir=layout.profile_dir,
                custom_user_data_dir=str(layout.custom_user_data_dir),
            )
            if post_launch_usability_recheck_packet.get("status") == "ok":
                window_packet = rechecked_window_packet
                usability_packet = rechecked_usability_packet
        usability_packet = _bounded_recheck_codex_desktop_auth_blocker(
            usability_packet,
            profile_dir=layout.profile_dir,
            launcher_stderr_path=launch_result.get("launcher_stderr_path"),
        )
        runtime_ready_packet = _runtime_ready_from_launcher_stdout(launch_result, layout)
        identity_packet = _build_identity_binding(window_packet, layout, launch_result)
        expected_identity = identity_packet.get("window_bound_to_custom_launch") is True
        native_window_observed = window_packet.get("window_observed") is True
        custom_window_visible = (
            native_window_observed and window_packet.get("window_visible") is True
        )
        custom_window_frontmost = window_packet.get("window_frontmost") is True
        input_capable_ui_observed = usability_packet.get("native_window_usable") is True
        runtime_ready_observed = runtime_ready_packet.get("runtime_ready_observed") is True
        native_app_usable = input_capable_ui_observed
        desktop_auth_blocker = usability_packet.get("codex_desktop_auth_blocker_observed") is True
        native_app_usability_source = (
            str(usability_packet.get("native_app_usability_source") or "input_capable_ui")
            if input_capable_ui_observed or desktop_auth_blocker
            else "not_proven"
        )
        usability_blocked_reason = str(usability_packet.get("blocked_reason_class") or "")
        renderer_surface_blocked_reason = str(
            usability_packet.get("renderer_surface_blocked_reason_class") or usability_blocked_reason
        )
        blocked_machine_error = _custom_native_launch_blocked_machine_error(
            launcher_failed_before_process=launcher_failed_before_process,
            process_started=process_started,
            process_still_alive=process_still_alive,
            custom_window_visible=custom_window_visible,
            native_app_usable=native_app_usable,
            desktop_auth_blocker=desktop_auth_blocker,
            renderer_surface_blocked_reason=renderer_surface_blocked_reason,
        )
        blocked_human_message = _custom_native_launch_blocked_human_message(
            launcher_failed_before_process=launcher_failed_before_process,
            process_started=process_started,
            process_still_alive=process_still_alive,
            custom_window_visible=custom_window_visible,
            native_app_usable=native_app_usable,
            desktop_auth_blocker=desktop_auth_blocker,
            renderer_surface_blocked_reason=renderer_surface_blocked_reason,
        )
        success = (
            process_started
            and process_still_alive
            and expected_identity
            and runtime_ready_observed
            and native_window_observed
            and native_app_usable
        )
        keep_running_with_limited_proof = (
            keep_running_on_window_observed
            and process_started
            and process_still_alive
            and expected_identity
            and native_window_observed
        )

        if not success and not keep_running_with_limited_proof:
            termination = terminate_custom_processes(str(layout.custom_user_data_dir))
            usability_packet = _bounded_recheck_codex_desktop_auth_blocker(
                usability_packet,
                profile_dir=layout.profile_dir,
                launcher_stderr_path=launch_result.get("launcher_stderr_path"),
                allow_profile_auth_state_fallback=True,
                profile_auth_state_fallback_allowed_by_current_launch=(
                    process_started
                    and process_still_alive
                    and not launcher_failed_before_process
                ),
            )
            input_capable_ui_observed = usability_packet.get("native_window_usable") is True
            native_app_usable = input_capable_ui_observed
            desktop_auth_blocker = usability_packet.get("codex_desktop_auth_blocker_observed") is True
            native_app_usability_source = (
                str(usability_packet.get("native_app_usability_source") or "input_capable_ui")
                if input_capable_ui_observed or desktop_auth_blocker
                else "not_proven"
            )
            usability_blocked_reason = str(usability_packet.get("blocked_reason_class") or "")
            renderer_surface_blocked_reason = str(
                usability_packet.get("renderer_surface_blocked_reason_class")
                or usability_blocked_reason
            )
            blocked_machine_error = _custom_native_launch_blocked_machine_error(
                launcher_failed_before_process=launcher_failed_before_process,
                process_started=process_started,
                process_still_alive=process_still_alive,
                custom_window_visible=custom_window_visible,
                native_app_usable=native_app_usable,
                desktop_auth_blocker=desktop_auth_blocker,
                renderer_surface_blocked_reason=renderer_surface_blocked_reason,
            )
            blocked_human_message = _custom_native_launch_blocked_human_message(
                launcher_failed_before_process=launcher_failed_before_process,
                process_started=process_started,
                process_still_alive=process_still_alive,
                custom_window_visible=custom_window_visible,
                native_app_usable=native_app_usable,
                desktop_auth_blocker=desktop_auth_blocker,
                renderer_surface_blocked_reason=renderer_surface_blocked_reason,
            )
            cleanup_error = remove_tree_with_retry(tmp_root)

        return {
            **base,
            **persistent_fields,
            **keychain_fields,
            **prelaunch_fields,
            "status": "ok" if success else "blocked",
            "machine_error_code": "OK" if success else blocked_machine_error,
            "human_message": (
                "Custom Codex native app launched and pid-bound window proof passed."
                if success
                else blocked_human_message
            ),
            "running_status": success or keep_running_with_limited_proof,
            "process_started": process_started,
            "custom_process_observed": process_started,
            "custom_process_pid": window_packet.get("observed_pid"),
            "process_still_observed_after_wait": process_still_alive,
            "process_exited_after_start": process_started and not process_still_alive,
            "post_observation_wait_seconds": launch_result.get(
                "post_observation_wait_seconds",
                0,
            ),
            "expected_custom_identity_observed": expected_identity,
            "native_window_observed": native_window_observed,
            "custom_window_observed": native_window_observed,
            "custom_window_visible": custom_window_visible,
            "custom_window_frontmost": custom_window_frontmost,
            "custom_window_bounds": window_packet.get("window_bounds", {}),
            "window_focus_action_attempted": focus_packet.get("window_focus_action_attempted") is True,
            "window_focus_action_succeeded": focus_packet.get("window_focus_action_succeeded") is True,
            "window_focus_packet": focus_packet,
            "native_app_usable": native_app_usable,
            "native_app_usability_source": native_app_usability_source,
            "input_capable_ui_observed": input_capable_ui_observed,
            "cdp_localhost_only": usability_packet.get("cdp_localhost_only") is True,
            "cdp_endpoint_redacted": usability_packet.get("cdp_endpoint_redacted") is True,
            "cdp_target_bound_to_custom_launch": usability_packet.get("cdp_target_bound_to_custom_launch") is True,
            "cdp_editable_surface_observed": usability_packet.get("cdp_editable_surface_observed") is True,
            "raw_dom_exposed": usability_packet.get("raw_dom_exposed") is True,
            "raw_ax_tree_exposed": usability_packet.get("raw_ax_tree_exposed") is True,
            "browser_cdp_authority_widened": usability_packet.get("browser_cdp_authority_widened") is True,
            "codex_desktop_auth_blocker_observed": desktop_auth_blocker,
            "codex_desktop_auth_blocked_reason_class": str(
                usability_packet.get("codex_desktop_auth_blocked_reason_class") or ""
            ),
            "codex_desktop_auth_error_class": str(
                usability_packet.get("codex_desktop_auth_error_class") or ""
            ),
            "renderer_surface_blocked_reason_class": str(
                renderer_surface_blocked_reason if not native_app_usable else ""
            ),
            "renderer_startup_loader_observed": (
                usability_packet.get("renderer_startup_loader_observed") is True
            ),
            "renderer_mounted": usability_packet.get("renderer_mounted") is True,
            "renderer_recovery_attempted": renderer_recovery_packet.get("attempted") is True,
            "renderer_recovery_status": str(renderer_recovery_packet.get("status") or ""),
            "renderer_recovery_action": str(renderer_recovery_packet.get("action") or ""),
            "renderer_recovery_packet": renderer_recovery_packet,
            "post_launch_usability_recheck_attempted": (
                post_launch_usability_recheck_packet.get("attempted") is True
            ),
            "post_launch_usability_recheck_status": str(
                post_launch_usability_recheck_packet.get("status") or ""
            ),
            "post_launch_usability_recheck_machine_error_code": str(
                post_launch_usability_recheck_packet.get("machine_error_code") or ""
            ),
            "post_launch_usability_recheck_attempt_count": int(
                post_launch_usability_recheck_packet.get("attempt_count") or 0
            ),
            "post_launch_usability_recheck_packet": (
                post_launch_usability_recheck_packet
            ),
            **runtime_ready_packet,
            "real_codex_app_launched": success,
            "isolated_home": True,
            "isolated_codex_home": True,
            "isolated_profile_dir": True,
            "isolated_app_support_dir": True,
            "isolated_cache_dir": True,
            "isolated_runtime_dir": True,
            "server_owned_route_configuration": True,
            "current_original_profile_shortcut_used": False,
            "current_codex_touched": False,
            "cleanup_deferred_while_running": success or keep_running_with_limited_proof,
            "keep_running_on_window_observed": keep_running_on_window_observed,
            "native_window_process_kept_running": keep_running_with_limited_proof and not success,
            "profile_receipt_redacted": True,
            "route_endpoint_redacted": True,
            "selection_model_id": model,
            "next_action": (
                "none"
                if success
                else (
                    "stop_and_diagnose_custom_native_launcher"
                    if launcher_failed_before_process
                    else (
                        "relaunch_custom_codex_after_process_exit"
                        if process_started and not process_still_alive
                        else "sign_in_to_codex_desktop_custom_profile"
                        if desktop_auth_blocker
                        else "stop_and_diagnose_custom_renderer_startup_loader"
                        if renderer_surface_blocked_reason == "cdp_renderer_startup_loader_stuck"
                        else "stop_and_diagnose_custom_window_usability"
                        if custom_window_visible and not native_app_usable
                        else "stop_and_diagnose_native_launch"
                    )
                )
            ),
            "new_launch_started": True,
            "launcher_exit_code_early": launcher_exit_code_early,
            "launcher_failed_before_custom_process": launcher_failed_before_process,
            "window_observation_blocked_reason_class": str(window_packet.get("blocked_reason_class") or ""),
            "native_app_usability_blocked_reason_class": str(
                ""
                if native_app_usable
                else usability_packet.get("blocked_reason_class") or ""
            ),
            "native_window_usability_packet": usability_packet,
            "identity_chain_status": identity_packet.get("status"),
            "launch_receipt": {
                "tmp_root_redacted": True,
                "launcher_stdout_redacted": True,
                "launcher_stderr_redacted": True,
                "cleanup_deferred_while_running": success or keep_running_with_limited_proof,
            },
            "cleanup_result": {
                "attempted": not (success or keep_running_with_limited_proof),
                "status": (
                    "deferred_running_process"
                    if success
                    else (
                        "deferred_window_observed_process_running"
                        if keep_running_with_limited_proof
                        else ("ok" if not cleanup_error else "blocked")
                    )
                ),
                "termination": termination or {},
                "cleanup_error_class": cleanup_error,
            },
        }
    except Exception as exc:
        if layout is not None:
            termination = terminate_custom_processes(str(layout.custom_user_data_dir))
        if tmp_root is not None:
            cleanup_error = remove_tree_with_retry(tmp_root)
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "CUSTOM_NATIVE_LAUNCH_EXCEPTION",
            "human_message": f"Custom native launch failed before proof completed: {type(exc).__name__}.",
            "next_action": "stop_and_diagnose_native_launch_exception",
            "cleanup_result": {
                "attempted": True,
                "status": "ok" if not cleanup_error else "blocked",
                "termination": termination or {},
                "cleanup_error_class": cleanup_error,
                "exception_class": type(exc).__name__,
            },
        }


def run_native_window_probe(
    *,
    repo_root: Path,
    evidence_dir: Path,
    endpoint: str,
    model: str,
    owner_authorization_phrase: str | None = None,
) -> dict[str, Any]:
    admission = build_native_custom_preflight_packet(
        native_window_probe_command(),
        native_window_probe_server_plan(),
    )
    auth = build_native_dispatch_authorization_packet(
        owner_authorized=owner_authorization_phrase_present(owner_authorization_phrase),
        admission_packet=admission,
    )
    json_write(evidence_dir / "native_dispatch_authorization_packet.json", auth)
    if auth["status"] != "ok":
        blocked = build_native_custom_dispatch_packet(
            owner_authorized=False,
            admission_packet=admission,
        )
        process_packet = build_native_process_observation_packet(
            dispatch_observed=False,
            process_observed=False,
            observation_blocked_reason="owner_authorization_missing",
        )
        window_packet = build_native_window_observation_packet(
            window_observed=False,
            blocked_reason_class="owner_authorization_missing",
        )
        usability_packet = build_native_window_usability_packet(
            window_observed=False,
            input_capable_ui_observed=False,
            blocked_reason_class="owner_authorization_missing",
        )
        protection_packet = build_native_current_codex_protection_packet(
            before_snapshot_captured=False,
            after_snapshot_captured=False,
            current_codex_touched=False,
            protection_basis="no_live_dispatch_attempted",
        )
        cleanup_packet = build_native_cleanup_rollback_execution_packet(
            cleanup_attempted=False,
            rollback_attempted=False,
            cleanup_or_rollback_status="ok_no_process_launched",
            cleanup_blocked_reason_class="owner_authorization_missing_no_live_dispatch",
        )
        original_deferred = build_native_original_dispatch_deferred_packet()
        false_green = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=blocked,
            original_deferred_packet=original_deferred,
        )
        summary = {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "machine_error_code": auth["machine_error_code"],
            "runner_surface_ready": False,
            "owner_authorization_phrase_present": False,
            "expected_runner_command": "python3 tools/native_window_proof_probe.py --repo-root <repo> --evidence-dir <dir> --endpoint <url> --model <model> --owner-authorization-phrase <phrase>",
            "reason_class": auth["blocked_reason_class"],
        }
        for name, packet in {
            "native_custom_launch_packet.json": blocked,
            "process_lineage_packet.json": process_packet,
            "window_observation_packet.json": window_packet,
            "native_window_ui_surface_packet.json": usability_packet,
            "current_codex_running_state_before.json": protection_packet,
            "current_codex_running_state_after.json": protection_packet,
            "cleanup_reversibility_packet.json": cleanup_packet,
            "native_window_proof_summary.json": summary,
            "independent_native_window_audit.json": false_green,
        }.items():
            json_write(evidence_dir / name, packet)
        return summary

    real_runtime_paths = RuntimePaths.from_env()
    local_token = emit_local_token(real_runtime_paths)
    tmp_root = Path(tempfile.mkdtemp(prefix="wbp-native-window-", dir="/tmp"))
    layout: NativeProbeLayout = create_native_probe_layout(tmp_root)
    materialized = materialize_probe_profile(
        layout=layout,
        endpoint=endpoint,
        model=model,
        auth_command_path=repo_root / "wbp_codex_auth_command.py",
        local_token=local_token,
    )
    before_process = collect_codex_process_inventory(custom_user_data_dir=str(layout.custom_user_data_dir))
    launch_result = launch_native_candidate(
        repo_root=repo_root,
        layout=layout,
        real_runtime_paths=real_runtime_paths,
    )
    process_packet = build_native_process_observation_packet(
        dispatch_observed=launch_result["custom_process_observed"],
        process_observed=launch_result["custom_process_observed"],
    )
    process_packet.update(
        {
            "process_id": launch_result["launcher_pid"],
            "process_lineage": launch_result["startup_inventory"].get("sample", []),
        }
    )
    window_packet = _window_observation_via_ax(launch_result["startup_inventory"])
    usability_packet = _window_usability_from_observation(window_packet)
    protection_before = build_native_current_codex_protection_packet(
        before_snapshot_captured=True,
        after_snapshot_captured=False,
        current_codex_touched=False,
    )
    termination = terminate_custom_processes(str(layout.custom_user_data_dir))
    after_process = collect_codex_process_inventory(custom_user_data_dir=str(layout.custom_user_data_dir))
    protection_after = build_native_current_codex_protection_packet(
        before_snapshot_captured=True,
        after_snapshot_captured=True,
        current_codex_touched=False,
        protection_basis="repo_owned_window_runner_no_default_codex_process_delta",
    )
    cleanup_error = remove_tree_with_retry(tmp_root)
    cleanup_packet = build_native_cleanup_rollback_execution_packet(
        cleanup_attempted=True,
        rollback_attempted=False,
        cleanup_or_rollback_status="ok" if not cleanup_error else "blocked",
        cleanup_blocked_reason_class="" if not cleanup_error else cleanup_error,
    )
    custom_dispatch = build_native_custom_dispatch_packet(
        owner_authorized=True,
        admission_packet=admission,
        dispatch_result={"dispatch_attempted": True, "dispatch_observed": launch_result["custom_process_observed"]},
        process_observation={"process_observed": launch_result["custom_process_observed"]},
        window_observation=window_packet,
        usability_observation=usability_packet,
        protection_packet={"current_codex_touched": False},
        cleanup_packet={"cleanup_or_rollback_status": cleanup_packet["cleanup_or_rollback_status"]},
    )
    custom_dispatch["process_id"] = launch_result["launcher_pid"]
    custom_dispatch["profile_dir"] = materialized["profile_dir"]
    custom_dispatch["codex_home"] = materialized["profile_dir"]
    window_observed = window_packet.get("window_observed") is True
    input_capable = usability_packet.get("input_capable_ui_observed") is True
    custom_dispatch["window_id_or_title"] = str(window_packet.get("window_query") or "observed") if window_observed else "unproven"
    custom_dispatch["cleanup_command"] = f"remove_tree_with_retry({tmp_root})"
    custom_dispatch["wbp_action_id"] = "wbp-native-window-proof"
    custom_dispatch["trace_id"] = "unproven"
    custom_dispatch["route_endpoint"] = endpoint
    original_deferred = build_native_original_dispatch_deferred_packet()
    false_green = build_native_dispatch_false_green_audit(
        custom_dispatch_packet=custom_dispatch,
        original_deferred_packet=original_deferred,
    )
    window_proof_pass = window_observed and input_capable
    summary = {
        "captured_at_utc": utc_now(),
        "status": "ok" if window_proof_pass else "blocked",
        "machine_error_code": "OK" if window_proof_pass else "NATIVE_CUSTOM_WINDOW_NOT_PROVEN",
        "runner_surface_ready": True,
        "selected_strategy_id": "repo_canonical_custom_proxy_auth_isolated_home",
        "owner_authorization_phrase_present": True,
        "expected_runner_command": "python3 tools/native_window_proof_probe.py --repo-root <repo> --evidence-dir <dir> --endpoint <url> --model <model> --owner-authorization-phrase <phrase>",
        "window_observed": window_observed,
        "input_capable_ui_surface_observed": input_capable,
        "window_proof_pass": window_proof_pass,
        "blocked_reason_class": "" if window_proof_pass else (
            "input_capable_window_not_proven_for_pid" if window_observed and not input_capable
            else "pid_visible_but_accessible_window_absent" if not window_observed
            else "native_custom_window_not_proven"
        ),
        "materialized_profile": materialized,
        "custom_native_launch_packet": custom_dispatch,
    }
    packets = {
        "native_custom_launch_packet.json": custom_dispatch,
        "process_lineage_packet.json": process_packet,
        "window_observation_packet.json": window_packet,
        "window_identity_binding_packet.json": _build_identity_binding(window_packet, layout, launch_result),
        "native_window_ui_surface_packet.json": usability_packet,
        "current_codex_running_state_before.json": before_process,
        "current_codex_running_state_after.json": after_process,
        "cleanup_reversibility_packet.json": {
            "captured_at_utc": utc_now(),
            "cleanup_or_rollback_status": cleanup_packet["cleanup_or_rollback_status"],
            "cleanup_error": cleanup_error,
            "termination": termination,
            "tmp_root": str(tmp_root),
            "tmp_root_removed": not tmp_root.exists(),
        },
        "native_window_proof_summary.json": summary,
        "independent_native_window_audit.json": false_green,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    return summary
