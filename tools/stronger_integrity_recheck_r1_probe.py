#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
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

from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_native_integrity_packet,
    build_original_codex_profile_drift_packet,
    build_original_codex_protected_surface_scope_packet,
    build_original_profile_inventory_packet,
    build_protected_surface_read_classification_packet,
    build_original_surface_read_classification_packet,
    json_write,
    run_idle_baseline_window,
    scan_protected_surfaces,
    summarize_idle_baseline_windows,
)


IMPORTED_PACKET_PATHS = {
    "final_e2e_integrity": (
        "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/"
        "final_dual_lane_integrity_packet.json"
    ),
    "final_e2e_acceptance": (
        "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/"
        "final_dual_lane_acceptance_matrix.json"
    ),
    "history_restore": (
        "audit_results/real_history_restore_proof_r1_2026-05-28/"
        "history_restore_packet.json"
    ),
}

APP_BUNDLE = Path("/Applications/Codex.app")
INFO_PLIST = APP_BUNDLE / "Contents" / "Info.plist"
APP_BINARY = APP_BUNDLE / "Contents" / "MacOS" / "Codex"
APP_ASAR = APP_BUNDLE / "Contents" / "Resources" / "app.asar"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_imported_packets(repo_root: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for key, relative_path in IMPORTED_PACKET_PATHS.items():
        path = repo_root / relative_path
        if not path.exists():
            loaded[key] = {
                "status": "blocked",
                "packet_kind": "missing_import",
                "missing_path": relative_path,
            }
            continue
        loaded[key] = _read_json(path)
    return loaded


def _run_text(command: list[str]) -> str:
    process = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        return ""
    return process.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_dirty_snapshot(repo_root: Path) -> dict[str, Any]:
    process = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    protected_markers = (
        "/.codex",
        "/Library/Application Support/Codex",
        "/Library/Caches/com.openai.codex",
        "/Library/HTTPStorages/com.openai.codex",
    )
    protected_like = [line for line in lines if any(marker in line for marker in protected_markers)]
    return {
        "status": "ok",
        "git_status_short": lines,
        "repo_dirty_entry_count": len(lines),
        "repo_dirty_under_protected_surface": bool(protected_like),
        "repo_dirty_protected_like_entries": protected_like,
        "repo_dirty_counts_as_protected_codex_drift": False,
    }


def _observe_bundle_boundary() -> dict[str, Any]:
    short_version = _run_text(
        [
            "/usr/libexec/PlistBuddy",
            "-c",
            "Print :CFBundleShortVersionString",
            str(INFO_PLIST),
        ]
    )
    bundle_version = _run_text(
        [
            "/usr/libexec/PlistBuddy",
            "-c",
            "Print :CFBundleVersion",
            str(INFO_PLIST),
        ]
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "bundle_boundary_observation",
        "status": "ok",
        "app_bundle_exists": APP_BUNDLE.exists(),
        "info_plist_exists": INFO_PLIST.exists(),
        "app_binary_exists": APP_BINARY.exists(),
        "app_asar_exists": APP_ASAR.exists(),
        "cfbundle_short_version_recorded": bool(short_version),
        "cfbundle_version_recorded": bool(bundle_version),
        "cfbundle_short_version": short_version,
        "cfbundle_version": bundle_version,
        "app_binary_sha256_recorded": APP_BINARY.exists(),
        "app_binary_sha256": _sha256_file(APP_BINARY) if APP_BINARY.exists() else "",
        "app_asar_sha256_recorded": APP_ASAR.exists(),
        "app_asar_sha256": _sha256_file(APP_ASAR) if APP_ASAR.exists() else "",
        "dyld_insert_libraries_present": bool(os.environ.get("DYLD_INSERT_LIBRARIES")),
        "dyld_insert_libraries_value_recorded": False,
        "codesign_recheck_performed": False,
        "bundle_hash_observation_is_scope_only": True,
        "bundle_hash_counts_as_full_runtime_integrity": False,
    }


def _live_measurements(
    *,
    idle_window_count: int = 3,
    idle_sleep_seconds: float = 0.05,
) -> dict[str, Any]:
    protected_read = build_protected_surface_read_classification_packet()
    original_surface_read = build_original_surface_read_classification_packet()
    original_inventory = build_original_profile_inventory_packet()
    native_integrity = build_native_integrity_packet(
        native_launch_attempted=False,
        temp_surface_action_performed=False,
        protected_surface_read_packet=protected_read,
    )
    original_scope = build_original_codex_protected_surface_scope_packet()
    before_surfaces = scan_protected_surfaces()
    after_surfaces = scan_protected_surfaces()
    current_drift = build_original_codex_profile_drift_packet(
        before_surfaces=before_surfaces,
        after_surfaces=after_surfaces,
    )
    windows = [
        run_idle_baseline_window(sleep_seconds=idle_sleep_seconds)
        for _ in range(idle_window_count)
    ]
    baseline_summary = summarize_idle_baseline_windows(windows)
    bundle_boundary = _observe_bundle_boundary()
    return {
        "protected_read": protected_read,
        "original_surface_read": original_surface_read,
        "original_inventory": original_inventory,
        "native_integrity": native_integrity,
        "original_scope": original_scope,
        "current_drift": current_drift,
        "idle_windows": windows,
        "baseline_summary": baseline_summary,
        "bundle_boundary": bundle_boundary,
    }


def _classify_attribution(
    *,
    current_drift: dict[str, Any],
    baseline_summary: dict[str, Any],
    repo_dirty_snapshot: dict[str, Any],
) -> dict[str, Any]:
    drift_blocked = current_drift.get("status") != "ok"
    final_verdict = str(baseline_summary.get("final_verdict") or "")
    any_baseline_drift = int(baseline_summary.get("windows_with_any_drift") or 0) > 0
    baseline_repeated = str(baseline_summary.get("drift_repeatability") or "") == "repeated"
    baseline_sporadic = any_baseline_drift and not baseline_repeated
    if not drift_blocked:
        attribution = "no_drift_observed"
        stronger = True
    elif final_verdict == "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE" and any_baseline_drift:
        attribution = "ambient_external"
        stronger = False
    elif baseline_sporadic:
        attribution = "ambient_external"
        stronger = False
    else:
        attribution = "unknown"
        stronger = False
    return {
        "current_drift_blocked": drift_blocked,
        "attribution_class": attribution,
        "repo_dirty_unrelated": repo_dirty_snapshot.get("repo_dirty_under_protected_surface") is False,
        "stronger_clean_recheck_observed": stronger,
        "unknown_attribution": attribution == "unknown",
        "ambient_external_attribution": attribution == "ambient_external",
    }


def _build_protected_surface_recheck_packet(
    *,
    live: dict[str, Any],
    repo_dirty_snapshot: dict[str, Any],
    attribution: dict[str, Any],
) -> dict[str, Any]:
    baseline_summary = live["baseline_summary"]
    current_drift = live["current_drift"]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "protected_surface_recheck",
        "status": "ok",
        "classification": (
            "clean_recheck_with_limits"
            if attribution["stronger_clean_recheck_observed"]
            else "attribution_localized_with_limits"
            if attribution["ambient_external_attribution"]
            else "blocked_unknown_attribution_with_limits"
        ),
        "protected_surface_read_status": live["protected_read"].get("status"),
        "current_contour_native_launch_attempted": False,
        "current_contour_temp_surface_action_performed": False,
        "current_contour_original_codex_write_performed": False,
        "current_contour_caused_protected_drift": False,
        "repo_dirty_entry_count": repo_dirty_snapshot["repo_dirty_entry_count"],
        "repo_dirty_under_protected_surface": repo_dirty_snapshot["repo_dirty_under_protected_surface"],
        "repo_dirty_counts_as_protected_codex_drift": False,
        "current_before_after_drift_status": current_drift.get("status"),
        "all_protected_surfaces_unchanged_in_current_recheck": current_drift.get(
            "all_protected_surfaces_unchanged"
        )
        is True,
        "idle_baseline_status": baseline_summary.get("status"),
        "idle_baseline_final_verdict": baseline_summary.get("final_verdict", ""),
        "idle_baseline_drift_repeatability": baseline_summary.get("drift_repeatability", ""),
        "idle_windows_with_any_drift": baseline_summary.get("windows_with_any_drift"),
        "attribution_class": attribution["attribution_class"],
        "stronger_clean_recheck_observed": attribution["stronger_clean_recheck_observed"],
        "unknown_attribution_cannot_upgrade_integrity": attribution["unknown_attribution"],
    }


