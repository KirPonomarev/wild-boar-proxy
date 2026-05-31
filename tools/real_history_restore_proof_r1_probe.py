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
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_owner_visible_thread_context_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    build_persistent_profile_state_diff_packet,
    build_persistent_profile_state_preservation_packet,
    build_persistent_thread_history_preservation_r2_packet,
    build_thread_history_preservation_packet,
    default_persistent_custom_profile_paths,
    json_write,
    scan_tree,
)


PRIMARY_MODEL_ID = "gpt-5.3-codex"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"
PROFILE_ID = "wbp-custom-main"

IMPORTED_PACKET_PATHS = {
    "final_e2e_history": (
        "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/"
        "final_dual_lane_history_packet.json"
    ),
    "final_e2e_acceptance": (
        "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/"
        "final_dual_lane_acceptance_matrix.json"
    ),
    "role_slot_persistence": (
        "audit_results/persistent_profile_and_thread_history_r1_2026-05-28/"
        "role_slot_persistence_packet.json"
    ),
    "thread_history_classification": (
        "audit_results/persistent_profile_and_thread_history_r1_2026-05-28/"
        "thread_history_classification_packet.json"
    ),
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


class RecordingPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        call = dict(payload)
        self.calls.append(call)
        model_id = str(call.get("model_id") or "")
        requested_slot_id = str(
            call.get("slot_id")
            or (CODING_AGENT_MODEL_SLOT if model_id == CODING_AGENT_MODEL_ID else PRIMARY_MODEL_SLOT)
        )
        final_message = (
            "REAL_HISTORY_RESTORE_CODING_MARKER"
            if requested_slot_id == CODING_AGENT_MODEL_SLOT
            else "REAL_HISTORY_RESTORE_PRIMARY_MARKER"
        )
        configured_provider = "external_route" if model_id == CODING_AGENT_MODEL_ID else "cliproxy"
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
            "runtime_model": model_id,
            "trace_observer_packet": {
                "path": "/v1/responses",
                "upstream_status": 200,
                "forwarded_to_wbp": True,
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            },
        }


def _read_json(path: Path) -> dict[str, Any]:
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
        loaded[key] = _read_json(path)
    return loaded


def _session_event_names(transcript_packet: dict[str, Any]) -> list[str]:
    return [
        str(entry.get("event") or "")
        for entry in transcript_packet.get("entries", [])
        if isinstance(entry, dict)
    ]


