#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""R3 read-only Persistent Custom profile storage-truth classifier.

Phase A is forensic only: no native launch, no owner prompt, and no live
mutation. It classifies storage surfaces and limits without turning R2C
owner-visible continuity into durable local thread-history proof.
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

from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    default_persistent_custom_profile_paths,
    json_write,
)


DEFAULT_R2B_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27"
)
DEFAULT_R2C_EVIDENCE_DIR = (
    ROOT
    / "audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27"
)
DEFAULT_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_storage_truth_r3_2026-05-27"
)
DEFAULT_SAMPLE_PER_CLASS = 40

STATE_CLASSES = (
    "thread_history",
    "session_state",
    "user_settings",
    "model_menu_state",
    "provider_wbp_linkage_state",
    "integration_state",
    "cache_or_incidental_state",
    "unknown",
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


def _packet_file_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "exists": path.exists(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "content_hash_recorded": False,
    }


def classify_r3_storage_state_class(relative_path: str) -> str:
    lower = relative_path.replace("\\", "/").lower()
    if any(token in lower for token in ("thread", "conversation", "history", "transcript", "message")):
        return "thread_history"
    if any(token in lower for token in ("session", "window-state", "state.vscdb", "local storage", "indexeddb")):
        return "session_state"
    if any(token in lower for token in ("settings", "preferences", "config.toml", "user.json")):
        return "user_settings"
    if any(token in lower for token in ("model", "catalog", "menu")):
        return "model_menu_state"
    if any(token in lower for token in ("provider", "wbp", "registry", "proxy")):
        return "provider_wbp_linkage_state"
    if any(token in lower for token in ("integration", "mcp", "plugin", "connector", "marketplace")):
        return "integration_state"
    if any(token in lower for token in ("cache", "cached", "tmp", "blob_storage", "gpucache", "shadercache", "code cache")):
        return "cache_or_incidental_state"
    return "unknown"


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
        "tools/persistent_custom_profile_storage_truth_r3_probe.py",
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


def build_r3_sync_gate_packet(
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
        "packet_kind": "persistent_storage_sync_gate",
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
        "phase": "phase_a_readonly_forensic",
        "native_launch_attempted": False,
        "live_mutation_attempted": False,
        "master_plan_written_to_repo": False,
    }


def build_r3_historical_dirt_quarantine_packet(
    *,
    repo_root: Path,
    evidence_dir: Path,
    skip_git: bool = False,
) -> dict[str, Any]:
    quarantined, _unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }


def build_r2b_storage_reference_packet(*, r2b_evidence_dir: Path) -> dict[str, Any]:
    r2b_evidence_dir = r2b_evidence_dir.expanduser().resolve(strict=False)
    summary_path = r2b_evidence_dir / "persistent_custom_profile_history_r2b_summary_packet.json"
    state_path = r2b_evidence_dir / "persistent_r2b_profile_state_preservation_packet.json"
    thread_path = r2b_evidence_dir / "persistent_r2b_thread_history_preservation_packet.json"
    diff_path = r2b_evidence_dir / "persistent_r2b_relaunch_state_diff_packet.json"
    missing = [str(path) for path in (summary_path, state_path, thread_path, diff_path) if not path.exists()]
    if missing:
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_storage_r2b_reference",
            "status": "blocked",
            "reason_class": "R2B_STORAGE_REFERENCE_MISSING",
            "missing_packets": missing,
            "r2b_counts_as_r3_storage_pass": False,
        }
    summary = _read_json(summary_path)
    state = _read_json(state_path)
    thread = _read_json(thread_path)
    diff = _read_json(diff_path)
    expected_limited = (
        summary.get("final_status") == "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN"
        and state.get("profile_state_preserved") is False
        and thread.get("thread_history_preserved") is False
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_r2b_reference",
        "status": "ok" if expected_limited else "blocked",
        "reason_class": "" if expected_limited else "R2B_STORAGE_REFERENCE_OVERCLAIM_OR_UNUSABLE",
        "r2b_evidence_dir": str(r2b_evidence_dir),
        "referenced_packets": {
            "summary": _packet_file_metadata(summary_path),
            "profile_state": _packet_file_metadata(state_path),
            "thread_history": _packet_file_metadata(thread_path),
            "relaunch_diff": _packet_file_metadata(diff_path),
        },
        "prior_final_status": summary.get("final_status", ""),
        "prior_profile_state_preserved": state.get("profile_state_preserved") is True,
        "prior_thread_history_preserved": thread.get("thread_history_preserved") is True,
        "prior_relaunch_state_classes_observed": diff.get("state_classes_observed", []),
        "r2b_imported_as_blocked_limited_storage_evidence": expected_limited,
        "r2b_counts_as_r3_storage_pass": False,
        "profile_file_content_hashes_recorded": False,
        "evidence_file_content_hashes_recorded": False,
    }