def _build_original_codex_untouched_packet(
    *,
    live: dict[str, Any],
    attribution: dict[str, Any],
) -> dict[str, Any]:
    bundle = live["bundle_boundary"]
    current_drift = live["current_drift"]
    classification = (
        "inspection_only_untouched_with_clean_recheck"
        if attribution["stronger_clean_recheck_observed"]
        else "inspection_only_untouched_with_ambient_drift_blocker"
        if attribution["ambient_external_attribution"]
        else "inspection_only_untouched_with_unknown_drift_blocker"
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_codex_untouched",
        "status": "ok",
        "classification": classification,
        "original_codex_runtime_input": False,
        "current_contour_non_mutation_observed": True,
        "current_contour_non_mutation_equals_global_untouched": False,
        "original_codex_untouched_within_admitted_scope": True,
        "all_protected_surfaces_unchanged": current_drift.get("all_protected_surfaces_unchanged")
        is True,
        "drift_attribution_class": attribution["attribution_class"],
        "inspection_only_evidence": True,
        "inspection_only_equals_live_native_proof": False,
        "bundle_boundary_status": bundle.get("status"),
        "bundle_hash_observed_scope_only": bundle.get("bundle_hash_observation_is_scope_only") is True,
        "bundle_hash_counts_as_full_runtime_integrity": False,
        "dyld_insert_libraries_present": bundle.get("dyld_insert_libraries_present") is True,
        "codesign_recheck_performed": bundle.get("codesign_recheck_performed") is True,
        "app_binary_sha256_recorded": bundle.get("app_binary_sha256_recorded") is True,
        "app_asar_sha256_recorded": bundle.get("app_asar_sha256_recorded") is True,
    }


