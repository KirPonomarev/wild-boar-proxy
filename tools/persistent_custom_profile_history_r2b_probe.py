#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""R2B live-gated Persistent Custom profile relaunch probe.

This contour deliberately does not reuse the older R2 backup root as truth.
It imports the repaired timestamped rollback evidence, records bounded profile
manifests, and stops at the owner-action boundary before any history claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    build_persistent_cleanup_policy_packet,
    build_persistent_concurrent_launch_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    build_persistent_profile_false_green_audit,
    build_persistent_profile_state_preservation_packet,
    build_persistent_thread_history_preservation_r2_packet,
    classify_persistent_profile_state_class,
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
    json_write,
    launch_native_candidate,
    materialize_probe_profile,
    scan_protected_surfaces,
    terminate_custom_processes,
)
from wild_boar_proxy.keychain_preflight import prepare_isolated_home_keychain
from wild_boar_proxy.runtime import RuntimePaths
from wild_boar_proxy.token_command import emit_local_token

DEFAULT_REPAIR_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_backup_rollback_repair_r1_2026-05-27"
)
DEFAULT_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27"
)
DEFAULT_SAMPLE_LIMIT = 300


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _redact_owner_nonce_in_packet(value: Any, *, owner_nonce: str) -> Any:
    if not owner_nonce:
        return value
    if isinstance(value, str):
        return value.replace(owner_nonce, "<owner_nonce>")
    if isinstance(value, list):
        return [
            _redact_owner_nonce_in_packet(item, owner_nonce=owner_nonce)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _redact_owner_nonce_in_packet(item, owner_nonce=owner_nonce)
            for key, item in value.items()
        }
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
        "tools/persistent_custom_profile_history_r2b_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tests/test_persistent_custom_profile_history_r3_probe.py",
        "wild_boar_proxy/native_filesystem_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "?? audit_results/_tmp_wbp_catalog_prep_inspect/",
        "?? audit_results/custom_codex_persistent_thread_history_proof_r2_2026-05-28/",
        "?? audit_results/custom_codex_persistent_thread_history_proof_r3_2026-05-28/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? audit_results/wbp_web_control_surface_actions_wired_and_guarded_r2_2026-05-27/",
        "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
    )
    current_contour_prefixes = (f"?? {relative_evidence_dir}/",)
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
        "r2b_sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2b_sync_gate",
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
        "r2b_historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2b_historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "r2b_version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2b_version_pinning",
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


def build_rollback_reference_packet(*, repair_evidence_dir: Path) -> dict[str, Any]:
    repair_evidence_dir = repair_evidence_dir.expanduser().resolve(strict=False)
    summary_path = repair_evidence_dir / "backup_repair_summary_packet.json"
    readiness_path = repair_evidence_dir / "rollback_readiness_packet.json"
    state_manifest_path = repair_evidence_dir / "state_backup_manifest_packet.json"
    cache_manifest_path = repair_evidence_dir / "cache_exclusion_manifest_packet.json"
    marker_packet_path = repair_evidence_dir / "timestamped_backup_complete_marker_packet.json"
    missing = [
        str(path)
        for path in (
            summary_path,
            readiness_path,
            state_manifest_path,
            cache_manifest_path,
            marker_packet_path,
        )
        if not path.exists()
    ]
    if missing:
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2b_rollback_reference",
            "status": "blocked",
            "reason_class": "ROLLBACK_REPAIR_EVIDENCE_MISSING",
            "repair_evidence_dir": str(repair_evidence_dir),
            "missing_packets": missing,
            "rollback_ready": False,
            "counts_as_history_proof": False,
        }

    summary = _read_json(summary_path)
    readiness = _read_json(readiness_path)
    state_manifest = _read_json(state_manifest_path)
    cache_manifest = _read_json(cache_manifest_path)
    marker_packet = _read_json(marker_packet_path)
    marker_path = Path(str(marker_packet.get("marker_path", ""))).expanduser()
    backup_root = Path(str(summary.get("timestamped_backup_root", ""))).expanduser()
    resolved_marker_path = marker_path.resolve(strict=False)
    resolved_backup_root = backup_root.resolve(strict=False)
    marker_exists = marker_path.exists()
    marker_sha256 = _sha256_file(marker_path) if marker_exists and marker_path.is_file() else ""
    copied_count = int(state_manifest.get("copied_file_count", 0))
    excluded_count = int(cache_manifest.get("excluded_count", 0))
    expected_marker_path = resolved_backup_root / ".wbp_backup_complete"
    timestamped_backup_name_ok = (
        resolved_backup_root.name.startswith("wbp-custom-main.backup.")
        or ".backup." in resolved_backup_root.name
    )
    marker_matches_backup_root = resolved_marker_path == expected_marker_path
    ok = (
        summary.get("status") == "ok"
        and summary.get("final_status") == "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY"
        and readiness.get("rollback_ready") is True
        and marker_packet.get("status") == "ok"
        and marker_exists
        and bool(marker_sha256)
        and resolved_backup_root.exists()
        and timestamped_backup_name_ok
        and marker_matches_backup_root
        and copied_count > 0
        and excluded_count > 0
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2b_rollback_reference",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "ROLLBACK_REPAIR_NOT_READY",
        "repair_evidence_dir": str(repair_evidence_dir),
        "summary_packet_sha256": _sha256_file(summary_path),
        "readiness_packet_sha256": _sha256_file(readiness_path),
        "state_manifest_packet_sha256": _sha256_file(state_manifest_path),
        "cache_manifest_packet_sha256": _sha256_file(cache_manifest_path),
        "marker_packet_sha256": _sha256_file(marker_packet_path),
        "timestamped_backup_root": str(resolved_backup_root),
        "timestamped_backup_root_exists": resolved_backup_root.exists(),
        "timestamped_backup_name_ok": timestamped_backup_name_ok,
        "marker_path": str(resolved_marker_path),
        "marker_matches_timestamped_backup_root": marker_matches_backup_root,
        "marker_exists": marker_exists,
        "marker_sha256": marker_sha256,
        "rollback_ready": ok,
        "copied_state_file_count": copied_count,
        "excluded_cache_entry_count": excluded_count,
        "manifest_records_hashes_only": state_manifest.get("raw_content_recorded") is False,
        "repair_counts_as_thread_history_proof": False,
        "repair_counts_as_native_relaunch_proof": False,
        "repair_counts_as_route_or_egress_proof": False,
    }


def collect_bounded_profile_manifest(
    root: Path,
    *,
    phase: str,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
    changed_since_ns: int | None = None,
) -> dict[str, Any]:
    root = root.expanduser()
    counts = {"files": 0, "dirs": 0, "symlinks": 0, "other": 0}
    total_file_bytes = 0
    state_class_counts: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    changed_candidates: list[dict[str, Any]] = []
    fingerprint = hashlib.sha256()
    entry_count = 0
    max_mtime_ns = 0

    if root.exists():
        paths = sorted([root, *root.rglob("*")], key=lambda item: str(item))
        for path in paths:
            relative = "." if path == root else str(path.relative_to(root))
            try:
                stat = path.lstat()
                is_symlink = path.is_symlink()
                is_dir = path.is_dir()
                is_file = path.is_file()
            except OSError:
                kind = "other"
                size = 0
                mtime_ns = 0
            else:
                if is_symlink:
                    kind = "symlink"
                    counts["symlinks"] += 1
                elif is_dir:
                    kind = "dir"
                    counts["dirs"] += 1
                elif is_file:
                    kind = "file"
                    counts["files"] += 1
                    total_file_bytes += stat.st_size
                else:
                    kind = "other"
                    counts["other"] += 1
                size = stat.st_size
                mtime_ns = stat.st_mtime_ns
            max_mtime_ns = max(max_mtime_ns, mtime_ns)

            state_class = classify_persistent_profile_state_class(relative)
            state_class_counts[state_class] = state_class_counts.get(state_class, 0) + 1
            fingerprint.update(
                f"{relative}\0{kind}\0{size}\0{mtime_ns}\0{state_class}\n".encode("utf-8")
            )
            entry = {
                "relative_path": relative,
                "kind": kind,
                "size": size,
                "mtime_ns": mtime_ns,
                "state_class": state_class,
                "raw_content_recorded": False,
            }
            if len(samples) < sample_limit:
                samples.append(entry)
            if changed_since_ns is not None and mtime_ns >= changed_since_ns:
                if len(changed_candidates) < sample_limit:
                    changed_candidates.append(entry)
            entry_count += 1

    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2b_bounded_profile_manifest",
        "status": "ok" if root.exists() else "blocked",
        "reason_class": "" if root.exists() else "PERSISTENT_PROFILE_ROOT_MISSING",
        "phase": phase,
        "root": str(root),
        "exists": root.exists(),
        "bounded_manifest": True,
        "full_entry_list_recorded": False,
        "raw_content_recorded": False,
        "sample_limit": sample_limit,
        "entry_count": entry_count,
        "counts": counts,
        "total_file_bytes": total_file_bytes,
        "max_mtime_ns": max_mtime_ns,
        "state_class_counts": dict(sorted(state_class_counts.items())),
        "profile_fingerprint_sha256": fingerprint.hexdigest(),
        "entries_sample": samples,
        "entries_sample_truncated": entry_count > len(samples),
        "changed_since_ns": changed_since_ns,
        "changed_since_candidates_sample": changed_candidates,
        "changed_since_candidates_truncated": (
            changed_since_ns is not None and len(changed_candidates) >= sample_limit
        ),
    }


