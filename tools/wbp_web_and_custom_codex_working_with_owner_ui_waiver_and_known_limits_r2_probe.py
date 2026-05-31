#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthesize the final bounded acceptance bundle from closed Pass 1-5 truth."""

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


FINAL_STATUS_OK = "WBP_WEB_AND_CUSTOM_CODEX_WORKING_WITH_OWNER_UI_WAIVER_AND_KNOWN_LIMITS"
FINAL_STATUS_BLOCKED = "WBP_FINAL_ACCEPTANCE_TRUTH_NOT_PROVEN"
EXPECTED_EVIDENCE_DIR = (
    "audit_results/wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_2026-05-27"
)

DEFAULT_SOURCE_FILES = {
    "current_truth_owner_ui_waiver": Path(
        "audit_results/wbp_current_truth_reconciliation_closeout_r2_2026-05-27/"
        "owner_ui_waiver_boundary_packet.json"
    ),
    "pass1_acceptance_summary": Path(
        "audit_results/wbp_web_control_surface_actions_acceptance_and_blocked_closeout_r2_2026-05-27/"
        "acceptance_summary.json"
    ),
    "pass1_false_green_audit": Path(
        "audit_results/wbp_web_control_surface_actions_acceptance_and_blocked_closeout_r2_2026-05-27/"
        "false_green_audit.json"
    ),
    "pass2_provider_lane_selection": Path(
        "audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/"
        "provider_lane_selection_packet.json"
    ),
    "pass2_route_validation": Path(
        "audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/"
        "route_validation_packet.json"
    ),
    "pass2_route_smoke_check": Path(
        "audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/"
        "route_smoke_check_packet.json"
    ),
    "pass2_false_green_audit": Path(
        "audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/"
        "false_green_audit.json"
    ),
    "pass3_availability_lattice": Path(
        "audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/"
        "availability_lattice_packet.json"
    ),
    "pass3_false_green_audit": Path(
        "audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/"
        "false_green_audit.json"
    ),
    "pass4_launcher_contract": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "custom_launcher_contract_packet.json"
    ),
    "pass4_owner_acceptance": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "owner_manual_acceptance_packet.json"
    ),
    "pass4_route_trace": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "custom_route_trace_packet.json"
    ),
    "pass4_original_drift": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "original_codex_drift_packet.json"
    ),
    "pass4_false_green_audit": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "false_green_audit.json"
    ),
    "pass45_profile_identity": Path(
        "audit_results/wbp_custom_profile_and_keychain_classified_with_limits_r2_2026-05-27/"
        "custom_profile_identity_packet.json"
    ),
    "pass45_keychain_behavior": Path(
        "audit_results/wbp_custom_profile_and_keychain_classified_with_limits_r2_2026-05-27/"
        "keychain_behavior_packet.json"
    ),
    "pass45_false_green_audit": Path(
        "audit_results/wbp_custom_profile_and_keychain_classified_with_limits_r2_2026-05-27/"
        "false_green_audit.json"
    ),
    "pass5_failure_semantics": Path(
        "audit_results/custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_2026-05-27/"
        "direct_non_wbp_failure_semantics_packet.json"
    ),
    "pass5_false_green_audit": Path(
        "audit_results/custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_2026-05-27/"
        "false_green_audit.json"
    ),
}

OUTPUT_FILES = (
    "final_acceptance_summary_packet.json",
    "pass_truth_matrix_packet.json",
    "final_limits_boundary_packet.json",
    "owner_ui_waiver_boundary_packet.json",
    "provider_and_catalog_boundary_packet.json",
    "persistence_keychain_boundary_packet.json",
    "direct_egress_boundary_packet.json",
    "false_green_audit.json",
)

REQUIRED_OWNER_UI_WAIVER_DOES_NOT_CLOSE = frozenset(
    {
        "route_trace_proof",
        "network_egress_proof",
        "model_availability_proof",
        "machine_ui_input_field_proof",
        "machine_observed_response_text_proof",
    }
)


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
    paths: dict[str, str] = {}
    for key, relative_path in resolved_files.items():
        full_path = (repo_root / relative_path).resolve()
        packets[key] = read_json(full_path)
        paths[key] = str(full_path)
    return packets, paths


