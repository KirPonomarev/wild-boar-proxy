#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify owner UX confirmation and WBP route trace as separate lanes."""

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
    build_machine_ui_waiver_packet,
    build_native_owner_ux_false_green_audit,
    build_native_route_trace_binding_packet,
    build_owner_manual_ux_check_packet,
    build_owner_nonce_prompt_packet,
    build_owner_ux_action_boundary_packet,
    build_two_lane_result_matrix,
    build_wbp_trace_observation_packet,
    json_write,
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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_ux_route_input_error",
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


def _read_trace_packet(trace_path: Path | None) -> dict[str, Any] | None:
    if trace_path is None:
        return None
    return json.loads(trace_path.read_text(encoding="utf-8"))


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
        "tools/native_custom_owner_ux_route_confirmation_probe.py",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-custom-owner-ux-route-confirmation-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--trace-packet", default="")
    parser.add_argument("--owner-waives-machine-ui", action="store_true")
    parser.add_argument("--owner-saw-window", action="store_true")
    parser.add_argument("--owner-typed-prompt", action="store_true")
    parser.add_argument("--owner-saw-response", action="store_true")
    parser.add_argument("--owner-edited-runtime-authority", action="store_true")
    parser.add_argument("--owner-edited-provider-or-model-authority", action="store_true")
    parser.add_argument("--owner-hidden-cleanup", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    trace_path = Path(args.trace_packet).resolve() if args.trace_packet else None
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if trace_path is not None and not trace_path.exists():
        return _emit_input_error(
            reason_class="TRACE_PACKET_MISSING",
            message="--trace-packet does not exist.",
            evidence_dir=evidence_dir,
        )
    try:
        source_trace = _read_trace_packet(trace_path)
    except json.JSONDecodeError:
        return _emit_input_error(
            reason_class="TRACE_PACKET_INVALID_JSON",
            message="--trace-packet is not valid JSON.",
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
    no_native_safety = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_safety_limitation_reference",
        "status": "ok",
        "filesystem_safety_reproved_in_this_contour": False,
        "direct_egress_reproved_in_this_contour": False,
        "machine_ui_reproved_in_this_contour": False,
    }
    owner_boundary = build_owner_ux_action_boundary_packet(
        owner_typed_specified_prompt=args.owner_typed_prompt,
        runtime_authority_edited=args.owner_edited_runtime_authority,
        provider_or_model_authority_edited=args.owner_edited_provider_or_model_authority,
        hidden_cleanup_performed=args.owner_hidden_cleanup,
    )
    machine_ui = build_machine_ui_waiver_packet(
        owner_waives_machine_ui=args.owner_waives_machine_ui
    )
    nonce_prompt = build_owner_nonce_prompt_packet(nonce=args.nonce)
    owner_ux = build_owner_manual_ux_check_packet(
        owner_saw_window=args.owner_saw_window,
        owner_typed_prompt=args.owner_typed_prompt,
        owner_saw_response=args.owner_saw_response,
        machine_ui_waiver_packet=machine_ui,
    )
    wbp_trace = build_wbp_trace_observation_packet(trace_packet=source_trace)
    route_binding = build_native_route_trace_binding_packet(
        owner_nonce_prompt_packet=nonce_prompt,
        wbp_trace_observation_packet=wbp_trace,
    )
    matrix = build_two_lane_result_matrix(
        owner_manual_ux_check_packet=owner_ux,
        route_trace_binding_packet=route_binding,
        wbp_trace_observation_packet=wbp_trace,
    )
    redaction_audit = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_ux_redaction_audit",
        "status": "ok"
        if not (
            wbp_trace["raw_prompt_recorded"]
            or wbp_trace["auth_header_recorded"]
            or wbp_trace["raw_auth_recorded"]
        )
        else "blocked",
        "raw_prompt_recorded": wbp_trace["raw_prompt_recorded"],
        "auth_header_recorded": wbp_trace["auth_header_recorded"],
        "raw_auth_recorded": wbp_trace["raw_auth_recorded"],
        "prompt_hash_recorded": nonce_prompt["prompt_hash_recorded"],
        "request_body_hash_recorded": bool(wbp_trace["request_body_sha256"]),
        "response_body_hash_recorded": bool(wbp_trace["response_body_sha256"]),
    }
    allowed_claims = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_ux_allowed_claims_matrix",
        "status": "ok",
        "owner_ux_claim_allowed": owner_ux["ux_status"] == "confirmed",
        "route_claim_allowed": matrix["route_trace_confirmed"],
        "machine_ui_proof_claim_allowed": False,
        "filesystem_safety_claim_allowed": False,
        "direct_egress_claim_allowed": False,
        "final_e2e_claim_allowed": False,
    }
    false_green = build_native_owner_ux_false_green_audit(
        machine_ui_waiver_packet=machine_ui,
        owner_manual_ux_check_packet=owner_ux,
        wbp_trace_observation_packet=wbp_trace,
        two_lane_result_matrix=matrix,
    )
    independent_audit = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_owner_ux_route_audit",
        "status": "ok"
        if sync_packet["status"] == "ok"
        and owner_boundary["status"] == "ok"
        and redaction_audit["status"] == "ok"
        and false_green["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "owner_manual_ux_check_packet.json",
            "wbp_trace_observation_packet.json",
            "native_route_trace_binding_packet.json",
            "two_lane_result_matrix.json",
            "native_owner_ux_false_green_audit.json",
        ],
        "manual_ui_waiver_counted_as_route_proof": False,
        "route_trace_counted_as_machine_ui_proof": False,
        "direct_egress_claimed": False,
        "final_e2e_claimed": False,
    }
    summary = {
        "captured_at_utc": _utc_now(),
        "status": "ok"
        if matrix["status"] == "ok"
        and sync_packet["status"] == "ok"
        and owner_boundary["status"] == "ok"
        and independent_audit["status"] == "ok"
        else "blocked",
        "final_status": matrix["final_status"],
        "owner_ux_confirmed": matrix["owner_ux_confirmed"],
        "route_trace_confirmed": matrix["route_trace_confirmed"],
        "machine_ui_proof_claimed": False,
        "filesystem_safety_claimed": False,
        "direct_egress_claimed": False,
        "final_e2e_claimed": False,
    }

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": _version_packet(repo_root),
        "declared_write_surfaces_packet.json": declared_write_surfaces,
        "owner_action_boundary_packet.json": owner_boundary,
        "machine_ui_waiver_packet.json": machine_ui,
        "native_safety_limitation_reference_packet.json": no_native_safety,
        "owner_nonce_prompt_packet.json": nonce_prompt,
        "owner_manual_ux_check_packet.json": owner_ux,
        "wbp_trace_observation_packet.json": wbp_trace,
        "native_route_trace_binding_packet.json": route_binding,
        "two_lane_result_matrix.json": matrix,
        "native_owner_ux_allowed_claims_matrix.json": allowed_claims,
        "native_owner_ux_redaction_audit.json": redaction_audit,
        "native_owner_ux_false_green_audit.json": false_green,
        "independent_owner_ux_route_audit.json": independent_audit,
        "owner_ux_route_summary_packet.json": summary,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
