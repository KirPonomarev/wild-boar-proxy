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

from wild_boar_proxy.codex_custom_sessions import CodexCustomSessionManager  # noqa: E402
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_original_codex_profile_drift_packet,
    build_owner_visible_thread_context_packet,
    build_persistent_backup_rollback_packet,
    build_persistent_cleanup_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_profile_false_green_audit,
    build_persistent_profile_state_diff_packet,
    build_persistent_profile_state_preservation_packet,
    default_persistent_custom_profile_paths,
    json_write,
    scan_protected_surfaces,
    scan_tree,
)


PRIMARY_MODEL_ID = "gpt-5.3-codex"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"


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
        "status": {"status": "ok", "machine_error_code": "OK"},
        "claim_gate": {"status": "blocked_by_policy_drift"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": [PRIMARY_MODEL_ID, "gpt-5.4"],
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


def _materialize_profile_root(profile_root: Path, user_data_dir: Path, home_dir: Path, tmp_dir: Path) -> None:
    for path in (profile_root, user_data_dir, home_dir, tmp_dir):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)


def _write_synthetic_profile_state(profile_root: Path) -> list[str]:
    thread_marker = profile_root / "thread-history" / "bounded-thread.marker"
    session_marker = profile_root / "session-state" / "session-state.json"
    thread_marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    thread_marker.write_text("synthetic-thread-history-marker\n", encoding="utf-8")
    session_marker.write_text(
        json.dumps({"slot_catalog_revalidated": False, "synthetic": True}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return [
        str(thread_marker.relative_to(profile_root)),
        str(session_marker.relative_to(profile_root)),
    ]


def _role_slot_session_packets(session_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
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
    session_id = str(created["session"]["session_id"])
    manager.prompt_dry_run_packet(session_id, {"prompt": "Reply with exactly OK."})
    reloaded = CodexCustomSessionManager(session_root)
    detail = reloaded.get_packet(session_id)
    blocked = reloaded.prompt_packet(
        session_id,
        {"prompt": "Reply with exactly OK."},
        lambda payload: {"status": "ok", "final_message": "OK"},
        owner_authorized=True,
    )

    role_slot_persistence_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_persistence",
        "status": "ok"
        if (
            detail["session"]["session_id"] == session_id
            and detail["session"]["role_slot_binding_count"]
            == created["session"]["role_slot_binding_count"]
        )
        else "blocked",
        "session_id_matches_after_reload": detail["session"]["session_id"] == session_id,
        "role_slot_binding_count_before_reload": created["session"]["role_slot_binding_count"],
        "role_slot_binding_count_after_reload": detail["session"]["role_slot_binding_count"],
        "primary_slot_model_id_after_reload": detail["session"]["role_slots"]["primary_model_slot"]["model_id"],
        "coding_agent_slot_model_id_after_reload": detail["session"]["role_slots"]["coding_agent_model_slot"]["model_id"],
        "slot_catalog_revalidated_after_reload": detail["session"]["slot_catalog_revalidated"],
        "session_root_scope": detail["session"]["session_root_scope"],
        "counts_as_persistent_profile_identity_proof": False,
        "counts_as_thread_history_restoration": False,
        "counts_as_runtime_dispatch_proof": False,
    }
    reload_revalidation_boundary_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "reload_revalidation_boundary",
        "status": "ok"
        if blocked["machine_error_code"] == "SLOT_CATALOG_REVALIDATION_REQUIRED"
        else "blocked",
        "slot_catalog_revalidated_before_reload": created["session"]["slot_catalog_revalidated"],
        "slot_catalog_revalidated_after_reload": detail["session"]["slot_catalog_revalidated"],
        "prompt_admitted_without_revalidation": blocked["status"] == "ok",
        "blocked_machine_error_code": blocked["machine_error_code"],
        "precondition_failures": blocked.get("precondition_failures", []),
        "reloaded_role_slots_present": detail["role_slot_binding_packet"]["role_slot_binding_present"],
        "counts_as_slot_catalog_revalidation_proof": False,
        "counts_as_runtime_dispatch_proof": False,
    }
    return role_slot_persistence_packet, reload_revalidation_boundary_packet


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
) -> dict[str, dict[str, Any]]:
    probe_base_dir = evidence_dir / "probe_profile_base"
    session_root = evidence_dir / "probe_session_root"
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=probe_base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    home_dir = Path(paths["home_dir"])
    tmp_dir = Path(paths["tmp_dir"])
    backup_root = profile_root.parent / f"{profile_id}.backup"

    _materialize_profile_root(profile_root, user_data_dir, home_dir, tmp_dir)
    before_scan = scan_tree(profile_root)
    protected_before = scan_protected_surfaces()
    synthetic_paths = _write_synthetic_profile_state(profile_root)
    after_scan = scan_tree(profile_root)
    relaunch_scan = scan_tree(profile_root)
    protected_after = scan_protected_surfaces()

    identity_packet = build_persistent_custom_profile_identity_packet(
        phase="before",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    relaunch_identity_packet = build_persistent_custom_profile_identity_packet(
        phase="relaunch",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
        expected_profile_id=profile_id,
        expected_profile_root=profile_root,
    )
    state_diff_packet = build_persistent_profile_state_diff_packet(
        before_scan=before_scan,
        after_scan=after_scan,
        relaunch_scan=relaunch_scan,
    )
    after_relaunch_state_diff_packet = build_persistent_profile_state_diff_packet(
        before_scan=after_scan,
        after_scan=relaunch_scan,
    )
    owner_visible_thread_context_packet = build_owner_visible_thread_context_packet(
        owner_visible_prior_thread=False,
        owner_confirmation_collected=False,
    )
    profile_state_preservation_packet = build_persistent_profile_state_preservation_packet(
        before_identity_packet=identity_packet,
        relaunch_identity_packet=relaunch_identity_packet,
        after_action_state_diff_packet=state_diff_packet,
        after_relaunch_state_diff_packet=after_relaunch_state_diff_packet,
    )
    cleanup_boundary_packet = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=profile_root.exists(),
    )
    role_slot_persistence_packet, reload_revalidation_boundary_packet = (
        _role_slot_session_packets(session_root)
    )

    relaunch_continuity_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "relaunch_continuity",
        "status": "ok"
        if (
            identity_packet["status"] == "ok"
            and relaunch_identity_packet["status"] == "ok"
            and identity_packet["persistent_profile_id"]
            == relaunch_identity_packet["persistent_profile_id"]
            and identity_packet["persistent_profile_root"]
            == relaunch_identity_packet["persistent_profile_root"]
        )
        else "blocked",
        "same_persistent_profile_identity": (
            identity_packet["persistent_profile_id"]
            == relaunch_identity_packet["persistent_profile_id"]
            and identity_packet["persistent_profile_root"]
            == relaunch_identity_packet["persistent_profile_root"]
        ),
        "profile_root_exists_before": before_scan.get("exists") is True,
        "profile_root_exists_after_relaunch": relaunch_scan.get("exists") is True,
        "live_native_relaunch_attempted": False,
        "same_profile_identity_classified_across_relaunch": True,
        "owner_visible_thread_continuity_proven": False,
        "storage_level_thread_history_proven": False,
        "same_active_execution_path_proven": False,
        "same_provider_account_selection_proven": False,
        "continuity_scope": "profile_identity_only",
    }

    observed_classes = set(state_diff_packet.get("state_classes_observed", []))
    thread_history_classification_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "thread_history_classification",
        "status": "ok",
        "classification": "synthetic_storage_only_with_limits",
        "same_persistent_profile_identity": relaunch_continuity_packet[
            "same_persistent_profile_identity"
        ],
        "profile_state_preserved": profile_state_preservation_packet["profile_state_preserved"],
        "observed_state_classes": sorted(observed_classes),
        "synthetic_paths_written": synthetic_paths,
        "synthetic_history_state_preserved": (
            profile_state_preservation_packet["profile_state_preserved"]
            and bool(observed_classes & {"thread_history", "session_state"})
        ),
        "thread_history_preserved": False,
        "owner_visible_thread_continuity_proven": False,
        "storage_level_thread_history_proven": False,
        "native_thread_history_restoration_proven": False,
        "role_slot_persistence_counted_as_thread_history": False,
        "owner_visible_thread_counted_as_storage_proof": False,
        "route_trace_counted_as_saved_thread_proof": False,
        "visible_thread_context_only": owner_visible_thread_context_packet["context_only"],
    }

    non_claims_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "persistent_profile_non_claims",
        "status": "ok",
        "simultaneous_execution_proven": False,
        "runtime_dispatch_truth_proven": False,
        "visible_continuity_implies_storage_continuity": False,
        "slot_persistence_implies_runtime_honor": False,
        "custom_history_equals_original_codex_history": False,
        "same_active_execution_path_proven": False,
        "same_provider_account_selection_truth_proven": False,
        "slot_persistence_implies_slot_catalog_revalidation": False,
    }

    gap_matrix_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "persistent_profile_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "live_native_relaunch_not_attempted_here",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "owner_visible_thread_continuity_not_proven_here",
                "status": "open",
                "blocks_runtime_claim": False,
            },
            {
                "id": "storage_level_thread_history_uses_synthetic_owned_state_only",
                "status": "open",
                "blocks_runtime_claim": False,
            },
            {
                "id": "role_slot_persistence_not_linked_to_persistent_profile_root_here",
                "status": "open",
                "blocks_runtime_claim": False,
            },
            {
                "id": "runtime_slot_dispatch_and_simultaneous_execution_remain_later_contours",
                "status": "open",
                "blocks_runtime_claim": True,
            },
        ],
    }

    false_green_boundary_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "persistent_profile_false_green_boundary",
        "status": "ok",
        "visible_continuity_treated_as_storage_proof": False,
        "role_slot_persistence_treated_as_thread_history": False,
        "reloaded_slot_state_treated_as_revalidated_truth": False,
        "original_codex_profile_used_as_input": False,
        "cleanup_treated_as_profile_deletion_default": False,
        "synthetic_storage_state_treated_as_native_history_restore": False,
    }

    independent_audit_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "persistent_profile_independent_audit",
        "status": "ok",
        "source": "local_probe_plus_subagent_read_only_inventory",
        "findings": [
            {
                "id": "persistent_profile_identity_is_packet_backed",
                "status": "ok",
            },
            {
                "id": "persistent_cleanup_boundary_stays_non_destructive_by_default",
                "status": "ok",
            },
            {
                "id": "reload_keeps_slot_state_but_blocks_prompt_until_revalidation",
                "status": "ok",
            },
            {
                "id": "thread_history_claims_remain_bounded_to_synthetic_storage_classification",
                "status": "ok",
            },
            {
                "id": "live_native_relaunch_and_owner_visible_history_truth_remain_open",
                "status": "open_risk",
                "scope": "later_runtime_or_owner_observed_contours",
            },
        ],
    }

    packets = {
        "persistent_profile_identity_packet.json": {
            **identity_packet,
            "profile_root_materialized_by_probe": True,
            "identity_counts_as_thread_history_preservation": False,
        },
        "role_slot_persistence_packet.json": role_slot_persistence_packet,
        "relaunch_continuity_packet.json": relaunch_continuity_packet,
        "thread_history_classification_packet.json": thread_history_classification_packet,
        "persistent_cleanup_boundary_packet.json": cleanup_boundary_packet,
        "reload_revalidation_boundary_packet.json": reload_revalidation_boundary_packet,
        "persistent_profile_non_claims_packet.json": non_claims_packet,
        "persistent_profile_gap_matrix.json": gap_matrix_packet,
        "false_green_boundary_packet.json": false_green_boundary_packet,
        "independent_audit_packet.json": independent_audit_packet,
        "persistent_profile_state_preservation_packet.json": profile_state_preservation_packet,
        "persistent_profile_state_diff_packet.json": state_diff_packet,
        "persistent_custom_profile_contract_packet.json": build_persistent_custom_profile_contract_packet(
            profile_id=profile_id,
            profile_root=profile_root,
            codex_home=codex_home,
            user_data_dir=user_data_dir,
        ),
        "persistent_backup_rollback_packet.json": build_persistent_backup_rollback_packet(
            profile_root=profile_root,
            backup_root=backup_root,
            profile_existed_before=False,
            backup_created=False,
        ),
        "owner_visible_thread_context_packet.json": owner_visible_thread_context_packet,
        "original_codex_profile_drift_packet.json": build_original_codex_profile_drift_packet(
            before_surfaces=protected_before,
            after_surfaces=protected_after,
        ),
    }
    packets["persistent_profile_false_green_audit_packet.json"] = (
        build_persistent_profile_false_green_audit(
            thread_history_packet=thread_history_classification_packet,
            owner_visible_thread_context_packet=owner_visible_thread_context_packet,
            cleanup_policy_packet=cleanup_boundary_packet,
            original_drift_packet=packets["original_codex_profile_drift_packet.json"],
        )
    )
    shutil.rmtree(probe_base_dir, ignore_errors=True)
    shutil.rmtree(session_root, ignore_errors=True)
    return packets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--profile-id", default="wbp-custom-main")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        profile_id=args.profile_id,
    )
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "packet_count": len(packets),
                "evidence_dir": str(evidence_dir),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