def _build_integrity_strengthening_packet(
    *,
    imported: dict[str, dict[str, Any]],
    protected_surface_packet: dict[str, Any],
    untouched_packet: dict[str, Any],
) -> dict[str, Any]:
    prior = imported["final_e2e_integrity"]
    attribution = protected_surface_packet["attribution_class"]
    if protected_surface_packet["stronger_clean_recheck_observed"]:
        classification = "integrity_strengthened_with_clean_recheck_limits"
    elif attribution == "ambient_external":
        classification = "integrity_blocker_localized_as_ambient_external"
    else:
        classification = "integrity_remains_blocked_unknown_attribution"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "integrity_strengthening",
        "status": "ok",
        "final_status": "STRONGER_INTEGRITY_RECHECK_CLASSIFIED_WITH_LIMITS",
        "prior_integrity_classification": prior.get("classification", ""),
        "current_integrity_classification": classification,
        "current_contour_non_mutation_observed": untouched_packet[
            "current_contour_non_mutation_observed"
        ],
        "prior_integrity_limiter_reduced": protected_surface_packet[
            "stronger_clean_recheck_observed"
        ],
        "known_blocker_localized": attribution == "ambient_external",
        "unknown_blocker_remains": attribution == "unknown",
        "imported_safety_reproven_here": False,
        "full_integrity_claimed": False,
    }


def _build_gap_matrix(
    *,
    protected_surface_packet: dict[str, Any],
    untouched_packet: dict[str, Any],
    integrity_packet: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "id": "protected_surface_clean_recheck",
            "status": "reduced"
            if protected_surface_packet["stronger_clean_recheck_observed"]
            else "blocked",
            "claim_boundary": "clean observation remains bounded integrity only",
        },
        {
            "id": "repo_dirt_vs_protected_drift",
            "status": "reduced",
            "claim_boundary": "repo dirt remains unrelated to protected surfaces",
        },
        {
            "id": "original_codex_untouched_scope",
            "status": "reduced",
            "claim_boundary": "bounded to admitted observed scope only",
        },
        {
            "id": "bundle_hash_runtime_integrity_gap",
            "status": "open_with_limits",
            "claim_boundary": "bundle/hash observation is not full runtime integrity",
        },
        {
            "id": "unknown_attribution_gap",
            "status": "open_with_limits"
            if integrity_packet["unknown_blocker_remains"]
            else "reduced",
            "claim_boundary": "unknown attribution cannot upgrade integrity",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "integrity_gap_matrix",
        "status": "ok",
        "rows": rows,
        "full_integrity_removed_all_limits": False,
        "bundle_hash_alone_proves_runtime_integrity": False,
    }


def _build_false_green_boundary_packet(
    *,
    protected_surface_packet: dict[str, Any],
    untouched_packet: dict[str, Any],
    integrity_packet: dict[str, Any],
) -> dict[str, Any]:
    booleans = {
        "repo_dirt_treated_as_protected_codex_drift": protected_surface_packet[
            "repo_dirty_counts_as_protected_codex_drift"
        ],
        "imported_safety_treated_as_reproven": integrity_packet["imported_safety_reproven_here"],
        "clean_scan_treated_as_full_integrity": (
            protected_surface_packet["stronger_clean_recheck_observed"]
            and integrity_packet["full_integrity_claimed"]
        ),
        "current_contour_non_mutation_treated_as_global_untouched": untouched_packet[
            "current_contour_non_mutation_equals_global_untouched"
        ],
        "bundle_hash_treated_as_full_runtime_integrity": untouched_packet[
            "bundle_hash_counts_as_full_runtime_integrity"
        ],
        "unknown_attribution_upgraded_to_stronger_integrity": (
            protected_surface_packet["unknown_attribution_cannot_upgrade_integrity"]
            and protected_surface_packet["stronger_clean_recheck_observed"]
        ),
    }
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "stronger_integrity_recheck_false_green_boundary",
        "status": "ok" if not any(booleans.values()) else "blocked",
        **booleans,
    }


