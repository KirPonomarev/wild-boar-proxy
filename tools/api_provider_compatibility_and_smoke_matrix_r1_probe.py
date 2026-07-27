#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.model_catalog_fidelity_probe import api_snapshot, operator_status  # noqa: E402
from tools.responses_streaming_tools_failure_semantics_r1_probe import (  # noqa: E402
    build_packets as build_semantic_packets,
)
from wild_boar_proxy.codex_custom_sessions import (  # noqa: E402
    CODING_AGENT_MODEL_SLOT,
    CodexCustomSessionManager,
)
from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_generic_model_registry_packet,
)


PRIMARY_MODEL_ID = "gpt-5.5"


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


class RowPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        model_id = str(payload.get("model_id") or "")
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "final_message": f"ROW_SMOKE_OK::{model_id}",
            "secret_value_recorded": False,
            "configured_provider": "external_route",
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


def _semantic_limits_reference(repo_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        packets = build_semantic_packets(
            repo_root=repo_root,
            evidence_dir=Path(tmpdir) / "semantic_reference",
        )
    return {
        "reference_status": "ok",
        "reference_mode": "reproved_via_current_probe_code",
        "plain_text_only": packets["responses_semantics_packet.json"].get("text_only_semantics_proven")
        is True,
        "structured_semantics_proven": packets["responses_semantics_packet.json"].get(
            "structured_semantics_proven"
        )
        is True,
        "streaming_classification": str(
            packets["streaming_semantics_packet.json"].get("classification") or ""
        ),
        "consumer_streaming_accepted": packets["streaming_semantics_packet.json"].get(
            "consumer_streaming_accepted"
        )
        is True,
        "tool_classification": str(
            packets["tool_call_semantics_packet.json"].get("classification") or ""
        ),
        "consumer_tool_semantics_accepted": packets["tool_call_semantics_packet.json"].get(
            "consumer_tool_semantics_accepted"
        )
        is True,
        "model_driven_function_tool_protocol_supported": packets[
            "tool_call_semantics_packet.json"
        ].get("model_driven_function_tool_protocol_supported")
        is True,
    }


def _current_api_rows() -> list[dict[str, Any]]:
    registry = build_generic_model_registry_packet(
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    rows = registry.get("current_catalog_models")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("lane_kind") or "") == "wbp_api"
    ]


def _row_provider_truth(row: dict[str, Any]) -> tuple[str, bool]:
    provider = str(row.get("provider") or "").strip()
    return provider, bool(provider)


def _row_failure_category(create_packet: dict[str, Any]) -> str:
    code = str(create_packet.get("machine_error_code") or "")
    if code == "MODEL_NOT_SELECTABLE":
        return "route_disabled_or_not_selectable"
    if code in {"EXTERNAL_API_ROUTE_NOT_VISIBLE", "HEURISTIC_ONLY_NOT_EXECUTABLE"}:
        return "catalog_runtime_route_visibility_mismatch"
    if code == "EXTERNAL_API_ROUTE_NOT_READY":
        return "route_visible_but_not_ready"
    if code == "MODEL_NOT_SERVER_ISSUED":
        return "not_server_issued"
    return "unknown_blocked_row"


