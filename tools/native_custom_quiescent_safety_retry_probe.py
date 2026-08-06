#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run prelaunch gates for the native Custom quiescent safety retry contour."""

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
    build_owner_action_boundary_packet,
    build_protected_surface_read_classification_packet,
    build_quiescent_retry_blocker_packet,
    build_quiescent_retry_launch_admission_packet,
    classify_host_context,
    classify_quiescent_current_codex_precondition,
    collect_codex_process_inventory,
    json_write,
    run_idle_baseline_window,
    summarize_idle_baseline_windows,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
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
            check=True,
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
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
            )
        )
    ]
    admitted_current_contour = [
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_quiescent_safety_retry_probe.py",
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="native-custom-quiescent-safety-retry-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--sleep-seconds", type=float, default=3.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    sync_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": _run(repo_root, ["git", "status", "--short"]).splitlines(),
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
        "master_plan_written_to_repo": False,
    }
    dirt_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "quarantine_classification": "out_of_scope_historical_residue",
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    version_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "status": "ok",
        "codex_cli_version": _run(repo_root, ["codex", "--version"], check=False),
        "codex_cli_path": _run(repo_root, ["which", "codex"], check=False),
        "codex_app_path": "/Applications/Codex.app",
        "codex_app_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
            check=False,
        ),
        "codex_app_bundle_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
            check=False,
        ),
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
    }
    owner_boundary = build_owner_action_boundary_packet()
    inventory = collect_codex_process_inventory(
        custom_user_data_dir="/tmp/nonexistent-custom-user-data"
    )
    precondition = classify_quiescent_current_codex_precondition(inventory)
    host_context = classify_host_context(_host_process_chain())
    declared_write_surfaces = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": [
            "fresh evidence directory only",
            "server-owned isolated temp Custom profile under /tmp/wbp-native-fs-* if launch admitted",
            "server-owned isolated CODEX_HOME under /tmp/wbp-native-fs-* if launch admitted",
            "server-owned isolated user-data-dir under /tmp/wbp-native-fs-* if launch admitted",
        ],
        "protected_surfaces_write_allowed": False,
        "original_codex_bundle_write_allowed": False,
        "original_codex_profile_write_allowed": False,
    }
    protected_read = build_protected_surface_read_classification_packet()

    idle_summary = None
    if host_context.get("status") == "ok" and precondition.get("status") == "ok":
        idle_1 = run_idle_baseline_window(sleep_seconds=args.sleep_seconds)
        idle_2 = run_idle_baseline_window(sleep_seconds=args.sleep_seconds)
        idle_summary = summarize_idle_baseline_windows([idle_1, idle_2])
        json_write(evidence_dir / "pre_custom_idle_window_1.json", idle_1)
        json_write(evidence_dir / "pre_custom_idle_window_2.json", idle_2)
    else:
        idle_summary = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "pre_custom_idle_stability",
            "status": "blocked",
            "reason_class": "PRELAUNCH_GATE_BLOCKED_BEFORE_IDLE_STABILITY",
            "final_verdict": "PRELAUNCH_GATE_BLOCKED_BEFORE_IDLE_STABILITY",
            "idle_windows_attempted": False,
            "blocked_by_host_context": host_context.get("status") != "ok",
            "blocked_by_quiescent_precondition": precondition.get("status") != "ok",
        }

    admission = build_quiescent_retry_launch_admission_packet(
        host_context_packet=host_context,
        owner_action_boundary_packet=owner_boundary,
        quiescent_precondition_packet=precondition,
        idle_stability_packet=idle_summary,
        declared_write_surfaces_packet=declared_write_surfaces,
        protected_surface_read_packet=protected_read,
    )
    blocker = build_quiescent_retry_blocker_packet(
        launch_admission_packet=admission,
        host_context_packet=host_context,
        quiescent_precondition_packet=precondition,
        idle_stability_packet=idle_summary,
    )
    auth_reference = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "auth_strategy_reference",
        "status": "ok",
        "referenced_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "referenced_packet": str(
            repo_root
            / "audit_results/wbp_provider_auth_strategy_contract_2026-05-26/provider_auth_strategy_packet.json"
        ),
        "referenced_packet_status": _json_file_status(
            repo_root
            / "audit_results/wbp_provider_auth_strategy_contract_2026-05-26/provider_auth_strategy_packet.json"
        ),
        "auth_strategy_reproved_in_this_contour": False,
    }
    model_reference = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "model_availability_reference",
        "status": "ok",
        "referenced_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        "referenced_packet": str(
            repo_root
            / "audit_results/wbp_model_availability_smoke_matrix_2026-05-26/model_availability_matrix.json"
        ),
        "referenced_packet_status": _json_file_status(
            repo_root
            / "audit_results/wbp_model_availability_smoke_matrix_2026-05-26/model_availability_matrix.json"
        ),
        "model_availability_reproved_in_this_contour": False,
    }
    allowed_claims = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "quiescent_retry_allowed_claims_matrix",
        "status": "ok",
        "allowed_claims": [
            "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS only if launch admitted and protected surfaces remain unchanged",
            "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_HOSTED_EXECUTOR_CONTEXT",
            "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_NON_QUIESCENT_CURRENT_CODEX",
            "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_IDLE_PROTECTED_SURFACE_DRIFT",
        ],
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
        "model_availability_reproof_allowed": False,
    }
    false_green_audit = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "quiescent_retry_false_green_audit",
        "status": "ok",
        "checks": [
            {"name": "native_launch_not_attempted_before_prelaunch_gates", "passed": not admission["native_launch_admitted"] and not admission["native_launch_attempted"]},
            {"name": "route_claim_not_allowed", "passed": not admission["route_claim_allowed"]},
            {"name": "ux_claim_not_allowed", "passed": not admission["ux_claim_allowed"]},
            {"name": "egress_claim_not_allowed", "passed": not admission["egress_claim_allowed"]},
            {"name": "auth_strategy_not_reproved", "passed": not auth_reference["auth_strategy_reproved_in_this_contour"]},
            {"name": "model_availability_not_reproved", "passed": not model_reference["model_availability_reproved_in_this_contour"]},
        ],
        "forbidden_claims_present": False,
    }

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": version_packet,
        "host_context_packet.json": host_context,
        "owner_action_boundary_packet.json": owner_boundary,
        "current_codex_running_state_initial.json": inventory,
        "quiescent_current_codex_precondition_packet.json": precondition,
        "pre_custom_idle_stability_packet.json": idle_summary,
        "launch_admission_packet.json": admission,
        "declared_write_surfaces_packet.json": declared_write_surfaces,
        "protected_surface_read_classification_packet.json": protected_read,
        "auth_strategy_reference_packet.json": auth_reference,
        "model_availability_reference_packet.json": model_reference,
        "allowed_claims_matrix.json": allowed_claims,
        "native_safety_false_green_audit.json": false_green_audit,
        "native_safety_blocker_packet.json": blocker,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(blocker, indent=2, sort_keys=True))
    return 0 if blocker["target_status_achieved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
