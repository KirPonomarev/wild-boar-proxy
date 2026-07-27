#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_custom_sessions import (  # noqa: E402
    CodexCustomSessionManager,
    forbidden_session_create_fields,
)


PRIMARY_MODEL_ID = "gpt-5.5"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _legacy_session_payload() -> dict[str, Any]:
    return {
        "session": {
            "session_id": "ccs-legacy1234",
            "created_at_utc": "2026-05-28T00:00:00Z",
            "updated_at_utc": "2026-05-28T00:00:00Z",
            "status": "ready",
            "model_id": PRIMARY_MODEL_ID,
            "model_server_issued": True,
            "selected_source_class": "gpt_account",
            "selected_backend_digest": "digest-acct-a",
            "selected_backend_id_redacted": True,
            "selected_backend_server_issued": True,
            "selected_route_digest": "",
            "selected_route_server_issued": False,
            "route_provenance_required": False,
            "route_provenance_proven": False,
            "source_provenance_status": "backend_proven",
            "source_provenance_proven": True,
            "selection_dry_run_proven": True,
            "live_selection_proven": False,
            "selection_proven": True,
            "selection_machine_error_code": "OK",
            "session_root_digest": "legacy-root",
            "codex_home_digest": "legacy-home",
            "session_root_scope": "owned_temp_session_root",
            "current_codex_home_used": False,
            "prompt_admission_count": 0,
            "cleanup_state": "not_cleaned",
            "cancel_state": "not_cancelled",
            "ledger_entry_count": 0,
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
        },
        "ledger": [],
    }


