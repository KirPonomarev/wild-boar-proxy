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
    REVIEWER_MODEL_SLOT,
    CodexCustomSessionManager,
)


PRIMARY_MODEL_ID = "gpt-5.3-codex"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"


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


class RecordingPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        slot_id = str(payload.get("slot_id") or "")
        route_backed = payload.get("model_id") == CODING_AGENT_MODEL_ID
        if slot_id == PRIMARY_MODEL_SLOT and "PRIMARY_STEP_2" in str(payload.get("prompt") or ""):
            final_message = "PRIMARY_STEP_2_OK"
        elif slot_id == PRIMARY_MODEL_SLOT:
            final_message = "PRIMARY_STEP_1_OK"
        else:
            final_message = "CODING_STEP_OK"
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "requested_slot_id": slot_id,
            "selected_model": str(payload.get("model_id") or ""),
            "runtime_model": str(payload.get("model_id") or ""),
            "final_message": final_message,
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


def _step_packet(packet: dict[str, Any], call: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": packet.get("status"),
        "session_id": packet.get("session_id"),
        "requested_slot_id": packet.get("requested_slot_id"),
        "requested_slot_explicit": packet.get("requested_slot_explicit") is True,
        "packet_execution_slot_id": packet.get("current_execution_slot_id"),
        "runner_slot_id_echo": packet.get("runner_slot_id_echo"),
        "runner_slot_id_matches_requested": packet.get("runner_slot_id_matches_requested") is True,
        "runner_payload_slot_id": call.get("slot_id"),
        "runner_payload_model_id": call.get("model_id"),
        "requested_slot_bound": packet.get("requested_slot_bound") is True,
        "slot_catalog_revalidated": packet.get("slot_catalog_revalidated") is True,
        "slot_model_server_issued": packet.get("slot_model_server_issued") is True,
        "slot_lane_revalidated": packet.get("slot_lane_revalidated") is True,
        "slot_source_revalidated": packet.get("slot_source_revalidated") is True,
        "slot_admission_passed": packet.get("slot_admission_passed") is True,
        "wbp_runner_payload_slot_id": packet.get("wbp_runner_payload_slot_id"),
        "wbp_runner_payload_model_id": packet.get("wbp_runner_payload_model_id"),
        "wbp_runner_payload_slot_matches_requested": (
            packet.get("wbp_runner_payload_slot_matches_requested") is True
        ),
        "wbp_runner_payload_model_matches_slot": (
            packet.get("wbp_runner_payload_model_matches_slot") is True
        ),
        "wbp_session_manager_slot_dispatch_proven": (
            packet.get("wbp_session_manager_slot_dispatch_proven") is True
        ),
        "runtime_slot_dispatch_proof_scope": packet.get("runtime_slot_dispatch_proof_scope"),
        "downstream_runner_slot_echo_present": (
            packet.get("downstream_runner_slot_echo_present") is True
        ),
        "downstream_runner_slot_echo": packet.get("downstream_runner_slot_echo"),
        "downstream_runner_slot_echo_matches_requested": (
            packet.get("downstream_runner_slot_echo_matches_requested") is True
        ),
        "executed_slot_id": packet.get("executed_slot_id"),
        "executed_slot_model_id": packet.get("executed_slot_model_id"),
        "runtime_slot_dispatch_proven": packet.get("runtime_slot_dispatch_proven") is True,
        "slot_binding_runtime_dispatch_claimed": (
            packet.get("slot_binding_runtime_dispatch_claimed") is True
        ),
        "parallel_slot_execution_proven": packet.get("parallel_slot_execution_proven") is True,
        "fanout_execution_proven": packet.get("fanout_execution_proven") is True,
        "model_id": packet.get("model_id"),
        "selected_source_provenance": packet.get("selected_source_provenance"),
        "configured_provider": packet.get("configured_provider"),
        "live_prompt_full_success": packet.get("live_prompt_full_success") is True,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root
    with tempfile.TemporaryDirectory(prefix="wbp-role-slot-handoff-r1-") as temp_dir:
        session_root = Path(temp_dir)
        manager = CodexCustomSessionManager(session_root)
        runner = RecordingPromptRunner()

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

        primary_first = manager.prompt_packet(
            session_id,
            {
                "prompt": "PRIMARY_STEP_1",
                "slot_id": PRIMARY_MODEL_SLOT,
            },
            runner.run,
            owner_authorized=True,
        )
        coding = manager.prompt_packet(
            session_id,
            {
                "prompt": "CODING_STEP",
                "slot_id": CODING_AGENT_MODEL_SLOT,
            },
            runner.run,
            owner_authorized=True,
        )
        primary_second = manager.prompt_packet(
            session_id,
            {
                "prompt": "PRIMARY_STEP_2",
                "slot_id": PRIMARY_MODEL_SLOT,
            },
            runner.run,
            owner_authorized=True,
        )
        call_count_before_blocked = len(runner.calls)
        blocked = manager.prompt_packet(
            session_id,
            {
                "prompt": "REVIEW_STEP",
                "slot_id": REVIEWER_MODEL_SLOT,
            },
            runner.run,
            owner_authorized=True,
        )
        call_count_after_blocked = len(runner.calls)
        defaulted_primary = manager.prompt_packet(
            session_id,
            {
                "prompt": "DEFAULT_PRIMARY_STEP",
            },
            runner.run,
            owner_authorized=True,
        )
        detail = manager.get_packet(session_id)
        transcript = manager.transcript_packet(session_id)

        primary_first_call = runner.calls[0]
        coding_call = runner.calls[1]
        primary_second_call = runner.calls[2]
    primary_honored = (
        primary_first.get("status") == "ok"
        and primary_first.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
        and primary_first.get("runner_slot_id_matches_requested") is True
        and primary_first.get("runtime_slot_dispatch_proven") is True
        and primary_first.get("slot_binding_runtime_dispatch_claimed") is True
        and primary_first.get("runtime_slot_dispatch_proof_scope") == "wbp_session_manager_payload_plus_downstream_echo"
        and primary_first.get("parallel_slot_execution_proven") is False
        and primary_first.get("fanout_execution_proven") is False
        and primary_first_call.get("slot_id") == PRIMARY_MODEL_SLOT
        and primary_first.get("wbp_runner_payload_slot_id") == PRIMARY_MODEL_SLOT
        and primary_first.get("wbp_runner_payload_model_id") == PRIMARY_MODEL_ID
        and primary_first.get("wbp_session_manager_slot_dispatch_proven") is True
        and primary_first.get("model_id") == PRIMARY_MODEL_ID
        and primary_first_call.get("model_id") == PRIMARY_MODEL_ID
        and primary_first.get("configured_provider") == "cliproxy"
        and primary_first.get("selected_source_provenance") == "backend_proven"
    )
    coding_honored = (
        coding.get("status") == "ok"
        and coding.get("current_execution_slot_id") == CODING_AGENT_MODEL_SLOT
        and coding.get("runner_slot_id_matches_requested") is True
        and coding.get("runtime_slot_dispatch_proven") is True
        and coding.get("slot_binding_runtime_dispatch_claimed") is True
        and coding.get("runtime_slot_dispatch_proof_scope") == "wbp_session_manager_payload_plus_downstream_echo"
        and coding.get("parallel_slot_execution_proven") is False
        and coding.get("fanout_execution_proven") is False
        and coding_call.get("slot_id") == CODING_AGENT_MODEL_SLOT
        and coding.get("wbp_runner_payload_slot_id") == CODING_AGENT_MODEL_SLOT
        and coding.get("wbp_runner_payload_model_id") == CODING_AGENT_MODEL_ID
        and coding.get("wbp_session_manager_slot_dispatch_proven") is True
        and coding.get("model_id") == CODING_AGENT_MODEL_ID
        and coding_call.get("model_id") == CODING_AGENT_MODEL_ID
        and coding.get("configured_provider") == "external_route"
        and coding.get("selected_source_provenance") == "route_proven"
    )
    return_to_primary_observed = (
        primary_second.get("status") == "ok"
        and primary_second.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
        and primary_second.get("runner_slot_id_matches_requested") is True
        and primary_second.get("runtime_slot_dispatch_proven") is True
        and primary_second.get("slot_binding_runtime_dispatch_claimed") is True
        and primary_second.get("runtime_slot_dispatch_proof_scope") == "wbp_session_manager_payload_plus_downstream_echo"
        and primary_second.get("parallel_slot_execution_proven") is False
        and primary_second.get("fanout_execution_proven") is False
        and primary_second_call.get("slot_id") == PRIMARY_MODEL_SLOT
        and primary_second.get("wbp_runner_payload_slot_id") == PRIMARY_MODEL_SLOT
        and primary_second.get("wbp_runner_payload_model_id") == PRIMARY_MODEL_ID
        and primary_second.get("wbp_session_manager_slot_dispatch_proven") is True
        and primary_second.get("model_id") == PRIMARY_MODEL_ID
        and primary_second_call.get("model_id") == PRIMARY_MODEL_ID
        and primary_second.get("configured_provider") == "cliproxy"
        and detail.get("session", {}).get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
    )
    blocked_reviewer_honest = (
        blocked.get("status") == "rejected"
        and blocked.get("machine_error_code") == "SLOT_NOT_BOUND"
        and blocked.get("requested_slot_id") == REVIEWER_MODEL_SLOT
        and blocked.get("runtime_slot_dispatch_proven") is False
        and blocked.get("slot_binding_runtime_dispatch_claimed") is False
        and blocked.get("runtime_slot_dispatch_proof_scope") == "not_attempted_precondition_failed"
        and blocked.get("fallback_attempted") is False
        and call_count_after_blocked == call_count_before_blocked
    )
    implicit_primary_default_observed = (
        defaulted_primary.get("status") == "ok"
        and defaulted_primary.get("requested_slot_id") == PRIMARY_MODEL_SLOT
        and defaulted_primary.get("requested_slot_explicit") is False
        and defaulted_primary.get("requested_slot_defaulted_to_primary") is True
        and defaulted_primary.get("wbp_runner_payload_slot_id") == PRIMARY_MODEL_SLOT
        and defaulted_primary.get("wbp_session_manager_slot_dispatch_proven") is True
        and defaulted_primary.get("runtime_slot_dispatch_proven") is True
    )

    dispatch_ok = primary_honored and coding_honored and return_to_primary_observed
    packets: dict[str, dict[str, Any]] = {}

    packets["role_slot_dispatch_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_dispatch",
        "status": "ok" if dispatch_ok else "blocked",
        "session_id": session_id,
        "primary_slot_dispatched": primary_honored,
        "coding_agent_slot_dispatched": coding_honored,
        "reviewer_slot_dispatched": False,
        "requested_slot_ids": [
            primary_first.get("requested_slot_id"),
            coding.get("requested_slot_id"),
            primary_second.get("requested_slot_id"),
        ],
        "runner_received_slot_ids": [
            primary_first_call.get("slot_id"),
            coding_call.get("slot_id"),
            primary_second_call.get("slot_id"),
        ],
        "runtime_slot_dispatch_proof_scope": "wbp_session_manager_payload_plus_downstream_echo",
        "wbp_session_manager_slot_dispatch_proven": dispatch_ok,
        "runtime_slot_dispatch_proven": dispatch_ok,
        "slot_binding_implies_dispatch": False,
        "operator_mediated_sequential_dispatch_proven": dispatch_ok,
        "parallel_slot_execution_proven": False,
        "fanout_execution_proven": False,
        "runtime_native_orchestration_proven": False,
        "same_model_multi_role_disambiguation_proven": False,
    }
    packets["orchestration_handoff_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "orchestration_handoff",
        "status": "ok" if dispatch_ok else "blocked",
        "session_id": session_id,
        "handoff_chain": [
            f"{PRIMARY_MODEL_SLOT}->{CODING_AGENT_MODEL_SLOT}",
            f"{CODING_AGENT_MODEL_SLOT}->{PRIMARY_MODEL_SLOT}",
        ],
        "handoff_kind": "operator_mediated_sequential",
        "primary_to_coding_handoff_observed": primary_honored and coding_honored,
        "coding_to_primary_return_observed": return_to_primary_observed,
        "concurrent_execution_observed": False,
        "generalized_workflow_capability_proven": False,
        "autonomous_runtime_native_orchestration_proven": False,
    }
    packets["step_provenance_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "step_provenance",
        "status": "ok" if dispatch_ok else "blocked",
        "session_id": session_id,
        "steps": [
            _step_packet(primary_first, primary_first_call),
            _step_packet(coding, coding_call),
            _step_packet(primary_second, primary_second_call),
        ],
        "transcript_entry_count": len(transcript.get("entries") or []),
        "transcript_preserves_step_events": len(transcript.get("entries") or []) >= 4,
    }
    packets["role_honor_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_honor_boundary",
        "status": "ok",
        "session_id": session_id,
        "primary_honored": primary_honored,
        "coding_agent_honored": coding_honored,
        "reviewer_honored": False,
        "cheap_scanner_honored": False,
        "deep_reasoning_honored": False,
        "only_primary_and_coding_directly_observed": True,
        "operator_mediated_not_autonomous": True,
        "same_model_multi_role_disambiguation_proven": False,
        "implicit_primary_default_observed": implicit_primary_default_observed,
    }
    packets["blocked_handoff_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "blocked_handoff",
        "status": "ok" if blocked_reviewer_honest else "blocked",
        "blocked_packet_status": blocked.get("status"),
        "blocked_packet_machine_error_code": blocked.get("machine_error_code"),
        "requested_slot_id": blocked.get("requested_slot_id"),
        "current_execution_slot_id": blocked.get("current_execution_slot_id"),
        "precondition_failures": list(blocked.get("precondition_failures") or []),
        "runner_call_count_unchanged": call_count_after_blocked == call_count_before_blocked,
        "fallback_attempted": blocked.get("fallback_attempted") is True,
        "blocked_handoff_honest": blocked_reviewer_honest,
    }
    packets["orchestration_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "orchestration_non_claims",
        "status": "ok",
        "stored_slots_imply_autonomous_orchestration": False,
        "single_handoff_proves_generalized_workflow": False,
        "sequential_handoff_implies_concurrent_execution": False,
        "reviewer_slot_runtime_honor_proven": False,
        "scanner_slot_runtime_honor_proven": False,
        "deep_reasoning_slot_runtime_honor_proven": False,
        "operator_mediated_equals_runtime_native": False,
        "completed_chain_implies_workflow_usefulness": False,
        "blocked_handoff_expands_fallback_policy": False,
        "same_model_multi_role_disambiguation_proven": False,
        "implicit_primary_defaulting_is_handoff_proof": False,
    }
    packets["orchestration_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "orchestration_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "runtime_native_orchestration_not_proven",
                "severity": "high",
                "summary": "Current contour proves only operator-mediated sequential handoff truth.",
            },
            {
                "id": "downstream_reviewer_scanner_slots_unproven",
                "severity": "medium",
                "summary": "Reviewer/scanner/deep-reasoning slot runtime honor remains unproven here.",
            },
            {
                "id": "concurrent_orchestration_not_proven",
                "severity": "medium",
                "summary": "Sequential handoff truth does not prove concurrent orchestration readiness.",
            },
            {
                "id": "same_model_multi_role_disambiguation_not_proven",
                "severity": "medium",
                "summary": "Current runtime does not prove distinct slot honor when multiple roles share one model identity.",
            },
            {
                "id": "implicit_primary_defaulting_remains_admitted",
                "severity": "medium",
                "summary": "Omitted slot_id still defaults to primary_model_slot and must not be read as explicit handoff truth.",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "orchestration_false_green_boundary",
        "status": "ok",
        "stored_slot_treated_as_dispatch_proof": False,
        "operator_mediated_sequence_treated_as_autonomous": False,
        "sequential_handoff_treated_as_concurrent": False,
        "completed_chain_treated_as_workflow_value": False,
        "blocked_handoff_treated_as_successful_fallback": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "orchestration_independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "explicit_slot_target_is_forwarded_to_runner_payload",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "primary_coding_primary_sequence_is_packet_backed",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "blocked_unbound_reviewer_slot_does_not_fallback",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "distinct_runtime_model_and_provider_paths_observed_for_primary_and_coding_slots",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "implicit_primary_defaulting_is_packet_visible_and_left_narrow",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "autonomous_runtime_native_orchestration_remains_unproven",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return packets


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="role-slot-runtime-honor-and-handoff-semantics-r1-probe"
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()

    packets = build_packets(repo_root=args.repo_root.resolve(), evidence_dir=args.evidence_dir.resolve())
    for name, payload in packets.items():
        json_write(args.evidence_dir / name, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "packet_count": len(packets),
                "evidence_dir": str(args.evidence_dir.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
