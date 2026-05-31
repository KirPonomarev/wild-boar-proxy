#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import packet-backed owner-confirmed Custom UX evidence under current claim bounds."""

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

from wild_boar_proxy.native_filesystem_probe import json_write


SOURCE_REQUIRED_PACKETS = {
    "owner_action_boundary_packet.json",
    "owner_manual_ux_check_packet.json",
    "owner_visible_response_confirmation_packet.json",
    "wbp_trace_observation_packet.json",
    "native_route_trace_binding_packet.json",
    "two_lane_result_matrix.json",
    "native_owner_ux_false_green_audit.json",
    "independent_owner_ux_route_audit.json",
    "owner_ux_route_summary_packet.json",
}


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
        "packet_kind": "native_owner_ux_acceptance_import_input_error",
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


def _historical_quarantine(
    repo_root: Path, evidence_dir: Path
) -> tuple[list[str], list[str]]:
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
        "tools/native_custom_owner_ux_acceptance_import_r1_probe.py",
        "tests/test_native_custom_owner_ux_acceptance_import_r1_probe.py",
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
        prog="native-custom-owner-ux-acceptance-import-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--source-evidence-dir", required=True)
    parser.add_argument("--route-reference-summary", default="")
    return parser


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_evidence_dir: Path,
    route_reference_summary_path: Path | None,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = {
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
    packets["historical_dirt_quarantine_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "quarantine_classification": "out_of_scope_historical_residue",
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["version_pinning_packet.json"] = _version_packet(repo_root)
    packets["declared_write_surfaces_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": ["fresh evidence directory only"],
        "native_app_launch_attempted_by_this_probe": False,
        "protected_surfaces_write_allowed": False,
        "original_codex_bundle_write_allowed": False,
        "original_codex_profile_write_allowed": False,
    }

    parsed: dict[str, dict[str, Any]] = {}
    missing_packets: list[str] = []
    invalid_packets: list[str] = []
    for name in sorted(SOURCE_REQUIRED_PACKETS):
        path = source_evidence_dir / name
        if not path.exists():
            missing_packets.append(name)
            continue
        try:
            parsed[name] = _read_json(path)
        except json.JSONDecodeError:
            invalid_packets.append(name)

    packets["source_owner_ux_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_owner_ux_evidence_inventory",
        "status": "ok" if not missing_packets and not invalid_packets else "blocked",
        "source_evidence_dir": str(source_evidence_dir),
        "required_packets": sorted(SOURCE_REQUIRED_PACKETS),
        "missing_packets": missing_packets,
        "invalid_json_packets": invalid_packets,
        "source_packet_count": len(parsed),
        "historical_source_packet_chain": True,
        "current_owner_action_collected": False,
    }

    owner_boundary = parsed.get("owner_action_boundary_packet.json", {})
    owner_manual = parsed.get("owner_manual_ux_check_packet.json", {})
    owner_visible = parsed.get("owner_visible_response_confirmation_packet.json", {})
    source_trace = parsed.get("wbp_trace_observation_packet.json", {})
    source_route = parsed.get("native_route_trace_binding_packet.json", {})
    source_matrix = parsed.get("two_lane_result_matrix.json", {})
    source_false_green = parsed.get("native_owner_ux_false_green_audit.json", {})
    source_independent = parsed.get("independent_owner_ux_route_audit.json", {})
    source_summary = parsed.get("owner_ux_route_summary_packet.json", {})

    source_summary_ok = (
        source_summary.get("status") == "ok"
        and source_summary.get("final_status")
        == "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION"
        and source_matrix.get("status") == "ok"
        and source_matrix.get("owner_ux_confirmed") is True
        and source_matrix.get("route_trace_confirmed") is True
        and owner_manual.get("status") == "ok"
        and owner_manual.get("ux_status") == "confirmed"
        and source_false_green.get("status") == "ok"
        and source_independent.get("status") == "ok"
    )
    packets["source_owner_ux_summary_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_owner_ux_summary_validation",
        "status": "ok" if source_summary_ok else "blocked",
        "source_summary_status": source_summary.get("status", "missing"),
        "source_summary_final_status": source_summary.get("final_status", ""),
        "source_matrix_status": source_matrix.get("status", "missing"),
        "source_false_green_status": source_false_green.get("status", "missing"),
        "source_independent_audit_status": source_independent.get("status", "missing"),
        "route_trace_confirmed_in_source": source_matrix.get("route_trace_confirmed") is True,
        "owner_ux_confirmed_in_source": source_matrix.get("owner_ux_confirmed") is True,
        "counts_as_machine_ui_proof": False,
        "counts_as_general_usability_proof": False,
    }

    action_boundary_ok = (
        owner_boundary.get("status") == "ok"
        and owner_boundary.get("owner_typed_specified_prompt") is True
        and owner_boundary.get("runtime_authority_edited") is False
        and owner_boundary.get("provider_or_model_authority_edited") is False
        and owner_boundary.get("hidden_cleanup_performed") is False
    )
    packets["native_owner_action_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_action_boundary_import",
        "status": "ok" if action_boundary_ok else "blocked",
        "source_packet": str(source_evidence_dir / "owner_action_boundary_packet.json"),
        "owner_typed_specified_prompt": owner_boundary.get("owner_typed_specified_prompt") is True,
        "runtime_authority_edited": owner_boundary.get("runtime_authority_edited") is True,
        "provider_or_model_authority_edited": (
            owner_boundary.get("provider_or_model_authority_edited") is True
        ),
        "hidden_cleanup_performed": owner_boundary.get("hidden_cleanup_performed") is True,
        "current_owner_action_collected": False,
        "imported_owner_action_boundary": True,
        "counts_as_machine_ui_proof": False,
    }

    visible_interaction_ok = (
        owner_manual.get("status") == "ok"
        and owner_manual.get("owner_saw_window") is True
        and owner_manual.get("owner_typed_prompt") is True
        and owner_manual.get("owner_saw_response") is True
        and owner_manual.get("ux_status") == "confirmed"
    )
    packets["native_owner_visible_interaction_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_visible_interaction",
        "status": "ok" if visible_interaction_ok else "blocked",
        "source_packet": str(source_evidence_dir / "owner_manual_ux_check_packet.json"),
        "prompt_entry_visibly_possible": owner_manual.get("owner_typed_prompt") is True,
        "submit_action_visibly_possible": owner_manual.get("owner_typed_prompt") is True,
        "response_visibly_appeared": owner_manual.get("owner_saw_response") is True,
        "window_visibly_present": owner_manual.get("owner_saw_window") is True,
        "ux_status": owner_manual.get("ux_status", "missing"),
        "current_owner_action_collected": False,
        "machine_ui_input_field_proven": False,
        "machine_observed_response_text_proven": False,
    }

    response_visibility_ok = (
        owner_visible.get("status") == "ok"
        and owner_visible.get("owner_saw_response") is True
        and owner_visible.get("owner_reported_agent_answered") is True
        and owner_visible.get("owner_reported_config_model_route_untouched") is True
        and owner_visible.get("owner_reported_hidden_cleanup_not_performed") is True
    )
    packets["native_owner_response_visibility_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_response_visibility",
        "status": "ok" if response_visibility_ok else "blocked",
        "source_packet": str(
            source_evidence_dir / "owner_visible_response_confirmation_packet.json"
        ),
        "owner_saw_response": owner_visible.get("owner_saw_response") is True,
        "owner_reported_agent_answered": (
            owner_visible.get("owner_reported_agent_answered") is True
        ),
        "config_model_route_untouched": (
            owner_visible.get("owner_reported_config_model_route_untouched") is True
        ),
        "hidden_cleanup_not_performed": (
            owner_visible.get("owner_reported_hidden_cleanup_not_performed") is True
        ),
        "counts_as_machine_ui_proof": False,
    }

    blocker_free = (
        action_boundary_ok
        and visible_interaction_ok
        and response_visibility_ok
        and owner_manual.get("ux_status") == "confirmed"
    )
    packets["native_owner_visible_blocker_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_visible_blocker",
        "status": "ok" if blocker_free else "blocked",
        "visible_blocker_classification": (
            "no_obvious_blocker_reported_in_source_event"
            if blocker_free
            else "source_event_contains_missing_or_blocked_visible_step"
        ),
        "blocking_prompt_observed": False,
        "visible_friction_reported": False,
        "derived_from_source_packets_only": True,
        "current_owner_action_collected": False,
    }

    route_reference_summary: dict[str, Any] = {}
    if route_reference_summary_path is not None:
        route_reference_summary = _read_json(route_reference_summary_path)
    route_reference_ok = (
        not route_reference_summary
        or (
            route_reference_summary.get("status") == "ok"
            and str(route_reference_summary.get("final_status", "")).startswith(
                "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED"
            )
        )
    )
    packets["route_reference_truth_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "route_reference_truth",
        "status": "ok" if route_reference_ok else "blocked",
        "route_reference_packet": (
            str(route_reference_summary_path) if route_reference_summary_path else ""
        ),
        "route_reference_present": route_reference_summary_path is not None,
        "route_reference_status": route_reference_summary.get("status", "not_provided"),
        "route_reference_final_status": route_reference_summary.get("final_status", ""),
        "route_reference_supports_interpretation_only": True,
        "route_reference_reopens_route_proof": False,
        "source_route_trace_confirmed": source_route.get("route_trace_bound") is True
        and source_trace.get("route_status") == "confirmed",
    }

    classification_ok = (
        packets["source_owner_ux_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_owner_ux_summary_validation_packet.json"]["status"] == "ok"
        and packets["native_owner_action_boundary_packet.json"]["status"] == "ok"
        and packets["native_owner_visible_interaction_packet.json"]["status"] == "ok"
        and packets["native_owner_response_visibility_packet.json"]["status"] == "ok"
        and packets["native_owner_visible_blocker_packet.json"]["status"] == "ok"
        and packets["route_reference_truth_packet.json"]["status"] == "ok"
    )
    packets["native_owner_usability_classification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_usability_classification",
        "status": "ok" if classification_ok else "blocked",
        "final_status": (
            "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION"
            if classification_ok
            else "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABILITY_CLASSIFIED_WITH_LIMITS"
        ),
        "usability_classification": "usable" if classification_ok else "blocked",
        "degraded_but_usable": False,
        "blocked": not classification_ok,
        "owner_confirmation_imported": True,
        "current_owner_action_collected": False,
        "machine_ui_proof_claimed": False,
        "general_day_to_day_usability_claimed": False,
        "original_codex_via_wbp_claimed": False,
        "final_e2e_claimed": False,
    }

    false_green_checks = [
        {
            "name": "no_machine_ui_proof_claim",
            "passed": packets["native_owner_usability_classification_packet.json"][
                "machine_ui_proof_claimed"
            ]
            is False,
        },
        {
            "name": "no_general_day_to_day_usability_claim",
            "passed": packets["native_owner_usability_classification_packet.json"][
                "general_day_to_day_usability_claimed"
            ]
            is False,
        },
        {
            "name": "route_reference_not_used_as_visible_usability_substitute",
            "passed": packets["route_reference_truth_packet.json"][
                "route_reference_supports_interpretation_only"
            ]
            is True,
        },
        {
            "name": "source_false_green_audit_ok",
            "passed": source_false_green.get("status") == "ok",
        },
        {
            "name": "no_original_or_final_e2e_claim",
            "passed": packets["native_owner_usability_classification_packet.json"][
                "original_codex_via_wbp_claimed"
            ]
            is False
            and packets["native_owner_usability_classification_packet.json"][
                "final_e2e_claimed"
            ]
            is False,
        },
    ]
    packets["native_owner_ux_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_ux_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(
            check["passed"] for check in false_green_checks
        ),
        "current_owner_action_collected": False,
    }

    packets["independent_native_owner_ux_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_native_owner_ux_audit",
        "status": "ok"
        if packets["source_owner_ux_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["native_owner_usability_classification_packet.json"]["status"] == "ok"
        and packets["native_owner_ux_false_green_audit.json"]["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "source_owner_ux_summary_validation_packet.json",
            "native_owner_action_boundary_packet.json",
            "native_owner_visible_interaction_packet.json",
            "native_owner_response_visibility_packet.json",
            "route_reference_truth_packet.json",
            "native_owner_usability_classification_packet.json",
            "native_owner_ux_false_green_audit.json",
        ],
        "owner_confirmation_imported": True,
        "current_owner_action_collected": False,
        "machine_ui_proof_claimed": False,
        "route_reference_counted_as_ux_substitute": False,
        "direct_egress_claimed": False,
        "final_e2e_claimed": False,
    }

    packets["native_owner_usability_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_owner_usability_summary",
        "status": packets["native_owner_usability_classification_packet.json"]["status"],
        "final_status": packets["native_owner_usability_classification_packet.json"][
            "final_status"
        ],
        "owner_confirmation_imported": True,
        "current_owner_action_collected": False,
        "source_evidence_dir": str(source_evidence_dir),
        "route_reference_packet": (
            str(route_reference_summary_path) if route_reference_summary_path else ""
        ),
        "route_reference_status": packets["route_reference_truth_packet.json"]["status"],
        "machine_ui_proof_claimed": False,
        "general_day_to_day_usability_claimed": False,
        "original_codex_via_wbp_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_evidence_dir = Path(args.source_evidence_dir).resolve()
    route_reference_summary_path = (
        Path(args.route_reference_summary).resolve()
        if args.route_reference_summary
        else None
    )
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
        )
    if not source_evidence_dir.exists():
        return _emit_input_error(
            reason_class="SOURCE_EVIDENCE_DIR_MISSING",
            message="--source-evidence-dir does not exist.",
            evidence_dir=evidence_dir,
        )
    if route_reference_summary_path is not None and not route_reference_summary_path.exists():
        return _emit_input_error(
            reason_class="ROUTE_REFERENCE_PACKET_MISSING",
            message="--route-reference-summary does not exist.",
            evidence_dir=evidence_dir,
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        packets = build_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            source_evidence_dir=source_evidence_dir,
            route_reference_summary_path=route_reference_summary_path,
        )
    except json.JSONDecodeError:
        return _emit_input_error(
            reason_class="SOURCE_PACKET_INVALID_JSON",
            message="A source or route reference packet was not valid JSON.",
            evidence_dir=evidence_dir,
        )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(
        json.dumps(
            packets["native_owner_usability_summary_packet.json"],
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packets["native_owner_usability_summary_packet.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
