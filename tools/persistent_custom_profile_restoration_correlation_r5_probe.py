#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""R5 live-bounded restoration correlation for Persistent Custom Codex.

R5 correlates selected local storage hypothesis deltas with owner-visible
thread continuity across relaunch. It must not claim durable local restoration
proof, route proof, egress proof, model availability, UX acceptance, or E2E.
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

from tools.persistent_custom_profile_history_r2b_probe import (  # noqa: E402
    _max_manifest_mtime_ns,
    collect_bounded_profile_manifest,
)
from tools.persistent_custom_profile_r2c_owner_visible_thread_continuity_probe import (  # noqa: E402
    _layout,
)
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
    json_write,
    launch_native_candidate,
    materialize_probe_profile,
    terminate_custom_processes,
)
from wild_boar_proxy.runtime import RuntimePaths  # noqa: E402
from wild_boar_proxy.token_command import emit_local_token  # noqa: E402


DEFAULT_R4_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_storage_schema_attribution_r4_2026-05-27"
)
DEFAULT_EVIDENCE_DIR = (
    ROOT
    / "audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27"
)

SENSITIVE_PATH_TOKENS = (
    "auth.json",
    "token",
    "secret",
    "credential",
    "keychain",
)
FORBIDDEN_CLAIM_FIELDS = (
    "durable_restoration_proven",
    "local_only_restoration_source_proven",
    "storage_level_thread_history_proven",
    "route_proof_claimed",
    "direct_egress_absence_claimed",
    "model_availability_claimed",
    "native_ux_acceptance_claimed",
    "original_codex_reversibility_claimed",
    "final_e2e_claimed",
)


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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_r5_nonce_prompt_packet(*, nonce: str) -> dict[str, Any]:
    prompt = (
        "WBP Persistent Custom R5 restoration correlation check. "
        f"Please reply with OK and this nonce only: {nonce}"
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_nonce_prompt",
        "status": "ok" if nonce else "blocked",
        "nonce_sha256": _sha256_text(nonce) if nonce else "",
        "prompt_sha256": _sha256_text(prompt) if nonce else "",
        "nonce_recorded": False,
        "raw_nonce_recorded": False,
        "prompt_hash_recorded": bool(nonce),
        "raw_prompt_recorded": False,
        "prompt_template_shape": (
            "WBP Persistent Custom R5 restoration correlation check. "
            "Please reply with OK and this nonce only: <nonce>"
        ),
    }


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
        "tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
        "tests/test_native_filesystem_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
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


def build_r5_sync_gate_packet(
    *,
    repo_root: Path,
    evidence_dir: Path,
    skip_git: bool = False,
) -> dict[str, Any]:
    quarantined, unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_sync_gate",
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
        "quarantined_entry_count": len(quarantined),
        "native_launch_attempted": False,
        "live_mutation_attempted": False,
        "master_plan_written_to_repo": False,
    }


def build_r5_r4_reference_packet(*, r4_evidence_dir: Path) -> dict[str, Any]:
    r4_evidence_dir = r4_evidence_dir.expanduser().resolve(strict=False)
    summary_path = r4_evidence_dir / "persistent_storage_r4_summary_packet.json"
    hypothesis_path = r4_evidence_dir / "persistent_storage_restoration_hypothesis_packet.json"
    candidate_path = r4_evidence_dir / "persistent_storage_candidate_selection_packet.json"
    missing = [
        str(path)
        for path in (summary_path, hypothesis_path, candidate_path)
        if not path.exists()
    ]
    if missing:
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_r4_reference",
            "status": "blocked",
            "reason_class": "R4_REFERENCE_MISSING",
            "missing_packets": missing,
            "r4_counts_as_r5_proof": False,
        }
    summary = _read_json(summary_path)
    hypothesis = _read_json(hypothesis_path)
    candidate = _read_json(candidate_path)
    expected = (
        summary.get("final_status")
        == "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_HYPOTHESES_CLASSIFIED_WITH_LIMITS"
        and hypothesis.get("durable_restoration_proven") is False
        and hypothesis.get("storage_level_thread_history_proven") is False
        and candidate.get("metadata_only") is True
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_r4_reference",
        "status": "ok" if expected else "blocked",
        "reason_class": "" if expected else "R4_REFERENCE_OVERCLAIM_OR_UNUSABLE",
        "r4_evidence_dir": str(r4_evidence_dir),
        "summary_sha256": _sha256_file(summary_path),
        "hypothesis_sha256": _sha256_file(hypothesis_path),
        "candidate_sha256": _sha256_file(candidate_path),
        "r4_final_status": summary.get("final_status", ""),
        "r4_hypothesis_count": hypothesis.get("hypothesis_count", 0),
        "r4_schema_observed_count": summary.get("schema_observed_count", 0),
        "r4_counts_as_r5_proof": False,
        "durable_restoration_proven_by_r4": False,
        "storage_level_thread_history_proven_by_r4": False,
    }


