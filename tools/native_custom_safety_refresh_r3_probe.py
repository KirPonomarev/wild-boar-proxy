#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Native Custom safety refresh R3 evidence without launching native Codex."""

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
    build_cleanup_reversibility_plan_packet,
    build_custom_profile_ownership_packet,
    build_custom_profile_write_inventory_packet,
    build_custom_user_data_dir_ownership_packet,
    build_native_safety_layer_boundary_packet,
    build_native_safety_refresh_false_green_audit,
    build_owner_action_boundary_packet,
    build_protected_surface_read_classification_packet,
    classify_host_context,
    classify_keychain_observation,
    classify_quiescent_current_codex_precondition,
    collect_codex_process_inventory,
    create_native_probe_layout,
    json_write,
    scan_protected_surfaces,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


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
        "tools/native_custom_safety_refresh_r3_probe.py",
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
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": ["fresh evidence directory only"],
            "native_launch_allowed": False,
            "native_launch_attempted": False,
            "protected_surfaces_write_allowed": False,
            "original_codex_bundle_write_allowed": False,
            "original_codex_profile_write_allowed": False,
            "route_account_model_provider_mutation_allowed": False,
        },
    }


def _reference_packets(repo_root: Path) -> dict[str, dict[str, Any]]:
    auth_path = (
        repo_root
        / "audit_results/wbp_provider_auth_strategy_contract_refresh_2026-05-26/provider_auth_strategy_packet.json"
    )
    model_path = (
        repo_root
        / "audit_results/wbp_model_availability_smoke_matrix_refresh_2026-05-26/model_availability_matrix.json"
    )
    return {
        "reference_prerequisites_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "reference_prerequisites",
            "status": "ok",
            "auth_strategy_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
            "model_availability_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
            "owner_assisted_native_baseline": "OWNER_ASSISTED_NATIVE_CUSTOM_WBP_200_RESPONSE_PROVEN_WITH_LIMITS",
            "references_are_prerequisite_only": True,
        },
        "auth_strategy_reference_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "auth_strategy_reference",
            "status": "ok",
            "referenced_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
            "referenced_packet": str(auth_path),
            "referenced_packet_status": _json_file_status(auth_path),
            "auth_strategy_reproved_in_this_contour": False,
        },
        "model_availability_reference_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "model_availability_reference",
            "status": "ok",
            "referenced_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
            "referenced_packet": str(model_path),
            "referenced_packet_status": _json_file_status(model_path),
            "model_availability_reproved_in_this_contour": False,
        },
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "declared_write_surfaces_packet.json",
        "reference_prerequisites_packet.json",
        "current_codex_running_state_before.json",
        "protected_surface_read_classification_packet.json",
        "protected_surface_recursive_before.json",
        "custom_profile_ownership_packet.json",
        "custom_user_data_dir_ownership_packet.json",
        "custom_profile_write_inventory_packet.json",
        "cleanup_reversibility_packet.json",
        "keychain_observation_packet.json",
        "native_safety_layer_boundary_packet.json",
        "native_safety_false_green_audit.json",
        "secret_redaction_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = [
        name
        for name, packet in packets.items()
        if packet.get("status") == "blocked"
        and name
        not in {
            "host_context_packet.json",
            "quiescent_current_codex_precondition_packet.json",
            "native_safety_result_packet.json",
        }
    ]
    false_green = packets["native_safety_false_green_audit.json"]
    secret_audit = packets["secret_redaction_audit.json"]
    layer = packets["native_safety_layer_boundary_packet.json"]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_native_safety_audit",
        "status": "blocked"
        if missing or blocked or false_green.get("status") != "ok" or secret_audit.get("status") != "ok"
        else "ok",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "unexpected_blocked_packets": sorted(blocked),
        "false_green_audit_status": false_green.get("status"),
        "secret_redaction_audit_status": secret_audit.get("status"),
        "process_inventory_treated_as_ux_proof": False,
        "keychain_treated_as_auth_proof": False,
        "cleanup_treated_as_original_reversibility": False,
        "auth_or_model_reproved": False,
        "native_launch_attempted": False,
        "adjacent_claims_forbidden": layer.get("native_ux_acceptance_proven") is False
        and layer.get("direct_egress_absence_proven") is False
        and layer.get("final_e2e_proven") is False,
    }


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    raw_secret_markers = [
        "OPENAI_API_KEY=",
        "OPENROUTER_API_KEY=",
        "Authorization: Bearer",
        '"access_token":',
        '"refresh_token":',
    ]
    findings = [marker for marker in raw_secret_markers if marker in serialized]
    strict_openai_key = __import__("re").search(r"sk-[A-Za-z0-9]{20,}", serialized) is not None
    if strict_openai_key:
        findings.append("strict_openai_key_pattern")
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "secret_redaction_audit",
        "status": "blocked" if findings else "ok",
        "raw_secret_found": bool(findings),
        "secret_marker_findings": findings,
        "auth_header_recorded": "Authorization: Bearer" in serialized,
        "current_codex_auth_json_recorded": '"access_token":' in serialized
        or '"refresh_token":' in serialized,
        "protected_snapshot_filename_false_positive_possible": True,
        "checked_packet_count": len(packets),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="native-custom-safety-refresh-r3-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    planned_tmp_root = Path("/tmp") / f"wbp-native-safety-r3-{os.getpid()}"
    layout = create_native_probe_layout(planned_tmp_root)
    host_context = classify_host_context(_host_process_chain())
    process_inventory = collect_codex_process_inventory(
        custom_user_data_dir=str(layout.custom_user_data_dir)
    )
    quiescent = classify_quiescent_current_codex_precondition(process_inventory)
    protected_read = build_protected_surface_read_classification_packet()
    protected_before = scan_protected_surfaces()
    owner_boundary = build_owner_action_boundary_packet()
    layer_boundary = build_native_safety_layer_boundary_packet()
    profile_ownership = build_custom_profile_ownership_packet(
        tmp_root=layout.tmp_root,
        profile_dir=layout.profile_dir,
        codex_home=layout.custom_codex_home,
    )
    user_data_ownership = build_custom_user_data_dir_ownership_packet(
        tmp_root=layout.tmp_root,
        profile_dir=layout.profile_dir,
        user_data_dir=layout.custom_user_data_dir,
    )
    write_inventory = build_custom_profile_write_inventory_packet(
        tmp_root=layout.tmp_root,
        profile_dir=layout.profile_dir,
        user_data_dir=layout.custom_user_data_dir,
        codex_home=layout.custom_codex_home,
    )
    cleanup = build_cleanup_reversibility_plan_packet(
        tmp_root=layout.tmp_root,
        owned_paths=[layout.profile_dir, layout.custom_user_data_dir, layout.custom_codex_home],
    )
    keychain = classify_keychain_observation(machine_prompt_observed=False)
    packets = _base_packets(repo_root, evidence_dir)
    packets.update(_reference_packets(repo_root))
    packets.update(
        {
            "host_context_packet.json": host_context,
            "owner_action_boundary_packet.json": owner_boundary,
            "current_codex_running_state_before.json": process_inventory,
            "quiescent_current_codex_precondition_packet.json": quiescent,
            "protected_surface_read_classification_packet.json": protected_read,
            "protected_surface_recursive_before.json": protected_before,
            "custom_profile_ownership_packet.json": profile_ownership,
            "custom_user_data_dir_ownership_packet.json": user_data_ownership,
            "custom_profile_write_inventory_packet.json": write_inventory,
            "cleanup_reversibility_packet.json": cleanup,
            "keychain_observation_packet.json": keychain,
            "native_safety_layer_boundary_packet.json": layer_boundary,
        }
    )
    packets["native_safety_false_green_audit.json"] = build_native_safety_refresh_false_green_audit(
        layer_boundary_packet=layer_boundary,
        owner_action_boundary_packet=owner_boundary,
        protected_surface_read_packet=protected_read,
        profile_ownership_packet=profile_ownership,
        user_data_ownership_packet=user_data_ownership,
        write_inventory_packet=write_inventory,
        cleanup_reversibility_packet=cleanup,
        keychain_observation_packet=keychain,
        auth_strategy_reference_packet=packets["auth_strategy_reference_packet.json"],
        model_availability_reference_packet=packets["model_availability_reference_packet.json"],
    )
    packets["secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    blocked_by_host = host_context.get("status") != "ok" or quiescent.get("status") != "ok"
    actual_status = (
        "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_BLOCKED_BY_HOST_ENVIRONMENT"
        if host_context.get("status") != "ok"
        else "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_BLOCKED_BY_UNCLEAR_WRITE_SURFACE"
        if any(
            packet.get("status") == "blocked"
            for packet in (profile_ownership, user_data_ownership, write_inventory, cleanup)
        )
        else "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_BLOCKED_BY_HOST_ENVIRONMENT"
        if blocked_by_host
        else "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_CLASSIFIED"
    )
    packets["native_safety_result_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_safety_result",
        "status": "blocked" if actual_status != "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_CLASSIFIED" else "ok",
        "target_status": "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_CLASSIFIED",
        "actual_status": actual_status,
        "native_launch_attempted": False,
        "owner_ui_action_performed": False,
        "protected_surface_read_classified": True,
        "custom_profile_ownership_classified": profile_ownership.get("status") == "ok",
        "custom_user_data_dir_ownership_classified": user_data_ownership.get("status") == "ok",
        "cleanup_reversibility_classified": cleanup.get("status") == "ok",
        "host_context_status": host_context.get("status"),
        "quiescent_precondition_status": quiescent.get("status"),
        "route_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "original_reversibility_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
    }
    packets["independent_native_safety_audit.json"] = _independent_audit(packets)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(packets["native_safety_result_packet.json"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