def build_r2c_storage_reference_packet(*, r2c_evidence_dir: Path) -> dict[str, Any]:
    r2c_evidence_dir = r2c_evidence_dir.expanduser().resolve(strict=False)
    summary_path = r2c_evidence_dir / "r2c_summary_packet.json"
    classification_path = r2c_evidence_dir / "r2c_thread_continuity_classification_packet.json"
    storage_path = r2c_evidence_dir / "r2c_storage_context_packet.json"
    missing = [str(path) for path in (summary_path, classification_path, storage_path) if not path.exists()]
    if missing:
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_storage_r2c_reference",
            "status": "blocked",
            "reason_class": "R2C_STORAGE_REFERENCE_MISSING",
            "missing_packets": missing,
            "r2c_counts_as_r3_storage_pass": False,
        }
    summary = _read_json(summary_path)
    classification = _read_json(classification_path)
    storage = _read_json(storage_path)
    expected_limited = (
        summary.get("final_status")
        == "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_CLASSIFIED_WITH_STORAGE_UNPROVEN"
        and classification.get("owner_visible_thread_continuity_classified") is True
        and classification.get("storage_level_thread_history_proven") is False
        and storage.get("storage_context_only") is True
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_r2c_reference",
        "status": "ok" if expected_limited else "blocked",
        "reason_class": "" if expected_limited else "R2C_STORAGE_REFERENCE_OVERCLAIM_OR_UNUSABLE",
        "r2c_evidence_dir": str(r2c_evidence_dir),
        "referenced_packets": {
            "summary": _packet_file_metadata(summary_path),
            "classification": _packet_file_metadata(classification_path),
            "storage_context": _packet_file_metadata(storage_path),
        },
        "prior_final_status": summary.get("final_status", ""),
        "prior_owner_visible_thread_continuity_classified": (
            classification.get("owner_visible_thread_continuity_classified") is True
        ),
        "prior_storage_level_thread_history_proven": (
            classification.get("storage_level_thread_history_proven") is True
        ),
        "prior_bounded_diff_state_classes_observed": storage.get(
            "bounded_diff_state_classes_observed",
            [],
        ),
        "r2c_imported_as_owner_visible_continuity_only": expected_limited,
        "r2c_counts_as_r3_storage_pass": False,
        "profile_file_content_hashes_recorded": False,
        "evidence_file_content_hashes_recorded": False,
    }


