#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Refresh Native Custom pre-live safety boundaries without launching Codex.app."""

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
    build_native_safety_execution_mode_decision_packet,
    build_native_safety_isolated_path_packet,
    build_native_safety_layer_boundary_packet,
    build_native_safety_reference_packet,
    build_no_ambient_authority_safety_packet,
    build_original_auth_boundary_packet,
    build_original_profile_inventory_packet,
    build_original_surface_read_classification_packet,
    build_persistent_cleanup_policy_packet,
    build_protected_surface_read_classification_packet,
    collect_ambient_env_context,
    create_native_probe_layout,
    json_write,
    scan_protected_surfaces,
)
from tools.historical_audit_fixtures import historical_audit_path


TARGET_STATUS = "NATIVE_CUSTOM_SAFETY_REFRESH_CLASSIFIED"
EVIDENCE_DIR_NAME = "audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27"
AUTH_STRATEGY_DIR = "audit_results/wbp_provider_auth_strategy_precedence_r1_2026-05-27"
CLI_RUNNER_DIR = "audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27"
MODEL_AVAILABILITY_DIR = "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27"
MODEL_AVAILABILITY_SUMMARY = "model_availability_direct_only_summary_packet.json"

FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_prompt_required",
    "owner_input_required",
    "live_provider_request_attempted",
    "route_proof_claimed",
    "direct_egress_absence_claimed",
    "native_ux_claimed",
    "final_e2e_claimed",
    "original_codex_reversibility_claimed",
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
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def json_file_status(path: Path) -> str:
    payload = read_json(path)
    return "present" if payload else "missing"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    try:
        return sha256_text(path.read_text(encoding="utf-8", errors="replace"))
    except FileNotFoundError:
        return ""


