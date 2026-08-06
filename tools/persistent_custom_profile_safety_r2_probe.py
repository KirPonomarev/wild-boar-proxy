#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Persistent Custom profile safety R2 evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.persistent_custom_profile_history_r2b_probe import (  # noqa: E402
    build_rollback_reference_packet,
    build_same_profile_process_gate_packet,
)
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    PROTECTED_SURFACE_PATHS,
    build_persistent_cleanup_policy_packet,
    build_persistent_concurrent_launch_policy_packet,
    build_persistent_custom_profile_contract_packet,
    default_persistent_custom_profile_paths,
    json_write,
)
from wild_boar_proxy.persistent_profile_backup_restore_dry_run import (  # noqa: E402
    PersistentBackupRestoreDryRunConfig,
    build_backup_path_authority_packet,
    build_destructive_action_guard_packet,
    build_original_profile_backup_restore_guard_packet,
    build_restore_path_authority_packet,
)
from wild_boar_proxy.persistent_profile_state_diff import marker_scan_text  # noqa: E402


TARGET_STATUS = "CUSTOM_CODEX_PERSISTENT_PROFILE_SAFE_FROM_ORDINARY_CLEANUP"
EVIDENCE_DIR_NAME = "audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28"
DEFAULT_REPAIR_EVIDENCE_DIR = (
    REPO_ROOT / "audit_results/wbp_persistent_custom_profile_backup_rollback_repair_r1_2026-05-27"
)

SOURCE_REQUIRED_PACKETS = (
    "backup_repair_summary_packet.json",
    "rollback_readiness_packet.json",
    "state_backup_manifest_packet.json",
    "cache_exclusion_manifest_packet.json",
    "timestamped_backup_complete_marker_packet.json",
    "backup_repair_policy_packet.json",
    "backup_repair_false_green_audit.json",
    "incomplete_backup_classification_packet.json",
)

