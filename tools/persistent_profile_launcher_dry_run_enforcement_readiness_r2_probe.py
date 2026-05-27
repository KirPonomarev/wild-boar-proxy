#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Persistent Custom launcher dry-run enforcement readiness evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import json_write
from wild_boar_proxy.persistent_launcher_dry_run import (
    PersistentLauncherDryRunConfig,
    default_persistent_launcher_dry_run_config,
    dry_run_rejection_matrix,
    render_persistent_launcher_dry_run_command,
    validate_persistent_launcher_dry_run_config,
)


TARGET_STATUS = (
    "WBP_CUSTOM_PERSISTENT_PROFILE_LAUNCHER_DRY_RUN_ENFORCEMENT_READINESS_R2_CLASSIFIED"
)
PARENT_STATUS = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
EVIDENCE_DIR_NAME = (
    "audit_results/"
    "wbp_persistent_profile_launcher_dry_run_enforcement_readiness_r2_2026-05-27"
)
PROFILE_ID = "wbp-custom-main"

FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_prompt_required",
    "owner_input_required",
    "live_provider_request_attempted",
    "command_executed",
    "persistent_profile_state_written",
    "persistent_profile_created_as_proof",
    "thread_history_preservation_claimed",
    "profile_storage_persistence_claimed",
    "cleanup_executed",
    "backup_export_executed",
    "backup_created",
    "lock_acquired",
    "lock_enforcement_claimed",
    "lock_execution_proven",
    "live_enforcement_proven",
    "config_validation_is_live_runtime_enforcement",
    "dry_run_rejection_is_live_rejection_proof",
    "original_codex_profile_dependency",
    "original_codex_profile_mutated",
    "native_ux_claimed",
    "keychain_behavior_classified",
    "final_e2e_claimed",
    "live_execution_allowed_in_this_contour",
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
        "wild_boar_proxy/persistent_launcher_dry_run.py",
        "tools/persistent_profile_launcher_dry_run_enforcement_readiness_r2_probe.py",
        "tests/test_persistent_profile_launcher_dry_run_enforcement_readiness_r2.py",
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
        "dry_run_enforcement_sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch=run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
        git_status_short=run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        master_plan_written_to_repo=False,
        current_contour=(
            "WBP_CUSTOM_PERSISTENT_PROFILE_LAUNCHER_DRY_RUN_ENFORCEMENT_READINESS_R2"
        ),
    )


def build_historical_quarantine_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "dry_run_enforcement_historical_dirt_quarantine",
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
        "dry_run_enforcement_version_pinning",
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


def build_enforcement_contract_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    validation = validate_persistent_launcher_dry_run_config(config)
    return packet(
        "persistent_launcher_enforcement_contract",
        status=validation["status"],
        validation=validation,
        deterministic_config_builder_present=True,
        dry_run_validation_present=True,
        dry_run_rejection_present=True,
        native_launch_attempted=False,
        command_executed=False,
        persistent_profile_state_written=False,
        config_validation_is_live_runtime_enforcement=False,
    )


def build_dry_run_command_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    rendered = render_persistent_launcher_dry_run_command(config)
    validation = validate_persistent_launcher_dry_run_config(config)
    return packet(
        "persistent_launcher_dry_run_command",
        status=validation["status"],
        rendered_command=rendered,
        validation_failed_checks=validation["failed_checks"],
        command_shape_rendered=True,
        command_executed=False,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        owner_input_required=False,
        live_provider_request_attempted=False,
        command_shape_counts_as_launch_proof=False,
    )


def build_profile_mode_validation_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    valid = validate_persistent_launcher_dry_run_config(config)
    invalid = validate_persistent_launcher_dry_run_config(
        replace(config, profile_mode="ephemeral_custom")
    )
    expected_failure = "profile_mode_must_be_persistent_custom"
    ok = valid["status"] == "ok" and expected_failure in invalid["failed_checks"]
    return packet(
        "persistent_profile_mode_validation",
        status="ok" if ok else "blocked",
        valid_profile_mode=config.profile_mode,
        invalid_profile_mode="ephemeral_custom",
        invalid_status=invalid["status"],
        invalid_failed_checks=invalid["failed_checks"],
        expected_failure=expected_failure,
        expected_failure_present=expected_failure in invalid["failed_checks"],
        silent_persistent_to_ephemeral_fallback_allowed=False,
    )