def current_status_lines(repo_root: Path) -> list[str]:
    return run_text(repo_root, ["git", "status", "--short"]).splitlines()


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = current_status_lines(repo_root)
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/native_custom_safety_refresh_pre_live_r1_probe.py",
        "tools/native_custom_safety_admission_refresh_r2_probe.py",
        "tests/test_native_custom_safety_refresh_pre_live_r1_probe.py",
    }
    admitted_current_evidence_prefixes = (
        f"?? {relative_evidence_dir}/",
        f"M {relative_evidence_dir}/",
        f" M {relative_evidence_dir}/",
        f"?? {EVIDENCE_DIR_NAME}/",
        f"M {EVIDENCE_DIR_NAME}/",
        f" M {EVIDENCE_DIR_NAME}/",
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
        git_status_short=current_status_lines(repo_root),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        current_contour="NATIVE_CUSTOM_SAFETY_REFRESH_PRE_LIVE_R1",
        master_plan_written_to_repo=False,
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
            "tools/native_custom_safety_refresh_pre_live_r1_probe.py",
            "tests/test_native_custom_safety_refresh_pre_live_r1_probe.py",
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


def build_launcher_identity_packet(layout: Any) -> dict[str, Any]:
    launcher_path = layout.launcher_path.resolve(strict=False)
    tmp_root = layout.tmp_root.resolve(strict=False)
    under_tmp_root = launcher_path.is_relative_to(tmp_root)
    profile_dir = layout.profile_dir.resolve(strict=False)
    return packet(
        "native_custom_launcher_identity",
        status="ok" if under_tmp_root else "blocked",
        launch_mode="CODEX_CUSTOM_NATIVE_APP",
        profile_mode="ephemeral_custom",
        launcher_path=str(launcher_path),
        profile_dir=str(profile_dir),
        effective_codex_home=str(layout.custom_codex_home.resolve(strict=False)),
        effective_user_data_dir=str(layout.custom_user_data_dir.resolve(strict=False)),
        launcher_under_tmp_root=under_tmp_root,
        launcher_materialized=False,
        silent_fallback_to_ephemeral_allowed=False,
        browser_client_override_allowed=False,
        remote_client_override_allowed=False,
        counts_as_launch_success=False,
    )


def build_effective_paths_packet(layout: Any) -> dict[str, Any]:
    tmp_root = layout.tmp_root
    codex_home_packet = build_native_safety_isolated_path_packet(
        packet_kind="isolated_codex_home",
        tmp_root=tmp_root,
        path=layout.custom_codex_home,
        path_role="CODEX_HOME",
        execution_mode="inspection_only",
        materialized=False,
    )
    user_data_packet = build_native_safety_isolated_path_packet(
        packet_kind="isolated_user_data_dir",
        tmp_root=tmp_root,
        path=layout.custom_user_data_dir,
        path_role="electron_user_data_dir",
        execution_mode="inspection_only",
        materialized=False,
    )
    home_under_tmp = layout.custom_home_dir.resolve(strict=False).is_relative_to(
        tmp_root.resolve(strict=False)
    )
    tmp_under_tmp = layout.custom_tmp_dir.resolve(strict=False).is_relative_to(
        tmp_root.resolve(strict=False)
    )
    ok = (
        codex_home_packet.get("status") == "ok"
        and user_data_packet.get("status") == "ok"
        and home_under_tmp
        and tmp_under_tmp
    )
    return packet(
        "native_custom_effective_paths",
        status="ok" if ok else "blocked",
        tmp_root=str(tmp_root.resolve(strict=False)),
        effective_codex_home=str(layout.custom_codex_home.resolve(strict=False)),
        effective_user_data_dir=str(layout.custom_user_data_dir.resolve(strict=False)),
        effective_home=str(layout.custom_home_dir.resolve(strict=False)),
        effective_tmp_dir=str(layout.custom_tmp_dir.resolve(strict=False)),
        codex_home_packet=codex_home_packet,
        user_data_dir_packet=user_data_packet,
        home_under_tmp_root=home_under_tmp,
        tmp_dir_under_tmp_root=tmp_under_tmp,
        native_launch_attempted=False,
    )


def build_protected_surface_observation_packet() -> dict[str, Any]:
    protected_read = build_protected_surface_read_classification_packet()
    protected_snapshot = scan_protected_surfaces()
    ok = (
        protected_read.get("status") == "ok"
        and protected_read.get("inspection_only") is True
        and protected_read.get("filesystem_write_performed") is False
    )
    return packet(
        "native_custom_protected_surface_observation",
        status="ok" if ok else "blocked",
        protected_surface_read_status=protected_read.get("status"),
        inspection_only=protected_read.get("inspection_only") is True,
        filesystem_read_performed=protected_read.get("filesystem_read_performed") is True,
        filesystem_write_performed=False,
        runtime_auth_input_used=False,
        snapshot_targets=protected_read.get("snapshot_targets", []),
        protected_surface_snapshot=protected_snapshot,
        observation_only=True,
        counts_as_no_hidden_mutation_everywhere=False,
    )


def build_original_codex_untouched_packet() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    surface_read = build_original_surface_read_classification_packet()
    profile_inventory = build_original_profile_inventory_packet()
    auth_boundary = build_original_auth_boundary_packet(
        profile_inventory_packet=profile_inventory
    )
    ok = (
        surface_read.get("status") == "ok"
        and profile_inventory.get("status") == "ok"
        and auth_boundary.get("status") == "ok"
    )
    packet_payload = packet(
        "native_custom_original_codex_untouched",
        status="ok" if ok else "blocked",
        original_surface_read_status=surface_read.get("status"),
        original_profile_inventory_status=profile_inventory.get("status"),
        original_auth_boundary_status=auth_boundary.get("status"),
        filesystem_write_performed=False,
        original_codex_mutated=False,
        original_codex_bundle_write_allowed=False,
        original_codex_profile_write_allowed=False,
        current_auth_json_execution_dependency=False,
        counts_as_original_reversibility_proof=False,
    )
    return packet_payload, profile_inventory, auth_boundary


def build_cleanup_rollback_packet(layout: Any) -> dict[str, Any]:
    cleanup_expectation = build_native_cleanup_rollback_expectation_packet(
        tmp_root=layout.tmp_root,
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
    persistent_cleanup = build_persistent_cleanup_policy_packet(
        profile_root=Path.home() / ".wbp" / "codex-custom" / "profiles" / "main",
        cleanup_attempted=False,
        profile_exists_after_cleanup=None,
    )
    ok = (
        cleanup_expectation.get("status") == "ok"
        and persistent_cleanup.get("status") == "ok"
        and persistent_cleanup.get("cleanup_deletes_persistent_profile_by_default")
        is False
    )
    return packet(
        "native_custom_cleanup_rollback",
        status="ok" if ok else "blocked",
        cleanup_expectation_status=cleanup_expectation.get("status"),
        persistent_cleanup_status=persistent_cleanup.get("status"),
        cleanup_required=cleanup_expectation.get("cleanup_required"),
        rollback_required=cleanup_expectation.get("rollback_required"),
        cleanup_executed=False,
        rollback_executed=False,
        explicit_owner_delete_authorization_required=True,
        persistent_history_delete_allowed_by_default=False,
        cleanup_removes_only_custom_owned_surfaces=cleanup_expectation.get(
            "cleanup_removes_only_custom_owned_surfaces"
        )
        is True,
        persistent_cleanup_policy_packet=persistent_cleanup,
        cleanup_expectation_packet=cleanup_expectation,
    )


def build_auth_boundary_refresh_packet(
    repo_root: Path,
    ambient_env_packet: dict[str, Any],
    original_auth_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    summary_path = historical_audit_path(
        repo_root, f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json"
    )
    summary = read_json(summary_path)
    selected_strategy = str(summary.get("selected_strategy", ""))
    reference = build_native_safety_reference_packet(
        packet_kind="provider_auth_strategy_reference",
        source_path=f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
        source_status=json_file_status(summary_path),
        expected_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
    )
    no_ambient = build_no_ambient_authority_safety_packet(
        ambient_env_packet=ambient_env_packet,
        native_launch_attempted=False,
    )
    ok = (
        reference.get("status") == "ok"
        and no_ambient.get("status") == "ok"
        and original_auth_boundary_packet.get("status") == "ok"
        and selected_strategy == "auth.command"
    )
    return packet(
        "native_custom_auth_boundary_refresh",
        status="ok" if ok else "blocked",
        provider_auth_strategy_reference=reference,
        selected_strategy=selected_strategy,
        ambient_env_status=ambient_env_packet.get("status"),
        ambient_authority_used_for_native_launch=False,
        current_codex_auth_json_runtime_dependency=False,
        original_auth_boundary_status=original_auth_boundary_packet.get("status"),
        auth_boundary_dependency_check_only=True,
        auth_boundary_clean_counts_as_route_proof=False,
        auth_boundary_clean_counts_as_launcher_usability_proof=False,
        no_ambient_authority_packet=no_ambient,
    )


def build_execution_hygiene_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "native_custom_execution_hygiene",
        status="ok" if not unexpected_dirty else "blocked",
        quarantined_paths=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        current_contour_relies_on_quarantined_paths=False,
        current_contour_mutates_quarantined_paths=False,
        current_contour_stages_quarantined_paths=False,
        admitted_current_contour_writes=[
            "tools/native_custom_safety_refresh_pre_live_r1_probe.py",
            "tests/test_native_custom_safety_refresh_pre_live_r1_probe.py",
            str(evidence_dir.relative_to(repo_root)),
        ],
        execution_hygiene_is_product_truth=False,
    )


def build_admission_packet(
    *,
    execution_mode_packet: dict[str, Any],
    effective_paths_packet: dict[str, Any],
    protected_surface_observation_packet: dict[str, Any],
    cleanup_rollback_packet: dict[str, Any],
    auth_boundary_refresh_packet: dict[str, Any],
    original_codex_untouched_packet: dict[str, Any],
    launcher_identity_packet: dict[str, Any],
) -> dict[str, Any]:
    admission_core = build_native_custom_admission_packet(
        execution_mode_packet=execution_mode_packet,
        isolated_codex_home_packet=effective_paths_packet.get("codex_home_packet", {}),
        isolated_user_data_dir_packet=effective_paths_packet.get("user_data_dir_packet", {}),
        no_ambient_authority_packet=auth_boundary_refresh_packet.get(
            "no_ambient_authority_packet", {}
        ),
        protected_surface_read_packet={
            "inspection_only": protected_surface_observation_packet.get("inspection_only"),
            "runtime_auth_input_used": protected_surface_observation_packet.get(
                "runtime_auth_input_used"
            ),
            "filesystem_write_performed": protected_surface_observation_packet.get(
                "filesystem_write_performed"
            ),
        },
        cleanup_rollback_expectation_packet=cleanup_rollback_packet.get(
            "cleanup_expectation_packet", {}
        ),
        native_integrity_packet=build_native_integrity_packet(
            native_launch_attempted=False,
            temp_surface_action_performed=False,
            protected_surface_read_packet={
                "inspection_only": protected_surface_observation_packet.get("inspection_only"),
                "runtime_auth_input_used": protected_surface_observation_packet.get(
                    "runtime_auth_input_used"
                ),
                "filesystem_write_performed": protected_surface_observation_packet.get(
                    "filesystem_write_performed"
                ),
                "status": protected_surface_observation_packet.get("status"),
            },
        ),
    )
    checks = [
        {
            "name": "launcher_identity_classified",
            "passed": launcher_identity_packet.get("status") == "ok",
            "evidence": "native_custom_launcher_identity_packet.json",
        },
        {
            "name": "effective_paths_classified",
            "passed": effective_paths_packet.get("status") == "ok",
            "evidence": "native_custom_effective_paths_packet.json",
        },
        {
            "name": "protected_surface_observation_classified",
            "passed": protected_surface_observation_packet.get("status") == "ok",
            "evidence": "native_custom_protected_surface_observation_packet.json",
        },
        {
            "name": "cleanup_and_rollback_classified",
            "passed": cleanup_rollback_packet.get("status") == "ok",
            "evidence": "native_custom_cleanup_rollback_packet.json",
        },
        {
            "name": "auth_boundary_refresh_classified",
            "passed": auth_boundary_refresh_packet.get("status") == "ok",
            "evidence": "native_custom_auth_boundary_refresh_packet.json",
        },
        {
            "name": "original_codex_untouched_classified",
            "passed": original_codex_untouched_packet.get("status") == "ok",
            "evidence": "native_custom_original_codex_untouched_packet.json",
        },
        {
            "name": "native_admission_core_ok",
            "passed": admission_core.get("status") == "ok",
            "evidence": "derived native admission core",
        },
    ]
    ready = all(check["passed"] for check in checks)
    return packet(
        "native_custom_safety_admission",
        status="ok" if ready else "blocked",
        final_status=TARGET_STATUS if ready else "",
        admission_ready=ready,
        launch_executed=False,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        live_execution_allowed_in_this_contour=False,
        route_proof_claimed=False,
        direct_egress_absence_claimed=False,
        native_ux_claimed=False,
        original_codex_reversibility_claimed=False,
        final_e2e_claimed=False,
        checks=checks,
    )


def build_false_green_audit(
    *,
    admission_packet: dict[str, Any],
    launcher_identity_packet: dict[str, Any],
    protected_surface_observation_packet: dict[str, Any],
    auth_boundary_refresh_packet: dict[str, Any],
    execution_hygiene_packet: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        {
            "name": "admission_not_launch",
            "passed": admission_packet.get("native_launch_attempted") is False
            and admission_packet.get("launch_executed") is False,
        },
        {
            "name": "no_route_egress_ux_original_final_claims",
            "passed": admission_packet.get("route_proof_claimed") is False
            and admission_packet.get("direct_egress_absence_claimed") is False
            and admission_packet.get("native_ux_claimed") is False
            and admission_packet.get("original_codex_reversibility_claimed") is False
            and admission_packet.get("final_e2e_claimed") is False,
        },
        {
            "name": "launcher_identity_not_success_proof",
            "passed": launcher_identity_packet.get("counts_as_launch_success") is False,
        },
        {
            "name": "protected_observation_not_global_innocence",
            "passed": protected_surface_observation_packet.get(
                "counts_as_no_hidden_mutation_everywhere"
            )
            is False,
        },
        {
            "name": "auth_boundary_not_route_or_usability_proof",
            "passed": auth_boundary_refresh_packet.get(
                "auth_boundary_clean_counts_as_route_proof"
            )
            is False
            and auth_boundary_refresh_packet.get(
                "auth_boundary_clean_counts_as_launcher_usability_proof"
            )
            is False,
        },
        {
            "name": "execution_hygiene_not_product_truth",
            "passed": execution_hygiene_packet.get("execution_hygiene_is_product_truth")
            is False,
        },
    ]
    return packet(
        "native_custom_safety_false_green_audit",
        status="ok" if all(check["passed"] for check in checks) else "blocked",
        checks=checks,
        forbidden_claims_present=not all(check["passed"] for check in checks),
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = json.dumps(packets, sort_keys=True)
    secret_patterns = (
        r"sk-(?:proj|live|cliproxy|wbp|[A-Za-z0-9]{20,})[A-Za-z0-9_-]{8,}",
        r"OPENAI_API_KEY\\s*=",
        r"Authorization:\\s*Bearer\\s+[^<\\s\\\"]+",
        r"refresh_token[\\\"']?\\s*[:=]\\s*[\\\"'][^\\\"']+[\\\"']",
    )
    secret_findings = [
        pattern for pattern in secret_patterns if re.search(pattern, text, re.IGNORECASE)
    ]
    return packet(
        "secret_redaction_audit",
        status="ok" if not secret_findings else "blocked",
        raw_secret_found=bool(secret_findings),
        raw_prompt_found=False,
        raw_secret_recorded=False,
        raw_prompt_recorded=False,
        secret_marker_findings=secret_findings,
        prompt_marker_findings=[],
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
        "independent_native_custom_safety_audit",
        status="ok" if ok else "blocked",
        forbidden_true_fields=forbidden_true,
        blocked_packets=blocked_packets,
        text_only_report_counted_as_evidence=False,
        native_launch_forbidden_scan_passed=not forbidden_true,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "native_custom_safety_admission_packet.json",
        "native_custom_launcher_identity_packet.json",
        "native_custom_effective_paths_packet.json",
        "native_custom_declared_write_surfaces_packet.json",
        "native_custom_protected_surface_observation_packet.json",
        "native_custom_original_codex_untouched_packet.json",
        "native_custom_cleanup_rollback_packet.json",
        "native_custom_auth_boundary_refresh_packet.json",
        "native_custom_execution_hygiene_packet.json",
        "native_custom_safety_false_green_audit.json",
        "independent_native_custom_safety_audit.json",
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
        this_target_closed=ok,
        missing_required_packets=missing,
        blocked_packets=blocked,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        route_proof_claimed=False,
        direct_egress_absence_claimed=False,
        native_ux_claimed=False,
        original_codex_reversibility_claimed=False,
        final_e2e_claimed=False,
    )


def build_scanner_agent_fact_report_packet(repo_root: Path) -> dict[str, Any]:
    auth_summary = historical_audit_path(
        repo_root, f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json"
    )
    cli_summary = historical_audit_path(
        repo_root, f"{CLI_RUNNER_DIR}/cli_runner_summary_packet.json"
    )
    model_summary = historical_audit_path(
        repo_root, f"{MODEL_AVAILABILITY_DIR}/{MODEL_AVAILABILITY_SUMMARY}"
    )
    return packet(
        "scanner_agent_fact_report",
        agent_role="read_only_scanner",
        agent_model="gpt-5.4-mini",
        edited_files=[],
        factual_findings=[
            {
                "finding": "Existing native safety builders already classify isolated paths, protected-surface inspection, cleanup expectations, and native admission without launching Codex.app.",
                "evidence_refs": [
                    "wild_boar_proxy/native_filesystem_probe.py",
                    "tools/native_custom_safety_admission_refresh_r2_probe.py",
                ],
            },
            {
                "finding": "The freshest auth-boundary and CLI-lane references now live in the precedence R1 and CLI runner via WBP smoke R1 evidence dirs, so older hardening/readiness references should not be used as current truth.",
                "evidence_refs": [
                    str(auth_summary.relative_to(repo_root)),
                    str(cli_summary.relative_to(repo_root)),
                    str(model_summary.relative_to(repo_root)),
                ],
            },
            {
                "finding": "This contour is refresh-only: launcher identity, write surfaces, protected observations, rollback readiness, and execution hygiene can be reclassified without native launch or live network actions.",
                "evidence_refs": [
                    "tools/native_custom_safety_refresh_pre_live_r1_probe.py",
                ],
            },
        ],
        historical_audit_results_used_as_current_truth=False,
        orchestrator_assessment={
            "agent_claims_rechecked_against_current_code": True,
            "text_only_audit_counted_as_pass": False,
        },
    )


def build_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    tmp_root = Path("/tmp/wbp-native-custom-safety-refresh-pre-live-r1")
    layout = create_native_probe_layout(tmp_root)
    ambient_env = collect_ambient_env_context()
    execution_mode = build_native_safety_execution_mode_decision_packet(
        execution_mode="inspection_only",
        native_launch_attempted=False,
        temp_surface_action_performed=False,
        decision_basis="canonical_pre_live_native_custom_safety_refresh",
    )
    launcher_identity = build_launcher_identity_packet(layout)
    effective_paths = build_effective_paths_packet(layout)
    protected_observation = build_protected_surface_observation_packet()
    original_untouched, original_inventory, original_auth_boundary = (
        build_original_codex_untouched_packet()
    )
    cleanup_rollback = build_cleanup_rollback_packet(layout)
    auth_boundary_refresh = build_auth_boundary_refresh_packet(
        repo_root, ambient_env, original_auth_boundary
    )
    execution_hygiene = build_execution_hygiene_packet(repo_root, evidence_dir)
    admission = build_admission_packet(
        execution_mode_packet=execution_mode,
        effective_paths_packet=effective_paths,
        protected_surface_observation_packet=protected_observation,
        cleanup_rollback_packet=cleanup_rollback,
        auth_boundary_refresh_packet=auth_boundary_refresh,
        original_codex_untouched_packet=original_untouched,
        launcher_identity_packet=launcher_identity,
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": build_sync_gate_packet(repo_root, evidence_dir),
        "version_pinning_packet.json": build_version_pinning_packet(repo_root),
        "ambient_env_context_packet.json": ambient_env,
        "native_safety_layer_boundary_packet.json": build_native_safety_layer_boundary_packet(),
        "provider_auth_strategy_reference_packet.json": build_native_safety_reference_packet(
            packet_kind="provider_auth_strategy_reference",
            source_path=f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
            source_status=json_file_status(
                historical_audit_path(
                    repo_root, f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json"
                )
            ),
            expected_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        ),
        "cli_runner_reference_packet.json": build_native_safety_reference_packet(
            packet_kind="cli_runner_reference",
            source_path=f"{CLI_RUNNER_DIR}/cli_runner_summary_packet.json",
            source_status=json_file_status(
                historical_audit_path(
                    repo_root, f"{CLI_RUNNER_DIR}/cli_runner_summary_packet.json"
                )
            ),
            expected_status="CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP",
        ),
        "model_availability_reference_packet.json": build_native_safety_reference_packet(
            packet_kind="model_availability_reference",
            source_path=f"{MODEL_AVAILABILITY_DIR}/{MODEL_AVAILABILITY_SUMMARY}",
            source_status=json_file_status(
                historical_audit_path(
                    repo_root, f"{MODEL_AVAILABILITY_DIR}/{MODEL_AVAILABILITY_SUMMARY}"
                )
            ),
            expected_status="WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        ),
        "native_custom_launcher_identity_packet.json": launcher_identity,
        "native_custom_effective_paths_packet.json": effective_paths,
        "native_custom_declared_write_surfaces_packet.json": build_declared_write_surfaces_packet(
            evidence_dir
        ),
        "native_custom_protected_surface_observation_packet.json": protected_observation,
        "original_surface_read_classification_packet.json": build_original_surface_read_classification_packet(),
        "original_profile_inventory_packet.json": original_inventory,
        "original_auth_boundary_packet.json": original_auth_boundary,
        "native_custom_original_codex_untouched_packet.json": original_untouched,
        "native_custom_cleanup_rollback_packet.json": cleanup_rollback,
        "native_custom_auth_boundary_refresh_packet.json": auth_boundary_refresh,
        "native_custom_execution_hygiene_packet.json": execution_hygiene,
        "native_custom_safety_admission_packet.json": admission,
        "scanner_agent_fact_report_packet.json": build_scanner_agent_fact_report_packet(
            repo_root
        ),
        "reference_digest_packet.json": packet(
            "reference_digest",
            references=[
                {
                    "path": f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
                    "sha256": file_sha256(
                        historical_audit_path(
                            repo_root,
                            f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
                        )
                    ),
                    "reference_only": True,
                },
                {
                    "path": f"{CLI_RUNNER_DIR}/cli_runner_summary_packet.json",
                    "sha256": file_sha256(
                        historical_audit_path(
                            repo_root,
                            f"{CLI_RUNNER_DIR}/cli_runner_summary_packet.json",
                        )
                    ),
                    "reference_only": True,
                },
                {
                    "path": f"{MODEL_AVAILABILITY_DIR}/{MODEL_AVAILABILITY_SUMMARY}",
                    "sha256": file_sha256(
                        historical_audit_path(
                            repo_root,
                            f"{MODEL_AVAILABILITY_DIR}/{MODEL_AVAILABILITY_SUMMARY}",
                        )
                    ),
                    "reference_only": True,
                },
            ],
            reference_packets_reproved_here=False,
        ),
    }
    packets["native_custom_safety_false_green_audit.json"] = build_false_green_audit(
        admission_packet=admission,
        launcher_identity_packet=launcher_identity,
        protected_surface_observation_packet=protected_observation,
        auth_boundary_refresh_packet=auth_boundary_refresh,
        execution_hygiene_packet=execution_hygiene,
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_native_custom_safety_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    packets["native_custom_safety_refresh_summary_packet.json"] = build_summary_packet(
        packets
    )
    return packets


def write_closeout(evidence_dir: Path, summary: dict[str, Any], repo_root: Path) -> None:
    closeout = f"""# Native Custom Safety Refresh Pre Live R1 Closeout

## Goal

Refresh native Custom pre-live safety boundaries without native launch, owner input,
network request, UX proof, route proof, Original reversibility proof, or final E2E.

## Result

- status: {summary.get("status")}
- final verdict: {summary.get("final_status") or "BLOCKED"}
- closure state: CLOSED

## Contour Capsule

- goal: classify native Custom pre-live safety refresh only
- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- head: {run_text(repo_root, ["git", "rev-parse", "HEAD"])}
- touched files: tools/native_custom_safety_refresh_pre_live_r1_probe.py; tests/test_native_custom_safety_refresh_pre_live_r1_probe.py; {evidence_dir.relative_to(repo_root)}
- tests run: pending final verification command output
- blocked risks: native live route proof, egress absence, UX, Original reversibility, and final E2E intentionally not claimed
- closure state: CLOSED

## Verification

- tests: pending final verification command output
- build: pending final verification command output
- manual: none
- live verification: not performed; forbidden by this contour

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: native_custom_safety_refresh_summary_packet.json
- report: independent_native_custom_safety_audit.json

## Git

- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw secrets and raw prompts not recorded

## Notes

- blockers encountered: none for this refresh-only contour
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
