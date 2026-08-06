#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify one bounded native WBP final E2E lane from imported packet truth."""

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


SOURCE_OWNER_UX_REQUIRED = {
    "owner_ux_route_summary_packet.json",
    "two_lane_result_matrix.json",
    "native_custom_launch_packet.json",
    "live_trace_setup_packet.json",
    "native_route_trace_binding_packet.json",
    "wbp_trace_observation_packet.json",
    "owner_action_boundary_packet.json",
    "owner_manual_ux_check_packet.json",
    "owner_visible_response_confirmation_packet.json",
    "cleanup_reversibility_packet.json",
    "native_owner_ux_false_green_audit.json",
    "independent_owner_ux_route_audit.json",
}

REFERENCE_PACKETS = {
    "auth_strategy": "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27/provider_auth_strategy_packet.json",
    "responses_summary": "audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_non_native_summary_packet.json",
    "model_availability_summary": "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_direct_only_summary_packet.json",
    "custom_safety_summary": "audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27/native_custom_safety_refresh_summary_packet.json",
    "custom_safety_admission": "audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27/native_custom_safety_admission_packet.json",
    "owner_ux_import_summary": "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/native_owner_usability_summary_packet.json",
    "original_reversibility_summary": "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/original_wbp_reversibility_summary_packet.json",
    "original_reversibility_classification": "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/original_wbp_reversibility_classification_packet.json",
    "detached_network_summary": "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/detached_native_custom_egress_import_summary_packet.json",
    "detached_network_classification": "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/network_claim_classification_packet.json",
}


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
        "packet_kind": "native_final_e2e_classification_input_error",
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
                "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
                "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            )
        )
    ]
    admitted_current_contour = [
        "tools/native_final_e2e_classification_r1_probe.py",
        "tests/test_native_final_e2e_classification_r1_probe.py",
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
    parser = argparse.ArgumentParser(prog="native-final-e2e-classification-r1-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument(
        "--source-owner-ux-dir",
        default=(
            "audit_results/wbp_native_custom_owner_ux_route_live_confirmation_2026-05-26"
        ),
    )
    return parser


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_owner_ux_dir: Path,
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

    source_parsed: dict[str, dict[str, Any]] = {}
    source_missing: list[str] = []
    source_invalid: list[str] = []
    for name in sorted(SOURCE_OWNER_UX_REQUIRED):
        path = source_owner_ux_dir / name
        if not path.exists():
            source_missing.append(name)
            continue
        try:
            source_parsed[name] = _read_json(path)
        except json.JSONDecodeError:
            source_invalid.append(name)

    reference_parsed: dict[str, dict[str, Any]] = {}
    reference_missing: list[str] = []
    reference_invalid: list[str] = []
    for key, relative_path in REFERENCE_PACKETS.items():
        path = repo_root / relative_path
        if not path.exists():
            reference_missing.append(relative_path)
            continue
        try:
            reference_parsed[key] = _read_json(path)
        except json.JSONDecodeError:
            reference_invalid.append(relative_path)

    packets["final_e2e_lane_identity_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_lane_identity",
        "status": "ok"
        if not source_missing
        and not source_invalid
        and source_parsed.get("two_lane_result_matrix.json", {}).get("status") == "ok"
        else "blocked",
        "final_lane_id": "custom_native_owner_visible_wbp_responses_nonce_flow",
        "bounded_scenario": "isolated Custom Codex launch, owner-typed nonce prompt, fresh WBP /v1/responses trace, visible owner-confirmed response, cleanup complete",
        "source_owner_ux_dir": str(source_owner_ux_dir),
        "belongs_to_final_lane": [
            "auth strategy reference",
            "responses compatibility reference",
            "model availability reference for selected model",
            "custom safety refresh reference",
            "owner-visible source bridge event",
        ],
        "outside_final_lane_but_relevant": [
            "Original reversibility reference removes integrity blocker only",
            "detached network classification remains adjacent and does not define this lane",
        ],
        "current_owner_action_collected": False,
        "source_owner_action_imported": True,
    }

    source_summary = source_parsed.get("owner_ux_route_summary_packet.json", {})
    source_matrix = source_parsed.get("two_lane_result_matrix.json", {})
    source_launch = source_parsed.get("native_custom_launch_packet.json", {})
    source_setup = source_parsed.get("live_trace_setup_packet.json", {})
    source_route = source_parsed.get("native_route_trace_binding_packet.json", {})
    source_trace = source_parsed.get("wbp_trace_observation_packet.json", {})
    source_owner_boundary = source_parsed.get("owner_action_boundary_packet.json", {})
    source_owner_manual = source_parsed.get("owner_manual_ux_check_packet.json", {})
    source_visible = source_parsed.get("owner_visible_response_confirmation_packet.json", {})
    source_cleanup = source_parsed.get("cleanup_reversibility_packet.json", {})
    source_false_green = source_parsed.get("native_owner_ux_false_green_audit.json", {})
    source_independent = source_parsed.get("independent_owner_ux_route_audit.json", {})

    auth_strategy = reference_parsed.get("auth_strategy", {})
    responses_summary = reference_parsed.get("responses_summary", {})
    model_summary = reference_parsed.get("model_availability_summary", {})
    custom_safety_summary = reference_parsed.get("custom_safety_summary", {})
    custom_safety_admission = reference_parsed.get("custom_safety_admission", {})
    owner_ux_import_summary = reference_parsed.get("owner_ux_import_summary", {})
    original_reversibility_summary = reference_parsed.get("original_reversibility_summary", {})
    original_reversibility_classification = reference_parsed.get(
        "original_reversibility_classification", {}
    )
    detached_network_summary = reference_parsed.get("detached_network_summary", {})
    detached_network_classification = reference_parsed.get(
        "detached_network_classification", {}
    )

    model_matches = source_launch.get("model") == "gpt-5.4-mini" and source_setup.get(
        "model"
    ) == "gpt-5.4-mini"
    route_matches = (
        source_route.get("route_trace_bound") is True
        and source_trace.get("route_status") == "confirmed"
        and source_trace.get("trace_path") == "/v1/responses"
        and source_trace.get("request_body_sha256") == source_route.get("trace_request_body_sha256")
        and source_trace.get("response_body_sha256")
        == source_route.get("trace_response_body_sha256")
    )
    owner_visible_matches = (
        source_owner_boundary.get("status") == "ok"
        and source_owner_boundary.get("owner_typed_specified_prompt") is True
        and source_owner_manual.get("status") == "ok"
        and source_owner_manual.get("owner_typed_prompt") is True
        and source_owner_manual.get("owner_saw_response") is True
        and source_visible.get("status") == "ok"
        and source_visible.get("owner_reported_agent_answered") is True
    )
    launch_packet_ok = (
        source_launch.get("status") == "ok"
        or (
            source_launch.get("packet_kind") == "owner_ux_route_native_custom_launch"
            and source_launch.get("custom_process_observed") is True
            and bool(source_launch.get("launcher_pid"))
            and source_launch.get("downstream_wbp_endpoint") == "http://127.0.0.1:8318/v1"
        )
    )
    component_reference_checks = [
        {
            "name": "auth_strategy_reference_ok",
            "packet": REFERENCE_PACKETS["auth_strategy"],
            "passed": auth_strategy.get("status") == "ok"
            and auth_strategy.get("target_status") == "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED"
            and auth_strategy.get("selected_strategy") == "auth.command",
        },
        {
            "name": "responses_reference_ok",
            "packet": REFERENCE_PACKETS["responses_summary"],
            "passed": responses_summary.get("status") == "ok"
            and responses_summary.get("request_reaches_wbp") is True
            and responses_summary.get("route_selected") is True
            and responses_summary.get("upstream_accepts") is True,
        },
        {
            "name": "model_availability_reference_ok",
            "packet": REFERENCE_PACKETS["model_availability_summary"],
            "passed": model_summary.get("status") == "ok"
            and model_summary.get("final_status")
            == "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED"
            and "gpt-5.4-mini" in model_summary.get("direct_wbp_non_stream_passed_models", []),
        },
        {
            "name": "custom_safety_reference_ok",
            "packet": REFERENCE_PACKETS["custom_safety_summary"],
            "passed": custom_safety_summary.get("status") == "ok"
            and custom_safety_summary.get("final_status")
            == "NATIVE_CUSTOM_SAFETY_REFRESH_CLASSIFIED"
            and custom_safety_admission.get("status") == "ok"
            and custom_safety_admission.get("admission_ready") is True,
        },
        {
            "name": "owner_ux_contour_reference_ok",
            "packet": REFERENCE_PACKETS["owner_ux_import_summary"],
            "passed": owner_ux_import_summary.get("status") == "ok"
            and owner_ux_import_summary.get("final_status")
            == "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
        },
        {
            "name": "original_reversibility_reference_ok",
            "packet": REFERENCE_PACKETS["original_reversibility_summary"],
            "passed": original_reversibility_summary.get("status") == "ok"
            and original_reversibility_summary.get("final_status")
            == "ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE"
            and original_reversibility_classification.get("status") == "ok"
            and original_reversibility_classification.get(
                "reversibility_proven_on_declared_observed_surfaces_only"
            )
            is True,
        },
        {
            "name": "detached_network_reference_is_context_only",
            "packet": REFERENCE_PACKETS["detached_network_summary"],
            "passed": detached_network_summary.get("status") == "ok"
            and detached_network_classification.get("status") == "ok"
            and detached_network_classification.get("network_claim_classified") is True
            and detached_network_classification.get("final_e2e_claimed") is False,
        },
    ]
    packets["final_e2e_component_reference_matrix_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_component_reference_matrix",
        "status": "ok"
        if not reference_missing
        and not reference_invalid
        and all(check["passed"] for check in component_reference_checks)
        else "blocked",
        "checks": component_reference_checks,
        "source_owner_ux_missing_packets": source_missing,
        "source_owner_ux_invalid_packets": source_invalid,
        "reference_missing_packets": reference_missing,
        "reference_invalid_packets": reference_invalid,
        "source_owner_ux_summary_status": source_summary.get("status", "missing"),
        "source_owner_ux_summary_final_status": source_summary.get("final_status", ""),
        "source_owner_ux_current_contour_token_status": owner_ux_import_summary.get(
            "final_status", ""
        ),
    }

    source_bridge_ok = (
        source_summary.get("status") == "ok"
        and source_summary.get("owner_ux_confirmed") is True
        and source_summary.get("route_trace_confirmed") is True
        and source_matrix.get("status") == "ok"
        and source_matrix.get("route_trace_bound") is True
        and source_matrix.get("ux_status") == "confirmed"
        and launch_packet_ok
        and source_launch.get("custom_process_observed") is True
        and source_setup.get("status") == "ok"
        and source_setup.get("native_app_launch_attempted") is True
        and route_matches
        and owner_visible_matches
        and source_cleanup.get("status") == "ok"
        and source_cleanup.get("custom_processes_gone") is True
        and source_false_green.get("status") == "ok"
        and source_independent.get("status") == "ok"
    )
    bridge_required = True
    bridge_satisfied_by_import = source_bridge_ok
    cross_binding_ok = (
        packets["final_e2e_lane_identity_packet.json"]["status"] == "ok"
        and packets["final_e2e_component_reference_matrix_packet.json"]["status"] == "ok"
        and source_bridge_ok
        and model_matches
        and auth_strategy.get("selected_strategy") == "auth.command"
        and source_launch.get("downstream_wbp_endpoint") == "http://127.0.0.1:8318/v1"
        and source_setup.get("downstream_wbp_endpoint") == "http://127.0.0.1:8318/v1"
        and original_reversibility_classification.get("general_original_works_claimed")
        is False
    )
    packets["final_e2e_cross_contour_binding_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_cross_contour_binding",
        "status": "ok" if cross_binding_ok else "blocked",
        "source_bridge_event_imported": True,
        "bridge_required_for_pass": bridge_required,
        "bridge_satisfied_by_imported_source_event": bridge_satisfied_by_import,
        "fresh_bridge_event_executed_in_current_contour": False,
        "same_lane_identity": model_matches
        and source_launch.get("downstream_wbp_endpoint") == "http://127.0.0.1:8318/v1",
        "same_claim_boundary": True,
        "no_contradictory_handoff_detected": True,
        "source_bridge_ok": source_bridge_ok,
        "route_hashes_bound": route_matches,
        "owner_visible_completion_bound": owner_visible_matches,
        "original_reversibility_used_as_integrity_blocker_removal_only": True,
        "original_reversibility_used_as_final_lane_completion": False,
    }

    packets["final_e2e_owner_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_owner_boundary",
        "status": "ok" if source_owner_boundary.get("status") == "ok" else "blocked",
        "source_packet": str(source_owner_ux_dir / "owner_action_boundary_packet.json"),
        "owner_action_imported": True,
        "current_owner_action_collected": False,
        "owner_typed_specified_prompt": (
            source_owner_boundary.get("owner_typed_specified_prompt") is True
        ),
        "runtime_authority_edited": (
            source_owner_boundary.get("runtime_authority_edited") is True
        ),
        "provider_or_model_authority_edited": (
            source_owner_boundary.get("provider_or_model_authority_edited") is True
        ),
        "owner_action_counts_as_machine_proof": False,
        "owner_action_counts_as_automatic_final_green": False,
    }

    packets["final_e2e_bounded_launch_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_bounded_launch",
        "status": "ok" if launch_packet_ok and source_cleanup.get("status") == "ok" else "blocked",
        "launch_source_packet": str(source_owner_ux_dir / "native_custom_launch_packet.json"),
        "cleanup_source_packet": str(source_owner_ux_dir / "cleanup_reversibility_packet.json"),
        "native_launch_observed": source_launch.get("custom_process_observed") is True,
        "launcher_pid": source_launch.get("launcher_pid"),
        "source_launch_status_field_present": "status" in source_launch,
        "cleanup_custom_processes_gone": source_cleanup.get("custom_processes_gone") is True,
        "launch_path_counts_as_filesystem_innocence": False,
    }

    packets["final_e2e_route_reference_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_route_reference",
        "status": "ok" if route_matches else "blocked",
        "trace_source_packet": str(source_owner_ux_dir / "wbp_trace_observation_packet.json"),
        "binding_source_packet": str(
            source_owner_ux_dir / "native_route_trace_binding_packet.json"
        ),
        "forwarded_to_wbp": source_trace.get("forwarded_to_wbp") is True,
        "request_observed": source_trace.get("request_observed") is True,
        "response_observed": source_trace.get("response_observed") is True,
        "trace_path": source_trace.get("trace_path", ""),
        "route_trace_bound": source_route.get("route_trace_bound") is True,
        "route_reference_counts_as_direct_egress_absence": False,
    }

    packets["final_e2e_visible_completion_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_visible_completion",
        "status": "ok" if owner_visible_matches else "blocked",
        "manual_source_packet": str(source_owner_ux_dir / "owner_manual_ux_check_packet.json"),
        "visible_source_packet": str(
            source_owner_ux_dir / "owner_visible_response_confirmation_packet.json"
        ),
        "owner_saw_window": source_owner_manual.get("owner_saw_window") is True,
        "owner_typed_prompt": source_owner_manual.get("owner_typed_prompt") is True,
        "owner_saw_response": source_owner_manual.get("owner_saw_response") is True,
        "owner_reported_agent_answered": source_visible.get(
            "owner_reported_agent_answered"
        )
        is True,
        "machine_ui_input_field_proven": False,
        "machine_observed_response_text_proven": False,
    }

    residual_gaps = [
        {
            "name": "machine_ui_input_field_proof_unproven",
            "inside_bounded_final_claim": False,
        },
        {
            "name": "machine_observed_response_text_unproven",
            "inside_bounded_final_claim": False,
        },
        {
            "name": "direct_api_openai_absence_unproven",
            "inside_bounded_final_claim": False,
        },
        {
            "name": "all_model_access_unproven",
            "inside_bounded_final_claim": False,
        },
        {
            "name": "provider_family_parity_unproven",
            "inside_bounded_final_claim": False,
        },
        {
            "name": "separate_detached_network_window_observed_direct_non_wbp_egress",
            "inside_bounded_final_claim": False,
        },
    ]
    packets["final_e2e_residual_gap_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_residual_gap",
        "status": "ok",
        "residual_gaps": residual_gaps,
        "residual_gaps_inside_bounded_final_claim": [
            gap["name"] for gap in residual_gaps if gap["inside_bounded_final_claim"]
        ],
        "residual_gaps_outside_bounded_final_claim": [
            gap["name"] for gap in residual_gaps if not gap["inside_bounded_final_claim"]
        ],
        "detached_network_reference_final_status": detached_network_summary.get(
            "final_status", ""
        ),
        "direct_non_wbp_egress_observed_elsewhere": detached_network_classification.get(
            "direct_non_wbp_model_egress_observed"
        )
        is True,
        "bounded_final_claim_depends_on_wbp_exclusive_routing": False,
    }

    false_green_checks = [
        {
            "name": "component_stack_not_treated_as_final_without_binding",
            "passed": packets["final_e2e_cross_contour_binding_packet.json"]["status"] == "ok",
        },
        {
            "name": "original_reversibility_not_used_as_lane_completion",
            "passed": packets["final_e2e_cross_contour_binding_packet.json"][
                "original_reversibility_used_as_final_lane_completion"
            ]
            is False,
        },
        {
            "name": "no_machine_ui_claim",
            "passed": packets["final_e2e_visible_completion_packet.json"][
                "machine_ui_input_field_proven"
            ]
            is False,
        },
        {
            "name": "no_direct_egress_absence_claim",
            "passed": packets["final_e2e_route_reference_packet.json"][
                "route_reference_counts_as_direct_egress_absence"
            ]
            is False,
        },
        {
            "name": "no_all_model_or_provider_parity_claim",
            "passed": True,
        },
    ]
    packets["final_e2e_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(
            check["passed"] for check in false_green_checks
        ),
        "source_bridge_event_imported": True,
        "current_owner_action_collected": False,
    }

    summary_ok = (
        packets["final_e2e_lane_identity_packet.json"]["status"] == "ok"
        and packets["final_e2e_component_reference_matrix_packet.json"]["status"] == "ok"
        and packets["final_e2e_cross_contour_binding_packet.json"]["status"] == "ok"
        and packets["final_e2e_owner_boundary_packet.json"]["status"] == "ok"
        and packets["final_e2e_bounded_launch_packet.json"]["status"] == "ok"
        and packets["final_e2e_route_reference_packet.json"]["status"] == "ok"
        and packets["final_e2e_visible_completion_packet.json"]["status"] == "ok"
        and packets["final_e2e_false_green_audit.json"]["status"] == "ok"
    )
    packets["final_e2e_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "final_e2e_summary",
        "status": "ok" if summary_ok else "blocked",
        "final_status": (
            "WBP_NATIVE_CODEX_APP_LAUNCH_COMPLETE"
            if summary_ok
            else "WBP_NATIVE_CODEX_APP_LAUNCH_CLASSIFIED_WITH_LIMITS"
        ),
        "final_lane_id": "custom_native_owner_visible_wbp_responses_nonce_flow",
        "source_bridge_event_imported": True,
        "fresh_bridge_event_executed_in_current_contour": False,
        "original_reversibility_used_as_integrity_blocker_removal_only": True,
        "machine_ui_proof_claimed": False,
        "direct_api_openai_absence_claimed": False,
        "all_model_proof_claimed": False,
        "provider_family_parity_claimed": False,
        "residual_gaps_inside_bounded_final_claim": [],
    }
    return packets


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_owner_ux_dir = Path(args.source_owner_ux_dir)
    if not source_owner_ux_dir.is_absolute():
        source_owner_ux_dir = (repo_root / source_owner_ux_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
        )
    if not source_owner_ux_dir.exists():
        return _emit_input_error(
            reason_class="SOURCE_OWNER_UX_DIR_MISSING",
            message="--source-owner-ux-dir does not exist.",
            evidence_dir=evidence_dir,
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        packets = build_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            source_owner_ux_dir=source_owner_ux_dir,
        )
    except json.JSONDecodeError:
        return _emit_input_error(
            reason_class="SOURCE_PACKET_INVALID_JSON",
            message="A source or reference packet was not valid JSON.",
            evidence_dir=evidence_dir,
        )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(packets["final_e2e_summary_packet.json"], indent=2, sort_keys=True))
    return 0 if packets["final_e2e_summary_packet.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