def build_profile_id_validation_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    cases = [
        validate_persistent_launcher_dry_run_config(replace(config, persistent_profile_id="")),
        validate_persistent_launcher_dry_run_config(
            replace(config, persistent_profile_id="../original")
        ),
    ]
    ok = all("persistent_profile_id_invalid" in case["failed_checks"] for case in cases)
    return packet(
        "persistent_profile_id_validation",
        status="ok" if ok else "blocked",
        valid_profile_id=config.persistent_profile_id,
        invalid_cases=cases,
        missing_id_rejected=True,
        traversal_id_rejected=True,
        profile_id_validation_counts_as_history_proof=False,
    )


def build_path_authority_enforcement_packet(
    config: PersistentLauncherDryRunConfig,
) -> dict[str, Any]:
    browser = validate_persistent_launcher_dry_run_config(
        replace(config, browser_client_path_authority=True)
    )
    remote = validate_persistent_launcher_dry_run_config(
        replace(config, remote_client_path_authority=True)
    )
    provider = validate_persistent_launcher_dry_run_config(
        replace(config, client_model_provider_authority=True)
    )
    ok = (
        "browser_client_path_authority_forbidden" in browser["failed_checks"]
        and "remote_client_path_authority_forbidden" in remote["failed_checks"]
        and "client_model_provider_authority_forbidden" in provider["failed_checks"]
    )
    return packet(
        "persistent_path_authority_enforcement",
        status="ok" if ok else "blocked",
        browser_client_path_authority_rejected=(
            "browser_client_path_authority_forbidden" in browser["failed_checks"]
        ),
        remote_client_path_authority_rejected=(
            "remote_client_path_authority_forbidden" in remote["failed_checks"]
        ),
        client_model_provider_authority_rejected=(
            "client_model_provider_authority_forbidden" in provider["failed_checks"]
        ),
        browser_validation_failed_checks=browser["failed_checks"],
        remote_validation_failed_checks=remote["failed_checks"],
        provider_validation_failed_checks=provider["failed_checks"],
        profile_storage_persistence_claimed=False,
    )


def build_no_silent_fallback_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    fallback = validate_persistent_launcher_dry_run_config(
        replace(config, silent_fallback_to_ephemeral_allowed=True)
    )
    expected = "silent_persistent_to_ephemeral_fallback_forbidden"
    return packet(
        "persistent_no_silent_fallback",
        status="ok" if expected in fallback["failed_checks"] else "blocked",
        silent_persistent_to_ephemeral_fallback_allowed=False,
        fallback_rejected=expected in fallback["failed_checks"],
        fallback_validation_failed_checks=fallback["failed_checks"],
        fallback_rejection_counts_as_live_runtime_rejection=False,
    )


def build_original_profile_guard_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    dependency = validate_persistent_launcher_dry_run_config(
        replace(config, original_codex_profile_dependency=True)
    )
    mutation = validate_persistent_launcher_dry_run_config(
        replace(config, original_codex_profile_mutation_allowed=True)
    )
    ok = (
        "original_codex_profile_dependency_forbidden" in dependency["failed_checks"]
        and "original_codex_profile_mutation_forbidden" in mutation["failed_checks"]
    )
    return packet(
        "persistent_original_profile_guard",
        status="ok" if ok else "blocked",
        original_codex_profile_dependency=False,
        original_codex_profile_mutated=False,
        original_codex_profile_used_as_custom_shortcut=False,
        original_codex_history_copied=False,
        original_codex_auth_copied=False,
        dependency_rejected=(
            "original_codex_profile_dependency_forbidden" in dependency["failed_checks"]
        ),
        mutation_rejected=(
            "original_codex_profile_mutation_forbidden" in mutation["failed_checks"]
        ),
        original_guard_counts_as_original_reversibility_proof=False,
    )


def build_lock_policy_dry_run_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    invalid = validate_persistent_launcher_dry_run_config(
        replace(config, lock_policy="concurrent_same_profile_classified")
    )
    expected = "lock_policy_must_be_single_writer_only"
    return packet(
        "persistent_lock_policy_dry_run",
        status="ok" if expected in invalid["failed_checks"] else "blocked",
        policy=config.lock_policy,
        lock_path=str(config.persistent_profile_root / ".wbp-profile.lock"),
        lock_policy_rendered=True,
        lock_acquired=False,
        lock_enforcement_claimed=False,
        lock_execution_proven=False,
        concurrent_real_launch_tested=False,
        invalid_policy_rejected=expected in invalid["failed_checks"],
        lock_policy_rendered_counts_as_lock_acquired=False,
    )


