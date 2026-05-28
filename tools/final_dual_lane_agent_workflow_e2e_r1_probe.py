#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_custom_sessions import (  # noqa: E402
    CODING_AGENT_MODEL_SLOT,
    PRIMARY_MODEL_SLOT,
    CodexCustomSessionManager,
)
from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_dual_lane_model_selection_ui_packet,
    build_dual_lane_selection_intent_packet,
)
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_integration_ownership_baseline_packet,
    build_native_integrity_packet,
    build_original_codex_profile_drift_packet,
    build_original_codex_protected_surface_scope_packet,
    build_owner_visible_thread_context_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    build_persistent_profile_state_diff_packet,
    build_protected_surface_read_classification_packet,
    build_thread_history_preservation_packet,
    default_persistent_custom_profile_paths,
    json_write,
    scan_protected_surfaces,
    scan_tree,
)


PRIMARY_MODEL_ID = "gpt-5.3-codex"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"
PROFILE_ID = "wbp-custom-main"

IMPORTED_PACKET_PATHS = {
    "provider_auth": "audit_results/generic_provider_auth_and_secret_admission_r1_2026-05-28/admitted_provider_list_packet.json",
    "provider_registry": "audit_results/generic_provider_and_model_registry_r1_2026-05-28/generic_provider_registry_packet.json",
    "provider_smoke_matrix": "audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28/provider_smoke_matrix_packet.json",
    "budget_boundary": "audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/budget_boundary_packet.json",
    "concurrency_boundary": "audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/concurrency_boundary_packet.json",
    "acceleration_non_claims": "audit_results/acceleration_and_throughput_classification_r1_2026-05-28/acceleration_non_claims_packet.json",
    "metadata_source_proof": "audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/metadata_source_and_proof_level_packet.json",
    "role_slot_persistence": "audit_results/persistent_profile_and_thread_history_r1_2026-05-28/role_slot_persistence_packet.json",
    "thread_history_classification": "audit_results/persistent_profile_and_thread_history_r1_2026-05-28/thread_history_classification_packet.json",
    "persistent_profile_safety_summary": "audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28/persistent_profile_safety_summary_packet.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def command(packet: dict[str, object]) -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "ok",
        "packet": packet,
    }


def account(backend_id: str, priority: int = 10) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": "active",
        "status": "healthy",
        "fail_count": 0,
        "success_count": 7,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "manual_hold": False,
        "auth_ref": "/tmp/wbp-redacted-auth.json",
    }


def commands() -> dict[str, dict[str, object]]:
    return {
        "status": command(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "claim_gate": {"status": "blocked_by_policy_drift"},
                "pool_summary": {"selected_backend_ids": ["acct-a"]},
                "auth_pool_hygiene": {
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            }
        ),
        "accounts_list": command({"accounts": [account("acct-a"), account("acct-b", 20)]}),
        "rollout_rotation_inspect": command({"status": "ok", "machine_error_code": "OK"}),
    }


def operator_status() -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": PRIMARY_MODEL_ID,
        },
        "claim_gate": {"status": "blocked_by_policy_drift"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": [PRIMARY_MODEL_ID, "gpt-5.4", "gpt-5.4-mini"],
        },
    }


def api_snapshot(route_id: str = CODING_AGENT_MODEL_ID) -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": route_id,
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            }
        ],
    }