def _is_sensitive_path(relative_path: str) -> bool:
    lower = relative_path.replace("\\", "/").lower()
    return any(token in lower for token in SENSITIVE_PATH_TOKENS)


def _r5_hypothesis_score(item: dict[str, Any]) -> int:
    relative_path = str(item.get("relative_path", ""))
    lower = relative_path.lower()
    if _is_sensitive_path(relative_path):
        return -1000
    if lower.startswith((".tmp/", "plugins/cache/", "vendor_imports/")):
        return -50
    if lower == "session_index.jsonl":
        return 100
    if lower.startswith("sessions/") and lower.endswith(".jsonl"):
        return 90
    if lower in {"sessions", "sessions/"}:
        return 80
    if item.get("surface_type") == "sqlite" and any(
        token in lower for token in ("session", "thread", "history", "conversation")
    ):
        return 70
    if item.get("surface_type") == "jsonl" and "session" in lower:
        return 65
    if item.get("surface_type") == "json" and any(
        token in lower for token in ("session", "thread", "history")
    ):
        return 50
    return 0


def select_r5_hypotheses(
    *,
    r4_evidence_dir: Path,
    profile_root: Path,
    max_selected: int = 3,
) -> dict[str, Any]:
    candidate_path = r4_evidence_dir / "persistent_storage_candidate_selection_packet.json"
    hypothesis_path = r4_evidence_dir / "persistent_storage_restoration_hypothesis_packet.json"
    if not candidate_path.exists() or not hypothesis_path.exists():
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_hypothesis_selection",
            "status": "blocked",
            "reason_class": "R4_SELECTION_INPUT_MISSING",
            "selected_hypothesis_count": 0,
            "selected_hypotheses": [],
        }
    candidate = _read_json(candidate_path)
    hypothesis = _read_json(hypothesis_path)
    hypothesis_paths = {
        str(item.get("relative_path", ""))
        for item in hypothesis.get("hypotheses", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for item in candidate.get("candidates", []):
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("relative_path", ""))
        score = _r5_hypothesis_score(item)
        if score <= 0:
            continue
        rows.append(
            {
                "relative_path": relative_path,
                "surface_type": item.get("surface_type", ""),
                "state_class": item.get("state_class", ""),
                "r4_hypothesis_path_present": relative_path in hypothesis_paths,
                "selection_score": score,
                "selection_reason": "high_signal_session_surface",
                "exists_now": (profile_root / relative_path).exists(),
                "raw_content_recorded": False,
                "durable_restoration_proven": False,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["selection_score"]),
            0 if row["relative_path"] == "session_index.jsonl" else 1,
            str(row["relative_path"]),
        )
    )
    selected: list[dict[str, Any]] = []
    seen_kinds: set[str] = set()
    for row in rows:
        kind = "session_index" if row["relative_path"] == "session_index.jsonl" else "session_jsonl"
        if kind in seen_kinds and kind == "session_index":
            continue
        selected.append(row)
        seen_kinds.add(kind)
        if len(selected) >= max_selected:
            break
    auth_selected = any(_is_sensitive_path(row["relative_path"]) for row in selected)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_hypothesis_selection",
        "status": "ok" if selected and not auth_selected else "blocked",
        "reason_class": "" if selected and not auth_selected else "NO_SAFE_R5_HYPOTHESES",
        "r4_candidate_count": candidate.get("candidate_count", 0),
        "r4_hypothesis_count": hypothesis.get("hypothesis_count", 0),
        "selection_policy": "1_to_3_high_signal_session_surfaces_only",
        "all_r4_hypotheses_treated_equal": False,
        "selected_hypothesis_count": len(selected),
        "selected_hypotheses": selected,
        "auth_token_secret_surfaces_selected": auth_selected,
        "raw_content_recorded": False,
    }


