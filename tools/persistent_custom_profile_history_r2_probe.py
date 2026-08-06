#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded R2 probe for Persistent Custom profile history."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    NativeProbeLayout,
    build_integration_ownership_baseline_packet,
    build_original_codex_profile_drift_packet,
    build_original_codex_protected_surface_scope_packet,
    build_owner_visible_thread_context_packet,
    build_persistent_backup_rollback_packet,
    build_persistent_cleanup_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_profile_false_green_audit,
    build_persistent_profile_state_diff_packet,
    build_persistent_profile_state_preservation_packet,
    build_persistent_thread_history_preservation_r2_packet,
    build_thread_history_preservation_packet,
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
    json_write,
    launch_native_candidate,
    materialize_probe_profile,
    scan_protected_surfaces,
    scan_tree,
    terminate_custom_processes,
)
from wild_boar_proxy.runtime import RuntimePaths
from wild_boar_proxy.token_command import emit_local_token


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> tuple[list[str], list[str]]:
    if skip_git:
        return [], []
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/native_filesystem_probe.py",
        "tools/persistent_custom_profile_history_r2_probe.py",
        "tests/test_native_filesystem_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    current_contour_prefixes = (
        f"?? {relative_evidence_dir}/",
        "?? audit_results/wbp_persistent_custom_profile_history_r2_2026-05-27/",
        "?? audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(current_contour_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _base_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": []
            if skip_git
            else _run(repo_root, ["git", "status", "--short"]).splitlines(),
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "master_plan_written_to_repo": False,
        },
        "historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "quarantine_classification": "out_of_scope_historical_residue",
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "codex_cli_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "codex_app_bundle_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleVersion",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
    }


def _parse_nullable_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    if normalized in {"unknown", "none", ""}:
        return None
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _layout(paths: dict[str, Any], evidence_dir: Path) -> NativeProbeLayout:
    profile_root = Path(paths["persistent_profile_root"])
    return NativeProbeLayout(
        tmp_root=evidence_dir,
        profile_dir=profile_root,
        launcher_path=Path(paths["launcher_path"]),
        launcher_stdout=evidence_dir / "persistent_r2_launcher.stdout.log",
        launcher_stderr=evidence_dir / "persistent_r2_launcher.stderr.log",
        custom_user_data_dir=Path(paths["user_data_dir"]),
        custom_home_dir=Path(paths["home_dir"]),
        custom_codex_home=Path(paths["codex_home"]),
        custom_tmp_dir=Path(paths["tmp_dir"]),
    )


def _copy_backup_if_needed(profile_root: Path, backup_root: Path) -> tuple[bool, str]:
    marker = backup_root / ".wbp_backup_complete"
    if not profile_root.exists():
        return False, ""
    if backup_root.exists():
        if marker.exists():
            return True, ""
        return False, "INCOMPLETE_BACKUP_EXISTS"
    try:
        shutil.copytree(profile_root, backup_root)
        marker.write_text(_utc_now() + "\n", encoding="utf-8")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def _apply_state_class_overrides(
    *,
    state_diff_packet: dict[str, Any],
    state_classes_observed: list[str],
) -> dict[str, Any]:
    if not state_classes_observed:
        return state_diff_packet
    normalized = sorted({value.strip() for value in state_classes_observed if value.strip()})
    synthetic_changes = [
        {
            "relative_path": f"synthetic/{state_class}.marker",
            "state_class": state_class,
            "raw_content_recorded": False,
        }
        for state_class in normalized
    ]
    packet = dict(state_diff_packet)
    packet["status"] = "ok"
    packet["reason_class"] = ""
    packet["created_count"] = max(len(normalized), int(packet.get("created_count", 0)))
    packet["state_classes_observed"] = normalized
    packet["classified_changes"] = synthetic_changes
    packet["synthetic_classification_input"] = True
    return packet


