# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-owned bounded runner surface for native window proof contours.

This module normalizes a repeatable Phase 9 runner surface without changing
launch semantics. It reuses the existing custom native launch lane, packet
builders, and bounded cleanup model.
"""

from __future__ import annotations

import json
import tempfile
import time
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
from .process_runner import BoundedProcessResult, run_bounded_process
from .runtime import RuntimePaths
from .token_command import emit_local_token


OWNER_STANDING_AUTHORIZATION_PHRASE = "разрешаю тебе любые законные действия в рамках разработки проекта"
WINDOW_OBSERVATION_WAIT_SECONDS = 12.0
WINDOW_OBSERVATION_POLL_SECONDS = 0.5
DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID = "wbp-custom-main"
NATIVE_AX_RUNTIME_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
NATIVE_AX_OSASCRIPT_TIMEOUT_SECONDS = 10.0
NATIVE_AX_OSASCRIPT_OUTPUT_CAP_BYTES = 16 * 1024
NATIVE_AX_OSASCRIPT_CWD = Path("/")
RUNTIME_READY_STDOUT_MARKERS = (
    "Handled 'ready' message",
    "method=model/list",
    "browser_use_iab_backend_startup_ready",
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


def _native_ax_env() -> dict[str, str]:
    return {
        "PATH": NATIVE_AX_RUNTIME_PATH,
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
    }


def _run_osascript(script: str) -> BoundedProcessResult:
    return run_bounded_process(
        ["osascript", "-e", script],
        env=_native_ax_env(),
        cwd=NATIVE_AX_OSASCRIPT_CWD,
        timeout_seconds=NATIVE_AX_OSASCRIPT_TIMEOUT_SECONDS,
        output_cap_bytes=NATIVE_AX_OSASCRIPT_OUTPUT_CAP_BYTES,
    )


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
    result = _run_osascript(script)
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
        result.exit_code == 0
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
                "window_query_rc": result.exit_code,
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
                "window_query_rc": result.exit_code,
                "window_query_error_class": "",
                "window_count": 1,
                "window_frontmost": frontmost,
                "window_visible": True,
                "window_background_only": background_only,
                "window_bounds": window_bounds,
                "window_position": window_position,
                "window_size": window_size,
                "ax_window_query": stdout,
                "ax_window_query_error_class": "SystemEventsInvalidIndex" if result.exit_code else "",
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
            "window_query_rc": result.exit_code,
            "window_query_error_class": "SystemEventsInvalidIndex" if result.exit_code else "",
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
    result = _run_osascript(script)
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
    succeeded = result.exit_code == 0 and visible and frontmost and window_count > 0
    return {
        "window_focus_action_attempted": True,
        "window_focus_action_succeeded": succeeded,
        "window_focus_query": stdout,
        "window_focus_query_rc": result.exit_code,
        "window_focus_query_error_class": "" if result.exit_code == 0 else "SystemEventsFocusFailed",
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
    visible = after.get("window_observed") is True and after.get("window_visible") is True
    frontmost = after.get("window_frontmost") is True
    status_ok = visible and focus.get("window_focus_action_succeeded") is True
    return {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_show_window",
        "status": "ok" if status_ok else "blocked",
        "machine_error_code": "OK" if status_ok else "CUSTOM_CODEX_WINDOW_VISIBILITY_NOT_PROVEN",
        "human_message": (
            "Custom Codex window is visible and frontmost."
            if status_ok
            else "Custom Codex window could not be proven visible and frontmost."
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
        "window_observation_before_focus": before,
        "window_observation_after_focus": after,
        "original_codex_touched": False,
        "asar_touched": False,
        "next_action": "none" if status_ok else "stop_and_diagnose_window_visibility",
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
        '    set hasField to exists (first UI element of w whose role is "AXTextField" or role is "AXTextArea")\n'
        '  end try\n'
        '  return {name of w, hasField}\n'
        'end tell\n'
    )
    result = _run_osascript(script)
    stdout = result.stdout.strip()
    if result.exit_code != 0 or not stdout:
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
        '    set hasField to exists (first UI element of w whose role is "AXTextField" or role is "AXTextArea")\n'
        '  end try\n'
        '  return (name of p as text) & tab & (name of w as text) & tab & (hasField as text)\n'
        'end tell\n'
    )
    result = _run_osascript(script)
    stdout = result.stdout.strip()
    if result.exit_code != 0 or not stdout:
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
    input_capable_m2, result_m2 = _cg_input_capable(observed_pid)
    query_result = f"mechanism_1_pid_guarded: {result_m1}; mechanism_2_cg_pid_window_only: {result_m2}"
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
        "new_launch_started": False,
        "launcher_exit_code_early": None,
        "launcher_failed_before_custom_process": False,
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
        materialize_probe_profile(
            layout=layout,
            endpoint=endpoint,
            model=model,
            auth_command_path=repo_root / "wbp_codex_auth_command.py",
            local_token=local_token,
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
                return {
                    **base,
                    **persistent_fields,
                    **keychain_fields,
                    "status": "ok" if existing_window_visible else "blocked",
                    "machine_error_code": (
                        "OK"
                        if existing_window_visible
                        else "CUSTOM_CODEX_EXISTING_WINDOW_VISIBILITY_NOT_PROVEN"
                    ),
                    "human_message": (
                        "Existing Custom Codex window was reused; no new launch was started."
                        if existing_window_visible
                        else "Existing Custom Codex process was found, but window visibility was not proven."
                    ),
                    "next_action": (
                        "none"
                        if existing_window_visible
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
                    "native_app_usable": existing_window_visible,
                    "native_app_usability_source": (
                        "existing_visible_custom_window" if existing_window_visible else "not_proven"
                    ),
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
                    "existing_custom_window_reused": existing_window_visible,
                    "new_launch_started": False,
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
        native_app_usable = input_capable_ui_observed or custom_window_visible
        native_app_usability_source = (
            "input_capable_ui"
            if input_capable_ui_observed
            else ("visible_custom_window" if custom_window_visible else "not_proven")
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
            cleanup_error = remove_tree_with_retry(tmp_root)

        return {
            **base,
            **persistent_fields,
            **keychain_fields,
            **prelaunch_fields,
            "status": "ok" if success else "blocked",
            "machine_error_code": (
                "OK"
                if success
                else (
                    "CUSTOM_NATIVE_LAUNCHER_EXIT_NONZERO"
                    if launcher_failed_before_process
                    else "CUSTOM_NATIVE_WINDOW_NOT_PROVEN"
                )
            ),
            "human_message": (
                "Custom Codex native app launched and pid-bound window proof passed."
                if success
                else (
                    "Custom Codex launcher exited before a Custom process was observed."
                    if launcher_failed_before_process
                    else "Custom Codex native launch did not satisfy process/window proof."
                )
            ),
            "running_status": success or keep_running_with_limited_proof,
            "process_started": process_started,
            "custom_process_observed": process_started,
            "custom_process_pid": window_packet.get("observed_pid"),
            "process_still_observed_after_wait": process_still_alive,
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
                    else "stop_and_diagnose_native_launch"
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