def build_bounded_state_diff_packet(
    *,
    before_manifest: dict[str, Any],
    after_manifest: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    before_count = int(before_manifest.get("entry_count", 0))
    after_count = int(after_manifest.get("entry_count", 0))
    changed = (
        before_manifest.get("profile_fingerprint_sha256")
        != after_manifest.get("profile_fingerprint_sha256")
    )
    changed_candidates = [
        {
            "relative_path": entry.get("relative_path", ""),
            "state_class": entry.get("state_class", "unclassified_profile_state"),
            "raw_content_recorded": False,
        }
        for entry in after_manifest.get("changed_since_candidates_sample", [])
        if isinstance(entry, dict)
    ]
    state_classes = sorted(
        {
            entry.get("state_class", "unclassified_profile_state")
            for entry in changed_candidates
            if isinstance(entry, dict)
        }
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2b_bounded_profile_state_diff",
        "status": "ok" if changed else "blocked",
        "reason_class": "" if changed else "PERSISTENT_PROFILE_STATE_UNCHANGED",
        "phase": phase,
        "bounded_diff": True,
        "before_fingerprint_sha256": before_manifest.get("profile_fingerprint_sha256", ""),
        "after_fingerprint_sha256": after_manifest.get("profile_fingerprint_sha256", ""),
        "before_entry_count": before_count,
        "after_entry_count": after_count,
        "created_count": max(after_count - before_count, 0),
        "deleted_count": max(before_count - after_count, 0),
        "changed_count": len(changed_candidates) if changed_candidates else int(changed),
        "state_classes_observed": state_classes,
        "classified_changes": changed_candidates,
        "raw_prompt_recorded": False,
        "raw_auth_recorded": False,
        "raw_session_body_recorded": False,
    }


def build_redacted_owner_nonce_prompt_packet(*, nonce: str) -> dict[str, Any]:
    prompt = (
        "WBP Persistent Custom R2B relaunch check. "
        f"Please reply with OK and this nonce only: {nonce}"
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2b_owner_nonce_prompt",
        "status": "ok" if nonce else "blocked",
        "nonce_sha256": _sha256_text(nonce) if nonce else "",
        "prompt_sha256": _sha256_text(prompt) if nonce else "",
        "nonce_recorded": False,
        "raw_nonce_recorded": False,
        "prompt_hash_recorded": bool(nonce),
        "raw_prompt_recorded": False,
        "prompt_template_shape": (
            "WBP Persistent Custom R2B relaunch check. "
            "Please reply with OK and this nonce only: <nonce>"
        ),
    }


def build_owner_action_boundary_packet(
    *,
    owner_ready_now: bool,
    prompt_entered: bool,
    nonce_used: bool,
    evidence_dir_preserved: bool,
) -> dict[str, Any]:
    ok = owner_ready_now and prompt_entered and nonce_used and evidence_dir_preserved
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2b_owner_action_boundary",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "OWNER_ACTION_MARKER_INCOMPLETE",
        "owner_ready_now": owner_ready_now,
        "prompt_entered": prompt_entered,
        "nonce_used": nonce_used,
        "evidence_dir_preserved": evidence_dir_preserved,
        "owner_action_required_before_relaunch_classification": True,
        "owner_action_counts_as_storage_proof": False,
        "owner_action_counts_as_route_proof": False,
        "owner_action_counts_as_ux_acceptance": False,
        "raw_prompt_recorded": False,
        "raw_nonce_recorded": False,
    }


def build_r3_thread_target_selection_packet(
    *,
    profile_root: Path,
    max_session_jsonl: int = 1,
    owner_nonce: str = "",
) -> dict[str, Any]:
    session_index = profile_root / "session_index.jsonl"
    selected: list[dict[str, Any]] = []
    nonce_sha256 = _sha256_text(owner_nonce) if owner_nonce else ""
    if session_index.exists():
        stat = session_index.lstat()
        selected.append(
            {
                "relative_path": "session_index.jsonl",
                "surface_type": "jsonl",
                "state_class": "session_state",
                "selection_reason": "session_index_root",
                "exists_now": True,
                "selection_score": 100,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "raw_content_recorded": False,
            }
        )
    session_rows: list[tuple[int, int, int, str]] = []
    sessions_root = profile_root / "sessions"
    if sessions_root.exists():
        for path in sessions_root.rglob("*.jsonl"):
            try:
                stat = path.lstat()
            except OSError:
                continue
            nonce_candidate = False
            if owner_nonce:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    text = ""
                nonce_candidate = owner_nonce in text
            session_rows.append(
                (
                    1 if nonce_candidate else 0,
                    int(stat.st_mtime_ns),
                    int(stat.st_size),
                    str(path.relative_to(profile_root)),
                )
            )
    session_rows.sort(reverse=True)
    for nonce_rank, mtime_ns, size, relative_path in session_rows[:max_session_jsonl]:
        selected.append(
            {
                "relative_path": relative_path,
                "surface_type": "jsonl",
                "state_class": "session_state",
                "selection_reason": "same_nonce_session_history_path"
                if nonce_rank
                else "session_history_path",
                "exists_now": True,
                "selection_score": 110 if nonce_rank else 90,
                "size": size,
                "mtime_ns": mtime_ns,
                "same_nonce_candidate": bool(nonce_rank),
                "nonce_sha256": nonce_sha256 if nonce_rank else "",
                "raw_content_recorded": False,
            }
        )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_thread_target_selection_r3",
        "status": "ok" if selected else "blocked",
        "reason_class": "" if selected else "NO_SAFE_THREAD_TARGETS_SELECTED",
        "selection_policy": "session_index_and_recent_sessions_jsonl_only",
        "owner_nonce_hash_recorded": bool(nonce_sha256),
        "same_nonce_candidate_selected": any(
            item.get("same_nonce_candidate") is True for item in selected
        ),
        "selected_hypothesis_count": len(selected),
        "selected_hypotheses": selected,
        "raw_content_recorded": False,
    }


def build_r3_cutoff_baseline_target_manifest(
    *,
    selection_packet: dict[str, Any],
    profile_root: Path,
    cutoff_ns: int,
    phase: str,
) -> dict[str, Any]:
    targets = []
    for item in selection_packet.get("selected_hypotheses", []):
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("relative_path", ""))
        selected_mtime = int(item.get("mtime_ns", 0) or 0)
        selected_size = int(item.get("size", 0) or 0)
        changed_after_cutoff = selected_mtime >= cutoff_ns if cutoff_ns else False
        targets.append(
            {
                "relative_path": relative_path,
                "exists": not changed_after_cutoff,
                "kind": "file",
                "size": 0 if changed_after_cutoff else selected_size,
                "mtime_ns": 0 if changed_after_cutoff else selected_mtime,
                "baseline_inferred_from_cutoff": True,
                "cutoff_ns": cutoff_ns,
                "selected_mtime_ns": selected_mtime,
                "selected_path_changed_after_cutoff": changed_after_cutoff,
                "raw_content_recorded": False,
                "content_hash_recorded": False,
                "durable_restoration_proven": False,
            }
        )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_target_manifest",
        "status": "ok" if targets else "blocked",
        "reason_class": "" if targets else "NO_TARGETS_SELECTED",
        "phase": phase,
        "profile_root": str(profile_root),
        "target_count": len(targets),
        "targets": targets,
        "metadata_only": True,
        "baseline_inferred_from_cutoff": True,
        "raw_content_recorded": False,
        "content_hash_recorded": False,
    }


def build_r3_owner_visible_thread_continuity_packet(
    *,
    visibility_result_packet: dict[str, Any],
    owner_visibility_packet: dict[str, Any],
) -> dict[str, Any]:
    same_nonce_visible = owner_visibility_packet.get("same_nonce_thread_visible") is True
    same_identity = visibility_result_packet.get("same_persistent_profile_identity") is True
    continuity = (
        visibility_result_packet.get("owner_visible_thread_continuity_classified") is True
        and same_nonce_visible
        and same_identity
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_visible_thread_continuity_r3",
        "status": "ok" if continuity else "blocked",
        "reason_class": ""
        if continuity
        else (
            "SAME_NONCE_THREAD_NOT_VISIBLE"
            if not same_nonce_visible
            else "PERSISTENT_PROFILE_IDENTITY_MISMATCH"
            if not same_identity
            else "OWNER_VISIBLE_THREAD_CONTINUITY_UNPROVEN"
        ),
        "same_persistent_profile_identity": same_identity,
        "same_nonce_thread_visible": same_nonce_visible,
        "owner_visible_thread_continuity_classified": continuity,
        "owner_visible_thread_counts_as_storage_proof": False,
        "storage_level_thread_history_proven": False,
        "durable_restoration_proven": False,
        "raw_thread_content_recorded": False,
    }


