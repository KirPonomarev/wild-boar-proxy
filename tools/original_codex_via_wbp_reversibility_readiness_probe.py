#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""No-launch readiness classifier for future Original Codex via WBP proof."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_original_auth_boundary_packet,
    build_original_live_admissibility_decision_packet,
    build_original_process_window_state_packet,
    build_original_profile_inventory_packet,
    build_original_readiness_false_green_audit,
    build_original_rollback_feasibility_packet,
    build_original_surface_read_classification_packet,
    build_original_temporary_route_strategy_packet,
    build_original_via_wbp_claim_limits_packet,
    collect_codex_process_inventory,
    json_write,
)


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"access_token[\"']?\s*[:=]\s*[\"'][^\"']{8,}", re.IGNORECASE),
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


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = (
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/original_codex_via_wbp_reversibility_readiness_probe.py",
    )
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
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": status_lines,
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
            "native_original_launch_allowed": False,
            "native_original_launch_attempted": False,
            "original_codex_profile_write_allowed": False,
            "original_codex_profile_write_performed": False,
            "current_auth_json_execution_dependency_allowed": False,
            "runtime_route_or_account_mutation_allowed": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "codex_cli_version": _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version_optional_not_blocking": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "original_readiness_schema_version": 1,
        },
    }


def _historical_context_reference_packet(repo_root: Path) -> dict[str, Any]:
    reference_dirs = [
        "audit_results/wbp_provider_auth_strategy_contract_refresh_2026-05-26",
        "audit_results/wbp_model_availability_smoke_matrix_refresh_2026-05-26",
        "audit_results/wbp_native_custom_owner_ux_historical_acceptance_2026-05-26",
        "audit_results/native_wbp_route_network_observer_feasibility_2026-05-26",
        "audit_results/wbp_native_custom_safety_refresh_r3_2026-05-26",
    ]
    entries = [
        {
            "path": path,
            "exists": (repo_root / path).exists(),
            "used_as_original_route_proof": False,
            "used_as_original_ux_proof": False,
            "used_as_original_egress_proof": False,
        }
        for path in reference_dirs
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_context_reference",
        "status": "ok",
        "references": entries,
        "current_contour_relies_on_history_as_original_proof": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
        "native_custom_history_promoted_to_original": False,
        "egress_blocker_promoted_to_pass": False,
    }


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    raw_secret_found = any(pattern.search(serialized) for pattern in SECRET_PATTERNS)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_readiness_secret_redaction_audit",
        "status": "blocked" if raw_secret_found else "ok",
        "raw_secret_found": raw_secret_found,
        "auth_json_token_value_recorded": False,
        "auth_header_recorded": False,
        "upstream_secret_recorded": False,
        "checked_packet_count": len(packets),
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "historical_context_reference_packet.json",
        "original_surface_read_classification_packet.json",
        "original_profile_inventory_packet.json",
        "original_auth_boundary_packet.json",
        "original_process_window_state_packet.json",
        "temporary_route_strategy_packet.json",
        "rollback_feasibility_packet.json",
        "original_live_admissibility_decision_packet.json",
        "original_via_wbp_claim_limits_packet.json",
        "original_readiness_false_green_audit.json",
        "original_readiness_secret_redaction_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = [
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    ]
    decision = packets.get("original_live_admissibility_decision_packet.json", {})
    false_green = packets.get("original_readiness_false_green_audit.json", {})
    auth = packets.get("original_auth_boundary_packet.json", {})
    rollback = packets.get("rollback_feasibility_packet.json", {})
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_original_readiness_audit",
        "status": "ok" if not missing and not blocked else "blocked",
        "referenced_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": sorted(blocked),
        "no_native_original_launch": decision.get("native_original_launch_attempted") is False,
        "no_original_profile_write": decision.get("original_profile_write_performed") is False,
        "current_auth_json_not_runtime_input": auth.get("auth_json_used_as_runtime_input") is False,
        "rollback_not_executed": rollback.get("rollback_executed") is False,
        "false_green_audit_ok": false_green.get("status") == "ok",
        "route_proof_claimed": decision.get("original_route_proven") is True,
        "final_e2e_claimed": decision.get("final_e2e_proven") is True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="original-codex-via-wbp-readiness-probe")
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

    packets: dict[str, dict[str, Any]] = _base_packets(repo_root, evidence_dir)
    packets["historical_context_reference_packet.json"] = _historical_context_reference_packet(
        repo_root
    )
    process_inventory = collect_codex_process_inventory(
        custom_user_data_dir="__original_readiness_no_custom_launch__"
    )
    surface_read = build_original_surface_read_classification_packet()
    profile_inventory = build_original_profile_inventory_packet()
    auth_boundary = build_original_auth_boundary_packet(
        profile_inventory_packet=profile_inventory
    )
    process_window = build_original_process_window_state_packet(
        process_inventory_packet=process_inventory
    )
    route_strategy = build_original_temporary_route_strategy_packet(
        profile_inventory_packet=profile_inventory
    )
    rollback = build_original_rollback_feasibility_packet(
        temporary_route_strategy_packet=route_strategy
    )
    claim_limits = build_original_via_wbp_claim_limits_packet()
    decision = build_original_live_admissibility_decision_packet(
        surface_read_packet=surface_read,
        profile_inventory_packet=profile_inventory,
        auth_boundary_packet=auth_boundary,
        process_window_state_packet=process_window,
        temporary_route_strategy_packet=route_strategy,
        rollback_feasibility_packet=rollback,
        claim_limits_packet=claim_limits,
        egress_blocked_prior_context=True,
    )
    false_green = build_original_readiness_false_green_audit(
        live_admissibility_decision_packet=decision,
        claim_limits_packet=claim_limits,
    )
    packets.update(
        {
            "original_surface_read_classification_packet.json": surface_read,
            "original_profile_inventory_packet.json": profile_inventory,
            "original_auth_boundary_packet.json": auth_boundary,
            "original_process_window_state_packet.json": process_window,
            "temporary_route_strategy_packet.json": route_strategy,
            "rollback_feasibility_packet.json": rollback,
            "original_via_wbp_claim_limits_packet.json": claim_limits,
            "original_live_admissibility_decision_packet.json": decision,
            "original_readiness_false_green_audit.json": false_green,
        }
    )
    packets["original_readiness_secret_redaction_audit.json"] = _secret_redaction_audit(
        packets
    )
    packets["independent_original_readiness_audit.json"] = _independent_audit(packets)
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_readiness_summary",
        "status": (
            "ok"
            if all(packet.get("status") != "blocked" for packet in packets.values())
            else "blocked"
        ),
        "final_status": decision["final_status"],
        "native_original_launch_attempted": False,
        "original_profile_write_performed": False,
        "original_route_proven": False,
        "rollback_executed": False,
        "normal_original_post_cleanup_proven": False,
        "direct_egress_absence_proven": False,
        "final_e2e_proven": False,
    }
    packets["original_readiness_summary_packet.json"] = summary
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