def collect_target_manifest(
    profile_root: Path,
    selected_packet: dict[str, Any],
    *,
    phase: str,
    changed_since_ns: int | None = None,
) -> dict[str, Any]:
    targets = []
    for item in selected_packet.get("selected_hypotheses", []):
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("relative_path", ""))
        path = profile_root / relative_path
        exists = path.exists()
        entry: dict[str, Any] = {
            "relative_path": relative_path,
            "exists": exists,
            "raw_content_recorded": False,
            "content_hash_recorded": False,
            "durable_restoration_proven": False,
        }
        if exists:
            try:
                stat = path.lstat()
                changed_since_cutoff = (
                    changed_since_ns is not None and stat.st_mtime_ns >= changed_since_ns
                )
                entry.update(
                    {
                        "kind": "dir"
                        if path.is_dir()
                        else "file"
                        if path.is_file()
                        else "symlink"
                        if path.is_symlink()
                        else "other",
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "changed_since_ns": changed_since_ns,
                        "changed_since_cutoff": changed_since_cutoff,
                    }
                )
            except OSError as exc:
                entry.update(
                    {
                        "kind": "error",
                        "error_class": type(exc).__name__,
                        "error_message_recorded": False,
                    }
                )
        targets.append(entry)
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
        "raw_content_recorded": False,
        "content_hash_recorded": False,
    }


def build_r5_target_delta_packet(
    *,
    before_manifest: dict[str, Any],
    after_action_manifest: dict[str, Any],
    relaunch_manifest: dict[str, Any],
) -> dict[str, Any]:
    def by_path(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(item.get("relative_path", "")): item
            for item in packet.get("targets", [])
            if isinstance(item, dict)
        }

    before = by_path(before_manifest)
    after = by_path(after_action_manifest)
    relaunch = by_path(relaunch_manifest)
    rows = []
    for relative_path in sorted(set(before) | set(after) | set(relaunch)):
        b = before.get(relative_path, {})
        a = after.get(relative_path, {})
        r = relaunch.get(relative_path, {})
        changed_after_action = (
            b.get("exists") != a.get("exists")
            or b.get("size") != a.get("size")
            or b.get("mtime_ns") != a.get("mtime_ns")
        )
        retained_after_relaunch = (
            a.get("exists") == r.get("exists")
            and a.get("size") == r.get("size")
            and a.get("mtime_ns") == r.get("mtime_ns")
        )
        rows.append(
            {
                "relative_path": relative_path,
                "changed_after_owner_action": changed_after_action,
                "retained_after_relaunch": retained_after_relaunch,
                "target_delta_counts_as_participation_proof": False,
                "target_delta_counts_as_durable_restoration_proof": False,
                "raw_content_recorded": False,
            }
        )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_target_delta",
        "status": "ok" if rows else "blocked",
        "reason_class": "" if rows else "NO_TARGET_DELTAS",
        "target_delta_rows": rows,
        "changed_target_count": sum(1 for row in rows if row["changed_after_owner_action"]),
        "retained_target_count": sum(1 for row in rows if row["retained_after_relaunch"]),
        "target_file_changed_counts_as_participation_proof": False,
        "target_file_retained_counts_as_participation_proof": False,
        "raw_content_recorded": False,
    }


def build_prelaunch_window_inventory_packet(*, custom_user_data_dir: str) -> dict[str, Any]:
    inventory = collect_codex_process_inventory(custom_user_data_dir=custom_user_data_dir)
    target_custom_count = int(inventory.get("custom_process_count", 0) or 0)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "prelaunch_window_inventory",
        "status": "ok" if target_custom_count == 0 else "blocked",
        "reason_class": "" if target_custom_count == 0 else "TARGET_CUSTOM_WINDOW_ALREADY_ACTIVE",
        "process_inventory": inventory,
        "target_custom_process_count": target_custom_count,
        "single_window_admission_required": True,
        "target_window_clear": target_custom_count == 0,
        "process_inventory_counts_as_usable_window_proof": False,
    }


def build_r5_admission_packet(
    *,
    sync_packet: dict[str, Any],
    r4_reference_packet: dict[str, Any],
    selection_packet: dict[str, Any],
    prelaunch_window_packet: dict[str, Any],
    contract_packet: dict[str, Any],
    identity_packet: dict[str, Any],
    launcher_packet: dict[str, Any],
) -> dict[str, Any]:
    ok = all(
        packet.get("status") == "ok"
        for packet in (
            sync_packet,
            r4_reference_packet,
            selection_packet,
            prelaunch_window_packet,
            contract_packet,
            identity_packet,
            launcher_packet,
        )
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_admission",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "R5_ADMISSION_BLOCKED",
        "native_launch_attempted": False,
        "live_mutation_attempted": False,
        "owner_action_required_before_native_launch": ok,
        "stop_required_before_native_launch": ok,
        "single_window_admission_passed": prelaunch_window_packet.get("status") == "ok",
        "hypothesis_selection_passed": selection_packet.get("status") == "ok",
        "declared_write_surfaces": [
            str(identity_packet.get("persistent_profile_root", "")),
            str(identity_packet.get("codex_home", "")),
            str(identity_packet.get("user_data_dir", "")),
        ],
        "cleanup_rollback_expectation": "terminate_only_custom_process; do_not_delete_persistent_profile",
        "storage_proof_may_remain_unproven": True,
    }


