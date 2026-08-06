#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Native Custom safety/admission R1 evidence without launching Codex.app."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    build_protected_surface_read_classification_packet,
    classify_keychain_observation,
    collect_ambient_env_context,
    collect_codex_process_inventory,
    create_native_probe_layout,
    json_write,
    scan_protected_surfaces,
    validate_native_safety_admission_contour_packets,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _json_file_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_json"
    return "present"


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_safety_admission_refresh_r1_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _host_process_chain() -> list[dict[str, Any]]:
    pid = os.getpid()
    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    while pid and pid not in seen:
        seen.add(pid)
        process = subprocess.run(
            ["ps", "-o", "pid=,ppid=,command=", "-p", str(pid)],
            text=True,
            capture_output=True,
            check=False,
        )
        line = process.stdout.strip()
        if not line:
            break
        parts = line.split(None, 2)
        if len(parts) < 3:
            break
        cur_pid = int(parts[0])
        ppid = int(parts[1])
        command = parts[2]
        chain.append({"pid": cur_pid, "ppid": ppid, "command": command})
        pid = ppid
    return chain


def _base_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": _run(repo_root, ["git", "status", "--short"]).splitlines(),
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "master_plan_written_to_repo": False,
        },
        "historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "quarantine_classification": "out_of_scope_historical_residue",
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": ["fresh evidence directory only"],
            "native_launch_allowed": False,
            "native_launch_attempted": False,
            "temp_surface_action_allowed": False,
            "temp_surface_action_performed": False,
            "protected_surfaces_write_allowed": False,
            "original_codex_bundle_write_allowed": False,
            "original_codex_profile_write_allowed": False,
            "route_account_model_provider_mutation_allowed": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "codex_cli_version": _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "codex_app_bundle_version": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleVersion",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
        "current_runtime_state_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "current_runtime_state",
            "status": "ok",
            "host_process_chain": _host_process_chain(),
            "native_launch_attempted": False,
            "live_network_capture_attempted": False,
            "runtime_mutation_performed": False,
        },
    }


def _reference_packets(repo_root: Path) -> dict[str, dict[str, Any]]:
    auth_path = (
        repo_root
        / "audit_results/wbp_provider_auth_strategy_contract_r1_hardening_2026-05-26/provider_auth_strategy_packet.json"
    )
    model_path = (
        repo_root
        / "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_matrix.json"
    )
    cli_path = (
        repo_root
        / "audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/cli_runner_closeout_packet.json"
    )
    return {
        "provider_auth_strategy_reference_packet.json": build_native_safety_reference_packet(
            packet_kind="provider_auth_strategy_reference",
            source_path=str(auth_path),
            source_status=_json_file_status(auth_path),
            expected_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        ),
        "model_availability_reference_packet.json": build_native_safety_reference_packet(
            packet_kind="model_availability_reference",
            source_path=str(model_path),
            source_status=_json_file_status(model_path),
            expected_status="WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        ),
        "cli_runner_reference_packet.json": build_native_safety_reference_packet(
            packet_kind="cli_runner_reference",
            source_path=str(cli_path),
            source_status=_json_file_status(cli_path),
            expected_status="CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP",
        ),
    }


def build_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    planned_tmp_root = Path("/tmp/wbp-native-custom-safety-admission-r1")
    layout = create_native_probe_layout(planned_tmp_root)
    packets = _base_packets(repo_root, evidence_dir)
    packets.update(_reference_packets(repo_root))

    ambient_env = collect_ambient_env_context()
    execution_mode = build_native_safety_execution_mode_decision_packet(
        execution_mode="inspection_only",
        native_launch_attempted=False,
        temp_surface_action_performed=False,
        decision_basis="canonical_platform_safe_work_before_live_native_egress",
    )
    protected_read = build_protected_surface_read_classification_packet()
    protected_before = scan_protected_surfaces()
    process_before = collect_codex_process_inventory(
        custom_user_data_dir=str(layout.custom_user_data_dir)
    )
    no_ambient = build_no_ambient_authority_safety_packet(
        ambient_env_packet=ambient_env,
        native_launch_attempted=False,
    )
    isolated_codex_home = build_native_safety_isolated_path_packet(
        packet_kind="isolated_codex_home",
        tmp_root=planned_tmp_root,
        path=layout.custom_codex_home,
        path_role="CODEX_HOME",
        execution_mode="inspection_only",
        materialized=False,
    )
    isolated_user_data_dir = build_native_safety_isolated_path_packet(
        packet_kind="isolated_user_data_dir",
        tmp_root=planned_tmp_root,
        path=layout.custom_user_data_dir,
        path_role="electron_user_data_dir",
        execution_mode="inspection_only",
        materialized=False,
    )
    cleanup = build_native_cleanup_rollback_expectation_packet(
        tmp_root=planned_tmp_root,
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
    keychain = classify_keychain_observation(machine_prompt_observed=False)
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
    false_green = build_native_safety_admission_false_green_audit(
        native_custom_admission_packet=admission,
        auth_strategy_reference_packet=packets["provider_auth_strategy_reference_packet.json"],
        model_availability_reference_packet=packets["model_availability_reference_packet.json"],
        cli_runner_reference_packet=packets["cli_runner_reference_packet.json"],
    )

    packets.update(
        {
            "ambient_env_context_packet.json": ambient_env,
            "execution_mode_decision_packet.json": execution_mode,
            "current_codex_running_state_before.json": process_before,
            "protected_surface_read_classification_packet.json": protected_read,
            "protected_surface_recursive_before.json": protected_before,
            "native_safety_layer_boundary_packet.json": build_native_safety_layer_boundary_packet(),
            "isolated_codex_home_packet.json": isolated_codex_home,
            "isolated_user_data_dir_packet.json": isolated_user_data_dir,
            "no_ambient_authority_packet.json": no_ambient,
            "cleanup_rollback_expectation_packet.json": cleanup,
            "keychain_observation_packet.json": keychain,
            "native_integrity_packet.json": integrity,
            "native_custom_admission_packet.json": admission,
            "native_safety_false_green_audit.json": false_green,
        }
    )
    validation_packets = {
        name: packet
        for name, packet in packets.items()
        if name.endswith(".json") and isinstance(packet, dict)
    }
    packets["independent_native_safety_audit.json"] = (
        validate_native_safety_admission_contour_packets(validation_packets)
    )
    failed_packets = [
        name
        for name, packet in packets.items()
        if isinstance(packet, dict) and packet.get("status") not in {"ok", None}
    ]
    packets["native_safety_admission_result_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_safety_admission_result",
        "status": "ok" if not failed_packets else "blocked",
        "allowed_final_claim": (
            "NATIVE_CUSTOM_SAFETY_ADMISSION_INSPECTION_ONLY_CLASSIFIED"
            if not failed_packets
            else ""
        ),
        "failed_packets": failed_packets,
        "execution_mode": "inspection_only",
        "native_launch_attempted": False,
        "native_route_proof_claimed": False,
        "native_ux_claimed": False,
        "direct_egress_absence_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default="audit_results/wbp_native_custom_safety_admission_refresh_r1_2026-05-27",
    )
    args = parser.parse_args()

    repo_root = ROOT
    evidence_dir = (repo_root / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root, evidence_dir)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    result = packets["native_safety_admission_result_packet.json"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
