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
)
from wild_boar_proxy.operator_surface import WbpTraceObserver, clean_env, stat_hash
from wild_boar_proxy.runtime import RuntimePaths, build_launcher_subprocess_env


DEFAULT_EVIDENCE_DIR = (
    REPO_ROOT / "audit_results" / "wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-26"
)
DEFAULT_CODEX_BIN = Path("/Applications/Codex.app/Contents/Resources/codex")
DEFAULT_WBP_ENDPOINT = "http://127.0.0.1:8318/v1"
EXPECTED_RESPONSE = "CLI_RUNNER_WBP_OK"
PROMPT = (
    "WBP_CLI_RUNNER_R1_NONCE_2026_05_26: "
    "answer exactly CLI_RUNNER_WBP_OK"
)
CURRENT_CODEX_CONFIG = "/Users/kirillponomarev/.codex/config.toml"
CURRENT_CODEX_AUTH = "/Users/kirillponomarev/.codex/auth.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


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

    sync_gate_packet = {
        "contour_id": CONTOUR_ID,
        "created_at_utc": utc_now(),
        "status": "started",
        "repo_root": str(REPO_ROOT),
        "evidence_dir": str(evidence_dir),
        "thread_only_master_plan_not_written_to_repo": True,
        "historical_audit_results_used_as_navigation_source": False,
    }
    write_json(evidence_dir / "sync_gate_packet.json", sync_gate_packet)

    layer_boundary_packet = build_cli_runner_layer_boundary_packet()
    write_json(evidence_dir / "cli_runner_layer_boundary_packet.json", layer_boundary_packet)

    declared_write_surfaces_packet = {
        "contour_id": CONTOUR_ID,
        "declared_write_surfaces": [
            str(evidence_dir),
            str(temp_root),
        ],
        "current_codex_config_write_authorized": False,
        "current_codex_auth_write_authorized": False,
        "original_codex_config_mutation_allowed": False,
    }
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
            write_json(evidence_dir / "cli_runner_env_no_ambient_authority_packet.json", env_packet)
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
            write_json(evidence_dir / "cli_runner_trace_packet.json", trace_acceptance_packet)

            last_message_bytes = output_file.read_bytes() if output_file.exists() else b""
            response_match_observed = (
                last_message_bytes.decode("utf-8", errors="replace").strip()
                == EXPECTED_RESPONSE
            )
            auth_command_invoked = auth_stamp.exists()
            command_packet = {
                "contour_id": CONTOUR_ID,
                "started_at_utc": started_at,
                "completed_at_utc": completed_at,
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
            write_json(
                evidence_dir / "cli_runner_prompt_response_hash_packet.json",
                command_packet,
            )
            claims_packet = build_cli_runner_claims_packet(
                probe_status="passed" if completed.returncode == 0 else "failed",
                model_id=PRIMARY_MODEL_ID,
                response_match_observed=response_match_observed,
                auth_command_invoked=auth_command_invoked,
                trace_acceptance_packet=trace_acceptance_packet,
            )
            write_json(evidence_dir / "cli_runner_claims_packet.json", claims_packet)
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
            "status": "passed" if snapshots_equal(authority_before, authority_after) else "failed",
            "route_account_authority_surfaces_unchanged": snapshots_equal(
                authority_before, authority_after
            ),
            "dynamic_registry_counters_used_as_truth": False,
            "active_route_or_account_mutation_claimed": False,
        }
        write_json(evidence_dir / "cli_runner_route_account_guard_packet.json", route_guard_packet)

    model_reference_packet = {
        "contour_id": CONTOUR_ID,
        "model_id": PRIMARY_MODEL_ID,
        "reference_only": True,
        "source_packet": str(
            REPO_ROOT
            / "audit_results"
            / "wbp_model_availability_direct_only_r1_2026-05-26"
            / "model_availability_matrix.json"
        ),
        "source_packet_snapshot": stat_hash(
            str(
                REPO_ROOT
                / "audit_results"
                / "wbp_model_availability_direct_only_r1_2026-05-26"
                / "model_availability_matrix.json"
            )
        ),
        "model_availability_expansion_claimed": False,
        "native_model_availability_claimed": False,
    }
    write_json(evidence_dir / "cli_runner_model_reference_packet.json", model_reference_packet)

    false_green_audit = build_false_green_audit_packet(
        layer_boundary_packet=layer_boundary_packet,
        env_packet=env_packet,
        trace_packet=trace_acceptance_packet,
        claims_packet=claims_packet,
        original_integrity_passed=original_integrity_packet.get("status") == "passed",
        cleanup_passed=cleanup_packet.get("status") == "passed",
    )
    write_json(evidence_dir / "cli_runner_false_green_audit.json", false_green_audit)

    closeout_status = (
        "passed"
        if exit_status == "passed"
        and false_green_audit.get("status") == "passed"
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