def build_owner_first_action_boundary_packet(
    *,
    owner_prompt_entered: bool,
    nonce_used: bool,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
) -> dict[str, Any]:
    ok = owner_prompt_entered and nonce_used and target_window_clear and evidence_dir_preserved
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_owner_action_boundary",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "R5_FIRST_OWNER_MARKER_INCOMPLETE",
        "owner_prompt_entered": owner_prompt_entered,
        "nonce_used": nonce_used,
        "target_window_clear": target_window_clear,
        "evidence_dir_preserved": evidence_dir_preserved,
        "owner_action_counts_as_storage_proof": False,
        "owner_action_counts_as_route_proof": False,
        "raw_prompt_recorded": False,
        "raw_nonce_recorded": False,
    }


def build_owner_visibility_packet(
    *,
    owner_relaunch_checked: bool,
    same_nonce_thread_visible: bool | None,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
) -> dict[str, Any]:
    ok = (
        owner_relaunch_checked
        and same_nonce_thread_visible is not None
        and target_window_clear
        and evidence_dir_preserved
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_owner_visibility",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "R5_RELAUNCH_VISIBILITY_MARKER_INCOMPLETE",
        "owner_relaunch_checked": owner_relaunch_checked,
        "same_nonce_thread_visible": same_nonce_thread_visible,
        "target_window_clear": target_window_clear,
        "evidence_dir_preserved": evidence_dir_preserved,
        "owner_visibility_counts_as_storage_proof": False,
        "owner_visibility_counts_as_route_proof": False,
        "raw_thread_content_recorded": False,
    }


def build_visibility_result_packet(
    *,
    before_identity_packet: dict[str, Any],
    relaunch_identity_packet: dict[str, Any],
    owner_visibility_packet: dict[str, Any],
    relaunch_packet: dict[str, Any],
) -> dict[str, Any]:
    same_profile = (
        before_identity_packet.get("status") == "ok"
        and relaunch_identity_packet.get("status") == "ok"
        and before_identity_packet.get("persistent_profile_id")
        == relaunch_identity_packet.get("persistent_profile_id")
        and before_identity_packet.get("persistent_profile_root")
        == relaunch_identity_packet.get("persistent_profile_root")
    )
    visible = owner_visibility_packet.get("same_nonce_thread_visible") is True
    ok = same_profile and visible and relaunch_packet.get("custom_process_observed") is True
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_visibility_result",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "R5_VISIBILITY_NOT_CLASSIFIED",
        "same_persistent_profile_identity": same_profile,
        "same_nonce_thread_visible": visible,
        "owner_visible_thread_continuity_classified": ok,
        "visibility_result_counts_as_storage_correlation": False,
        "visibility_result_counts_as_durable_restoration_proof": False,
        "raw_thread_content_recorded": False,
    }


def build_storage_correlation_result_packet(
    *,
    visibility_result_packet: dict[str, Any],
    target_delta_packet: dict[str, Any],
) -> dict[str, Any]:
    visible = visibility_result_packet.get("owner_visible_thread_continuity_classified") is True
    changed = int(target_delta_packet.get("changed_target_count", 0) or 0)
    retained = int(target_delta_packet.get("retained_target_count", 0) or 0)
    correlated = visible and (changed > 0 or retained > 0)
    ambiguous = visible and changed == 0 and retained == 0
    if correlated:
        status = "ok"
        correlation = "correlated_with_limits"
    elif ambiguous:
        status = "blocked"
        correlation = "ambiguous_visible_without_selected_target_delta"
    else:
        status = "blocked"
        correlation = "not_correlated_or_visibility_absent"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_storage_correlation_result",
        "status": status,
        "correlation_classification": correlation,
        "visibility_result_status": visibility_result_packet.get("status"),
        "target_delta_status": target_delta_packet.get("status"),
        "selected_targets_changed_after_action": changed,
        "selected_targets_retained_after_relaunch": retained,
        "storage_correlation_classified": correlated,
        "durable_restoration_proven": False,
        "local_only_restoration_source_proven": False,
        "storage_level_thread_history_proven": False,
        "remote_sync_cache_or_mixed_remains_possible": True,
        "target_delta_counts_as_participation_proof": False,
    }