def build_r3_storage_level_history_correlation_packet(
    *,
    selection_packet: dict[str, Any],
    target_delta_packet: dict[str, Any],
    storage_correlation_packet: dict[str, Any],
    correlation_classification_packet: dict[str, Any],
) -> dict[str, Any]:
    selected_paths = [
        str(item.get("relative_path", ""))
        for item in selection_packet.get("selected_hypotheses", [])
        if isinstance(item, dict) and item.get("relative_path")
    ]
    rows = [
        row
        for row in target_delta_packet.get("target_delta_rows", [])
        if isinstance(row, dict) and str(row.get("relative_path", ""))
    ]
    has_session_index = "session_index.jsonl" in selected_paths
    session_rollout_paths = [path for path in selected_paths if path.startswith("sessions/")]
    has_single_session_rollout = len(session_rollout_paths) == 1
    selected_target_set_sufficient = (
        len(selected_paths) == 2 and has_session_index and has_single_session_rollout
    )
    row_by_path = {
        str(row.get("relative_path", "")): row
        for row in rows
        if row.get("relative_path")
    }
    session_index_row = row_by_path.get("session_index.jsonl", {})
    session_rollout_row = row_by_path.get(session_rollout_paths[0], {}) if session_rollout_paths else {}
    changed = int(target_delta_packet.get("changed_target_count", 0) or 0)
    retained = int(target_delta_packet.get("retained_target_count", 0) or 0)
    selected_target_delta_sufficient = (
        bool(session_index_row)
        and bool(session_rollout_row)
        and session_index_row.get("changed_after_owner_action") is True
        and session_index_row.get("retained_after_relaunch") is True
        and session_rollout_row.get("changed_after_owner_action") is True
        and session_rollout_row.get("retained_after_relaunch") is True
    )
    selected_same_nonce_binding = any(
        item.get("same_nonce_candidate") is True
        for item in selection_packet.get("selected_hypotheses", [])
        if isinstance(item, dict)
    )
    same_nonce_target_binding_proven = (
        selected_same_nonce_binding and selected_target_delta_sufficient
    )
    correlated = (
        storage_correlation_packet.get("storage_correlation_classified") is True
        and selected_target_set_sufficient
        and selected_target_delta_sufficient
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "storage_level_history_correlation_r3",
        "status": "ok" if correlated else "blocked",
        "reason_class": ""
        if correlated
        else (
            "SELECTED_THREAD_TARGET_SET_INSUFFICIENT"
            if not selected_target_set_sufficient
            else "SELECTED_THREAD_TARGET_DELTA_INSUFFICIENT"
            if not selected_target_delta_sufficient
            else "STORAGE_LEVEL_HISTORY_CORRELATION_UNPROVEN"
        ),
        "selected_target_count": len(selected_paths),
        "selected_target_paths": selected_paths,
        "selected_target_set_sufficient": selected_target_set_sufficient,
        "selected_target_delta_sufficient": selected_target_delta_sufficient,
        "selected_targets_changed_after_action": changed,
        "selected_targets_retained_after_relaunch": retained,
        "storage_correlation_classified": correlated,
        "correlation_classification": correlation_classification_packet.get(
            "final_status", ""
        ),
        "bounded_selected_session_target_correlation_proven": correlated,
        "same_nonce_target_binding_proven": same_nonce_target_binding_proven,
        "storage_level_thread_history_proven": same_nonce_target_binding_proven,
        "durable_restoration_proven": False,
        "target_delta_counts_as_thread_identity_proof": False,
        "raw_thread_content_recorded": False,
    }


def build_r3_thread_history_preservation_packet(
    *,
    profile_state_packet: dict[str, Any],
    owner_visible_thread_continuity_packet: dict[str, Any],
    storage_level_history_correlation_packet: dict[str, Any],
    keychain_packet: dict[str, Any],
) -> dict[str, Any]:
    profile_state_preserved = profile_state_packet.get("profile_state_preserved") is True
    same_nonce_visible = (
        owner_visible_thread_continuity_packet.get("same_nonce_thread_visible") is True
    )
    visible_continuity = (
        owner_visible_thread_continuity_packet.get(
            "owner_visible_thread_continuity_classified"
        )
        is True
    )
    storage_correlated = (
        storage_level_history_correlation_packet.get("storage_correlation_classified") is True
    )
    bounded_correlation_proven = (
        storage_level_history_correlation_packet.get(
            "bounded_selected_session_target_correlation_proven"
        )
        is True
    )
    same_nonce_target_binding_proven = (
        storage_level_history_correlation_packet.get("same_nonce_target_binding_proven")
        is True
    )
    keychain_ok = keychain_packet.get("status") == "ok"
    storage_level_thread_history_proven = (
        bounded_correlation_proven and same_nonce_target_binding_proven and keychain_ok
    )
    candidate = (
        profile_state_preserved
        and same_nonce_visible
        and visible_continuity
        and storage_correlated
        and keychain_ok
    )
    with_limits = candidate and bounded_correlation_proven and not storage_level_thread_history_proven
    preserved = candidate and storage_level_thread_history_proven
    if not profile_state_preserved:
        reason = "PROFILE_STATE_PRESERVATION_UNPROVEN"
    elif not same_nonce_visible:
        reason = "SAME_NONCE_THREAD_NOT_VISIBLE"
    elif not visible_continuity:
        reason = "OWNER_VISIBLE_THREAD_CONTINUITY_UNPROVEN"
    elif not storage_correlated:
        reason = "STORAGE_LEVEL_HISTORY_CORRELATION_UNPROVEN"
    elif not keychain_ok:
        reason = "PERSISTENT_KEYCHAIN_PRECONDITION_UNPROVEN"
    elif preserved or with_limits:
        reason = ""
    elif not bounded_correlation_proven:
        reason = "SELECTED_SESSION_TARGET_CORRELATION_UNPROVEN"
    elif not same_nonce_target_binding_proven:
        reason = "SAME_NONCE_STORAGE_BINDING_UNPROVEN"
    else:
        reason = "STORAGE_LEVEL_THREAD_HISTORY_UNPROVEN"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "thread_history_preservation_r3",
        "status": "ok" if preserved or with_limits else "blocked",
        "reason_class": reason,
        "profile_state_preserved": profile_state_preserved,
        "same_nonce_thread_visible": same_nonce_visible,
        "owner_visible_thread_continuity_classified": visible_continuity,
        "storage_correlation_classified": storage_correlated,
        "bounded_selected_session_target_correlation_proven": bounded_correlation_proven,
        "same_nonce_target_binding_proven": same_nonce_target_binding_proven,
        "thread_history_preservation_candidate": candidate,
        "thread_history_preserved": preserved,
        "storage_level_thread_history_proven": storage_level_thread_history_proven,
        "durable_restoration_proven": False,
        "thread_history_preserved_with_limits": with_limits,
        "thread_history_limit_class": "SAME_NONCE_STORAGE_BINDING_UNPROVEN"
        if with_limits
        else "",
        "storage_level_proof_scope": "selected_session_surface_metadata_plus_same_nonce_binding"
        if storage_level_thread_history_proven
        else "selected_session_surface_metadata_plus_same_nonce_visibility"
        if with_limits
        else "unproven",
        "owner_visible_thread_counted_as_storage_proof": False,
        "selected_target_delta_counts_as_thread_identity_proof": False,
        "prompt_absence_counted_as_auth_proof": False,
        "raw_thread_content_recorded": False,
    }


def build_r3_profile_state_with_thread_target_retention_packet(
    *,
    profile_state_packet: dict[str, Any],
    target_delta_packet: dict[str, Any],
) -> dict[str, Any]:
    retained_selected_targets = int(target_delta_packet.get("retained_target_count", 0) or 0)
    changed_selected_targets = int(target_delta_packet.get("changed_target_count", 0) or 0)
    target_retention_proven = retained_selected_targets >= 2 and changed_selected_targets >= 2
    if profile_state_packet.get("profile_state_preserved") is True or not target_retention_proven:
        return profile_state_packet
    if profile_state_packet.get("same_persistent_profile_identity") is not True:
        return profile_state_packet
    if profile_state_packet.get("after_action_storage_changed") is not True:
        return profile_state_packet
    adjusted = dict(profile_state_packet)
    adjusted.update(
        {
            "status": "ok",
            "reason_class": "",
            "profile_state_preserved": True,
            "after_relaunch_state_kept": True,
            "profile_state_preserved_by_selected_thread_target_retention": True,
            "selected_thread_targets_changed_after_action": changed_selected_targets,
            "selected_thread_targets_retained_after_relaunch": retained_selected_targets,
            "service_runtime_churn_not_counted_as_thread_history_loss": True,
            "counts_as_thread_history_proof": False,
        }
    )
    return adjusted


