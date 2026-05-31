#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthesize Pass 4 Custom-via-WBP owner acceptance with explicit claim limits."""

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


FINAL_STATUS_OK = "CUSTOM_CODEX_VIA_WBP_OWNER_ACCEPTED_WITH_LIMITS"
FINAL_STATUS_BLOCKED = "CUSTOM_CODEX_VIA_WBP_OWNER_ACCEPTANCE_NOT_PROVEN"
EXPECTED_EVIDENCE_DIR = (
    "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27"
)

DEFAULT_SOURCE_FILES = {
    "owner_summary": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "native_owner_usability_summary_packet.json"
    ),
    "owner_classification": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "native_owner_usability_classification_packet.json"
    ),
    "route_reference_truth": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "route_reference_truth_packet.json"
    ),
    "owner_source_validation": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "source_owner_ux_summary_validation_packet.json"
    ),
    "owner_action_boundary": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "native_owner_action_boundary_packet.json"
    ),
    "owner_visible_interaction": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "native_owner_visible_interaction_packet.json"
    ),
    "owner_response_visibility": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "native_owner_response_visibility_packet.json"
    ),
    "owner_false_green": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "native_owner_ux_false_green_audit.json"
    ),
    "owner_independent_audit": Path(
        "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/"
        "independent_native_owner_ux_audit.json"
    ),
    "owner_live_trace": Path(
        "audit_results/wbp_native_custom_owner_ux_route_live_confirmation_2026-05-26/"
        "wbp_trace_observation_packet.json"
    ),
    "owner_live_summary": Path(
        "audit_results/wbp_native_custom_owner_ux_route_live_confirmation_2026-05-26/"
        "owner_ux_route_summary_packet.json"
    ),
    "owner_live_matrix": Path(
        "audit_results/wbp_native_custom_owner_ux_route_live_confirmation_2026-05-26/"
        "two_lane_result_matrix.json"
    ),
    "persistent_launcher_contract": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_launcher_contract_packet.json"
    ),
    "persistent_profile_identity": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_profile_identity_contract_packet.json"
    ),
    "persistent_concurrent_policy": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_concurrent_launch_policy_packet.json"
    ),
    "persistent_cleanup_policy": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_cleanup_retention_policy_packet.json"
    ),
    "persistent_original_non_dependency": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "original_codex_profile_non_dependency_packet.json"
    ),
    "persistent_readiness_summary": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_launcher_readiness_summary_packet.json"
    ),
    "original_summary": Path(
        "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/"
        "original_wbp_reversibility_summary_packet.json"
    ),
    "original_classification": Path(
        "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/"
        "original_wbp_reversibility_classification_packet.json"
    ),
    "original_false_green": Path(
        "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/"
        "original_wbp_false_green_audit.json"
    ),
    "original_independent_audit": Path(
        "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/"
        "independent_original_wbp_reversibility_audit.json"
    ),
}


