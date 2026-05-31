#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit owner UX readiness and handoff evidence without launching native Codex."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_cleanup_perception_limit_packet,
    build_historical_or_incidental_route_context_packet,
    build_machine_ui_waiver_packet,
    build_owner_handoff_instruction_packet,
    build_owner_ux_action_boundary_packet,
    build_owner_ux_layer_boundary_packet,
    build_owner_ux_readiness_false_green_audit,
    build_owner_ux_readiness_packet,
    build_provider_marker_observation_limit_packet,
    build_screenshot_limit_packet,
    json_write,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
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
        "tools/native_custom_owner_ux_readiness_handoff_probe.py",
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


def _reference_packet(repo_root: Path, *, name: str, status: str, path: Path) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": name,
        "status": "ok",
        "referenced_status": status,
        "referenced_packet": str(path),
        "referenced_packet_status": _json_file_status(path),
        "reference_only": True,
        "reproved_in_this_contour": False,
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "owner_ux_readiness_packet.json",
        "owner_handoff_instruction_packet.json",
        "owner_action_boundary_packet.json",
        "machine_ui_waiver_packet.json",
        "screenshot_limit_packet.json",
        "provider_marker_observation_limit_packet.json",
        "cleanup_perception_limit_packet.json",
        "historical_or_incidental_route_context_packet.json",
        "owner_ux_layer_boundary_packet.json",
        "owner_ux_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    unexpected_blocked = sorted(
        name
        for name, packet in packets.items()
        if packet.get("status") == "blocked" and name not in {"native_safety_reference_packet.json"}
    )
    false_green = packets.get("owner_ux_false_green_audit.json", {})
    readiness = packets.get("owner_ux_readiness_packet.json", {})
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_owner_ux_readiness_audit",
        "status": "ok"
        if not missing
        and not unexpected_blocked
        and false_green.get("status") == "ok"
        and readiness.get("native_launch_attempted") is False
        else "blocked",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "unexpected_blocked_packets": unexpected_blocked,
        "false_green_audit_status": false_green.get("status"),
        "native_launch_attempted": False,
        "owner_confirmation_collected": False,
        "readiness_counted_as_ux_acceptance": False,
        "provider_marker_counted_as_route": False,
        "cleanup_perception_counted_as_filesystem": False,
        "historical_or_incidental_route_counted_as_route_proof": False,
        "direct_egress_claimed": False,
        "final_e2e_claimed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-custom-owner-ux-readiness-handoff-probe"
    )
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
    declared_write_surfaces = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": ["fresh evidence directory only"],
        "native_app_launch_attempted_by_this_probe": False,
        "protected_surfaces_write_allowed": False,
        "original_codex_bundle_write_allowed": False,
        "original_codex_profile_write_allowed": False,
    }

    exact_prompt = "WBP_OWNER_UX_READINESS_NONCE_2026_05_26: reply WBP_OK"
    readiness = build_owner_ux_readiness_packet(
        native_launch_from_hosted_context_allowed=False,
        owner_confirmation_collected=False,
    )
    handoff = build_owner_handoff_instruction_packet(exact_prompt=exact_prompt)
    owner_boundary = build_owner_ux_action_boundary_packet(
        owner_typed_specified_prompt=False,
        runtime_authority_edited=False,
        provider_or_model_authority_edited=False,
        hidden_cleanup_performed=False,
    )
    machine_ui = build_machine_ui_waiver_packet(owner_waives_machine_ui=True)
    screenshot_limit = build_screenshot_limit_packet(
        screenshot_count=0,
        screenshots_used_as_narrative_support=False,
    )
    provider_marker = build_provider_marker_observation_limit_packet(
        provider_marker_visible=False
    )
    cleanup_limit = build_cleanup_perception_limit_packet()
    route_context = build_historical_or_incidental_route_context_packet()
    layer_boundary = build_owner_ux_layer_boundary_packet()
    false_green = build_owner_ux_readiness_false_green_audit(
        readiness_packet=readiness,
        handoff_instruction_packet=handoff,
        provider_marker_limit_packet=provider_marker,
        cleanup_perception_limit_packet=cleanup_limit,
        route_context_packet=route_context,
        layer_boundary_packet=layer_boundary,
    )

    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "declared_write_surfaces_packet.json": declared_write_surfaces,
        "version_pinning_packet.json": _version_packet(repo_root),
        "auth_strategy_reference_packet.json": _reference_packet(
            repo_root,
            name="auth_strategy_reference",
            status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
            path=repo_root
            / "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-26/provider_auth_strategy_packet.json",
        ),
        "model_availability_reference_packet.json": _reference_packet(
            repo_root,
            name="model_availability_reference",
            status="WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
            path=repo_root
            / "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-26/model_availability_matrix.json",
        ),
        "native_safety_reference_packet.json": _reference_packet(
            repo_root,
            name="native_safety_reference",
            status="NATIVE_CUSTOM_SAFETY_GUARD_BLOCKED_BY_HOST_ENVIRONMENT_WITH_HANDOFF",
            path=repo_root
            / "audit_results/wbp_native_custom_safety_guard_r2_2026-05-26/native_safety_result_packet.json",
        ),
        "owner_ux_readiness_packet.json": readiness,
        "owner_handoff_instruction_packet.json": handoff,
        "owner_action_boundary_packet.json": owner_boundary,
        "machine_ui_waiver_packet.json": machine_ui,
        "screenshot_limit_packet.json": screenshot_limit,
        "provider_marker_observation_limit_packet.json": provider_marker,
        "cleanup_perception_limit_packet.json": cleanup_limit,
        "historical_or_incidental_route_context_packet.json": route_context,
        "owner_ux_layer_boundary_packet.json": layer_boundary,
        "owner_ux_false_green_audit.json": false_green,
    }
    packets["independent_owner_ux_readiness_audit.json"] = _independent_audit(packets)
    packets["owner_ux_readiness_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_ux_readiness_summary",
        "status": "ok"
        if packets["independent_owner_ux_readiness_audit.json"].get("status") == "ok"
        else "blocked",
        "final_status": "NATIVE_CUSTOM_OWNER_UX_READINESS_AND_HANDOFF_CLASSIFIED"
        if packets["independent_owner_ux_readiness_audit.json"].get("status") == "ok"
        else "NATIVE_CUSTOM_OWNER_UX_READINESS_BLOCKED",
        "native_launch_attempted": False,
        "owner_confirmation_collected": False,
        "conditional_live_pass_claimed": False,
        "routing_claimed": False,
        "egress_claimed": False,
        "filesystem_safety_claimed": False,
        "original_reversibility_claimed": False,
        "final_e2e_claimed": False,
    }

    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(packets["owner_ux_readiness_summary_packet.json"], indent=2, sort_keys=True))
    return 0 if packets["owner_ux_readiness_summary_packet.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