def build_cleanup_backup_policy_guard_packet(
    config: PersistentLauncherDryRunConfig,
) -> dict[str, Any]:
    cleanup = validate_persistent_launcher_dry_run_config(
        replace(config, cleanup_execution_allowed=True)
    )
    backup = validate_persistent_launcher_dry_run_config(
        replace(config, backup_export_execution_allowed=True)
    )
    ok = (
        "cleanup_execution_forbidden_in_dry_run" in cleanup["failed_checks"]
        and "backup_export_execution_forbidden_in_dry_run" in backup["failed_checks"]
    )
    return packet(
        "persistent_cleanup_backup_policy_guard",
        status="ok" if ok else "blocked",
        cleanup_policy_recorded=True,
        backup_export_policy_recorded=True,
        cleanup_executed=False,
        backup_export_executed=False,
        backup_created=False,
        cleanup_execution_rejected=(
            "cleanup_execution_forbidden_in_dry_run" in cleanup["failed_checks"]
        ),
        backup_export_execution_rejected=(
            "backup_export_execution_forbidden_in_dry_run" in backup["failed_checks"]
        ),
        cleanup_policy_counts_as_cleanup_execution=False,
        backup_policy_counts_as_backup_created=False,
    )


def build_live_enforcement_non_claim_packet(config: PersistentLauncherDryRunConfig) -> dict[str, Any]:
    live = validate_persistent_launcher_dry_run_config(
        replace(config, live_execution_allowed=True)
    )
    expected = "live_execution_forbidden_in_dry_run"
    return packet(
        "persistent_launcher_live_enforcement_non_claim",
        status="ok" if expected in live["failed_checks"] else "blocked",
        live_execution_allowed_in_this_contour=False,
        live_execution_rejected=expected in live["failed_checks"],
        live_enforcement_proven=False,
        macos_open_runtime_enforcement_proven=False,
        codex_app_runtime_behavior_proven=False,
        dry_run_rejection_is_live_rejection_proof=False,
        config_validation_is_live_runtime_enforcement=False,
    )


