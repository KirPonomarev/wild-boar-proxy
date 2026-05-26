#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import historical owner-visible native Custom UX acceptance with claim limits."""

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
    build_historical_routing_trace_reference_packet,
    build_machine_ui_waiver_packet,
    build_owner_cleanup_perception_packet,
    build_owner_historical_observation_import_packet,
    build_owner_ux_action_boundary_packet,
    build_owner_ux_historical_false_green_audit,
    build_owner_ux_layer_boundary_packet,
    build_owner_visible_response_observation_packet,
    build_screenshot_limit_packet,
    build_wbp_trace_observation_packet,
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
        "packet_kind": "owner_ux_historical_input_error",
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
        "tools/native_custom_owner_ux_historical_acceptance_probe.py",
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
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-custom-owner-ux-historical-acceptance-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--source-trace-packet", required=True)
    parser.add_argument("--source-closeout", default="")
    parser.add_argument("--owner-confirmation-text", required=True)
    parser.add_argument("--owner-reported-agent-answered", action="store_true")
    parser.add_argument("--owner-reported-first-custom-answered", action="store_true")
    parser.add_argument("--owner-reported-config-model-route-untouched", action="store_true")
    parser.add_argument("--owner-reported-hidden-cleanup-not-performed", action="store_true")
    parser.add_argument("--owner-confirmed-cleanup-result", action="store_true")
    parser.add_argument("--owner-waives-machine-ui", action="store_true")
    parser.add_argument("--screenshot-count", type=int, default=0)
    parser.add_argument("--screenshots-used-as-narrative-support", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_trace_path = Path(args.source_trace_packet).resolve()
    source_closeout_path = Path(args.source_closeout).resolve() if args.source_closeout else None
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if not source_trace_path.exists():
        return _emit_input_error(
            reason_class="SOURCE_TRACE_PACKET_MISSING",
            message="--source-trace-packet does not exist.",
            evidence_dir=evidence_dir,
        )
    if source_closeout_path is not None and not source_closeout_path.exists():
        return _emit_input_error(
            reason_class="SOURCE_CLOSEOUT_MISSING",
            message="--source-closeout does not exist.",
            evidence_dir=evidence_dir,
        )

    try:
        source_trace = _read_json(source_trace_path)
    except json.JSONDecodeError:
        return _emit_input_error(
            reason_class="SOURCE_TRACE_PACKET_INVALID_JSON",
            message="--source-trace-packet is not valid JSON.",
            evidence_dir=evidence_dir,
        )

    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    sync_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
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
    reference_prereqs = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "reference_prerequisites",
        "status": "ok",
        "source_trace_packet": str(source_trace_path),
        "source_closeout": str(source_closeout_path) if source_closeout_path else "",
        "source_trace_exists": source_trace_path.exists(),
        "source_closeout_exists": bool(
            source_closeout_path and source_closeout_path.exists()
        ),
        "references_are_historical_context_only": True,
        "current_contour_reuses_historical_trace_as_fresh_proof": False,
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
    owner_boundary = build_owner_ux_action_boundary_packet(
        owner_typed_specified_prompt=True,
        runtime_authority_edited=False,
        provider_or_model_authority_edited=not args.owner_reported_config_model_route_untouched,
        hidden_cleanup_performed=not args.owner_reported_hidden_cleanup_not_performed,
    )
    historical_import = build_owner_historical_observation_import_packet(
        owner_confirmation_text=args.owner_confirmation_text,
        owner_reported_agent_answered=args.owner_reported_agent_answered,
        owner_reported_first_custom_answered=args.owner_reported_first_custom_answered,
        owner_reported_config_model_route_untouched=(
            args.owner_reported_config_model_route_untouched
        ),
        owner_reported_hidden_cleanup_not_performed=(
            args.owner_reported_hidden_cleanup_not_performed
        ),
    )
    machine_ui = build_machine_ui_waiver_packet(
        owner_waives_machine_ui=args.owner_waives_machine_ui
    )
    screenshot_limit = build_screenshot_limit_packet(
        screenshot_count=args.screenshot_count,
        screenshots_used_as_narrative_support=(
            args.screenshots_used_as_narrative_support
        ),
    )
    visible_response = build_owner_visible_response_observation_packet(
        historical_observation_import_packet=historical_import,
        screenshot_limit_packet=screenshot_limit,
    )
    cleanup = build_owner_cleanup_perception_packet(
        owner_reported_hidden_cleanup_not_performed=(
            args.owner_reported_hidden_cleanup_not_performed
        ),
        owner_confirmed_cleanup_result=args.owner_confirmed_cleanup_result,
    )
    wbp_trace = build_wbp_trace_observation_packet(trace_packet=source_trace)
    historical_route_reference = build_historical_routing_trace_reference_packet(
        wbp_trace_observation_packet=wbp_trace,
        source_trace_path=str(source_trace_path),
        source_closeout_path=str(source_closeout_path) if source_closeout_path else "",
    )
    layer_boundary = build_owner_ux_layer_boundary_packet()
    allowed_claims = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_ux_historical_allowed_claims_matrix",
        "status": "ok",
        "historical_owner_visible_response_claim_allowed": (
            visible_response.get("status") == "ok"
        ),
        "historical_route_reference_allowed": (
            historical_route_reference.get("status") == "ok"
        ),
        "fresh_native_launch_claim_allowed": False,
        "fresh_route_claim_allowed": False,
        "machine_ui_proof_claim_allowed": False,
        "filesystem_safety_claim_allowed": False,
        "direct_egress_claim_allowed": False,
        "original_codex_via_wbp_claim_allowed": False,
        "final_e2e_claim_allowed": False,
    }
    false_green = build_owner_ux_historical_false_green_audit(
        historical_observation_import_packet=historical_import,
        visible_response_observation_packet=visible_response,
        cleanup_perception_packet=cleanup,
        screenshot_limit_packet=screenshot_limit,
        historical_routing_trace_reference_packet=historical_route_reference,
        layer_boundary_packet=layer_boundary,
    )
    independent_audit = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_owner_ux_historical_audit",
        "status": "ok"
        if sync_packet["status"] == "ok"
        and owner_boundary["status"] == "ok"
        and historical_import["status"] == "ok"
        and visible_response["status"] == "ok"
        and cleanup["status"] == "ok"
        and historical_route_reference["status"] == "ok"
        and false_green["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "owner_historical_observation_import_packet.json",
            "owner_visible_response_observation_packet.json",
            "owner_cleanup_perception_packet.json",
            "screenshot_limit_packet.json",
            "historical_routing_trace_reference_packet.json",
            "owner_ux_historical_false_green_audit.json",
        ],
        "historical_acceptance_counted_as_fresh_native_launch": False,
        "owner_observation_counted_as_route_proof": False,
        "screenshot_counted_as_packet_truth": False,
        "cleanup_perception_counted_as_filesystem_proof": False,
        "direct_egress_claimed": False,
        "final_e2e_claimed": False,
    }
    summary_status_ok = (
        independent_audit["status"] == "ok"
        and allowed_claims["historical_owner_visible_response_claim_allowed"]
        and allowed_claims["historical_route_reference_allowed"]
    )
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_ux_historical_acceptance_summary",
        "status": "ok" if summary_status_ok else "blocked",
        "final_status": (
            "CODEX_CUSTOM_NATIVE_OWNER_UX_HISTORICAL_ACCEPTED_WITH_LIMITS"
            if summary_status_ok
            else "CODEX_CUSTOM_NATIVE_OWNER_UX_HISTORICAL_ACCEPTANCE_BLOCKED"
        ),
        "historical_owner_visible_response_accepted": (
            visible_response.get("status") == "ok"
        ),
        "historical_route_reference_accepted": (
            historical_route_reference.get("status") == "ok"
        ),
        "fresh_native_launch_performed": False,
        "fresh_native_launch_claimed": False,
        "fresh_route_claimed": False,
        "machine_ui_proof_claimed": False,
        "filesystem_safety_claimed": False,
        "direct_egress_claimed": False,
        "original_codex_via_wbp_claimed": False,
        "final_e2e_claimed": False,
    }

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": _version_packet(repo_root),
        "declared_write_surfaces_packet.json": declared_write_surfaces,
        "reference_prerequisites_packet.json": reference_prereqs,
        "owner_action_boundary_packet.json": owner_boundary,
        "owner_historical_observation_import_packet.json": historical_import,
        "machine_ui_waiver_packet.json": machine_ui,
        "screenshot_limit_packet.json": screenshot_limit,
        "owner_visible_response_observation_packet.json": visible_response,
        "owner_cleanup_perception_packet.json": cleanup,
        "wbp_trace_observation_packet.json": wbp_trace,
        "historical_routing_trace_reference_packet.json": historical_route_reference,
        "ux_layer_boundary_packet.json": layer_boundary,
        "owner_ux_historical_allowed_claims_matrix.json": allowed_claims,
        "native_ux_false_green_audit.json": false_green,
        "independent_owner_ux_audit.json": independent_audit,
        "owner_ux_historical_acceptance_summary_packet.json": summary,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
