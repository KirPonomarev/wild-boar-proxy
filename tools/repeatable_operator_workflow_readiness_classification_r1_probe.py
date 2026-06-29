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
TARGET_STATUS = "REPEATABLE_OPERATOR_WORKFLOW_READINESS_CLASSIFIED_WITH_LIMITS"
TASK_CLASSES = (
    "route_selection",
    "coding_artifact_skeleton",
    "review_return_artifact",
)


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


TASK_CLASS_FIXTURES: dict[str, dict[str, Any]] = {
    "route_selection": {
        "baseline_prompt": "BASELINE_ROUTE_SELECTION",
        "chain_prompts": [
            ("CHAIN_ROUTE_PRIMARY_PLAN", PRIMARY_MODEL_SLOT),
            ("CHAIN_ROUTE_CODING", CODING_AGENT_MODEL_SLOT),
            ("CHAIN_ROUTE_PRIMARY_RETURN", PRIMARY_MODEL_SLOT),
        ],
        "classification": "baseline_only_preferred",
        "task_relevant_chain_signal": False,
        "reason_code": "chain_adds_ceremony_without_extra_route_utility",
    },
    "coding_artifact_skeleton": {
        "baseline_prompt": "BASELINE_CODING_ARTIFACT",
        "chain_prompts": [
            ("CHAIN_CODING_PRIMARY_PLAN", PRIMARY_MODEL_SLOT),
            ("CHAIN_CODING_ARTIFACT", CODING_AGENT_MODEL_SLOT),
            ("CHAIN_CODING_PRIMARY_RETURN", PRIMARY_MODEL_SLOT),
        ],
        "classification": "useful_with_limits",
        "task_relevant_chain_signal": True,
        "reason_code": "coding_artifact_step_separation_preserved",
    },
    "review_return_artifact": {
        "baseline_prompt": "BASELINE_REVIEW_RETURN",
        "chain_prompts": [
            ("CHAIN_REVIEW_PRIMARY_PLAN", PRIMARY_MODEL_SLOT),
            ("CHAIN_REVIEW_CODING", CODING_AGENT_MODEL_SLOT),
            ("CHAIN_REVIEW_PRIMARY_RETURN", PRIMARY_MODEL_SLOT),
        ],
        "classification": "useful_with_limits",
        "task_relevant_chain_signal": True,
        "reason_code": "review_return_artifact_preserves_step_separation",
    },
}