def collect_persistent_storage_surface_inventory(
    profile_root: Path,
    *,
    sample_per_class: int = DEFAULT_SAMPLE_PER_CLASS,
) -> dict[str, Any]:
    profile_root = profile_root.expanduser()
    counts_by_class = {state_class: 0 for state_class in STATE_CLASSES}
    samples_by_class: dict[str, list[dict[str, Any]]] = {
        state_class: [] for state_class in STATE_CLASSES
    }
    kind_counts = {"files": 0, "dirs": 0, "symlinks": 0, "other": 0}
    total_file_bytes = 0
    max_mtime_ns = 0
    entry_count = 0
    fingerprint = hashlib.sha256()

    if profile_root.exists():
        paths = sorted([profile_root, *profile_root.rglob("*")], key=lambda item: str(item))
        for path in paths:
            relative_path = "." if path == profile_root else str(path.relative_to(profile_root))
            try:
                stat = path.lstat()
                if path.is_symlink():
                    kind = "symlink"
                    kind_counts["symlinks"] += 1
                elif path.is_dir():
                    kind = "dir"
                    kind_counts["dirs"] += 1
                elif path.is_file():
                    kind = "file"
                    kind_counts["files"] += 1
                    total_file_bytes += stat.st_size
                else:
                    kind = "other"
                    kind_counts["other"] += 1
                size = stat.st_size
                mtime_ns = stat.st_mtime_ns
            except OSError:
                kind = "other"
                size = 0
                mtime_ns = 0
                kind_counts["other"] += 1
            state_class = classify_r3_storage_state_class(relative_path)
            counts_by_class[state_class] += 1
            max_mtime_ns = max(max_mtime_ns, mtime_ns)
            fingerprint.update(
                f"{relative_path}\0{kind}\0{size}\0{mtime_ns}\0{state_class}\n".encode("utf-8")
            )
            sample = {
                "relative_path": relative_path,
                "kind": kind,
                "size": size,
                "mtime_ns": mtime_ns,
                "state_class": state_class,
                "classification_source": "path_metadata_only",
                "raw_content_recorded": False,
            }
            if len(samples_by_class[state_class]) < sample_per_class:
                samples_by_class[state_class].append(sample)
            entry_count += 1

    observed_classes = sorted(
        state_class for state_class, count in counts_by_class.items() if count > 0
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_surface_inventory",
        "status": "ok" if profile_root.exists() else "blocked",
        "reason_class": "" if profile_root.exists() else "PERSISTENT_PROFILE_ROOT_MISSING",
        "phase": "phase_a_readonly_forensic",
        "profile_root": str(profile_root),
        "profile_root_exists": profile_root.exists(),
        "metadata_only": True,
        "raw_content_recorded": False,
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
        "entry_count": entry_count,
        "kind_counts": kind_counts,
        "total_file_bytes": total_file_bytes,
        "max_mtime_ns": max_mtime_ns,
        "state_class_counts": counts_by_class,
        "observed_state_classes": observed_classes,
        "samples_by_state_class": samples_by_class,
        "samples_per_class_limit": sample_per_class,
        "profile_fingerprint_sha256": fingerprint.hexdigest(),
        "storage_surface_observed": entry_count > 0,
        "storage_surface_observed_counts_as_thread_history_proof": False,
    }


def build_persistent_storage_candidate_state_matrix(
    *,
    inventory_packet: dict[str, Any],
    r2b_reference_packet: dict[str, Any],
    r2c_reference_packet: dict[str, Any],
) -> dict[str, Any]:
    counts = inventory_packet.get("state_class_counts", {})
    rows = []
    for state_class in STATE_CLASSES:
        count = int(counts.get(state_class, 0))
        observed = count > 0
        is_thread_candidate = state_class in {"thread_history", "session_state"}
        rows.append(
            {
                "state_class": state_class,
                "surface_count": count,
                "storage_surface_observed": observed,
                "state_class_classified": observed,
                "classification_source": "path_metadata_only" if observed else "not_observed",
                "thread_history_candidate": observed and is_thread_candidate,
                "thread_history_durable_proven": False,
                "relaunch_restoration_source_proven": False,
                "proof_level": "candidate" if observed else "unobserved",
                "raw_content_recorded": False,
            }
        )
    candidate_count = sum(1 for row in rows if row["thread_history_candidate"])
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_candidate_state_matrix",
        "status": "ok" if inventory_packet.get("status") == "ok" else "blocked",
        "phase": "phase_a_readonly_forensic",
        "rows": rows,
        "thread_history_candidate_class_count": candidate_count,
        "durable_thread_history_proven": False,
        "relaunch_restoration_source_proven": False,
        "r2b_counts_as_storage_pass": r2b_reference_packet.get("r2b_counts_as_r3_storage_pass") is True,
        "r2c_counts_as_storage_pass": r2c_reference_packet.get("r2c_counts_as_r3_storage_pass") is True,
        "visible_thread_counted_as_storage_proof": False,
        "raw_content_recorded": False,
    }


