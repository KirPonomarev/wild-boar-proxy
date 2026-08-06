#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Phase A handoff evidence for detached native Custom egress proof."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_detached_egress_command_admission_packet,
    build_detached_egress_command_hash_packet,
    build_detached_egress_execution_command_packet,
    build_detached_egress_future_result_import_contract_packet,
    build_detached_egress_future_result_required_packets_packet,
    build_detached_egress_handoff_false_green_audit,
    build_detached_egress_owner_action_boundary_packet,
    build_detached_egress_quiescent_requirement_packet,
    build_native_direct_egress_capability_packet,
    build_network_claim_limits_packet,
    json_write,
)


def _observer_tool_path(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    canonical = Path(f"/usr/sbin/{name}")
    return str(canonical) if canonical.exists() else ""


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


def _safe_run(repo_root: Path, command: list[str]) -> str:
    try:
        return _run(repo_root, command)
    except OSError as exc:
        return f"unavailable: {exc}"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool,
) -> tuple[list[str], list[str], list[str]]:
    if skip_git:
        return [], [], []
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    admitted_current_contour = [
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_detached_egress_execution_handoff_probe.py",
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return status_lines, quarantined, unexpected_dirty


def _version_packet(repo_root: Path, *, skip_git: bool) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "status": "ok",
        "codex_cli_version": _safe_run(repo_root, ["codex", "--version"]),
        "codex_cli_path": _safe_run(repo_root, ["which", "codex"]),
        "codex_app_path": "/Applications/Codex.app",
        "codex_app_version": _safe_run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        "codex_app_bundle_version": _safe_run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        "wbp_git_commit": "skipped" if skip_git else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
    }


def _current_wbp_status_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "current_wbp_status",
        "status": "ok",
        "live_wbp_route_verified_in_this_contour": False,
        "wbp_required_for_future_detached_run": True,
        "phase_a_counts_as_wbp_runtime_proof": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "source_path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "invalid_json",
            "source_path": str(path),
            "error": str(exc),
        }


def _safety_admission_reference_packet(path: Path) -> dict[str, Any]:
    packet = _read_json(path)
    ok = (
        packet.get("status") == "ok"
        and packet.get("allowed_final_claim")
        == "NATIVE_CUSTOM_SAFETY_ADMISSION_INSPECTION_ONLY_CLASSIFIED"
        and packet.get("native_launch_attempted") is False
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "safety_admission_reference",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "SAFETY_ADMISSION_REFERENCE_NOT_OK",
        "source_path": str(path),
        "source_status": packet.get("status", "missing"),
        "source_allowed_final_claim": packet.get("allowed_final_claim", ""),
        "source_native_launch_attempted": packet.get("native_launch_attempted"),
        "reference_only": True,
        "counts_as_native_launch_proof": False,
        "counts_as_network_claim": False,
    }