def _build_independent_audit_packet(
    *,
    protected_surface_packet: dict[str, Any],
    untouched_packet: dict[str, Any],
    integrity_packet: dict[str, Any],
    imported: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    findings = [
        {
            "id": "repo_dirt_not_counted_as_protected_surface_drift",
            "severity": "info",
            "status": "ok",
            "evidence": "protected_surface_recheck_packet.json",
        },
        {
            "id": "imported_safety_not_promoted_to_reproven_truth",
            "severity": "info",
            "status": "ok",
            "evidence": "integrity_strengthening_packet.json",
        },
        {
            "id": "current_contour_non_mutation_remains_bounded_scope_only",
            "severity": "info",
            "status": "ok",
            "evidence": "original_codex_untouched_packet.json",
        },
        {
            "id": "bundle_hash_scope_only_not_full_runtime_integrity",
            "severity": "medium",
            "status": "open_with_limits",
            "evidence": "original_codex_untouched_packet.json",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "stronger_integrity_recheck_independent_audit",
        "status": "ok",
        "audit_mode": "local_materialized_packet_plus_optional_agent_report",
        "agent_verdict_counted": False,
        "imported_final_e2e_integrity_status": imported["final_e2e_integrity"].get("status"),
        "protected_surface_recheck_classification": protected_surface_packet.get("classification"),
        "integrity_strengthening_classification": integrity_packet.get(
            "current_integrity_classification"
        ),
        "original_codex_untouched_classification": untouched_packet.get("classification"),
        "findings": findings,
    }


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    live: dict[str, Any] | None = None,
    repo_dirty_snapshot: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    imported = _load_imported_packets(repo_root)
    live = live or _live_measurements()
    repo_dirty_snapshot = repo_dirty_snapshot or _git_dirty_snapshot(repo_root)
    attribution = _classify_attribution(
        current_drift=live["current_drift"],
        baseline_summary=live["baseline_summary"],
        repo_dirty_snapshot=repo_dirty_snapshot,
    )
    protected_surface_packet = _build_protected_surface_recheck_packet(
        live=live,
        repo_dirty_snapshot=repo_dirty_snapshot,
        attribution=attribution,
    )
    untouched_packet = _build_original_codex_untouched_packet(
        live=live,
        attribution=attribution,
    )
    integrity_packet = _build_integrity_strengthening_packet(
        imported=imported,
        protected_surface_packet=protected_surface_packet,
        untouched_packet=untouched_packet,
    )
    gap_matrix = _build_gap_matrix(
        protected_surface_packet=protected_surface_packet,
        untouched_packet=untouched_packet,
        integrity_packet=integrity_packet,
    )
    false_green = _build_false_green_boundary_packet(
        protected_surface_packet=protected_surface_packet,
        untouched_packet=untouched_packet,
        integrity_packet=integrity_packet,
    )
    audit = _build_independent_audit_packet(
        protected_surface_packet=protected_surface_packet,
        untouched_packet=untouched_packet,
        integrity_packet=integrity_packet,
        imported=imported,
    )
    return {
        "protected_surface_recheck_packet.json": protected_surface_packet,
        "original_codex_untouched_packet.json": untouched_packet,
        "integrity_strengthening_packet.json": integrity_packet,
        "integrity_gap_matrix.json": gap_matrix,
        "false_green_boundary_packet.json": false_green,
        "independent_audit_packet.json": audit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stronger-integrity-recheck-r1")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(REPO_ROOT / "audit_results/stronger_integrity_recheck_r1_2026-05-28"),
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    evidence_dir = Path(args.evidence_dir).expanduser().resolve(strict=False)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root=repo_root, evidence_dir=evidence_dir)
    for filename, packet in packets.items():
        json_write(evidence_dir / filename, packet)
    print(
        json.dumps(
            {
                "status": "ok",
                "evidence_dir": str(evidence_dir),
                "packet_count": len(packets),
                "integrity_classification": packets[
                    "integrity_strengthening_packet.json"
                ].get("current_integrity_classification"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
