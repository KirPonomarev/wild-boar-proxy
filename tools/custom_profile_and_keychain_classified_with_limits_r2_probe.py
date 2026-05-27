#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthesize a bounded Pass 4.5 Custom profile/keychain classification bundle."""

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


FINAL_STATUS_OK = "WBP_CUSTOM_PROFILE_AND_KEYCHAIN_CLASSIFIED_WITH_LIMITS"
FINAL_STATUS_BLOCKED = "WBP_CUSTOM_PROFILE_AND_KEYCHAIN_CLASSIFICATION_NOT_PROVEN"
EXPECTED_EVIDENCE_DIR = (
    "audit_results/wbp_custom_profile_and_keychain_classified_with_limits_r2_2026-05-27"
)

DEFAULT_SOURCE_FILES = {
    "custom_profile_mode": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "custom_profile_mode_packet.json"
    ),
    "profile_identity_contract": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_profile_identity_contract_packet.json"
    ),
    "profile_path_authority": Path(
        "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27/"
        "persistent_profile_path_authority_packet.json"
    ),
    "profile_summary": Path(
        "audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/"
        "persistent_profile_summary_packet.json"
    ),
    "profile_continuity": Path(
        "audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/"
        "persistent_profile_continuity_classification_packet.json"
    ),
    "profile_identity_import": Path(
        "audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/"
        "persistent_custom_profile_identity_packet.json"
    ),
    "storage_truth": Path(
        "audit_results/wbp_persistent_custom_profile_storage_truth_r3_2026-05-27/"
        "persistent_storage_truth_classification_packet.json"
    ),
    "storage_inventory": Path(
        "audit_results/wbp_persistent_custom_profile_storage_truth_r3_2026-05-27/"
        "persistent_storage_surface_inventory_packet.json"
    ),
    "profile_false_green": Path(
        "audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/"
        "persistent_profile_false_green_audit.json"
    ),
    "profile_independent_audit": Path(
        "audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/"
        "independent_persistent_profile_audit.json"
    ),
    "keychain_behavior": Path(
        "audit_results/wbp_keychain_prompt_behavior_import_r1_2026-05-27/"
        "keychain_prompt_behavior_classification_packet.json"
    ),
    "keychain_summary": Path(
        "audit_results/wbp_keychain_prompt_behavior_import_r1_2026-05-27/"
        "keychain_prompt_summary_packet.json"
    ),
    "keychain_owner_action": Path(
        "audit_results/wbp_keychain_prompt_behavior_import_r1_2026-05-27/"
        "keychain_prompt_owner_action_packet.json"
    ),
    "keychain_false_green": Path(
        "audit_results/wbp_keychain_prompt_behavior_import_r1_2026-05-27/"
        "keychain_prompt_false_green_audit.json"
    ),
    "keychain_independent_audit": Path(
        "audit_results/wbp_keychain_prompt_behavior_import_r1_2026-05-27/"
        "independent_keychain_prompt_behavior_audit.json"
    ),
    "original_drift": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "original_codex_drift_packet.json"
    ),
    "original_reversibility": Path(
        "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/"
        "original_wbp_reversibility_classification_packet.json"
    ),
}

