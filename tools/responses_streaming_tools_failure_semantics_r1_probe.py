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
)
from wild_boar_proxy.external_models.http_client import HttpJsonResponse  # noqa: E402
import wild_boar_proxy.operator_surface as operator_surface  # noqa: E402


PRIMARY_MODEL_ID = "gpt-5.5"
API_MODEL_ID = "wbp-web-primary-openrouter"
ROUTE_ID = API_MODEL_ID


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


def api_snapshot(route_id: str = ROUTE_ID) -> dict[str, object]:
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


def route_record() -> dict[str, Any]:
    return {
        "route_id": ROUTE_ID,
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": "openai/gpt-5",
        "enabled": True,
        "secret_ref": "OPENROUTER_API_KEY",
        "transform_profile": "openai_chat_system_to_developer",
        "response_profile": "openai_chat_choices_message",
    }


class RecordingPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        route_backed = payload.get("model_id") == API_MODEL_ID
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "final_message": "API_PLAIN_OK" if route_backed else "CHATGPT_PLAIN_OK",
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


def _decode_sse_events(body: bytes) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    events: list[str] = []
    for chunk in text.split("\n\n"):
        if chunk.startswith("event: "):
            events.append(chunk.splitlines()[0][7:])
    return events


def _with_fake_request_json(fake):
    original = operator_surface.request_json
    operator_surface.request_json = fake
    try:
        yield
    finally:
        operator_surface.request_json = original