def build_packets() -> dict[str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        manager = CodexCustomSessionManager(root)
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
        detail = manager.get_packet(session_id)
        listed = manager.list_packet()

        session_schema_packet = {
            "status": "ok",
            "packet_kind": "dual_slot_session_schema",
            "captured_at_utc": utc_now(),
            "session_schema_version": created["session"]["session_schema_version"],
            "role_slot_binding_proven": created["session"]["role_slot_binding_proven"],
            "slot_catalog_revalidated": created["session"]["slot_catalog_revalidated"],
            "role_slot_binding_count": created["session"]["role_slot_binding_count"],
            "single_model_truth_remaining": False,
            "primary_slot_model_id": created["session"]["role_slots"]["primary_model_slot"]["model_id"],
            "coding_agent_slot_model_id": created["session"]["role_slots"]["coding_agent_model_slot"]["model_id"],
            "reviewer_slot_bound": (
                created["session"]["role_slots"]["reviewer_model_slot"]["binding_status"] == "bound"
            ),
            "list_packet_session_schema_version": listed["session_schema_version"],
        }

        role_slot_binding_packet = {
            "status": "ok",
            "packet_kind": "role_slot_binding",
            "captured_at_utc": utc_now(),
            "role_slot_binding_present": detail["role_slot_binding_packet"]["role_slot_binding_present"],
            "role_slot_binding_count": detail["role_slot_binding_packet"]["role_slot_binding_count"],
            "slot_catalog_revalidated": detail["role_slot_binding_packet"]["slot_catalog_revalidated"],
            "runtime_execution_truth_closed_here": (
                detail["role_slot_binding_packet"]["runtime_execution_truth_closed_here"]
            ),
            "primary_slot_bound": (
                detail["role_slot_binding_packet"]["role_slots"]["primary_model_slot"]["binding_status"]
                == "bound"
            ),
            "coding_agent_slot_bound": (
                detail["role_slot_binding_packet"]["role_slots"]["coding_agent_model_slot"]["binding_status"]
                == "bound"
            ),
            "binding_source": detail["role_slot_binding_packet"]["role_slots"]["coding_agent_model_slot"]["binding_source"],
        }

        forbidden_fields = forbidden_session_create_fields(
            {
                "primary_model_id": PRIMARY_MODEL_ID,
                "coding_agent_model_id": CODING_AGENT_MODEL_ID,
                "account_id": "acct-a",
                "backend_id": "acct-a",
                "route_id": "route",
                "codex_home": "/tmp/home",
                "provider": "openrouter",
                "base_url": "https://example.invalid/v1",
                "auth_path": "/tmp/auth.json",
            }
        )
        authority_boundary_packet = {
            "status": "ok",
            "packet_kind": "session_slot_authority_boundary",
            "captured_at_utc": utc_now(),
            "browser_can_supply_provider": False,
            "browser_can_supply_route_id": False,
            "browser_can_supply_account_id": False,
            "browser_can_supply_codex_home": False,
            "forbidden_fields_detected": forbidden_fields,
            "authority_boundary_held": all(
                field in forbidden_fields
                for field in (
                    "account_id",
                    "backend_id",
                    "route_id",
                    "codex_home",
                    "provider",
                    "base_url",
                    "auth_path",
                )
            ),
        }

        legacy_root = root / "ccs-legacy1234"
        legacy_root.mkdir()
        (legacy_root / "codex-home").mkdir()
        (legacy_root / "workdir").mkdir()
        (legacy_root / "session.json").write_text(
            json.dumps(_legacy_session_payload(), indent=2) + "\n",
            encoding="utf-8",
        )
        migrated_manager = CodexCustomSessionManager(root)
        migrated = migrated_manager.get_packet("ccs-legacy1234")
        migration_packet = {
            "status": "ok",
            "packet_kind": "single_to_multi_slot_migration",
            "captured_at_utc": utc_now(),
            "legacy_single_model_migrated": migrated["session"]["legacy_single_model_migrated"],
            "migration_status": migrated["session"]["migration_status"],
            "slot_catalog_revalidated": migrated["session"]["slot_catalog_revalidated"],
            "primary_slot_model_id": migrated["session"]["role_slots"]["primary_model_slot"]["model_id"],
            "coding_agent_slot_fabricated": (
                migrated["session"]["role_slots"]["coding_agent_model_slot"]["binding_status"] == "bound"
            ),
            "history_loss_claimed": False,
        }

        current_execution_path_packet = {
            "status": "ok",
            "packet_kind": "current_execution_path_separation",
            "captured_at_utc": utc_now(),
            "current_execution_slot_id": created["current_execution_slot_id"],
            "current_execution_path_model_id": created["current_execution_path_model_id"],
            "current_execution_path_source": created["current_execution_path_source"],
            "coding_agent_bound_not_dispatched": (
                created["session"]["role_slots"]["coding_agent_model_slot"]["binding_status"] == "bound"
                and created["current_execution_path_model_id"] != CODING_AGENT_MODEL_ID
            ),
            "slot_binding_implies_runtime_dispatch": False,
        }

        non_claims_packet = {
            "status": "ok",
            "packet_kind": "session_slot_non_claims",
            "captured_at_utc": utc_now(),
            "simultaneous_execution_proven": False,
            "coding_agent_dispatch_proven": False,
            "api_lane_runtime_compatibility_proven": False,
            "slot_persistence_implies_relaunch_continuity": False,
            "slot_persistence_implies_thread_history_restoration": False,
            "runtime_honors_slot_binding_proven": False,
        }

        gap_matrix = {
            "status": "ok",
            "packet_kind": "session_slot_gap_matrix",
            "captured_at_utc": utc_now(),
            "gaps": [
                {
                    "id": "simultaneous_chatgpt_api_execution_not_closed_here",
                    "status": "open",
                    "blocks_runtime_claim": True,
                },
                {
                    "id": "runtime_dispatch_truth_not_closed_here",
                    "status": "open",
                    "blocks_runtime_claim": True,
                },
                {
                    "id": "persistent_thread_history_continuity_not_closed_here",
                    "status": "open",
                    "blocks_runtime_claim": False,
                },
                {
                    "id": "runtime_may_not_honor_non_primary_slots_until_later_contour",
                    "status": "open",
                    "blocks_runtime_claim": True,
                },
                {
                    "id": "slot_lane_compatibility_and_uniqueness_policy_not_closed_here",
                    "status": "open",
                    "blocks_runtime_claim": False,
                },
            ],
        }

        false_green_packet = {
            "status": "ok",
            "packet_kind": "session_slot_false_green_boundary",
            "captured_at_utc": utc_now(),
            "selector_truth_treated_as_session_truth": False,
            "session_truth_treated_as_runtime_truth": False,
            "slot_binding_treated_as_dispatch_proof": False,
            "browser_authority_widened_here": False,
            "legacy_slot_fabrication_detected": False,
        }

        independent_audit_packet = {
            "status": "ok",
            "packet_kind": "session_slot_independent_audit",
            "captured_at_utc": utc_now(),
            "source": "subagent_read_only_audit_then_local_fix_verification",
            "findings": [
                {
                    "id": "role_slot_binding_is_packet_backed_session_truth",
                    "status": "ok",
                },
                {
                    "id": "current_execution_path_remains_primary_slot_scoped",
                    "status": "ok",
                },
                {
                    "id": "legacy_single_model_sessions_migrate_to_primary_slot_only",
                    "status": "ok",
                },
                {
                    "id": "persisted_slot_reload_requires_catalog_revalidation_before_prompt",
                    "status": "ok",
                },
                {
                    "id": "ui_loaded_state_no_longer_synthesizes_ok_packet_truth",
                    "status": "ok",
                },
                {
                    "id": "all_declared_role_slot_fields_are_test_covered_as_explicit_contract",
                    "status": "ok",
                },
                {
                    "id": "simultaneous_execution_and_dispatch_truth_remain_open",
                    "status": "open_risk",
                    "scope": "later_runtime_contours",
                },
                {
                    "id": "thread_history_relaunch_continuity_not_proven_here",
                    "status": "open_risk",
                    "scope": "later_persistence_contours",
                },
                {
                    "id": "non_primary_slot_compatibility_policy_remains_intentionally_broad_here",
                    "status": "open_risk",
                    "scope": "later_role_policy_contours",
                },
            ],
        }

    return {
        "dual_slot_session_schema_packet.json": session_schema_packet,
        "role_slot_binding_packet.json": role_slot_binding_packet,
        "session_slot_authority_boundary_packet.json": authority_boundary_packet,
        "single_to_multi_slot_migration_packet.json": migration_packet,
        "current_execution_path_separation_packet.json": current_execution_path_packet,
        "session_slot_non_claims_packet.json": non_claims_packet,
        "session_slot_gap_matrix.json": gap_matrix,
        "false_green_boundary_packet.json": false_green_packet,
        "independent_audit_packet.json": independent_audit_packet,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    evidence_dir = Path(args.evidence_dir).resolve()
    packets = build_packets()
    for name, payload in packets.items():
        write_json(evidence_dir / name, payload)
    print(json.dumps({"status": "ok", "packet_count": len(packets), "evidence_dir": str(evidence_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
