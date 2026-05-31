#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify bounded native Custom process egress admission without overclaiming."""

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
    build_bounded_observation_window_packet,
    build_bounded_process_egress_false_green_audit,
    build_current_background_codex_noise_packet,
    build_custom_process_binding_packet,
    build_domain_attribution_limit_packet,
    build_native_direct_egress_capability_packet,
    build_native_direct_egress_claim_packet,
    build_native_direct_egress_false_green_audit,
    build_network_claim_limits_packet,
    build_owner_visible_response_context_packet,
    build_temp_custom_cleanup_packet,
    build_wbp_trace_observation_packet,
    collect_codex_process_inventory,
    json_write,
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
    admitted_current_contour = [
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_bounded_process_egress_classification_probe.py",
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


def _admission_packet(
    *,
    capability_packet: dict[str, Any],
    background_noise_packet: dict[str, Any],
    allow_live: bool,
) -> dict[str, Any]:
    observer_ok = capability_packet.get("status") == "ok"
    background_noise = background_noise_packet.get("background_codex_noise_detected") is True
    admitted = observer_ok and not background_noise and allow_live
    if not observer_ok:
        reason_class = "OBSERVER_CAPABILITY_UNAVAILABLE"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_OBSERVER_INSUFFICIENT"
    elif background_noise:
        reason_class = "BACKGROUND_CODEX_NOISE"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE"
    elif not allow_live:
        reason_class = "LIVE_NATIVE_EGRESS_NOT_AUTHORIZED_FOR_THIS_RUN"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_OBSERVER_INSUFFICIENT"
    else:
        reason_class = ""
        final_status = "NATIVE_WBP_ROUTE_NETWORK_LIVE_CAPTURE_ADMITTED"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_launch_admission",
        "status": "ok" if admitted else "blocked",
        "final_status": final_status,
        "reason_class": reason_class,
        "observer_capability_ok": observer_ok,
        "background_codex_noise_detected": background_noise,
        "allow_live_requested": allow_live,
        "native_launch_admitted": admitted,
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "observer_capability_packet.json",
        "current_background_codex_noise_before_packet.json",
        "bounded_observation_window_packet.json",
        "custom_process_binding_packet.json",
        "native_launch_admission_packet.json",
        "owner_action_boundary_packet.json",
        "native_process_network_observation_packet.json",
        "source_wbp_trace_packet.json",
        "wbp_trace_observation_packet.json",
        "native_direct_egress_claim_packet.json",
        "domain_attribution_limit_packet.json",
        "native_direct_egress_false_green_audit.json",
        "bounded_process_egress_false_green_audit.json",
        "owner_visible_response_context_packet.json",
        "network_claim_limits_packet.json",
        "temp_custom_cleanup_packet.json",
    }
    missing = sorted(required - set(packets))
    forbidden_claim = any(
        packet.get(key) is True
        for packet in packets.values()
        for key in (
            "api_openai_com_absence_proven",
            "full_network_absence_proven",
            "native_ux_claimed",
            "filesystem_safety_proven",
            "original_reversibility_proven",
            "final_e2e_claimed",
        )
    )
    bounded_audit = packets.get("bounded_process_egress_false_green_audit.json", {})
    direct_audit = packets.get("native_direct_egress_false_green_audit.json", {})
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_native_direct_egress_audit",
        "status": "ok"
        if not missing
        and not forbidden_claim
        and bounded_audit.get("status") == "ok"
        and direct_audit.get("status") == "ok"
        else "blocked",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "bounded_false_green_audit_status": bounded_audit.get("status"),
        "native_direct_egress_false_green_audit_status": direct_audit.get("status"),
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "owner_visible_response_counted_as_network_proof": False,
        "api_openai_absence_claimed_without_domain_attribution": False,
        "blocked_result_counted_as_pass": False,
        "forbidden_claim_detected": forbidden_claim,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-custom-bounded-process-egress-classification-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--wait-seconds", type=int, default=90)
    parser.add_argument("--hosted-by-codex-context", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
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
    capability = build_native_direct_egress_capability_packet(
        lsof_path=shutil.which("lsof") or "",
        tcpdump_path=shutil.which("tcpdump") or "",
        nettop_path=shutil.which("nettop") or "",
        process_tree_observer_available=True,
    )
    current_inventory = collect_codex_process_inventory(
        custom_user_data_dir="__no_live_custom__"
    )
    current_noise = build_current_background_codex_noise_packet(
        current_process_inventory_packet=current_inventory,
        hosted_by_codex_context=args.hosted_by_codex_context,
    )
    window = build_bounded_observation_window_packet(
        wait_seconds=args.wait_seconds,
        live_native_launch_attempted=False,
    )
    admission = _admission_packet(
        capability_packet=capability,
        background_noise_packet=current_noise,
        allow_live=args.allow_live,
    )
    empty_network = {
        "status": "ok",
        "machine_error_code": "INSUFFICIENT_OBSERVATION",
        "classification": "insufficient_observation",
        "direct_non_wbp_model_egress_absent_proven": False,
        "process_tree_observed": False,
        "sample_count": 0,
        "allowed_local_endpoint_observed": False,
        "peer_endpoints": [],
        "live_network_capture_attempted": False,
    }
    wbp_trace = build_wbp_trace_observation_packet(trace_packet={})
    process_binding = build_custom_process_binding_packet(
        launch_packet={"custom_process_observed": False},
        observer_root_pid_bound=False,
    )
    claim = build_native_direct_egress_claim_packet(
        process_network_observation_packet=empty_network,
        wbp_trace_observation_packet=wbp_trace,
        custom_process_bound=False,
        background_codex_noise_detected=current_noise[
            "background_codex_noise_detected"
        ]
        is True,
    )
    domain_limit = build_domain_attribution_limit_packet(
        process_network_observation_packet=empty_network,
        domain_attribution_available=False,
    )
    direct_false_green = build_native_direct_egress_false_green_audit(
        native_direct_egress_claim_packet=claim,
        process_network_observation_packet=empty_network,
        wbp_trace_observation_packet=wbp_trace,
    )
    owner_context = build_owner_visible_response_context_packet()
    cleanup_reversibility = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "cleanup_reversibility",
        "status": "ok",
        "cleanup_not_required_reason": "native_launch_not_attempted",
        "tmp_root_removed": True,
        "custom_processes_gone": True,
        "hidden_cleanup_performed": False,
        "filesystem_safety_proven": False,
    }
    temp_cleanup = build_temp_custom_cleanup_packet(
        cleanup_reversibility_packet=cleanup_reversibility
    )
    bounded_false_green = build_bounded_process_egress_false_green_audit(
        native_direct_egress_claim_packet=claim,
        domain_attribution_limit_packet=domain_limit,
        owner_visible_response_context_packet=owner_context,
        temp_custom_cleanup_packet=temp_cleanup,
    )
    owner_action_boundary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_action_boundary",
        "status": "ok",
        "owner_prompt_requested": False,
        "owner_visible_response_report_requested": False,
        "runtime_authority_edited": False,
        "provider_or_model_authority_edited": False,
        "hidden_cleanup_performed": False,
        "owner_visible_response_counts_as_context_only": True,
    }
    source_wbp_trace = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_wbp_trace",
        "status": "blocked",
        "reason_class": admission["reason_class"],
        "request_observed": False,
        "response_observed": False,
        "trace_started": False,
        "native_launch_attempted": False,
        "raw_prompt_recorded": False,
        "raw_auth_recorded": False,
    }
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": sync_packet,
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
            "native_app_launch_attempted_by_this_probe": False,
            "live_network_capture_attempted_by_this_probe": False,
            "protected_surfaces_write_allowed": False,
            "original_codex_bundle_write_allowed": False,
            "original_codex_profile_write_allowed": False,
        },
        "version_pinning_packet.json": _version_packet(repo_root),
        "observer_capability_packet.json": capability,
        "current_codex_process_inventory_before_packet.json": current_inventory,
        "current_background_codex_noise_before_packet.json": current_noise,
        "bounded_observation_window_packet.json": window,
        "custom_process_binding_packet.json": process_binding,
        "native_launch_admission_packet.json": admission,
        "owner_action_boundary_packet.json": owner_action_boundary,
        "native_process_network_observation_packet.json": empty_network,
        "source_wbp_trace_packet.json": source_wbp_trace,
        "wbp_trace_observation_packet.json": wbp_trace,
        "native_direct_egress_claim_packet.json": claim,
        "domain_attribution_limit_packet.json": domain_limit,
        "native_direct_egress_false_green_audit.json": direct_false_green,
        "bounded_process_egress_false_green_audit.json": bounded_false_green,
        "owner_visible_response_context_packet.json": owner_context,
        "network_claim_limits_packet.json": build_network_claim_limits_packet(),
        "cleanup_reversibility_packet.json": cleanup_reversibility,
        "temp_custom_cleanup_packet.json": temp_cleanup,
    }
    packets["independent_native_direct_egress_audit.json"] = _independent_audit(
        packets
    )
    packets["bounded_process_egress_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "bounded_process_egress_summary",
        "status": packets["independent_native_direct_egress_audit.json"]["status"],
        "final_status": claim["final_status"],
        "reason_class": claim["reason_class"] or admission["reason_class"],
        "native_launch_attempted": False,
        "live_network_capture_attempted": False,
        "direct_non_wbp_model_egress_absent_proven": False,
        "api_openai_com_absence_proven": False,
        "full_network_absence_proven": False,
        "owner_visible_response_context_only": True,
        "final_e2e_claimed": False,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(packets["bounded_process_egress_summary_packet.json"], indent=2, sort_keys=True))
    return 0 if packets["independent_native_direct_egress_audit.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
