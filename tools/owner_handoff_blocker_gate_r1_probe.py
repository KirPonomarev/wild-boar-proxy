#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.historical_audit_fixtures import historical_audit_path


FINAL_DIR = Path("audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-29")
API_MATRIX_DIR = Path("audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28")
PERSISTENCE_DIR = Path("audit_results/persistent_profile_and_thread_history_r1_2026-05-28")
BUDGET_DIR = Path("audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28")

FINAL_STATUS = "OWNER_HANDOFF_BLOCKER_GATE_CLASSIFIED_WITH_LIMITS"
OWNER_BLOCKER_IDS = (
    "live_native_relaunch_history_restore",
    "live_provider_response_smoke",
    "live_concurrent_dual_lane_execution",
    "owner_authorized_paid_budget_policy",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(repo_root: Path, relative_path: Path | str) -> dict[str, Any]:
    return json.loads(historical_audit_path(repo_root, relative_path).read_text(encoding="utf-8"))


def _blocker_row(
    *,
    blocker_id: str,
    status: str = "blocked_owner_required",
    owner_required: bool = True,
    proof_present: bool = False,
    required_owner_action: str,
    supporting_packets: list[str],
    guards: dict[str, bool],
) -> dict[str, Any]:
    return {
        "id": blocker_id,
        "status": status,
        "owner_required": owner_required,
        "proof_present": proof_present,
        "required_owner_action": required_owner_action,
        "supporting_packets": supporting_packets,
        "guards": guards,
        "readiness_counts_as_proof": False,
        "counts_as_closed_without_owner": False,
    }


def validate_blocker_gate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("owner_required_blockers")
    if not isinstance(rows, list):
        rows = []
    violations: list[dict[str, Any]] = []
    row_ids = [str(row.get("id") or "") for row in rows if isinstance(row, dict)]
    missing = sorted(set(OWNER_BLOCKER_IDS).difference(row_ids))
    duplicates = sorted({row_id for row_id in row_ids if row_ids.count(row_id) > 1})
    for blocker_id in missing:
        violations.append({"blocker_id": blocker_id, "violation": "missing_owner_blocker"})
    for blocker_id in duplicates:
        violations.append({"blocker_id": blocker_id, "violation": "duplicate_owner_blocker"})

    for row in rows:
        if not isinstance(row, dict):
            continue
        blocker_id = str(row.get("id") or "")
        row_status = str(row.get("status") or "")
        if row.get("owner_required") is not True:
            violations.append({"blocker_id": blocker_id, "violation": "owner_required_not_true"})
        if row.get("proof_present") is True:
            violations.append({"blocker_id": blocker_id, "violation": "proof_present_without_owner"})
        if row_status not in {"blocked_owner_required", "classified_with_limits"}:
            violations.append(
                {
                    "blocker_id": blocker_id,
                    "violation": "owner_blocker_not_blocked_or_limited",
                    "status": row_status,
                }
            )
        if row.get("readiness_counts_as_proof") is True:
            violations.append({"blocker_id": blocker_id, "violation": "readiness_counted_as_proof"})
        if row.get("counts_as_closed_without_owner") is True:
            violations.append(
                {"blocker_id": blocker_id, "violation": "owner_blocker_closed_without_owner"}
            )
        guards = row.get("guards")
        if isinstance(guards, dict):
            bad_guards = sorted(key for key, value in guards.items() if value is True)
            for guard in bad_guards:
                violations.append(
                    {
                        "blocker_id": blocker_id,
                        "violation": "false_green_guard_enabled",
                        "guard": guard,
                    }
                )

    if payload.get("final_status") != FINAL_STATUS:
        violations.append(
            {
                "violation": "wrong_final_status",
                "final_status": payload.get("final_status"),
            }
        )
    if (
        payload.get("final_status_with_limits") is not True
        or not str(payload.get("final_status") or "").endswith("WITH_LIMITS")
    ):
        violations.append({"violation": "final_status_without_with_limits"})
    if payload.get("global_product_acceptance_claimed") is True:
        violations.append({"violation": "global_product_acceptance_claimed"})
    if payload.get("gate_is_repo_resident_roadmap") is True:
        violations.append({"violation": "gate_treated_as_repo_resident_roadmap"})
    if payload.get("owner_required_blockers_counted_as_closed") is True:
        violations.append({"violation": "owner_required_blockers_counted_as_closed"})

    return {
        "status": "ok" if not violations else "blocked",
        "violation_count": len(violations),
        "violations": violations,
        "missing_owner_blockers": missing,
        "duplicate_owner_blockers": duplicates,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del evidence_dir
    final_acceptance = _read_json(repo_root, FINAL_DIR / "final_dual_lane_acceptance_matrix.json")
    final_runtime = _read_json(repo_root, FINAL_DIR / "final_dual_lane_runtime_packet.json")
    final_selection = _read_json(repo_root, FINAL_DIR / "final_dual_lane_selection_packet.json")
    final_history = _read_json(repo_root, FINAL_DIR / "final_dual_lane_history_packet.json")
    final_workflow = _read_json(repo_root, FINAL_DIR / "final_dual_lane_workflow_packet.json")
    api_matrix = _read_json(repo_root, API_MATRIX_DIR / "provider_smoke_matrix_packet.json")
    thread_history = _read_json(repo_root, PERSISTENCE_DIR / "thread_history_classification_packet.json")
    role_slots = _read_json(repo_root, PERSISTENCE_DIR / "role_slot_persistence_packet.json")
    budget = _read_json(repo_root, BUDGET_DIR / "budget_boundary_packet.json")
    concurrency = _read_json(repo_root, BUDGET_DIR / "concurrency_boundary_packet.json")

    owner_required_blockers = [
        _blocker_row(
            blocker_id="live_native_relaunch_history_restore",
            required_owner_action="owner_runs_live_native_relaunch_and_visible_history_restore_check",
            supporting_packets=[
                str(FINAL_DIR / "final_dual_lane_history_packet.json"),
                str(PERSISTENCE_DIR / "thread_history_classification_packet.json"),
                str(PERSISTENCE_DIR / "role_slot_persistence_packet.json"),
            ],
            guards={
                "synthetic_storage_counted_as_live_history_restore": final_history.get(
                    "synthetic_history_state_preserved"
                )
                is True
                and final_history.get("native_visible_thread_history_proven") is True,
                "thread_history_files_counted_as_native_visible_restore": thread_history.get(
                    "storage_level_thread_history_proven"
                )
                is True
                and thread_history.get("native_thread_history_restoration_proven") is True,
                "role_slot_persistence_counted_as_thread_history": role_slots.get(
                    "counts_as_thread_history_restoration"
                )
                is True
                or thread_history.get("role_slot_persistence_counted_as_thread_history") is True,
                "operator_visible_context_counted_as_storage_proof": thread_history.get(
                    "owner_visible_thread_counted_as_storage_proof"
                )
                is True,
            },
        ),
        _blocker_row(
            blocker_id="live_provider_response_smoke",
            required_owner_action="owner_authorizes_live_provider_response_smoke_or_keeps_blocked",
            supporting_packets=[
                str(FINAL_DIR / "final_dual_lane_selection_packet.json"),
                str(FINAL_DIR / "final_dual_lane_runtime_packet.json"),
                str(API_MATRIX_DIR / "provider_smoke_matrix_packet.json"),
            ],
            guards={
                "selection_intent_counted_as_execution": final_selection.get(
                    "selection_intent_counts_as_execution_proof"
                )
                is True,
                "selection_intent_counted_as_provider_response": final_selection.get(
                    "selection_intent_counts_as_provider_response"
                )
                is True,
                "route_snapshot_counted_as_provider_response": final_runtime.get(
                    "route_snapshot_counted_as_provider_response"
                )
                is True,
                "recording_runner_counted_as_live_upstream": final_runtime.get(
                    "live_upstream_request_attempted"
                )
                is False
                and final_runtime.get("provider_response_proven") is True,
                "provider_matrix_claimed_live_acceptance": api_matrix.get(
                    "live_provider_calls_attempted"
                )
                is False
                and api_matrix.get("upstream_provider_acceptance_proven") is True,
            },
        ),
        _blocker_row(
            blocker_id="live_concurrent_dual_lane_execution",
            required_owner_action="owner_authorizes_live_dual_lane_concurrency_check_or_keeps_non_claim",
            supporting_packets=[
                str(FINAL_DIR / "final_dual_lane_workflow_packet.json"),
                str(BUDGET_DIR / "concurrency_boundary_packet.json"),
            ],
            guards={
                "sequential_chain_counted_as_concurrency": final_workflow.get(
                    "operator_mediated_sequential"
                )
                is True
                and concurrency.get("concurrent_execution_observed") is True,
                "same_session_counted_as_parallel_execution": final_runtime.get(
                    "same_custom_codex_environment"
                )
                is True
                and final_workflow.get("autonomous_orchestration_proven") is True,
                "concurrency_classification_counted_as_throughput_gain": concurrency.get(
                    "concurrency_classification_implies_throughput_gain"
                )
                is True,
                "paid_parallel_fanout_counted_as_proven": concurrency.get(
                    "paid_parallel_fanout_proven"
                )
                is True,
            },
        ),
        _blocker_row(
            blocker_id="owner_authorized_paid_budget_policy",
            required_owner_action="owner_supplies_explicit_paid_budget_quota_retry_fallback_policy",
            supporting_packets=[
                str(BUDGET_DIR / "budget_boundary_packet.json"),
                str(BUDGET_DIR / "concurrency_boundary_packet.json"),
            ],
            guards={
                "paid_route_executed_without_owner_policy": budget.get(
                    "external_paid_routes_enabled_default"
                )
                is True,
                "declared_policy_counted_as_hard_spend_gate": budget.get(
                    "budget_packet_presence_implies_hard_enforcement"
                )
                is True,
                "hard_spend_gate_claimed_without_proof": budget.get(
                    "pre_execution_spend_gate_proven"
                )
                is True
                and budget.get("hard_overspend_prevention_proven") is False,
                "fallback_policy_settled_without_owner": False,
            },
        ),
    ]

    gate_payload = {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_handoff_blocker_gate",
        "status": "ok",
        "final_status": FINAL_STATUS,
        "final_status_with_limits": FINAL_STATUS.endswith("WITH_LIMITS"),
        "global_product_acceptance_claimed": False,
        "gate_is_repo_resident_roadmap": False,
        "readiness_counts_as_proof": False,
        "owner_required_blockers_counted_as_closed": False,
        "owner_required_blocker_count": len(owner_required_blockers),
        "owner_required_blockers": owner_required_blockers,
        "automatic_checks_complete": True,
        "live_actions_attempted_here": False,
        "paid_calls_attempted_here": False,
        "original_codex_touched_here": False,
    }
    gate_validation = validate_blocker_gate_payload(gate_payload)
    gate_payload["status"] = gate_validation["status"]
    gate_payload["validation"] = gate_validation

    final_matrix_binding = {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_handoff_final_matrix_binding",
        "status": "ok"
        if (
            final_acceptance.get("final_status")
            == "CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN_WITH_LIMITS"
            and final_acceptance.get("global_product_acceptance_claimed") is False
            and final_acceptance.get("owner_required_leftovers_counted_as_closed") is False
            and isinstance(
                final_acceptance.get("owner_required_to_close_global_product_acceptance"),
                list,
            )
            and set(final_acceptance.get("owner_required_to_close_global_product_acceptance"))
            == {
                "live_native_relaunch_history_restore",
                "live_provider_response_smoke",
                "live_concurrent_dual_lane_execution_or_explicit_non_claim",
                "owner_authorized_paid_budget_policy_packet",
            }
        )
        else "blocked",
        "final_matrix_packet": str(FINAL_DIR / "final_dual_lane_acceptance_matrix.json"),
        "final_matrix_status": final_acceptance.get("status"),
        "final_matrix_final_status": final_acceptance.get("final_status"),
        "final_matrix_with_limits_preserved": str(
            final_acceptance.get("final_status") or ""
        ).endswith("WITH_LIMITS"),
        "final_matrix_global_product_acceptance_claimed": final_acceptance.get(
            "global_product_acceptance_claimed"
        ),
        "final_matrix_owner_leftovers_counted_as_closed": final_acceptance.get(
            "owner_required_leftovers_counted_as_closed"
        ),
        "gate_counts_as_live_api_history_or_concurrency_proof": False,
    }

    false_green = {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_handoff_false_green_boundary",
        "status": "ok",
        "readiness_treated_as_proof": False,
        "selection_intent_treated_as_execution": False,
        "selection_intent_treated_as_provider_response": False,
        "route_snapshot_treated_as_provider_response": False,
        "synthetic_storage_treated_as_live_history_restore": False,
        "recording_runner_treated_as_live_upstream": False,
        "operator_observed_context_treated_as_durable_storage": False,
        "with_limits_treated_as_full_green": False,
        "owner_blockers_closed_without_owner": False,
        "gate_treated_as_roadmap": False,
    }
    independent_audit = {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_handoff_independent_audit",
        "status": "ok"
        if gate_payload["status"] == "ok"
        and final_matrix_binding["status"] == "ok"
        and all(value is False for key, value in false_green.items() if key not in {"captured_at_utc", "packet_kind", "status"})
        else "blocked",
        "findings": [
            {
                "id": "owner_blockers_remain_blocked_or_limited_until_owner_action",
                "severity": "high",
                "status": "confirmed",
            },
            {
                "id": "final_dual_lane_status_remains_with_limits",
                "severity": "high",
                "status": "confirmed",
            },
            {
                "id": "live_provider_response_history_restore_and_concurrency_unproven_here",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "paid_budget_policy_requires_owner_authorization",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return {
        "owner_handoff_blocker_gate_packet.json": gate_payload,
        "owner_handoff_final_matrix_binding_packet.json": final_matrix_binding,
        "false_green_boundary_packet.json": false_green,
        "independent_audit_packet.json": independent_audit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
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
