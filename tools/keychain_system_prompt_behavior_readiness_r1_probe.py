#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit non-live Keychain/system prompt behavior readiness evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import classify_keychain_observation, json_write
from wild_boar_proxy.provider_auth_strategy import build_current_codex_auth_independence_packet


TARGET_STATUS = "CODEX_CUSTOM_KEYCHAIN_PROMPT_BEHAVIOR_READINESS_R1_CLASSIFIED"
PARENT_STATUS = "CODEX_CUSTOM_KEYCHAIN_PROMPT_BEHAVIOR_CLASSIFIED"
AUTH_STRATEGY_STATUS = "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED"
AUTH_STRATEGY_DIR = "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27"
EVIDENCE_DIR_NAME = "audit_results/wbp_keychain_system_prompt_behavior_readiness_r1_2026-05-27"

FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_prompt_required",
    "owner_input_required",
    "live_provider_request_attempted",
    "keychain_mutation_performed",
    "keychain_reset_performed",
    "keychain_default_changed",
    "keychain_independence_claimed",
    "prompt_behavior_classified",
    "prompt_suppressed_claimed",
    "prompt_observed_claimed",
    "auth_success_claimed",
    "native_ux_claimed",
    "original_codex_auth_keychain_dependency",
    "original_codex_keychain_mutated",
    "automatic_owner_ready_treated_as_live_authorization",
    "live_execution_allowed_in_this_contour",
    "final_e2e_claimed",
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


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/keychain_system_prompt_behavior_readiness_r1_probe.py",
        "tests/test_keychain_system_prompt_behavior_readiness_r1_probe.py",
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
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_keychain_prompt_behavior_import_r1_2026-05-27/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? tests/test_keychain_prompt_behavior_import_r1_probe.py",
        "?? tools/keychain_prompt_behavior_import_r1_probe.py",
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
        current_contour="WBP_CODEX_CUSTOM_KEYCHAIN_SYSTEM_PROMPT_BEHAVIOR_READINESS_R1",
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
        "declared_write_surfaces",
        declared_write_surfaces=[
            "tools/keychain_system_prompt_behavior_readiness_r1_probe.py",
            "tests/test_keychain_system_prompt_behavior_readiness_r1_probe.py",
            str(evidence_dir),
        ],
        runtime_write_surfaces_declared=[],
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        keychain_mutation_allowed=False,
        keychain_reset_allowed=False,
        original_codex_keychain_mutation_allowed=False,
        route_account_model_provider_mutation_allowed=False,
    )


def build_keychain_prompt_surface_inventory_packet() -> dict[str, Any]:
    return packet(
        "keychain_prompt_surface_inventory",
        surfaces=[
            {
                "path": "wild_boar_proxy/native_filesystem_probe.py",
                "surface": "classify_keychain_observation",
                "safe_use_in_this_contour": "non-live classification packet only",
                "forbidden_use_in_this_contour": "actual prompt interaction or Keychain mutation",
            },
            {
                "path": "wild_boar_proxy/provider_auth_strategy.py",
                "surface": "auth.command and current_codex_auth_json independence packets",
                "safe_use_in_this_contour": "reference-only auth boundary",
                "forbidden_use_in_this_contour": "auth success or live use claim",
            },
            {
                "path": "wild_boar_proxy/native_launch_dispatch.py",
                "surface": "native dispatch and prompt_attempted flags",
                "safe_use_in_this_contour": "readiness boundary only",
                "forbidden_use_in_this_contour": "dispatch/process/window/prompt proof",
            },
        ],
        readiness_only=True,
        prompt_observation_performed=False,
        prompt_observed_claimed=False,
        keychain_independence_claimed=False,
    )


def build_keychain_allowed_owner_action_boundary_packet() -> dict[str, Any]:
    return packet(
        "keychain_allowed_owner_action_boundary",
        allowed_future_owner_actions=["Cancel", "Allow", "Ignore", "Not Observed"],
        owner_action_performed=False,
        owner_action_recorded="not_observed_in_readiness_contour",
        owner_cancel_counted_as_machine_proof=False,
        owner_allow_counted_as_auth_success=False,
        owner_ignore_counted_as_prompt_resolution=False,
        automatic_owner_ready_treated_as_live_authorization=False,
        prompt_action_boundary_ack_required_for_future_live=True,
    )


def build_keychain_no_hidden_mutation_packet() -> dict[str, Any]:
    return packet(
        "keychain_no_hidden_mutation",
        keychain_mutation_performed=False,
        keychain_reset_performed=False,
        keychain_default_changed=False,
        original_codex_keychain_mutated=False,
        keychain_read_performed=False,
        keychain_write_allowed=False,
        keychain_reset_allowed=False,
        hidden_runtime_mutation_allowed=False,
        raw_secret_recorded=False,
    )