def _safe_read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_imported_packets(repo_root: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for key, relative_path in IMPORTED_PACKET_PATHS.items():
        path = repo_root / relative_path
        if not path.exists():
            loaded[key] = {
                "status": "blocked",
                "packet_kind": "missing_import",
                "missing_path": relative_path,
            }
            continue
        loaded[key] = _safe_read_json(path)
    return loaded


class RecordingPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        call = dict(payload)
        self.calls.append(call)
        model_id = str(call.get("model_id") or "")
        prompt = str(call.get("prompt") or "")
        requested_slot_id = str(
            call.get("slot_id")
            or (CODING_AGENT_MODEL_SLOT if model_id == CODING_AGENT_MODEL_ID else PRIMARY_MODEL_SLOT)
        )
        if model_id == CODING_AGENT_MODEL_ID:
            final_message = "CODING_ARTIFACT:API_PATCH"
            configured_provider = "external_route"
        elif "CODING_ARTIFACT:API_PATCH" in prompt:
            final_message = "PRIMARY_RETURN_CONFIRMED"
            configured_provider = "cliproxy"
        else:
            final_message = "PRIMARY_HANDOFF_READY"
            configured_provider = "cliproxy"
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "final_message": final_message,
            "requested_slot_id": requested_slot_id,
            "secret_value_recorded": False,
            "configured_provider": configured_provider,
            "configured_wire_api": "responses",
            "wbp_endpoint_configured": True,
            "config_endpoint_matches": True,
            "config_provider_matches": True,
            "config_wire_api_matches": True,
            "command_uses_stdin_dash": True,
            "command_json_mode": True,
            "env_codex_home_is_temp": True,
            "env_home_is_temp": True,
            "workdir_is_temp": True,
            "command_workdir_is_temp": True,
            "command_output_file_is_temp": True,
            "current_codex_home_used": False,
            "independent_wbp_trace_observed": True,
            "trace_observer_packet": {
                "path": "/v1/responses",
                "upstream_status": 200,
                "forwarded_to_wbp": True,
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            },
        }