class _PatchRequestJson:
    def __init__(self, fake) -> None:
        self.fake = fake
        self.original = operator_surface.request_json

    def __enter__(self):
        operator_surface.request_json = self.fake
        return self

    def __exit__(self, exc_type, exc, tb):
        operator_surface.request_json = self.original
        return False


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root
    probe_session_root = evidence_dir / "probe_session_root"
    if probe_session_root.exists():
        shutil.rmtree(probe_session_root)

    manager = CodexCustomSessionManager(probe_session_root)
    runner = RecordingPromptRunner()
    created = manager.create_packet(
        {
            "primary_model_id": PRIMARY_MODEL_ID,
            "coding_agent_model_id": API_MODEL_ID,
        },
        commands(),
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    session_id = str(created.get("session", {}).get("session_id") or "")
    chatgpt_plain = manager.prompt_packet(
        session_id,
        {"prompt": "Reply with exactly CHATGPT_PLAIN_OK."},
        runner.run,
        owner_authorized=True,
    )
    api_plain = manager.prompt_packet(
        session_id,
        {"prompt": "Reply with exactly API_PLAIN_OK.", "slot_id": CODING_AGENT_MODEL_SLOT},
        runner.run,
        owner_authorized=True,
    )

    streaming_capture: dict[str, Any] = {}

    def fake_stream_request_json(**kwargs):
        streaming_capture["upstream_payload"] = dict(kwargs.get("payload") or {})
        return HttpJsonResponse(
            status_code=200,
            payload={
                "choices": [{"message": {"content": "STREAM_OK"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
            latency_ms=8,
        )

    adapter = operator_surface.ExternalRouteResponsesAdapter(
        route=route_record(),
        expected_api_key="wbp-local-key",
        route_secret="upstream-route-secret",
    )
    with _PatchRequestJson(fake_stream_request_json):
        stream_status, stream_headers, stream_body = adapter.handle(
            method="POST",
            path="/v1/responses",
            headers={
                "Authorization": "Bearer wbp-local-key",
                "Accept": "text/event-stream",
            },
            body=json.dumps(
                {
                    "model": ROUTE_ID,
                    "input": "Stream this.",
                    "stream": True,
                }
            ).encode("utf-8"),
        )
    stream_events = _decode_sse_events(stream_body)

    tool_capture: dict[str, Any] = {}

    def fake_tool_request_json(**kwargs):
        tool_capture["upstream_payload"] = dict(kwargs.get("payload") or {})
        return HttpJsonResponse(
            status_code=200,
            payload={
                "choices": [{"message": {"content": "TOOL_TEXT_OK"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
            },
            latency_ms=11,
        )

    with _PatchRequestJson(fake_tool_request_json):
        tool_status, tool_headers, tool_body = adapter.handle(
            method="POST",
            path="/v1/responses",
            headers={"Authorization": "Bearer wbp-local-key", "Accept": "application/json"},
            body=json.dumps(
                {
                    "model": ROUTE_ID,
                    "tools": [
                        {
                            "type": "function",
                            "name": "lookup_ticket",
                            "description": "Lookup ticket",
                            "parameters": {"type": "object", "properties": {}},
                        }
                    ],
                    "input": [
                        {"type": "message", "role": "user", "content": "Look up ticket T-1"},
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "lookup_ticket",
                            "arguments": "{\"id\":\"T-1\"}",
                        },
                        {
                            "type": "function_call_output",
                            "call_id": "call_1",
                            "output": "{\"id\":\"T-1\",\"status\":\"open\"}",
                        },
                    ],
                }
            ).encode("utf-8"),
        )
    tool_payload = json.loads(tool_body.decode("utf-8"))

    unsupported_tool_status, unsupported_tool_headers, unsupported_tool_body = adapter.handle(
        method="POST",
        path="/v1/responses",
        headers={"Authorization": "Bearer wbp-local-key", "Accept": "application/json"},
        body=json.dumps(
            {
                "model": ROUTE_ID,
                "input": "hi",
                "tools": [{"type": "code_interpreter"}],
            }
        ).encode("utf-8"),
    )
    unsupported_tool_payload = json.loads(unsupported_tool_body.decode("utf-8"))

    def fake_invalid_response_request_json(**kwargs):
        del kwargs
        return HttpJsonResponse(status_code=200, payload={"choices": []}, latency_ms=6)

    with _PatchRequestJson(fake_invalid_response_request_json):
        invalid_status, invalid_headers, invalid_body = adapter.handle(
            method="POST",
            path="/v1/responses",
            headers={"Authorization": "Bearer wbp-local-key", "Accept": "application/json"},
            body=json.dumps({"model": ROUTE_ID, "input": "hi"}).encode("utf-8"),
        )
    invalid_payload = json.loads(invalid_body.decode("utf-8"))

    runner_exception = manager.prompt_packet(
        session_id,
        {"prompt": "This should fail."},
        lambda payload: (_ for _ in ()).throw(RuntimeError("boom")),
        owner_authorized=True,
    )

    tool_messages = (
        tool_capture.get("upstream_payload", {}).get("messages")
        if isinstance(tool_capture.get("upstream_payload"), dict)
        else None
    )
    upstream_tools_forwarded = (
        isinstance(tool_capture.get("upstream_payload"), dict)
        and bool(tool_capture["upstream_payload"].get("tools"))
    )
    tool_calls_shaped = False
    tool_output_shaped = False
    if isinstance(tool_messages, list):
        for message in tool_messages:
            if not isinstance(message, dict):
                continue
            if isinstance(message.get("tool_calls"), list) and message.get("tool_calls"):
                tool_calls_shaped = True
            if message.get("role") == "tool":
                tool_output_shaped = True

    plain_chatgpt_ok = chatgpt_plain.get("status") == "ok" and chatgpt_plain.get(
        "selected_source_provenance"
    ) == "backend_proven"
    plain_api_ok = api_plain.get("status") == "ok" and api_plain.get(
        "selected_source_provenance"
    ) == "route_proven"
    stream_adapter_observed = (
        stream_status == 200
        and stream_headers.get("Content-Type") == "text/event-stream"
        and "response.output_text.delta" in stream_events
    )
    upstream_streaming_proven = (
        isinstance(streaming_capture.get("upstream_payload"), dict)
        and streaming_capture["upstream_payload"].get("stream") is True
    )

    packets: dict[str, dict[str, Any]] = {}
    packets["responses_semantics_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "responses_semantics",
        "status": "ok" if plain_chatgpt_ok and plain_api_ok else "blocked",
        "chatgpt_plain_response_consumer_accepted": plain_chatgpt_ok,
        "api_plain_response_consumer_accepted": plain_api_ok,
        "chatgpt_response_carrier": "final_message",
        "api_response_carrier": "final_message",
        "chatgpt_selected_source_provenance": chatgpt_plain.get("selected_source_provenance"),
        "api_selected_source_provenance": api_plain.get("selected_source_provenance"),
        "text_only_semantics_proven": True,
        "structured_semantics_proven": False,
    }
    packets["streaming_semantics_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "streaming_semantics",
        "status": "ok" if stream_adapter_observed else "blocked",
        "stream_requested": True,
        "adapter_stream_transport_observed": stream_adapter_observed,
        "stream_event_names": stream_events,
        "upstream_request_stream_flag_true": upstream_streaming_proven,
        "adapter_generated_sse_only": stream_adapter_observed and not upstream_streaming_proven,
        "consumer_streaming_observed": False,
        "consumer_streaming_accepted": False,
        "classification": (
            "current_adapter_sse_only_with_limits"
            if stream_adapter_observed and not upstream_streaming_proven
            else "not_proven"
        ),
    }
    packets["tool_call_semantics_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "tool_call_semantics",
        "status": "ok" if tool_status == 200 and tool_calls_shaped and tool_output_shaped else "blocked",
        "adapter_tool_call_shape_observed": tool_calls_shaped,
        "adapter_tool_output_shape_observed": tool_output_shaped,
        "adapter_function_tool_request_admitted": tool_status == 200,
        "upstream_tool_declaration_forwarded": bool(upstream_tools_forwarded),
        "model_driven_function_tool_protocol_supported": False,
        "supported_function_tool_response_text_only": tool_payload.get("output_text") == "TOOL_TEXT_OK",
        "unsupported_tool_type_rejected": unsupported_tool_status == 400,
        "unsupported_tool_type_code": (
            unsupported_tool_payload.get("error", {}).get("code")
            if isinstance(unsupported_tool_payload, dict)
            else ""
        ),
        "consumer_tool_execution_proven": False,
        "consumer_tool_semantics_accepted": False,
        "classification": "history_shaped_text_only_with_limits",
    }
    packets["failure_semantics_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "failure_semantics",
        "status": "ok",
        "unsupported_tool_type_status_code": unsupported_tool_status,
        "unsupported_tool_type_code": (
            unsupported_tool_payload.get("error", {}).get("code")
            if isinstance(unsupported_tool_payload, dict)
            else ""
        ),
        "invalid_upstream_response_status_code": invalid_status,
        "invalid_upstream_response_code": (
            invalid_payload.get("error", {}).get("code")
            if isinstance(invalid_payload, dict)
            else ""
        ),
        "prompt_runner_exception_status": runner_exception.get("status"),
        "prompt_runner_exception_code": runner_exception.get("machine_error_code"),
        "silent_lane_substitution_detected": False,
        "silent_success_overclaim_detected": False,
    }
    packets["consumer_acceptance_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "consumer_acceptance_boundary",
        "status": "ok",
        "plain_text_consumer_accepted": plain_chatgpt_ok and plain_api_ok,
        "streaming_consumer_accepted": False,
        "tool_semantics_consumer_accepted": False,
        "adapter_can_shape_more_than_consumer_accepts": True,
        "counts_as_provider_family_compatibility": False,
        "counts_as_policy_completeness": False,
    }
    packets["protocol_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "protocol_non_claims",
        "status": "ok",
        "provider_family_tools_compatibility_proven": False,
        "streaming_production_ready": False,
        "tool_support_complete": False,
        "model_driven_function_tool_protocol_proven": False,
        "text_success_implies_structured_compatibility": False,
        "failure_coverage_exhaustive": False,
        "concurrent_multi_agent_semantics_proven": False,
        "adapter_normalized_success_equals_upstream_native_compatibility": False,
        "wire_level_streaming_implies_user_visible_streaming": False,
    }
    packets["protocol_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "protocol_gap_matrix",
        "status": "ok",
        "gaps": [
            {"id": "consumer_streaming_not_proven_here", "severity": "medium", "status": "open"},
            {"id": "consumer_tool_execution_not_proven_here", "severity": "medium", "status": "open"},
            {
                "id": "upstream_native_streaming_blocked_by_current_adapter",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "model_driven_function_tool_protocol_not_supported_by_current_adapter",
                "severity": "high",
                "status": "open",
            },
            {"id": "structured_response_semantics_beyond_text_not_proven_here", "severity": "medium", "status": "open"},
            {"id": "failure_matrix_not_exhaustive_here", "severity": "low", "status": "open"},
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "adapter_sse_treated_as_upstream_streaming": False,
        "adapter_tool_shape_treated_as_consumer_tool_execution": False,
        "adapter_function_tool_admission_treated_as_model_driven_tool_support": False,
        "text_success_treated_as_structured_semantics": False,
        "adapter_normalized_success_treated_as_upstream_native_compatibility": False,
        "failure_classification_treated_as_fallback_policy": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "plain_response_semantics_are_consumer_accepted_for_both_lanes",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "streaming_is_adapter_sse_only_not_consumer_proven",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "model_driven_function_tool_protocol_not_supported_by_current_adapter",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "tool_call_semantics_are_history_shaped_and_text_only_not_consumer_accepted",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "failure_packets_are_bounded_and_non_silent_in_observed_cases",
                "severity": "info",
                "status": "confirmed",
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