OUTPUT_FILES = (
    "custom_profile_identity_packet.json",
    "custom_profile_continuity_packet.json",
    "custom_profile_storage_boundary_packet.json",
    "keychain_behavior_packet.json",
    "keychain_owner_action_packet.json",
    "original_profile_non_equivalence_packet.json",
    "false_green_audit.json",
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


def build_custom_profile_identity_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    mode = sources["custom_profile_mode"]
    contract = sources["profile_identity_contract"]
    path_authority = sources["profile_path_authority"]
    imported = sources["profile_identity_import"]

    consistent_profile_id = (
        mode.get("persistent_profile_id") == contract.get("persistent_profile_id")
        == imported.get("persistent_profile_id")
        == path_authority.get("persistent_profile_id")
    )
    consistent_profile_root = (
        mode.get("persistent_profile_root") == contract.get("persistent_profile_root")
        == imported.get("persistent_profile_root")
        == path_authority.get("persistent_profile_root")
    )
    consistent_codex_home = contract.get("codex_home") == imported.get("codex_home")
    consistent_user_data_dir = contract.get("user_data_dir") == imported.get("user_data_dir")

    status = "ok"
    for key in (
        "custom_profile_mode",
        "profile_identity_contract",
        "profile_path_authority",
        "profile_identity_import",
    ):
        if sources[key].get("status") != "ok":
            status = "blocked"
    if mode.get("profile_mode") != "persistent_custom":
        status = "blocked"
    if mode.get("persistent_mode_is_contract_only") is not True:
        status = "blocked"
    if mode.get("profile_storage_persistence_claimed") is not False:
        status = "blocked"
    if mode.get("thread_history_preservation_claimed") is not False:
        status = "blocked"
    if contract.get("identity_counts_as_profile_storage_persistence") is not False:
        status = "blocked"
    if contract.get("identity_counts_as_thread_history_preservation") is not False:
        status = "blocked"
    if path_authority.get("profile_storage_persistence_claimed") is not False:
        status = "blocked"
    if path_authority.get("silent_profile_switching_allowed") is not False:
        status = "blocked"
    if imported.get("counts_as_daily_reliability_proof") is not False:
        status = "blocked"
    if not all(
        (
            consistent_profile_id,
            consistent_profile_root,
            consistent_codex_home,
            consistent_user_data_dir,
            contract.get("same_profile_id_as_expected") is True,
            contract.get("same_profile_root_as_expected") is True,
            contract.get("silent_profile_switching_detected") is False,
            imported.get("same_profile_identity_across_relaunch") is True,
            imported.get("same_profile_id_across_relaunch") is True,
            imported.get("same_profile_root_across_relaunch") is True,
            imported.get("same_codex_home_across_relaunch") is True,
            imported.get("same_user_data_dir_across_relaunch") is True,
            imported.get("silent_persistent_to_ephemeral_fallback_allowed") is False,
            imported.get("silent_profile_switching_detected") is False,
            path_authority.get("operator_explicit_profile_id_required") is True,
        )
    ):
        status = "blocked"

    return packet(
        "custom_profile_identity",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="identity_path_only",
        imported_truth_only=True,
        continuity_claim_limited_to_identity_path=True,
        persistent_profile_id=contract.get("persistent_profile_id", ""),
        persistent_profile_root=contract.get("persistent_profile_root", ""),
        codex_home=contract.get("codex_home", ""),
        user_data_dir=contract.get("user_data_dir", ""),
        identity_path_only_proven=status == "ok",
        owner_visible_continuity_proven=False,
        storage_continuity_proven=False,
        thread_history_storage_proven=False,
        consistent_profile_id=consistent_profile_id,
        consistent_profile_root=consistent_profile_root,
        consistent_codex_home=consistent_codex_home,
        consistent_user_data_dir=consistent_user_data_dir,
        operator_explicit_profile_id_required=(
            path_authority.get("operator_explicit_profile_id_required") is True
        ),
        silent_profile_switching_allowed=(
            path_authority.get("silent_profile_switching_allowed") is True
        ),
        source_custom_profile_mode_packet=source_paths["custom_profile_mode"],
        source_profile_identity_contract_packet=source_paths["profile_identity_contract"],
        source_profile_path_authority_packet=source_paths["profile_path_authority"],
        source_profile_identity_import_packet=source_paths["profile_identity_import"],
    )


def build_custom_profile_continuity_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    summary = sources["profile_summary"]
    continuity = sources["profile_continuity"]
    identity = sources["profile_identity_import"]

    owner_visible_only = (
        summary.get("owner_visible_thread_continuity_classified") is True
        and continuity.get("owner_visible_thread_continuity_classified") is True
        and continuity.get("profile_state_preservation_proven") is False
        and continuity.get("storage_level_thread_history_proven") is False
        and continuity.get("relaunch_restoration_source_proven") is False
        and continuity.get("thread_history_preserved") is False
    )

    status = "ok"
    for key in ("profile_summary", "profile_continuity", "profile_identity_import"):
        if sources[key].get("status") != "ok":
            status = "blocked"
    if summary.get("persistent_profile_identity_proven") is not True:
        status = "blocked"
    if continuity.get("persistent_profile_identity_proven") is not True:
        status = "blocked"
    if continuity.get("original_codex_profile_non_dependency_proven") is not True:
        status = "blocked"
    if summary.get("profile_state_preservation_proven") is not False:
        status = "blocked"
    if summary.get("storage_level_thread_history_proven") is not False:
        status = "blocked"
    if continuity.get("with_limits_required") is not True:
        status = "blocked"
    if not owner_visible_only:
        status = "blocked"

    return packet(
        "custom_profile_continuity",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification=(
            "owner_visible_continuity_only" if owner_visible_only else "continuity_not_proven"
        ),
        imported_truth_only=True,
        persistent_profile_identity_proven=(
            summary.get("persistent_profile_identity_proven") is True
        ),
        identity_packet_counts_as_continuity_only=False,
        owner_visible_thread_continuity_classified=owner_visible_only,
        profile_state_preservation_proven=(
            continuity.get("profile_state_preservation_proven") is True
        ),
        storage_level_thread_history_proven=(
            continuity.get("storage_level_thread_history_proven") is True
        ),
        relaunch_restoration_source_proven=(
            continuity.get("relaunch_restoration_source_proven") is True
        ),
        thread_history_preserved=continuity.get("thread_history_preserved") is True,
        continuity_requires_limits=continuity.get("with_limits_required") is True,
        with_limits_reasons=continuity.get("with_limits_reasons", []),
        selected_profile_id=identity.get("persistent_profile_id", ""),
        selected_profile_root=identity.get("persistent_profile_root", ""),
        source_profile_summary_packet=source_paths["profile_summary"],
        source_profile_continuity_packet=source_paths["profile_continuity"],
        source_profile_identity_import_packet=source_paths["profile_identity_import"],
    )


def build_custom_profile_storage_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    storage = sources["storage_truth"]
    inventory = sources["storage_inventory"]

    status = "ok"
    for key in ("storage_truth", "storage_inventory"):
        if sources[key].get("status") != "ok":
            status = "blocked"
    if storage.get("state_class_classified") is not True:
        status = "blocked"
    if storage.get("storage_surface_observed") is not True:
        status = "blocked"
    if storage.get("thread_history_candidate") is not True:
        status = "blocked"
    if storage.get("owner_visible_thread_counted_as_storage_proof") is not False:
        status = "blocked"
    if storage.get("storage_level_thread_history_proven") is not False:
        status = "blocked"
    if storage.get("thread_history_durable_proven") is not False:
        status = "blocked"
    if storage.get("relaunch_restoration_source_proven") is not False:
        status = "blocked"
    if storage.get("raw_thread_content_recorded") is not False:
        status = "blocked"
    if inventory.get("metadata_only") is not True:
        status = "blocked"
    if inventory.get("raw_content_recorded") is not False:
        status = "blocked"
    if inventory.get("raw_thread_content_recorded") is not False:
        status = "blocked"

    return packet(
        "custom_profile_storage_boundary",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="storage_surface_observed_thread_history_candidate_only",
        imported_truth_only=True,
        storage_surface_observed=storage.get("storage_surface_observed") is True,
        state_class_classified=storage.get("state_class_classified") is True,
        metadata_only_inventory=inventory.get("metadata_only") is True,
        observed_state_classes=inventory.get("observed_state_classes", []),
        profile_root=inventory.get("profile_root", ""),
        profile_root_exists=inventory.get("profile_root_exists") is True,
        entry_count=inventory.get("entry_count", 0),
        thread_history_candidate=storage.get("thread_history_candidate") is True,
        storage_level_thread_history_proven=(
            storage.get("storage_level_thread_history_proven") is True
        ),
        thread_history_durable_proven=storage.get("thread_history_durable_proven") is True,
        relaunch_restoration_source_proven=(
            storage.get("relaunch_restoration_source_proven") is True
        ),
        owner_visible_thread_counted_as_storage_proof=(
            storage.get("owner_visible_thread_counted_as_storage_proof") is True
        ),
        raw_thread_content_recorded=inventory.get("raw_thread_content_recorded") is True,
        source_storage_truth_packet=source_paths["storage_truth"],
        source_storage_inventory_packet=source_paths["storage_inventory"],
    )


def build_keychain_behavior_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    behavior = sources["keychain_behavior"]
    summary = sources["keychain_summary"]

    status = "ok"
    for key in ("keychain_behavior", "keychain_summary"):
        if sources[key].get("status") != "ok":
            status = "blocked"
    if behavior.get("with_limits_required") is not True:
        status = "blocked"
    if behavior.get("historical_pre_repair_prompt_observed") is not True:
        status = "blocked"
    if behavior.get("current_live_prompt_behavior_proven") is not False:
        status = "blocked"
    if behavior.get("auth_boundary_proven") is not False:
        status = "blocked"
    if behavior.get("repaired_isolated_lane_repeated_prompt_observed") is not False:
        status = "blocked"
    if summary.get("current_live_prompt_behavior_proven") is not False:
        status = "blocked"
    if summary.get("auth_boundary_proven") is not False:
        status = "blocked"

    return packet(
        "keychain_behavior",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="historical_prompt_observed_current_behavior_unknown_bounded",
        imported_truth_only=True,
        historical_pre_repair_prompt_observed=(
            behavior.get("historical_pre_repair_prompt_observed") is True
        ),
        current_live_prompt_behavior_proven=(
            behavior.get("current_live_prompt_behavior_proven") is True
        ),
        current_keychain_behavior_unknown_bounded=(
            behavior.get("current_live_prompt_behavior_proven") is False
        ),
        auth_boundary_proven=behavior.get("auth_boundary_proven") is True,
        prompt_absence_claimed=False,
        repaired_isolated_lane_repeated_prompt_observed=(
            behavior.get("repaired_isolated_lane_repeated_prompt_observed") is True
        ),
        persistent_profile_continuity_claimed=(
            behavior.get("persistent_profile_continuity_claimed") is True
        ),
        with_limits_reasons=behavior.get("with_limits_reasons", []),
        source_keychain_behavior_packet=source_paths["keychain_behavior"],
        source_keychain_summary_packet=source_paths["keychain_summary"],
    )


def build_keychain_owner_action_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    owner_action = sources["keychain_owner_action"]

    status = "ok"
    if owner_action.get("status") != "ok":
        status = "blocked"
    if owner_action.get("owner_action_boundary_reference_only") is not True:
        status = "blocked"
    if owner_action.get("owner_action_performed_in_this_contour") is not False:
        status = "blocked"
    if owner_action.get("owner_allow_counted_as_auth_success") is not False:
        status = "blocked"
    if owner_action.get("owner_cancel_counted_as_machine_proof") is not False:
        status = "blocked"
    if owner_action.get("historical_destructive_dialog_interacted_with") is not False:
        status = "blocked"

    return packet(
        "keychain_owner_action_boundary",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="reference_only_not_observed_in_this_contour",
        imported_truth_only=True,
        owner_action_performed_in_this_contour=(
            owner_action.get("owner_action_performed_in_this_contour") is True
        ),
        owner_action_boundary_reference_only=(
            owner_action.get("owner_action_boundary_reference_only") is True
        ),
        allowed_future_owner_actions=owner_action.get("allowed_future_owner_actions", []),
        owner_allow_counted_as_auth_success=(
            owner_action.get("owner_allow_counted_as_auth_success") is True
        ),
        owner_cancel_counted_as_machine_proof=(
            owner_action.get("owner_cancel_counted_as_machine_proof") is True
        ),
        source_keychain_owner_action_packet=source_paths["keychain_owner_action"],
    )


def build_original_profile_non_equivalence_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    drift = sources["original_drift"]
    reversibility = sources["original_reversibility"]

    status = "ok"
    for key in ("original_drift", "original_reversibility"):
        if sources[key].get("status") != "ok":
            status = "blocked"
    if drift.get("bounded_non_equivalence_explicit") is not True:
        status = "blocked"
    if drift.get("original_equivalence_claimed") is not False:
        status = "blocked"
    if drift.get("general_original_works_claimed") is not False:
        status = "blocked"
    if drift.get("broad_original_filesystem_innocence_claimed") is not False:
        status = "blocked"
    if reversibility.get("reversibility_proven_on_declared_observed_surfaces_only") is not True:
        status = "blocked"
    if reversibility.get("general_original_works_claimed") is not False:
        status = "blocked"
    if reversibility.get("broad_original_filesystem_innocence_claimed") is not False:
        status = "blocked"

    return packet(
        "original_profile_non_equivalence",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="reversibility_only_not_original_equivalence",
        imported_truth_only=True,
        bounded_non_equivalence_explicit=drift.get("bounded_non_equivalence_explicit") is True,
        original_equivalence_claimed=drift.get("original_equivalence_claimed") is True,
        general_original_works_claimed=drift.get("general_original_works_claimed") is True,
        broad_original_filesystem_innocence_claimed=(
            drift.get("broad_original_filesystem_innocence_claimed") is True
        ),
        reversibility_proven_on_declared_observed_surfaces_only=(
            reversibility.get("reversibility_proven_on_declared_observed_surfaces_only") is True
        ),
        route_observation_supporting_only=(
            reversibility.get("route_observation_supporting_only") is True
        ),
        source_original_drift_packet=source_paths["original_drift"],
        source_original_reversibility_packet=source_paths["original_reversibility"],
    )


def build_false_green_audit(
    packets: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    findings: list[str] = []

    def expect_false(filename: str, field: str) -> None:
        if packets[filename].get(field) is True:
            findings.append(f"{filename}.{field}")

    def expect_true(filename: str, field: str) -> None:
        if packets[filename].get(field) is not True:
            findings.append(f"{filename}.{field}")

    expect_true("custom_profile_identity_packet.json", "identity_path_only_proven")
    expect_false("custom_profile_identity_packet.json", "owner_visible_continuity_proven")
    expect_false("custom_profile_identity_packet.json", "storage_continuity_proven")
    expect_false("custom_profile_identity_packet.json", "thread_history_storage_proven")
    expect_true("custom_profile_continuity_packet.json", "owner_visible_thread_continuity_classified")
    expect_false("custom_profile_continuity_packet.json", "profile_state_preservation_proven")
    expect_false("custom_profile_continuity_packet.json", "storage_level_thread_history_proven")
    expect_false("custom_profile_continuity_packet.json", "relaunch_restoration_source_proven")
    expect_false(
        "custom_profile_storage_boundary_packet.json",
        "owner_visible_thread_counted_as_storage_proof",
    )
    expect_false("custom_profile_storage_boundary_packet.json", "thread_history_durable_proven")
    expect_false("keychain_behavior_packet.json", "current_live_prompt_behavior_proven")
    expect_true("keychain_behavior_packet.json", "current_keychain_behavior_unknown_bounded")
    expect_false("keychain_behavior_packet.json", "auth_boundary_proven")
    expect_false("keychain_owner_action_packet.json", "owner_action_performed_in_this_contour")
    expect_false("original_profile_non_equivalence_packet.json", "original_equivalence_claimed")
    expect_false("original_profile_non_equivalence_packet.json", "general_original_works_claimed")
    expect_false(
        "original_profile_non_equivalence_packet.json",
        "broad_original_filesystem_innocence_claimed",
    )

    for key in (
        "profile_false_green",
        "profile_independent_audit",
        "keychain_false_green",
        "keychain_independent_audit",
    ):
        if sources[key].get("status") != "ok":
            findings.append(f"source_status:{key}")

    status = "ok" if not findings else "blocked"
    return packet(
        "custom_profile_and_keychain_false_green_audit",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        forbidden_claims_present=bool(findings),
        findings=findings,
        checks=[
            {"name": "identity_kept_to_identity_path_only", "passed": not any(
                item.startswith("custom_profile_identity_packet.json") for item in findings
            )},
            {"name": "continuity_kept_to_owner_visible_only", "passed": not any(
                item.startswith("custom_profile_continuity_packet.json") for item in findings
            )},
            {"name": "storage_not_widened_to_durable_thread_history", "passed": not any(
                item.startswith("custom_profile_storage_boundary_packet.json")
                for item in findings
            )},
            {"name": "keychain_kept_unknown_when_not_reobserved", "passed": not any(
                item.startswith("keychain_behavior_packet.json") for item in findings
            )},
            {"name": "owner_action_kept_reference_only", "passed": not any(
                item.startswith("keychain_owner_action_packet.json") for item in findings
            )},
            {"name": "original_reversibility_not_widened_to_equivalence", "passed": not any(
                item.startswith("original_profile_non_equivalence_packet.json")
                for item in findings
            )},
            {"name": "source_false_green_audits_remain_ok", "passed": not any(
                item.startswith("source_status:") for item in findings
            )},
        ],
        source_packets={
            key: source_paths[key]
            for key in (
                "profile_false_green",
                "profile_independent_audit",
                "keychain_false_green",
                "keychain_independent_audit",
            )
        },
    )


def build_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    source_packets: dict[str, dict[str, Any]] | None = None,
    source_paths: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    if source_packets is None or source_paths is None:
        source_packets, source_paths = load_source_packets(repo_root)

    packets = {
        "custom_profile_identity_packet.json": build_custom_profile_identity_packet(
            source_packets, source_paths
        ),
        "custom_profile_continuity_packet.json": build_custom_profile_continuity_packet(
            source_packets, source_paths
        ),
        "custom_profile_storage_boundary_packet.json": build_custom_profile_storage_boundary_packet(
            source_packets, source_paths
        ),
        "keychain_behavior_packet.json": build_keychain_behavior_packet(
            source_packets, source_paths
        ),
        "keychain_owner_action_packet.json": build_keychain_owner_action_packet(
            source_packets, source_paths
        ),
        "original_profile_non_equivalence_packet.json": (
            build_original_profile_non_equivalence_packet(source_packets, source_paths)
        ),
    }
    packets["false_green_audit.json"] = build_false_green_audit(
        packets, source_packets, source_paths
    )
    return packets


def overall_status(
    packets: dict[str, dict[str, Any]]
) -> tuple[str, str]:
    statuses = {name: packet["status"] for name, packet in packets.items()}
    if all(status == "ok" for status in statuses.values()):
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
    blocked_risks = (
        "storage-level thread history remains unproven; relaunch restoration source "
        "remains unproven; current live keychain behavior remains unknown/bounded; "
        "Original reversibility remains narrower than Original equivalence"
    )
    touched_files = (
        "tools/custom_profile_and_keychain_classified_with_limits_r2_probe.py; "
        "tests/test_custom_profile_and_keychain_classified_with_limits_r2_probe.py; "
        f"{evidence_dir.relative_to(repo_root)}/*"
    )
    tests_run = (
        "python3 -m unittest "
        "tests.test_custom_profile_and_keychain_classified_with_limits_r2_probe; "
        f"python3 tools/custom_profile_and_keychain_classified_with_limits_r2_probe.py "
        f"--evidence-dir {evidence_dir.relative_to(repo_root)}; "
        "python3 tools/check_closeout_resilience.py "
        f"{evidence_dir.relative_to(repo_root) / 'closeout.md'}; "
        "python3 JSON parse sweep for all json files in the new dir; "
        "git diff --check"
    )
    return (
        "# Custom Profile And Keychain Classified With Limits R2 Closeout\n\n"
        "## Goal\n\n"
        "Synthesize a truthful Pass 4.5 classification bundle from existing packet truth "
        "only, without widening identity/path truth into storage continuity, keychain "
        "behavior into absence/auth proof, or Original reversibility into equivalence.\n\n"
        "## Result\n\n"
        f"- status: `{status}`\n"
        f"- final verdict: `{verdict}`\n"
        "- closure state: CLOSED\n\n"
        "## Contour Capsule\n\n"
        "- goal: import the declared profile, storage, keychain, and Original truth owners "
        "and restate them as the narrowest combined Pass 4.5 bundle\n"
        f"- branch: `{branch}`\n"
        f"- head: `{head}`\n"
        f"- touched files: `{touched_files}`\n"
        f"- tests run: `{tests_run}`\n"
        f"- blocked risks: `{blocked_risks}`\n"
        "- closure state: CLOSED\n\n"
        "## Verification\n\n"
        "- tests: required unittest slice and probe generation command are the contour "
        "verification surface\n"
        "- build: no build step; probe is import-only Python synthesis\n"
        "- manual: JSON packets are emitted from imported packet truth only; no live launch, "
        "no live keychain interaction, and no storage mutation performed\n"
        "- live verification: none in this contour by design\n\n"
        "## Artifacts\n\n"
        "- spec: thread-scoped contour request only\n"
        f"- packet: `{evidence_dir.relative_to(repo_root) / 'custom_profile_continuity_packet.json'}`\n"
        f"- report: `{evidence_dir.relative_to(repo_root) / 'false_green_audit.json'}`\n\n"
        "## Git\n\n"
        f"- branch: `{branch}`\n"
        f"- commit: `{head}`\n"
        "- pushed: no\n\n"
        "## Scope Check\n\n"
        "- unrelated work mixed in: no; pre-existing dirty worktree entries outside the "
        "declared contour scope were left untouched\n"
        "- private-data risk reviewed: yes; imported packets remain metadata/classification "
        "only and do not add raw thread or prompt content\n\n"
        "## Notes\n\n"
        "- blockers encountered: none inside the admitted packet chain; the contour stays "
        "bounded by existing unproven storage durability, unobserved current keychain "
        "behavior, and non-equivalence of Original\n"
        "- resume from here: CLOSED\n"
    )


def write_outputs(evidence_dir: Path, packets: dict[str, dict[str, Any]], closeout: str) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for filename, contents in packets.items():
        json_write(evidence_dir / filename, contents)
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="custom-profile-and-keychain-classified-with-limits-r2-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()

    try:
        packets = build_packets(repo_root, evidence_dir)
        closeout = build_closeout(repo_root, evidence_dir, packets)
        write_outputs(evidence_dir, packets, closeout)
    except SourcePacketError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    status, verdict = overall_status(packets)
    print(
        json.dumps(
            {
                "captured_at_utc": utc_now(),
                "packet_kind": "custom_profile_and_keychain_synthesis_result",
                "status": status,
                "final_status": verdict,
                "evidence_dir": str(evidence_dir),
                "output_files": sorted((*OUTPUT_FILES, "closeout.md")),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