def build_persistent_storage_proof_ladder_packet(
    *,
    inventory_packet: dict[str, Any],
    matrix_packet: dict[str, Any],
) -> dict[str, Any]:
    storage_surface_observed = inventory_packet.get("storage_surface_observed") is True
    state_class_classified = any(
        row.get("state_class_classified") is True for row in matrix_packet.get("rows", [])
    )
    thread_history_candidate = any(
        row.get("thread_history_candidate") is True for row in matrix_packet.get("rows", [])
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_proof_ladder",
        "status": "ok" if storage_surface_observed and state_class_classified else "blocked",
        "storage_surface_observed": storage_surface_observed,
        "state_class_classified": state_class_classified,
        "thread_history_candidate": thread_history_candidate,
        "thread_history_durable_proven": False,
        "relaunch_restoration_source_proven": False,
        "ladder": [
            "storage_surface_observed",
            "state_class_classified",
            "thread_history_candidate",
            "thread_history_durable_proven",
            "relaunch_restoration_source_proven",
        ],
        "current_highest_proven_rung": "thread_history_candidate"
        if thread_history_candidate
        else "state_class_classified"
        if state_class_classified
        else "storage_surface_observed"
        if storage_surface_observed
        else "none",
        "changed_file_counts_as_durable_thread_proof": False,
        "visible_thread_counts_as_storage_proof": False,
    }


