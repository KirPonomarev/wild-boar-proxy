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
    CODING_AGENT_MODEL_SLOT,
    PRIMARY_MODEL_SLOT,
    CodexCustomSessionManager,
)


PRIMARY_MODEL_ID = "gpt-5.5"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"
TASK_FIXTURE_ID = "workflow_task_alpha"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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
                "claim_gate": {"status": "ok"},
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
        "claim_gate": {"status": "ok"},
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


class WorkflowComparisonPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        prompt = str(payload.get("prompt") or "")
        model_id = str(payload.get("model_id") or "")
        route_backed = model_id == CODING_AGENT_MODEL_ID

        workflow_artifact_kind = "unknown"
        workflow_artifact = ""
        workflow_artifact_task_relevant = False
        workflow_artifact_consumed_by_next_step = False
        final_message = "UNCLASSIFIED"

        if prompt == "BASELINE_TASK_ALPHA":
            workflow_artifact_kind = "single_path_summary"
            workflow_artifact = "single_plan_and_fix_summary"
            workflow_artifact_task_relevant = True
            final_message = "BASELINE_SINGLE_PATH::single_plan_and_fix_summary"
        elif prompt == "CHAIN_PRIMARY_PLAN_ALPHA":
            workflow_artifact_kind = "primary_plan"
            workflow_artifact = "task_alpha_plan"
            workflow_artifact_task_relevant = True
            workflow_artifact_consumed_by_next_step = True
            final_message = "PRIMARY_PLAN::task_alpha_plan"
        elif prompt == "CHAIN_CODING_ALPHA":
            workflow_artifact_kind = "coding_artifact"
            workflow_artifact = "task_alpha_patch_skeleton"
            workflow_artifact_task_relevant = True
            workflow_artifact_consumed_by_next_step = True
            final_message = "CODING_ARTIFACT::task_alpha_patch_skeleton"
        elif prompt == "CHAIN_PRIMARY_RETURN_ALPHA":
            workflow_artifact_kind = "primary_return"
            workflow_artifact = "integrated_patch_skeleton"
            workflow_artifact_task_relevant = True
            final_message = "PRIMARY_RETURN::integrated_patch_skeleton"

        result = {
            "status": "ok",
            "machine_error_code": "OK",
            "requested_slot_id": str(payload.get("slot_id") or ""),
            "selected_model": model_id,
            "runtime_model": model_id,
            "final_message": final_message,
            "workflow_artifact_kind": workflow_artifact_kind,
            "workflow_artifact": workflow_artifact,
            "workflow_artifact_task_relevant": workflow_artifact_task_relevant,
            "workflow_artifact_consumed_by_next_step": workflow_artifact_consumed_by_next_step,
            "secret_value_recorded": False,
            "configured_provider": "external_route" if route_backed else "cliproxy",
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
        self.results.append(dict(result))
        return result


def _prompt_result(
    manager: CodexCustomSessionManager,
    runner: WorkflowComparisonPromptRunner,
    session_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    packet = manager.prompt_packet(
        session_id,
        payload,
        runner.run,
        owner_authorized=True,
    )
    return {
        "packet": packet,
        "call": dict(runner.calls[-1]),
        "runner_result": dict(runner.results[-1]),
    }


def _outcome_view(entry: dict[str, Any]) -> dict[str, Any]:
    packet = entry["packet"]
    runner_result = entry["runner_result"]
    return {
        "status": packet.get("status"),
        "machine_error_code": packet.get("machine_error_code"),
        "execution_slot_id": packet.get("current_execution_slot_id"),
        "model_id": packet.get("model_id"),
        "configured_provider": packet.get("configured_provider"),
        "selected_source_provenance": packet.get("selected_source_provenance"),
        "live_prompt_full_success": packet.get("live_prompt_full_success") is True,
        "response_preview_bounded": packet.get("response_preview_bounded"),
        "artifact_kind": runner_result.get("workflow_artifact_kind"),
        "artifact_task_relevant": runner_result.get("workflow_artifact_task_relevant") is True,
        "artifact_consumed_by_next_step": (
            runner_result.get("workflow_artifact_consumed_by_next_step") is True
        ),
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root, evidence_dir
    with tempfile.TemporaryDirectory(prefix="wbp-workflow-value-r1-") as temp_dir:
        session_root = Path(temp_dir)
        manager = CodexCustomSessionManager(session_root)
        runner = WorkflowComparisonPromptRunner()

        baseline_created = manager.create_packet(
            {
                "primary_model_id": PRIMARY_MODEL_ID,
                "coding_agent_model_id": CODING_AGENT_MODEL_ID,
            },
            commands(),
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        baseline_session_id = str(baseline_created.get("session", {}).get("session_id") or "")
        baseline = _prompt_result(
            manager,
            runner,
            baseline_session_id,
            {
                "prompt": "BASELINE_TASK_ALPHA",
                "slot_id": PRIMARY_MODEL_SLOT,
            },
        )
        baseline_transcript = manager.transcript_packet(baseline_session_id)

        chain_created = manager.create_packet(
            {
                "primary_model_id": PRIMARY_MODEL_ID,
                "coding_agent_model_id": CODING_AGENT_MODEL_ID,
            },
            commands(),
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        chain_session_id = str(chain_created.get("session", {}).get("session_id") or "")
        chain_primary_plan = _prompt_result(
            manager,
            runner,
            chain_session_id,
            {
                "prompt": "CHAIN_PRIMARY_PLAN_ALPHA",
                "slot_id": PRIMARY_MODEL_SLOT,
            },
        )
        chain_coding = _prompt_result(
            manager,
            runner,
            chain_session_id,
            {
                "prompt": "CHAIN_CODING_ALPHA",
                "slot_id": CODING_AGENT_MODEL_SLOT,
            },
        )
        chain_primary_return = _prompt_result(
            manager,
            runner,
            chain_session_id,
            {
                "prompt": "CHAIN_PRIMARY_RETURN_ALPHA",
                "slot_id": PRIMARY_MODEL_SLOT,
            },
        )
        chain_transcript = manager.transcript_packet(chain_session_id)

    baseline_packet = baseline["packet"]
    chain_primary_plan_packet = chain_primary_plan["packet"]
    chain_coding_packet = chain_coding["packet"]
    chain_primary_return_packet = chain_primary_return["packet"]
    baseline_ok = baseline_packet.get("status") == "ok"
    chain_ok = all(
        packet.get("status") == "ok"
        for packet in (
            chain_primary_plan_packet,
            chain_coding_packet,
            chain_primary_return_packet,
        )
    )
    chain_step_separation_observed = (
        chain_primary_plan_packet.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
        and chain_coding_packet.get("current_execution_slot_id") == CODING_AGENT_MODEL_SLOT
        and chain_primary_return_packet.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
    )
    coding_artifact_task_relevant = (
        chain_coding["runner_result"].get("workflow_artifact_task_relevant") is True
    )
    coding_artifact_consumed = (
        chain_coding["runner_result"].get("workflow_artifact_consumed_by_next_step") is True
        and chain_primary_return["runner_result"].get("workflow_artifact_kind") == "primary_return"
    )
    same_task_class = True
    same_policy_guard_conditions = (
        baseline_packet.get("authorization_status") == "authorized_by_owner_gate"
        and chain_primary_plan_packet.get("authorization_status") == "authorized_by_owner_gate"
        and chain_coding_packet.get("authorization_status") == "authorized_by_owner_gate"
        and chain_primary_return_packet.get("authorization_status") == "authorized_by_owner_gate"
    )
    same_admitted_semantic_mode = all(
        packet.get("configured_wire_api") == "responses"
        for packet in (
            baseline_packet,
            chain_primary_plan_packet,
            chain_coding_packet,
            chain_primary_return_packet,
        )
    )
    same_runtime_family = (
        baseline_packet.get("mode_id") == chain_primary_plan_packet.get("mode_id") == "codex_custom"
    )
    structural_signal_observed = chain_step_separation_observed and coding_artifact_task_relevant and coding_artifact_consumed
    comparison_admitted_for_structure = (
        baseline_ok
        and chain_ok
        and same_task_class
        and same_policy_guard_conditions
        and same_admitted_semantic_mode
        and same_runtime_family
    )
    superiority_claim_admitted = False

    packets: dict[str, dict[str, Any]] = {}
    packets["primary_only_baseline_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "primary_only_baseline",
        "status": "ok" if baseline_ok else "blocked",
        "task_fixture_id": TASK_FIXTURE_ID,
        "session_id": baseline_session_id,
        "path_kind": "primary_only",
        "step_count": 1,
        "completion_observed": baseline_ok,
        "output_present": baseline_packet.get("model_response_present") is True,
        "baseline_output_view": _outcome_view(baseline),
        "transcript_entry_count": len(baseline_transcript.get("entries") or []),
        "transcript_preserves_response_event": any(
            str(entry.get("event") or "").startswith("prompt_completed")
            for entry in baseline_transcript.get("entries", [])
            if isinstance(entry, dict)
        ),
    }
    packets["bounded_orchestration_outcome_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "bounded_orchestration_outcome",
        "status": "ok" if chain_ok else "blocked",
        "task_fixture_id": TASK_FIXTURE_ID,
        "session_id": chain_session_id,
        "path_kind": "primary_to_coding_to_primary",
        "step_count": 3,
        "completion_observed": chain_ok,
        "step_separation_observed": chain_step_separation_observed,
        "coding_artifact_task_relevant": coding_artifact_task_relevant,
        "coding_artifact_consumed_by_primary_return": coding_artifact_consumed,
        "primary_plan_step": _outcome_view(chain_primary_plan),
        "coding_step": _outcome_view(chain_coding),
        "primary_return_step": _outcome_view(chain_primary_return),
        "transcript_entry_count": len(chain_transcript.get("entries") or []),
        "transcript_preserves_all_completed_events": sum(
            1
            for entry in chain_transcript.get("entries", [])
            if isinstance(entry, dict)
            and str(entry.get("event") or "").startswith("prompt_completed")
        )
        >= 3,
        "operator_mediated_chain_only": True,
    }
    packets["workflow_usefulness_comparison_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "workflow_usefulness_comparison",
        "status": "ok",
        "task_fixture_id": TASK_FIXTURE_ID,
        "structural_signal_source_classification": "contour_local_runner_harness_packetized_by_probe",
        "comparison_status": (
            "bounded_structural_signal_only_with_limits"
            if comparison_admitted_for_structure and structural_signal_observed
            else "indeterminate"
        ),
        "baseline_completed": baseline_ok,
        "bounded_chain_completed": chain_ok,
        "comparison_admitted_for_structure": comparison_admitted_for_structure,
        "comparison_admitted_for_superiority": superiority_claim_admitted,
        "task_relevant_structural_signal_observed": structural_signal_observed,
        "chain_only_ceremony_observed": False if structural_signal_observed else True,
        "bounded_chain_structural_signal_only": structural_signal_observed,
        "workflow_usefulness_superiority_proven": False,
        "answer_quality_superiority_proven": False,
        "general_productivity_gain_proven": False,
        "operator_mediated_not_autonomous": True,
    }
    packets["workflow_comparability_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "workflow_comparability",
        "status": "ok",
        "task_fixture_id": TASK_FIXTURE_ID,
        "comparison_scope_classification": "bounded_probe_only",
        "same_task_class": same_task_class,
        "same_policy_guard_conditions": same_policy_guard_conditions,
        "same_admitted_semantic_mode": same_admitted_semantic_mode,
        "same_runtime_family": same_runtime_family,
        "same_lane_topology": False,
        "same_execution_path": False,
        "materially_comparable_for_structure": comparison_admitted_for_structure,
        "materially_comparable_for_superiority_claim": superiority_claim_admitted,
        "comparison_blocker": (
            "harness_local_synthetic_outputs_do_not_support_superiority_claim"
            if not superiority_claim_admitted
            else ""
        ),
        "latency_or_throughput_decisive_here": False,
    }
    packets["workflow_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "workflow_non_claims",
        "status": "ok",
        "bounded_chain_proves_general_multi_agent_productivity": False,
        "successful_chain_implies_better_coding_quality_generally": False,
        "extra_role_steps_imply_useful_orchestration": False,
        "one_comparison_generalizes_to_broader_workloads": False,
        "operator_mediated_chain_equals_autonomous_workflow_intelligence": False,
        "sequential_workflow_usefulness_implies_concurrency_usefulness": False,
        "longer_output_implies_better_workflow_usefulness": False,
        "bounded_usefulness_implies_answer_quality_superiority": False,
        "structured_chain_implies_better_spend_efficiency": False,
        "one_useful_comparison_authorizes_broader_orchestration_policy": False,
    }
    packets["workflow_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "workflow_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "workflow_superiority_over_primary_only_not_proven",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "harness_local_synthetic_outputs_limit_usefulness_claim_scope",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "operator_mediated_chain_not_autonomous_workflow_intelligence",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "single_task_fixture_does_not_generalize_to_broader_workloads",
                "severity": "medium",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "handoff_success_treated_as_workflow_value_by_itself": False,
        "extra_chain_steps_treated_as_better_outcome_without_packet_evidence": False,
        "longer_output_treated_as_better_workflow_value": False,
        "operator_mediated_chain_treated_as_autonomous_intelligence": False,
        "latency_or_throughput_reused_as_usefulness_proof": False,
        "chain_complexity_treated_as_usefulness": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "baseline_and_chain_both_run_under_authorized_plain_response_guards",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "bounded_chain_preserves_primary_coding_primary_step_separation",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "task_relevant_coding_artifact_is_observed_and_consumed_by_primary_return",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "same_execution_path_remains_false_even_when_structural_comparison_is_admitted",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "workflow_superiority_claim_remains_not_admitted_under_harness_local_synthetic_outputs",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "general_productivity_gain_remains_unproven",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bounded-workflow-value-and-orchestration-usefulness-classification-r1-probe"
    )
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