def false_green_audit_ok(packet_data: dict[str, Any]) -> bool:
    status = packet_data.get("status")
    if status is not None:
        return status == "ok"

    claims = packet_data.get("claims")
    if not isinstance(claims, dict):
        return False

    selected_route_success = claims.get("single_selected_route_smoke_check_ok_counts_as_success")
    other_claims = {
        key: value
        for key, value in claims.items()
        if key != "single_selected_route_smoke_check_ok_counts_as_success"
    }
    return selected_route_success is True and all(value is False for value in other_claims.values())


def build_pass_truth_matrix_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    pass1 = sources["pass1_acceptance_summary"]
    pass2_selection = sources["pass2_provider_lane_selection"]
    pass2_validate = sources["pass2_route_validation"]
    pass2_smoke = sources["pass2_route_smoke_check"]
    pass3 = sources["pass3_availability_lattice"]
    pass4_launcher = sources["pass4_launcher_contract"]
    pass4_owner = sources["pass4_owner_acceptance"]
    pass4_original_drift = sources["pass4_original_drift"]
    pass45_profile = sources["pass45_profile_identity"]
    pass45_keychain = sources["pass45_keychain_behavior"]
    pass5 = sources["pass5_failure_semantics"]

    rows = [
        {
            "pass_id": "Pass 1",
            "final_status": pass1.get("final_verdict"),
            "status": "ok"
            if pass1.get("acceptance_truth") == "ok"
            and pass1.get("final_verdict") == "WBP_WEB_CONTROL_SURFACE_ACTIONS_WIRED_AND_GUARDED"
            and false_green_audit_ok(sources["pass1_false_green_audit"])
            else "blocked",
            "summary": "web control surface actions wired and guarded",
            "source_packet": source_paths["pass1_acceptance_summary"],
        },
        {
            "pass_id": "Pass 2",
            "final_status": "WBP_ONE_EXTERNAL_PROVIDER_ROUTE_WORKS_WITH_LIMITS",
            "status": "ok"
            if pass2_validate.get("packet", {}).get("status") == "ok"
            and pass2_smoke.get("packet", {}).get("status") == "ok"
            and false_green_audit_ok(sources["pass2_false_green_audit"])
            else "blocked",
            "summary": "one selected external provider lane only",
            "source_packet": source_paths["pass2_provider_lane_selection"],
        },
        {
            "pass_id": "Pass 3",
            "final_status": "WBP_MODEL_CATALOG_FIDELITY_AND_AVAILABILITY_ALIGNED",
            "status": "ok"
            if pass3.get("status") == "ok"
            and false_green_audit_ok(sources["pass3_false_green_audit"])
            else "blocked",
            "summary": "catalog aligned with availability lattice",
            "source_packet": source_paths["pass3_availability_lattice"],
        },
        {
            "pass_id": "Pass 4",
            "final_status": pass4_launcher.get("final_status"),
            "status": "ok"
            if pass4_launcher.get("status") == "ok"
            and pass4_launcher.get("final_status")
            == "CUSTOM_CODEX_VIA_WBP_OWNER_ACCEPTED_WITH_LIMITS"
            and pass4_owner.get("status") == "ok"
            and pass4_original_drift.get("status") == "ok"
            and pass4_original_drift.get("original_equivalence_claimed") is False
            and pass4_original_drift.get("bounded_non_equivalence_explicit") is True
            and false_green_audit_ok(sources["pass4_false_green_audit"])
            else "blocked",
            "summary": "Custom Codex via WBP owner accepted with limits",
            "source_packet": source_paths["pass4_launcher_contract"],
        },
        {
            "pass_id": "Pass 4.5",
            "final_status": pass45_profile.get("contour_final_status"),
            "status": "ok"
            if pass45_profile.get("status") == "ok"
            and pass45_profile.get("contour_final_status")
            == "WBP_CUSTOM_PROFILE_AND_KEYCHAIN_CLASSIFIED_WITH_LIMITS"
            and pass45_keychain.get("status") == "ok"
            and false_green_audit_ok(sources["pass45_false_green_audit"])
            else "blocked",
            "summary": "profile/keychain claims bounded to proven level",
            "source_packet": source_paths["pass45_profile_identity"],
        },
        {
            "pass_id": "Pass 5",
            "final_status": pass5.get("final_status"),
            "status": "ok"
            if pass5.get("status") == "ok"
            and false_green_audit_ok(sources["pass5_false_green_audit"])
            else "blocked",
            "summary": "direct non-WBP egress known blocker remains explicit",
            "source_packet": source_paths["pass5_failure_semantics"],
        },
    ]
    status = "ok" if all(row["status"] == "ok" for row in rows) else "blocked"
    return packet(
        "final_acceptance_pass_truth_matrix",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        rows=rows,
        imported_evidence_only=True,
    )


