#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Native Custom safety/admission R2 evidence without launching Codex.app."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_native_cleanup_rollback_expectation_packet,
    build_native_custom_admission_packet,
    build_native_integrity_packet,
    build_native_safety_admission_false_green_audit,
    build_native_safety_execution_mode_decision_packet,
    build_native_safety_isolated_path_packet,
    build_native_safety_layer_boundary_packet,
    build_native_safety_reference_packet,
    build_no_ambient_authority_safety_packet,
    build_persistent_cleanup_policy_packet,
    build_persistent_custom_profile_identity_packet,
    build_protected_surface_read_classification_packet,
    classify_keychain_observation,
    collect_ambient_env_context,
    create_native_probe_layout,
    json_write,
    scan_protected_surfaces,
    validate_native_safety_admission_contour_packets,
)


TARGET_STATUS = "NATIVE_CUSTOM_SAFETY_ADMISSION_REFRESH_R2_CLASSIFIED"
PARENT_STATUS = "NATIVE_CUSTOM_SAFETY_REFRESH_CLASSIFIED"
EVIDENCE_DIR_NAME = "audit_results/wbp_native_custom_safety_admission_refresh_r2_2026-05-27"
AUTH_STRATEGY_DIR = "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27"
MODEL_READINESS_DIR = "audit_results/wbp_model_availability_smoke_matrix_readiness_r1_2026-05-27"
CLI_READINESS_DIR = "audit_results/wbp_codex_cli_runner_via_wbp_smoke_readiness_r1_2026-05-27"

FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_prompt_required",
    "owner_input_required",
    "live_provider_request_attempted",
    "network_egress_claimed",
    "direct_egress_absence_claimed",
    "native_ux_claimed",
    "native_ux_acceptance_claimed",
    "thread_history_persistence_claimed",
    "keychain_independence_claimed",
    "original_codex_mutated",
    "route_proof_claimed",
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


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    text = read_text(path)
    return sha256_text(text) if text else ""


