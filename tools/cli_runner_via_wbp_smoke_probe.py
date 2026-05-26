#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate completed evidence for the CLI runner via WBP smoke contour."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.cli_runner_via_wbp import (
    CONTOUR_ID,
    PASS_STATUS,
    PRIMARY_MODEL_ID,
    build_cli_runner_claims_packet,
    build_cli_runner_layer_boundary_packet,
    build_codex_auth_command_config,
    build_false_green_audit_packet,
    build_no_ambient_authority_packet,
    build_trace_acceptance_packet,
    remove_tree,
    sha256_bytes,
    sha256_text,
    validate_cli_runner_contour_packets,
)
from wild_boar_proxy.operator_surface import WbpTraceObserver, clean_env, stat_hash
from wild_boar_proxy.runtime import RuntimePaths, build_launcher_subprocess_env


DEFAULT_EVIDENCE_DIR = (
    REPO_ROOT / "audit_results" / "wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27"
)
DEFAULT_CODEX_BIN = Path("/Applications/Codex.app/Contents/Resources/codex")
DEFAULT_WBP_ENDPOINT = "http://127.0.0.1:8318/v1"
EXPECTED_RESPONSE = "CLI_RUNNER_WBP_OK"
PROMPT = (
    "WBP_CLI_RUNNER_R1_NONCE_2026_05_27: "
    "answer exactly CLI_RUNNER_WBP_OK"
)
CURRENT_CODEX_CONFIG = "/Users/kirillponomarev/.codex/config.toml"
CURRENT_CODEX_AUTH = "/Users/kirillponomarev/.codex/auth.json"
AUTH_STRATEGY_PACKET = (
    REPO_ROOT
    / "audit_results"
    / "wbp_provider_auth_strategy_contract_r1_hardening_2026-05-26"
    / "provider_auth_strategy_packet.json"
)
MODEL_AVAILABILITY_PACKET = (
    REPO_ROOT
    / "audit_results"
    / "wbp_model_availability_smoke_matrix_r1_2026-05-27"
    / "model_availability_matrix.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def run_text(args: list[str], *, timeout: int = 15) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive packet path
        return {
            "status": "error",
            "machine_error_code": type(exc).__name__,
            "stdout_sha256": "",
            "stderr_sha256": "",
            "stdout_len": 0,
            "stderr_len": 0,
        }
    return {
        "exit_code": completed.returncode,
        "stdout_sha256": sha256_text(completed.stdout),
        "stderr_sha256": sha256_text(completed.stderr),
        "stdout_len": len(completed.stdout),
        "stderr_len": len(completed.stderr),
        "stdout_first_line": completed.stdout.splitlines()[0] if completed.stdout else "",
    }


def run_text_output(args: list[str], *, timeout: int = 15) -> str:
    result = run_text(args, timeout=timeout)
    if result.get("exit_code") != 0:
        return ""
    completed = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def git_status_lines() -> list[str]:
    return run_text_output(["git", "status", "--short"]).splitlines()


def historical_quarantine(evidence_dir: Path) -> tuple[list[str], list[str]]:
    relative_evidence_dir = str(evidence_dir.relative_to(REPO_ROOT))
    admitted_current_contour = {
        "wild_boar_proxy/cli_runner.py",
        "wild_boar_proxy/cli_runner_via_wbp.py",
        "tests/test_cli_runner.py",
        "tools/cli_runner_via_wbp_smoke_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined: list[str] = []
    unexpected: list[str] = []
    for line in git_status_lines():
        stripped = line.strip()
        if stripped.startswith(quarantined_prefixes):
            quarantined.append(line)
        elif stripped.startswith(f"?? {relative_evidence_dir}/"):
            continue
        elif any(path in line for path in admitted_current_contour):
            continue
        else:
            unexpected.append(line)
    return quarantined, unexpected


def reference_packet(
    *,
    packet_kind: str,
    source_path: Path,
    expected_status: str = "",
) -> dict[str, Any]:
    payload = read_json(source_path)
    status = str(payload.get("status") or payload.get("target_status") or "")
    failures: list[str] = []
    if not payload:
        failures.append("referenced_packet_missing_or_invalid")
    if expected_status and expected_status not in json.dumps(payload, sort_keys=True):
        failures.append("expected_status_not_found")
    return {
        "contour_id": CONTOUR_ID,
        "packet_kind": packet_kind,
        "created_at_utc": utc_now(),
        "status": "passed" if not failures else "failed",
        "source_packet": str(source_path),
        "source_packet_snapshot": stat_hash(str(source_path)),
        "referenced_status": status,
        "reference_only": True,
        "auth_strategy_reproved_in_this_contour": False,
        "model_availability_reproved_in_this_contour": False,
        "model_availability_expansion_claimed": False,
        "new_model_availability_claims_allowed": False,
        "native_model_availability_claimed": False,
        "validation_failures": failures,
    }


def secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    markers = [
        "sk-",
        "Authorization: Bearer",
        "OPENAI_API_KEY=",
        "OPENROUTER_API_KEY=",
        "WBP_CLI_RUNNER_R1_NONCE_2026_05_27",
        "answer exactly CLI_RUNNER_WBP_OK",
    ]
    findings = [marker for marker in markers if marker in serialized]
    return {
        "contour_id": CONTOUR_ID,
        "packet_kind": "secret_redaction_audit",
        "created_at_utc": utc_now(),
        "status": "failed" if findings else "passed",
        "raw_secret_found": bool(findings),
        "raw_prompt_found": "WBP_CLI_RUNNER_R1_NONCE_2026_05_27" in findings,
        "secret_marker_findings": findings,
        "auth_header_recorded": "Authorization: Bearer" in serialized,
        "checked_packet_count": len(packets),
    }


def independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    blocked = sorted(name for name, packet in packets.items() if packet.get("status") in {"failed", "blocked"})
    validation_failures = validate_cli_runner_contour_packets(packets)
    return {
        "contour_id": CONTOUR_ID,
        "packet_kind": "independent_cli_runner_audit",
        "created_at_utc": utc_now(),
        "status": "failed" if blocked or validation_failures else "passed",
        "blocked_packets": blocked,
        "contour_validation_failures": validation_failures,
        "native_app_claimed": packets.get("cli_runner_smoke_packet.json", {}).get("native_app_claimed") is True,
        "egress_absence_claimed": packets.get("cli_runner_smoke_packet.json", {}).get("direct_egress_absence_claimed") is True,
        "streaming_claimed": packets.get("cli_runner_smoke_packet.json", {}).get("streaming_claimed") is True,
        "tool_loop_claimed": packets.get("cli_runner_smoke_packet.json", {}).get("tool_loop_claimed") is True,
        "text_only_audit_counted_as_pass": False,
    }


def command_warning_classes(stderr: str) -> list[str]:
    warnings: list[str] = []
    if "plugins/featured failed with status 401" in stderr:
        warnings.append("remote_plugin_sync_401")
    if "failed to refresh available models" in stderr:
        warnings.append("model_refresh_warning")
    return warnings


def snapshot_current_codex() -> dict[str, Any]:
    return {
        "current_codex_config": stat_hash(CURRENT_CODEX_CONFIG),
        "current_codex_auth": stat_hash(CURRENT_CODEX_AUTH),
    }


def snapshot_authority_surfaces(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "stable_config": stat_hash(str(paths.stable_config)),
        "stable_runtime_generated_config": stat_hash(
            str(paths.stable_runtime_generated_config_file)
        ),
        "custom_profile_config": stat_hash(str(paths.config_toml)),
        "dynamic_registry_counters_used_as_truth": False,
        "registry_file_classification": "dynamic_runtime_state_not_used_as_pass_fail",
    }


def snapshots_equal(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return before == after


def build_env(paths: RuntimePaths, *, home: Path, codex_home: Path, stamp: Path) -> dict[str, str]:
    env = clean_env()
    runtime_env = build_launcher_subprocess_env(paths)
    for key, value in runtime_env.items():
        if key.startswith("WBP_"):
            env[key] = value
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)
    env["WBP_TOKEN_COMMAND_AUDIT_STAMP_PATH"] = str(stamp)
    env.pop("OPENAI_API_KEY", None)
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env.pop(key, None)
    return env


def run_probe(*, evidence_dir: Path, codex_bin: Path, timeout: int) -> dict[str, Any]:
    evidence_dir = evidence_dir.resolve()
    codex_bin = codex_bin.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    paths = RuntimePaths.from_env()
    auth_command_path = REPO_ROOT / "wbp_codex_auth_command.py"
    temp_root = Path(tempfile.mkdtemp(prefix="wbp-cli-runner-via-wbp-r1-"))
    home = temp_root / "home"
    codex_home = temp_root / "codex-home"
    workdir = temp_root / "work"
    output_file = temp_root / "last_message.txt"
    auth_stamp = temp_root / "auth-command-stamp.txt"
    for path in (home, codex_home, workdir):
        path.mkdir(parents=True, exist_ok=True)

    quarantined, unexpected_dirty = historical_quarantine(evidence_dir)
    packets: dict[str, dict[str, Any]] = {}

    sync_gate_packet = {
        "contour_id": CONTOUR_ID,
        "created_at_utc": utc_now(),
        "status": "passed" if not unexpected_dirty else "failed",
        "repo_root": str(REPO_ROOT),
        "evidence_dir": str(evidence_dir),
        "git_branch": run_text_output(["git", "branch", "--show-current"]),
        "git_head": run_text_output(["git", "rev-parse", "HEAD"]),
        "git_status_short": git_status_lines(),
        "unexpected_dirty_entries": unexpected_dirty,
        "thread_only_master_plan_not_written_to_repo": True,
        "historical_audit_results_used_as_navigation_source": False,
    }
    packets["sync_gate_packet.json"] = sync_gate_packet
    write_json(evidence_dir / "sync_gate_packet.json", sync_gate_packet)
    historical_packet = {
        "contour_id": CONTOUR_ID,
        "packet_kind": "historical_dirt_quarantine",
        "created_at_utc": utc_now(),
        "status": "passed",
        "quarantined_paths": quarantined,
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["historical_dirt_quarantine_packet.json"] = historical_packet
    write_json(evidence_dir / "historical_dirt_quarantine_packet.json", historical_packet)

    layer_boundary_packet = build_cli_runner_layer_boundary_packet()
    packets["cli_runner_layer_boundary_packet.json"] = layer_boundary_packet
    write_json(evidence_dir / "cli_runner_layer_boundary_packet.json", layer_boundary_packet)

    declared_write_surfaces_packet = {
        "contour_id": CONTOUR_ID,
        "packet_kind": "declared_write_surfaces",
        "status": "passed",
        "declared_write_surfaces": [
            str(evidence_dir),
            str(temp_root),
        ],
        "current_codex_config_write_authorized": False,
        "current_codex_auth_write_authorized": False,
        "original_codex_config_mutation_allowed": False,
        "native_launch_attempted": False,
        "codex_cli_runner_allowed": True,
    }
    packets["declared_write_surfaces_packet.json"] = declared_write_surfaces_packet
    write_json(
        evidence_dir / "declared_write_surfaces_packet.json",
        declared_write_surfaces_packet,
    )

    version_pinning_packet = {
        "contour_id": CONTOUR_ID,
        "created_at_utc": utc_now(),
        "codex_cli_path": str(codex_bin),
        "codex_cli_version": run_text([str(codex_bin), "--version"]).get(
            "stdout_first_line", ""
        ),
        "wbp_git_commit": run_text(["git", "rev-parse", "HEAD"]).get(
            "stdout_first_line", ""
        ),
        "provider_endpoint": DEFAULT_WBP_ENDPOINT,
        "provider_endpoint_version_status": "local_wbp_endpoint_configured",
        "model_catalog_schema_version": "not_used_by_this_contour",
        "adapter_matrix_version": "not_used_by_this_contour",
    }
    packets["version_pinning_packet.json"] = version_pinning_packet
    write_json(evidence_dir / "version_pinning_packet.json", version_pinning_packet)

    original_before = snapshot_current_codex()
    authority_before = snapshot_authority_surfaces(paths)
    write_json(
        evidence_dir / "current_codex_targeted_surface_before.json",
        original_before,
    )
    write_json(evidence_dir / "route_account_authority_before.json", authority_before)

    env_packet: dict[str, Any] = {}
    trace_acceptance_packet: dict[str, Any] = {}
    claims_packet: dict[str, Any] = {}
    command_packet: dict[str, Any] = {}
    cleanup_packet: dict[str, Any] = {}
    original_integrity_packet: dict[str, Any] = {}
    false_green_audit: dict[str, Any] = {}
    exit_status = "failed"
    machine_error_code = "PROBE_NOT_COMPLETED"
    try:
        with WbpTraceObserver(downstream_endpoint=DEFAULT_WBP_ENDPOINT) as trace:
            config_path = codex_home / "config.toml"
            config_path.write_text(
                build_codex_auth_command_config(
                    base_url=trace.listen_endpoint,
                    auth_command_path=str(auth_command_path),
                    model_id=PRIMARY_MODEL_ID,
                )
            )
            env = build_env(paths, home=home, codex_home=codex_home, stamp=auth_stamp)
            env_packet = build_no_ambient_authority_packet(
                env=env,
                home=home,
                codex_home=codex_home,
                auth_command_path=auth_command_path,
            )
            packets["no_ambient_authority_packet.json"] = env_packet
            write_json(evidence_dir / "no_ambient_authority_packet.json", env_packet)
            auth_contract_packet = {
                "contour_id": CONTOUR_ID,
                "selected_strategy": "auth.command",
                "auth_command_path": str(auth_command_path),
                "bounded_bearer_fallback_selected": False,
                "file_auth_selected": False,
                "current_codex_auth_json_used_as_execution_input": False,
                "auth_command_runtime_env_is_server_owned": True,
                "raw_token_recorded": False,
                "raw_auth_header_recorded": False,
            }
            write_json(evidence_dir / "cli_runner_auth_command_contract_packet.json", auth_contract_packet)
            packets["provider_auth_strategy_reference_packet.json"] = reference_packet(
                packet_kind="provider_auth_strategy_reference",
                source_path=AUTH_STRATEGY_PACKET,
                expected_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
            )
            write_json(
                evidence_dir / "provider_auth_strategy_reference_packet.json",
                packets["provider_auth_strategy_reference_packet.json"],
            )
            packets["model_availability_reference_packet.json"] = reference_packet(
                packet_kind="model_availability_reference",
                source_path=MODEL_AVAILABILITY_PACKET,
                expected_status="WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
            )
            packets["model_availability_reference_packet.json"].update(
                {
                    "model_id": PRIMARY_MODEL_ID,
                    "claim_level_cannot_exceed_reference": True,
                    "model_availability_reproved_in_this_contour": False,
                    "new_model_availability_claims_allowed": False,
                }
            )
            write_json(
                evidence_dir / "model_availability_reference_packet.json",
                packets["model_availability_reference_packet.json"],
            )
            admission_packet = {
                "contour_id": CONTOUR_ID,
                "packet_kind": "cli_runner_admission",
                "created_at_utc": utc_now(),
                "status": "passed" if env_packet.get("status") == "passed" else "failed",
                "runner_command_path": str(codex_bin),
                "runner_command_path_repo_owned": False,
                "runner_command_path_version_pinned": True,
                "selected_model_id": PRIMARY_MODEL_ID,
                "model_availability_reference_only": True,
                "native_launch_allowed": False,
                "route_account_mutation_allowed": False,
            }
            packets["cli_runner_admission_packet.json"] = admission_packet
            write_json(evidence_dir / "cli_runner_admission_packet.json", admission_packet)

            started_at = utc_now()
            completed = subprocess.run(
                [
                    str(codex_bin),
                    "exec",
                    "--skip-git-repo-check",
                    "--ephemeral",
                    "--ignore-rules",
                    "--sandbox",
                    "read-only",
                    "-C",
                    str(workdir),
                    "--json",
                    "-o",
                    str(output_file),
                    "-",
                ],
                input=PROMPT,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
                env=env,
            )
            completed_at = utc_now()
            trace_packet = trace.packet()
            trace_acceptance_packet = build_trace_acceptance_packet(trace_packet)
            packets["cli_runner_route_trace_packet.json"] = trace_acceptance_packet
            write_json(evidence_dir / "cli_runner_route_trace_packet.json", trace_acceptance_packet)

            last_message_bytes = output_file.read_bytes() if output_file.exists() else b""
            response_match_observed = (
                last_message_bytes.decode("utf-8", errors="replace").strip()
                == EXPECTED_RESPONSE
            )
            auth_command_invoked = auth_stamp.exists()
            command_packet = {
                "contour_id": CONTOUR_ID,
                "packet_kind": "cli_runner_command",
                "started_at_utc": started_at,
                "completed_at_utc": completed_at,
                "status": "passed" if completed.returncode == 0 else "failed",
                "exit_code": completed.returncode,
                "command_kind": "codex_exec_json_stdin_prompt",
                "command_uses_stdin_dash": True,
                "command_json_mode": True,
                "stdin_prompt_sha256": sha256_text(PROMPT),
                "stdin_prompt_len": len(PROMPT),
                "raw_prompt_recorded": False,
                "stdout_sha256": sha256_text(completed.stdout),
                "stderr_sha256": sha256_text(completed.stderr),
                "stdout_len": len(completed.stdout),
                "stderr_len": len(completed.stderr),
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "warning_classes": command_warning_classes(completed.stderr),
                "last_message_sha256": sha256_bytes(last_message_bytes),
                "last_message_len": len(last_message_bytes),
                "last_message_raw_recorded": False,
                "expected_response_match_observed": response_match_observed,
                "auth_command_invoked": auth_command_invoked,
                "auth_command_stamp_raw_recorded": False,
            }
            packets["cli_runner_command_packet.json"] = command_packet
            write_json(evidence_dir / "cli_runner_command_packet.json", command_packet)
            response_hash_packet = {
                "contour_id": CONTOUR_ID,
                "packet_kind": "cli_runner_response_hash",
                "created_at_utc": utc_now(),
                "status": "passed" if last_message_bytes else "failed",
                "response_exists": bool(last_message_bytes),
                "response_sha256": sha256_bytes(last_message_bytes),
                "response_len": len(last_message_bytes),
                "response_hash_recorded_is_semantic_quality": False,
                "raw_response_body_recorded": False,
                "prompt_sha256": sha256_text(PROMPT),
                "raw_prompt_recorded": False,
                "auth_header_recorded": False,
                "raw_upstream_secret_recorded": False,
                "response_accepted_by_codex_app": False,
            }
            packets["cli_runner_response_hash_packet.json"] = response_hash_packet
            write_json(evidence_dir / "cli_runner_response_hash_packet.json", response_hash_packet)
            claims_packet = build_cli_runner_claims_packet(
                probe_status="passed" if completed.returncode == 0 else "failed",
                model_id=PRIMARY_MODEL_ID,
                response_match_observed=response_match_observed,
                auth_command_invoked=auth_command_invoked,
                trace_acceptance_packet=trace_acceptance_packet,
            )
            packets["cli_runner_smoke_packet.json"] = claims_packet
            write_json(evidence_dir / "cli_runner_smoke_packet.json", claims_packet)
            machine_error_code = "OK" if claims_packet["status"] == "passed" else "CLI_RUNNER_SMOKE_FAILED"
            exit_status = claims_packet["status"]
    finally:
        cleanup_packet = remove_tree(temp_root)
        write_json(evidence_dir / "cli_runner_cleanup_packet.json", cleanup_packet)
        original_after = snapshot_current_codex()
        authority_after = snapshot_authority_surfaces(paths)
        write_json(evidence_dir / "current_codex_targeted_surface_after.json", original_after)
        write_json(evidence_dir / "route_account_authority_after.json", authority_after)
        original_integrity_packet = {
            "contour_id": CONTOUR_ID,
            "status": "passed" if snapshots_equal(original_before, original_after) else "failed",
            "current_codex_config_auth_unchanged": snapshots_equal(original_before, original_after),
            "current_codex_auth_json_used_as_execution_input": False,
            "before_packet": "current_codex_targeted_surface_before.json",
            "after_packet": "current_codex_targeted_surface_after.json",
        }
        write_json(
            evidence_dir / "cli_runner_original_surface_integrity_packet.json",
            original_integrity_packet,
        )
        route_guard_packet = {
            "contour_id": CONTOUR_ID,
            "packet_kind": "route_account_mutation_guard",
            "status": "passed" if snapshots_equal(authority_before, authority_after) else "failed",
            "route_account_authority_surfaces_unchanged": snapshots_equal(
                authority_before, authority_after
            ),
            "dynamic_registry_counters_used_as_truth": False,
            "active_route_or_account_mutation_claimed": False,
        }
        packets["route_account_mutation_guard_packet.json"] = route_guard_packet
        write_json(evidence_dir / "route_account_mutation_guard_packet.json", route_guard_packet)

    false_green_audit = build_false_green_audit_packet(
        layer_boundary_packet=layer_boundary_packet,
        env_packet=env_packet,
        trace_packet=trace_acceptance_packet,
        claims_packet=claims_packet,
        original_integrity_passed=original_integrity_packet.get("status") == "passed",
        cleanup_passed=cleanup_packet.get("status") == "passed",
    )
    packets["cli_runner_false_green_audit.json"] = false_green_audit
    packets["secret_redaction_audit.json"] = secret_redaction_audit(packets)
    packets["verification_results_packet.json"] = {
        "contour_id": CONTOUR_ID,
        "packet_kind": "verification_results",
        "created_at_utc": utc_now(),
        "status": "passed",
        "probe_execution_status": exit_status,
        "final_manual_verification_packet_may_extend_this": True,
        "native_launch_attempted": False,
        "codex_cli_runner_attempted": True,
    }
    packets["independent_cli_runner_audit.json"] = {
        "contour_id": CONTOUR_ID,
        "packet_kind": "independent_cli_runner_audit",
        "created_at_utc": utc_now(),
        "status": "pending",
        "placeholder_for_self_validation_only": True,
    }
    packets["independent_cli_runner_audit.json"] = independent_audit(packets)
    write_json(evidence_dir / "secret_redaction_audit.json", packets["secret_redaction_audit.json"])
    write_json(evidence_dir / "verification_results_packet.json", packets["verification_results_packet.json"])
    write_json(evidence_dir / "independent_cli_runner_audit.json", packets["independent_cli_runner_audit.json"])
    contour_failures = validate_cli_runner_contour_packets(packets)
    false_green_audit = {
        **false_green_audit,
        "status": "failed" if false_green_audit.get("status") != "passed" or contour_failures else "passed",
        "contour_validation_failures": contour_failures,
    }
    packets["cli_runner_false_green_audit.json"] = false_green_audit
    write_json(evidence_dir / "cli_runner_false_green_audit.json", false_green_audit)

    closeout_status = (
        "passed"
        if exit_status == "passed"
        and false_green_audit.get("status") == "passed"
        and packets["secret_redaction_audit.json"].get("status") == "passed"
        and packets["independent_cli_runner_audit.json"].get("status") == "passed"
        else "failed"
    )
    closeout = {
        "contour_id": CONTOUR_ID,
        "status": closeout_status,
        "pass_status": PASS_STATUS if closeout_status == "passed" else "",
        "machine_error_code": machine_error_code,
        "completed_at_utc": utc_now(),
        "evidence_dir": str(evidence_dir),
        "raw_prompt_recorded": False,
        "raw_token_recorded": False,
        "native_app_claimed": False,
        "original_codex_lane_claimed": False,
        "direct_egress_absence_claimed": False,
        "streaming_claimed": False,
        "tool_loop_claimed": False,
        "final_e2e_claimed": False,
    }
    write_json(evidence_dir / "cli_runner_closeout_packet.json", closeout)
    return closeout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--codex-bin", default=str(DEFAULT_CODEX_BIN))
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    closeout = run_probe(
        evidence_dir=Path(args.evidence_dir),
        codex_bin=Path(args.codex_bin),
        timeout=args.timeout,
    )
    sys.stdout.write(json.dumps(closeout, indent=2, sort_keys=True) + "\n")
    return 0 if closeout.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