def build_r5_correlation_classification_packet(
    *,
    visibility_result_packet: dict[str, Any],
    storage_correlation_packet: dict[str, Any],
    owner_action_packet: dict[str, Any],
    owner_visibility_packet: dict[str, Any],
) -> dict[str, Any]:
    target_clear = (
        owner_action_packet.get("target_window_clear") is True
        and owner_visibility_packet.get("target_window_clear") is True
    )
    visible = visibility_result_packet.get("owner_visible_thread_continuity_classified") is True
    correlated = storage_correlation_packet.get("storage_correlation_classified") is True
    if visible and correlated and target_clear:
        status = "ok"
        final_status = (
            "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_LOCAL_RESTORATION_CORRELATION_CLASSIFIED"
        )
    elif visible and target_clear:
        status = "ok"
        final_status = (
            "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_VISIBLE_WITH_STORAGE_CORRELATION_LIMITED"
        )
    elif not target_clear:
        status = "blocked"
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_AMBIGUOUS"
    else:
        status = "blocked"
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_BLOCKED"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_correlation_classification",
        "status": status,
        "final_status": final_status,
        "visibility_result_separate_from_storage_correlation": True,
        "owner_visible_thread_continuity_classified": visible,
        "storage_correlation_classified": correlated,
        "target_window_clear": target_clear,
        "durable_restoration_proven": False,
        "local_only_restoration_source_proven": False,
        "storage_level_thread_history_proven": False,
        "route_proof_claimed": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "native_ux_acceptance_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def build_r5_false_green_audit(
    *,
    classification_packet: dict[str, Any],
    visibility_result_packet: dict[str, Any],
    storage_correlation_packet: dict[str, Any],
    target_delta_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = any(
        classification_packet.get(field) is True for field in FORBIDDEN_CLAIM_FIELDS
    ) or any(
        packet.get("durable_restoration_proven") is True
        or packet.get("local_only_restoration_source_proven") is True
        or packet.get("storage_level_thread_history_proven") is True
        for packet in (visibility_result_packet, storage_correlation_packet, target_delta_packet)
    )
    checks = [
        {
            "name": "visibility_result_not_storage_proof",
            "passed": visibility_result_packet.get(
                "visibility_result_counts_as_durable_restoration_proof"
            )
            is False,
        },
        {
            "name": "target_delta_not_participation_or_restoration_proof",
            "passed": target_delta_packet.get("target_file_changed_counts_as_participation_proof")
            is False
            and target_delta_packet.get("target_file_retained_counts_as_participation_proof")
            is False,
        },
        {
            "name": "correlation_not_local_only_source",
            "passed": storage_correlation_packet.get("local_only_restoration_source_proven")
            is False
            and storage_correlation_packet.get("remote_sync_cache_or_mixed_remains_possible")
            is True,
        },
        {
            "name": "no_route_egress_model_ux_original_e2e_claims",
            "passed": not any(
                classification_packet.get(field) is True
                for field in (
                    "route_proof_claimed",
                    "direct_egress_absence_claimed",
                    "model_availability_claimed",
                    "native_ux_acceptance_claimed",
                    "original_codex_reversibility_claimed",
                    "final_e2e_claimed",
                )
            ),
        },
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_restore_r5_false_green_audit",
        "status": "ok"
        if not forbidden_claims_present and all(check["passed"] for check in checks)
        else "blocked",
        "forbidden_claims_present": forbidden_claims_present,
        "checks": checks,
        "text_only_audit_counted_as_pass": False,
    }


def _paths(profile_id: str, base_dir: Path | None) -> dict[str, Any]:
    return default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)