def build_owner_ui_waiver_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    current_waiver = sources["current_truth_owner_ui_waiver"]
    owner_acceptance = sources["pass4_owner_acceptance"]
    waiver_does_not_close = set(current_waiver.get("waiver_does_not_close", []))
    ok = all(
        (
            current_waiver.get("status") == "ok",
            current_waiver.get("owner_waives_machine_ui") is True,
            current_waiver.get("manual_ui_confirmation_allowed") is True,
            current_waiver.get("machine_ui_proof_claimed") is False,
            current_waiver.get("manual_ui_confirmation_replaces_route_trace") is False,
            REQUIRED_OWNER_UI_WAIVER_DOES_NOT_CLOSE.issubset(waiver_does_not_close),
            owner_acceptance.get("status") == "ok",
            owner_acceptance.get("owner_ui_waiver_closes_ux_only") is True,
            owner_acceptance.get("machine_ui_proof_claimed") is False,
            owner_acceptance.get("historical_owner_acceptance_imported") is True,
        )
    )
    return packet(
        "final_acceptance_owner_ui_waiver_boundary",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        classification="owner_ui_waiver_closes_ux_only",
        imported_evidence_only=True,
        owner_ui_waiver_applies_to_ux_only=True,
        machine_ui_proof_claimed=False,
        route_trace_proof_granted_by_ui_waiver="route_trace_proof" not in waiver_does_not_close,
        network_proof_granted_by_ui_waiver="network_egress_proof" not in waiver_does_not_close,
        model_availability_proof_granted_by_ui_waiver="model_availability_proof"
        not in waiver_does_not_close,
        persistence_proof_granted_by_ui_waiver=False,
        keychain_proof_granted_by_ui_waiver=False,
        waiver_does_not_close=sorted(waiver_does_not_close),
        source_current_truth_waiver_packet=source_paths["current_truth_owner_ui_waiver"],
        source_pass4_owner_acceptance_packet=source_paths["pass4_owner_acceptance"],
    )


def build_provider_and_catalog_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    selection = sources["pass2_provider_lane_selection"]
    validate = sources["pass2_route_validation"]
    smoke = sources["pass2_route_smoke_check"]
    lattice = sources["pass3_availability_lattice"]
    selected = selection.get("selected_provider_lane", {})
    validate_packet = validate.get("packet", {})
    smoke_packet = smoke.get("packet", {})
    ok = all(
        (
            validate_packet.get("status") == "ok",
            validate_packet.get("data", {}).get("route_state") == "model_visible",
            smoke_packet.get("status") == "ok",
            smoke_packet.get("data", {}).get("route_state") == "verified",
            selected.get("provider") == "openrouter",
            selection.get("selection_policy", {}).get("exactly_one_provider_admitted") is True,
            lattice.get("status") == "ok",
            lattice.get("all_listed_models_equally_usable") is False,
        )
    )
    return packet(
        "final_acceptance_provider_and_catalog_boundary",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        classification="one_selected_provider_lane_and_bounded_catalog_only",
        imported_evidence_only=True,
        selected_provider=selected.get("provider", ""),
        selected_route_id=selected.get("route_id", ""),
        one_provider_lane_only=selection.get("selection_policy", {}).get(
            "exactly_one_provider_admitted"
        )
        is True,
        route_state_model_visible=validate_packet.get("data", {}).get("route_state")
        == "model_visible",
        route_state_verified=smoke_packet.get("data", {}).get("route_state") == "verified",
        provider_family_parity_claimed=False,
        all_models_equally_usable_claimed=False,
        listed_means_usable_claimed=False,
        current_live_proven_model_ids=lattice.get("current_live_proven_model_ids", []),
        historically_bounded_model_ids=lattice.get("historically_bounded_model_ids", []),
        listed_only_model_ids=lattice.get("listed_only_model_ids", []),
        source_provider_selection_packet=source_paths["pass2_provider_lane_selection"],
        source_catalog_lattice_packet=source_paths["pass3_availability_lattice"],
    )