def classify_r2_persistent_profile_history_packet(
    *,
    execution_mode: str,
    profile_state_preservation_packet: dict[str, Any],
    thread_history_preservation_packet: dict[str, Any],
    false_green_audit_packet: dict[str, Any],
) -> dict[str, Any]:
    allowed_modes = {"inspection", "admission"}
    failed_checks: list[str] = []
    if execution_mode not in allowed_modes:
        failed_checks.append("execution_mode_must_be_inspection_or_admission")
    false_green_ok = false_green_audit_packet.get("status") == "ok"
    if not false_green_ok:
        failed_checks.append("persistent_false_green_guard_must_be_ok")

    profile_state_preserved = (
        profile_state_preservation_packet.get("status") == "ok"
        and profile_state_preservation_packet.get("profile_state_preserved") is True
    )
    thread_history_preserved = (
        thread_history_preservation_packet.get("status") == "ok"
        and thread_history_preservation_packet.get("thread_history_preserved") is True
    )
    inspection_mode = execution_mode == "inspection"
    admission_mode = execution_mode == "admission"

    if failed_checks:
        final_status = "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_BLOCKED_CLASSIFICATION_GUARD"
        status = "blocked"
        admitted = False
    elif admission_mode:
        final_status = "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_ADMITTED_NO_NATIVE_LAUNCH"
        status = "ok"
        admitted = True
    elif not profile_state_preserved:
        final_status = "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_BLOCKED_PROFILE_STATE_UNPROVEN"
        status = "blocked"
        admitted = False
    elif not thread_history_preserved:
        final_status = (
            "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_BLOCKED_THREAD_HISTORY_UNPROVEN"
        )
        status = "blocked"
        admitted = False
    else:
        final_status = "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_CLASSIFIED"
        status = "ok"
        admitted = False

    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_r2_classification",
        "status": status,
        "final_status": final_status,
        "execution_mode": execution_mode,
        "inspection_mode": inspection_mode,
        "admission_mode": admission_mode,
        "admitted": admitted,
        "native_launch_attempted": False,
        "native_launch_performed": False,
        "runtime_mutation_performed": False,
        "profile_state_preserved": profile_state_preserved,
        "thread_history_preserved": thread_history_preserved,
        "thread_history_requires_profile_state_preserved": True,
        "failed_checks": failed_checks,
        "route_trace_counted_as_history_proof": False,
        "owner_visible_thread_counted_as_storage_proof": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "keychain_prompt_resolved_claimed": False,
        "final_e2e_claimed": False,
    }


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    execution_mode: str,
    owner_visible_prior_thread: bool | None,
    owner_confirmation_collected: bool,
    state_classes_observed: list[str],
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = default_persistent_custom_profile_paths(
        profile_id=profile_id,
        base_dir=base_dir,
    )
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])

    packets = _base_packets(repo_root, evidence_dir, skip_git=skip_git)

    before_scan = scan_tree(profile_root)
    protected_before = scan_protected_surfaces()
    after_scan = scan_tree(profile_root)
    relaunch_scan = scan_tree(profile_root)
    protected_after = scan_protected_surfaces()

    before_identity = build_persistent_custom_profile_identity_packet(
        phase="before",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    relaunch_identity = build_persistent_custom_profile_identity_packet(
        phase="relaunch",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
        expected_profile_id=profile_id,
        expected_profile_root=profile_root,
    )
    state_diff = build_persistent_profile_state_diff_packet(
        before_scan=before_scan,
        after_scan=after_scan,
        relaunch_scan=relaunch_scan,
    )
    state_diff = _apply_state_class_overrides(
        state_diff_packet=state_diff,
        state_classes_observed=state_classes_observed,
    )
    relaunch_diff = build_persistent_profile_state_diff_packet(
        before_scan=after_scan,
        after_scan=relaunch_scan,
    )
    profile_state = build_persistent_profile_state_preservation_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        after_action_state_diff_packet=state_diff,
        after_relaunch_state_diff_packet=relaunch_diff,
    )
    owner_context = build_owner_visible_thread_context_packet(
        owner_visible_prior_thread=owner_visible_prior_thread,
        owner_confirmation_collected=owner_confirmation_collected,
    )
    thread_history_legacy = build_thread_history_preservation_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        state_diff_packet=state_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    thread_history_r2 = build_persistent_thread_history_preservation_r2_packet(
        profile_state_preservation_packet=profile_state,
        state_diff_packet=state_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    cleanup_policy = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=profile_root.exists(),
    )
    original_scope = build_original_codex_protected_surface_scope_packet()
    original_drift = build_original_codex_profile_drift_packet(
        before_surfaces=protected_before,
        after_surfaces=protected_after,
    )
    false_green = build_persistent_profile_false_green_audit(
        thread_history_packet=thread_history_legacy,
        owner_visible_thread_context_packet=owner_context,
        cleanup_policy_packet=cleanup_policy,
        original_drift_packet=original_drift,
    )
    classification = classify_r2_persistent_profile_history_packet(
        execution_mode=execution_mode,
        profile_state_preservation_packet=profile_state,
        thread_history_preservation_packet=thread_history_r2,
        false_green_audit_packet=false_green,
    )
    if packets["sync_gate_packet.json"]["status"] != "ok":
        classification = dict(classification)
        classification["status"] = "blocked"
        classification["final_status"] = (
            "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_BLOCKED_SYNC_GATE"
        )
        classification["admitted"] = False
        classification["failed_checks"] = [
            *classification.get("failed_checks", []),
            "sync_gate_must_be_ok",
        ]

    packets.update(
        {
            "declared_write_surfaces_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "declared_write_surfaces",
                "status": "ok",
                "declared_write_surfaces": [str(profile_root)],
                "native_launch_attempted": False,
                "persistent_write_performed": False,
                "protected_surfaces_write_allowed": False,
                "original_codex_profile_write_allowed": False,
            },
            "persistent_history_admission_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_history_admission",
                "status": "ok" if execution_mode in {"inspection", "admission"} else "blocked",
                "execution_mode": execution_mode,
                "inspection_only": execution_mode == "inspection",
                "admission_only": execution_mode == "admission",
                "native_launch_attempted": False,
                "native_launch_performed": False,
                "counts_as_history_proof": False,
            },
            "persistent_custom_profile_contract_packet.json": (
                build_persistent_custom_profile_contract_packet(
                    profile_id=profile_id,
                    profile_root=profile_root,
                    codex_home=codex_home,
                    user_data_dir=user_data_dir,
                )
            ),
            "persistent_custom_profile_identity_before_packet.json": before_identity,
            "persistent_custom_profile_identity_relaunch_packet.json": relaunch_identity,
            "persistent_profile_state_diff_packet.json": state_diff,
            "persistent_profile_relaunch_diff_packet.json": relaunch_diff,
            "persistent_profile_state_preservation_packet.json": profile_state,
            "persistent_thread_history_preservation_packet.json": thread_history_r2,
            "thread_history_preservation_legacy_packet.json": thread_history_legacy,
            "persistent_custom_profile_before_snapshot.json": before_scan,
            "persistent_custom_profile_after_admission_snapshot.json": after_scan,
            "persistent_custom_profile_relaunch_admission_snapshot.json": relaunch_scan,
            "persistent_r2_original_codex_before_snapshot.json": protected_before,
            "owner_visible_thread_context_packet.json": owner_context,
            "persistent_cleanup_policy_packet.json": cleanup_policy,
            "original_codex_protected_surface_scope_packet.json": original_scope,
            "original_codex_profile_drift_packet.json": original_drift,
            "integration_ownership_baseline_packet.json": (
                build_integration_ownership_baseline_packet()
            ),
            "persistent_profile_false_green_audit.json": false_green,
            "persistent_custom_profile_history_r2_classification_packet.json": (
                classification
            ),
            "persistent_custom_profile_history_r2_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_custom_profile_history_r2_summary",
                "status": classification["status"],
                "final_status": classification["final_status"],
                "execution_mode": execution_mode,
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "profile_state_preserved": classification["profile_state_preserved"],
                "thread_history_preserved": classification["thread_history_preserved"],
                "thread_history_requires_profile_state_preserved": True,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "keychain_prompt_resolved_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    )
    return packets