def _admission_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    r4_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_nonce: str,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    sync = build_r5_sync_gate_packet(repo_root=repo_root, evidence_dir=evidence_dir, skip_git=skip_git)
    r4_reference = build_r5_r4_reference_packet(r4_evidence_dir=r4_evidence_dir)
    selection = select_r5_hypotheses(r4_evidence_dir=r4_evidence_dir, profile_root=profile_root)
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    identity = build_persistent_custom_profile_identity_packet(
        phase="r5_admission",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    launcher = build_persistent_launcher_selection_packet(
        launcher_path=Path(paths["launcher_path"]),
        profile_mode="persistent_custom",
        selected_profile_id=profile_id,
        selected_profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    prelaunch = build_prelaunch_window_inventory_packet(custom_user_data_dir=str(user_data_dir))
    before_manifest = collect_bounded_profile_manifest(profile_root, phase="r5_before")
    before_targets = collect_target_manifest(profile_root, selection, phase="r5_before")
    nonce = build_r5_nonce_prompt_packet(nonce=owner_nonce)
    admission = build_r5_admission_packet(
        sync_packet=sync,
        r4_reference_packet=r4_reference,
        selection_packet=selection,
        prelaunch_window_packet=prelaunch,
        contract_packet=contract,
        identity_packet=identity,
        launcher_packet=launcher,
    )
    stop_ok = admission.get("status") == "ok" and nonce.get("status") == "ok"
    return {
        "persistent_restore_r5_sync_gate_packet.json": sync,
        "persistent_restore_r5_r4_reference_packet.json": r4_reference,
        "persistent_restore_r5_hypothesis_selection_packet.json": selection,
        "persistent_custom_profile_contract_packet.json": contract,
        "persistent_restore_r5_profile_identity_before_packet.json": identity,
        "persistent_launcher_selection_packet.json": launcher,
        "prelaunch_window_inventory_packet.json": prelaunch,
        "persistent_restore_r5_before_manifest_packet.json": before_manifest,
        "persistent_restore_r5_before_target_manifest_packet.json": before_targets,
        "persistent_restore_r5_nonce_prompt_packet.json": nonce,
        "persistent_restore_r5_admission_packet.json": admission,
        "persistent_restore_r5_owner_live_stop_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_owner_live_stop",
            "status": "blocked",
            "reason_class": "R5_OWNER_LIVE_READY_REQUIRED"
            if stop_ok
            else "R5_ADMISSION_OR_NONCE_BLOCKED",
            "stop_required_before_native_launch": True,
            "native_launch_attempted": False,
            "required_owner_marker": "owner_live_ready_now=true",
            "next_action_after_marker": "run execution-mode=first-launch",
            "target_window_rule": "type only into the newly launched target Persistent Custom window",
            "storage_proof_may_remain_unproven": True,
        },
        "persistent_restore_r5_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_summary",
            "status": "blocked",
            "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_R5_STOP_OWNER_LIVE_READY_REQUIRED"
            if stop_ok
            else "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_BLOCKED",
            "execution_mode": "admission",
            "native_launch_attempted": False,
            "owner_action_required": stop_ok,
            "storage_correlation_classified": False,
            "durable_restoration_proven": False,
            "local_only_restoration_source_proven": False,
            "storage_level_thread_history_proven": False,
            "route_proof_claimed": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
        },
    }


