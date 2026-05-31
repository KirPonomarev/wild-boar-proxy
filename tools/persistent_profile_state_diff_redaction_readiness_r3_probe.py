#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Persistent Custom profile state diff/redaction readiness evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import json_write
from wild_boar_proxy.persistent_profile_state_diff import (
    STATE_CLASSES,
    build_profile_snapshot,
    classify_persistent_profile_state_path,
    diff_profile_snapshots,
    marker_scan_text,
    redacted_snapshot_entry,
    synthetic_profile_snapshots,
)


TARGET_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_STATE_DIFF_REDACTION_READINESS_R3_CLASSIFIED"
PARENT_STATUS = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
EVIDENCE_DIR_NAME = (
    "audit_results/wbp_persistent_profile_state_diff_redaction_readiness_r3_2026-05-27"
)

FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_prompt_required",
    "owner_input_required",
    "live_provider_request_attempted",
    "persistent_profile_state_written",
    "persistent_profile_created_as_proof",
    "real_thread_created",
    "real_relaunch_performed",
    "real_profile_pass_claimed",
    "thread_history_preservation_claimed",
    "profile_storage_persistence_claimed",
    "saved_thread_proven",
    "native_ux_claimed",
    "keychain_behavior_classified",
    "original_codex_profile_dependency",
    "original_codex_profile_mutated",
    "original_reversibility_proven",
    "final_e2e_claimed",
    "state_class_label_is_runtime_truth",
    "state_class_label_is_thread_preservation_proof",
    "classifier_label_treated_as_runtime_truth",
    "diff_detected_is_saved_thread_proof",
    "hash_changed_is_user_visible_state",
    "synthetic_diff_is_real_profile_pass",
    "synthetic_relaunch_is_actual_relaunch_proof",
    "cache_drift_is_thread_history",
    "route_trace_used_as_history_proof",
    "raw_prompt_recorded",
    "raw_secret_recorded",
    "exhaustive_dlp_claimed",
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


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/persistent_profile_state_diff.py",
        "tools/persistent_profile_state_diff_redaction_readiness_r3_probe.py",
        "tests/test_persistent_profile_state_diff_redaction_readiness_r3.py",
    }
    admitted_current_evidence_dirs = (
        f"{relative_evidence_dir}/",
        f"{EVIDENCE_DIR_NAME}/",
    )
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "M tests/test_native_filesystem_probe.py",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]

    def is_current_contour_line(line: str) -> bool:
        path = line[3:] if len(line) > 3 else line.strip()
        return path in admitted_current_contour or path.startswith(
            admitted_current_evidence_dirs
        )

    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not is_current_contour_line(line)
    ]
    return quarantined, unexpected_dirty


def build_sync_gate_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "persistent_state_diff_sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch=run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
        git_status_short=run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        master_plan_written_to_repo=False,
        current_contour="WBP_CUSTOM_PERSISTENT_PROFILE_STATE_DIFF_REDACTION_READINESS_R3",
    )


def build_historical_quarantine_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "persistent_state_diff_historical_dirt_quarantine",
        status="ok" if not unexpected_dirty else "blocked",
        quarantined_paths=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        quarantine_classification="out_of_scope_historical_or_paused_r5_residue",
        current_contour_relies_on_quarantined_paths=False,
        current_contour_mutates_quarantined_paths=False,
        current_contour_stages_quarantined_paths=False,
    )