def build_r3_false_green_audit(
    *,
    owner_visible_thread_continuity_packet: dict[str, Any],
    storage_level_history_correlation_packet: dict[str, Any],
    thread_history_preservation_packet: dict[str, Any],
    legacy_r2_thread_history_packet: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        {
            "name": "owner_visible_not_storage_proof",
            "passed": owner_visible_thread_continuity_packet.get(
                "owner_visible_thread_counts_as_storage_proof"
            )
            is False,
        },
        {
            "name": "storage_correlation_not_durable_proof",
            "passed": storage_level_history_correlation_packet.get(
                "durable_restoration_proven"
            )
            is False
            and storage_level_history_correlation_packet.get(
                "target_delta_counts_as_thread_identity_proof"
            )
            is False,
        },
        {
            "name": "thread_history_packet_only_claims_bounded_storage_level_proof",
            "passed": thread_history_preservation_packet.get("durable_restoration_proven")
            is False
            and (
                thread_history_preservation_packet.get(
                    "storage_level_thread_history_proven"
                )
                is False
                or thread_history_preservation_packet.get("storage_level_proof_scope")
                in {
                    "selected_session_surface_metadata_plus_same_nonce_visibility",
                    "selected_session_surface_metadata_plus_same_nonce_binding",
                }
            ),
        },
        {
            "name": "thread_history_preserved_requires_storage_level_proof",
            "passed": thread_history_preservation_packet.get("thread_history_preserved")
            is not True
            or thread_history_preservation_packet.get("storage_level_thread_history_proven")
            is True,
        },
        {
            "name": "with_limits_not_promoted_to_full_storage_proof",
            "passed": thread_history_preservation_packet.get(
                "thread_history_preserved_with_limits"
            )
            is not True
            or (
                thread_history_preservation_packet.get("thread_history_preserved") is False
                and thread_history_preservation_packet.get(
                    "storage_level_thread_history_proven"
                )
                is False
                and thread_history_preservation_packet.get("thread_history_limit_class")
                == "SAME_NONCE_STORAGE_BINDING_UNPROVEN"
            ),
        },
        {
            "name": "legacy_r2_packet_not_used_as_final_claim",
            "passed": legacy_r2_thread_history_packet.get("thread_history_preserved") is False
            or thread_history_preservation_packet.get("thread_history_preserved") is True,
        },
    ]
    ok = all(check["passed"] for check in checks)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_thread_history_r3_false_green_audit",
        "status": "ok" if ok else "blocked",
        "checks": checks,
        "forbidden_claims_present": not ok,
        "legacy_r2_thread_history_packet_counted_as_final_claim": False,
        "text_only_audit_counted_as_pass": False,
    }


def build_r3_summary_packet(
    *,
    profile_id: str,
    profile_root: Path,
    relaunch_packet: dict[str, Any],
    profile_state_packet: dict[str, Any],
    owner_continuity_packet: dict[str, Any],
    storage_correlation_packet: dict[str, Any],
    thread_history_packet: dict[str, Any],
    keychain_packet: dict[str, Any],
    false_green_packet: dict[str, Any],
    legacy_false_green_packet: dict[str, Any],
) -> dict[str, Any]:
    full_pass = (
        relaunch_packet.get("custom_process_observed") is True
        and profile_state_packet.get("profile_state_preserved") is True
        and thread_history_packet.get("thread_history_preserved") is True
        and keychain_packet.get("status") == "ok"
        and false_green_packet.get("status") == "ok"
        and legacy_false_green_packet.get("status") == "ok"
    )
    with_limits = (
        relaunch_packet.get("custom_process_observed") is True
        and profile_state_packet.get("profile_state_preserved") is True
        and owner_continuity_packet.get("owner_visible_thread_continuity_classified") is True
        and storage_correlation_packet.get("storage_correlation_classified") is True
        and keychain_packet.get("status") == "ok"
        and false_green_packet.get("status") == "ok"
        and legacy_false_green_packet.get("status") == "ok"
        and thread_history_packet.get("thread_history_preserved_with_limits") is True
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_r3_summary",
        "status": "ok" if full_pass or with_limits else "blocked",
        "final_status": (
            "CUSTOM_CODEX_THREAD_HISTORY_PRESERVED_ACROSS_RELAUNCH"
            if full_pass
            else "CUSTOM_CODEX_PERSISTENT_THREAD_HISTORY_CLASSIFIED_WITH_LIMITS"
            if with_limits
            else "CUSTOM_CODEX_PERSISTENT_THREAD_HISTORY_BLOCKED"
        ),
        "execution_mode": "relaunch-classify",
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "native_launch_attempted": True,
        "relaunch_attempted": True,
        "profile_state_preserved": profile_state_packet.get("profile_state_preserved") is True,
        "owner_visible_thread_continuity_classified": (
            owner_continuity_packet.get("owner_visible_thread_continuity_classified") is True
        ),
        "storage_correlation_classified": (
            storage_correlation_packet.get("storage_correlation_classified") is True
        ),
        "thread_history_preservation_candidate": (
            thread_history_packet.get("thread_history_preservation_candidate") is True
        ),
        "thread_history_preserved": (
            thread_history_packet.get("thread_history_preserved") is True
        ),
        "thread_history_preserved_with_limits": (
            thread_history_packet.get("thread_history_preserved_with_limits") is True
        ),
        "storage_level_thread_history_proven": (
            thread_history_packet.get("storage_level_thread_history_proven") is True
        ),
        "durable_restoration_proven": (
            thread_history_packet.get("durable_restoration_proven") is True
        ),
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "keychain_prompt_resolved_claimed": False,
        "keychain_preflight_status": keychain_packet.get("status"),
        "native_ux_acceptance_claimed": False,
        "final_e2e_claimed": False,
    }


def build_same_profile_process_gate_packet(
    *,
    custom_user_data_dir: Path,
    phase: str,
) -> dict[str, Any]:
    inventory = collect_codex_process_inventory(
        custom_user_data_dir=str(custom_user_data_dir)
    )
    custom_process_count = inventory.get("custom_process_count")
    custom_process_lines = inventory.get("custom_process_lines")
    root_app_pids = inventory.get("root_app_pids")
    inventory_usable = (
        isinstance(custom_process_count, int)
        and custom_process_count >= 0
        and isinstance(custom_process_lines, list)
        and isinstance(root_app_pids, list)
    )
    same_profile_process_present = (
        inventory_usable and int(custom_process_count) > 0
    )
    blocked = (not inventory_usable) or same_profile_process_present
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2b_same_profile_process_gate",
        "status": "blocked" if blocked else "ok",
        "reason_class": (
            "PROCESS_INVENTORY_UNUSABLE"
            if not inventory_usable
            else (
            "SAME_PROFILE_PROCESS_ALREADY_RUNNING"
            if same_profile_process_present
            else ""
            )
        ),
        "phase": phase,
        "custom_user_data_dir": str(custom_user_data_dir),
        "inventory_usable": inventory_usable,
        "custom_process_count": int(custom_process_count)
        if isinstance(custom_process_count, int)
        else -1,
        "custom_process_lines": custom_process_lines
        if isinstance(custom_process_lines, list)
        else [],
        "same_profile_process_present": same_profile_process_present,
        "root_app_pid_count": len(root_app_pids) if isinstance(root_app_pids, list) else 0,
        "single_writer_only_counts_as_lock_acquired": False,
    }


def build_persistent_keychain_preflight_packet(
    *,
    isolated_home: Path,
    phase: str,
) -> dict[str, Any]:
    preflight = prepare_isolated_home_keychain(isolated_home=isolated_home)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_keychain_preflight",
        "status": str(preflight.get("status") or ""),
        "reason_class": str(preflight.get("machine_error_code") or ""),
        "phase": phase,
        "isolated_home": str(isolated_home),
        "isolated_default_keychain_verified": preflight.get(
            "isolated_default_keychain_verified"
        )
        is True,
        "isolated_search_list_verified": preflight.get(
            "isolated_search_list_verified"
        )
        is True,
        "prompt_avoidance_claim_scope": str(
            preflight.get("prompt_avoidance_claim_scope")
            or "keychain_not_found_prompt_only"
        ),
        "real_user_keychain_modified": False,
        "keychain_item_read": False,
        "keychain_reset_performed": False,
        "prompt_observation_collected": False,
        "prompt_observed": False,
    }


def _layout(paths: dict[str, Any], evidence_dir: Path) -> NativeProbeLayout:
    profile_root = Path(paths["persistent_profile_root"])
    return NativeProbeLayout(
        tmp_root=evidence_dir,
        profile_dir=profile_root,
        launcher_path=Path(paths["launcher_path"]),
        launcher_stdout=evidence_dir / "persistent_r2b_launcher.stdout.log",
        launcher_stderr=evidence_dir / "persistent_r2b_launcher.stderr.log",
        custom_user_data_dir=Path(paths["user_data_dir"]),
        custom_home_dir=Path(paths["home_dir"]),
        custom_codex_home=Path(paths["codex_home"]),
        custom_tmp_dir=Path(paths["tmp_dir"]),
    )