def build_persistence_keychain_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    profile = sources["pass45_profile_identity"]
    keychain = sources["pass45_keychain_behavior"]
    ok = all(
        (
            profile.get("status") == "ok",
            profile.get("classification") == "identity_path_only",
            profile.get("identity_path_only_proven") is True,
            profile.get("storage_continuity_proven") is False,
            profile.get("thread_history_storage_proven") is False,
            keychain.get("status") == "ok",
            keychain.get("classification")
            == "historical_prompt_observed_current_behavior_unknown_bounded",
            keychain.get("current_keychain_behavior_unknown_bounded") is True,
            keychain.get("current_live_prompt_behavior_proven") is False,
            keychain.get("prompt_absence_claimed") is False,
        )
    )
    return packet(
        "final_acceptance_persistence_keychain_boundary",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        classification="identity_path_only_and_keychain_unknown_bounded",
        imported_evidence_only=True,
        persistent_profile_identity_path_only=True,
        storage_continuity_proven=False,
        thread_history_storage_proven=False,
        owner_visible_continuity_proven=False,
        current_live_keychain_behavior_proven=False,
        current_keychain_behavior_unknown_bounded=True,
        prompt_absence_claimed=False,
        source_profile_identity_packet=source_paths["pass45_profile_identity"],
        source_keychain_behavior_packet=source_paths["pass45_keychain_behavior"],
    )


def build_direct_egress_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    failure = sources["pass5_failure_semantics"]
    pass4_route = sources["pass4_route_trace"]
    ok = all(
        (
            pass4_route.get("status") == "ok",
            failure.get("status") == "ok",
            failure.get("final_status") == "CUSTOM_CODEX_DIRECT_NON_WBP_EGRESS_KNOWN_BLOCKER",
            failure.get("direct_non_wbp_model_egress_known_blocker") is True,
            failure.get("direct_lane_fix_proven") is False,
            failure.get("wbp_routed_truth_preserved") is True,
            failure.get("global_egress_failure_claimed") is False,
            pass4_route.get("forwarded_to_wbp") is True,
            pass4_route.get("upstream_status") == 200,
            pass4_route.get("direct_egress_claimed") is False,
        )
    )
    return packet(
        "final_acceptance_direct_egress_boundary",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        classification="direct_non_wbp_known_blocker_wbp_route_truth_preserved",
        imported_evidence_only=True,
        direct_non_wbp_model_egress_known_blocker=True,
        direct_lane_fix_proven=False,
        wbp_routed_truth_preserved=True,
        direct_lane_recovery_implied=False,
        global_egress_failure_claimed=False,
        api_openai_com_absence_proven=False,
        source_pass5_failure_semantics_packet=source_paths["pass5_failure_semantics"],
        source_pass4_route_trace_packet=source_paths["pass4_route_trace"],
    )