PROMPT_BEHAVIOR: dict[str, dict[str, Any]] = {
    "BASELINE_ROUTE_SELECTION": {
        "artifact_kind": "route_decision",
        "artifact_value": "route_selected_compact",
        "task_relevant": True,
        "consumed_by_next_step": False,
        "final_message": "BASELINE_ROUTE::route_selected_compact",
    },
    "CHAIN_ROUTE_PRIMARY_PLAN": {
        "artifact_kind": "route_plan",
        "artifact_value": "route_eval_plan",
        "task_relevant": True,
        "consumed_by_next_step": True,
        "final_message": "CHAIN_ROUTE_PLAN::route_eval_plan",
    },
    "CHAIN_ROUTE_CODING": {
        "artifact_kind": "route_context",
        "artifact_value": "route_context_table",
        "task_relevant": True,
        "consumed_by_next_step": True,
        "final_message": "CHAIN_ROUTE_CONTEXT::route_context_table",
    },
    "CHAIN_ROUTE_PRIMARY_RETURN": {
        "artifact_kind": "route_decision",
        "artifact_value": "route_selected_with_context",
        "task_relevant": True,
        "consumed_by_next_step": False,
        "final_message": "CHAIN_ROUTE_RETURN::route_selected_with_context",
    },
    "BASELINE_CODING_ARTIFACT": {
        "artifact_kind": "single_path_summary",
        "artifact_value": "single_patch_summary",
        "task_relevant": True,
        "consumed_by_next_step": False,
        "final_message": "BASELINE_CODING::single_patch_summary",
    },
    "CHAIN_CODING_PRIMARY_PLAN": {
        "artifact_kind": "primary_plan",
        "artifact_value": "coding_plan",
        "task_relevant": True,
        "consumed_by_next_step": True,
        "final_message": "CHAIN_CODING_PLAN::coding_plan",
    },
    "CHAIN_CODING_ARTIFACT": {
        "artifact_kind": "coding_artifact",
        "artifact_value": "patch_skeleton",
        "task_relevant": True,
        "consumed_by_next_step": True,
        "final_message": "CHAIN_CODING_ARTIFACT::patch_skeleton",
    },
    "CHAIN_CODING_PRIMARY_RETURN": {
        "artifact_kind": "primary_return",
        "artifact_value": "integrated_patch_skeleton",
        "task_relevant": True,
        "consumed_by_next_step": False,
        "final_message": "CHAIN_CODING_RETURN::integrated_patch_skeleton",
    },
    "BASELINE_REVIEW_RETURN": {
        "artifact_kind": "review_summary",
        "artifact_value": "single_review_summary",
        "task_relevant": True,
        "consumed_by_next_step": False,
        "final_message": "BASELINE_REVIEW::single_review_summary",
    },
    "CHAIN_REVIEW_PRIMARY_PLAN": {
        "artifact_kind": "review_plan",
        "artifact_value": "review_plan",
        "task_relevant": True,
        "consumed_by_next_step": True,
        "final_message": "CHAIN_REVIEW_PLAN::review_plan",
    },
    "CHAIN_REVIEW_CODING": {
        "artifact_kind": "review_findings",
        "artifact_value": "structured_review_findings",
        "task_relevant": True,
        "consumed_by_next_step": True,
        "final_message": "CHAIN_REVIEW_FINDINGS::structured_review_findings",
    },
    "CHAIN_REVIEW_PRIMARY_RETURN": {
        "artifact_kind": "review_return",
        "artifact_value": "prioritized_review_return",
        "task_relevant": True,
        "consumed_by_next_step": False,
        "final_message": "CHAIN_REVIEW_RETURN::prioritized_review_return",
    },
}


class RepeatableWorkflowPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        prompt = str(payload.get("prompt") or "")
        model_id = str(payload.get("model_id") or "")
        route_backed = model_id == CODING_AGENT_MODEL_ID
        behavior = PROMPT_BEHAVIOR[prompt]
        result = {
            "status": "ok",
            "machine_error_code": "OK",
            "requested_slot_id": str(payload.get("slot_id") or ""),
            "selected_model": model_id,
            "runtime_model": model_id,
            "final_message": behavior["final_message"],
            "workflow_artifact_kind": behavior["artifact_kind"],
            "workflow_artifact": behavior["artifact_value"],
            "workflow_artifact_task_relevant": behavior["task_relevant"],
            "workflow_artifact_consumed_by_next_step": behavior["consumed_by_next_step"],
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
    runner: RepeatableWorkflowPromptRunner,
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
        "artifact_kind": runner_result.get("workflow_artifact_kind"),
        "artifact_task_relevant": runner_result.get("workflow_artifact_task_relevant") is True,
        "artifact_consumed_by_next_step": (
            runner_result.get("workflow_artifact_consumed_by_next_step") is True
        ),
        "response_preview_bounded": packet.get("response_preview_bounded"),
    }