def build_persistent_relaunch_restoration_source_packet(
    *,
    r2c_reference_packet: dict[str, Any],
    proof_ladder_packet: dict[str, Any],
) -> dict[str, Any]:
    owner_visible = (
        r2c_reference_packet.get("prior_owner_visible_thread_continuity_classified") is True
    )
    local_durable = proof_ladder_packet.get("relaunch_restoration_source_proven") is True
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_relaunch_restoration_source",
        "status": "ok",
        "owner_visible_thread_continuity_imported": owner_visible,
        "owner_visible_thread_counted_as_restoration_source_proof": False,
        "local_storage_restoration_source_proven": local_durable,
        "local_storage_not_proven_remote_or_sync_possible": owner_visible and not local_durable,
        "remote_or_sync_likely_claimed": False,
        "cache_only_restoration_claimed": False,
        "restoration_source_classification": "local_storage_not_proven_remote_or_sync_possible"
        if owner_visible and not local_durable
        else "local_storage_restoration_source_proven"
        if local_durable
        else "storage_truth_blocked",
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def build_persistent_storage_truth_classification_packet(
    *,
    sync_packet: dict[str, Any],
    r2b_reference_packet: dict[str, Any],
    r2c_reference_packet: dict[str, Any],
    inventory_packet: dict[str, Any],
    matrix_packet: dict[str, Any],
    proof_ladder_packet: dict[str, Any],
    restoration_packet: dict[str, Any],
) -> dict[str, Any]:
    core_ok = all(
        packet.get("status") == "ok"
        for packet in (
            sync_packet,
            r2b_reference_packet,
            r2c_reference_packet,
            inventory_packet,
            matrix_packet,
            proof_ladder_packet,
            restoration_packet,
        )
    )
    restoration_source_proven = (
        restoration_packet.get("local_storage_restoration_source_proven") is True
    )
    has_candidates = proof_ladder_packet.get("thread_history_candidate") is True
    if core_ok and restoration_source_proven:
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_LOCAL_STORAGE_CLASSIFIED"
        status = "ok"
    elif core_ok and has_candidates:
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_STORAGE_TRUTH_CLASSIFIED_WITH_LIMITS"
        status = "ok"
    elif core_ok:
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_LOCAL_STORAGE_NOT_PROVEN_REMOTE_OR_SYNC_POSSIBLE"
        status = "ok"
    else:
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_STORAGE_TRUTH_BLOCKED"
        status = "blocked"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_truth_classification",
        "status": status,
        "final_status": final_status,
        "phase": "phase_a_readonly_forensic",
        "native_launch_attempted": False,
        "live_mutation_attempted": False,
        "storage_surface_observed": inventory_packet.get("storage_surface_observed") is True,
        "state_class_classified": proof_ladder_packet.get("state_class_classified") is True,
        "thread_history_candidate": has_candidates,
        "thread_history_durable_proven": False,
        "relaunch_restoration_source_proven": restoration_source_proven,
        "storage_level_thread_history_proven": restoration_source_proven,
        "owner_visible_thread_counted_as_storage_proof": False,
        "profile_diff_counted_as_thread_history_proof": False,
        "cache_drift_counted_as_thread_preservation": False,
        "route_proof_claimed": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "native_ux_acceptance_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def build_persistent_storage_false_green_audit(
    *,
    classification_packet: dict[str, Any],
    restoration_packet: dict[str, Any],
    matrix_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = (
        classification_packet.get("owner_visible_thread_counted_as_storage_proof") is True
        or classification_packet.get("profile_diff_counted_as_thread_history_proof") is True
        or classification_packet.get("cache_drift_counted_as_thread_preservation") is True
        or classification_packet.get("route_proof_claimed") is True
        or classification_packet.get("direct_egress_absence_claimed") is True
        or classification_packet.get("model_availability_claimed") is True
        or classification_packet.get("native_ux_acceptance_claimed") is True
        or classification_packet.get("final_e2e_claimed") is True
        or restoration_packet.get("owner_visible_thread_counted_as_restoration_source_proof") is True
        or restoration_packet.get("remote_or_sync_likely_claimed") is True
        or any(
            row.get("thread_history_durable_proven") is True
            or row.get("relaunch_restoration_source_proven") is True
            for row in matrix_packet.get("rows", [])
        )
    )
    checks = [
        {
            "name": "visible_thread_not_storage_proof",
            "passed": classification_packet.get("owner_visible_thread_counted_as_storage_proof") is False,
        },
        {
            "name": "profile_diff_not_thread_history_proof",
            "passed": classification_packet.get("profile_diff_counted_as_thread_history_proof") is False,
        },
        {
            "name": "cache_drift_not_thread_preservation",
            "passed": classification_packet.get("cache_drift_counted_as_thread_preservation") is False,
        },
        {
            "name": "no_route_egress_model_ux_e2e_claims",
            "passed": not any(
                classification_packet.get(field) is True
                for field in (
                    "route_proof_claimed",
                    "direct_egress_absence_claimed",
                    "model_availability_claimed",
                    "native_ux_acceptance_claimed",
                    "final_e2e_claimed",
                )
            ),
        },
        {
            "name": "remote_or_sync_not_claimed_likely",
            "passed": restoration_packet.get("remote_or_sync_likely_claimed") is False,
        },
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_false_green_audit",
        "status": "ok"
        if not forbidden_claims_present and all(check["passed"] for check in checks)
        else "blocked",
        "forbidden_claims_present": forbidden_claims_present,
        "checks": checks,
        "text_only_audit_counted_as_pass": False,
    }


