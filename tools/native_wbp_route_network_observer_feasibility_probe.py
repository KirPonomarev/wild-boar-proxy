#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""No-launch replay and observer-feasibility classifier for native WBP egress."""

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
    build_current_background_codex_noise_packet,
    build_egress_prior_blocker_replay_packet,
    build_historical_route_context_packet,
    build_native_direct_egress_capability_packet,
    build_native_egress_observer_false_green_audit,
    build_network_claim_limits_packet,
    build_network_observer_feasibility_decision_packet,
    build_quiescent_network_precondition_packet,
    build_wbp_trace_observation_packet,
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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "network_observer_feasibility_input_error",
        "status": "blocked",
        "reason_class": reason_class,
        "message": message,
        "traceback_emitted": False,
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        json_write(evidence_dir / "input_error_packet.json", packet)
    print(json.dumps(packet, indent=2, sort_keys=True), file=sys.stderr)
    return 2


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
    admitted_current_contour = [
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_wbp_route_network_observer_feasibility_probe.py",
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _sync_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
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
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": ["fresh evidence directory only"],
            "native_app_launch_attempted_by_this_probe": False,
            "owner_prompt_requested": False,
            "protected_surfaces_write_allowed": False,
            "original_codex_bundle_write_allowed": False,
            "original_codex_profile_write_allowed": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-wbp-route-network-observer-feasibility-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--prior-evidence-dir", required=True)
    parser.add_argument("--hosted-by-codex-context", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    prior_dir = Path(args.prior_evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root.",
        )
    if not prior_dir.exists():
        return _emit_input_error(
            reason_class="PRIOR_EVIDENCE_DIR_MISSING",
            message="--prior-evidence-dir does not exist.",
            evidence_dir=evidence_dir,
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    required = {
        "native_direct_egress_claim_packet.json": prior_dir
        / "native_direct_egress_claim_packet.json",
        "native_process_network_observation_packet.json": prior_dir
        / "native_process_network_observation_packet.json",
        "native_background_codex_noise_packet.json": prior_dir
        / "native_background_codex_noise_packet.json",
        "source_wbp_trace_packet.json": prior_dir / "source_wbp_trace_packet.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        return _emit_input_error(
            reason_class="PRIOR_EVIDENCE_PACKET_MISSING",
            message=f"Missing prior packets: {', '.join(missing)}",
            evidence_dir=evidence_dir,
        )
    try:
        prior_claim = _read_json(required["native_direct_egress_claim_packet.json"])
        prior_network = _read_json(required["native_process_network_observation_packet.json"])
        prior_noise = _read_json(required["native_background_codex_noise_packet.json"])
        prior_trace_source = _read_json(required["source_wbp_trace_packet.json"])
    except json.JSONDecodeError as exc:
        return _emit_input_error(
            reason_class="PRIOR_EVIDENCE_PACKET_INVALID_JSON",
            message=str(exc),
            evidence_dir=evidence_dir,
        )

    packets = _sync_packets(repo_root, evidence_dir)
    wbp_trace = build_wbp_trace_observation_packet(trace_packet=prior_trace_source)
    replay = build_egress_prior_blocker_replay_packet(
        prior_claim_packet=prior_claim,
        prior_process_network_observation_packet=prior_network,
        prior_background_noise_packet=prior_noise,
        prior_wbp_trace_observation_packet=wbp_trace,
    )
    historical_route = build_historical_route_context_packet(
        wbp_trace_observation_packet=wbp_trace,
        source_trace_path=str(required["source_wbp_trace_packet.json"]),
    )
    capability = build_native_direct_egress_capability_packet(
        lsof_path=_observer_tool_path("lsof"),
        tcpdump_path=_observer_tool_path("tcpdump"),
        nettop_path=_observer_tool_path("nettop"),
        process_tree_observer_available=True,
    )
    current_inventory = collect_codex_process_inventory(custom_user_data_dir="__no_live_custom__")
    current_noise = build_current_background_codex_noise_packet(
        current_process_inventory_packet=current_inventory,
        hosted_by_codex_context=args.hosted_by_codex_context,
    )
    quiescent = build_quiescent_network_precondition_packet(
        observer_capability_packet=capability,
        current_background_codex_noise_packet=current_noise,
    )
    decision = build_network_observer_feasibility_decision_packet(
        prior_blocker_replay_packet=replay,
        observer_capability_packet=capability,
        quiescent_network_precondition_packet=quiescent,
    )
    limits = build_network_claim_limits_packet()
    false_green = build_native_egress_observer_false_green_audit(
        historical_route_context_packet=historical_route,
        network_observer_feasibility_decision_packet=decision,
        network_claim_limits_packet=limits,
    )
    independent_audit = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_network_observer_audit",
        "status": "ok"
        if packets["sync_gate_packet.json"]["status"] == "ok"
        and replay["status"] == "ok"
        and historical_route["status"] == "ok"
        and capability["status"] == "ok"
        and false_green["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "egress_prior_blocker_replay_packet.json",
            "historical_route_context_packet.json",
            "network_observer_capability_packet.json",
            "current_background_codex_noise_packet.json",
            "quiescent_network_precondition_packet.json",
            "network_observer_feasibility_decision_packet.json",
            "network_claim_limits_packet.json",
            "native_egress_observer_false_green_audit.json",
        ],
        "historical_route_counted_as_current_egress_proof": False,
        "owner_ux_counted_as_network_proof": False,
        "screenshot_counted_as_network_proof": False,
        "blocked_observer_counted_as_pass": False,
        "fresh_native_launch_attempted": False,
        "direct_egress_absence_claimed": False,
        "api_openai_com_absence_claimed": False,
        "final_e2e_claimed": False,
    }
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "network_observer_feasibility_summary",
        "status": "ok" if independent_audit["status"] == "ok" else "blocked",
        "final_status": decision["final_status"],
        "reason_class": decision["reason_class"],
        "observer_capability_ok": capability["status"] == "ok",
        "current_background_codex_noise_detected": (
            current_noise["background_codex_noise_detected"] is True
        ),
        "separate_live_bounded_egress_contour_admissible": (
            decision["separate_live_bounded_egress_contour_admissible"] is True
        ),
        "fresh_native_launch_attempted": False,
        "direct_egress_absence_proven": False,
        "api_openai_com_absence_proven": False,
        "full_network_absence_proven": False,
        "final_e2e_claimed": False,
    }
    packets.update(
        {
            "egress_prior_blocker_replay_packet.json": replay,
            "historical_route_context_packet.json": historical_route,
            "network_observer_capability_packet.json": capability,
            "current_codex_process_inventory_packet.json": current_inventory,
            "current_background_codex_noise_packet.json": current_noise,
            "quiescent_network_precondition_packet.json": quiescent,
            "network_observer_feasibility_decision_packet.json": decision,
            "network_claim_limits_packet.json": limits,
            "native_egress_observer_false_green_audit.json": false_green,
            "independent_network_observer_audit.json": independent_audit,
            "network_observer_feasibility_summary_packet.json": summary,
        }
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