def _parse_nullable_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    if normalized in {"unknown", "none", ""}:
        return None
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _paths(profile_id: str, base_dir: Path | None) -> dict[str, Any]:
    return default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)


def _admission_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    repair_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    launcher_path = Path(paths["launcher_path"])
    protected_before = scan_protected_surfaces()
    before_manifest = collect_bounded_profile_manifest(profile_root, phase="before")
    rollback_reference = build_rollback_reference_packet(
        repair_evidence_dir=repair_evidence_dir
    )
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    identity = build_persistent_custom_profile_identity_packet(
        phase="before",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    launcher_selection = build_persistent_launcher_selection_packet(
        launcher_path=launcher_path,
        profile_mode="persistent_custom",
        selected_profile_id=profile_id,
        selected_profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    concurrent = build_persistent_concurrent_launch_policy_packet(
        policy="single_writer_only",
        lock_path=profile_root / ".wbp-persistent-profile.lock",
        launcher_enforces_policy=True,
    )
    cleanup = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=profile_root.exists(),
    )
    original_scope = build_original_codex_protected_surface_scope_packet()
    original_drift = build_original_codex_profile_drift_packet(
        before_surfaces=protected_before,
        after_surfaces=scan_protected_surfaces(),
    )
    original_drift_admissible = (
        original_drift.get("original_codex_write_performed_by_contour") is False
    )
    base = _base_packets(repo_root, evidence_dir, skip_git=skip_git)
    admission_ok = all(
        packet.get("status") == "ok"
        for packet in (
            base["r2b_sync_gate_packet.json"],
            rollback_reference,
            before_manifest,
            contract,
            identity,
            launcher_selection,
            concurrent,
            cleanup,
        )
    ) and original_drift_admissible
    base.update(
        {
            "r2b_rollback_reference_packet.json": rollback_reference,
            "r2b_declared_write_surfaces_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2b_declared_write_surfaces",
                "status": "ok",
                "declared_write_surfaces": [str(profile_root)],
                "persistent_profile_root": str(profile_root),
                "codex_home": str(codex_home),
                "user_data_dir": str(user_data_dir),
                "persistent_profile_deletion_allowed": False,
                "protected_surfaces_write_allowed": False,
                "original_codex_profile_write_allowed": False,
            },
            "persistent_custom_profile_contract_packet.json": contract,
            "persistent_custom_profile_identity_before_packet.json": identity,
            "persistent_launcher_selection_packet.json": launcher_selection,
            "persistent_concurrent_launch_policy_packet.json": concurrent,
            "persistent_cleanup_policy_packet.json": cleanup,
            "integration_ownership_baseline_packet.json": (
                build_integration_ownership_baseline_packet()
            ),
            "original_codex_protected_surface_scope_packet.json": original_scope,
            "r2b_original_codex_before_snapshot.json": protected_before,
            "original_codex_profile_drift_packet.json": original_drift,
            "persistent_custom_profile_before_bounded_manifest.json": before_manifest,
            "r2b_admission_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2b_admission",
                "status": "ok" if admission_ok else "blocked",
                "reason_class": "" if admission_ok else "R2B_ADMISSION_BLOCKED",
                "execution_mode": "admission",
                "rollback_reference_status": rollback_reference.get("status"),
                "bounded_manifest_status": before_manifest.get("status"),
                "original_drift_status": original_drift.get("status"),
                "original_drift_classified": True,
                "original_codex_write_performed_by_contour": original_drift.get(
                    "original_codex_write_performed_by_contour"
                )
                is True,
                "original_drift_blocks_filesystem_pass_claim": original_drift.get("status")
                != "ok",
                "protected_filesystem_pass_claimed": False,
                "native_launch_attempted": False,
                "owner_action_required": False,
                "thread_history_claimed": False,
                "route_egress_model_claimed": False,
            },
            "persistent_custom_profile_history_r2b_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_custom_profile_history_r2b_summary",
                "status": "ok" if admission_ok else "blocked",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_ADMITTED_NO_NATIVE_LAUNCH"
                if admission_ok
                else "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_ADMISSION",
                "execution_mode": "admission",
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "owner_action_required": False,
                "profile_state_preserved": False,
                "thread_history_preserved": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "keychain_prompt_resolved_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    )
    return base


def build_first_launch_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    repair_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    endpoint: str,
    model: str,
    owner_nonce: str,
    startup_wait_seconds: float,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    packets = _admission_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        repair_evidence_dir=repair_evidence_dir,
        profile_id=profile_id,
        base_dir=base_dir,
        skip_git=skip_git,
    )
    admission = packets["r2b_admission_packet.json"]
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    before_manifest = packets["persistent_custom_profile_before_bounded_manifest.json"]
    owner_nonce_packet = build_redacted_owner_nonce_prompt_packet(nonce=owner_nonce)
    packets["r2b_owner_nonce_prompt_packet.json"] = owner_nonce_packet
    if admission.get("status") != "ok":
        packets["persistent_r2b_first_launch_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_r2b_first_launch",
            "status": "blocked",
            "reason_class": "R2B_ADMISSION_BLOCKED",
            "native_launch_attempted": False,
        }
        packets["persistent_custom_profile_history_r2b_summary_packet.json"].update(
            {
                "status": "blocked",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_ADMISSION",
                "execution_mode": "first-launch",
            }
        )
        return packets

    same_profile_gate = build_same_profile_process_gate_packet(
        custom_user_data_dir=user_data_dir,
        phase="before_first_launch",
    )
    packets["persistent_r2b_same_profile_process_gate_before_first_launch_packet.json"] = (
        same_profile_gate
    )
    if same_profile_gate.get("status") != "ok":
        reason_class = str(
            same_profile_gate.get("reason_class")
            or "SAME_PROFILE_PROCESS_ALREADY_RUNNING"
        )
        packets["persistent_r2b_first_launch_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_r2b_first_launch",
            "status": "blocked",
            "reason_class": reason_class,
            "native_launch_attempted": False,
        }
        packets["persistent_custom_profile_history_r2b_summary_packet.json"].update(
            {
                "status": "blocked",
                "final_status": (
                    "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_PROCESS_INVENTORY_UNUSABLE"
                    if reason_class == "PROCESS_INVENTORY_UNUSABLE"
                    else "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_CONCURRENT_PROFILE_PROCESS"
                ),
                "execution_mode": "first-launch",
            }
        )
        return packets

    runtime_paths = RuntimePaths.from_env()
    local_token = emit_local_token(runtime_paths)
    layout = _layout(paths, evidence_dir)
    keychain_preflight = build_persistent_keychain_preflight_packet(
        isolated_home=layout.custom_home_dir,
        phase="first_launch",
    )
    packets["persistent_r2b_keychain_preflight_first_launch_packet.json"] = (
        keychain_preflight
    )
    if keychain_preflight.get("status") == "blocked":
        packets["persistent_r2b_first_launch_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_r2b_first_launch",
            "status": "blocked",
            "reason_class": str(
                keychain_preflight.get("reason_class") or "KEYCHAIN_PREFLIGHT_BLOCKED"
            ),
            "native_launch_attempted": False,
        }
        packets["persistent_custom_profile_history_r2b_summary_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_history_r2b_summary",
            "status": "blocked",
            "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_KEYCHAIN_PREFLIGHT",
            "execution_mode": "first-launch",
            "profile_id": profile_id,
            "profile_root": str(profile_root),
            "native_launch_attempted": False,
            "custom_process_observed": False,
            "owner_action_required": False,
            "owner_nonce_hash_recorded": owner_nonce_packet.get("nonce_sha256", "") != "",
            "profile_state_preserved": False,
            "thread_history_preserved": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "keychain_prompt_resolved_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
            "keychain_preflight_status": keychain_preflight.get("status"),
        }
        return packets
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
    after_first_launch = collect_bounded_profile_manifest(
        profile_root,
        phase="after_first_launch",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    packets.update(
        {
            "persistent_r2b_first_launch_packet.json": {
                **launch,
                "packet_kind": "persistent_r2b_first_launch",
                "status": "ok" if launch.get("custom_process_observed") else "blocked",
                "profile_mode": "persistent_custom",
                "custom_user_data_dir": str(user_data_dir),
                "materialized_profile": materialized,
                "local_listener_token_materialized": True,
                "raw_token_recorded": False,
                "raw_prompt_recorded": False,
            },
            "persistent_custom_profile_after_first_launch_bounded_manifest.json": (
                after_first_launch
            ),
            "persistent_r2b_process_inventory_after_launch_packet.json": (
                collect_codex_process_inventory(custom_user_data_dir=str(user_data_dir))
            ),
            "r2b_owner_action_stop_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2b_owner_action_stop",
                "status": "blocked",
                "reason_class": "OWNER_ACTION_REQUIRED",
                "stop_required_before_relaunch_classification": True,
                "required_owner_marker": (
                    "owner_ready_now=true; prompt_entered=true; "
                    "nonce_used=true; evidence_dir_preserved=true"
                ),
                "raw_prompt_recorded": False,
                "raw_nonce_recorded": False,
                "thread_history_claimed": False,
            },
        }
    )
    observed = launch.get("custom_process_observed") is True
    packets["persistent_custom_profile_history_r2b_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_r2b_summary",
        "status": "blocked",
        "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_OWNER_ACTION_REQUIRED"
        if observed
        else "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_NATIVE_LAUNCH_FAILED",
        "execution_mode": "first-launch",
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "native_launch_attempted": True,
        "custom_process_observed": observed,
        "owner_action_required": observed,
        "owner_nonce_hash_recorded": owner_nonce_packet.get("nonce_sha256", "") != "",
        "profile_state_preserved": False,
        "thread_history_preserved": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "keychain_prompt_resolved_claimed": False,
        "keychain_preflight_status": keychain_preflight.get("status"),
        "native_ux_acceptance_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def _max_manifest_mtime_ns(manifest: dict[str, Any]) -> int:
    if "max_mtime_ns" in manifest:
        return int(manifest.get("max_mtime_ns") or 0)
    mtimes = [
        int(entry.get("mtime_ns", 0))
        for entry in manifest.get("entries_sample", [])
        if isinstance(entry, dict)
    ]
    return max(mtimes) if mtimes else 0


_R4_RELAUNCH_STAGE_PACKET_NAMES = (
    "persistent_custom_profile_before_bounded_manifest.json",
    "persistent_custom_profile_after_owner_action_bounded_manifest.json",
    "persistent_custom_profile_after_relaunch_bounded_manifest.json",
    "persistent_custom_profile_identity_before_packet.json",
    "persistent_r2b_identity_relaunch_packet.json",
    "persistent_r2b_keychain_preflight_relaunch_packet.json",
    "persistent_r2b_relaunch_packet.json",
    "persistent_r3_thread_target_selection_packet.json",
    "persistent_r3_before_target_manifest_packet.json",
    "persistent_r3_after_action_target_manifest_packet.json",
    "persistent_r3_relaunch_target_manifest_packet.json",
    "r2b_original_codex_before_snapshot.json",
)


def _r4_missing_relaunch_stage_packets(evidence_dir: Path) -> list[str]:
    return [
        name
        for name in _R4_RELAUNCH_STAGE_PACKET_NAMES
        if not (evidence_dir / name).exists()
    ]


def _r4_relaunch_stage_available(evidence_dir: Path) -> bool:
    return not _r4_missing_relaunch_stage_packets(evidence_dir)


def _build_r4_owner_visibility_stop_packet(*, observed: bool) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r4_owner_visibility_stop",
        "status": "blocked",
        "reason_class": "R4_OWNER_RELAUNCH_VISIBILITY_REQUIRED",
        "required_owner_marker": (
            "owner_confirmation_collected=true; same_nonce_thread_visible=true|false; "
            "owner_visible_prior_thread=true|false|unknown; owner_ready_now=true; "
            "prompt_entered=true; nonce_used=true; evidence_dir_preserved=true"
        ),
        "stop_required_before_thread_history_classification": observed,
    }