def _first_launch_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    r4_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    endpoint: str,
    model: str,
    owner_nonce: str,
    startup_wait_seconds: float,
    skip_git: bool,
) -> dict[str, dict[str, Any]]:
    packets = _admission_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        r4_evidence_dir=r4_evidence_dir,
        profile_id=profile_id,
        base_dir=base_dir,
        owner_nonce=owner_nonce,
        skip_git=skip_git,
    )
    if packets["persistent_restore_r5_admission_packet.json"].get("status") != "ok":
        packets["persistent_restore_r5_summary_packet.json"].update(
            {
                "execution_mode": "first-launch",
                "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_BLOCKED",
            }
        )
        return packets
    paths = _paths(profile_id, base_dir)
    runtime_paths = RuntimePaths.from_env()
    layout = _layout(paths, evidence_dir)
    materialized = materialize_probe_profile(
        layout=layout,
        endpoint=endpoint,
        model=model,
        auth_command_path=repo_root / "wbp_codex_auth_command.py",
        local_token=emit_local_token(runtime_paths),
    )
    launch = launch_native_candidate(
        repo_root=repo_root,
        layout=layout,
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    observed = launch.get("custom_process_observed") is True
    packets.update(
        {
            "persistent_restore_r5_first_launch_packet.json": {
                **launch,
                "packet_kind": "persistent_restore_r5_first_launch",
                "status": "ok" if observed else "blocked",
                "profile_mode": "persistent_custom",
                "materialized_profile": materialized,
                "raw_token_recorded": False,
                "raw_prompt_recorded": False,
            },
            "persistent_restore_r5_process_inventory_after_first_launch_packet.json": (
                collect_codex_process_inventory(custom_user_data_dir=paths["user_data_dir"])
            ),
            "persistent_restore_r5_owner_prompt_stop_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_restore_r5_owner_prompt_stop",
                "status": "blocked",
                "reason_class": "R5_OWNER_PROMPT_REQUIRED",
                "required_owner_marker": (
                    "owner_prompt_entered=true; nonce_used=true; "
                    "target_window_clear=true; evidence_dir_preserved=true"
                ),
                "stop_required_before_relaunch": True,
                "raw_prompt_recorded": False,
                "raw_nonce_recorded": False,
            },
            "persistent_restore_r5_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_restore_r5_summary",
                "status": "blocked",
                "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_R5_STOP_OWNER_PROMPT_REQUIRED"
                if observed
                else "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_BLOCKED",
                "execution_mode": "first-launch",
                "native_launch_attempted": True,
                "custom_process_observed": observed,
                "owner_action_required": observed,
                "storage_correlation_classified": False,
                "durable_restoration_proven": False,
                "local_only_restoration_source_proven": False,
                "storage_level_thread_history_proven": False,
                "route_proof_claimed": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    )
    return packets


def _relaunch_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_prompt_entered: bool,
    nonce_used: bool,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
    startup_wait_seconds: float,
) -> dict[str, dict[str, Any]]:
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    user_data_dir = Path(paths["user_data_dir"])
    owner_action = build_owner_first_action_boundary_packet(
        owner_prompt_entered=owner_prompt_entered,
        nonce_used=nonce_used,
        target_window_clear=target_window_clear,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    if owner_action.get("status") != "ok":
        return {
            "persistent_restore_r5_owner_action_boundary_packet.json": owner_action,
            "persistent_restore_r5_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_restore_r5_summary",
                "status": "blocked",
                "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_AMBIGUOUS"
                if target_window_clear is False
                else "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_BLOCKED",
                "execution_mode": "relaunch",
                "native_launch_attempted": False,
                "storage_correlation_classified": False,
            },
        }
    before_manifest = _read_json(evidence_dir / "persistent_restore_r5_before_manifest_packet.json")
    selection = _read_json(evidence_dir / "persistent_restore_r5_hypothesis_selection_packet.json")
    after_action_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="r5_after_owner_action",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    after_action_targets = collect_target_manifest(profile_root, selection, phase="r5_after_owner_action")
    cleanup = terminate_custom_processes(str(user_data_dir))
    runtime_paths = RuntimePaths.from_env()
    relaunch = launch_native_candidate(
        repo_root=repo_root,
        layout=_layout(paths, evidence_dir),
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    relaunch_identity = build_persistent_custom_profile_identity_packet(
        phase="r5_relaunch",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=Path(paths["codex_home"]),
        user_data_dir=user_data_dir,
        expected_profile_id=profile_id,
        expected_profile_root=profile_root,
    )
    relaunch_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="r5_after_relaunch",
        changed_since_ns=_max_manifest_mtime_ns(after_action_manifest),
    )
    relaunch_targets = collect_target_manifest(profile_root, selection, phase="r5_after_relaunch")
    observed = relaunch.get("custom_process_observed") is True
    return {
        "persistent_restore_r5_owner_action_boundary_packet.json": owner_action,
        "persistent_restore_r5_after_action_manifest_packet.json": after_action_manifest,
        "persistent_restore_r5_after_action_target_manifest_packet.json": after_action_targets,
        "persistent_restore_r5_process_cleanup_packet.json": cleanup,
        "persistent_restore_r5_relaunch_packet.json": {
            **relaunch,
            "packet_kind": "persistent_restore_r5_relaunch",
            "status": "ok" if observed else "blocked",
            "profile_mode": "persistent_custom",
        },
        "persistent_restore_r5_profile_identity_relaunch_packet.json": relaunch_identity,
        "persistent_restore_r5_relaunch_manifest_packet.json": relaunch_manifest,
        "persistent_restore_r5_relaunch_target_manifest_packet.json": relaunch_targets,
        "persistent_restore_r5_owner_visibility_stop_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_owner_visibility_stop",
            "status": "blocked",
            "reason_class": "R5_OWNER_RELAUNCH_VISIBILITY_REQUIRED",
            "required_owner_marker": (
                "owner_relaunch_checked=true; same_nonce_thread_visible=true|false; "
                "target_window_clear=true; evidence_dir_preserved=true"
            ),
            "stop_required_before_correlation_classification": True,
        },
        "persistent_restore_r5_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_summary",
            "status": "blocked",
            "final_status": "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_R5_STOP_RELAUNCH_VISIBILITY_REQUIRED"
            if observed
            else "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_CORRELATION_BLOCKED",
            "execution_mode": "relaunch",
            "native_launch_attempted": True,
            "relaunch_attempted": True,
            "custom_process_observed": observed,
            "owner_action_required": observed,
            "storage_correlation_classified": False,
            "durable_restoration_proven": False,
            "local_only_restoration_source_proven": False,
            "storage_level_thread_history_proven": False,
        },
    }


