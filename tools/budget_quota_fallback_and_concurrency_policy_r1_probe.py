#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.api_provider_compatibility_and_smoke_matrix_r1_probe import (  # noqa: E402
    build_packets as build_provider_packets,
)
from tools.model_catalog_fidelity_probe import api_snapshot, operator_status  # noqa: E402
from wild_boar_proxy.codex_account_selection import (  # noqa: E402
    build_account_selection_packet,
    build_accounts_truth_packet,
)
from wild_boar_proxy.codex_custom_sessions import (  # noqa: E402
    CODING_AGENT_MODEL_SLOT,
    PRIMARY_MODEL_SLOT,
    ROLE_SLOT_IDS,
    CodexCustomSessionManager,
    forbidden_prompt_run_fields,
)
from wild_boar_proxy.external_models import contracts  # noqa: E402


PRIMARY_MODEL_ID = "gpt-5.3-codex"
API_MODEL_ID = "wbp:deepseek-max"


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


def account(
    backend_id: str,
    *,
    pool: str = "active",
    status: str = "healthy",
    priority: int = 10,
    last_error: str = "",
    last_error_class: str = "",
    cooldown_until: str | None = None,
    manual_hold: bool = False,
) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": pool,
        "status": status,
        "fail_count": 0,
        "success_count": 7,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": last_error,
        "last_error_class": last_error_class,
        "cooldown_until": cooldown_until,
        "manual_hold": manual_hold,
        "auth_ref": f"managed:{backend_id}",
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
        "accounts_list": command(
            {
                "accounts": [
                    account("acct-a", pool="active", status="healthy", priority=10),
                    account(
                        "acct-quota",
                        pool="active",
                        status="down",
                        priority=20,
                        last_error="HTTP 429: usage_limit_reached",
                        last_error_class="quota",
                    ),
                    account(
                        "acct-auth",
                        pool="active",
                        status="down",
                        priority=30,
                        last_error="HTTP 401: auth_unavailable",
                        last_error_class="auth",
                    ),
                    account(
                        "acct-cooldown",
                        pool="active",
                        status="degraded",
                        priority=40,
                        cooldown_until="2026-05-29T00:00:00Z",
                    ),
                ]
            }
        ),
        "rollout_rotation_inspect": command({"status": "ok", "machine_error_code": "OK"}),
    }


class RecordingPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        route_backed = str(payload.get("model_id") or "") == API_MODEL_ID
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "final_message": "API_POLICY_OK" if route_backed else "PRIMARY_POLICY_OK",
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