def _independent_handoff_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "safety_admission_reference_packet.json",
        "current_wbp_status_packet.json",
        "observer_capability_packet.json",
        "detached_egress_execution_command_packet.json",
        "detached_egress_command_hash_packet.json",
        "detached_egress_command_admission_packet.json",
        "detached_egress_owner_action_boundary_packet.json",
        "quiescent_precondition_requirement_packet.json",
        "future_result_required_packets_packet.json",
        "future_result_import_contract_packet.json",
        "network_claim_limits_packet.json",
        "handoff_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    false_green = packets.get("handoff_false_green_audit.json", {})
    command = packets.get("detached_egress_execution_command_packet.json", {})
    forbidden_claim = any(
        packet.get(key) is True
        for packet in packets.values()
        for key in (
            "native_launch_attempted",
            "live_network_capture_attempted",
            "direct_egress_absence_proven",
            "api_openai_com_absence_proven",
            "final_e2e_proven",
            "external_result_imported",
        )
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_detached_egress_handoff_audit",
        "status": "ok"
        if not missing
        and false_green.get("status") == "ok"
        and packets.get("safety_admission_reference_packet.json", {}).get("status")
        == "ok"
        and not forbidden_claim
        and "native_custom_direct_egress_classification_probe.py" in command.get("target_tool", "")
        else "blocked",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "false_green_audit_status": false_green.get("status"),
        "command_targets_live_direct_egress_probe": (
            "native_custom_direct_egress_classification_probe.py"
            in command.get("target_tool", "")
        ),
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "external_result_imported": False,
        "direct_egress_absence_claimed": False,
        "api_openai_com_absence_claimed": False,
        "forbidden_claim_detected": forbidden_claim,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-custom-detached-egress-execution-handoff-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--external-evidence-dir", default="")
    parser.add_argument(
        "--safety-admission-path",
        default=str(
            ROOT
            / "audit_results/wbp_native_custom_safety_admission_refresh_r1_2026-05-27/native_safety_admission_result_packet.json"
        ),
    )
    parser.add_argument(
        "--ready-final-status",
        default="NATIVE_DETACHED_EGRESS_EXECUTION_HANDOFF_READY_OWNER_ACTION_REQUIRED",
    )
    parser.add_argument(
        "--blocked-final-status",
        default="NATIVE_DETACHED_EGRESS_EXECUTION_HANDOFF_BLOCKED",
    )
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--wait-seconds", type=int, default=90)
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    external_evidence_dir = (
        Path(args.external_evidence_dir).resolve()
        if args.external_evidence_dir
        else repo_root
        / "audit_results"
        / "wbp_native_custom_detached_egress_execution_EXTERNAL_2026-05-26"
    )
    safety_reference = _safety_admission_reference_packet(
        Path(args.safety_admission_path).resolve()
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)

    status_lines, quarantined, unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=args.skip_git,
    )
    sync_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": "skipped" if args.skip_git else _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": "skipped" if args.skip_git else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        "git_status_short": status_lines,
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
    write_surfaces = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "phase": "phase_a_handoff_only",
        "declared_write_surfaces": [str(evidence_dir)],
        "future_detached_write_surfaces": [
            str(external_evidence_dir),
            "/tmp/wbp-native-egress-* during external owner run only",
        ],
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "protected_surface_write_allowed": False,
        "original_codex_config_write_allowed": False,
    }
    capability = build_native_direct_egress_capability_packet(
        lsof_path=_observer_tool_path("lsof"),
        tcpdump_path=_observer_tool_path("tcpdump"),
        nettop_path=_observer_tool_path("nettop"),
    )
    command = build_detached_egress_execution_command_packet(
        repo_root=repo_root,
        evidence_dir=external_evidence_dir,
        model=args.model,
        wait_seconds=args.wait_seconds,
    )
    command_hash = build_detached_egress_command_hash_packet(command_packet=command)
    admission = build_detached_egress_command_admission_packet(
        command_packet=command,
        repo_root=repo_root,
    )
    owner_boundary = build_detached_egress_owner_action_boundary_packet()
    quiescent = build_detached_egress_quiescent_requirement_packet()
    required = build_detached_egress_future_result_required_packets_packet()
    import_contract = build_detached_egress_future_result_import_contract_packet(
        required_packets_packet=required,
    )
    network_limits = build_network_claim_limits_packet()
    false_green = build_detached_egress_handoff_false_green_audit(
        command_admission_packet=admission,
        command_hash_packet=command_hash,
        owner_action_boundary_packet=owner_boundary,
        future_result_import_contract_packet=import_contract,
        network_claim_limits_packet=network_limits,
    )
    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "declared_write_surfaces_packet.json": write_surfaces,
        "version_pinning_packet.json": _version_packet(repo_root, skip_git=args.skip_git),
        "safety_admission_reference_packet.json": safety_reference,
        "current_wbp_status_packet.json": _current_wbp_status_packet(),
        "observer_capability_packet.json": capability,
        "detached_egress_execution_command_packet.json": command,
        "detached_egress_command_hash_packet.json": command_hash,
        "detached_egress_command_admission_packet.json": admission,
        "detached_egress_owner_action_boundary_packet.json": owner_boundary,
        "quiescent_precondition_requirement_packet.json": quiescent,
        "future_result_required_packets_packet.json": required,
        "future_result_import_contract_packet.json": import_contract,
        "network_claim_limits_packet.json": network_limits,
        "handoff_false_green_audit.json": false_green,
    }
    independent_audit = _independent_handoff_audit(packets)
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "detached_egress_execution_handoff_summary",
        "status": "ok"
        if sync_packet["status"] == "ok"
        and admission["status"] == "ok"
        and false_green["status"] == "ok"
        and independent_audit["status"] == "ok"
        else "blocked",
        "final_status": (
            args.ready_final_status
            if sync_packet["status"] == "ok"
            and safety_reference["status"] == "ok"
            and admission["status"] == "ok"
            and false_green["status"] == "ok"
            and independent_audit["status"] == "ok"
            else args.blocked_final_status
        ),
        "owner_action_required": True,
        "external_command_sha256": command_hash["command_sha256"],
        "external_shell_command": command["shell_command"],
        "external_evidence_dir": str(external_evidence_dir),
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "external_result_imported": False,
        "direct_egress_absence_claimed": False,
        "api_openai_com_absence_claimed": False,
        "next_phase": "owner_detached_run_then_phase_b_import",
    }
    packets["independent_handoff_audit.json"] = independent_audit
    packets["handoff_summary_packet.json"] = summary
    for filename, packet in packets.items():
        json_write(evidence_dir / filename, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