def _build_r4_relaunch_stage_required_summary(
    *,
    profile_id: str,
    profile_root: Path,
    observed: bool,
    keychain_preflight_status: str,
) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_r2b_summary",
        "status": "blocked",
        "final_status": (
            "WBP_CUSTOM_PERSISTENT_PROFILE_R4_STOP_RELAUNCH_VISIBILITY_REQUIRED"
            if observed
            else "WBP_CUSTOM_PERSISTENT_PROFILE_R4_BLOCKED_NATIVE_RELAUNCH_FAILED"
        ),
        "execution_mode": "relaunch-classify",
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "native_launch_attempted": True,
        "relaunch_attempted": True,
        "custom_process_observed": observed,
        "owner_action_required": observed,
        "profile_state_preserved": False,
        "thread_history_preserved": False,
        "thread_history_preserved_with_limits": False,
        "storage_level_thread_history_proven": False,
        "durable_restoration_proven": False,
        "keychain_preflight_status": keychain_preflight_status,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "keychain_prompt_resolved_claimed": False,
        "native_ux_acceptance_claimed": False,
        "final_e2e_claimed": False,
    }


def _build_r4_relaunch_stage_missing_summary(
    *,
    profile_id: str,
    profile_root: Path,
    missing_packets: list[str],
) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_r2b_summary",
        "status": "blocked",
        "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R4_BLOCKED_RELAUNCH_STAGE_MISSING",
        "execution_mode": "relaunch-classify",
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "native_launch_attempted": False,
        "relaunch_attempted": False,
        "owner_action_required": False,
        "missing_relaunch_stage_packets": missing_packets,
        "profile_state_preserved": False,
        "thread_history_preserved": False,
        "thread_history_preserved_with_limits": False,
        "storage_level_thread_history_proven": False,
        "durable_restoration_proven": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "keychain_prompt_resolved_claimed": False,
        "native_ux_acceptance_claimed": False,
        "final_e2e_claimed": False,
    }