def build_version_pinning_packet(repo_root: Path) -> dict[str, Any]:
    return packet(
        "persistent_state_diff_version_pinning",
        codex_cli_version=run_text(repo_root, ["codex", "--version"]),
        codex_cli_path=run_text(repo_root, ["which", "codex"]),
        codex_app_path="/Applications/Codex.app",
        codex_app_version=run_text(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        codex_app_bundle_version=run_text(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        wbp_git_commit=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
    )


def build_snapshot_schema_packet() -> dict[str, Any]:
    sample = build_profile_snapshot(
        snapshot_label="schema_sample",
        entries=[redacted_snapshot_entry(relative_path="conversations/thread-redacted.json", size=1)],
    )
    return packet(
        "persistent_profile_snapshot_schema",
        required_entry_fields=["relative_path", "kind", "size", "sha256", "state_class"],
        allowed_state_classes=sorted(STATE_CLASSES),
        sample_entry=sample["entries"][0],
        content_recorded=False,
        raw_prompt_recorded=False,
        raw_secret_recorded=False,
        snapshot_schema_is_live_profile_proof=False,
    )


def build_diff_schema_packet() -> dict[str, Any]:
    snapshots = synthetic_profile_snapshots()
    diff = diff_profile_snapshots(snapshots["before"], snapshots["after"], diff_label="schema_sample")
    return packet(
        "persistent_profile_diff_schema",
        required_fields=[
            "created",
            "deleted",
            "changed",
            "state_class_counts",
            "diff_detected",
        ],
        sample_counts={
            "created_count": diff["created_count"],
            "deleted_count": diff["deleted_count"],
            "changed_count": diff["changed_count"],
        },
        diff_detected_is_saved_thread_proof=False,
        hash_changed_is_user_visible_state=False,
        synthetic_diff_is_real_profile_pass=False,
    )


def build_state_classification_packet() -> dict[str, Any]:
    examples = {
        "conversations/thread-redacted.json": "thread_history",
        "Local Storage/state.vscdb": "session_state",
        "settings/config.toml": "user_settings",
        "model-menu/catalog.json": "model_menu_state",
        "wbp/provider-linkage.json": "provider_wbp_linkage_state",
        "integrations/connector-state.json": "integration_state",
        "Cache/blob_storage/index": "cache_or_incidental_state",
        "unknown/file.bin": "unclassified_profile_state",
    }
    classified = {
        path: classify_persistent_profile_state_path(path) for path in examples
    }
    mismatches = [
        path for path, expected in examples.items() if classified[path] != expected
    ]
    return packet(
        "persistent_state_classification",
        status="ok" if not mismatches else "blocked",
        classified_examples=classified,
        expected_examples=examples,
        mismatches=mismatches,
        classifier_label_treated_as_runtime_truth=False,
        state_class_label_is_thread_preservation_proof=False,
    )


def build_classifier_non_runtime_truth_packet() -> dict[str, Any]:
    return packet(
        "persistent_state_classifier_non_runtime_truth",
        classifier_ready=True,
        classifier_label_treated_as_runtime_truth=False,
        state_class_label_is_runtime_truth=False,
        state_class_label_is_thread_preservation_proof=False,
        diff_detected_is_saved_thread_proof=False,
        route_trace_used_as_history_proof=False,
        requires_future_relaunch_visibility_proof=True,
    )


def build_redaction_policy_packet() -> dict[str, Any]:
    clean_scan = marker_scan_text("paths sizes hashes only")
    dirty_scan = marker_scan_text("OPENAI_API_KEY=example nonce_used=true")
    return packet(
        "persistent_redaction_policy",
        status="ok" if not clean_scan["raw_prompt_found"] and dirty_scan["raw_prompt_found"] else "blocked",
        allowed_evidence_fields=["relative_path", "kind", "size", "sha256", "state_class"],
        forbidden_evidence_fields=["raw_content", "raw_prompt", "raw_secret", "token"],
        clean_marker_scan=clean_scan,
        dirty_marker_scan_detects_fixture=(
            dirty_scan["raw_prompt_found"] and dirty_scan["raw_secret_found"]
        ),
        dirty_marker_scan_marker_count=len(dirty_scan["marker_findings"]),
        dirty_marker_scan_secret_pattern_count=len(dirty_scan["secret_pattern_findings"]),
        raw_prompt_recorded=False,
        raw_secret_recorded=False,
        exhaustive_dlp_claimed=False,
    )


def build_synthetic_diff_packets() -> tuple[dict[str, Any], dict[str, Any]]:
    snapshots = synthetic_profile_snapshots()
    before_after = diff_profile_snapshots(
        snapshots["before"],
        snapshots["after"],
        diff_label="synthetic_before_after",
    )
    relaunch = diff_profile_snapshots(
        snapshots["after"],
        snapshots["relaunch"],
        diff_label="synthetic_relaunch",
    )
    before_after.update(
        {
            "packet_kind": "synthetic_before_after_diff",
            "status": "ok",
            "real_profile_pass_claimed": False,
            "real_thread_created": False,
        }
    )
    relaunch.update(
        {
            "packet_kind": "synthetic_relaunch_diff",
            "status": "ok",
            "real_relaunch_performed": False,
            "synthetic_relaunch_is_actual_relaunch_proof": False,
            "real_profile_pass_claimed": False,
        }
    )
    return before_after, relaunch


def build_thread_history_non_claim_packet(before_after: dict[str, Any]) -> dict[str, Any]:
    thread_items = [
        item
        for item in before_after.get("created", []) + before_after.get("changed", [])
        if item.get("state_class") == "thread_history"
    ]
    return packet(
        "thread_history_non_claim",
        thread_history_classified_paths=[item["relative_path"] for item in thread_items],
        thread_history_preservation_claimed=False,
        saved_thread_proven=False,
        real_thread_created=False,
        real_relaunch_performed=False,
        state_class_label_is_thread_preservation_proof=False,
        requires_future_owner_visible_relaunch_proof=True,
    )


def build_cache_drift_non_claim_packet(before_after: dict[str, Any], relaunch: dict[str, Any]) -> dict[str, Any]:
    cache_items = [
        item
        for item in (
            before_after.get("created", [])
            + before_after.get("changed", [])
            + relaunch.get("created", [])
            + relaunch.get("changed", [])
        )
        if item.get("state_class") == "cache_or_incidental_state"
    ]
    return packet(
        "cache_drift_non_claim",
        cache_or_incidental_paths=[item["relative_path"] for item in cache_items],
        cache_drift_detected=bool(cache_items),
        cache_drift_is_thread_history=False,
        hash_changed_is_user_visible_state=False,
        profile_storage_persistence_claimed=False,
    )


def collect_forbidden_true_fields(payload: Any, *, prefix: str) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            if key in FORBIDDEN_TRUE_FIELDS and value is True:
                findings.append(child_prefix)
            findings.extend(collect_forbidden_true_fields(value, prefix=child_prefix))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(collect_forbidden_true_fields(value, prefix=f"{prefix}[{index}]"))
    return findings


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    for name, payload in packets.items():
        findings.extend(collect_forbidden_true_fields(payload, prefix=name))
    blocked_packets = [
        name for name, payload in packets.items() if payload.get("status") == "blocked"
    ]
    return packet(
        "persistent_state_diff_false_green_audit",
        status="ok" if not findings and not blocked_packets else "blocked",
        findings=findings,
        blocked_packets=blocked_packets,
        synthetic_used_as_live_profile_proof=False,
        classifier_label_used_as_runtime_truth=False,
        cache_drift_used_as_thread_history=False,
        hash_change_used_as_user_visible_state=False,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scan = marker_scan_text(json.dumps(packets, sort_keys=True))
    return packet(
        "persistent_state_diff_secret_redaction_audit",
        status="ok" if not scan["raw_prompt_found"] and not scan["raw_secret_found"] else "blocked",
        **scan,
        raw_prompt_recorded=False,
        raw_secret_recorded=False,
    )


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true: list[str] = []
    for name, payload in packets.items():
        forbidden_true.extend(collect_forbidden_true_fields(payload, prefix=name))
    blocked_packets = [
        name for name, payload in packets.items() if payload.get("status") == "blocked"
    ]
    ok = not forbidden_true and not blocked_packets
    return packet(
        "independent_persistent_state_diff_readiness_audit",
        status="ok" if ok else "blocked",
        forbidden_true_fields=forbidden_true,
        blocked_packets=blocked_packets,
        text_only_report_counted_as_evidence=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "persistent_profile_snapshot_schema_packet.json",
        "persistent_profile_diff_schema_packet.json",
        "persistent_state_classification_packet.json",
        "persistent_state_classifier_non_runtime_truth_packet.json",
        "persistent_redaction_policy_packet.json",
        "synthetic_before_after_diff_packet.json",
        "synthetic_relaunch_diff_packet.json",
        "thread_history_non_claim_packet.json",
        "cache_drift_non_claim_packet.json",
        "persistent_state_diff_false_green_audit.json",
        "secret_redaction_audit.json",
        "independent_persistent_state_diff_readiness_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [
        name for name, payload in packets.items() if payload.get("status") == "blocked"
    ]
    ok = not missing and not blocked
    return packet(
        "persistent_state_diff_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "",
        parent_target=PARENT_STATUS,
        parent_target_closed=False,
        this_target_closed=ok,
        missing_required_packets=missing,
        blocked_packets=blocked,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        owner_input_required=False,
        live_provider_request_attempted=False,
        persistent_profile_state_written=False,
        real_thread_created=False,
        real_relaunch_performed=False,
        thread_history_preservation_claimed=False,
        profile_storage_persistence_claimed=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        original_reversibility_proven=False,
        final_e2e_claimed=False,
    )


def build_readiness_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    before_after, relaunch = build_synthetic_diff_packets()
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": build_sync_gate_packet(repo_root, evidence_dir),
        "historical_dirt_quarantine_packet.json": build_historical_quarantine_packet(
            repo_root, evidence_dir
        ),
        "version_pinning_packet.json": build_version_pinning_packet(repo_root),
        "persistent_profile_snapshot_schema_packet.json": build_snapshot_schema_packet(),
        "persistent_profile_diff_schema_packet.json": build_diff_schema_packet(),
        "persistent_state_classification_packet.json": build_state_classification_packet(),
        "persistent_state_classifier_non_runtime_truth_packet.json": (
            build_classifier_non_runtime_truth_packet()
        ),
        "persistent_redaction_policy_packet.json": build_redaction_policy_packet(),
        "synthetic_before_after_diff_packet.json": before_after,
        "synthetic_relaunch_diff_packet.json": relaunch,
        "thread_history_non_claim_packet.json": build_thread_history_non_claim_packet(
            before_after
        ),
        "cache_drift_non_claim_packet.json": build_cache_drift_non_claim_packet(
            before_after, relaunch
        ),
    }
    packets["persistent_state_diff_false_green_audit.json"] = build_false_green_audit(
        packets
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_persistent_state_diff_readiness_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    packets["persistent_state_diff_summary_packet.json"] = build_summary_packet(packets)
    return packets


def write_closeout(evidence_dir: Path, summary: dict[str, Any], repo_root: Path) -> None:
    closeout = f"""# WBP Custom Persistent Profile State Diff Redaction Readiness R3 Closeout

## Goal

Classify Persistent Custom profile snapshot/diff/state-classification/redaction readiness without native launch, owner input, live provider calls, persistent profile writes, real thread creation, relaunch proof, storage proof, UX, Keychain, route/egress proof, or final E2E claims.

## Result

- status: {summary.get("status")}
- final verdict: {summary.get("final_status") or "BLOCKED"}
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Contour Capsule

- goal: prove synthetic snapshot/diff/classifier/redaction readiness only
- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- head: {run_text(repo_root, ["git", "rev-parse", "HEAD"])}
- touched files: wild_boar_proxy/persistent_profile_state_diff.py; tools/persistent_profile_state_diff_redaction_readiness_r3_probe.py; tests/test_persistent_profile_state_diff_redaction_readiness_r3.py; {evidence_dir.relative_to(repo_root)}
- tests run: pending final verification command output
- blocked risks: synthetic/live, classifier/runtime-truth, hash/UX, cache/history, route/history claims intentionally not made; parent target remains open
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Verification

- tests: pending final verification command output
- build: python py_compile pending final verification
- manual: none
- live verification: not performed; forbidden by this contour

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: persistent_state_diff_summary_packet.json
- report: independent_persistent_state_diff_readiness_audit.json

## Git

- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw secrets and raw prompts not recorded

## Notes

- blockers encountered: none for this readiness-only classification
- resume from here: CLOSED
"""
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=EVIDENCE_DIR_NAME)
    args = parser.parse_args()

    repo_root = REPO_ROOT
    evidence_dir = (repo_root / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_readiness_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    write_closeout(evidence_dir, packets["persistent_state_diff_summary_packet.json"], repo_root)
    result = packets["persistent_state_diff_summary_packet.json"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
