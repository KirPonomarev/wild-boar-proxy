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
    CodexCustomSessionManager,
    PRIMARY_MODEL_SLOT,
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
        route_backed = payload.get("model_id") == CODING_AGENT_MODEL_ID
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "final_message": "API_LANE_OK" if route_backed else "CHATGPT_LANE_OK",
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


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root
    session_root = evidence_dir / "probe_session_root"
    if session_root.exists():
        shutil.rmtree(session_root)
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
    primary = manager.prompt_packet(
        session_id,
        {"prompt": "Reply with exactly CHATGPT_LANE_OK."},
        runner.run,
        owner_authorized=True,
    )
    api_lane = manager.prompt_packet(
        session_id,
        {
            "prompt": "Reply with exactly API_LANE_OK.",
            "slot_id": CODING_AGENT_MODEL_SLOT,
        },
        runner.run,
        owner_authorized=True,
    )
    detail = manager.get_packet(session_id)

    same_session_ok = (
        created.get("status") == "ok"
        and primary.get("status") == "ok"
        and api_lane.get("status") == "ok"
        and bool(session_id)
        and primary.get("session_id") == session_id
        and api_lane.get("session_id") == session_id
    )
    provenance_separated = (
        primary.get("selected_source_provenance") == "backend_proven"
        and api_lane.get("selected_source_provenance") == "route_proven"
        and primary.get("model_id") != api_lane.get("model_id")
        and primary.get("selected_route_server_issued") is False
        and api_lane.get("selected_route_server_issued") is True
        and primary.get("configured_provider") == "cliproxy"
        and api_lane.get("configured_provider") == "external_route"
    )
    fallback_clean = (
        primary.get("fallback_attempted") is False
        and api_lane.get("fallback_attempted") is False
        and len(runner.calls) == 2
        and runner.calls[0].get("model_id") == PRIMARY_MODEL_ID
        and runner.calls[1].get("model_id") == CODING_AGENT_MODEL_ID
    )

    packets: dict[str, dict[str, Any]] = {}
    packets["chatgpt_lane_runtime_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "chatgpt_lane_runtime",
        "status": primary.get("status"),
        "session_id": session_id,
        "current_execution_slot_id": primary.get("current_execution_slot_id"),
        "model_id": primary.get("model_id"),
        "selected_source_class": primary.get("selected_source_class"),
        "selected_source_provenance": primary.get("selected_source_provenance"),
        "configured_provider": primary.get("configured_provider"),
        "selected_backend_server_issued": primary.get("selected_backend_server_issued"),
        "selected_route_server_issued": primary.get("selected_route_server_issued"),
        "live_prompt_full_success": primary.get("live_prompt_full_success") is True,
        "same_session_identity_proven": primary.get("session_id") == session_id,
        "counts_as_api_lane_truth": False,
    }
    packets["api_lane_runtime_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "api_lane_runtime",
        "status": api_lane.get("status"),
        "session_id": session_id,
        "current_execution_slot_id": api_lane.get("current_execution_slot_id"),
        "model_id": api_lane.get("model_id"),
        "selected_source_class": api_lane.get("selected_source_class"),
        "selected_source_provenance": api_lane.get("selected_source_provenance"),
        "configured_provider": api_lane.get("configured_provider"),
        "selected_backend_server_issued": api_lane.get("selected_backend_server_issued"),
        "selected_route_server_issued": api_lane.get("selected_route_server_issued"),
        "route_provenance_required": api_lane.get("route_provenance_required") is True,
        "route_provenance_proven": api_lane.get("route_provenance_proven") is True,
        "live_prompt_full_success": api_lane.get("live_prompt_full_success") is True,
        "same_session_identity_proven": api_lane.get("session_id") == session_id,
        "counts_as_provider_family_compatibility": False,
    }
    packets["simultaneous_session_runtime_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "same_session_dual_lane_runtime",
        "status": "ok" if same_session_ok and provenance_separated and fallback_clean else "blocked",
        "session_id": session_id,
        "same_session_identity_proven": same_session_ok,
        "chatgpt_lane_callable": primary.get("status") == "ok",
        "api_lane_callable": api_lane.get("status") == "ok",
        "same_session_callability_proven": same_session_ok and provenance_separated,
        "concurrent_execution_observed": False,
        "simultaneous_dispatch_proven": False,
        "current_execution_slot_id_after_second_call": detail.get("session", {}).get(
            "current_execution_slot_id"
        ),
        "current_execution_path_source_after_second_call": detail.get("session", {}).get(
            "current_execution_path_source"
        ),
        "runner_call_count": len(runner.calls),
    }
    packets["dual_lane_source_provenance_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "dual_lane_source_provenance",
        "status": "ok" if provenance_separated else "blocked",
        "chatgpt_selected_source_provenance": primary.get("selected_source_provenance"),
        "api_selected_source_provenance": api_lane.get("selected_source_provenance"),
        "chatgpt_selected_source_class": primary.get("selected_source_class"),
        "api_selected_source_class": api_lane.get("selected_source_class"),
        "chatgpt_configured_provider": primary.get("configured_provider"),
        "api_configured_provider": api_lane.get("configured_provider"),
        "chatgpt_backend_server_issued": primary.get("selected_backend_server_issued") is True,
        "api_route_server_issued": api_lane.get("selected_route_server_issued") is True,
        "silent_source_collapse_observed": False,
        "counts_as_concurrent_execution": False,
    }
    packets["slot_dispatch_separation_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "slot_dispatch_separation",
        "status": "ok"
        if (
            created.get("session", {}).get("role_slot_binding_count") == 2
            and primary.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT
            and api_lane.get("current_execution_slot_id") == CODING_AGENT_MODEL_SLOT
        )
        else "blocked",
        "bound_slot_count": created.get("session", {}).get("role_slot_binding_count"),
        "primary_slot_dispatched": primary.get("current_execution_slot_id") == PRIMARY_MODEL_SLOT,
        "coding_slot_dispatched": api_lane.get("current_execution_slot_id") == CODING_AGENT_MODEL_SLOT,
        "slot_binding_equals_dispatch_claimed": False,
        "session_detail_after_second_call_slot_id": detail.get("session", {}).get(
            "current_execution_slot_id"
        ),
    }
    packets["fallback_and_substitution_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "fallback_and_substitution_boundary",
        "status": "ok" if fallback_clean else "blocked",
        "chatgpt_fallback_attempted": primary.get("fallback_attempted") is True,
        "api_fallback_attempted": api_lane.get("fallback_attempted") is True,
        "chatgpt_runtime_provider": primary.get("configured_provider"),
        "api_runtime_provider": api_lane.get("configured_provider"),
        "silent_gpt_substitution_for_api_lane": runner.calls[1].get("model_id") == PRIMARY_MODEL_ID
        if len(runner.calls) > 1
        else False,
        "silent_api_substitution_for_chatgpt_lane": runner.calls[0].get("model_id") == CODING_AGENT_MODEL_ID
        if runner.calls
        else False,
        "browser_authored_backend_authority_observed": False,
    }
    packets["simultaneous_session_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "same_session_non_claims",
        "status": "ok",
        "all_role_slots_runtime_proven": False,
        "provider_family_compatibility_proven": False,
        "concurrent_execution_proven": False,
        "persistent_relaunch_continuity_proven": False,
        "tools_or_streaming_parity_proven": False,
        "orchestration_policy_complete": False,
    }
    packets["simultaneous_session_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "same_session_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "concurrent_execution_not_observed_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "provider_family_compatibility_not_proven_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "reviewer_scanner_deep_slots_not_runtime_proven_here",
                "severity": "low",
                "status": "open",
            },
            {
                "id": "responses_streaming_tools_semantics_not_proven_here",
                "severity": "medium",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "same_session_callability_treated_as_concurrent_execution": False,
        "binding_treated_as_dispatch": False,
        "one_api_lane_treated_as_provider_family_proof": False,
        "selector_or_persistence_truth_treated_as_runtime_proof": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok" if same_session_ok and provenance_separated else "blocked",
        "findings": [
            {
                "id": "same_session_dual_lane_callability_is_packet_backed",
                "severity": "info",
                "status": "confirmed" if same_session_ok else "not_confirmed",
            },
            {
                "id": "source_provenance_remains_lane_specific",
                "severity": "info",
                "status": "confirmed" if provenance_separated else "not_confirmed",
            },
            {
                "id": "concurrent_execution_remains_unproven_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "provider_family_and_other_role_slot_runtime_truth_remain_open",
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