def _build_r4_classification_from_saved_relaunch(
    *,
    evidence_dir: Path,
    repair_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_visible_prior_thread: bool | None,
    same_nonce_thread_visible: bool | None,
    owner_confirmation_collected: bool,
    owner_ready_now: bool,
    prompt_entered: bool,
    nonce_used: bool,
    evidence_dir_preserved: bool,
) -> dict[str, dict[str, Any]]:
    from tools.persistent_custom_profile_restoration_correlation_r5_probe import (
        build_owner_visibility_packet as build_r5_owner_visibility_packet,
        build_r5_correlation_classification_packet,
        build_r5_target_delta_packet,
        build_storage_correlation_result_packet,
        build_visibility_result_packet,
    )

    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    codex_home = Path(paths["codex_home"])
    missing_packets = _r4_missing_relaunch_stage_packets(evidence_dir)
    owner_boundary = build_owner_action_boundary_packet(
        owner_ready_now=owner_ready_now,
        prompt_entered=prompt_entered,
        nonce_used=nonce_used,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    if owner_boundary.get("status") != "ok":
        return {
            "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
                repair_evidence_dir=repair_evidence_dir
            ),
            "r2b_owner_action_boundary_packet.json": owner_boundary,
            "persistent_custom_profile_history_r2b_summary_packet.json": {
                **_build_r4_relaunch_stage_missing_summary(
                    profile_id=profile_id,
                    profile_root=profile_root,
                    missing_packets=missing_packets,
                ),
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_OWNER_ACTION_REQUIRED",
                "missing_relaunch_stage_packets": missing_packets,
            },
        }
    if missing_packets:
        return {
            "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
                repair_evidence_dir=repair_evidence_dir
            ),
            "r2b_owner_action_boundary_packet.json": owner_boundary,
            "persistent_custom_profile_history_r2b_summary_packet.json": (
                _build_r4_relaunch_stage_missing_summary(
                    profile_id=profile_id,
                    profile_root=profile_root,
                    missing_packets=missing_packets,
                )
            ),
        }
    before_manifest = _read_json(
        evidence_dir / "persistent_custom_profile_before_bounded_manifest.json"
    )
    after_action_manifest = _read_json(
        evidence_dir / "persistent_custom_profile_after_owner_action_bounded_manifest.json"
    )
    relaunch_manifest = _read_json(
        evidence_dir / "persistent_custom_profile_after_relaunch_bounded_manifest.json"
    )
    protected_before = _read_json(evidence_dir / "r2b_original_codex_before_snapshot.json")
    before_identity = _read_json(evidence_dir / "persistent_custom_profile_identity_before_packet.json")
    relaunch_identity = _read_json(evidence_dir / "persistent_r2b_identity_relaunch_packet.json")
    keychain_preflight = _read_json(evidence_dir / "persistent_r2b_keychain_preflight_relaunch_packet.json")
    relaunch = _read_json(evidence_dir / "persistent_r2b_relaunch_packet.json")
    r3_selection = _read_json(evidence_dir / "persistent_r3_thread_target_selection_packet.json")
    r3_before_targets = _read_json(
        evidence_dir / "persistent_r3_before_target_manifest_packet.json"
    )
    r3_after_action_targets = _read_json(
        evidence_dir / "persistent_r3_after_action_target_manifest_packet.json"
    )
    r3_relaunch_targets = _read_json(
        evidence_dir / "persistent_r3_relaunch_target_manifest_packet.json"
    )
    after_action_diff = build_bounded_state_diff_packet(
        before_manifest=before_manifest,
        after_manifest=after_action_manifest,
        phase="after_owner_action",
    )
    relaunch_diff = build_bounded_state_diff_packet(
        before_manifest=after_action_manifest,
        after_manifest=relaunch_manifest,
        phase="after_relaunch",
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
    owner_visibility = build_r5_owner_visibility_packet(
        owner_relaunch_checked=owner_confirmation_collected,
        same_nonce_thread_visible=same_nonce_thread_visible,
        target_window_clear=owner_ready_now,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    visibility_result = build_visibility_result_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        owner_visibility_packet=owner_visibility,
        relaunch_packet=relaunch,
    )
    target_delta = build_r5_target_delta_packet(
        before_manifest=r3_before_targets,
        after_action_manifest=r3_after_action_targets,
        relaunch_manifest=r3_relaunch_targets,
    )
    profile_state = build_r3_profile_state_with_thread_target_retention_packet(
        profile_state_packet=profile_state,
        target_delta_packet=target_delta,
    )
    thread_history = build_persistent_thread_history_preservation_r2_packet(
        profile_state_preservation_packet=profile_state,
        state_diff_packet=after_action_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    storage_correlation = build_storage_correlation_result_packet(
        visibility_result_packet=visibility_result,
        target_delta_packet=target_delta,
    )
    correlation_classification = build_r5_correlation_classification_packet(
        visibility_result_packet=visibility_result,
        storage_correlation_packet=storage_correlation,
        owner_action_packet=owner_boundary,
        owner_visibility_packet=owner_visibility,
    )
    r3_owner_continuity = build_r3_owner_visible_thread_continuity_packet(
        visibility_result_packet=visibility_result,
        owner_visibility_packet=owner_visibility,
    )
    r3_storage_correlation = build_r3_storage_level_history_correlation_packet(
        selection_packet=r3_selection,
        target_delta_packet=target_delta,
        storage_correlation_packet=storage_correlation,
        correlation_classification_packet=correlation_classification,
    )
    r3_thread_history = build_r3_thread_history_preservation_packet(
        profile_state_packet=profile_state,
        owner_visible_thread_continuity_packet=r3_owner_continuity,
        storage_level_history_correlation_packet=r3_storage_correlation,
        keychain_packet=keychain_preflight,
    )
    original_drift = build_original_codex_profile_drift_packet(
        before_surfaces=protected_before,
        after_surfaces=scan_protected_surfaces(),
    )
    cleanup = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=True,
        profile_exists_after_cleanup=profile_root.exists(),
    )
    false_green = build_persistent_profile_false_green_audit(
        thread_history_packet={
            "route_trace_counted_as_saved_thread_proof": False,
            "status": thread_history.get("status"),
        },
        owner_visible_thread_context_packet=owner_context,
        cleanup_policy_packet=cleanup,
        original_drift_packet=original_drift,
    )
    r3_false_green = build_r3_false_green_audit(
        owner_visible_thread_continuity_packet=r3_owner_continuity,
        storage_level_history_correlation_packet=r3_storage_correlation,
        thread_history_preservation_packet=r3_thread_history,
        legacy_r2_thread_history_packet=thread_history,
    )
    persistent_identity = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_identity_r3",
        "status": "ok"
        if before_identity.get("status") == "ok"
        and relaunch_identity.get("status") == "ok"
        and before_identity.get("persistent_profile_id")
        == relaunch_identity.get("persistent_profile_id")
        and before_identity.get("persistent_profile_root")
        == relaunch_identity.get("persistent_profile_root")
        else "blocked",
        "reason_class": "",
        "before_profile_id": before_identity.get("persistent_profile_id", ""),
        "relaunch_profile_id": relaunch_identity.get("persistent_profile_id", ""),
        "before_profile_root": before_identity.get("persistent_profile_root", ""),
        "relaunch_profile_root": relaunch_identity.get("persistent_profile_root", ""),
        "same_persistent_profile_identity": before_identity.get("persistent_profile_id")
        == relaunch_identity.get("persistent_profile_id")
        and before_identity.get("persistent_profile_root")
        == relaunch_identity.get("persistent_profile_root"),
    }
    keychain_persistent_lane = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_persistent_lane_r3",
        "status": keychain_preflight.get("status", ""),
        "reason_class": keychain_preflight.get("reason_class", ""),
        "keychain_preflight_status": keychain_preflight.get("status", ""),
        "isolated_default_keychain_verified": (
            keychain_preflight.get("isolated_default_keychain_verified") is True
        ),
        "isolated_search_list_verified": (
            keychain_preflight.get("isolated_search_list_verified") is True
        ),
        "prompt_absence_counts_as_auth_proof": False,
        "prompt_absence_counts_as_persistence_proof": False,
    }
    r3_summary = build_r3_summary_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        relaunch_packet=relaunch,
        profile_state_packet=profile_state,
        owner_continuity_packet=r3_owner_continuity,
        storage_correlation_packet=r3_storage_correlation,
        thread_history_packet=r3_thread_history,
        keychain_packet=keychain_preflight,
        false_green_packet=r3_false_green,
        legacy_false_green_packet=false_green,
    )
    return {
        "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
            repair_evidence_dir=repair_evidence_dir
        ),
        "r2b_owner_action_boundary_packet.json": owner_boundary,
        "persistent_custom_profile_after_owner_action_bounded_manifest.json": (
            after_action_manifest
        ),
        "persistent_r2b_keychain_preflight_relaunch_packet.json": keychain_preflight,
        "persistent_r2b_relaunch_packet.json": relaunch,
        "persistent_custom_profile_after_relaunch_bounded_manifest.json": relaunch_manifest,
        "persistent_r2b_identity_relaunch_packet.json": relaunch_identity,
        "persistent_r2b_after_action_state_diff_packet.json": after_action_diff,
        "persistent_r2b_relaunch_state_diff_packet.json": relaunch_diff,
        "persistent_r2b_profile_state_preservation_packet.json": profile_state,
        "persistent_r2b_owner_visible_thread_context_packet.json": owner_context,
        "persistent_r2b_thread_history_preservation_packet.json": thread_history,
        "persistent_r3_thread_target_selection_packet.json": r3_selection,
        "persistent_r3_before_target_manifest_packet.json": r3_before_targets,
        "persistent_r3_after_action_target_manifest_packet.json": r3_after_action_targets,
        "persistent_r3_relaunch_target_manifest_packet.json": r3_relaunch_targets,
        "persistent_r3_owner_visibility_packet.json": owner_visibility,
        "persistent_r3_visibility_result_packet.json": visibility_result,
        "persistent_r3_target_delta_packet.json": target_delta,
        "persistent_r3_storage_correlation_result_packet.json": storage_correlation,
        "persistent_r3_correlation_classification_packet.json": correlation_classification,
        "persistent_profile_identity_packet.json": persistent_identity,
        "persistent_profile_state_preservation_packet.json": profile_state,
        "owner_visible_thread_continuity_packet.json": r3_owner_continuity,
        "storage_level_history_correlation_packet.json": r3_storage_correlation,
        "thread_history_preservation_packet.json": r3_thread_history,
        "keychain_persistent_lane_packet.json": keychain_persistent_lane,
        "persistent_r2b_original_codex_drift_packet.json": original_drift,
        "persistent_r2b_cleanup_policy_packet.json": cleanup,
        "persistent_r2b_false_green_audit.json": false_green,
        "false_green_audit.json": r3_false_green,
        "persistent_custom_profile_history_r2b_summary_packet.json": r3_summary,
    }


