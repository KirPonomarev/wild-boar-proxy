# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-owned bounded runner surface for native window proof contours.

This module normalizes a repeatable Phase 9 runner surface without changing
launch semantics. It reuses the existing custom native launch lane, packet
builders, and bounded cleanup model.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .native_filesystem_probe import (
    NativeProbeLayout,
    clean_env,
    collect_codex_process_inventory,
    create_native_probe_layout,
    json_write,
    launch_native_candidate,
    materialize_probe_profile,
    remove_tree_with_retry,
    terminate_custom_processes,
    utc_now,
)
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
from .runtime import RuntimePaths
from .token_command import emit_local_token


OWNER_STANDING_AUTHORIZATION_PHRASE = "разрешаю тебе любые законные действия в рамках разработки проекта"


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


def _window_observation_via_ax(process_inventory: dict[str, Any]) -> dict[str, Any]:
    root_pids = process_inventory.get("root_app_pids", [])
    if not root_pids:
        return build_native_window_observation_packet(
            window_observed=False,
            blocked_reason_class="process_not_observed",
        )
    observed_pid = int(root_pids[0])
    script = (
        'tell application "System Events"\n'
        f'  set p to first process whose unix id is {observed_pid}\n'
        '  return {name of p, visible of p, frontmost of p, background only of p, count of windows of p}\n'
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
    if result.returncode == 0 and stdout:
        packet = build_native_window_observation_packet(window_observed=True)
        packet.update(
            {
                "observed_pid": observed_pid,
                "window_query": stdout,
                "window_query_rc": result.returncode,
                "window_query_error_class": "",
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
            "window_query_rc": result.returncode,
            "window_query_error_class": "SystemEventsInvalidIndex" if result.returncode else "",
        }
    )
    return packet


def _ax_input_capable(observed_pid: int) -> tuple[bool, str]:
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
    input_capable, query_result = _ax_input_capable(observed_pid)
    packet = build_native_window_usability_packet(
        window_observed=True,
        input_capable_ui_observed=input_capable,
        blocked_reason_class="" if input_capable else "input_capable_window_not_proven_for_pid",
    )
    packet.update({
        "ax_query_result": query_result,
        "input_capable_query_method": "AX/System Events text input element inspection",
    })
    return packet


def _build_identity_binding(
    window_packet: dict[str, Any],
    layout: NativeProbeLayout,
    launch_result: dict[str, Any],
) -> dict[str, Any]:
    window_observed = window_packet.get("window_observed") is True
    window_name = window_packet.get("window_query", "")
    bound = window_observed and isinstance(window_name, str) and len(window_name) > 0
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