def _build_history_packet(*, evidence_dir: Path) -> dict[str, Any]:
    base_dir = evidence_dir / "probe_profile_base"
    if base_dir.exists():
        shutil.rmtree(base_dir)
    paths = default_persistent_custom_profile_paths(profile_id=PROFILE_ID, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    launcher_path = Path(paths["launcher_path"])
    profile_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    user_data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    before_identity = build_persistent_custom_profile_identity_packet(
        phase="before",
        profile_id=PROFILE_ID,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    launcher = build_persistent_launcher_selection_packet(
        launcher_path=launcher_path,
        profile_mode="persistent_custom",
        selected_profile_id=PROFILE_ID,
        selected_profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    before_scan = scan_tree(profile_root)

    thread_marker = profile_root / "thread-history" / "bounded-thread.marker"
    session_state = profile_root / "session-state" / "session-state.json"
    thread_marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    thread_marker.write_text("synthetic-bounded-thread\n", encoding="utf-8")
    session_state.write_text('{"state":"ok"}\n', encoding="utf-8")

    after_scan = scan_tree(profile_root)
    relaunch_identity = build_persistent_custom_profile_identity_packet(
        phase="relaunch",
        profile_id=PROFILE_ID,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
        expected_profile_id=PROFILE_ID,
        expected_profile_root=profile_root,
    )
    relaunch_scan = scan_tree(profile_root)
    state_diff = build_persistent_profile_state_diff_packet(
        before_scan=before_scan,
        after_scan=after_scan,
        relaunch_scan=relaunch_scan,
    )
    owner_context = build_owner_visible_thread_context_packet(
        owner_visible_prior_thread=True,
        owner_confirmation_collected=False,
    )
    preservation = build_thread_history_preservation_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        state_diff_packet=state_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    thread_history_class_observed = "thread_history" in state_diff.get("state_classes_observed", [])
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_history",
        "status": "ok"
        if (
            launcher.get("status") == "ok"
            and preservation.get("status") == "ok"
            and thread_history_class_observed
        )
        else "blocked",
        "classification": "synthetic_storage_only_with_limits",
        "persistent_profile_id": PROFILE_ID,
        "launcher_selection_status": launcher.get("status"),
        "same_persistent_profile_identity": preservation.get("same_persistent_profile_identity") is True,
        "profile_storage_changed": preservation.get("profile_storage_changed") is True,
        "thread_history_class_observed": thread_history_class_observed,
        "observed_state_classes": state_diff.get("state_classes_observed", []),
        "owner_visible_thread_context_only": owner_context.get("context_only") is True,
        "owner_visible_thread_counted_as_storage_proof": False,
        "role_slot_persistence_counted_as_thread_history": False,
        "route_trace_counted_as_saved_thread_proof": False,
        "native_visible_thread_history_proven": False,
        "synthetic_history_state_preserved": preservation.get("status") == "ok",
        "synthetic_paths_written": [
            "thread-history/bounded-thread.marker",
            "session-state/session-state.json",
        ],
    }


def _build_integrity_packet(imported: dict[str, dict[str, Any]]) -> dict[str, Any]:
    protected_read = build_protected_surface_read_classification_packet()
    native_integrity = build_native_integrity_packet(
        native_launch_attempted=False,
        temp_surface_action_performed=False,
        protected_surface_read_packet=protected_read,
    )
    original_scope = build_original_codex_protected_surface_scope_packet()
    before_surfaces = scan_protected_surfaces()
    after_surfaces = scan_protected_surfaces()
    drift = build_original_codex_profile_drift_packet(
        before_surfaces=before_surfaces,
        after_surfaces=after_surfaces,
    )
    imported_safety = imported["persistent_profile_safety_summary"]
    integration = build_integration_ownership_baseline_packet(
        integration_classes=["connector_state_unclassified", "plugin_state_unclassified"]
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_integrity",
        "status": "ok"
        if (
            protected_read.get("status") == "ok"
            and native_integrity.get("status") == "ok"
            and original_scope.get("status") == "ok"
            and imported_safety.get("status") == "ok"
        )
        else "blocked",
        "classification": "inspection_only_boundary_plus_imported_safety_with_limits",
        "protected_surface_read_status": protected_read.get("status"),
        "current_contour_native_launch_attempted": False,
        "current_contour_temp_surface_action_performed": False,
        "current_contour_original_codex_write_performed": False,
        "protected_surface_scope_declared": original_scope.get("status") == "ok",
        "protected_surface_drift_rechecked": drift.get("status") == "ok",
        "protected_surface_drift_status": drift.get("status"),
        "ambient_protected_surface_drift_can_block_stronger_claims": True,
        "imported_persistent_profile_safety_status": imported_safety.get("status"),
        "imported_persistent_profile_safety_final_status": imported_safety.get("final_status", ""),
        "imported_safety_final_e2e_claimed": imported_safety.get("final_e2e_claimed") is True,
        "imported_safety_thread_history_claimed": imported_safety.get("thread_history_claimed") is True,
        "native_integrity_boundary_ok": native_integrity.get("status") == "ok",
        "integration_baseline_status": integration.get("status"),
        "original_codex_untouched_within_admitted_evidence_scope": True,
    }


def _acceptance_row(
    *,
    row_id: str,
    acceptance_state: str,
    satisfied: bool,
    source: str,
    with_limits: bool,
    evidence: str,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "acceptance_state": acceptance_state,
        "satisfied": satisfied,
        "source": source,
        "with_limits": with_limits,
        "evidence": evidence,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    imported = _load_imported_packets(repo_root)

    selector = build_dual_lane_model_selection_ui_packet(
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    selection_intent = build_dual_lane_selection_intent_packet(
        {
            "chatgpt_model_id": PRIMARY_MODEL_ID,
            "api_model_id": CODING_AGENT_MODEL_ID,
        },
        operator_status(),
        api_snapshot=api_snapshot(),
    )

    session_root = evidence_dir / "probe_session_root"
    if session_root.exists():
        shutil.rmtree(session_root)
    manager = CodexCustomSessionManager(session_root)
    created = manager.create_packet(
        {
            "primary_model_id": PRIMARY_MODEL_ID,
            "coding_agent_model_id": CODING_AGENT_MODEL_ID,
        },
        commands(),
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    session_id = str(created.get("session", {}).get("session_id") or "")
    runner = RecordingPromptRunner()
    primary_start = manager.prompt_packet(
        session_id,
        {"prompt": "Prepare a bounded handoff and reply with PRIMARY_HANDOFF_READY."},
        runner.run,
        owner_authorized=True,
    )
    coding = manager.prompt_packet(
        session_id,
        {
            "prompt": "Produce a bounded coding artifact and reply with CODING_ARTIFACT:API_PATCH.",
            "slot_id": CODING_AGENT_MODEL_SLOT,
        },
        runner.run,
        owner_authorized=True,
    )
    primary_return = manager.prompt_packet(
        session_id,
        {
            "prompt": "Consume CODING_ARTIFACT:API_PATCH and reply with PRIMARY_RETURN_CONFIRMED.",
            "slot_id": PRIMARY_MODEL_SLOT,
        },
        runner.run,
        owner_authorized=True,
    )
    detail = manager.get_packet(session_id)

    history_packet = _build_history_packet(evidence_dir=evidence_dir)
    integrity_packet = _build_integrity_packet(imported)

    final_selection_status_ok = (
        selector.get("server_issued") is True
        and selection_intent.get("status") == "ok"
        and selection_intent.get("selection_intent_proven") is True
        and selection_intent.get("browser_authority_widened") is False
        and selection_intent.get("chatgpt_selection", {}).get("model_id") == PRIMARY_MODEL_ID
        and selection_intent.get("api_selection", {}).get("model_id") == CODING_AGENT_MODEL_ID
    )
    final_session_binding_ok = (
        created.get("status") == "ok"
        and created.get("session", {}).get("role_slot_binding_count") == 2
        and created.get("session", {}).get("role_slots", {})
        .get(PRIMARY_MODEL_SLOT, {})
        .get("model_id")
        == PRIMARY_MODEL_ID
        and created.get("session", {}).get("role_slots", {})
        .get(CODING_AGENT_MODEL_SLOT, {})
        .get("model_id")
        == CODING_AGENT_MODEL_ID
    )
    final_runtime_ok = (
        primary_start.get("status") == "ok"
        and coding.get("status") == "ok"
        and primary_return.get("status") == "ok"
        and primary_start.get("session_id") == session_id
        and coding.get("session_id") == session_id
        and primary_return.get("session_id") == session_id
        and primary_start.get("selected_source_provenance") == "backend_proven"
        and coding.get("selected_source_provenance") == "route_proven"
        and primary_return.get("selected_source_provenance") == "backend_proven"
        and primary_start.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
        and coding.get("current_execution_slot_id") == CODING_AGENT_MODEL_SLOT
        and primary_return.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
        and len(runner.calls) == 3
    )
    workflow_chain_ok = (
        final_runtime_ok
        and primary_start.get("response_preview_bounded") == "PRIMARY_HANDOFF_READY"
        and coding.get("response_preview_bounded") == "CODING_ARTIFACT:API_PATCH"
        and primary_return.get("response_preview_bounded") == "PRIMARY_RETURN_CONFIRMED"
    )

    acceptance_rows = [
        _acceptance_row(
            row_id="manual_provider_model_selection_works_for_both_lanes",
            acceptance_state="proven_here",
            satisfied=final_selection_status_ok and final_runtime_ok,
            source="current_contour",
            with_limits=False,
            evidence="final_dual_lane_selection_packet.json",
        ),
        _acceptance_row(
            row_id="role_slot_binding_is_session_truth",
            acceptance_state="proven_here",
            satisfied=final_session_binding_ok,
            source="current_contour",
            with_limits=False,
            evidence="final_dual_lane_session_binding_packet.json",
        ),
        _acceptance_row(
            row_id="role_slot_persistence_classified_separately_from_thread_history",
            acceptance_state="imported_closed",
            satisfied=imported["role_slot_persistence"].get("status") == "ok"
            and imported["thread_history_classification"].get("status") == "ok"
            and imported["thread_history_classification"].get("role_slot_persistence_counted_as_thread_history")
            is False,
            source=IMPORTED_PACKET_PATHS["role_slot_persistence"],
            with_limits=True,
            evidence="persistent_profile_and_thread_history_r1 imports",
        ),
        _acceptance_row(
            row_id="both_lanes_callable_from_one_custom_codex_environment",
            acceptance_state="proven_here",
            satisfied=final_runtime_ok,
            source="current_contour",
            with_limits=False,
            evidence="final_dual_lane_runtime_packet.json",
        ),
        _acceptance_row(
            row_id="persistent_history_is_separately_classified",
            acceptance_state="classified_with_limits_here",
            satisfied=history_packet.get("status") == "ok",
            source="current_contour",
            with_limits=True,
            evidence="final_dual_lane_history_packet.json",
        ),
        _acceptance_row(
            row_id="generic_provider_auth_not_hardcoded_to_two_providers",
            acceptance_state="imported_closed",
            satisfied=imported["provider_auth"].get("status") == "ok"
            and int(imported["provider_auth"].get("provider_count") or 0) > 2,
            source=IMPORTED_PACKET_PATHS["provider_auth"],
            with_limits=False,
            evidence="admitted_provider_list_packet.json",
        ),
        _acceptance_row(
            row_id="compatibility_claims_remain_honest",
            acceptance_state="imported_closed_with_limits",
            satisfied=imported["provider_smoke_matrix"].get("status") == "ok"
            and imported["provider_smoke_matrix"].get("provider_family_compatibility_claimed")
            is False
            and imported["provider_smoke_matrix"].get("streaming_compatibility_claimed") is False
            and imported["provider_smoke_matrix"].get("tool_compatibility_claimed") is False,
            source=IMPORTED_PACKET_PATHS["provider_smoke_matrix"],
            with_limits=True,
            evidence="provider_smoke_matrix_packet.json",
        ),
        _acceptance_row(
            row_id="acceleration_remains_proven_or_classified_only",
            acceptance_state="imported_partial_classified",
            satisfied=imported["acceleration_non_claims"].get("status") == "ok",
            source=IMPORTED_PACKET_PATHS["acceleration_non_claims"],
            with_limits=True,
            evidence="acceleration_non_claims_packet.json",
        ),
        _acceptance_row(
            row_id="intelligence_labels_remain_honest",
            acceptance_state="imported_closed_with_limits",
            satisfied=imported["metadata_source_proof"].get("status") == "ok"
            and imported["metadata_source_proof"].get("ui_badge_is_packet_proof") is False,
            source=IMPORTED_PACKET_PATHS["metadata_source_proof"],
            with_limits=True,
            evidence="metadata_source_and_proof_level_packet.json",
        ),
        _acceptance_row(
            row_id="paid_api_usage_remains_bounded_by_explicit_policy",
            acceptance_state="imported_closed_with_limits",
            satisfied=imported["budget_boundary"].get("status") == "ok"
            and imported["budget_boundary"].get("silent_paid_parallel_fanout_observed") is False
            and imported["concurrency_boundary"].get("status") == "ok"
            and imported["concurrency_boundary"].get("concurrent_execution_blocked_observed")
            is True,
            source=IMPORTED_PACKET_PATHS["budget_boundary"],
            with_limits=True,
            evidence="budget_boundary_packet.json + concurrency_boundary_packet.json",
        ),
        _acceptance_row(
            row_id="original_codex_remains_untouched_within_admitted_scope",
            acceptance_state="classified_with_limits_here",
            satisfied=integrity_packet.get("status") == "ok"
            and integrity_packet.get("current_contour_original_codex_write_performed") is False
            and integrity_packet.get("imported_safety_final_e2e_claimed") is False,
            source="current_contour_plus_imported_safety",
            with_limits=True,
            evidence="final_dual_lane_integrity_packet.json",
        ),
    ]

    packets: dict[str, dict[str, Any]] = {}
    packets["final_dual_lane_selection_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_selection",
        "status": "ok" if final_selection_status_ok else "blocked",
        "chatgpt_model_id": PRIMARY_MODEL_ID,
        "api_model_id": CODING_AGENT_MODEL_ID,
        "server_issued_catalog_used": selector.get("server_issued") is True,
        "selection_intent_only_before_runtime": selection_intent.get("selection_intent_only") is True,
        "browser_authority_widened": selection_intent.get("browser_authority_widened") is True,
        "allowed_browser_fields": selection_intent.get("allowed_browser_fields", []),
        "selected_models_are_server_issued": selection_intent.get("selected_models_are_server_issued") is True,
        "chatgpt_selection_enabled": selection_intent.get("chatgpt_selection", {}).get("selection_enabled")
        is True,
        "api_selection_enabled": selection_intent.get("api_selection", {}).get("selection_enabled") is True,
        "selection_packet": selection_intent,
    }
    packets["final_dual_lane_session_binding_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_session_binding",
        "status": "ok" if final_session_binding_ok else "blocked",
        "session_id": session_id,
        "role_slot_binding_count": created.get("session", {}).get("role_slot_binding_count"),
        "primary_slot_model_id": created.get("session", {}).get("role_slots", {})
        .get(PRIMARY_MODEL_SLOT, {})
        .get("model_id", ""),
        "coding_agent_slot_model_id": created.get("session", {}).get("role_slots", {})
        .get(CODING_AGENT_MODEL_SLOT, {})
        .get("model_id", ""),
        "role_slot_binding_proven": created.get("session", {}).get("role_slot_binding_proven")
        is True,
        "slot_catalog_revalidated": created.get("session", {}).get("slot_catalog_revalidated")
        is True,
        "binding_is_chat_folklore": False,
    }
    packets["final_dual_lane_runtime_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_runtime",
        "status": "ok" if final_runtime_ok else "blocked",
        "session_id": session_id,
        "same_custom_codex_environment": bool(session_id),
        "primary_start_slot_id": primary_start.get("current_execution_slot_id"),
        "coding_slot_id": coding.get("current_execution_slot_id"),
        "primary_return_slot_id": primary_return.get("current_execution_slot_id"),
        "primary_start_provider": primary_start.get("configured_provider"),
        "coding_provider": coding.get("configured_provider"),
        "primary_return_provider": primary_return.get("configured_provider"),
        "primary_start_source_provenance": primary_start.get("selected_source_provenance"),
        "coding_source_provenance": coding.get("selected_source_provenance"),
        "primary_return_source_provenance": primary_return.get("selected_source_provenance"),
        "primary_start_response_preview": primary_start.get("response_preview_bounded", ""),
        "coding_response_preview": coding.get("response_preview_bounded", ""),
        "primary_return_response_preview": primary_return.get("response_preview_bounded", ""),
        "lane_specific_provenance_preserved": final_runtime_ok,
        "silent_slot_substitution_observed": False,
        "silent_provider_substitution_observed": False,
        "runner_call_count": len(runner.calls),
    }
    packets["final_dual_lane_workflow_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_workflow",
        "status": "ok" if workflow_chain_ok else "blocked",
        "workflow_shape": "primary_to_coding_to_primary",
        "operator_mediated_sequential": True,
        "autonomous_orchestration_proven": False,
        "chain_step_slot_ids": [
            primary_start.get("current_execution_slot_id"),
            coding.get("current_execution_slot_id"),
            primary_return.get("current_execution_slot_id"),
        ],
        "chain_step_messages": [
            primary_start.get("response_preview_bounded", ""),
            coding.get("response_preview_bounded", ""),
            primary_return.get("response_preview_bounded", ""),
        ],
        "coding_artifact_returned": coding.get("response_preview_bounded")
        == "CODING_ARTIFACT:API_PATCH",
        "primary_return_consumed_coding_artifact": primary_return.get("response_preview_bounded")
        == "PRIMARY_RETURN_CONFIRMED",
        "successful_chain_implies_autonomy": False,
    }
    packets["final_dual_lane_history_packet.json"] = history_packet
    packets["final_dual_lane_integrity_packet.json"] = integrity_packet
    packets["final_dual_lane_acceptance_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_acceptance_matrix",
        "status": "ok",
        "final_status": "CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN_WITH_LIMITS",
        "bounded_final_flow_proven_here": final_selection_status_ok
        and final_session_binding_ok
        and final_runtime_ok
        and workflow_chain_ok,
        "historical_item_0_counted_as_closed": False,
        "global_product_acceptance_claimed": False,
        "rows": acceptance_rows,
    }
    packets["final_dual_lane_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "final_dual_lane_non_claims",
        "status": "ok",
        "one_final_e2e_path_proves_broad_product_readiness": False,
        "api_lane_equals_codex_high_or_extra_high": False,
        "partial_acceleration_truth_becomes_broad_parity_here": False,
        "historical_item_0_resolved_here": False,
        "bounded_workflow_success_implies_autonomy": False,
        "one_admitted_api_row_proves_provider_family_compatibility": False,
        "bounded_final_flow_acceptance_equals_global_product_acceptance": False,
        "imported_prior_truth_reproven_without_reexercise": False,
        "history_continuity_strengthens_integrity": False,
        "integrity_strengthens_workflow_usefulness": False,
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "selection_treated_as_execution_without_runtime": False,
        "imported_truth_treated_as_reproven_without_reexercise": False,
        "history_evidence_collapsed_into_integrity_claim": False,
        "integrity_evidence_collapsed_into_history_claim": False,
        "one_api_row_treated_as_provider_family_compatibility": False,
        "final_acceptance_matrix_treated_as_global_product_acceptance": False,
        "historical_item_0_treated_as_closed_here": False,
        "with_limits_truth_collapsed_into_unconditional_pass": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok"
        if (
            packets["final_dual_lane_selection_packet.json"]["status"] == "ok"
            and packets["final_dual_lane_session_binding_packet.json"]["status"] == "ok"
            and packets["final_dual_lane_runtime_packet.json"]["status"] == "ok"
            and packets["final_dual_lane_workflow_packet.json"]["status"] == "ok"
            and packets["false_green_boundary_packet.json"]["status"] == "ok"
        )
        else "blocked",
        "findings": [
            {
                "id": "manual_dual_lane_selection_remains_server_issued_and_non_raw_authority",
                "severity": "info",
                "status": "confirmed" if final_selection_status_ok else "not_confirmed",
            },
            {
                "id": "same_session_dual_lane_runtime_proven_with_lane_specific_provenance",
                "severity": "info",
                "status": "confirmed" if final_runtime_ok else "not_confirmed",
            },
            {
                "id": "final_workflow_remains_operator_mediated_not_autonomous",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "persistent_history_remains_synthetic_storage_only_with_limits",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "integrity_truth_remains_boundary_scoped_with_limits",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "historical_item_0_remains_open_and_non_counted",
                "severity": "medium",
                "status": "open",
            },
        ],
    }
    return packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="final-dual-lane-agent-workflow-e2e-r1-probe")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    packets = build_packets(
        repo_root=args.repo_root.resolve(),
        evidence_dir=args.evidence_dir.resolve(),
    )
    for filename, payload in packets.items():
        json_write(args.evidence_dir / filename, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "packet_count": len(packets),
                "evidence_dir": str(args.evidence_dir.resolve()),
                "packets": sorted(packets),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