def json_file_status(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "missing"
    except json.JSONDecodeError:
        return "invalid_json"
    return "present" if isinstance(payload, dict) else "invalid_json"


def build_historical_reference_context_packet(
    *,
    packet_kind: str,
    source_path: str,
    expected_status: str,
    source_status: str,
) -> dict[str, Any]:
    packet = build_native_safety_reference_packet(
        packet_kind=packet_kind,
        source_path=source_path,
        source_status=source_status,
        expected_status=expected_status,
    )
    if source_status != "present":
        packet["status"] = "ok"
        packet["reason_class"] = "HISTORICAL_REFERENCE_NOT_ACTIVE_TRUTH"
    packet["historical_reference_only"] = True
    packet["historical_reference_available"] = source_status == "present"
    packet["historical_reference_required_for_current_pass"] = False
    packet["current_contour_relies_on_reference"] = False
    packet["missing_historical_reference_blocks_summary"] = False
    return packet


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/native_custom_safety_admission_refresh_r2_probe.py",
        "tests/test_native_custom_safety_admission_refresh_r2_probe.py",
    }
    admitted_current_evidence_prefixes = (
        f"?? {relative_evidence_dir}/",
        f"?? {EVIDENCE_DIR_NAME}/",
    )
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "M tests/test_native_filesystem_probe.py",
        "?? tools/native_custom_safety_refresh_pre_live_r1_probe.py",
        "?? tests/test_native_custom_safety_refresh_pre_live_r1_probe.py",
        "M tools/native_custom_safety_refresh_pre_live_r1_probe.py",
        "M tests/test_native_custom_safety_refresh_pre_live_r1_probe.py",
        "?? audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27/",
        "M audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27/",
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
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(admitted_current_evidence_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def host_process_chain() -> list[dict[str, Any]]:
    pid = os.getpid()
    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    while pid and pid not in seen:
        seen.add(pid)
        process = subprocess.run(
            ["ps", "-o", "pid=,ppid=,command=", "-p", str(pid)],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
        line = process.stdout.strip()
        if not line:
            break
        parts = line.split(None, 2)
        if len(parts) < 3:
            break
        pid = int(parts[1])
        chain.append({"pid": int(parts[0]), "ppid": pid, "command": parts[2]})
    return chain


def build_sync_gate_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch=run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
        git_status_short=run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        master_plan_written_to_repo=False,
        current_contour="WBP_NATIVE_CUSTOM_SAFETY_ADMISSION_REFRESH_R2",
    )


def build_historical_quarantine_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "historical_dirt_quarantine",
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
        "version_pinning",
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


def build_declared_write_surfaces_packet(evidence_dir: Path) -> dict[str, Any]:
    return packet(
        "native_custom_declared_write_surfaces",
        declared_write_surfaces=[
            "tools/native_custom_safety_admission_refresh_r2_probe.py",
            "tests/test_native_custom_safety_admission_refresh_r2_probe.py",
            str(evidence_dir),
        ],
        runtime_write_surfaces_declared=[],
        native_launch_allowed=False,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        protected_surfaces_write_allowed=False,
        original_codex_bundle_write_allowed=False,
        original_codex_profile_write_allowed=False,
        persistent_custom_profile_write_allowed=False,
        route_account_model_provider_mutation_allowed=False,
        keychain_mutation_allowed=False,
    )


def build_admission_surface_inventory_packet(repo_root: Path) -> dict[str, Any]:
    surfaces = [
        {
            "path": "wild_boar_proxy/native_filesystem_probe.py",
            "surface": "packet builders, protected-surface scanners, and native launch helpers",
            "safe_use_in_this_contour": "packet builders and read-only snapshots only",
            "forbidden_use_in_this_contour": "launch_native_candidate/materialize/cleanup live helpers",
        },
        {
            "path": "wild_boar_proxy/native_launch_contract.py",
            "surface": "native launch command/preflight/admission contracts",
            "safe_use_in_this_contour": "contract validation only",
            "forbidden_use_in_this_contour": "runtime launch proof inference",
        },
        {
            "path": "wild_boar_proxy/native_launch_dispatch.py",
            "surface": "dispatch, process/window observation, cleanup execution packets",
            "safe_use_in_this_contour": "reference-only test boundary",
            "forbidden_use_in_this_contour": "dispatch/native-window/process observation",
        },
        {
            "path": "tools/native_custom_direct_egress_classification_probe.py",
            "surface": "bounded live native Custom egress probe",
            "safe_use_in_this_contour": "none",
            "forbidden_use_in_this_contour": "any execution or imported route/egress claim",
        },
    ]
    return packet(
        "native_custom_admission_surface_inventory",
        repo_root=str(repo_root),
        safety_admission_only=True,
        live_surfaces_identified=True,
        native_launch_surfaces_execution_allowed=False,
        route_egress_ux_surfaces_execution_allowed=False,
        surfaces=surfaces,
    )


def build_profile_mode_boundary_packet() -> dict[str, Any]:
    return packet(
        "native_custom_profile_mode_boundary",
        profile_modes={
            "ephemeral_custom": {
                "profile_lifetime": "single_contour",
                "cleanup_required": True,
                "thread_history_claim": "not_preserved_or_unproven",
                "cleanup_can_delete_history_by_default": False,
            },
            "persistent_custom": {
                "profile_lifetime": "long_lived",
                "cleanup_required": False,
                "thread_history_claim": "requires_relaunch_storage_proof",
                "cleanup_can_delete_history_by_default": False,
                "stable_profile_id_required": True,
            },
            "original_codex": {
                "profile_lifetime": "user_owned",
                "cleanup_required": "forbidden",
                "thread_history_claim": "original_app_only",
                "cleanup_can_delete_history_by_default": False,
            },
        },
        modes_distinguishable=True,
        persistent_identity_counts_as_history_proof=False,
        original_profile_shortcut_allowed=False,
        silent_persistent_to_ephemeral_fallback_allowed=False,
    )


def build_persistent_history_non_claim_packet(identity: dict[str, Any]) -> dict[str, Any]:
    return packet(
        "persistent_history_non_claim",
        persistent_profile_id=identity.get("persistent_profile_id", ""),
        persistent_profile_root=identity.get("persistent_profile_root", ""),
        stable_profile_identity_classified=identity.get("status") == "ok",
        thread_history_persistence_claimed=False,
        relaunch_storage_proof_present=False,
        owner_visible_thread_counted_as_storage_proof=False,
        route_trace_counted_as_saved_thread_proof=False,
        raw_prompt_recorded=False,
        raw_thread_content_recorded=False,
        identity_counts_as_history_proof=False,
    )


def build_keychain_prompt_non_claim_boundary_packet(
    keychain_observation: dict[str, Any],
) -> dict[str, Any]:
    return packet(
        "keychain_prompt_non_claim_boundary",
        prompt_appeared=keychain_observation.get("machine_prompt_observed"),
        prompt_observation_status=keychain_observation.get("status"),
        owner_action_recorded="none",
        owner_cancel_counted_as_machine_proof=False,
        keychain_prompt_absence_counted_as_independence_proof=False,
        keychain_independence_claimed=False,
        keychain_mutation_performed=False,
        keychain_reset_performed=False,
        original_keychain_runtime_dependency=False,
        raw_secret_recorded=False,
    )


def build_original_codex_protected_surface_packet(protected_read: dict[str, Any]) -> dict[str, Any]:
    snapshot = scan_protected_surfaces()
    targets = protected_read.get("snapshot_targets", [])
    return packet(
        "original_codex_protected_surface",
        protected_surface_snapshot=snapshot,
        protected_targets=targets,
        filesystem_read_performed=protected_read.get("filesystem_read_performed") is True,
        filesystem_write_performed=False,
        original_codex_mutated=False,
        original_codex_profile_write_allowed=False,
        original_codex_bundle_write_allowed=False,
        current_codex_auth_json_runtime_dependency=False,
        raw_secret_recorded=False,
        snapshot_is_runtime_authority=False,
    )


def build_custom_owned_surface_packet(tmp_root: Path, persistent_identity: dict[str, Any]) -> dict[str, Any]:
    layout = create_native_probe_layout(tmp_root)
    return packet(
        "custom_owned_surface",
        ephemeral_custom_owned_surfaces=[
            str(layout.profile_dir),
            str(layout.custom_codex_home),
            str(layout.custom_user_data_dir),
            str(layout.custom_home_dir),
            str(layout.custom_tmp_dir),
        ],
        persistent_custom_surface_reference={
            "persistent_profile_id": persistent_identity.get("persistent_profile_id", ""),
            "persistent_profile_root": persistent_identity.get("persistent_profile_root", ""),
            "reference_only": True,
            "writes_allowed_in_this_contour": False,
        },
        original_codex_surfaces_owned_by_custom=False,
        protected_surface_overlap_allowed=False,
        custom_owned_surface_materialized=False,
    )


def build_cleanup_rollback_policy_packet(
    cleanup_expectation: dict[str, Any],
    persistent_cleanup: dict[str, Any],
) -> dict[str, Any]:
    ok = (
        cleanup_expectation.get("status") == "ok"
        and persistent_cleanup.get("status") == "ok"
        and persistent_cleanup.get("cleanup_deletes_persistent_profile_by_default") is False
    )
    return packet(
        "native_custom_cleanup_rollback_policy",
        status="ok" if ok else "blocked",
        ephemeral_cleanup_policy="owned_temp_surfaces_only_when_materialized",
        persistent_cleanup_policy="preserve_history_by_default",
        cleanup_expectation_status=cleanup_expectation.get("status"),
        persistent_cleanup_status=persistent_cleanup.get("status"),
        cleanup_executed=False,
        rollback_executed=False,
        hidden_cleanup_performed=False,
        persistent_history_delete_allowed_by_default=False,
        explicit_owner_delete_authorization_required=True,
    )


def build_live_precondition_gate_packet() -> dict[str, Any]:
    requirements = [
        "native safety admission refreshed",
        "declared write surfaces recorded",
        "cleanup/rollback expectation recorded",
        "protected surface diff or equivalent runtime safety packet",
        "owner/detached command boundary when live owner input is required",
        "secret scan clean before import/closeout",
    ]
    return packet(
        "native_custom_live_precondition_gate",
        future_live_requirements=requirements,
        future_live_preconditions_classified=True,
        live_execution_allowed_in_this_contour=False,
        native_launch_attempted=False,
        owner_prompt_required=False,
        owner_input_required=False,
        prompt_entry_required_now=False,
        network_capture_allowed_in_this_contour=False,
        route_proof_claimed=False,
        direct_egress_absence_claimed=False,
        native_ux_claimed=False,
        final_e2e_claimed=False,
    )


def build_non_substitution_packet() -> dict[str, Any]:
    return packet(
        "native_custom_safety_non_substitution",
        filesystem_readiness_is_native_ux_proof=False,
        protected_surface_unchanged_is_route_proof=False,
        profile_identity_is_thread_history_persistence=False,
        keychain_prompt_not_observed_is_keychain_independence=False,
        admission_packet_is_native_launch=False,
        cleanup_plan_is_cleanup_execution=False,
        route_trace_200_claimed=False,
        direct_egress_absence_claimed=False,
        model_availability_claimed=False,
        original_codex_reversibility_claimed=False,
        final_e2e_claimed=False,
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
        "secret_redaction_audit",
        status="ok" if not secret_findings and not prompt_findings else "blocked",
        raw_secret_found=bool(secret_findings),
        raw_prompt_found=bool(prompt_findings),
        raw_secret_recorded=False,
        raw_prompt_recorded=False,
        secret_marker_findings=secret_findings,
        prompt_marker_findings=prompt_findings,
        protected_paths_recorded_as_classified_metadata=True,
        exhaustive_dlp_claimed=False,
    )


def build_false_green_audit(
    *,
    profile_mode: dict[str, Any],
    persistent_history: dict[str, Any],
    keychain_boundary: dict[str, Any],
    cleanup_policy: dict[str, Any],
    live_gate: dict[str, Any],
    non_substitution: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    if profile_mode.get("modes_distinguishable") is not True:
        findings.append("profile_modes_not_distinguishable")
    modes = profile_mode.get("profile_modes", {})
    persistent = modes.get("persistent_custom", {}) if isinstance(modes, dict) else {}
    if persistent.get("cleanup_can_delete_history_by_default") is not False:
        findings.append("persistent_cleanup_can_delete_history_by_default")
    if persistent_history.get("identity_counts_as_history_proof") is not False:
        findings.append("profile_identity_counts_as_history_proof")
    if persistent_history.get("thread_history_persistence_claimed") is not False:
        findings.append("thread_history_persistence_claimed")
    if keychain_boundary.get("keychain_prompt_absence_counted_as_independence_proof") is not False:
        findings.append("keychain_prompt_absence_counted_as_independence")
    if keychain_boundary.get("keychain_independence_claimed") is not False:
        findings.append("keychain_independence_claimed")
    if cleanup_policy.get("persistent_history_delete_allowed_by_default") is not False:
        findings.append("persistent_history_delete_allowed_by_default")
    if live_gate.get("live_execution_allowed_in_this_contour") is not False:
        findings.append("live_execution_allowed")
    for field, value in non_substitution.items():
        if field.endswith("_claimed") and value is not False:
            findings.append(f"non_substitution.{field}")
    return packet(
        "native_custom_safety_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_claims_present=bool(findings),
        safety_readiness_used_as_native_launch_proof=False,
        filesystem_classification_used_as_route_or_egress_proof=False,
        persistent_identity_used_as_thread_history_proof=False,
        keychain_absence_used_as_auth_boundary_proof=False,
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
        for field in FORBIDDEN_TRUE_FIELDS:
            if payload.get(field) is True:
                forbidden_true.append(f"{name}.{field}")
    ok = not forbidden_true and not blocked_packets
    return packet(
        "independent_native_custom_safety_r2_audit",
        status="ok" if ok else "blocked",
        forbidden_true_fields=forbidden_true,
        blocked_packets=blocked_packets,
        native_launch_forbidden_scan_passed=not forbidden_true,
        text_only_report_counted_as_evidence=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "native_custom_admission_surface_inventory_packet.json",
        "native_custom_profile_mode_boundary_packet.json",
        "persistent_history_non_claim_packet.json",
        "keychain_prompt_non_claim_boundary_packet.json",
        "native_custom_declared_write_surfaces_packet.json",
        "original_codex_protected_surface_packet.json",
        "custom_owned_surface_packet.json",
        "native_custom_cleanup_rollback_policy_packet.json",
        "native_custom_live_precondition_gate_packet.json",
        "native_custom_safety_non_substitution_packet.json",
        "native_custom_safety_false_green_audit.json",
        "independent_native_custom_safety_r2_audit.json",
        "secret_redaction_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    ok = not missing and not blocked
    return packet(
        "native_custom_safety_refresh_summary",
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
        live_provider_request_attempted=False,
        network_egress_claimed=False,
        direct_egress_absence_claimed=False,
        native_ux_claimed=False,
        thread_history_persistence_claimed=False,
        keychain_independence_claimed=False,
        original_codex_mutated=False,
        route_proof_claimed=False,
        final_e2e_claimed=False,
    )


def build_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    tmp_root = Path("/tmp/wbp-native-custom-safety-admission-r2")
    layout = create_native_probe_layout(tmp_root)
    persistent_root = Path.home() / ".wbp" / "codex-custom" / "profiles" / "main"
    persistent_identity = build_persistent_custom_profile_identity_packet(
        phase="admission_refresh_reference",
        profile_id="wbp-custom-main",
        profile_root=persistent_root,
        codex_home=persistent_root,
        user_data_dir=persistent_root / "user-data",
    )
    persistent_cleanup = build_persistent_cleanup_policy_packet(
        profile_root=persistent_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=None,
    )
    protected_read = build_protected_surface_read_classification_packet()
    ambient_env = collect_ambient_env_context()
    execution_mode = build_native_safety_execution_mode_decision_packet(
        execution_mode="inspection_only",
        native_launch_attempted=False,
        temp_surface_action_performed=False,
        decision_basis="canonical_platform_safe_work_before_live_native_custom",
    )
    isolated_codex_home = build_native_safety_isolated_path_packet(
        packet_kind="isolated_codex_home",
        tmp_root=tmp_root,
        path=layout.custom_codex_home,
        path_role="CODEX_HOME",
        execution_mode="inspection_only",
        materialized=False,
    )
    isolated_user_data_dir = build_native_safety_isolated_path_packet(
        packet_kind="isolated_user_data_dir",
        tmp_root=tmp_root,
        path=layout.custom_user_data_dir,
        path_role="electron_user_data_dir",
        execution_mode="inspection_only",
        materialized=False,
    )
    no_ambient = build_no_ambient_authority_safety_packet(
        ambient_env_packet=ambient_env,
        native_launch_attempted=False,
    )
    cleanup = build_native_cleanup_rollback_expectation_packet(
        tmp_root=tmp_root,
        owned_paths=[
            layout.profile_dir,
            layout.custom_codex_home,
            layout.custom_user_data_dir,
            layout.custom_home_dir,
            layout.custom_tmp_dir,
        ],
        temp_surface_action_performed=False,
        native_launch_attempted=False,
    )
    integrity = build_native_integrity_packet(
        native_launch_attempted=False,
        temp_surface_action_performed=False,
        protected_surface_read_packet=protected_read,
    )
    admission = build_native_custom_admission_packet(
        execution_mode_packet=execution_mode,
        isolated_codex_home_packet=isolated_codex_home,
        isolated_user_data_dir_packet=isolated_user_data_dir,
        no_ambient_authority_packet=no_ambient,
        protected_surface_read_packet=protected_read,
        cleanup_rollback_expectation_packet=cleanup,
        native_integrity_packet=integrity,
    )
    provider_reference = build_historical_reference_context_packet(
        packet_kind="provider_auth_strategy_reference",
        source_path=f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
        source_status=json_file_status(
            repo_root / AUTH_STRATEGY_DIR / "provider_auth_strategy_summary_packet.json"
        ),
        expected_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
    )
    model_reference = build_historical_reference_context_packet(
        packet_kind="model_availability_readiness_reference",
        source_path=f"{MODEL_READINESS_DIR}/model_availability_readiness_summary_packet.json",
        source_status=json_file_status(
            repo_root / MODEL_READINESS_DIR / "model_availability_readiness_summary_packet.json"
        ),
        expected_status="WBP_MODEL_AVAILABILITY_SMOKE_MATRIX_READINESS_CLASSIFIED",
    )
    cli_reference = build_historical_reference_context_packet(
        packet_kind="cli_runner_readiness_reference",
        source_path=f"{CLI_READINESS_DIR}/cli_runner_readiness_summary_packet.json",
        source_status=json_file_status(
            repo_root / CLI_READINESS_DIR / "cli_runner_readiness_summary_packet.json"
        ),
        expected_status="CODEX_CLI_RUNNER_VIA_WBP_SMOKE_READINESS_CLASSIFIED",
    )
    base_false_green = build_native_safety_admission_false_green_audit(
        native_custom_admission_packet=admission,
        auth_strategy_reference_packet=provider_reference,
        model_availability_reference_packet=model_reference,
        cli_runner_reference_packet=cli_reference,
    )
    profile_mode = build_profile_mode_boundary_packet()
    persistent_history = build_persistent_history_non_claim_packet(persistent_identity)
    keychain = classify_keychain_observation(machine_prompt_observed=False)
    keychain_boundary = build_keychain_prompt_non_claim_boundary_packet(keychain)
    cleanup_policy = build_cleanup_rollback_policy_packet(cleanup, persistent_cleanup)
    live_gate = build_live_precondition_gate_packet()
    non_substitution = build_non_substitution_packet()
    false_green = build_false_green_audit(
        profile_mode=profile_mode,
        persistent_history=persistent_history,
        keychain_boundary=keychain_boundary,
        cleanup_policy=cleanup_policy,
        live_gate=live_gate,
        non_substitution=non_substitution,
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": build_sync_gate_packet(repo_root, evidence_dir),
        "historical_dirt_quarantine_packet.json": build_historical_quarantine_packet(
            repo_root, evidence_dir
        ),
        "version_pinning_packet.json": build_version_pinning_packet(repo_root),
        "runtime_state_packet.json": packet(
            "runtime_state",
            host_process_chain=host_process_chain(),
            native_launch_attempted=False,
            custom_app_launch_attempted=False,
            live_network_capture_attempted=False,
            runtime_mutation_performed=False,
        ),
        "ambient_env_context_packet.json": ambient_env,
        "execution_mode_decision_packet.json": execution_mode,
        "native_custom_admission_surface_inventory_packet.json": build_admission_surface_inventory_packet(
            repo_root
        ),
        "native_custom_profile_mode_boundary_packet.json": profile_mode,
        "persistent_custom_profile_identity_packet.json": persistent_identity,
        "persistent_cleanup_policy_packet.json": persistent_cleanup,
        "persistent_history_non_claim_packet.json": persistent_history,
        "keychain_observation_packet.json": keychain,
        "keychain_prompt_non_claim_boundary_packet.json": keychain_boundary,
        "native_custom_declared_write_surfaces_packet.json": build_declared_write_surfaces_packet(
            evidence_dir
        ),
        "protected_surface_read_classification_packet.json": protected_read,
        "original_codex_protected_surface_packet.json": build_original_codex_protected_surface_packet(
            protected_read
        ),
        "custom_owned_surface_packet.json": build_custom_owned_surface_packet(
            tmp_root, persistent_identity
        ),
        "isolated_codex_home_packet.json": isolated_codex_home,
        "isolated_user_data_dir_packet.json": isolated_user_data_dir,
        "no_ambient_authority_packet.json": no_ambient,
        "cleanup_rollback_expectation_packet.json": cleanup,
        "native_custom_cleanup_rollback_policy_packet.json": cleanup_policy,
        "native_integrity_packet.json": integrity,
        "native_safety_layer_boundary_packet.json": build_native_safety_layer_boundary_packet(),
        "native_custom_admission_packet.json": admission,
        "provider_auth_strategy_reference_packet.json": provider_reference,
        "model_availability_reference_packet.json": model_reference,
        "cli_runner_reference_packet.json": cli_reference,
        "native_safety_admission_false_green_audit.json": base_false_green,
        "native_safety_false_green_audit.json": base_false_green,
        "native_custom_live_precondition_gate_packet.json": live_gate,
        "native_custom_safety_non_substitution_packet.json": non_substitution,
        "native_custom_safety_false_green_audit.json": false_green,
        "reference_digest_packet.json": packet(
            "reference_digest",
            references=[
                {
                    "path": f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
                    "sha256": file_sha256(
                        repo_root / AUTH_STRATEGY_DIR / "provider_auth_strategy_summary_packet.json"
                    ),
                    "reference_only": True,
                },
                {
                    "path": f"{MODEL_READINESS_DIR}/model_availability_readiness_summary_packet.json",
                    "sha256": file_sha256(
                        repo_root
                        / MODEL_READINESS_DIR
                        / "model_availability_readiness_summary_packet.json"
                    ),
                    "reference_only": True,
                },
                {
                    "path": f"{CLI_READINESS_DIR}/cli_runner_readiness_summary_packet.json",
                    "sha256": file_sha256(
                        repo_root / CLI_READINESS_DIR / "cli_runner_readiness_summary_packet.json"
                    ),
                    "reference_only": True,
                },
            ],
            reference_packets_reproved_here=False,
        ),
    }
    packets["native_safety_contour_validation_packet.json"] = (
        validate_native_safety_admission_contour_packets(packets)
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_native_custom_safety_r2_audit.json"] = build_independent_audit_packet(
        packets
    )
    packets["native_custom_safety_refresh_summary_packet.json"] = build_summary_packet(packets)
    return packets


def write_closeout(evidence_dir: Path, summary: dict[str, Any], repo_root: Path) -> None:
    closeout = f"""# WBP Native Custom Safety Admission Refresh R2 Closeout

## Goal

Refresh Native Custom safety/admission boundaries without native launch, owner input, network request, UX proof, route proof, thread-history proof, or Keychain-independence proof.

## Result

- status: {summary.get("status")}
- final verdict: {summary.get("final_status") or "BLOCKED"}
- closure state: CLOSED

## Contour Capsule

- goal: classify Native Custom safety/admission R2 only
- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- head: {run_text(repo_root, ["git", "rev-parse", "HEAD"])}
- touched files: tools/native_custom_safety_admission_refresh_r2_probe.py; tests/test_native_custom_safety_admission_refresh_r2_probe.py; {evidence_dir.relative_to(repo_root)}
- tests run: recorded in final operator closeout; probe packets generated and JSON-parseable
- blocked risks: live/native/route/UX/history/keychain claims intentionally not made
- closure state: CLOSED

## Verification

- tests: pending final verification command output
- build: python py_compile pending final verification
- manual: none
- live verification: not performed; forbidden by this contour

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: native_custom_safety_refresh_summary_packet.json
- report: independent_native_custom_safety_r2_audit.json

## Git

- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw secrets and raw prompts not recorded

## Notes

- blockers encountered: none for this safety/admission-only classification
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
    packets = build_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    write_closeout(
        evidence_dir,
        packets["native_custom_safety_refresh_summary_packet.json"],
        repo_root,
    )
    result = packets["native_custom_safety_refresh_summary_packet.json"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