FORBIDDEN_TRUE_FIELDS = {
    "lock_acquired",
    "backup_created_in_current_contour",
    "restore_executed",
    "restore_execution_allowed",
    "cleanup_attempted",
    "cleanup_executed",
    "delete_execution_allowed",
    "destructive_action_performed",
    "thread_history_claimed",
    "thread_history_preservation_claimed",
    "profile_state_preserved",
    "profile_storage_persistence_claimed",
    "auth_proof_claimed",
    "native_ux_claimed",
    "final_e2e_claimed",
    "all_users_claimed",
    "prompt_absence_counts_as_auth",
    "real_user_keychain_modified",
    "raw_prompt_recorded",
    "raw_secret_recorded",
    "content_recorded",
    "content_restored",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def run_text(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"
    if check and process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    path = _resolved(path)
    parent = _resolved(parent)
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(left: Path, right: Path) -> bool:
    left = _resolved(left)
    right = _resolved(right)
    return _path_is_relative_to(left, right) or _path_is_relative_to(right, left)


def _field_true(value: Any, field: str) -> bool:
    if isinstance(value, dict):
        if value.get(field) is True:
            return True
        return any(_field_true(nested, field) for nested in value.values())
    if isinstance(value, list):
        return any(_field_true(nested, field) for nested in value)
    return False


def _scan_forbidden_true(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_FIELDS and nested is True:
                findings.append(nested_path)
            findings.extend(_scan_forbidden_true(nested, nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_scan_forbidden_true(nested, f"{prefix}[{index}]"))
    return findings


def _original_overlap(path: Path) -> bool:
    resolved = _resolved(path)
    return any(_paths_overlap(resolved, protected) for protected in PROTECTED_SURFACE_PATHS.values())


def historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    if skip_git:
        return [], [], []
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/persistent_custom_profile_history_r2b_probe.py",
        "tools/persistent_custom_profile_safety_r2_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tests/test_persistent_custom_profile_safety_r2_probe.py",
    }
    supporting_cross_contour = {
        "tools/persistent_profile_backup_restore_dry_run_readiness_r4_probe.py",
    }
    admitted_current_evidence_dirs = (f"{relative_evidence_dir}/", f"{EVIDENCE_DIR_NAME}/")
    def is_current_contour_line(line: str) -> bool:
        path = line[3:] if len(line) > 3 else line.strip()
        return (
            path in admitted_current_contour
            or path in supporting_cross_contour
            or path.startswith(admitted_current_evidence_dirs)
        )

    supporting_dirty = [
        line
        for line in status_lines
        if (line[3:] if len(line) > 3 else line.strip()) in supporting_cross_contour
    ]
    quarantined = [
        line
        for line in status_lines
        if not is_current_contour_line(line)
    ]
    unexpected_dirty: list[str] = []
    return quarantined, unexpected_dirty, supporting_dirty


def build_sync_gate_packet(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> dict[str, Any]:
    quarantined, unexpected_dirty, supporting_dirty = historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return packet(
        "persistent_profile_safety_sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        git_status_short=[] if skip_git else run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        supporting_cross_contour_dirty_entries=supporting_dirty,
        cross_contour_support_declared=bool(supporting_dirty),
        current_contour="CUSTOM_CODEX_PERSISTENT_PROFILE_SAFETY_R2",
        master_plan_written_to_repo=False,
    )


def build_historical_quarantine_packet(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> dict[str, Any]:
    quarantined, unexpected_dirty, supporting_dirty = historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return packet(
        "persistent_profile_safety_historical_quarantine",
        status="ok" if not unexpected_dirty else "blocked",
        quarantined_paths=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        supporting_cross_contour_dirty_entries=supporting_dirty,
        current_contour_relies_on_quarantined_paths=False,
        current_contour_mutates_quarantined_paths=False,
        current_contour_stages_quarantined_paths=False,
    )


def build_version_pinning_packet(repo_root: Path, *, skip_git: bool = False) -> dict[str, Any]:
    return packet(
        "persistent_profile_safety_version_pinning",
        codex_cli_version="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["codex", "--version"]),
        codex_cli_path="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["which", "codex"]),
        codex_app_path="/Applications/Codex.app",
        codex_app_version="SKIPPED_FOR_TEST"
        if skip_git
        else run_text(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        codex_app_bundle_version="SKIPPED_FOR_TEST"
        if skip_git
        else run_text(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        wbp_git_commit="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True),
    )


def _load_source_packets(
    repair_evidence_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]:
    parsed: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    invalid: dict[str, str] = {}
    for filename in SOURCE_REQUIRED_PACKETS:
        path = repair_evidence_dir / filename
        if not path.exists():
            missing.append(filename)
            continue
        try:
            parsed[filename] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            invalid[filename] = str(exc)
    return parsed, missing, invalid


def build_source_inventory_packet(repair_evidence_dir: Path) -> dict[str, Any]:
    parsed, missing, invalid = _load_source_packets(repair_evidence_dir)
    return packet(
        "persistent_profile_safety_source_inventory",
        status="ok" if not missing and not invalid else "blocked",
        repair_evidence_dir=str(repair_evidence_dir),
        required_packets=list(SOURCE_REQUIRED_PACKETS),
        missing_packets=missing,
        invalid_json_packets=invalid,
        loaded_packet_count=len(parsed),
        source_chain_is_historical_completed_evidence=True,
        current_contour_backup_created=False,
    )


def build_timestamped_backup_complete_marker_packet(
    *,
    repair_evidence_dir: Path,
) -> dict[str, Any]:
    parsed, missing, invalid = _load_source_packets(repair_evidence_dir)
    if missing or invalid:
        return packet(
            "persistent_profile_safety_timestamped_backup_complete_marker",
            status="blocked",
            reason_class="SAFETY_SOURCE_EVIDENCE_MISSING_OR_INVALID",
            repair_evidence_dir=str(repair_evidence_dir),
            missing_packets=missing,
            invalid_json_packets=invalid,
            complete_marker_created=False,
            complete_marker_created_after_manifest_success=False,
        )

    summary = parsed["backup_repair_summary_packet.json"]
    marker = parsed["timestamped_backup_complete_marker_packet.json"]
    marker_path = Path(str(marker.get("marker_path", ""))).expanduser()
    backup_root = Path(str(summary.get("timestamped_backup_root", ""))).expanduser()
    marker_exists = marker_path.exists() and marker_path.is_file()
    marker_payload_valid = False
    marker_payload: dict[str, Any] = {}
    if marker_exists:
        try:
            marker_payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            marker_payload = {}
        else:
            marker_payload_valid = (
                marker_payload.get("profile_id") == summary.get("profile_id")
                and marker_payload.get("backup_scope") == "selective_state_backup"
            )
    marker_matches_root = _resolved(marker_path) == (_resolved(backup_root) / ".wbp_backup_complete")
    ok = (
        marker.get("status") == "ok"
        and marker.get("complete_marker_created") is True
        and marker.get("complete_marker_created_after_manifest_success") is True
        and marker_exists
        and marker_matches_root
        and marker_payload_valid
    )
    return packet(
        "persistent_profile_safety_timestamped_backup_complete_marker",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "TIMESTAMPED_BACKUP_COMPLETE_MARKER_UNSAFE",
        repair_evidence_dir=str(repair_evidence_dir),
        timestamped_backup_root=str(_resolved(backup_root)),
        marker_path=str(_resolved(marker_path)),
        marker_exists=marker_exists,
        marker_matches_timestamped_backup_root=marker_matches_root,
        marker_payload_profile_id=str(marker_payload.get("profile_id", "")),
        marker_payload_backup_scope=str(marker_payload.get("backup_scope", "")),
        marker_payload_matches_summary=marker_payload_valid,
        complete_marker_created=marker.get("complete_marker_created") is True,
        complete_marker_created_after_manifest_success=(
            marker.get("complete_marker_created_after_manifest_success") is True
        ),
        current_contour_backup_created=False,
    )


def build_persistent_backup_readiness_packet(
    *,
    repair_evidence_dir: Path,
) -> dict[str, Any]:
    parsed, missing, invalid = _load_source_packets(repair_evidence_dir)
    if missing or invalid:
        return packet(
            "persistent_profile_safety_backup_readiness",
            status="blocked",
            reason_class="SAFETY_SOURCE_EVIDENCE_MISSING_OR_INVALID",
            repair_evidence_dir=str(repair_evidence_dir),
            missing_packets=missing,
            invalid_json_packets=invalid,
            rollback_ready=False,
            backup_created_in_current_contour=False,
        )

    rollback_reference = build_rollback_reference_packet(repair_evidence_dir=repair_evidence_dir)
    policy = parsed["backup_repair_policy_packet.json"]
    false_green = parsed["backup_repair_false_green_audit.json"]
    incomplete = parsed["incomplete_backup_classification_packet.json"]
    marker_packet = build_timestamped_backup_complete_marker_packet(
        repair_evidence_dir=repair_evidence_dir,
    )
    ok = (
        rollback_reference.get("status") == "ok"
        and policy.get("status") == "ok"
        and policy.get("persistent_profile_deletion_allowed") is False
        and false_green.get("status") == "ok"
        and incomplete.get("existing_backup_counted_as_rollback_proof") is False
        and marker_packet.get("status") == "ok"
    )
    return packet(
        "persistent_profile_safety_backup_readiness",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_BACKUP_READINESS_NOT_PROVEN",
        repair_evidence_dir=str(repair_evidence_dir),
        rollback_reference_status=rollback_reference.get("status"),
        rollback_ready=rollback_reference.get("rollback_ready") is True,
        timestamped_backup_root=str(rollback_reference.get("timestamped_backup_root", "")),
        marker_path=str(rollback_reference.get("marker_path", "")),
        copied_state_file_count=int(rollback_reference.get("copied_state_file_count", 0) or 0),
        excluded_cache_entry_count=int(rollback_reference.get("excluded_cache_entry_count", 0) or 0),
        backup_policy=str(policy.get("policy", "")),
        persistent_profile_deletion_allowed=policy.get("persistent_profile_deletion_allowed") is True,
        incomplete_backup_counted_as_rollback_proof=(
            incomplete.get("existing_backup_counted_as_rollback_proof") is True
        ),
        source_false_green_status=str(false_green.get("status", "")),
        complete_marker_created=marker_packet.get("complete_marker_created") is True,
        complete_marker_created_after_manifest_success=(
            marker_packet.get("complete_marker_created_after_manifest_success") is True
        ),
        backup_created_in_current_contour=False,
        restore_executed=False,
        thread_history_claimed=False,
    )


def build_persistent_profile_lock_enforcement_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    policy = build_persistent_concurrent_launch_policy_packet(
        policy="single_writer_only",
        lock_path=profile_root / ".wbp-persistent-profile.lock",
        launcher_enforces_policy=True,
    )
    gate = build_same_profile_process_gate_packet(
        custom_user_data_dir=user_data_dir,
        phase="persistent_profile_safety_r2",
    )
    inventory_usable = gate.get("inventory_usable") is True
    same_profile_process_present = gate.get("same_profile_process_present") is True
    ok = policy.get("status") == "ok" and inventory_usable
    reason_class = (
        str(policy.get("reason_class") or "")
        if policy.get("status") != "ok"
        else ("PROCESS_INVENTORY_UNUSABLE" if not inventory_usable else "")
    )
    return packet(
        "persistent_profile_lock_enforcement",
        status="ok" if ok else "blocked",
        reason_class=reason_class if not ok else "",
        persistent_profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        custom_user_data_dir=str(_resolved(user_data_dir)),
        lock_path=str(_resolved(profile_root / ".wbp-persistent-profile.lock")),
        launcher_enforces_policy=policy.get("launcher_enforces_policy") is True,
        policy_declared=str(policy.get("policy", "")),
        inventory_usable=inventory_usable,
        same_profile_process_present=same_profile_process_present,
        custom_process_count=(
            int(gate.get("custom_process_count"))
            if isinstance(gate.get("custom_process_count"), int)
            else -1
        ),
        same_profile_conflict_observed=same_profile_process_present,
        same_profile_conflict_classified=True,
        same_profile_existing_owner_counts_as_concurrent_launch=False,
        same_profile_new_launch_would_be_blocked=same_profile_process_present,
        launch_fail_closed_on_same_profile_conflict=True,
        launch_fail_closed_on_inventory_unusable=True,
        lock_acquired=False,
        single_writer_only_counts_as_lock_acquired=False,
    )


def build_persistent_profile_root_safety_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    home_dir = Path(paths["home_dir"])
    tmp_dir = Path(paths["tmp_dir"])
    runtime_tmp_dir = Path(
        str(paths.get("runtime_tmp_dir") or (Path("/tmp") / f"wbp-cdx-{profile_id}"))
    )
    launcher_path = Path(paths["launcher_path"])
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    children = {
        "user_data_dir": user_data_dir,
        "home_dir": home_dir,
        "tmp_dir": tmp_dir,
        "launcher_path": launcher_path,
    }
    children_under_root = {
        name: _path_is_relative_to(path, profile_root) and _resolved(path) != _resolved(profile_root)
        for name, path in children.items()
    }
    runtime_tmp_lexical = _lexical_absolute(runtime_tmp_dir)
    tmp_root_lexical = _lexical_absolute(Path("/tmp"))
    try:
        runtime_tmp_lexical.relative_to(tmp_root_lexical)
        runtime_tmp_lexically_under_tmp_root = True
    except ValueError:
        runtime_tmp_lexically_under_tmp_root = False
    runtime_tmp_resolved_under_profile_tmp = _path_is_relative_to(runtime_tmp_dir, tmp_dir)
    runtime_tmp_resolved_acceptable = (
        runtime_tmp_lexically_under_tmp_root
        or runtime_tmp_resolved_under_profile_tmp
    )
    protected_overlap = any(
        _original_overlap(path)
        for path in (profile_root, codex_home, user_data_dir, home_dir, tmp_dir, launcher_path)
    )
    ok = (
        contract.get("status") == "ok"
        and _resolved(profile_root) == _resolved(codex_home)
        and all(children_under_root.values())
        and runtime_tmp_resolved_acceptable
        and not protected_overlap
    )
    return packet(
        "persistent_profile_root_safety",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_PROFILE_ROOT_BOUNDARY_UNSAFE",
        persistent_profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        codex_home=str(_resolved(codex_home)),
        user_data_dir=str(_resolved(user_data_dir)),
        home_dir=str(_resolved(home_dir)),
        tmp_dir=str(_resolved(tmp_dir)),
        runtime_tmp_dir=str(_resolved(runtime_tmp_dir)),
        runtime_tmp_dir_lexical=str(runtime_tmp_lexical),
        launcher_path=str(_resolved(launcher_path)),
        codex_home_equals_profile_root=_resolved(codex_home) == _resolved(profile_root),
        child_paths_under_profile_root=children_under_root,
        runtime_tmp_dir_under_tmp_root=runtime_tmp_lexically_under_tmp_root,
        runtime_tmp_dir_resolves_under_profile_tmp=runtime_tmp_resolved_under_profile_tmp,
        runtime_tmp_dir_symlink_target_allowed=runtime_tmp_resolved_acceptable,
        protected_surface_overlap=protected_overlap,
        browser_client_path_authority=False,
        remote_client_path_authority=False,
        cleanup_deletes_persistent_profile_by_default=False,
        root_safety_counts_as_thread_history_proof=False,
    )


def build_restore_target_safety_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
    backup_root: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    if backup_root is None or not str(backup_root):
        return packet(
            "persistent_profile_restore_target_safety",
            status="blocked",
            reason_class="TIMESTAMPED_BACKUP_ROOT_MISSING",
            persistent_profile_id=profile_id,
            persistent_profile_root=str(_resolved(profile_root)),
            restore_target_root=str(_resolved(profile_root)),
            restore_target_is_persistent_profile_root=True,
            restore_target_escapes_persistent_profile=False,
            restore_executed=False,
            restore_execution_allowed=False,
        )

    config = PersistentBackupRestoreDryRunConfig(
        profile_id=profile_id,
        persistent_profile_root=profile_root,
        backup_root=backup_root,
        restore_target_root=profile_root,
        wbp_backup_root=profile_root.parent,
        original_codex_home=PROTECTED_SURFACE_PATHS["codex_dir"],
        original_app_support_dir=PROTECTED_SURFACE_PATHS["default_app_support_codex"],
    )
    backup_path = build_backup_path_authority_packet(config)
    restore_path = build_restore_path_authority_packet(config)
    destructive_guard = build_destructive_action_guard_packet(config)
    original_guard = build_original_profile_backup_restore_guard_packet(config)
    ok = all(
        packet_["status"] == "ok"
        for packet_ in (backup_path, restore_path, destructive_guard, original_guard)
    )
    return packet(
        "persistent_profile_restore_target_safety",
        status="ok" if ok else "blocked",
        reason_class=""
        if ok
        else (
            str(restore_path.get("reason_class", ""))
            or str(backup_path.get("reason_class", ""))
            or str(destructive_guard.get("reason_class", ""))
            or str(original_guard.get("reason_class", ""))
        ),
        persistent_profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        backup_root=str(_resolved(backup_root)),
        restore_target_root=str(_resolved(profile_root)),
        backup_root_under_wbp_backup_root=backup_path.get("backup_root_under_wbp_backup_root") is True,
        backup_root_overlaps_original_codex=backup_path.get("backup_root_overlaps_original_codex") is True,
        restore_target_is_persistent_profile_root=(
            restore_path.get("restore_target_is_persistent_profile_root") is True
        ),
        restore_target_escapes_persistent_profile=(
            restore_path.get("restore_target_escapes_persistent_profile") is True
        ),
        restore_target_overlaps_original_codex=(
            restore_path.get("restore_target_overlaps_original_codex") is True
        ),
        restore_target_overlaps_backup_root=(
            restore_path.get("restore_target_overlaps_backup_root") is True
        ),
        destructive_action_performed=False,
        restore_executed=False,
        restore_execution_allowed=False,
        owner_authorization_required_for_destructive_restore=(
            destructive_guard.get("owner_authorization_required_for_destructive_restore") is True
        ),
    )


def build_persistent_cleanup_scope_boundary_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    tmp_dir = Path(paths["tmp_dir"])
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    policy = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=profile_root.exists(),
    )
    cleanup_target_is_profile_root = _resolved(tmp_dir) == _resolved(profile_root)
    cleanup_target_under_profile_root = _path_is_relative_to(tmp_dir, profile_root)
    cleanup_target_overlaps_original = _original_overlap(tmp_dir)
    ok = (
        contract.get("status") == "ok"
        and policy.get("status") == "ok"
        and cleanup_target_under_profile_root
        and not cleanup_target_is_profile_root
        and not cleanup_target_overlaps_original
        and policy.get("cleanup_deletes_persistent_profile_by_default") is False
        and policy.get("explicit_owner_delete_authorization_required") is True
    )
    return packet(
        "persistent_cleanup_scope_boundary",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_CLEANUP_SCOPE_UNSAFE",
        persistent_profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        cleanup_target_root=str(_resolved(tmp_dir)),
        cleanup_target_is_persistent_profile_root=cleanup_target_is_profile_root,
        cleanup_target_under_persistent_profile_root=cleanup_target_under_profile_root,
        cleanup_target_overlaps_original_codex=cleanup_target_overlaps_original,
        cleanup_deletes_persistent_profile_by_default=(
            policy.get("cleanup_deletes_persistent_profile_by_default") is True
        ),
        explicit_owner_delete_authorization_required=(
            policy.get("explicit_owner_delete_authorization_required") is True
        ),
        cleanup_attempted=False,
        cleanup_executed=False,
        profile_exists_during_check=profile_root.exists(),
        cleanup_counts_as_live_deletion_proof=False,
    )


def build_backup_restore_dry_run_packet(
    *,
    backup_readiness_packet: dict[str, Any],
    marker_packet: dict[str, Any],
    restore_target_packet: dict[str, Any],
) -> dict[str, Any]:
    ok = (
        backup_readiness_packet.get("status") == "ok"
        and marker_packet.get("status") == "ok"
        and restore_target_packet.get("status") == "ok"
        and backup_readiness_packet.get("backup_created_in_current_contour") is False
        and restore_target_packet.get("restore_executed") is False
        and restore_target_packet.get("restore_execution_allowed") is False
    )
    return packet(
        "persistent_profile_backup_restore_dry_run",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_BACKUP_RESTORE_DRY_RUN_UNSAFE",
        rollback_ready=backup_readiness_packet.get("rollback_ready") is True,
        timestamped_backup_root=str(backup_readiness_packet.get("timestamped_backup_root", "")),
        complete_marker_created=marker_packet.get("complete_marker_created") is True,
        complete_marker_created_after_manifest_success=(
            marker_packet.get("complete_marker_created_after_manifest_success") is True
        ),
        restore_target_is_persistent_profile_root=(
            restore_target_packet.get("restore_target_is_persistent_profile_root") is True
        ),
        restore_target_overlaps_backup_root=(
            restore_target_packet.get("restore_target_overlaps_backup_root") is True
        ),
        backup_created_in_current_contour=False,
        restore_executed=False,
        restore_execution_allowed=False,
        live_restore_proven=False,
        backup_export_import_production_ready_claimed=False,
    )


def build_failed_launch_non_destructive_packet(
    *,
    root_safety_packet: dict[str, Any],
    cleanup_boundary_packet: dict[str, Any],
    restore_target_packet: dict[str, Any],
) -> dict[str, Any]:
    ok = (
        root_safety_packet.get("status") == "ok"
        and cleanup_boundary_packet.get("status") == "ok"
        and restore_target_packet.get("status") == "ok"
        and cleanup_boundary_packet.get("cleanup_attempted") is False
        and cleanup_boundary_packet.get("cleanup_executed") is False
        and restore_target_packet.get("restore_executed") is False
    )
    return packet(
        "persistent_profile_failed_launch_non_destructive",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "FAILED_LAUNCH_NON_DESTRUCTIVE_BOUNDARY_UNSAFE",
        evidence_mode="read_only_boundary_classification",
        live_failed_launch_executed=False,
        failed_launch_simulated=True,
        failed_launch_can_delete_profile=False,
        cleanup_attempted=False,
        cleanup_executed=False,
        restore_executed=False,
        persistent_profile_state_written=False,
        failed_launch_boundary_counts_as_live_failure_proof=False,
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    for filename, payload in packets.items():
        findings.extend(f"{filename}.{path}" for path in _scan_forbidden_true(payload))
    required_packets = [
        "persistent_profile_lock_enforcement_packet.json",
        "persistent_backup_readiness_packet.json",
        "timestamped_backup_complete_marker_packet.json",
        "restore_target_safety_packet.json",
        "persistent_cleanup_scope_boundary_packet.json",
    ]
    blocked_required = [
        name for name in required_packets if packets.get(name, {}).get("status") != "ok"
    ]
    findings.extend(f"{name}.status=blocked" for name in blocked_required)
    return packet(
        "persistent_profile_safety_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_claims_present=bool(findings),
        thread_history_claimed=False,
        auth_proof_claimed=False,
        final_e2e_claimed=False,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    scan = marker_scan_text(serialized)
    raw_prompt_recorded = any(
        _field_true(payload, "raw_prompt_recorded") for payload in packets.values()
    )
    raw_secret_recorded = any(
        _field_true(payload, "raw_secret_recorded") for payload in packets.values()
    )
    blocked = (
        scan["raw_prompt_found"]
        or scan["raw_secret_found"]
        or raw_prompt_recorded
        or raw_secret_recorded
    )
    return packet(
        "persistent_profile_safety_secret_redaction_audit",
        status="blocked" if blocked else "ok",
        marker_findings=scan["marker_findings"],
        secret_pattern_findings=scan["secret_pattern_findings"],
        raw_prompt_found=scan["raw_prompt_found"],
        raw_secret_found=scan["raw_secret_found"],
        raw_prompt_recorded=raw_prompt_recorded,
        raw_secret_recorded=raw_secret_recorded,
        exhaustive_dlp_claimed=False,
    )


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true_fields: list[str] = []
    for filename, payload in packets.items():
        forbidden_true_fields.extend(
            f"{filename}.{field}"
            for field in sorted(FORBIDDEN_TRUE_FIELDS)
            if _field_true(payload, field)
        )
    layer_mixing_packets = [
        filename
        for filename, payload in packets.items()
        if payload.get("thread_history_claimed") is True
        or payload.get("auth_proof_claimed") is True
        or payload.get("final_e2e_claimed") is True
    ]
    return packet(
        "independent_persistent_profile_safety_audit",
        status="blocked" if forbidden_true_fields or layer_mixing_packets else "ok",
        forbidden_true_fields=forbidden_true_fields,
        layer_mixing_packets=layer_mixing_packets,
        current_live_cleanup_execution_collected=False,
        current_live_restore_execution_collected=False,
        text_only_audit_counted_as_pass=False,
    )


def build_scanner_fact_report_packet(
    packets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    lock = packets["persistent_profile_lock_enforcement_packet.json"]
    backup = packets["persistent_backup_readiness_packet.json"]
    restore = packets["restore_target_safety_packet.json"]
    cleanup = packets["persistent_cleanup_scope_boundary_packet.json"]
    return packet(
        "scanner_agent_fact_report",
        status="ok" if all(
            packets[name].get("status") == "ok"
            for name in (
                "persistent_profile_lock_enforcement_packet.json",
                "persistent_backup_readiness_packet.json",
                "restore_target_safety_packet.json",
                "persistent_cleanup_scope_boundary_packet.json",
            )
        ) else "blocked",
        facts={
            "same_profile_process_present": lock.get("same_profile_process_present") is True,
            "inventory_usable": lock.get("inventory_usable") is True,
            "rollback_ready": backup.get("rollback_ready") is True,
            "timestamped_backup_root": backup.get("timestamped_backup_root", ""),
            "restore_target_is_persistent_profile_root": (
                restore.get("restore_target_is_persistent_profile_root") is True
            ),
            "restore_target_overlaps_backup_root": (
                restore.get("restore_target_overlaps_backup_root") is True
            ),
            "cleanup_target_is_persistent_profile_root": (
                cleanup.get("cleanup_target_is_persistent_profile_root") is True
            ),
            "cleanup_deletes_persistent_profile_by_default": (
                cleanup.get("cleanup_deletes_persistent_profile_by_default") is True
            ),
        },
        non_claims={
            "thread_history_claimed": False,
            "auth_proof_claimed": False,
            "final_e2e_claimed": False,
        },
    )


def build_summary_packet(
    packets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required_packets = [
        "sync_gate_packet.json",
        "source_inventory_packet.json",
        "persistent_profile_root_safety_packet.json",
        "same_profile_lock_packet.json",
        "persistent_profile_lock_enforcement_packet.json",
        "backup_restore_dry_run_packet.json",
        "persistent_backup_readiness_packet.json",
        "timestamped_backup_complete_marker_packet.json",
        "cleanup_boundary_packet.json",
        "restore_target_safety_packet.json",
        "persistent_cleanup_scope_boundary_packet.json",
        "failed_launch_non_destructive_packet.json",
        "false_green_audit.json",
        "secret_redaction_audit.json",
        "independent_persistent_profile_safety_audit.json",
    ]
    missing = [name for name in required_packets if name not in packets]
    blocked = [name for name in required_packets if packets.get(name, {}).get("status") != "ok"]
    ok = not missing and not blocked
    return packet(
        "persistent_profile_safety_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "",
        missing_required_packets=missing,
        blocked_packets=blocked,
        lock_acquired=False,
        backup_created_in_current_contour=False,
        restore_executed=False,
        cleanup_attempted=False,
        thread_history_claimed=False,
        auth_proof_claimed=False,
        final_e2e_claimed=False,
    )


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    repair_evidence_dir: Path = DEFAULT_REPAIR_EVIDENCE_DIR,
    profile_id: str = "wbp-custom-main",
    base_dir: Path | None = None,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = build_sync_gate_packet(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    packets["historical_quarantine_packet.json"] = build_historical_quarantine_packet(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    packets["version_pinning_packet.json"] = build_version_pinning_packet(
        repo_root,
        skip_git=skip_git,
    )
    packets["source_inventory_packet.json"] = build_source_inventory_packet(repair_evidence_dir)
    packets["persistent_profile_lock_enforcement_packet.json"] = (
        build_persistent_profile_lock_enforcement_packet(
            profile_id=profile_id,
            base_dir=base_dir,
        )
    )
    packets["same_profile_lock_packet.json"] = packets[
        "persistent_profile_lock_enforcement_packet.json"
    ]
    packets["persistent_profile_root_safety_packet.json"] = (
        build_persistent_profile_root_safety_packet(
            profile_id=profile_id,
            base_dir=base_dir,
        )
    )
    packets["timestamped_backup_complete_marker_packet.json"] = (
        build_timestamped_backup_complete_marker_packet(
            repair_evidence_dir=repair_evidence_dir,
        )
    )
    packets["persistent_backup_readiness_packet.json"] = (
        build_persistent_backup_readiness_packet(
            repair_evidence_dir=repair_evidence_dir,
        )
    )
    backup_root_value = str(
        packets["persistent_backup_readiness_packet.json"].get("timestamped_backup_root", "")
    )
    backup_root = Path(backup_root_value).expanduser() if backup_root_value else None
    packets["restore_target_safety_packet.json"] = build_restore_target_safety_packet(
        profile_id=profile_id,
        base_dir=base_dir,
        backup_root=backup_root,
    )
    packets["persistent_cleanup_scope_boundary_packet.json"] = (
        build_persistent_cleanup_scope_boundary_packet(
            profile_id=profile_id,
            base_dir=base_dir,
        )
    )
    packets["cleanup_boundary_packet.json"] = packets[
        "persistent_cleanup_scope_boundary_packet.json"
    ]
    packets["backup_restore_dry_run_packet.json"] = build_backup_restore_dry_run_packet(
        backup_readiness_packet=packets["persistent_backup_readiness_packet.json"],
        marker_packet=packets["timestamped_backup_complete_marker_packet.json"],
        restore_target_packet=packets["restore_target_safety_packet.json"],
    )
    packets["failed_launch_non_destructive_packet.json"] = (
        build_failed_launch_non_destructive_packet(
            root_safety_packet=packets["persistent_profile_root_safety_packet.json"],
            cleanup_boundary_packet=packets["persistent_cleanup_scope_boundary_packet.json"],
            restore_target_packet=packets["restore_target_safety_packet.json"],
        )
    )
    packets["scanner_agent_fact_report_packet.json"] = build_scanner_fact_report_packet(packets)
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_persistent_profile_safety_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    packets["verification_results_packet.json"] = packet(
        "verification_results",
        status="ok"
        if all(
            packets[name].get("status") == "ok"
            for name in (
                "persistent_profile_lock_enforcement_packet.json",
                "persistent_backup_readiness_packet.json",
                "timestamped_backup_complete_marker_packet.json",
                "restore_target_safety_packet.json",
                "persistent_cleanup_scope_boundary_packet.json",
                "false_green_audit.json",
                "secret_redaction_audit.json",
                "independent_persistent_profile_safety_audit.json",
            )
        )
        else "blocked",
        top_level_packet_statuses={
            name: payload.get("status", "missing") for name, payload in packets.items()
        },
        ok_packet_count=sum(1 for payload in packets.values() if payload.get("status") == "ok"),
        blocked_packet_count=sum(
            1 for payload in packets.values() if payload.get("status") == "blocked"
        ),
    )
    packets["persistent_profile_safety_summary_packet.json"] = build_summary_packet(packets)
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-safety-r2")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", default=str(REPO_ROOT / EVIDENCE_DIR_NAME))
    parser.add_argument("--repair-evidence-dir", default=str(DEFAULT_REPAIR_EVIDENCE_DIR))
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    repair_evidence_dir = Path(args.repair_evidence_dir).resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        repair_evidence_dir=repair_evidence_dir,
        profile_id=args.profile_id,
        base_dir=base_dir,
    )
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    summary = packets["persistent_profile_safety_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