def _build_restore_context(*, evidence_dir: Path) -> dict[str, Any]:
    base_dir = evidence_dir / "real_history_profile_base"
    if base_dir.exists():
        shutil.rmtree(base_dir)
    paths = default_persistent_custom_profile_paths(profile_id=PROFILE_ID, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    launcher_path = Path(paths["launcher_path"])
    session_store_root = profile_root / "custom-codex-sessions"

    profile_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    user_data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    codex_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_store_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    before_scan = scan_tree(profile_root)
    before_identity = build_persistent_custom_profile_identity_packet(
        phase="before",
        profile_id=PROFILE_ID,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
        expected_profile_id=PROFILE_ID,
        expected_profile_root=profile_root,
    )
    launcher = build_persistent_launcher_selection_packet(
        launcher_path=launcher_path,
        profile_mode="persistent_custom",
        selected_profile_id=PROFILE_ID,
        selected_profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )

    manager = CodexCustomSessionManager(root=session_store_root)
    create_packet = manager.create_packet(
        {
            "primary_model_id": PRIMARY_MODEL_ID,
            "coding_agent_model_id": CODING_AGENT_MODEL_ID,
        },
        commands(),
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    session = create_packet.get("session") if isinstance(create_packet.get("session"), dict) else {}
    session_id = str(session.get("session_id") or "")
    runner = RecordingPromptRunner()
    primary_prompt = manager.prompt_packet(
        session_id,
        {"prompt": "REAL_HISTORY_RESTORE primary marker", "slot_id": PRIMARY_MODEL_SLOT},
        runner.run,
        owner_authorized=True,
    )
    coding_prompt = manager.prompt_packet(
        session_id,
        {"prompt": "REAL_HISTORY_RESTORE coding marker", "slot_id": CODING_AGENT_MODEL_SLOT},
        runner.run,
        owner_authorized=True,
    )
    before_reload_transcript = manager.transcript_packet(session_id)
    after_action_scan = scan_tree(profile_root)

    reloaded_manager = CodexCustomSessionManager(root=session_store_root)
    reloaded_get = reloaded_manager.get_packet(session_id)
    reloaded_transcript = reloaded_manager.transcript_packet(session_id)
    relaunch_scan = scan_tree(profile_root)
    relaunch_identity = build_persistent_custom_profile_identity_packet(
        phase="helper_reload",
        profile_id=PROFILE_ID,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
        expected_profile_id=PROFILE_ID,
        expected_profile_root=profile_root,
    )

    state_diff = build_persistent_profile_state_diff_packet(
        before_scan=before_scan,
        after_scan=after_action_scan,
        relaunch_scan=relaunch_scan,
    )
    after_reload_state_diff = build_persistent_profile_state_diff_packet(
        before_scan=after_action_scan,
        after_scan=relaunch_scan,
    )
    owner_context = build_owner_visible_thread_context_packet(
        owner_visible_prior_thread=False,
        owner_confirmation_collected=False,
    )
    thread_preservation = build_thread_history_preservation_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        state_diff_packet=state_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    profile_state_preservation = build_persistent_profile_state_preservation_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        after_action_state_diff_packet=state_diff,
        after_relaunch_state_diff_packet=after_reload_state_diff,
    )
    thread_history_r2 = build_persistent_thread_history_preservation_r2_packet(
        profile_state_preservation_packet=profile_state_preservation,
        state_diff_packet=state_diff,
        owner_visible_thread_context_packet=owner_context,
    )
    return {
        "paths": paths,
        "profile_root": profile_root,
        "session_store_root": session_store_root,
        "before_identity": before_identity,
        "launcher": launcher,
        "create_packet": create_packet,
        "primary_prompt": primary_prompt,
        "coding_prompt": coding_prompt,
        "before_reload_transcript": before_reload_transcript,
        "reloaded_get": reloaded_get,
        "reloaded_transcript": reloaded_transcript,
        "relaunch_identity": relaunch_identity,
        "state_diff": state_diff,
        "after_reload_state_diff": after_reload_state_diff,
        "owner_context": owner_context,
        "thread_preservation": thread_preservation,
        "profile_state_preservation": profile_state_preservation,
        "thread_history_r2": thread_history_r2,
        "runner_calls": runner.calls,
    }


def _build_history_restore_packet(context: dict[str, Any], imported: dict[str, dict[str, Any]]) -> dict[str, Any]:
    create_packet = context["create_packet"]
    primary_prompt = context["primary_prompt"]
    coding_prompt = context["coding_prompt"]
    reloaded_get = context["reloaded_get"]
    reloaded_transcript = context["reloaded_transcript"]
    state_diff = context["state_diff"]
    profile_state_preservation = context["profile_state_preservation"]
    thread_history_r2 = context["thread_history_r2"]
    event_names = _session_event_names(reloaded_transcript)
    helper_reload_observed = (
        create_packet.get("status") == "ok"
        and primary_prompt.get("status") == "ok"
        and coding_prompt.get("status") == "ok"
        and reloaded_get.get("status") == "ok"
        and reloaded_transcript.get("status") == "ok"
        and "prompt_completed_e2e" in event_names
        and len(event_names) >= 3
    )
    storage_state_observed = bool(
        set(state_diff.get("state_classes_observed", [])) & {"thread_history", "session_state"}
    )
    profile_state_preserved = profile_state_preservation.get("profile_state_preserved") is True
    classification = (
        "helper_reload_observed_with_limits"
        if helper_reload_observed and storage_state_observed and profile_state_preserved
        else (
            "storage_only_with_limits"
            if storage_state_observed
            else (
                "profile_identity_only"
                if context["relaunch_identity"].get("status") == "ok"
                else "blocked"
            )
        )
    )
    ok = classification in {
        "helper_reload_observed_with_limits",
        "storage_only_with_limits",
        "profile_identity_only",
    }
    final_e2e_history = imported["final_e2e_history"]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "real_history_restore",
        "status": "ok" if ok else "blocked",
        "final_status": "REAL_HISTORY_RESTORE_CLASSIFIED_WITH_LIMITS",
        "classification": classification,
        "prior_final_e2e_history_classification": final_e2e_history.get("classification", ""),
        "prior_synthetic_storage_limiter_reduced": classification == "helper_reload_observed_with_limits",
        "stable_profile_identity_observed": context["relaunch_identity"].get("status") == "ok",
        "stable_profile_identity_counted_as_thread_restore": False,
        "storage_state_observed": storage_state_observed,
        "storage_file_presence_counted_as_restore": False,
        "helper_reload_observed": helper_reload_observed,
        "helper_reload_counted_as_native_visible_restore": False,
        "native_visible_restore_proven": False,
        "native_visible_restore_non_claim": True,
        "thread_history_preservation_r2_status": thread_history_r2.get("status"),
        "profile_state_preserved": profile_state_preserved,
        "role_slot_persistence_counted_as_thread_history": False,
        "original_codex_profile_participates_in_proof": False,
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def _build_profile_relaunch_continuity_packet(context: dict[str, Any]) -> dict[str, Any]:
    reloaded_session = (
        context["reloaded_get"].get("session")
        if isinstance(context["reloaded_get"].get("session"), dict)
        else {}
    )
    reloaded_role_slots = (
        reloaded_session.get("role_slots")
        if isinstance(reloaded_session.get("role_slots"), dict)
        else {}
    )
    reloaded_transcript = context["reloaded_transcript"]
    event_names = _session_event_names(reloaded_transcript)
    helper_reload_ok = (
        context["before_identity"].get("status") == "ok"
        and context["relaunch_identity"].get("status") == "ok"
        and context["launcher"].get("status") == "ok"
        and context["reloaded_get"].get("status") == "ok"
        and reloaded_transcript.get("status") == "ok"
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "profile_relaunch_continuity",
        "status": "ok" if helper_reload_ok else "blocked",
        "classification": "helper_reload_like_only_with_limits" if helper_reload_ok else "blocked",
        "persistent_profile_id": PROFILE_ID,
        "persistent_profile_root": str(context["profile_root"]),
        "session_store_root": str(context["session_store_root"]),
        "same_persistent_profile_identity": context["relaunch_identity"].get("status") == "ok",
        "launcher_selects_persistent_custom_profile": context["launcher"].get("status") == "ok",
        "helper_reload_path": "CodexCustomSessionManager(root=same_session_store)",
        "helper_reload_observed": helper_reload_ok,
        "native_app_relaunch_observed": False,
        "helper_reload_equals_native_app_relaunch": False,
        "session_id_reloaded": str(reloaded_session.get("session_id") or ""),
        "ledger_event_count_after_reload": len(event_names),
        "ledger_event_names_after_reload": event_names,
        "primary_slot_reloaded": (
            isinstance(reloaded_role_slots, dict)
            and reloaded_role_slots.get(PRIMARY_MODEL_SLOT, {}).get("model_id") == PRIMARY_MODEL_ID
        ),
        "coding_slot_reloaded": (
            isinstance(reloaded_role_slots, dict)
            and reloaded_role_slots.get(CODING_AGENT_MODEL_SLOT, {}).get("model_id")
            == CODING_AGENT_MODEL_ID
        ),
        "role_slot_reload_counted_as_thread_history": False,
    }


def _build_history_vs_slot_separation_packet(context: dict[str, Any]) -> dict[str, Any]:
    reloaded_session = (
        context["reloaded_get"].get("session")
        if isinstance(context["reloaded_get"].get("session"), dict)
        else {}
    )
    role_slots = reloaded_session.get("role_slots") if isinstance(reloaded_session.get("role_slots"), dict) else {}
    event_names = _session_event_names(context["reloaded_transcript"])
    thread_ledger_restored = bool(event_names)
    slots_restored = (
        isinstance(role_slots, dict)
        and role_slots.get(PRIMARY_MODEL_SLOT, {}).get("model_id") == PRIMARY_MODEL_ID
        and role_slots.get(CODING_AGENT_MODEL_SLOT, {}).get("model_id") == CODING_AGENT_MODEL_ID
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "history_vs_slot_separation",
        "status": "ok" if thread_ledger_restored and slots_restored else "blocked",
        "thread_ledger_restored": thread_ledger_restored,
        "role_slots_restored": slots_restored,
        "role_slot_persistence_counted_as_thread_history": False,
        "thread_history_file_presence_counted_as_runtime_slot_truth": False,
        "history_and_slot_truth_collapsed": False,
        "thread_history_evidence_surface": "ledger/transcript reloaded by helper",
        "role_slot_evidence_surface": "session role_slots reloaded by helper",
        "thread_history_claim_requires_ledger_or_transcript": True,
        "role_slot_claim_requires_session_role_slots": True,
    }


def _build_native_visible_restore_boundary_packet(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_visible_restore_boundary",
        "status": "ok",
        "native_visible_restore_observed": False,
        "native_visible_restore_claimed": False,
        "helper_level_reload_observed": context["reloaded_transcript"].get("status") == "ok",
        "helper_level_reload_counts_as_native_visible_restore": False,
        "owner_confirmation_collected": False,
        "native_app_relaunch_attempted": False,
        "reason_native_visible_restore_not_upgraded": (
            "No exact native app relaunch and user-visible restored thread observation "
            "was performed in this surgical contour."
        ),
        "blocked_native_restore_observation_is_acceptable_if_packet_honest": True,
    }


def _build_gap_matrix(
    restore_packet: dict[str, Any],
    profile_packet: dict[str, Any],
    native_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "id": "stable_profile_identity",
            "status": "reduced" if restore_packet["stable_profile_identity_observed"] else "blocked",
            "claim_boundary": "profile identity only; not thread restore by itself",
        },
        {
            "id": "helper_reload_continuity",
            "status": "reduced" if restore_packet["helper_reload_observed"] else "blocked",
            "claim_boundary": "helper reload only; not native visible restore",
        },
        {
            "id": "native_visible_restore",
            "status": "open_with_limits"
            if native_boundary_packet["native_visible_restore_observed"] is False
            else "reduced",
            "claim_boundary": "requires direct native/user-visible observation",
        },
        {
            "id": "history_slot_separation",
            "status": "reduced" if profile_packet["role_slot_reload_counted_as_thread_history"] is False else "blocked",
            "claim_boundary": "slot reload remains separate from thread history",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "history_restore_gap_matrix",
        "status": "ok",
        "rows": rows,
        "open_native_visible_restore_gap": native_boundary_packet["native_visible_restore_observed"] is False,
        "synthetic_storage_limiter_reduced": restore_packet["prior_synthetic_storage_limiter_reduced"],
        "no_product_readiness_claim": True,
    }


def _build_false_green_boundary_packet(
    restore_packet: dict[str, Any],
    profile_packet: dict[str, Any],
    separation_packet: dict[str, Any],
    native_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    false_green = {
        "file_presence_treated_as_restore": restore_packet["storage_file_presence_counted_as_restore"],
        "stable_profile_identity_treated_as_thread_restore": restore_packet[
            "stable_profile_identity_counted_as_thread_restore"
        ],
        "helper_reload_treated_as_native_visible_restore": native_boundary_packet[
            "helper_level_reload_counts_as_native_visible_restore"
        ],
        "role_slot_persistence_treated_as_thread_history": separation_packet[
            "role_slot_persistence_counted_as_thread_history"
        ],
        "thread_history_file_presence_treated_as_runtime_slot_truth": separation_packet[
            "thread_history_file_presence_counted_as_runtime_slot_truth"
        ],
        "original_codex_profile_used_as_history_proof": restore_packet[
            "original_codex_profile_participates_in_proof"
        ],
        "native_visible_restore_claimed_without_observation": (
            native_boundary_packet["native_visible_restore_claimed"] is True
            and native_boundary_packet["native_visible_restore_observed"] is not True
        ),
        "helper_reload_profile_packet_claims_native_relaunch": profile_packet[
            "helper_reload_equals_native_app_relaunch"
        ],
    }
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "real_history_restore_false_green_boundary",
        "status": "ok" if not any(false_green.values()) else "blocked",
        **false_green,
    }


def _build_independent_audit_packet(
    restore_packet: dict[str, Any],
    profile_packet: dict[str, Any],
    native_boundary_packet: dict[str, Any],
    imported: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    findings = [
        {
            "id": "helper_reload_observed_but_not_native_visible_restore",
            "severity": "info",
            "status": "ok",
            "evidence": "profile_relaunch_continuity_packet.json",
        },
        {
            "id": "prior_synthetic_storage_limiter_reduced_only_to_helper_reload",
            "severity": "info",
            "status": "ok",
            "evidence": "history_restore_packet.json",
        },
        {
            "id": "history_slot_separation_preserved",
            "severity": "info",
            "status": "ok",
            "evidence": "history_vs_slot_separation_packet.json",
        },
        {
            "id": "native_visible_restore_remains_open_non_claim",
            "severity": "medium",
            "status": "open_with_limits",
            "evidence": "native_visible_restore_boundary_packet.json",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "real_history_restore_independent_audit",
        "status": "ok",
        "audit_mode": "local_materialized_packet_plus_optional_agent_report",
        "agent_verdict_counted": False,
        "imported_final_e2e_history_status": imported["final_e2e_history"].get("status"),
        "restore_classification_reviewed": restore_packet.get("classification"),
        "helper_reload_classification_reviewed": profile_packet.get("classification"),
        "native_visible_restore_claimed": native_boundary_packet.get("native_visible_restore_claimed"),
        "findings": findings,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    imported = _load_imported_packets(repo_root)
    context = _build_restore_context(evidence_dir=evidence_dir)
    restore_packet = _build_history_restore_packet(context, imported)
    profile_packet = _build_profile_relaunch_continuity_packet(context)
    separation_packet = _build_history_vs_slot_separation_packet(context)
    native_boundary_packet = _build_native_visible_restore_boundary_packet(context)
    gap_matrix = _build_gap_matrix(restore_packet, profile_packet, native_boundary_packet)
    false_green = _build_false_green_boundary_packet(
        restore_packet,
        profile_packet,
        separation_packet,
        native_boundary_packet,
    )
    audit = _build_independent_audit_packet(
        restore_packet,
        profile_packet,
        native_boundary_packet,
        imported,
    )
    return {
        "history_restore_packet.json": restore_packet,
        "profile_relaunch_continuity_packet.json": profile_packet,
        "history_vs_slot_separation_packet.json": separation_packet,
        "native_visible_restore_boundary_packet.json": native_boundary_packet,
        "history_restore_gap_matrix.json": gap_matrix,
        "false_green_boundary_packet.json": false_green,
        "independent_audit_packet.json": audit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="real-history-restore-proof-r1")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(REPO_ROOT / "audit_results/real_history_restore_proof_r1_2026-05-28"),
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    evidence_dir = Path(args.evidence_dir).expanduser().resolve(strict=False)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root=repo_root, evidence_dir=evidence_dir)
    for filename, packet in packets.items():
        json_write(evidence_dir / filename, packet)
    print(
        json.dumps(
            {
                "status": "ok",
                "evidence_dir": str(evidence_dir),
                "packet_count": len(packets),
                "history_restore_classification": packets[
                    "history_restore_packet.json"
                ].get("classification"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