def build_relaunch_classification_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    repair_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_visible_prior_thread: bool | None,
    same_nonce_thread_visible: bool | None = None,
    owner_confirmation_collected: bool,
    owner_ready_now: bool,
    prompt_entered: bool,
    nonce_used: bool,
    evidence_dir_preserved: bool,
    startup_wait_seconds: float,
    owner_nonce: str = "",
) -> dict[str, dict[str, Any]]:
    from tools.persistent_custom_profile_restoration_correlation_r5_probe import (
        collect_target_manifest,
    )

    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    owner_boundary = build_owner_action_boundary_packet(
        owner_ready_now=owner_ready_now,
        prompt_entered=prompt_entered,
        nonce_used=nonce_used,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    if owner_boundary.get("status") != "ok":
        return {
            "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
                repair_evidence_dir=repair_evidence_dir
            ),
            "r2b_owner_action_boundary_packet.json": owner_boundary,
            "persistent_custom_profile_history_r2b_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_custom_profile_history_r2b_summary",
                "status": "blocked",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_OWNER_ACTION_REQUIRED",
                "execution_mode": "relaunch-classify",
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "relaunch_attempted": False,
                "owner_action_required": True,
                "profile_state_preserved": False,
                "thread_history_preserved": False,
                "thread_history_preserved_with_limits": False,
                "storage_level_thread_history_proven": False,
                "durable_restoration_proven": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "keychain_prompt_resolved_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    classification_requested = same_nonce_thread_visible is not None
    if classification_requested:
        return _build_r4_classification_from_saved_relaunch(
            evidence_dir=evidence_dir,
            repair_evidence_dir=repair_evidence_dir,
            profile_id=profile_id,
            base_dir=base_dir,
            owner_visible_prior_thread=owner_visible_prior_thread,
            same_nonce_thread_visible=same_nonce_thread_visible,
            owner_confirmation_collected=owner_confirmation_collected,
            owner_ready_now=owner_ready_now,
            prompt_entered=prompt_entered,
            nonce_used=nonce_used,
            evidence_dir_preserved=evidence_dir_preserved,
        )
    if _r4_relaunch_stage_available(evidence_dir):
        relaunch = _read_json(evidence_dir / "persistent_r2b_relaunch_packet.json")
        keychain_preflight = _read_json(
            evidence_dir / "persistent_r2b_keychain_preflight_relaunch_packet.json"
        )
        return {
            "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
                repair_evidence_dir=repair_evidence_dir
            ),
            "r2b_owner_action_boundary_packet.json": owner_boundary,
            "r4_owner_visibility_stop_packet.json": _build_r4_owner_visibility_stop_packet(
                observed=relaunch.get("custom_process_observed") is True
            ),
            "persistent_custom_profile_history_r2b_summary_packet.json": (
                _build_r4_relaunch_stage_required_summary(
                    profile_id=profile_id,
                    profile_root=profile_root,
                    observed=relaunch.get("custom_process_observed") is True,
                    keychain_preflight_status=str(keychain_preflight.get("status", "")),
                )
            ),
        }

    before_manifest = _read_json(
        evidence_dir / "persistent_custom_profile_before_bounded_manifest.json"
    )
    after_action_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="after_owner_action",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    r3_selection = build_r3_thread_target_selection_packet(
        profile_root=profile_root,
        owner_nonce=owner_nonce,
    )
    r3_before_targets = build_r3_cutoff_baseline_target_manifest(
        selection_packet=r3_selection,
        profile_root=profile_root,
        cutoff_ns=_max_manifest_mtime_ns(before_manifest),
        phase="r3_before",
    )
    r3_after_action_targets = collect_target_manifest(
        profile_root,
        r3_selection,
        phase="r3_after_owner_action",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    termination = terminate_custom_processes(str(user_data_dir))
    same_profile_gate = build_same_profile_process_gate_packet(
        custom_user_data_dir=user_data_dir,
        phase="before_relaunch",
    )
    if same_profile_gate.get("status") != "ok":
        reason_class = str(
            same_profile_gate.get("reason_class")
            or "SAME_PROFILE_PROCESS_ALREADY_RUNNING"
        )
        return {
            "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
                repair_evidence_dir=repair_evidence_dir
            ),
            "r2b_owner_action_boundary_packet.json": owner_boundary,
            "persistent_custom_profile_after_owner_action_bounded_manifest.json": (
                after_action_manifest
            ),
            "persistent_r2b_first_launch_termination_packet.json": termination,
            "persistent_r2b_same_profile_process_gate_before_relaunch_packet.json": (
                same_profile_gate
            ),
            "persistent_custom_profile_history_r2b_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_custom_profile_history_r2b_summary",
                "status": "blocked",
                "final_status": (
                    "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_PROCESS_INVENTORY_UNUSABLE"
                    if reason_class == "PROCESS_INVENTORY_UNUSABLE"
                    else "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_CONCURRENT_PROFILE_PROCESS"
                ),
                "execution_mode": "relaunch-classify",
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "relaunch_attempted": False,
                "owner_action_required": False,
                "profile_state_preserved": False,
                "thread_history_preserved": False,
                "thread_history_preserved_with_limits": False,
                "storage_level_thread_history_proven": False,
                "durable_restoration_proven": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "keychain_prompt_resolved_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    runtime_paths = RuntimePaths.from_env()
    keychain_preflight = build_persistent_keychain_preflight_packet(
        isolated_home=Path(paths["home_dir"]),
        phase="relaunch",
    )
    if keychain_preflight.get("status") == "blocked":
        return {
            "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
                repair_evidence_dir=repair_evidence_dir
            ),
            "r2b_owner_action_boundary_packet.json": owner_boundary,
            "persistent_custom_profile_after_owner_action_bounded_manifest.json": (
                after_action_manifest
            ),
            "persistent_r2b_first_launch_termination_packet.json": termination,
            "persistent_r2b_same_profile_process_gate_before_relaunch_packet.json": (
                same_profile_gate
            ),
            "persistent_r2b_keychain_preflight_relaunch_packet.json": keychain_preflight,
            "persistent_custom_profile_history_r2b_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_custom_profile_history_r2b_summary",
                "status": "blocked",
                "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_KEYCHAIN_PREFLIGHT",
                "execution_mode": "relaunch-classify",
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "relaunch_attempted": False,
                "owner_action_required": False,
                "profile_state_preserved": False,
                "thread_history_preserved": False,
                "thread_history_preserved_with_limits": False,
                "storage_level_thread_history_proven": False,
                "durable_restoration_proven": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "keychain_prompt_resolved_claimed": False,
                "keychain_preflight_status": keychain_preflight.get("status"),
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    relaunch = launch_native_candidate(
        repo_root=repo_root,
        layout=_layout(paths, evidence_dir),
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    relaunch_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="after_relaunch",
        changed_since_ns=_max_manifest_mtime_ns(after_action_manifest),
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
    r3_relaunch_targets = collect_target_manifest(
        profile_root,
        r3_selection,
        phase="r3_after_relaunch",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    return {
        "r2b_rollback_reference_reverified_packet.json": build_rollback_reference_packet(
            repair_evidence_dir=repair_evidence_dir
        ),
        "r2b_owner_action_boundary_packet.json": owner_boundary,
        "persistent_custom_profile_after_owner_action_bounded_manifest.json": (
            after_action_manifest
        ),
        "persistent_r2b_first_launch_termination_packet.json": termination,
        "persistent_r2b_same_profile_process_gate_before_relaunch_packet.json": (
            same_profile_gate
        ),
        "persistent_r2b_keychain_preflight_relaunch_packet.json": keychain_preflight,
        "persistent_r2b_relaunch_packet.json": {
            **relaunch,
            "packet_kind": "persistent_r2b_relaunch",
            "status": "ok" if relaunch.get("custom_process_observed") else "blocked",
            "profile_mode": "persistent_custom",
            "custom_user_data_dir": str(user_data_dir),
        },
        "persistent_custom_profile_after_relaunch_bounded_manifest.json": relaunch_manifest,
        "persistent_r2b_identity_relaunch_packet.json": relaunch_identity,
        "persistent_r3_thread_target_selection_packet.json": r3_selection,
        "persistent_r3_before_target_manifest_packet.json": r3_before_targets,
        "persistent_r3_after_action_target_manifest_packet.json": r3_after_action_targets,
        "persistent_r3_relaunch_target_manifest_packet.json": r3_relaunch_targets,
        "r4_owner_visibility_stop_packet.json": _build_r4_owner_visibility_stop_packet(
            observed=relaunch.get("custom_process_observed") is True
        ),
        "persistent_custom_profile_history_r2b_summary_packet.json": (
            _build_r4_relaunch_stage_required_summary(
                profile_id=profile_id,
                profile_root=profile_root,
                observed=relaunch.get("custom_process_observed") is True,
                keychain_preflight_status=str(keychain_preflight.get("status", "")),
            )
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-history-r2b-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--repair-evidence-dir", default=str(DEFAULT_REPAIR_EVIDENCE_DIR))
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", default="")
    parser.add_argument(
        "--execution-mode",
        choices=["admission", "first-launch", "relaunch-classify"],
        default="admission",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:8318/v1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--owner-nonce", default="")
    parser.add_argument("--startup-wait-seconds", type=float, default=12.0)
    parser.add_argument("--owner-visible-prior-thread", default="unknown")
    parser.add_argument("--same-nonce-thread-visible", default="unknown")
    parser.add_argument("--owner-confirmation-collected", action="store_true")
    parser.add_argument("--owner-ready-now", action="store_true")
    parser.add_argument("--prompt-entered", action="store_true")
    parser.add_argument("--nonce-used", action="store_true")
    parser.add_argument("--evidence-dir-preserved", action="store_true")
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    repair_evidence_dir = Path(args.repair_evidence_dir).resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if args.execution_mode == "first-launch":
        packets = build_first_launch_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            repair_evidence_dir=repair_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            endpoint=args.endpoint,
            model=args.model,
            owner_nonce=args.owner_nonce,
            startup_wait_seconds=args.startup_wait_seconds,
            skip_git=args.skip_git,
        )
    elif args.execution_mode == "relaunch-classify":
        packets = build_relaunch_classification_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            repair_evidence_dir=repair_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            owner_nonce=args.owner_nonce,
            owner_visible_prior_thread=_parse_nullable_bool(args.owner_visible_prior_thread),
            same_nonce_thread_visible=_parse_nullable_bool(args.same_nonce_thread_visible),
            owner_confirmation_collected=args.owner_confirmation_collected,
            owner_ready_now=args.owner_ready_now,
            prompt_entered=args.prompt_entered,
            nonce_used=args.nonce_used,
            evidence_dir_preserved=args.evidence_dir_preserved,
            startup_wait_seconds=args.startup_wait_seconds,
        )
    else:
        packets = _admission_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            repair_evidence_dir=repair_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            skip_git=args.skip_git,
        )
    packets = {
        name: _redact_owner_nonce_in_packet(packet, owner_nonce=args.owner_nonce)
        for name, packet in packets.items()
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