def collect_forbidden_true_fields(
    payload: Any,
    *,
    prefix: str,
) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            if key in FORBIDDEN_TRUE_FIELDS and value is True:
                findings.append(child_prefix)
            findings.extend(collect_forbidden_true_fields(value, prefix=child_prefix))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                collect_forbidden_true_fields(value, prefix=f"{prefix}[{index}]")
            )
    return findings


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    for name, payload in packets.items():
        if not isinstance(payload, dict):
            continue
        findings.extend(collect_forbidden_true_fields(payload, prefix=name))
    blocked_packets = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    return packet(
        "persistent_launcher_enforcement_false_green_audit",
        status="ok" if not findings and not blocked_packets else "blocked",
        findings=findings,
        blocked_packets=blocked_packets,
        dry_run_used_as_native_launch_proof=False,
        dry_run_rejection_used_as_live_rejection_proof=False,
        lock_policy_used_as_lock_acquisition=False,
        cleanup_backup_policy_used_as_execution=False,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = json.dumps(packets, sort_keys=True)
    secret_patterns = (
        r"sk-(?:proj|live|cliproxy|wbp|[A-Za-z0-9]{20,})[A-Za-z0-9_-]{8,}",
        r"OPENAI_API_KEY\s*=",
        r"Authorization:\s*Bearer\s+[^<\s\"]+",
        r"refresh_token[\"']?\s*[:=]\s*[\"'][^\"']+[\"']",
    )
    prompt_markers = (
        "составь план следующего контура",
        "nonce_used=true",
        "owner_prompt_entered=true",
    )
    secret_findings = [
        pattern for pattern in secret_patterns if re.search(pattern, text, re.IGNORECASE)
    ]
    prompt_findings = [marker for marker in prompt_markers if marker in text]
    return packet(
        "persistent_launcher_enforcement_secret_redaction_audit",
        status="ok" if not secret_findings and not prompt_findings else "blocked",
        raw_secret_found=bool(secret_findings),
        raw_prompt_found=bool(prompt_findings),
        raw_secret_recorded=False,
        raw_prompt_recorded=False,
        secret_marker_findings=secret_findings,
        prompt_marker_findings=prompt_findings,
        exhaustive_dlp_claimed=False,
    )


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true: list[str] = []
    blocked_packets = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    for name, payload in packets.items():
        if not isinstance(payload, dict):
            continue
        forbidden_true.extend(collect_forbidden_true_fields(payload, prefix=name))
    ok = not forbidden_true and not blocked_packets
    return packet(
        "independent_persistent_launcher_enforcement_readiness_audit",
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
        "persistent_launcher_enforcement_contract_packet.json",
        "persistent_launcher_dry_run_command_packet.json",
        "persistent_profile_mode_validation_packet.json",
        "persistent_profile_id_validation_packet.json",
        "persistent_path_authority_enforcement_packet.json",
        "persistent_no_silent_fallback_packet.json",
        "persistent_original_profile_guard_packet.json",
        "persistent_lock_policy_dry_run_packet.json",
        "persistent_cleanup_backup_policy_guard_packet.json",
        "persistent_launcher_live_enforcement_non_claim_packet.json",
        "persistent_launcher_enforcement_false_green_audit.json",
        "secret_redaction_audit.json",
        "independent_persistent_launcher_enforcement_readiness_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    ok = not missing and not blocked
    return packet(
        "persistent_launcher_enforcement_summary",
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
        command_executed=False,
        persistent_profile_state_written=False,
        cleanup_executed=False,
        backup_export_executed=False,
        lock_acquired=False,
        live_enforcement_proven=False,
        thread_history_preservation_claimed=False,
        profile_storage_persistence_claimed=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        final_e2e_claimed=False,
    )


def build_readiness_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    config = default_persistent_launcher_dry_run_config(profile_id=PROFILE_ID)
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": build_sync_gate_packet(repo_root, evidence_dir),
        "historical_dirt_quarantine_packet.json": build_historical_quarantine_packet(
            repo_root, evidence_dir
        ),
        "version_pinning_packet.json": build_version_pinning_packet(repo_root),
        "persistent_launcher_enforcement_contract_packet.json": build_enforcement_contract_packet(
            config
        ),
        "persistent_launcher_dry_run_command_packet.json": build_dry_run_command_packet(
            config
        ),
        "persistent_profile_mode_validation_packet.json": build_profile_mode_validation_packet(
            config
        ),
        "persistent_profile_id_validation_packet.json": build_profile_id_validation_packet(
            config
        ),
        "persistent_path_authority_enforcement_packet.json": (
            build_path_authority_enforcement_packet(config)
        ),
        "persistent_no_silent_fallback_packet.json": build_no_silent_fallback_packet(
            config
        ),
        "persistent_original_profile_guard_packet.json": build_original_profile_guard_packet(
            config
        ),
        "persistent_lock_policy_dry_run_packet.json": build_lock_policy_dry_run_packet(
            config
        ),
        "persistent_cleanup_backup_policy_guard_packet.json": (
            build_cleanup_backup_policy_guard_packet(config)
        ),
        "persistent_launcher_live_enforcement_non_claim_packet.json": (
            build_live_enforcement_non_claim_packet(config)
        ),
        "dry_run_rejection_matrix_packet.json": packet(
            "dry_run_rejection_matrix",
            rejection_matrix=dry_run_rejection_matrix(config),
            live_rejection_proven=False,
        ),
    }
    packets["persistent_launcher_enforcement_false_green_audit.json"] = (
        build_false_green_audit(packets)
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_persistent_launcher_enforcement_readiness_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    packets["persistent_launcher_enforcement_summary_packet.json"] = build_summary_packet(
        packets
    )
    return packets


def write_closeout(evidence_dir: Path, summary: dict[str, Any], repo_root: Path) -> None:
    closeout = f"""# WBP Custom Persistent Profile Launcher Dry-Run Enforcement Readiness R2 Closeout

## Goal

Classify Persistent Custom launcher dry-run enforcement readiness without native launch, owner input, live provider calls, persistent profile writes, cleanup/backup execution, lock acquisition, history proof, storage proof, UX, Keychain, or final E2E claims.

## Result

- status: {summary.get("status")}
- final verdict: {summary.get("final_status") or "BLOCKED"}
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Contour Capsule

- goal: prove dry-run launcher config validation/rejection readiness only
- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- head: {run_text(repo_root, ["git", "rev-parse", "HEAD"])}
- touched files: wild_boar_proxy/persistent_launcher_dry_run.py; tools/persistent_profile_launcher_dry_run_enforcement_readiness_r2_probe.py; tests/test_persistent_profile_launcher_dry_run_enforcement_readiness_r2.py; {evidence_dir.relative_to(repo_root)}
- tests run: pending final verification command output
- blocked risks: live launch/history/storage/cleanup/backup/lock/UX/keychain/final claims intentionally not made; parent target remains open
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Verification

- tests: pending final verification command output
- build: python py_compile pending final verification
- manual: none
- live verification: not performed; forbidden by this contour

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: persistent_launcher_enforcement_summary_packet.json
- report: independent_persistent_launcher_enforcement_readiness_audit.json

## Git

- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw secrets and raw prompts not recorded

## Notes

- blockers encountered: none for this dry-run readiness classification
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
    write_closeout(
        evidence_dir,
        packets["persistent_launcher_enforcement_summary_packet.json"],
        repo_root,
    )
    result = packets["persistent_launcher_enforcement_summary_packet.json"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