def _classification_packets(
    *,
    evidence_dir: Path,
    owner_relaunch_checked: bool,
    same_nonce_thread_visible: bool | None,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
) -> dict[str, dict[str, Any]]:
    before_identity = _read_json(evidence_dir / "persistent_restore_r5_profile_identity_before_packet.json")
    relaunch_identity = _read_json(evidence_dir / "persistent_restore_r5_profile_identity_relaunch_packet.json")
    relaunch = _read_json(evidence_dir / "persistent_restore_r5_relaunch_packet.json")
    before_targets = _read_json(evidence_dir / "persistent_restore_r5_before_target_manifest_packet.json")
    after_targets = _read_json(evidence_dir / "persistent_restore_r5_after_action_target_manifest_packet.json")
    relaunch_targets = _read_json(evidence_dir / "persistent_restore_r5_relaunch_target_manifest_packet.json")
    owner_action = _read_json(evidence_dir / "persistent_restore_r5_owner_action_boundary_packet.json")
    owner_visibility = build_owner_visibility_packet(
        owner_relaunch_checked=owner_relaunch_checked,
        same_nonce_thread_visible=same_nonce_thread_visible,
        target_window_clear=target_window_clear,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    target_delta = build_r5_target_delta_packet(
        before_manifest=before_targets,
        after_action_manifest=after_targets,
        relaunch_manifest=relaunch_targets,
    )
    visibility_result = build_visibility_result_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        owner_visibility_packet=owner_visibility,
        relaunch_packet=relaunch,
    )
    storage_correlation = build_storage_correlation_result_packet(
        visibility_result_packet=visibility_result,
        target_delta_packet=target_delta,
    )
    classification = build_r5_correlation_classification_packet(
        visibility_result_packet=visibility_result,
        storage_correlation_packet=storage_correlation,
        owner_action_packet=owner_action,
        owner_visibility_packet=owner_visibility,
    )
    false_green = build_r5_false_green_audit(
        classification_packet=classification,
        visibility_result_packet=visibility_result,
        storage_correlation_packet=storage_correlation,
        target_delta_packet=target_delta,
    )
    ok = classification.get("status") == "ok" and false_green.get("status") == "ok"
    return {
        "persistent_restore_r5_owner_visibility_packet.json": owner_visibility,
        "persistent_restore_r5_target_delta_packet.json": target_delta,
        "persistent_restore_r5_visibility_result_packet.json": visibility_result,
        "persistent_restore_r5_storage_correlation_result_packet.json": storage_correlation,
        "persistent_restore_r5_correlation_classification_packet.json": classification,
        "persistent_restore_r5_false_green_audit.json": false_green,
        "persistent_restore_r5_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_restore_r5_summary",
            "status": "ok" if ok else "blocked",
            "final_status": classification.get("final_status"),
            "execution_mode": "classify",
            "owner_visible_thread_continuity_classified": (
                visibility_result.get("owner_visible_thread_continuity_classified") is True
            ),
            "storage_correlation_classified": (
                storage_correlation.get("storage_correlation_classified") is True
            ),
            "durable_restoration_proven": False,
            "local_only_restoration_source_proven": False,
            "storage_level_thread_history_proven": False,
            "route_proof_claimed": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
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


def write_packets(evidence_dir: Path, packets: dict[str, dict[str, Any]]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-restoration-correlation-r5")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--r4-evidence-dir", type=Path, default=DEFAULT_R4_EVIDENCE_DIR)
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", type=Path, default=None)
    parser.add_argument(
        "--execution-mode",
        choices=("admission", "first-launch", "relaunch", "classify"),
        default="admission",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:8318/v1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--owner-nonce", default="")
    parser.add_argument("--startup-wait-seconds", type=float, default=12.0)
    parser.add_argument("--owner-prompt-entered", action="store_true")
    parser.add_argument("--nonce-used", action="store_true")
    parser.add_argument("--target-window-clear", action="store_true")
    parser.add_argument("--evidence-dir-preserved", action="store_true")
    parser.add_argument("--owner-relaunch-checked", action="store_true")
    parser.add_argument("--same-nonce-thread-visible", default="unknown")
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    r4_evidence_dir = args.r4_evidence_dir.resolve()
    base_dir = args.base_dir.expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if args.execution_mode == "first-launch":
        packets = _first_launch_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            r4_evidence_dir=r4_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            endpoint=args.endpoint,
            model=args.model,
            owner_nonce=args.owner_nonce,
            startup_wait_seconds=args.startup_wait_seconds,
            skip_git=args.skip_git,
        )
    elif args.execution_mode == "relaunch":
        packets = _relaunch_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            owner_prompt_entered=args.owner_prompt_entered,
            nonce_used=args.nonce_used,
            target_window_clear=args.target_window_clear,
            evidence_dir_preserved=args.evidence_dir_preserved,
            startup_wait_seconds=args.startup_wait_seconds,
        )
    elif args.execution_mode == "classify":
        packets = _classification_packets(
            evidence_dir=evidence_dir,
            owner_relaunch_checked=args.owner_relaunch_checked,
            same_nonce_thread_visible=_parse_nullable_bool(args.same_nonce_thread_visible),
            target_window_clear=args.target_window_clear,
            evidence_dir_preserved=args.evidence_dir_preserved,
        )
    else:
        packets = _admission_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            r4_evidence_dir=r4_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            owner_nonce=args.owner_nonce,
            skip_git=args.skip_git,
        )
    write_packets(evidence_dir, packets)
    summary = packets["persistent_restore_r5_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