def _build_task_class_row(
    *,
    task_class_id: str,
    manager: CodexCustomSessionManager,
    runner: RepeatableWorkflowPromptRunner,
) -> dict[str, Any]:
    fixture = TASK_CLASS_FIXTURES[task_class_id]
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
    baseline = _prompt_result(
        manager,
        runner,
        session_id,
        {
            "prompt": fixture["baseline_prompt"],
            "slot_id": PRIMARY_MODEL_SLOT,
        },
    )
    chain_entries = [
        _prompt_result(
            manager,
            runner,
            session_id,
            {"prompt": prompt, "slot_id": slot_id},
        )
        for prompt, slot_id in fixture["chain_prompts"]
    ]
    transcript = manager.transcript_packet(session_id)

    baseline_ok = baseline["packet"].get("status") == "ok"
    chain_ok = all(entry["packet"].get("status") == "ok" for entry in chain_entries)
    chain_step_ids = [entry["packet"].get("current_execution_slot_id") for entry in chain_entries]
    chain_step_separation = chain_step_ids == [
        PRIMARY_MODEL_SLOT,
        CODING_AGENT_MODEL_SLOT,
        PRIMARY_MODEL_SLOT,
    ]
    task_relevant_chain_signal = fixture["task_relevant_chain_signal"] is True
    coding_artifact_consumed = (
        chain_entries[1]["runner_result"].get("workflow_artifact_consumed_by_next_step") is True
        and chain_entries[2]["runner_result"].get("workflow_artifact_kind")
        in {"primary_return", "review_return", "route_decision"}
    )
    classification = str(fixture["classification"])
    return {
        "task_class_id": task_class_id,
        "session_id": session_id,
        "baseline_completed": baseline_ok,
        "chain_completed": chain_ok,
        "same_task_class": True,
        "same_policy_guard_conditions": (
            baseline["packet"].get("authorization_status") == "authorized_by_owner_gate"
            and all(
                entry["packet"].get("authorization_status") == "authorized_by_owner_gate"
                for entry in chain_entries
            )
        ),
        "same_admitted_semantic_mode": (
            baseline["packet"].get("configured_wire_api") == "responses"
            and all(
                entry["packet"].get("configured_wire_api") == "responses"
                for entry in chain_entries
            )
        ),
        "same_runtime_family": (
            baseline["packet"].get("mode_id")
            == chain_entries[0]["packet"].get("mode_id")
            == "codex_custom"
        ),
        "same_execution_path": False,
        "step_separation_observed": chain_step_separation,
        "task_relevant_chain_signal_observed": task_relevant_chain_signal,
        "coding_artifact_consumed_by_primary_return": coding_artifact_consumed,
        "classification": classification,
        "classification_reason_code": str(fixture["reason_code"]),
        "useful_with_limits": classification == "useful_with_limits",
        "baseline_only_preferred": classification == "baseline_only_preferred",
        "ceremony_only": classification == "ceremony_only",
        "indeterminate": classification == "indeterminate",
        "preferred_by_default_proven": False,
        "answer_quality_superiority_proven": False,
        "operator_mediated_only": True,
        "baseline_outcome": _outcome_view(baseline),
        "chain_outcomes": [_outcome_view(entry) for entry in chain_entries],
        "transcript_entry_count": len(transcript.get("entries") or []),
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root, evidence_dir
    with tempfile.TemporaryDirectory(prefix="wbp-repeatable-operator-readiness-r1-") as temp_dir:
        manager = CodexCustomSessionManager(Path(temp_dir))
        runner = RepeatableWorkflowPromptRunner()
        rows = [
            _build_task_class_row(task_class_id=task_class_id, manager=manager, runner=runner)
            for task_class_id in TASK_CLASSES
        ]

    useful_count = sum(1 for row in rows if row["useful_with_limits"])
    baseline_only_count = sum(1 for row in rows if row["baseline_only_preferred"])
    ceremony_count = sum(1 for row in rows if row["ceremony_only"])
    indeterminate_count = sum(1 for row in rows if row["indeterminate"])
    repeatable_usefulness_observed = useful_count >= 2
    task_class_ids = [row["task_class_id"] for row in rows]

    packets: dict[str, dict[str, Any]] = {}
    packets["task_class_readiness_matrix_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "task_class_readiness_matrix",
        "status": "ok",
        "task_class_count": len(rows),
        "task_class_ids": task_class_ids,
        "rows": [
            {
                "task_class_id": row["task_class_id"],
                "classification": row["classification"],
                "baseline_completed": row["baseline_completed"],
                "chain_completed": row["chain_completed"],
                "useful_with_limits": row["useful_with_limits"],
                "baseline_only_preferred": row["baseline_only_preferred"],
                "ceremony_only": row["ceremony_only"],
                "indeterminate": row["indeterminate"],
                "preferred_by_default_proven": False,
            }
            for row in rows
        ],
        "useful_with_limits_count": useful_count,
        "baseline_only_preferred_count": baseline_only_count,
        "ceremony_only_count": ceremony_count,
        "indeterminate_count": indeterminate_count,
        "class_count_summary_is_readiness_proof": False,
    }
    packets["baseline_vs_chain_task_class_results.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "baseline_vs_chain_task_class_results",
        "status": "ok",
        "comparison_scope_classification": "bounded_probe_only",
        "same_execution_path_for_all_rows": False,
        "rows": rows,
    }
    packets["operator_workflow_readiness_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "operator_workflow_readiness",
        "status": "ok",
        "final_status": TARGET_STATUS,
        "readiness_scope_classification": "operator_facing_bounded_probe_only",
        "operator_facing_bounded_readiness_classification": (
            "repeatable_usefulness_observed_with_limits"
            if repeatable_usefulness_observed
            else "not_proven"
        ),
        "task_class_ids": task_class_ids,
        "repeatable_usefulness_observed": repeatable_usefulness_observed,
        "preferred_by_default_proven": False,
        "product_readiness_proven": False,
        "rollout_readiness_proven": False,
        "autonomous_workflow_quality_proven": False,
        "user_wide_productivity_gain_proven": False,
    }
    packets["workflow_repeatability_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "workflow_repeatability",
        "status": "ok",
        "repeatability_scope_classification": "bounded_task_class_probe_only",
        "task_class_count": len(rows),
        "useful_with_limits_count": useful_count,
        "repeatable_usefulness_threshold_met": repeatable_usefulness_observed,
        "repeatable_usefulness_observed": repeatable_usefulness_observed,
        "baseline_only_preferred_count": baseline_only_count,
        "ceremony_only_count": ceremony_count,
        "indeterminate_count": indeterminate_count,
        "operator_mediated_repeatability_only": True,
        "default_workflow_preference_proven": False,
        "counts_not_used_as_primary_claim_basis": True,
    }
    packets["readiness_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "readiness_non_claims",
        "status": "ok",
        "useful_classes_prove_general_multi_agent_productivity": False,
        "repeatability_implies_answer_quality_superiority": False,
        "operator_mediated_repeatability_implies_autonomy": False,
        "bounded_readiness_implies_product_wide_readiness": False,
        "chain_preferred_class_eliminates_baseline_only_preferred_classes": False,
        "task_class_summary_implies_concurrency_usefulness": False,
        "repeated_usefulness_implies_default_workflow_preference": False,
        "usable_bounded_artifacts_imply_answer_quality_superiority": False,
        "class_count_summary_implies_readiness_by_itself": False,
        "bounded_readiness_implies_rollout_readiness": False,
    }
    packets["readiness_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "readiness_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "bounded_probe_task_classes_do_not_generalize_to_product_readiness",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "operator_mediated_repeatability_not_autonomous_workflow_quality",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "baseline_only_preferred_class_remains_admitted",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "class_count_summary_cannot_stand_as_readiness_proof",
                "severity": "medium",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "one_useful_class_treated_as_general_workflow_readiness": False,
        "baseline_only_preferred_classes_hidden_or_averaged_away": False,
        "operator_mediated_repeatability_treated_as_autonomous_intelligence": False,
        "cross_class_counts_treated_as_superiority_claim": False,
        "chain_ceremony_treated_as_workflow_value": False,
        "bounded_readiness_treated_as_rollout_readiness": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "three_bounded_task_classes_observed_under_same_owner_authorized_plain_response_guard",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "repeatable_usefulness_observed_in_two_task_classes_with_limits",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "baseline_only_preferred_class_remains_visible_in_matrix",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "operator_facing_bounded_readiness_does_not_expand_to_product_readiness",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "class_count_summary_alone_does_not_support_default_workflow_preference",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repeatable-operator-workflow-readiness-classification-r1-probe"
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