def build_phase_a_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    r2b_evidence_dir: Path,
    r2c_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    sync = build_r3_sync_gate_packet(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        skip_git=skip_git,
    )
    dirt = build_r3_historical_dirt_quarantine_packet(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        skip_git=skip_git,
    )
    r2b_reference = build_r2b_storage_reference_packet(r2b_evidence_dir=r2b_evidence_dir)
    r2c_reference = build_r2c_storage_reference_packet(r2c_evidence_dir=r2c_evidence_dir)
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    identity = build_persistent_custom_profile_identity_packet(
        phase="r3_phase_a",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    inventory = collect_persistent_storage_surface_inventory(profile_root)
    matrix = build_persistent_storage_candidate_state_matrix(
        inventory_packet=inventory,
        r2b_reference_packet=r2b_reference,
        r2c_reference_packet=r2c_reference,
    )
    proof_ladder = build_persistent_storage_proof_ladder_packet(
        inventory_packet=inventory,
        matrix_packet=matrix,
    )
    restoration = build_persistent_relaunch_restoration_source_packet(
        r2c_reference_packet=r2c_reference,
        proof_ladder_packet=proof_ladder,
    )
    classification = build_persistent_storage_truth_classification_packet(
        sync_packet=sync,
        r2b_reference_packet=r2b_reference,
        r2c_reference_packet=r2c_reference,
        inventory_packet=inventory,
        matrix_packet=matrix,
        proof_ladder_packet=proof_ladder,
        restoration_packet=restoration,
    )
    false_green = build_persistent_storage_false_green_audit(
        classification_packet=classification,
        restoration_packet=restoration,
        matrix_packet=matrix,
    )
    summary_status = (
        classification.get("status") == "ok" and false_green.get("status") == "ok"
    )
    return {
        "persistent_storage_sync_gate_packet.json": sync,
        "persistent_storage_historical_dirt_quarantine_packet.json": dirt,
        "persistent_storage_r2b_reference_packet.json": r2b_reference,
        "persistent_storage_r2c_reference_packet.json": r2c_reference,
        "persistent_custom_profile_contract_packet.json": contract,
        "persistent_custom_profile_identity_packet.json": identity,
        "persistent_storage_surface_inventory_packet.json": inventory,
        "persistent_storage_candidate_state_matrix.json": matrix,
        "persistent_storage_proof_ladder_packet.json": proof_ladder,
        "persistent_relaunch_restoration_source_packet.json": restoration,
        "persistent_storage_truth_classification_packet.json": classification,
        "persistent_storage_false_green_audit.json": false_green,
        "persistent_storage_r3_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_storage_r3_summary",
            "status": "ok" if summary_status else "blocked",
            "final_status": classification.get("final_status"),
            "phase": "phase_a_readonly_forensic",
            "native_launch_attempted": False,
            "live_mutation_attempted": False,
            "storage_surface_observed": classification.get("storage_surface_observed") is True,
            "state_class_classified": classification.get("state_class_classified") is True,
            "thread_history_candidate": classification.get("thread_history_candidate") is True,
            "storage_level_thread_history_proven": (
                classification.get("storage_level_thread_history_proven") is True
            ),
            "relaunch_restoration_source_proven": (
                classification.get("relaunch_restoration_source_proven") is True
            ),
            "false_green_audit_status": false_green.get("status"),
            "route_proof_claimed": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
        },
    }


def write_packets(evidence_dir: Path, packets: dict[str, dict[str, Any]]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)


def main() -> int:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-storage-truth-r3")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--r2b-evidence-dir", type=Path, default=DEFAULT_R2B_EVIDENCE_DIR)
    parser.add_argument("--r2c-evidence-dir", type=Path, default=DEFAULT_R2C_EVIDENCE_DIR)
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", type=Path, default=None)
    parser.add_argument("--execution-mode", choices=("phase-a",), default="phase-a")
    parser.add_argument("--skip-git", action="store_true")
    args = parser.parse_args()

    packets = build_phase_a_packets(
        repo_root=args.repo_root,
        evidence_dir=args.evidence_dir,
        r2b_evidence_dir=args.r2b_evidence_dir,
        r2c_evidence_dir=args.r2c_evidence_dir,
        profile_id=args.profile_id,
        base_dir=args.base_dir,
        skip_git=args.skip_git,
    )
    write_packets(args.evidence_dir, packets)
    summary = packets["persistent_storage_r3_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