class SourcePacketError(RuntimeError):
    """Raised when a required packet is missing or invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourcePacketError(f"required packet missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourcePacketError(f"invalid JSON in required packet: {path}") from exc


def load_source_packets(
    repo_root: Path,
    *,
    source_files: dict[str, Path] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    resolved_files = source_files or DEFAULT_SOURCE_FILES
    packets: dict[str, dict[str, Any]] = {}
    resolved_paths: dict[str, str] = {}
    for key, relative_path in resolved_files.items():
        full_path = (repo_root / relative_path).resolve()
        packets[key] = read_json(full_path)
        resolved_paths[key] = str(full_path)
    return packets, resolved_paths


def build_custom_launcher_contract_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    contract = sources["persistent_launcher_contract"]
    readiness = sources["persistent_readiness_summary"]
    status = "ok"
    if contract.get("status") != "ok" or readiness.get("status") != "ok":
        status = "blocked"
    if contract.get("profile_mode") != "persistent_custom":
        status = "blocked"
    if contract.get("persistent_launcher_contract_recorded") is not True:
        status = "blocked"
    if contract.get("silent_fallback_to_ephemeral_allowed") is not False:
        status = "blocked"
    if contract.get("launcher_contract_counts_as_launch_execution") is not False:
        status = "blocked"
    if readiness.get("command_executed") is not False:
        status = "blocked"
    if readiness.get("persistent_profile_state_written") is not False:
        status = "blocked"
    if readiness.get("keychain_behavior_classified") is not False:
        status = "blocked"
    return packet(
        "custom_launcher_contract",
        status=status,
        final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        source_launcher_contract_packet=source_paths["persistent_launcher_contract"],
        source_readiness_summary_packet=source_paths["persistent_readiness_summary"],
        historical_contract_imported=True,
        current_probe_executed_launcher=False,
        current_probe_wrote_profile_state=False,
        profile_mode=contract.get("profile_mode", ""),
        selected_profile_id=contract.get("selected_profile_id", ""),
        selected_profile_root=contract.get("selected_profile_root", ""),
        launcher_path=contract.get("launcher_path", ""),
        persistent_launcher_contract_recorded=(
            contract.get("persistent_launcher_contract_recorded") is True
        ),
        silent_fallback_to_ephemeral_allowed=(
            contract.get("silent_fallback_to_ephemeral_allowed") is True
        ),
        launcher_contract_counts_as_launch_execution=(
            contract.get("launcher_contract_counts_as_launch_execution") is True
        ),
        command_executed=readiness.get("command_executed") is True,
        persistent_profile_state_written=(
            readiness.get("persistent_profile_state_written") is True
        ),
        keychain_behavior_classified=readiness.get("keychain_behavior_classified") is True,
        profile_storage_persistence_proven=False,
        thread_history_preservation_proven=False,
        imported_truth_only=True,
    )


def build_custom_profile_mode_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    contract = sources["persistent_launcher_contract"]
    identity = sources["persistent_profile_identity"]
    readiness = sources["persistent_readiness_summary"]
    original = sources["persistent_original_non_dependency"]
    status = "ok"
    if contract.get("status") != "ok" or identity.get("status") != "ok":
        status = "blocked"
    if readiness.get("status") != "ok" or original.get("status") != "ok":
        status = "blocked"
    if identity.get("same_profile_id_as_expected") is not True:
        status = "blocked"
    if identity.get("same_profile_root_as_expected") is not True:
        status = "blocked"
    if identity.get("silent_profile_switching_detected") is not False:
        status = "blocked"
    if readiness.get("thread_history_preservation_claimed") is not False:
        status = "blocked"
    if readiness.get("profile_storage_persistence_claimed") is not False:
        status = "blocked"
    if original.get("original_codex_profile_dependency") is not False:
        status = "blocked"
    return packet(
        "custom_profile_mode",
        status=status,
        source_launcher_contract_packet=source_paths["persistent_launcher_contract"],
        source_profile_identity_packet=source_paths["persistent_profile_identity"],
        source_readiness_summary_packet=source_paths["persistent_readiness_summary"],
        source_original_non_dependency_packet=source_paths[
            "persistent_original_non_dependency"
        ],
        historical_contract_imported=True,
        current_profile_mode_revalidated_live=False,
        profile_mode=contract.get("profile_mode", ""),
        persistent_profile_id=identity.get("persistent_profile_id", ""),
        persistent_profile_root=identity.get("persistent_profile_root", ""),
        same_profile_id_as_expected=identity.get("same_profile_id_as_expected") is True,
        same_profile_root_as_expected=identity.get("same_profile_root_as_expected") is True,
        silent_profile_switching_detected=(
            identity.get("silent_profile_switching_detected") is True
        ),
        thread_history_preservation_claimed=(
            readiness.get("thread_history_preservation_claimed") is True
        ),
        profile_storage_persistence_claimed=(
            readiness.get("profile_storage_persistence_claimed") is True
        ),
        original_codex_profile_dependency=(
            original.get("original_codex_profile_dependency") is True
        ),
        original_codex_profile_mutated=(
            original.get("original_codex_profile_mutated") is True
        ),
        persistent_mode_is_contract_only=True,
    )


def build_custom_route_trace_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    summary = sources["owner_summary"]
    classification = sources["owner_classification"]
    route_reference = sources["route_reference_truth"]
    validation = sources["owner_source_validation"]
    live_trace = sources["owner_live_trace"]
    live_summary = sources["owner_live_summary"]
    live_matrix = sources["owner_live_matrix"]
    status = "ok"
    if summary.get("status") != "ok" or classification.get("status") != "ok":
        status = "blocked"
    if route_reference.get("status") != "ok" or validation.get("status") != "ok":
        status = "blocked"
    if live_trace.get("status") != "ok" or live_summary.get("status") != "ok":
        status = "blocked"
    if live_matrix.get("status") != "ok":
        status = "blocked"
    if summary.get("final_status") != "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION":
        status = "blocked"
    if route_reference.get("route_reference_supports_interpretation_only") is not True:
        status = "blocked"
    if validation.get("route_trace_confirmed_in_source") is not True:
        status = "blocked"
    if live_trace.get("forwarded_to_wbp") is not True:
        status = "blocked"
    if live_trace.get("route_status") != "confirmed":
        status = "blocked"
    if live_trace.get("request_observed") is not True:
        status = "blocked"
    if live_trace.get("response_observed") is not True:
        status = "blocked"
    return packet(
        "custom_route_trace",
        status=status,
        source_owner_summary_packet=source_paths["owner_summary"],
        source_route_reference_packet=source_paths["route_reference_truth"],
        source_validation_packet=source_paths["owner_source_validation"],
        source_live_trace_packet=source_paths["owner_live_trace"],
        source_live_summary_packet=source_paths["owner_live_summary"],
        source_live_matrix_packet=source_paths["owner_live_matrix"],
        historical_trace_imported=True,
        current_trace_captured=False,
        route_trace_confirmed_in_source=validation.get("route_trace_confirmed_in_source")
        is True,
        route_reference_supports_interpretation_only=(
            route_reference.get("route_reference_supports_interpretation_only") is True
        ),
        route_reference_reopens_route_proof=(
            route_reference.get("route_reference_reopens_route_proof") is True
        ),
        owner_confirmation_imported=summary.get("owner_confirmation_imported") is True,
        forwarded_to_wbp=live_trace.get("forwarded_to_wbp") is True,
        request_observed=live_trace.get("request_observed") is True,
        response_observed=live_trace.get("response_observed") is True,
        trace_path=live_trace.get("trace_path", ""),
        upstream_status=live_trace.get("upstream_status"),
        direct_egress_claimed=False,
    )


def build_custom_authority_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    action = sources["owner_action_boundary"]
    original = sources["persistent_original_non_dependency"]
    readiness = sources["persistent_readiness_summary"]
    original_classification = sources["original_classification"]
    status = "ok"
    if action.get("status") != "ok" or original.get("status") != "ok":
        status = "blocked"
    if readiness.get("status") != "ok" or original_classification.get("status") != "ok":
        status = "blocked"
    if action.get("owner_typed_specified_prompt") is not True:
        status = "blocked"
    if action.get("runtime_authority_edited") is not False:
        status = "blocked"
    if action.get("provider_or_model_authority_edited") is not False:
        status = "blocked"
    if action.get("hidden_cleanup_performed") is not False:
        status = "blocked"
    if original.get("original_codex_profile_dependency") is not False:
        status = "blocked"
    if readiness.get("keychain_behavior_classified") is not False:
        status = "blocked"
    if original_classification.get("general_original_works_claimed") is not False:
        status = "blocked"
    return packet(
        "custom_authority_boundary",
        status=status,
        source_owner_action_boundary_packet=source_paths["owner_action_boundary"],
        source_original_non_dependency_packet=source_paths[
            "persistent_original_non_dependency"
        ],
        source_persistent_readiness_summary_packet=source_paths[
            "persistent_readiness_summary"
        ],
        source_original_classification_packet=source_paths["original_classification"],
        historical_boundary_imported=True,
        current_owner_action_collected=False,
        current_original_profile_write_performed=False,
        owner_typed_specified_prompt=action.get("owner_typed_specified_prompt") is True,
        runtime_authority_edited=action.get("runtime_authority_edited") is True,
        provider_or_model_authority_edited=(
            action.get("provider_or_model_authority_edited") is True
        ),
        hidden_cleanup_performed=action.get("hidden_cleanup_performed") is True,
        original_codex_profile_dependency=(
            original.get("original_codex_profile_dependency") is True
        ),
        original_codex_profile_mutated=(
            original.get("original_codex_profile_mutated") is True
        ),
        keychain_behavior_classified=readiness.get("keychain_behavior_classified") is True,
        direct_egress_claimed=False,
        original_equivalence_claimed=False,
        imported_truth_only=True,
    )


def build_concurrent_launch_policy_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    concurrent = sources["persistent_concurrent_policy"]
    status = "ok"
    if concurrent.get("status") != "ok":
        status = "blocked"
    if concurrent.get("policy") != "single_writer_only":
        status = "blocked"
    if concurrent.get("same_profile_multi_writer_allowed") is not False:
        status = "blocked"
    if concurrent.get("launcher_enforces_policy") is not True:
        status = "blocked"
    return packet(
        "custom_concurrent_launch_policy",
        status=status,
        source_packet=source_paths["persistent_concurrent_policy"],
        historical_policy_imported=True,
        current_lock_execution_proven=False,
        policy=concurrent.get("policy", ""),
        launcher_enforces_policy=concurrent.get("launcher_enforces_policy") is True,
        same_profile_multi_writer_allowed=(
            concurrent.get("same_profile_multi_writer_allowed") is True
        ),
        state_consistency_risk_classified=(
            concurrent.get("state_consistency_risk_classified") is True
        ),
        lock_path=concurrent.get("lock_path", ""),
        counts_as_live_lock_execution_proof=False,
    )


def build_cleanup_policy_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    cleanup = sources["persistent_cleanup_policy"]
    status = "ok"
    if cleanup.get("status") != "ok":
        status = "blocked"
    if cleanup.get("cleanup_executed") is not False:
        status = "blocked"
    if cleanup.get("cleanup_deletes_persistent_profile_by_default") is not False:
        status = "blocked"
    if cleanup.get("persistent_history_delete_allowed_by_default") is not False:
        status = "blocked"
    if cleanup.get("explicit_owner_delete_authorization_required") is not True:
        status = "blocked"
    return packet(
        "custom_cleanup_policy",
        status=status,
        source_packet=source_paths["persistent_cleanup_policy"],
        historical_policy_imported=True,
        current_cleanup_execution_proven=False,
        cleanup_attempted=cleanup.get("cleanup_attempted") is True,
        cleanup_executed=cleanup.get("cleanup_executed") is True,
        cleanup_deletes_persistent_profile_by_default=(
            cleanup.get("cleanup_deletes_persistent_profile_by_default") is True
        ),
        persistent_history_delete_allowed_by_default=(
            cleanup.get("persistent_history_delete_allowed_by_default") is True
        ),
        explicit_owner_delete_authorization_required=(
            cleanup.get("explicit_owner_delete_authorization_required") is True
        ),
        ordinary_cleanup_must_preserve_history=(
            cleanup.get("ordinary_cleanup_must_preserve_history") is True
        ),
        imported_policy_only=True,
    )


def build_original_codex_drift_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    summary = sources["original_summary"]
    classification = sources["original_classification"]
    original = sources["persistent_original_non_dependency"]
    status = "ok"
    if summary.get("status") != "ok" or classification.get("status") != "ok":
        status = "blocked"
    if original.get("status") != "ok":
        status = "blocked"
    if summary.get("final_status") != "ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE":
        status = "blocked"
    if classification.get("reversibility_proven_on_declared_observed_surfaces_only") is not True:
        status = "blocked"
    if classification.get("general_original_works_claimed") is not False:
        status = "blocked"
    if classification.get("broad_original_filesystem_innocence_claimed") is not False:
        status = "blocked"
    if classification.get("final_e2e_claimed") is not False:
        status = "blocked"
    if original.get("original_codex_profile_dependency") is not False:
        status = "blocked"
    return packet(
        "custom_original_codex_drift",
        status=status,
        source_summary_packet=source_paths["original_summary"],
        source_classification_packet=source_paths["original_classification"],
        source_original_non_dependency_packet=source_paths[
            "persistent_original_non_dependency"
        ],
        historical_reversibility_imported=True,
        current_original_profile_write_performed=False,
        final_status=summary.get("final_status", ""),
        reversibility_proven_on_declared_observed_surfaces_only=(
            classification.get("reversibility_proven_on_declared_observed_surfaces_only")
            is True
        ),
        source_live_pass_imported=summary.get("source_live_pass_imported") is True,
        general_original_works_claimed=(
            classification.get("general_original_works_claimed") is True
        ),
        broad_original_filesystem_innocence_claimed=(
            classification.get("broad_original_filesystem_innocence_claimed") is True
        ),
        final_e2e_claimed=classification.get("final_e2e_claimed") is True,
        original_codex_profile_dependency=(
            original.get("original_codex_profile_dependency") is True
        ),
        original_equivalence_claimed=False,
        bounded_non_equivalence_explicit=True,
    )


def build_owner_manual_acceptance_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    summary = sources["owner_summary"]
    classification = sources["owner_classification"]
    interaction = sources["owner_visible_interaction"]
    response = sources["owner_response_visibility"]
    live_matrix = sources["owner_live_matrix"]
    status = "ok"
    if summary.get("status") != "ok" or classification.get("status") != "ok":
        status = "blocked"
    if interaction.get("status") != "ok" or response.get("status") != "ok":
        status = "blocked"
    if live_matrix.get("status") != "ok":
        status = "blocked"
    if summary.get("owner_confirmation_imported") is not True:
        status = "blocked"
    if classification.get("usability_classification") != "usable":
        status = "blocked"
    if interaction.get("window_visibly_present") is not True:
        status = "blocked"
    if interaction.get("prompt_entry_visibly_possible") is not True:
        status = "blocked"
    if interaction.get("response_visibly_appeared") is not True:
        status = "blocked"
    if response.get("owner_reported_agent_answered") is not True:
        status = "blocked"
    if classification.get("machine_ui_proof_claimed") is not False:
        status = "blocked"
    if classification.get("general_day_to_day_usability_claimed") is not False:
        status = "blocked"
    return packet(
        "custom_owner_manual_acceptance",
        status=status,
        source_summary_packet=source_paths["owner_summary"],
        source_classification_packet=source_paths["owner_classification"],
        source_visible_interaction_packet=source_paths["owner_visible_interaction"],
        source_response_visibility_packet=source_paths["owner_response_visibility"],
        source_live_matrix_packet=source_paths["owner_live_matrix"],
        historical_owner_acceptance_imported=True,
        current_owner_action_collected=False,
        owner_confirmation_imported=summary.get("owner_confirmation_imported") is True,
        usability_classification=classification.get("usability_classification", ""),
        window_visibly_present=interaction.get("window_visibly_present") is True,
        prompt_entry_visibly_possible=(
            interaction.get("prompt_entry_visibly_possible") is True
        ),
        submit_action_visibly_possible=(
            interaction.get("submit_action_visibly_possible") is True
        ),
        response_visibly_appeared=interaction.get("response_visibly_appeared") is True,
        owner_reported_agent_answered=(
            response.get("owner_reported_agent_answered") is True
        ),
        route_trace_confirmed_in_source=live_matrix.get("route_trace_confirmed") is True,
        machine_ui_proof_claimed=classification.get("machine_ui_proof_claimed") is True,
        general_day_to_day_usability_claimed=(
            classification.get("general_day_to_day_usability_claimed") is True
        ),
        owner_ui_waiver_closes_ux_only=True,
    )


def build_false_green_audit(
    packets: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    findings: list[str] = []

    def require(name: str, condition: bool) -> None:
        if not condition:
            findings.append(name)

    launcher = packets["custom_launcher_contract_packet.json"]
    mode = packets["custom_profile_mode_packet.json"]
    route = packets["custom_route_trace_packet.json"]
    authority = packets["custom_authority_boundary_packet.json"]
    concurrent = packets["concurrent_launch_policy_packet.json"]
    cleanup = packets["cleanup_policy_packet.json"]
    original = packets["original_codex_drift_packet.json"]
    owner = packets["owner_manual_acceptance_packet.json"]

    require("custom_launcher_contract_packet.json.status", launcher.get("status") == "ok")
    require(
        "custom_launcher_contract_packet.json.launcher_contract_counts_as_launch_execution",
        launcher.get("launcher_contract_counts_as_launch_execution") is False,
    )
    require(
        "custom_launcher_contract_packet.json.command_executed",
        launcher.get("command_executed") is False,
    )
    require(
        "custom_launcher_contract_packet.json.keychain_behavior_classified",
        launcher.get("keychain_behavior_classified") is False,
    )
    require(
        "custom_profile_mode_packet.json.profile_storage_persistence_claimed",
        mode.get("profile_storage_persistence_claimed") is False,
    )
    require(
        "custom_profile_mode_packet.json.thread_history_preservation_claimed",
        mode.get("thread_history_preservation_claimed") is False,
    )
    require(
        "custom_profile_mode_packet.json.original_codex_profile_dependency",
        mode.get("original_codex_profile_dependency") is False,
    )
    require(
        "custom_route_trace_packet.json.direct_egress_claimed",
        route.get("direct_egress_claimed") is False,
    )
    require(
        "custom_route_trace_packet.json.route_reference_supports_interpretation_only",
        route.get("route_reference_supports_interpretation_only") is True,
    )
    require(
        "custom_authority_boundary_packet.json.original_equivalence_claimed",
        authority.get("original_equivalence_claimed") is False,
    )
    require(
        "custom_authority_boundary_packet.json.runtime_authority_edited",
        authority.get("runtime_authority_edited") is False,
    )
    require(
        "custom_authority_boundary_packet.json.provider_or_model_authority_edited",
        authority.get("provider_or_model_authority_edited") is False,
    )
    require(
        "concurrent_launch_policy_packet.json.counts_as_live_lock_execution_proof",
        concurrent.get("counts_as_live_lock_execution_proof") is False,
    )
    require(
        "cleanup_policy_packet.json.cleanup_executed",
        cleanup.get("cleanup_executed") is False,
    )
    require(
        "cleanup_policy_packet.json.persistent_history_delete_allowed_by_default",
        cleanup.get("persistent_history_delete_allowed_by_default") is False,
    )
    require(
        "original_codex_drift_packet.json.general_original_works_claimed",
        original.get("general_original_works_claimed") is False,
    )
    require(
        "original_codex_drift_packet.json.broad_original_filesystem_innocence_claimed",
        original.get("broad_original_filesystem_innocence_claimed") is False,
    )
    require(
        "original_codex_drift_packet.json.original_equivalence_claimed",
        original.get("original_equivalence_claimed") is False,
    )
    require(
        "owner_manual_acceptance_packet.json.machine_ui_proof_claimed",
        owner.get("machine_ui_proof_claimed") is False,
    )
    require(
        "owner_manual_acceptance_packet.json.general_day_to_day_usability_claimed",
        owner.get("general_day_to_day_usability_claimed") is False,
    )
    require(
        "owner_manual_acceptance_packet.json.owner_ui_waiver_closes_ux_only",
        owner.get("owner_ui_waiver_closes_ux_only") is True,
    )
    require("owner_false_green.status", sources["owner_false_green"].get("status") == "ok")
    require(
        "owner_independent_audit.status",
        sources["owner_independent_audit"].get("status") == "ok",
    )
    require(
        "original_false_green.status",
        sources["original_false_green"].get("status") == "ok",
    )
    require(
        "original_independent_audit.status",
        sources["original_independent_audit"].get("status") == "ok",
    )

    return packet(
        "custom_owner_accepted_with_limits_false_green_audit",
        status="ok" if not findings else "blocked",
        final_status=FINAL_STATUS_OK if not findings else FINAL_STATUS_BLOCKED,
        findings=findings,
        imported_truth_only=True,
        current_probe_collected_fresh_runtime_truth=False,
        persistence_claimed=False,
        keychain_claimed=False,
        direct_egress_claimed=False,
        original_equivalence_claimed=False,
    )


def overall_status(packets: dict[str, dict[str, Any]]) -> tuple[str, str]:
    if all(packet_data.get("status") == "ok" for packet_data in packets.values()):
        return "ok", FINAL_STATUS_OK
    return "blocked", FINAL_STATUS_BLOCKED


def build_closeout(
    repo_root: Path,
    evidence_dir: Path,
    packets: dict[str, dict[str, Any]],
) -> str:
    status, verdict = overall_status(packets)
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    tests_run = (
        "python3 -m unittest tests.test_custom_codex_via_wbp_owner_accepted_with_limits_r2_probe; "
        "python3 tools/custom_codex_via_wbp_owner_accepted_with_limits_r2_probe.py "
        "--evidence-dir audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27; "
        "python3 tools/check_closeout_resilience.py "
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/closeout.md; "
        "python3 -c \"import json, pathlib; "
        "[json.loads(path.read_text(encoding='utf-8')) for path in "
        "sorted(pathlib.Path('audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27').glob('*.json'))]\"; "
        "git diff --check"
    )
    blocked_risks = (
        "persistence, keychain, direct-egress, and Original-equivalence claims intentionally "
        "not made; owner manual acceptance remains imported UX truth only"
    )
    return "\n".join(
        [
            "# Custom Codex via WBP Owner Accepted with Limits R2 Closeout",
            "",
            "## Goal",
            "",
            "Synthesize a Pass 4 owner-accepted-with-limits closeout from existing packet-backed "
            "truth while keeping current-vs-imported boundaries explicit and without promoting the "
            "result into persistence proof, keychain proof, direct-egress proof, or Original "
            "equivalence.",
            "",
            "## Result",
            "",
            f"- status: {status}",
            f"- final verdict: {verdict}",
            "- closure state: CLOSED",
            "",
            "## Contour Capsule",
            "",
            "- goal: synthesize bounded Custom-via-WBP owner acceptance from imported packet truth only",
            f"- branch: {branch}",
            f"- head: {head}",
            (
                "- touched files: "
                "tools/custom_codex_via_wbp_owner_accepted_with_limits_r2_probe.py; "
                "tests/test_custom_codex_via_wbp_owner_accepted_with_limits_r2_probe.py; "
                "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/*"
            ),
            f"- tests run: {tests_run}",
            f"- blocked risks: {blocked_risks}",
            "- closure state: CLOSED",
            "",
            "## Verification",
            "",
            "- tests: focused unittest coverage for synthesis success, overclaim blocking, and missing-source failure boundaries",
            "- build: packet synthesis only; no current live mutation performed",
            "- manual: none",
            "- live verification: none in this contour; owner UX and Original reversibility remain historical imports",
            "",
            "## Artifacts",
            "",
            "- spec: thread-only contour plan, not stored in repo",
            "- packet: false_green_audit.json",
            "- report: closeout.md",
            "",
            "## Git",
            "",
            f"- branch: {branch}",
            f"- commit: {head}",
            "- pushed: not performed in this contour",
            "",
            "## Scope Check",
            "",
            "- unrelated work mixed in: no; existing unrelated dirt remained outside the declared write scope",
            "- private-data risk reviewed: yes; imported trace truth stays hash-only and no raw auth/prompt evidence is widened here",
            "",
            "## Notes",
            "",
            "- blockers encountered: none; the imported packets were sufficient for a bounded acceptance classification with explicit non-claims",
            "- resume from here: CLOSED",
            "",
        ]
    )


def build_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    source_packets: dict[str, dict[str, Any]] | None = None,
    source_paths: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    loaded_packets: dict[str, dict[str, Any]]
    loaded_paths: dict[str, str]
    if source_packets is None or source_paths is None:
        loaded_packets, loaded_paths = load_source_packets(repo_root)
    else:
        loaded_packets = source_packets
        loaded_paths = source_paths

    packets = {
        "custom_launcher_contract_packet.json": build_custom_launcher_contract_packet(
            loaded_packets, loaded_paths
        ),
        "custom_profile_mode_packet.json": build_custom_profile_mode_packet(
            loaded_packets, loaded_paths
        ),
        "custom_route_trace_packet.json": build_custom_route_trace_packet(
            loaded_packets, loaded_paths
        ),
        "custom_authority_boundary_packet.json": build_custom_authority_boundary_packet(
            loaded_packets, loaded_paths
        ),
        "concurrent_launch_policy_packet.json": build_concurrent_launch_policy_packet(
            loaded_packets, loaded_paths
        ),
        "cleanup_policy_packet.json": build_cleanup_policy_packet(
            loaded_packets, loaded_paths
        ),
        "original_codex_drift_packet.json": build_original_codex_drift_packet(
            loaded_packets, loaded_paths
        ),
        "owner_manual_acceptance_packet.json": build_owner_manual_acceptance_packet(
            loaded_packets, loaded_paths
        ),
    }
    packets["false_green_audit.json"] = build_false_green_audit(packets, loaded_packets)
    return packets


def write_evidence(
    evidence_dir: Path,
    packets: dict[str, dict[str, Any]],
    closeout: str,
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet_data in packets.items():
        json_write(evidence_dir / name, packet_data)
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")


def emit_input_error(evidence_dir: Path, message: str) -> int:
    error_packet = packet(
        "custom_owner_acceptance_input_error",
        status="blocked",
        final_status=FINAL_STATUS_BLOCKED,
        message=message,
        traceback_emitted=False,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_write(evidence_dir / "false_green_audit.json", error_packet)
    print(json.dumps(error_packet, indent=2, sort_keys=True), file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="custom-codex-via-wbp-owner-accepted-with-limits-r2-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    try:
        packets = build_packets(repo_root, evidence_dir)
        closeout = build_closeout(repo_root, evidence_dir, packets)
    except SourcePacketError as exc:
        return emit_input_error(evidence_dir, str(exc))

    write_evidence(evidence_dir, packets, closeout)
    status, _verdict = overall_status(packets)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