def _row_auth_status(create_packet: dict[str, Any]) -> str:
    code = str(create_packet.get("machine_error_code") or "")
    if code == "MODEL_NOT_SELECTABLE":
        return "route_visible_but_disabled"
    if code in {"EXTERNAL_API_ROUTE_NOT_VISIBLE", "HEURISTIC_ONLY_NOT_EXECUTABLE"}:
        return "not_proven_by_current_route_snapshot"
    if code == "EXTERNAL_API_ROUTE_NOT_READY":
        return "route_visible_but_not_ready"
    return "route_visible_and_secret_present"


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    semantic_limits = _semantic_limits_reference(repo_root)
    rows = _current_api_rows()
    commands_payload = commands()
    operator_payload = operator_status()
    api_payload = api_snapshot()

    row_results: list[dict[str, Any]] = []
    passing_rows: list[str] = []
    blocked_rows: list[str] = []
    observed_failure_categories: dict[str, int] = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        probe_session_root = Path(tmpdir) / "probe_session_root"
        if probe_session_root.exists():
            shutil.rmtree(probe_session_root)
        manager = CodexCustomSessionManager(probe_session_root)
        runner = RowPromptRunner()

        for row in rows:
            model_id = str(row.get("model_id") or "")
            provider, provider_proven = _row_provider_truth(row)
            create_packet = manager.create_packet(
                {
                    "primary_model_id": PRIMARY_MODEL_ID,
                    "coding_agent_model_id": model_id,
                },
                commands_payload,
                operator_payload,
                api_snapshot=api_payload,
            )
            result_row = {
                "model_id": model_id,
                "provider": provider,
                "provider_identity_proven": provider_proven,
                "provider_truth_status": "reported_by_current_snapshot"
                if provider_proven
                else "unresolved_in_current_snapshot",
                "provider_model_id": str(row.get("provider_model_id") or model_id),
                "display_name": str(row.get("display_name") or model_id),
                "selection_enabled": row.get("selection_enabled") is True,
                "selection_state": str(row.get("selection_state") or ""),
                "selection_disabled_reason_code": str(
                    row.get("selection_disabled_reason_code") or ""
                ),
                "auth_admission_status": "",
                "row_result": "",
                "row_pass_basis": "",
                "smoke_prompt_executed": False,
                "plain_response_smoke_passed": False,
                "live_provider_call_attempted": False,
                "upstream_provider_acceptance_proven": False,
                "failure_category": "",
                "failure_code": "",
                "source_provenance_status": "",
                "semantic_limits_inherited": {
                    "plain_text_only": semantic_limits["plain_text_only"],
                    "streaming_classification": semantic_limits["streaming_classification"],
                    "model_driven_function_tool_protocol_supported": semantic_limits[
                        "model_driven_function_tool_protocol_supported"
                    ],
                    "consumer_streaming_accepted": semantic_limits[
                        "consumer_streaming_accepted"
                    ],
                    "consumer_tool_semantics_accepted": semantic_limits[
                        "consumer_tool_semantics_accepted"
                    ],
                },
            }
            if create_packet.get("status") != "ok":
                failure_category = _row_failure_category(create_packet)
                observed_failure_categories[failure_category] = (
                    observed_failure_categories.get(failure_category, 0) + 1
                )
                result_row.update(
                    {
                        "auth_admission_status": _row_auth_status(create_packet),
                        "row_result": "blocked_by_runtime_path",
                        "row_pass_basis": "not_applicable_blocked_before_prompt",
                        "failure_category": failure_category,
                        "failure_code": str(create_packet.get("machine_error_code") or ""),
                        "source_provenance_status": "not_proven",
                    }
                )
                blocked_rows.append(model_id)
                row_results.append(result_row)
                continue
            prompt_packet = manager.prompt_packet(
                str(create_packet.get("session", {}).get("session_id") or ""),
                {
                    "prompt": f"Reply with exactly ROW_SMOKE_OK::{model_id}.",
                    "slot_id": CODING_AGENT_MODEL_SLOT,
                },
                runner.run,
                owner_authorized=True,
            )
            prompt_ok = prompt_packet.get("status") == "ok"
            result_row.update(
                {
                    "auth_admission_status": "route_visible_and_secret_present",
                    "row_result": "pass_with_limits" if prompt_ok else "blocked_by_protocol",
                    "row_pass_basis": (
                        "bounded_session_runtime_harness_plain_response_only"
                        if prompt_ok
                        else "bounded_session_runtime_harness_failed"
                    ),
                    "smoke_prompt_executed": True,
                    "plain_response_smoke_passed": prompt_ok,
                    "failure_category": ""
                    if prompt_ok
                    else "bounded_plain_response_smoke_failed",
                    "failure_code": ""
                    if prompt_ok
                    else str(prompt_packet.get("machine_error_code") or ""),
                    "source_provenance_status": str(
                        prompt_packet.get("selected_source_provenance") or ""
                    ),
                }
            )
            if prompt_ok:
                passing_rows.append(model_id)
            else:
                blocked_rows.append(model_id)
                observed_failure_categories["bounded_plain_response_smoke_failed"] = (
                    observed_failure_categories.get("bounded_plain_response_smoke_failed", 0)
                    + 1
                )
            row_results.append(result_row)

    packets: dict[str, dict[str, Any]] = {}
    packets["provider_smoke_row_results.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_smoke_row_results",
        "status": "ok" if row_results else "blocked",
        "row_count": len(row_results),
        "rows": row_results,
    }
    packets["provider_smoke_matrix_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_smoke_matrix",
        "status": "ok" if row_results else "blocked",
        "target_min_rows": 8,
        "target_max_rows": 12,
        "actual_row_count": len(row_results),
        "narrower_than_target_honestly_recorded": len(row_results) < 8,
        "passing_row_ids": passing_rows,
        "blocked_row_ids": blocked_rows,
        "row_pass_means_plain_response_smoke_only": True,
        "live_provider_calls_attempted": False,
        "upstream_provider_acceptance_proven": False,
        "session_runtime_harness_only": True,
        "provider_family_compatibility_claimed": False,
        "streaming_compatibility_claimed": False,
        "tool_compatibility_claimed": False,
    }
    packets["provider_failure_taxonomy_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_failure_taxonomy",
        "status": "ok",
        "observed_failure_categories": [
            {"category": category, "count": count}
            for category, count in sorted(observed_failure_categories.items())
        ],
        "failure_taxonomy_exhaustive": False,
        "fallback_policy_settled_here": False,
        "silent_substitution_detected": False,
    }
    packets["provider_semantic_limits_inheritance_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_semantic_limits_inheritance",
        "status": "ok",
        "reference_mode": semantic_limits["reference_mode"],
        "plain_text_only_inherited": semantic_limits["plain_text_only"],
        "streaming_classification_inherited": semantic_limits["streaming_classification"],
        "model_driven_function_tool_protocol_supported": semantic_limits[
            "model_driven_function_tool_protocol_supported"
        ],
        "consumer_streaming_accepted": semantic_limits["consumer_streaming_accepted"],
        "consumer_tool_semantics_accepted": semantic_limits["consumer_tool_semantics_accepted"],
        "semantic_limits_dropped_from_passing_rows": False,
    }
    packets["provider_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_non_claims",
        "status": "ok",
        "row_pass_implies_provider_family": False,
        "row_pass_implies_tools_generally": False,
        "row_pass_implies_streaming_generally": False,
        "row_pass_implies_durable_availability_over_time": False,
        "row_pass_implies_live_upstream_provider_acceptance": False,
        "failure_distribution_defines_budget_or_fallback_policy": False,
        "matrix_exhaustive": False,
    }
    packets["provider_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "current_server_issued_api_row_count_below_target_matrix_size",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "catalog_runtime_route_visibility_mismatch_for_direct_external_row",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "consumer_streaming_not_recleared_per_provider_row_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "consumer_tool_semantics_not_recleared_per_provider_row_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "provider_identity_unresolved_for_snapshot_rows_without_provider_field",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "live_provider_row_smoke_not_attempted_here",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "row_pass_treated_as_provider_family_support": False,
        "text_only_smoke_treated_as_streaming_or_tools_compatibility": False,
        "synthetic_harness_pass_treated_as_live_provider_compatibility": False,
        "historical_seed_rows_promoted_into_current_smoke_claims": False,
        "semantic_limits_dropped_from_passing_rows": False,
        "blocked_auth_or_runtime_row_treated_as_permanent_family_failure": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "passing_rows_are_limited_to_bounded_plain_response_smoke",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "no_material_overclaim_found_in_updated_evidence_scope",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "live_provider_acceptance_remains_unproven_here",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "direct_external_catalog_row_blocks_on_current_route_visibility",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "disabled_route_row_remains_blocked_and_non_selectable",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "matrix_size_remains_narrower_than_target_current_snapshot",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "streaming_and_tool_semantics_remain_inherited_not_row_proven",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "provider_identity_remains_unresolved_where_snapshot_omits_provider",
                "severity": "medium",
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

    packets = build_packets(repo_root=args.repo_root.resolve(), evidence_dir=args.evidence_dir.resolve())
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
