#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit no-launch native direct-egress observer readiness evidence."""

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
    build_absence_claim_limit_packet,
    build_current_background_codex_noise_packet,
    build_egress_readiness_false_green_audit,
    build_historical_route_context_reference_packet,
    build_native_direct_egress_capability_packet,
    build_native_egress_observer_readiness_packet,
    build_network_claim_limits_packet,
    build_owner_egress_handoff_instruction_packet,
    build_process_attribution_limit_packet,
    build_quiescent_network_precondition_packet,
    build_wbp_endpoint_observation_limit_packet,
    collect_codex_process_inventory,
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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


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
        "tools/native_direct_egress_observer_readiness_probe.py",
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


def _version_packet(repo_root: Path) -> dict[str, Any]:
    return {
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
    }


def _reference_packet(
    repo_root: Path,
    *,
    packet_kind: str,
    referenced_status: str,
    path: Path,
) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": packet_kind,
        "status": "ok",
        "referenced_status": referenced_status,
        "referenced_packet": str(path),
        "referenced_packet_status": _json_file_status(path),
        "reference_only": True,
        "reproved_in_this_contour": False,
        "repo_root": str(repo_root),
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "network_observer_capability_packet.json",
        "current_background_codex_noise_packet.json",
        "quiescent_network_precondition_packet.json",
        "native_egress_observer_readiness_packet.json",
        "wbp_endpoint_observation_limit_packet.json",
        "process_attribution_limit_packet.json",
        "absence_claim_limit_packet.json",
        "network_claim_limits_packet.json",
        "owner_egress_handoff_instruction_packet.json",
        "historical_route_context_reference_packet.json",
        "egress_readiness_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    false_green = packets.get("egress_readiness_false_green_audit.json", {})
    readiness = packets.get("native_egress_observer_readiness_packet.json", {})
    wbp_limit = packets.get("wbp_endpoint_observation_limit_packet.json", {})
    absence_limit = packets.get("absence_claim_limit_packet.json", {})
    forbidden_claim = any(
        packet.get(key) is True
        for packet in packets.values()
        for key in (
            "fresh_native_launch_attempted",
            "live_network_capture_attempted",
            "direct_egress_absence_proven",
            "api_openai_com_absence_proven",
            "full_network_absence_proven",
            "final_e2e_proven",
        )
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_egress_readiness_audit",
        "status": "ok"
        if not missing
        and false_green.get("status") == "ok"
        and not forbidden_claim
        and readiness.get("final_status")
        in {
            "NATIVE_DIRECT_EGRESS_OBSERVER_READINESS_CLASSIFIED",
            "NATIVE_DIRECT_EGRESS_OBSERVER_BLOCKED_BY_HOST_ENVIRONMENT_WITH_HANDOFF",
        }
        else "blocked",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "referenced_packets": sorted(required),
        "false_green_audit_status": false_green.get("status"),
        "fresh_native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "wbp_endpoint_counted_as_route_proof": wbp_limit.get("counts_as_route_proof")
        is True,
        "no_api_openai_observation_counted_as_absence": absence_limit.get(
            "no_observed_api_openai_equals_absence"
        )
        is True,
        "direct_egress_absence_claimed": False,
        "api_openai_com_absence_claimed": False,
        "final_e2e_claimed": False,
        "forbidden_claim_detected": forbidden_claim,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-direct-egress-observer-readiness-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--hosted-by-codex-context", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    sync_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
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
    declared_write_surfaces = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": ["fresh evidence directory only"],
        "native_app_launch_attempted_by_this_probe": False,
        "live_network_capture_attempted_by_this_probe": False,
        "protected_surfaces_write_allowed": False,
        "original_codex_bundle_write_allowed": False,
        "original_codex_profile_write_allowed": False,
    }
    capability = build_native_direct_egress_capability_packet(
        lsof_path=_observer_tool_path("lsof"),
        tcpdump_path=_observer_tool_path("tcpdump"),
        nettop_path=_observer_tool_path("nettop"),
        process_tree_observer_available=True,
    )
    current_inventory = collect_codex_process_inventory(
        custom_user_data_dir="__no_live_custom__"
    )
    current_noise = build_current_background_codex_noise_packet(
        current_process_inventory_packet=current_inventory,
        hosted_by_codex_context=args.hosted_by_codex_context,
    )
    quiescent = build_quiescent_network_precondition_packet(
        observer_capability_packet=capability,
        current_background_codex_noise_packet=current_noise,
    )
    readiness = build_native_egress_observer_readiness_packet(
        observer_capability_packet=capability,
        current_background_codex_noise_packet=current_noise,
        quiescent_network_precondition_packet=quiescent,
    )
    wbp_limit = build_wbp_endpoint_observation_limit_packet()
    process_limit = build_process_attribution_limit_packet(
        observer_capability_packet=capability,
        current_background_codex_noise_packet=current_noise,
    )
    absence_limit = build_absence_claim_limit_packet(
        quiescent_network_precondition_packet=quiescent,
        process_attribution_limit_packet=process_limit,
    )
    network_limits = build_network_claim_limits_packet()
    historical_reference = build_historical_route_context_reference_packet(
        source_packets=[
            "audit_results/wbp_native_custom_direct_egress_classification_2026-05-26/native_direct_egress_claim_packet.json",
            "audit_results/native_wbp_route_network_observer_feasibility_2026-05-26/network_observer_feasibility_summary_packet.json",
            "audit_results/wbp_native_custom_owner_ux_readiness_handoff_r1_2026-05-26/owner_ux_readiness_summary_packet.json",
        ]
    )
    false_green = build_egress_readiness_false_green_audit(
        native_egress_observer_readiness_packet=readiness,
        wbp_endpoint_observation_limit_packet=wbp_limit,
        process_attribution_limit_packet=process_limit,
        absence_claim_limit_packet=absence_limit,
        network_claim_limits_packet=network_limits,
        historical_route_context_reference_packet=historical_reference,
    )

    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "declared_write_surfaces_packet.json": declared_write_surfaces,
        "version_pinning_packet.json": _version_packet(repo_root),
        "auth_strategy_reference_packet.json": _reference_packet(
            repo_root,
            packet_kind="auth_strategy_reference",
            referenced_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
            path=repo_root
            / "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-26/provider_auth_strategy_packet.json",
        ),
        "model_availability_reference_packet.json": _reference_packet(
            repo_root,
            packet_kind="model_availability_reference",
            referenced_status="WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
            path=repo_root
            / "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-26/model_availability_matrix.json",
        ),
        "native_safety_reference_packet.json": _reference_packet(
            repo_root,
            packet_kind="native_safety_reference",
            referenced_status="NATIVE_CUSTOM_SAFETY_GUARD_BLOCKED_BY_HOST_ENVIRONMENT_WITH_HANDOFF",
            path=repo_root
            / "audit_results/wbp_native_custom_safety_guard_r2_2026-05-26/native_safety_result_packet.json",
        ),
        "owner_ux_readiness_reference_packet.json": _reference_packet(
            repo_root,
            packet_kind="owner_ux_readiness_reference",
            referenced_status="NATIVE_CUSTOM_OWNER_UX_READINESS_AND_HANDOFF_CLASSIFIED",
            path=repo_root
            / "audit_results/wbp_native_custom_owner_ux_readiness_handoff_r1_2026-05-26/owner_ux_readiness_summary_packet.json",
        ),
        "network_observer_capability_packet.json": capability,
        "current_codex_process_inventory_packet.json": current_inventory,
        "current_background_codex_noise_packet.json": current_noise,
        "quiescent_network_precondition_packet.json": quiescent,
        "native_egress_observer_readiness_packet.json": readiness,
        "wbp_endpoint_observation_limit_packet.json": wbp_limit,
        "process_attribution_limit_packet.json": process_limit,
        "absence_claim_limit_packet.json": absence_limit,
        "network_claim_limits_packet.json": network_limits,
        "owner_egress_handoff_instruction_packet.json": build_owner_egress_handoff_instruction_packet(),
        "historical_route_context_reference_packet.json": historical_reference,
        "egress_readiness_false_green_audit.json": false_green,
    }
    packets["independent_egress_readiness_audit.json"] = _independent_audit(packets)
    packets["native_direct_egress_observer_readiness_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_direct_egress_observer_readiness_summary",
        "status": packets["independent_egress_readiness_audit.json"]["status"],
        "final_status": readiness["final_status"],
        "reason_class": readiness["reason_class"],
        "observer_capability_ok": readiness["observer_capability_ok"],
        "current_background_codex_noise_detected": readiness[
            "current_background_codex_noise_detected"
        ],
        "owner_or_detached_handoff_required": readiness[
            "owner_or_detached_handoff_required"
        ],
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "direct_egress_absence_proven": False,
        "api_openai_com_absence_proven": False,
        "final_e2e_claimed": False,
    }

    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(
        json.dumps(
            packets["native_direct_egress_observer_readiness_summary_packet.json"],
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packets["independent_egress_readiness_audit.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