def build_original_codex_auth_keychain_non_dependency_packet(
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    current_auth = build_current_codex_auth_independence_packet(provider_auth_strategy_packet)
    dependency = current_auth.get("current_codex_auth_json_execution_dependency") is True
    return packet(
        "original_codex_auth_keychain_non_dependency",
        status="blocked" if dependency else "ok",
        current_codex_auth_independence=current_auth,
        original_codex_auth_keychain_dependency=False,
        original_codex_auth_json_execution_dependency=False,
        original_codex_keychain_runtime_dependency=False,
        original_codex_keychain_mutated=False,
        current_auth_json_copied=False,
        current_auth_json_symlinked=False,
        file_auth_used_in_this_contour=False,
        readiness_counts_as_runtime_non_dependency_proof=False,
    )


def build_auth_strategy_prompt_interaction_readiness_packet(
    repo_root: Path,
    provider_auth_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    summary_path = repo_root / AUTH_STRATEGY_DIR / "provider_auth_strategy_summary_packet.json"
    summary = read_json(summary_path)
    selected = str(
        summary.get("selected_strategy")
        or provider_auth_strategy_packet.get("selected_strategy")
        or "auth.command"
    )
    ok = selected == "auth.command" and summary.get("final_status") == AUTH_STRATEGY_STATUS
    return packet(
        "auth_strategy_prompt_interaction_readiness",
        status="ok" if ok else "blocked",
        auth_strategy_reference={
            "path": f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
            "sha256": file_sha256(summary_path),
            "expected_status": AUTH_STRATEGY_STATUS,
            "reference_only": True,
        },
        selected_strategy=selected,
        auth_strategy_reproved_in_this_contour=False,
        auth_invoked_in_this_contour=False,
        auth_success_claimed=False,
        auth_success_requires_future_live_trace=True,
        keychain_prompt_behavior_classified=False,
        current_codex_auth_json_used=False,
        original_codex_auth_keychain_dependency=False,
    )


def build_system_prompt_suppression_prohibition_packet() -> dict[str, Any]:
    return packet(
        "system_prompt_suppression_prohibition",
        asar_patching_allowed=False,
        codesign_hacks_allowed=False,
        dyld_injection_allowed=False,
        hidden_runtime_mutation_allowed=False,
        keychain_reset_as_suppression_allowed=False,
        keychain_default_mutation_allowed=False,
        prompt_suppressed_claimed=False,
        suppression_attempted=False,
        suppression_counts_as_safe_integration=False,
    )


def build_prompt_minimization_not_suppression_packet() -> dict[str, Any]:
    return packet(
        "prompt_minimization_not_suppression",
        allowed_minimization_strategies=[
            "isolated_CODEX_HOME",
            "isolated_user_data_dir",
            "server_owned_auth.command_where_supported",
            "bounded_local_token_only_in_explicit_fallback_contour",
            "owner_may_cancel_if_prompt_appears",
        ],
        minimization_prepared=True,
        minimization_executed=False,
        prompt_suppressed_claimed=False,
        hidden_suppression_performed=False,
        absence_of_prompt_counts_as_minimization_success=False,
        minimization_counts_as_keychain_independence=False,
    )


def build_future_live_owner_stop_gate_packet() -> dict[str, Any]:
    return packet(
        "future_live_owner_stop_gate",
        future_live_must_stop_before_launch=True,
        live_execution_allowed_in_this_contour=False,
        automatic_owner_ready_treated_as_live_authorization=False,
        previous_owner_approval_reusable=False,
        generic_owner_ready_enough=False,
        allowed_future_owner_signals=[
            "owner_live_ready_now=true",
            "target_window_clear=true",
            "prompt_action_boundary_ack=true",
            "evidence_dir_preserved=true",
        ],
        not_enough_by_itself=[
            "generic owner_ready_now=true",
            "repeated automated contour command",
            "previous owner approval",
            "screenshot alone",
            "prompt absent by visual inspection only",
        ],
        owner_input_required=False,
        owner_prompt_required=False,
    )


def build_future_live_keychain_observation_contract_packet() -> dict[str, Any]:
    return packet(
        "future_live_keychain_observation_contract",
        future_live_import_required=True,
        prompt_observation_performed=False,
        prompt_behavior_classified=False,
        required_future_fields=[
            "command_hash_verified",
            "evidence_dir_returned",
            "prompt_appeared_true_false_unknown",
            "prompt_category_text_without_secrets",
            "owner_action_cancel_allow_ignore_not_observed",
            "no_keychain_mutation_by_wbp_tools",
            "auth_strategy_in_use",
            "original_auth_keychain_non_dependency_checked_or_drift_classified",
            "flow_result_after_prompt_classified",
            "false_green_audit_passed",
        ],
        raw_prompt_text_allowed=False,
        raw_secret_allowed=False,
        screenshot_alone_counts_as_packet_truth=False,
    )


def build_keychain_prompt_non_substitution_packet() -> dict[str, Any]:
    return packet(
        "keychain_prompt_non_substitution",
        keychain_readiness_is_live_keychain_behavior=False,
        prompt_observation_schema_is_prompt_observed=False,
        prompt_not_observed_is_keychain_independence=False,
        owner_action_boundary_is_owner_action_performed=False,
        owner_cancel_is_machine_proof=False,
        owner_allow_is_auth_success=False,
        auth_strategy_reference_is_auth_success=False,
        no_hidden_mutation_packet_is_ux_acceptance=False,
        prompt_minimization_is_prompt_suppression=False,
        original_auth_keychain_non_dependency_readiness_is_runtime_proof=False,
        future_live_stop_gate_is_live_authorization=False,
        native_ux_claimed=False,
        final_e2e_claimed=False,
    )


def build_keychain_prompt_false_green_audit(
    *,
    owner_action: dict[str, Any],
    no_mutation: dict[str, Any],
    original_dependency: dict[str, Any],
    auth_interaction: dict[str, Any],
    suppression: dict[str, Any],
    minimization: dict[str, Any],
    live_stop: dict[str, Any],
    non_substitution: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    if owner_action.get("owner_cancel_counted_as_machine_proof") is not False:
        findings.append("owner_cancel_counted_as_machine_proof")
    if owner_action.get("owner_allow_counted_as_auth_success") is not False:
        findings.append("owner_allow_counted_as_auth_success")
    if no_mutation.get("keychain_mutation_performed") is not False:
        findings.append("keychain_mutation_performed")
    if no_mutation.get("keychain_reset_performed") is not False:
        findings.append("keychain_reset_performed")
    if original_dependency.get("original_codex_auth_keychain_dependency") is not False:
        findings.append("original_codex_auth_keychain_dependency")
    if auth_interaction.get("auth_success_claimed") is not False:
        findings.append("auth_success_claimed")
    if auth_interaction.get("keychain_prompt_behavior_classified") is not False:
        findings.append("keychain_prompt_behavior_classified")
    if suppression.get("suppression_attempted") is not False:
        findings.append("system_prompt_suppression_attempted")
    if minimization.get("prompt_suppressed_claimed") is not False:
        findings.append("prompt_minimization_treated_as_suppression")
    if live_stop.get("automatic_owner_ready_treated_as_live_authorization") is not False:
        findings.append("automatic_owner_ready_treated_as_live_authorization")
    for key, value in non_substitution.items():
        if key.endswith("_claimed") and value is not False:
            findings.append(f"non_substitution.{key}")
    return packet(
        "keychain_prompt_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_claims_present=bool(findings),
        prompt_absence_used_as_keychain_independence=False,
        owner_action_used_as_machine_proof=False,
        auth_reference_used_as_auth_success=False,
        readiness_used_as_live_behavior=False,
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
        for field in FORBIDDEN_TRUE_FIELDS:
            if payload.get(field) is True:
                forbidden_true.append(f"{name}.{field}")
    ok = not forbidden_true and not blocked_packets
    return packet(
        "independent_keychain_prompt_readiness_audit",
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
        "declared_write_surfaces_packet.json",
        "keychain_prompt_surface_inventory_packet.json",
        "keychain_allowed_owner_action_boundary_packet.json",
        "keychain_no_hidden_mutation_packet.json",
        "original_codex_auth_keychain_non_dependency_packet.json",
        "auth_strategy_prompt_interaction_readiness_packet.json",
        "system_prompt_suppression_prohibition_packet.json",
        "prompt_minimization_not_suppression_packet.json",
        "future_live_owner_stop_gate_packet.json",
        "future_live_keychain_observation_contract_packet.json",
        "keychain_prompt_non_substitution_packet.json",
        "keychain_prompt_false_green_audit.json",
        "secret_redaction_audit.json",
        "independent_keychain_prompt_readiness_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    ok = not missing and not blocked
    return packet(
        "keychain_prompt_readiness_summary",
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
        keychain_mutation_performed=False,
        keychain_reset_performed=False,
        keychain_independence_claimed=False,
        prompt_behavior_classified=False,
        prompt_suppressed_claimed=False,
        auth_success_claimed=False,
        native_ux_claimed=False,
        original_codex_auth_keychain_dependency=False,
        final_e2e_claimed=False,
    )


def build_readiness_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    provider_auth_path = repo_root / AUTH_STRATEGY_DIR / "provider_auth_strategy_packet.json"
    provider_auth = read_json(provider_auth_path)
    keychain_observation = classify_keychain_observation(machine_prompt_observed=False)
    owner_action = build_keychain_allowed_owner_action_boundary_packet()
    no_mutation = build_keychain_no_hidden_mutation_packet()
    original_dependency = build_original_codex_auth_keychain_non_dependency_packet(provider_auth)
    auth_interaction = build_auth_strategy_prompt_interaction_readiness_packet(
        repo_root, provider_auth
    )
    suppression = build_system_prompt_suppression_prohibition_packet()
    minimization = build_prompt_minimization_not_suppression_packet()
    live_stop = build_future_live_owner_stop_gate_packet()
    non_substitution = build_keychain_prompt_non_substitution_packet()
    false_green = build_keychain_prompt_false_green_audit(
        owner_action=owner_action,
        no_mutation=no_mutation,
        original_dependency=original_dependency,
        auth_interaction=auth_interaction,
        suppression=suppression,
        minimization=minimization,
        live_stop=live_stop,
        non_substitution=non_substitution,
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": build_sync_gate_packet(repo_root, evidence_dir),
        "historical_dirt_quarantine_packet.json": build_historical_quarantine_packet(
            repo_root, evidence_dir
        ),
        "version_pinning_packet.json": build_version_pinning_packet(repo_root),
        "declared_write_surfaces_packet.json": build_declared_write_surfaces_packet(
            evidence_dir
        ),
        "keychain_prompt_surface_inventory_packet.json": build_keychain_prompt_surface_inventory_packet(),
        "keychain_observation_readiness_packet.json": {
            **keychain_observation,
            "prompt_behavior_classified": False,
            "keychain_independence_claimed": False,
        },
        "keychain_allowed_owner_action_boundary_packet.json": owner_action,
        "keychain_no_hidden_mutation_packet.json": no_mutation,
        "original_codex_auth_keychain_non_dependency_packet.json": original_dependency,
        "auth_strategy_prompt_interaction_readiness_packet.json": auth_interaction,
        "system_prompt_suppression_prohibition_packet.json": suppression,
        "prompt_minimization_not_suppression_packet.json": minimization,
        "future_live_owner_stop_gate_packet.json": live_stop,
        "future_live_keychain_observation_contract_packet.json": build_future_live_keychain_observation_contract_packet(),
        "keychain_prompt_non_substitution_packet.json": non_substitution,
        "keychain_prompt_false_green_audit.json": false_green,
        "auth_strategy_reference_digest_packet.json": packet(
            "auth_strategy_reference_digest",
            reference_only=True,
            auth_strategy_reproved_in_this_contour=False,
            path=f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_packet.json",
            sha256=file_sha256(provider_auth_path),
            expected_status=AUTH_STRATEGY_STATUS,
        ),
    }
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_keychain_prompt_readiness_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    packets["keychain_prompt_readiness_summary_packet.json"] = build_summary_packet(packets)
    return packets


def write_closeout(evidence_dir: Path, summary: dict[str, Any], repo_root: Path) -> None:
    closeout = f"""# WBP Codex Custom Keychain System Prompt Behavior Readiness R1 Closeout

## Goal

Prepare non-live readiness packets for future Keychain/system prompt behavior classification without native launch, owner input, Keychain mutation, auth success, UX, or live behavior claims.

## Result

- status: {summary.get("status")}
- final verdict: {summary.get("final_status") or "BLOCKED"}
- closure state: CLOSED

## Contour Capsule

- goal: classify Keychain/system prompt behavior readiness only
- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- head: {run_text(repo_root, ["git", "rev-parse", "HEAD"])}
- touched files: tools/keychain_system_prompt_behavior_readiness_r1_probe.py; tests/test_keychain_system_prompt_behavior_readiness_r1_probe.py; {evidence_dir.relative_to(repo_root)}
- tests run: pending final verification command output
- blocked risks: live/keychain/auth/UX behavior claims intentionally not made
- closure state: CLOSED

## Verification

- tests: pending final verification command output
- build: python py_compile pending final verification
- manual: none
- live verification: not performed; forbidden by this contour

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: keychain_prompt_readiness_summary_packet.json
- report: independent_keychain_prompt_readiness_audit.json

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
    write_closeout(
        evidence_dir,
        packets["keychain_prompt_readiness_summary_packet.json"],
        repo_root,
    )
    result = packets["keychain_prompt_readiness_summary_packet.json"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