def build_first_launch_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    endpoint: str,
    model: str,
    startup_wait_seconds: float,
) -> dict[str, dict[str, Any]]:
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        profile_id=profile_id,
        base_dir=base_dir,
        execution_mode="admission",
        owner_visible_prior_thread=None,
        owner_confirmation_collected=False,
        state_classes_observed=[],
    )
    if packets["sync_gate_packet.json"]["status"] != "ok":
        packets["persistent_r2_first_launch_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_r2_first_launch",
            "status": "blocked",
            "reason_class": "SYNC_GATE_BLOCKED",
            "native_launch_attempted": False,
        }
        return packets

    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    backup_root = profile_root.parent / f"{profile_id}.backup"
    profile_existed_before = profile_root.exists()
    backup_created, backup_error = _copy_backup_if_needed(profile_root, backup_root)
    if backup_error:
        packets["persistent_r2_backup_rollback_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_backup_rollback",
            "status": "blocked",
            "reason_class": "PERSISTENT_BACKUP_ROLLBACK_MISSING",
            "profile_root": str(profile_root),
            "backup_root": str(backup_root),
            "profile_existed_before": True,
            "backup_created": False,
            "backup_complete_marker_present": False,
            "backup_error_class": backup_error.split(":", 1)[0],
            "backup_error_recorded_without_file_contents": True,
            "rollback_expectation_declared": True,
            "rollback_executed": False,
        }
        packets["persistent_r2_process_inventory_backup_blocked_packet.json"] = (
            collect_codex_process_inventory(custom_user_data_dir=str(Path(paths["user_data_dir"])))
        )
        packets["persistent_custom_profile_history_r2_summary_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_history_r2_summary",
            "status": "blocked",
            "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BLOCKED_BACKUP_ROLLBACK",
            "execution_mode": "first-launch",
            "profile_id": profile_id,
            "profile_root": str(profile_root),
            "native_launch_attempted": False,
            "backup_blocked": True,
            "profile_state_preserved": False,
            "thread_history_preserved": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "keychain_prompt_resolved_claimed": False,
            "final_e2e_claimed": False,
        }
        return packets
    runtime_paths = RuntimePaths.from_env()
    local_token = emit_local_token(runtime_paths)
    layout = _layout(paths, evidence_dir)
    materialized = materialize_probe_profile(
        layout=layout,
        endpoint=endpoint,
        model=model,
        auth_command_path=repo_root / "wbp_codex_auth_command.py",
        local_token=local_token,
    )
    launch = launch_native_candidate(
        repo_root=repo_root,
        layout=layout,
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    packets["persistent_r2_backup_rollback_packet.json"] = build_persistent_backup_rollback_packet(
        profile_root=profile_root,
        backup_root=backup_root,
        profile_existed_before=profile_existed_before,
        backup_created=backup_created,
    )
    packets["persistent_r2_first_launch_packet.json"] = {
        **launch,
        "packet_kind": "persistent_r2_first_launch",
        "status": "ok" if launch["custom_process_observed"] else "blocked",
        "profile_mode": "persistent_custom",
        "materialized_profile": materialized,
        "local_listener_token_materialized": True,
        "raw_token_recorded": False,
        "raw_prompt_recorded": False,
    }
    packets["persistent_r2_profile_after_first_launch_snapshot.json"] = scan_tree(profile_root)
    packets["persistent_custom_profile_history_r2_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_r2_summary",
        "status": "blocked",
        "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2_OWNER_ACTION_REQUIRED"
        if launch["custom_process_observed"]
        else "WBP_CUSTOM_PERSISTENT_PROFILE_BLOCKED_NATIVE_LAUNCH_FAILED",
        "execution_mode": "first-launch",
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "native_launch_attempted": True,
        "custom_process_observed": launch["custom_process_observed"],
        "owner_action_required": launch["custom_process_observed"],
        "profile_state_preserved": False,
        "thread_history_preserved": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "keychain_prompt_resolved_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def build_relaunch_classification_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_visible_prior_thread: bool | None,
    owner_confirmation_collected: bool,
    startup_wait_seconds: float,
) -> dict[str, dict[str, Any]]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    before_scan = json.loads(
        (evidence_dir / "persistent_custom_profile_before_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    protected_before = json.loads(
        (evidence_dir / "persistent_r2_original_codex_before_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    after_action_scan = scan_tree(profile_root)
    termination = terminate_custom_processes(str(user_data_dir))
    runtime_paths = RuntimePaths.from_env()
    relaunch = launch_native_candidate(
        repo_root=repo_root,
        layout=_layout(paths, evidence_dir),
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    relaunch_scan = scan_tree(profile_root)
    protected_after = scan_protected_surfaces()

    before_identity = build_persistent_custom_profile_identity_packet(
        phase="before",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=Path(paths["codex_home"]),
        user_data_dir=user_data_dir,
    )
    relaunch_identity = build_persistent_custom_profile_identity_packet(
        phase="relaunch",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=Path(paths["codex_home"]),
        user_data_dir=user_data_dir,
        expected_profile_id=profile_id,
        expected_profile_root=profile_root,
    )
    after_action_diff = build_persistent_profile_state_diff_packet(
        before_scan=before_scan,
        after_scan=after_action_scan,
    )
    relaunch_diff = build_persistent_profile_state_diff_packet(
        before_scan=after_action_scan,
        after_scan=relaunch_scan,
    )
    profile_state = build_persistent_profile_state_preservation_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        after_action_state_diff_packet=after_action_diff,
        after_relaunch_state_diff_packet=relaunch_diff,
    )
    owner_context = build_owner_visible_thread_context_packet(
        owner_visible_prior_thread=owner_visible_prior_thread,
        owner_confirmation_collected=owner_confirmation_collected,
    )
    thread_history = build_persistent_thread_history_preservation_r2_packet(
        profile_state_preservation_packet=profile_state,
        state_diff_packet=after_action_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    original_drift = build_original_codex_profile_drift_packet(
        before_surfaces=protected_before,
        after_surfaces=protected_after,
    )
    cleanup = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=profile_root.exists(),
    )
    false_green = build_persistent_profile_false_green_audit(
        thread_history_packet={"route_trace_counted_as_saved_thread_proof": False},
        owner_visible_thread_context_packet=owner_context,
        cleanup_policy_packet=cleanup,
        original_drift_packet=original_drift,
    )
    final_ok = (
        profile_state["profile_state_preserved"]
        and relaunch["custom_process_observed"]
        and false_green["status"] == "ok"
    )
    final_status = (
        "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
        if final_ok
        else "WBP_CUSTOM_PERSISTENT_PROFILE_BLOCKED_STATE_NOT_PRESERVED"
    )
    return {
        "persistent_r2_profile_after_thread_snapshot.json": after_action_scan,
        "persistent_r2_first_launch_termination_packet.json": termination,
        "persistent_r2_relaunch_packet.json": {
            **relaunch,
            "packet_kind": "persistent_r2_relaunch",
            "status": "ok" if relaunch["custom_process_observed"] else "blocked",
            "profile_mode": "persistent_custom",
        },
        "persistent_r2_profile_after_relaunch_snapshot.json": relaunch_scan,
        "persistent_r2_identity_relaunch_packet.json": relaunch_identity,
        "persistent_r2_state_diff_packet.json": after_action_diff,
        "persistent_r2_relaunch_state_diff_packet.json": relaunch_diff,
        "persistent_r2_profile_state_preservation_packet.json": profile_state,
        "persistent_r2_owner_visible_thread_context_packet.json": owner_context,
        "persistent_r2_thread_history_preservation_packet.json": thread_history,
        "persistent_r2_original_codex_after_snapshot.json": protected_after,
        "persistent_r2_original_codex_drift_packet.json": original_drift,
        "persistent_r2_cleanup_policy_packet.json": cleanup,
        "persistent_r2_false_green_audit.json": false_green,
        "persistent_custom_profile_history_r2_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_history_r2_summary",
            "status": "ok" if final_ok else "blocked",
            "final_status": final_status,
            "execution_mode": "relaunch-classify",
            "profile_id": profile_id,
            "profile_root": str(profile_root),
            "native_launch_attempted": True,
            "relaunch_attempted": True,
            "profile_state_preserved": profile_state["profile_state_preserved"],
            "thread_history_preserved": thread_history["thread_history_preserved"],
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "keychain_prompt_resolved_claimed": False,
            "final_e2e_claimed": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-history-r2-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(
            ROOT / "audit_results/wbp_persistent_custom_profile_history_r2_2026-05-27"
        ),
    )
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", default="")
    parser.add_argument(
        "--execution-mode",
        choices=["inspection", "admission", "first-launch", "relaunch-classify"],
        default="inspection",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:8318/v1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--startup-wait-seconds", type=float, default=12.0)
    parser.add_argument("--owner-visible-prior-thread", default="unknown")
    parser.add_argument("--owner-confirmation-collected", action="store_true")
    parser.add_argument(
        "--state-class-observed",
        action="append",
        default=[],
        help="Synthetic state class evidence for bounded classification (no launch).",
    )
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if args.execution_mode == "first-launch":
        packets = build_first_launch_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            endpoint=args.endpoint,
            model=args.model,
            startup_wait_seconds=args.startup_wait_seconds,
        )
    elif args.execution_mode == "relaunch-classify":
        packets = build_relaunch_classification_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            owner_visible_prior_thread=_parse_nullable_bool(args.owner_visible_prior_thread),
            owner_confirmation_collected=args.owner_confirmation_collected,
            startup_wait_seconds=args.startup_wait_seconds,
        )
    else:
        packets = build_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            execution_mode=args.execution_mode,
            owner_visible_prior_thread=_parse_nullable_bool(args.owner_visible_prior_thread),
            owner_confirmation_collected=args.owner_confirmation_collected,
            state_classes_observed=list(args.state_class_observed),
            skip_git=args.skip_git,
        )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["persistent_custom_profile_history_r2_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