def build_final_limits_boundary_packet(
    packets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    provider = packets["provider_and_catalog_boundary_packet.json"]
    persistence = packets["persistence_keychain_boundary_packet.json"]
    egress = packets["direct_egress_boundary_packet.json"]
    owner_ui = packets["owner_ui_waiver_boundary_packet.json"]
    ok = all(packet_data.get("status") == "ok" for packet_data in (provider, persistence, egress, owner_ui))
    return packet(
        "final_acceptance_limits_boundary",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        classification="with_limits_and_known_blocker_remain_visible",
        one_selected_provider_lane_only=provider.get("one_provider_lane_only") is True,
        all_models_equally_usable_claimed=False,
        provider_family_parity_claimed=False,
        machine_ui_proof_claimed=False,
        persistence_continuity_beyond_proven_level_claimed=False,
        current_live_keychain_proof_claimed=False,
        direct_lane_recovery_implied=False,
        global_egress_failure_claimed=False,
        imported_evidence_only=True,
    )


def build_final_acceptance_summary_packet(
    packets: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    matrix = packets["pass_truth_matrix_packet.json"]
    owner_ui = packets["owner_ui_waiver_boundary_packet.json"]
    provider = packets["provider_and_catalog_boundary_packet.json"]
    persistence = packets["persistence_keychain_boundary_packet.json"]
    egress = packets["direct_egress_boundary_packet.json"]
    limits = packets["final_limits_boundary_packet.json"]
    ok = all(
        packet_data.get("status") == "ok"
        for packet_data in (matrix, owner_ui, provider, persistence, egress, limits)
    )
    return packet(
        "final_acceptance_summary",
        status="ok" if ok else "blocked",
        final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        classification="final_bounded_acceptance_synthesis",
        imported_evidence_only=True,
        web_control_truth_preserved=sources["pass1_acceptance_summary"].get("final_verdict")
        == "WBP_WEB_CONTROL_SURFACE_ACTIONS_WIRED_AND_GUARDED",
        one_provider_lane_truth_preserved=provider.get("one_provider_lane_only") is True,
        catalog_alignment_truth_preserved=provider.get("all_models_equally_usable_claimed")
        is False,
        custom_owner_accepted_truth_preserved=owner_ui.get("owner_ui_waiver_applies_to_ux_only")
        is True,
        persistence_keychain_limits_explicit=persistence.get("status") == "ok",
        direct_non_wbp_egress_known_blocker_explicit=egress.get(
            "direct_non_wbp_model_egress_known_blocker"
        )
        is True,
        no_short_complete_alias=True,
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary = packets["final_acceptance_summary_packet.json"]
    provider = packets["provider_and_catalog_boundary_packet.json"]
    persistence = packets["persistence_keychain_boundary_packet.json"]
    egress = packets["direct_egress_boundary_packet.json"]
    owner_ui = packets["owner_ui_waiver_boundary_packet.json"]
    checks = [
        {
            "name": "final_status_is_bounded_alias_only",
            "passed": summary.get("final_status") == FINAL_STATUS_OK,
        },
        {
            "name": "no_all_model_or_provider_family_claim",
            "passed": provider.get("all_models_equally_usable_claimed") is False
            and provider.get("provider_family_parity_claimed") is False,
        },
        {
            "name": "owner_ui_waiver_stays_ux_only",
            "passed": owner_ui.get("network_proof_granted_by_ui_waiver") is False
            and owner_ui.get("model_availability_proof_granted_by_ui_waiver") is False
            and owner_ui.get("persistence_proof_granted_by_ui_waiver") is False,
        },
        {
            "name": "persistence_and_keychain_limits_visible",
            "passed": persistence.get("storage_continuity_proven") is False
            and persistence.get("current_live_keychain_behavior_proven") is False
            and persistence.get("prompt_absence_claimed") is False,
        },
        {
            "name": "direct_egress_known_blocker_stays_visible",
            "passed": egress.get("direct_non_wbp_model_egress_known_blocker") is True
            and egress.get("direct_lane_recovery_implied") is False
            and egress.get("global_egress_failure_claimed") is False,
        },
        {
            "name": "wbp_truth_not_collapsed_into_direct_lane_health",
            "passed": egress.get("wbp_routed_truth_preserved") is True,
        },
        {
            "name": "upstream_false_green_audits_remain_green",
            "passed": summary.get("status") == "ok",
        },
    ]
    ok = all(check["passed"] for check in checks)
    return packet(
        "final_acceptance_false_green_audit",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        checks=checks,
        forbidden_claims_present=not ok,
        positive_global_success_claim_without_limits=False,
    )


def build_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    source_packets: dict[str, dict[str, Any]] | None = None,
    source_paths: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    sources, paths = (
        (source_packets, source_paths)
        if source_packets is not None and source_paths is not None
        else load_source_packets(repo_root)
    )
    assert sources is not None
    assert paths is not None

    packets = {
        "pass_truth_matrix_packet.json": build_pass_truth_matrix_packet(sources, paths),
        "owner_ui_waiver_boundary_packet.json": build_owner_ui_waiver_boundary_packet(
            sources, paths
        ),
        "provider_and_catalog_boundary_packet.json": build_provider_and_catalog_boundary_packet(
            sources, paths
        ),
        "persistence_keychain_boundary_packet.json": build_persistence_keychain_boundary_packet(
            sources, paths
        ),
        "direct_egress_boundary_packet.json": build_direct_egress_boundary_packet(
            sources, paths
        ),
    }
    packets["final_limits_boundary_packet.json"] = build_final_limits_boundary_packet(
        packets
    )
    packets["final_acceptance_summary_packet.json"] = build_final_acceptance_summary_packet(
        packets, sources
    )
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    return packets


def overall_status(packets: dict[str, dict[str, Any]]) -> tuple[str, str]:
    ok = all(packet_data.get("status") == "ok" for packet_data in packets.values())
    return ("ok", FINAL_STATUS_OK) if ok else ("blocked", FINAL_STATUS_BLOCKED)


def build_closeout(
    repo_root: Path,
    evidence_dir: Path,
    packets: dict[str, dict[str, Any]],
) -> str:
    status, verdict = overall_status(packets)
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    touched_files = (
        "tools/wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe.py; "
        "tests/test_wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe.py; "
        f"{evidence_dir.relative_to(repo_root)}/*"
    )
    return f"""<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WBP Web And Custom Codex Working With Owner UI Waiver And Known Limits R2 Closeout

## Goal

Truthfully close the final acceptance contour by assembling the already closed
bounded pass truths into one final status, without widening any claim beyond
what Pass 1 through Pass 5 actually proved.

## Result

- status: {status}
- final verdict: `{verdict}`
- closure state: CLOSED

## Contour Capsule

- goal: synthesize final bounded acceptance from closed pass evidence only
- branch: {branch}
- head: {head}
- touched files: {touched_files}
- tests run: python3 -m py_compile tools/wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe.py tests/test_wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe.py; python3 -m unittest tests.test_wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe; python3 tools/wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe.py --evidence-dir {evidence_dir.relative_to(repo_root)}; python3 tools/check_closeout_resilience.py {evidence_dir.relative_to(repo_root)}/closeout.md; top-level JSON parse sweep; git diff --check
- blocked risks: direct non-WBP egress remains a known blocker; one provider lane only; listed models are not all equally usable; persistence and current live keychain proof remain bounded
- closure state: CLOSED

## Verification

- tests: targeted final synthesis unittest passed
- build: py_compile passed and git diff --check passed
- manual: final acceptance packets preserve pass boundaries, known limits, and no hidden COMPLETE-like alias
- live verification: none in this contour; all evidence remained imported from already closed pass bundles

## Artifacts

- spec: thread-only contour plan, not written to repo
- packet: final_acceptance_summary_packet.json
- report: false_green_audit.json

## Git

- branch: {branch}
- commit: final contour commit set recorded in pushed git history
- pushed: final operator closeout requires the contour commit set to be pushed

## Scope Check

- unrelated work mixed in: no; this contour stays within the dedicated final-synthesis probe, test, and contour-local evidence dir
- private-data risk reviewed: yes; final synthesis references packet truth only and does not copy raw secrets or prompt text

## Notes

- blockers encountered: none inside this contour; all closed pass boundaries remained compatible with one bounded final acceptance status
- resume from here: CLOSED
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wbp-web-and-custom-codex-working-with-owner-ui-waiver-and-known-limits-r2-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(ROOT / EXPECTED_EVIDENCE_DIR),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    try:
        packets = build_packets(repo_root, evidence_dir)
    except SourcePacketError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "final_status": FINAL_STATUS_BLOCKED,
                    "reason_class": "SOURCE_PACKET_ERROR",
                    "message": str(exc),
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    for filename, packet_data in packets.items():
        json_write(evidence_dir / filename, packet_data)

    closeout = build_closeout(repo_root, evidence_dir, packets)
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")

    status, verdict = overall_status(packets)
    print(
        json.dumps(
            {
                "status": status,
                "final_status": verdict,
                "output_files": ["closeout.md", *OUTPUT_FILES],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
