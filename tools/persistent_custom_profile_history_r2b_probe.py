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
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
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


def build_relaunch_classification_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    repair_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_visible_prior_thread: bool | None,
    owner_confirmation_collected: bool,
    owner_ready_now: bool,
    prompt_entered: bool,
    nonce_used: bool,
    evidence_dir_preserved: bool,
    startup_wait_seconds: float,
) -> dict[str, dict[str, Any]]:
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    codex_home = Path(paths["codex_home"])
    before_manifest = _read_json(
        evidence_dir / "persistent_custom_profile_before_bounded_manifest.json"
    )
    protected_before = _read_json(evidence_dir / "r2b_original_codex_before_snapshot.json")
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
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "keychain_prompt_resolved_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    after_action_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="after_owner_action",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    termination = terminate_custom_processes(str(user_data_dir))
    runtime_paths = RuntimePaths.from_env()
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
    final_ok = (
        owner_boundary.get("status") == "ok"
        and relaunch.get("custom_process_observed") is True
        and profile_state.get("profile_state_preserved") is True
        and thread_history.get("thread_history_preserved") is True
        and false_green.get("status") == "ok"
    )
    profile_state_only = (
        owner_boundary.get("status") == "ok"
        and relaunch.get("custom_process_observed") is True
        and profile_state.get("profile_state_preserved") is True
        and false_green.get("status") == "ok"
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
        "persistent_r2b_relaunch_packet.json": {
            **relaunch,
            "packet_kind": "persistent_r2b_relaunch",
            "status": "ok" if relaunch.get("custom_process_observed") else "blocked",
            "profile_mode": "persistent_custom",
            "custom_user_data_dir": str(user_data_dir),
        },
        "persistent_custom_profile_after_relaunch_bounded_manifest.json": relaunch_manifest,
        "persistent_r2b_identity_relaunch_packet.json": relaunch_identity,
        "persistent_r2b_after_action_state_diff_packet.json": after_action_diff,
        "persistent_r2b_relaunch_state_diff_packet.json": relaunch_diff,
        "persistent_r2b_profile_state_preservation_packet.json": profile_state,
        "persistent_r2b_owner_visible_thread_context_packet.json": owner_context,
        "persistent_r2b_thread_history_preservation_packet.json": thread_history,
        "persistent_r2b_original_codex_drift_packet.json": original_drift,
        "persistent_r2b_cleanup_policy_packet.json": cleanup,
        "persistent_r2b_false_green_audit.json": false_green,
        "persistent_custom_profile_history_r2b_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_history_r2b_summary",
            "status": "ok" if final_ok else "blocked",
            "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
            if final_ok
            else (
                "WBP_CUSTOM_PERSISTENT_PROFILE_STATE_PRESERVED_THREAD_HISTORY_UNCONFIRMED"
                if profile_state_only
                else "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN"
            ),
            "execution_mode": "relaunch-classify",
            "profile_id": profile_id,
            "profile_root": str(profile_root),
            "native_launch_attempted": True,
            "relaunch_attempted": True,
            "profile_state_preserved": profile_state.get("profile_state_preserved") is True,
            "thread_history_preserved": thread_history.get("thread_history_preserved") is True,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "keychain_prompt_resolved_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
        },
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
            owner_visible_prior_thread=_parse_nullable_bool(args.owner_visible_prior_thread),
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
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