def _provider_reference(repo_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        packets = build_provider_packets(
            repo_root=repo_root,
            evidence_dir=Path(tmpdir) / "provider_reference",
        )
    matrix = packets["provider_smoke_matrix_packet.json"]
    rows = packets["provider_smoke_row_results.json"]["rows"]
    failure = packets["provider_failure_taxonomy_packet.json"]
    return {
        "reference_mode": "reproved_via_current_probe_code",
        "passing_row_ids": list(matrix.get("passing_row_ids") or []),
        "blocked_row_ids": list(matrix.get("blocked_row_ids") or []),
        "row_pass_means_plain_response_smoke_only": matrix.get(
            "row_pass_means_plain_response_smoke_only"
        )
        is True,
        "silent_substitution_detected": failure.get("silent_substitution_detected") is True,
        "blocked_row_count": sum(
            1
            for row in rows
            if isinstance(row, dict) and str(row.get("row_result") or "").startswith("blocked")
        ),
        "passing_row_count": sum(
            1 for row in rows if isinstance(row, dict) and row.get("row_result") == "pass_with_limits"
        ),
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del evidence_dir
    commands_payload = commands()
    accounts_truth = build_accounts_truth_packet(commands_payload)
    selection = build_account_selection_packet(commands_payload, operator_status())
    provider_reference = _provider_reference(repo_root)
    default_policy = contracts.default_state_payload()["policy"]

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CodexCustomSessionManager(Path(tmpdir) / "probe_session_root")
        runner = RecordingPromptRunner()
        created = manager.create_packet(
            {
                "primary_model_id": PRIMARY_MODEL_ID,
                "coding_agent_model_id": API_MODEL_ID,
            },
            commands_payload,
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        session_id = str(created.get("session", {}).get("session_id") or "")
        invalid_slot = manager.prompt_packet(
            session_id,
            {"prompt": "Reply with exactly INVALID_SLOT_BLOCKED.", "slot_id": "made_up_slot"},
            runner.run,
            owner_authorized=True,
        )
        coding_run = manager.prompt_packet(
            session_id,
            {
                "prompt": "Reply with exactly API_POLICY_OK.",
                "slot_id": CODING_AGENT_MODEL_SLOT,
            },
            runner.run,
            owner_authorized=True,
        )
        concurrent_started = threading.Event()
        concurrent_release = threading.Event()
        concurrent_calls: list[dict[str, Any]] = []
        concurrent_first_result: dict[str, Any] = {}

        def blocking_runner(payload: dict[str, Any]) -> dict[str, Any]:
            concurrent_calls.append(dict(payload))
            concurrent_started.set()
            concurrent_release.wait(timeout=2)
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "PRIMARY_POLICY_OK",
                "secret_value_recorded": False,
                "configured_provider": "cliproxy",
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
                },
            }

        def invoke_first() -> None:
            concurrent_first_result["packet"] = manager.prompt_packet(
                session_id,
                {"prompt": "Reply with exactly FIRST_CONCURRENT_BLOCK."},
                blocking_runner,
                owner_authorized=True,
            )

        worker = threading.Thread(target=invoke_first)
        worker.start()
        concurrent_started.wait(timeout=2)
        concurrent_blocked = manager.prompt_packet(
            session_id,
            {"prompt": "Reply with exactly SECOND_CONCURRENT_BLOCK."},
            blocking_runner,
            owner_authorized=True,
        )
        concurrent_release.set()
        worker.join(timeout=2)

    forbidden_batch_fields = forbidden_prompt_run_fields(
        {
            "prompt": "Reply with exactly NO_BATCH.",
            "slot_ids": [PRIMARY_MODEL_SLOT, CODING_AGENT_MODEL_SLOT],
        }
    )
    allowed_runner_payload_fields = {"model_id", "prompt", "slot_id"}
    forbidden_model_dispatch_fields = {"model_ids", "models", "slot_ids"}
    one_model_id_per_call = all(
        isinstance(call.get("model_id"), str)
        and bool(str(call.get("model_id") or "").strip())
        and set(call.keys()).issubset(allowed_runner_payload_fields)
        and not any(field in call for field in forbidden_model_dispatch_fields)
        for call in runner.calls
    )
    coding_route_proven = coding_run.get("selected_route_server_issued") is True
    coding_fallback_attempted = coding_run.get("fallback_attempted") is True

    packets: dict[str, dict[str, Any]] = {}
    packets["budget_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "budget_boundary",
        "status": "ok",
        "external_paid_route_policy_present": True,
        "external_paid_routes_enabled_default": default_policy["paid_routes_enabled"] is True,
        "external_paid_route_default": str(default_policy["paid_route_default"] or ""),
        "external_paid_route_allowlist_count": len(default_policy["paid_route_allowlist"]),
        "custom_session_budget_packet_present": False,
        "per_session_budget_packet_present": False,
        "per_slot_budget_packet_present": False,
        "runtime_meter_attached": False,
        "hard_overspend_prevention_proven": False,
        "pre_execution_spend_gate_proven": False,
        "policy_enforcement_state": "declared_or_partial_only",
        "silent_paid_parallel_fanout_observed": False,
        "budget_packet_presence_implies_hard_enforcement": False,
    }
    packets["quota_handling_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "quota_handling",
        "status": "ok",
        "launch_capable_count": accounts_truth["launch_capable_count"],
        "quota_exhausted_count": accounts_truth["quota_classes"]["quota_exhausted"],
        "auth_invalid_count": accounts_truth["eligibility_classes"]["auth_invalid"],
        "cooldown_only_count": accounts_truth["cooldown_classes"]["cooldown_only"],
        "selection_status": str(selection.get("status") or ""),
        "selection_machine_error_code": str(selection.get("machine_error_code") or ""),
        "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
        "selected_backend_source": str(selection.get("selected_backend_source") or ""),
        "401_403_429_5xx_separate_runtime_policy_proven": False,
        "silent_retry_storm_observed": False,
        "retry_policy_explicit": False,
        "quota_failure_implies_provider_family_incompatibility": False,
    }
    packets["fallback_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "fallback_boundary",
        "status": "ok",
        "fallback_eligible_schema_field_present": "fallback_eligible"
        in contracts.ROUTE_ALLOWED_FIELDS,
        "automatic_fallback_policy_present": False,
        "invalid_slot_rejected_without_primary_fallback": (
            invalid_slot.get("status") == "rejected"
            and str(invalid_slot.get("machine_error_code") or "") == "SLOT_ID_NOT_SERVER_ISSUED"
            and invalid_slot.get("fallback_attempted") is False
        ),
        "prompt_path_fallback_attempted": coding_fallback_attempted,
        "provider_row_reference_mode": provider_reference["reference_mode"],
        "blocked_provider_rows_present": provider_reference["blocked_row_count"] > 0,
        "blocked_rows_auto_fallback_observed": False,
        "silent_substitution_detected": provider_reference["silent_substitution_detected"],
        "fallback_eligibility_implies_auto_fallback": False,
    }
    packets["concurrency_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "concurrency_boundary",
        "status": "ok",
        "prompt_run_single_slot_only": True,
        "browser_multi_slot_batch_request_forbidden": "slot_ids" in forbidden_batch_fields,
        "runner_call_count": len(runner.calls),
        "runner_payload_one_model_id_per_call": one_model_id_per_call,
        "runner_payload_forbidden_model_fields_absent": one_model_id_per_call,
        "runner_payload_only_allowed_fields_observed": all(
            set(call.keys()).issubset(allowed_runner_payload_fields) for call in runner.calls
        ),
        "coding_slot_route_proven": coding_route_proven,
        "concurrent_execution_blocked_observed": (
            concurrent_blocked.get("status") == "blocked"
            and str(concurrent_blocked.get("machine_error_code") or "")
            == "CONCURRENT_PROMPT_EXECUTION_NOT_ALLOWED"
            and concurrent_blocked.get("prompt_runner_called") is False
            and len(concurrent_calls) == 1
            and concurrent_first_result.get("packet", {}).get("status") == "ok"
        ),
        "concurrent_execution_observed": False,
        "paid_parallel_fanout_proven": False,
        "per_session_concurrency_cap_explicit": True,
        "per_slot_concurrency_cap_explicit": False,
        "classification": "forbidden_with_runtime_guard",
        "concurrency_classification_implies_throughput_gain": False,
    }
    packets["slot_execution_limit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "slot_execution_limit",
        "status": "ok",
        "allowed_slot_ids": list(ROLE_SLOT_IDS),
        "browser_batch_slot_surface_present": False,
        "forbidden_prompt_run_fields": forbidden_batch_fields,
        "current_execution_slot_id": str(coding_run.get("current_execution_slot_id") or ""),
        "current_execution_path_source": str(
            coding_run.get("current_execution_path_source") or ""
        ),
        "runner_payload_keys": sorted(runner.calls[-1].keys()) if runner.calls else [],
        "one_model_dispatch_per_run": one_model_id_per_call,
        "explicit_slot_id_allowed_in_runner_payload": (
            "slot_id" in runner.calls[-1] if runner.calls else False
        ),
        "slot_binding_runtime_dispatch_claimed": False,
    }
    packets["policy_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "policy_non_claims",
        "status": "ok",
        "automatic_cross_provider_fallback_safe": False,
        "retry_behavior_production_grade": False,
        "concurrent_slot_execution_safe": False,
        "concurrency_classification_implies_acceleration_benefit": False,
        "fallback_eligibility_implies_automatic_fallback_approval": False,
        "budget_packet_presence_alone_implies_hard_spend_enforcement": False,
        "row_pass_authorizes_paid_parallel_fanout": False,
    }
    packets["policy_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "policy_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "hard_budget_enforcement_not_proven_in_custom_session_runtime",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "operator_surface_pre_execution_spend_gate_not_proven_here",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "explicit_quota_retry_policy_not_proven_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "automatic_fallback_policy_remains_absent_or_manual_only",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "web_launch_default_model_substitution_not_closed_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "concurrent_paid_fanout_remains_forbidden_or_unproven",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "compatibility_row_becomes_automatic_fallback_target": False,
        "budget_presence_treated_as_hard_spend_protection": False,
        "concurrency_limit_treated_as_performance_improvement": False,
        "quota_classification_treated_as_final_retry_policy": False,
        "blocked_rows_treated_as_fallback_targets": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "silent_browser_driven_fallback_not_observed_in_current_prompt_path",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "external_paid_route_policy_exists_only_as_declared_contract_here",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "operator_surface_executes_before_full_spend_gate_proof",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "quota_handling_is_static_classification_not_live_retry_policy",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "launch_surfaces_still_allow_default_model_substitution_outside_this_fix",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "concurrent_paid_fanout_remains_unproven_beyond_single_slot_request_shape",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return packets


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
    summary = {
        "status": "ok",
        "packet_count": len(packets),
        "evidence_dir": str(args.evidence_dir.resolve()),
        "packets": sorted(packets),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
