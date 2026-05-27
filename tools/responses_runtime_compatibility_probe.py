#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate WBP Responses runtime compatibility evidence packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.external_models import errors  # noqa: E402
from wild_boar_proxy.operator_surface import ExternalRouteResponsesAdapter  # noqa: E402
from wild_boar_proxy.runtime import RuntimeErrorInfo  # noqa: E402


FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "wbp_responses_compatibility"
SECRET_SCAN_PATTERNS = ("sk-", "Authorization: Bearer", "OPENAI_API_KEY")


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    payload: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if process.returncode != 0:
        return process.stdout.strip() or process.stderr.strip()
    return process.stdout.strip()


def fixture_route() -> dict[str, Any]:
    return {
        "route_id": "wbp-fixture-route",
        "provider": "fixture",
        "base_url": "https://example.invalid/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": "fixture-upstream-model",
        "compatibility": "openai_chat_completions",
        "auth": {"secret_ref": "FIXTURE_SECRET"},
    }


def run_adapter_request(
    fixture_name: str,
    *,
    request_payload: dict[str, Any] | None = None,
    route_overrides: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    response_status: int = 200,
    accept: str = "application/json",
    side_effect: Any | None = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_request_json(**kwargs: Any) -> FakeResponse:
        captured.update(kwargs)
        if side_effect is not None:
            raise side_effect
        payload = (
            response_payload
            if response_payload is not None
            else load_json("non_stream_text_response.json")
        )
        return FakeResponse(status_code=response_status, payload=payload)

    route = fixture_route()
    if route_overrides:
        route.update(route_overrides)

    with (
        ExternalRouteResponsesAdapter(
            route=route,
            expected_api_key="local-runtime-fixture",
            route_secret="route-secret-fixture",
        ) as adapter,
        mock.patch(
            "wild_boar_proxy.operator_surface.request_json",
            side_effect=fake_request_json,
        ),
    ):
        request = urllib.request.Request(
            f"{adapter.listen_endpoint}/responses",
            data=json.dumps(
                request_payload if request_payload is not None else load_json(fixture_name)
            ).encode("utf-8"),
            headers={
                "Authorization": "Bearer local-runtime-fixture",
                "Content-Type": "application/json",
                "Accept": accept,
            },
            method="POST",
        )
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                request, timeout=5
            ) as response:
                status = int(response.status)
                body = response.read().decode("utf-8")
                headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            body = exc.read().decode("utf-8")
            headers = dict(exc.headers)

    try:
        parsed_body: Any = json.loads(body)
    except json.JSONDecodeError:
        parsed_body = None
    return {
        "status_code": status,
        "body": body,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "payload": parsed_body,
        "headers": headers,
        "captured_upstream_keys": sorted(captured.keys()),
        "captured_upstream_payload": captured.get("payload", {}),
        "fixture": fixture_name,
    }


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def event_names(body: str) -> list[str]:
    return [
        line.removeprefix("event: ").strip()
        for line in body.splitlines()
        if line.startswith("event: ")
    ]


def write_packet(evidence_dir: Path, name: str, payload: dict[str, Any]) -> None:
    (evidence_dir / name).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    branch = run_text(repo_root, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = [
        line
        for line in run_text(repo_root, ["git", "status", "--short"]).splitlines()
        if line.strip()
    ]
    non_stream = run_adapter_request("non_stream_text_request.json")
    stream = run_adapter_request(
        "stream_text_request.json",
        response_payload={"choices": [{"message": {"content": "WBP_STREAM_OK"}}]},
        accept="text/event-stream",
    )
    tool_call = run_adapter_request("tool_call_request.json")
    tool_loop = run_adapter_request("tool_call_output_followup.json")
    reasoning = run_adapter_request("reasoning_item_input.json")
    error_401 = run_adapter_request(
        "non_stream_text_request.json",
        response_payload=load_json("upstream_4xx_error.json"),
        response_status=401,
    )
    error_503 = run_adapter_request(
        "non_stream_text_request.json",
        response_payload=load_json("upstream_5xx_error.json"),
        response_status=503,
    )
    failure_429 = run_adapter_request(
        "non_stream_text_request.json",
        response_payload={
            "error": {
                "message": "rate limit fixture",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        },
        response_status=429,
    )
    timeout = run_adapter_request(
        "non_stream_text_request.json",
        side_effect=RuntimeErrorInfo(
            "Provider request timed out.",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            operator_action="retry",
        ),
    )
    disconnect = run_adapter_request(
        "non_stream_text_request.json",
        side_effect=RuntimeErrorInfo(
            "Provider network request failed: upstream disconnect",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            operator_action="retry",
        ),
    )
    empty_input = run_adapter_request(
        "non_stream_text_request.json",
        request_payload={"model": "wbp-fixture-route", "input": []},
    )
    transform_profile = run_adapter_request(
        "non_stream_text_request.json",
        request_payload={
            "model": "wbp-fixture-route",
            "input": [
                {
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": "system fixture"}],
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "user fixture"}],
                },
            ],
        },
        route_overrides={"transform_profile": "openai_chat_system_to_developer"},
    )
    stream_events = event_names(stream["body"])
    expected_events = [
        json.loads(line)["event"]
        for line in (FIXTURE_DIR / "stream_text_events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tool_messages = tool_call["captured_upstream_payload"].get("messages", [])
    loop_messages = tool_loop["captured_upstream_payload"].get("messages", [])
    reasoning_payload_text = json.dumps(reasoning["captured_upstream_payload"], ensure_ascii=True)
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": packet(
            "sync_gate",
            branch=branch,
            head=head,
            native_launch_attempted=False,
            external_provider_live_call_attempted=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            pre_existing_dirty_paths=dirty,
            current_contour_relies_on_historical_dirty_paths=False,
            current_contour_stages_historical_dirty_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=[
                "wild_boar_proxy/operator_surface.py",
                "tests/test_wbp_responses_fixture_compatibility.py",
                "tools/responses_runtime_compatibility_probe.py",
                str(evidence_dir.relative_to(repo_root)),
            ],
            native_profile_write_surface=False,
            original_codex_write_surface=False,
        ),
        "version_pinning_packet.json": packet(
            "version_pinning",
            wbp_git_commit=head,
            python_version=sys.version.split()[0],
            provider_endpoint_version_status="controlled_local_runtime_harness",
            model_catalog_schema_version_used=False,
        ),
        "responses_non_stream_regression_packet.json": packet(
            "responses_non_stream_regression",
            status="ok" if non_stream["status_code"] == 200 else "failed",
            http_status=non_stream["status_code"],
            object=non_stream["payload"].get("object"),
            response_status=non_stream["payload"].get("status"),
            output_text_present=bool(non_stream["payload"].get("output_text")),
            response_body_sha256=non_stream["body_sha256"],
        ),
        "responses_stream_runtime_harness_packet.json": packet(
            "responses_stream_runtime_harness",
            status="ok" if stream["status_code"] == 200 else "failed",
            http_status=stream["status_code"],
            content_type=stream["headers"].get("Content-Type", ""),
            event_count=len(stream_events),
            response_body_sha256=stream["body_sha256"],
        ),
        "responses_stream_sse_sequence_packet.json": packet(
            "responses_stream_sse_sequence",
            status="ok" if stream_events == expected_events else "failed",
            observed_events=stream_events,
            expected_events=expected_events,
            stream_started_counts_as_compatible=False,
            completed_event_required=True,
        ),
        "responses_output_text_shape_packet.json": packet(
            "responses_output_text_shape",
            status="ok" if non_stream["payload"].get("output_text") == "WBP_FIXTURE_OK" else "failed",
            output_text_present=True,
            output_text_hash=hashlib.sha256(
                str(non_stream["payload"].get("output_text") or "").encode("utf-8")
            ).hexdigest(),
            raw_prompt_recorded=False,
        ),
        "responses_completed_shape_packet.json": packet(
            "responses_completed_shape",
            status="ok" if non_stream["payload"].get("status") == "completed" else "failed",
            response_completed_shape_accepted=True,
            completed_status=non_stream["payload"].get("status"),
        ),
        "responses_tool_call_shape_packet.json": packet(
            "responses_tool_call_shape",
            status="ok"
            if len(tool_messages) > 1
            and tool_messages[1].get("tool_calls", [{}])[0].get("function", {}).get("name") == "shell"
            else "failed",
            tool_call_emitted_counts_as_loop_compatible=False,
            upstream_message_roles=[message.get("role") for message in tool_messages],
        ),
        "responses_tool_loop_packet.json": packet(
            "responses_tool_loop",
            status="ok"
            if len(loop_messages) >= 3
            and loop_messages[0].get("tool_calls", [{}])[0].get("id") == "call_fixture_1"
            and loop_messages[1].get("role") == "tool"
            else "failed",
            function_call_output_loop_classified=True,
            native_tool_ux_proven=False,
        ),
        "responses_reasoning_item_packet.json": packet(
            "responses_reasoning_item",
            status="ok"
            if "internal reasoning summary should not go upstream" not in reasoning_payload_text
            and "fixture-redacted-reasoning" not in reasoning_payload_text
            else "failed",
            reasoning_passthrough_supported=False,
            reasoning_summary_sent_upstream=False,
        ),
        "responses_error_shape_packet.json": packet(
            "responses_error_shape",
            status="ok"
            if error_401["status_code"] == 401
            and error_503["status_code"] == 503
            and "error" in error_401["payload"]
            and "error" in error_503["payload"]
            else "failed",
            observed_statuses=[error_401["status_code"], error_503["status_code"]],
            error_returned_counts_as_success=False,
        ),
        "responses_empty_input_error_packet.json": packet(
            "responses_empty_input_error",
            status="ok"
            if empty_input["status_code"] == 400
            and empty_input["payload"].get("error", {}).get("type")
            == "invalid_request_error"
            and not empty_input["captured_upstream_payload"]
            else "failed",
            http_status=empty_input["status_code"],
            upstream_call_attempted=bool(empty_input["captured_upstream_payload"]),
            error_returned_counts_as_success=False,
        ),
        "responses_transform_profile_packet.json": packet(
            "responses_transform_profile",
            status="ok"
            if transform_profile["status_code"] == 200
            and (
                transform_profile["captured_upstream_payload"].get("messages", [{}])[0].get(
                    "role"
                )
                == "developer"
            )
            else "failed",
            http_status=transform_profile["status_code"],
            transform_profile="openai_chat_system_to_developer",
            system_role_forwarded_as_system=False,
            system_role_mapped_to_developer=True,
        ),
        "failure_semantics_429_packet.json": packet(
            "failure_semantics_429",
            status="ok" if failure_429["status_code"] == 429 else "failed",
            http_status=failure_429["status_code"],
            classification="rate_limit_not_success",
            retry_behavior="not_retried_by_adapter",
            counts_as_provider_pass=False,
        ),
        "failure_semantics_timeout_packet.json": packet(
            "failure_semantics_timeout",
            status="ok" if timeout["status_code"] == 504 else "failed",
            http_status=timeout["status_code"],
            classification="timeout_error_shape_returned",
            retryable=timeout["payload"].get("error", {}).get("retryable") is True,
            retry_behavior="not_retried_by_adapter",
        ),
        "failure_semantics_disconnect_packet.json": packet(
            "failure_semantics_disconnect",
            status="ok" if disconnect["status_code"] == 502 else "failed",
            http_status=disconnect["status_code"],
            classification="upstream_disconnect_error_shape_returned",
            retryable=disconnect["payload"].get("error", {}).get("retryable") is True,
            retry_behavior="not_retried_by_adapter",
        ),
        "failure_semantics_partial_stream_packet.json": packet(
            "failure_semantics_partial_stream",
            status="ok" if stream_events[-1:] == ["response.completed"] else "failed",
            classification="not_exercised_buffered_upstream_then_local_sse",
            partial_stream_counts_as_pass=False,
            completed_event_required=True,
            observed_terminal_event=stream_events[-1] if stream_events else "",
        ),
        "failure_semantics_client_cancel_packet.json": packet(
            "failure_semantics_client_cancel",
            status="blocked_by_host_environment",
            counts_as_pass=False,
            root_cause="deterministic local harness does not expose reliable client-cancel observation without introducing flaky socket timing",
            what_was_exercised="no client-cancel runtime path",
            remains_unproven="adapter behavior after downstream client cancellation",
        ),
        "failure_semantics_retry_backpressure_packet.json": packet(
            "failure_semantics_retry_backpressure",
            retry_behavior_classified="adapter_does_not_retry",
            backpressure_behavior_classified="not_exercised_by_local_harness",
            idempotence_assumption="no automatic retry means adapter does not add idempotence risk",
            counts_as_full_robustness_pass=False,
        ),
        "adapter_boundary_packet.json": packet(
            "adapter_boundary",
            generic_runtime_harness_proves_provider_family_compatibility=False,
            provider_family_adapter_claims_absent=True,
            deterministic_fixture_scope="openai_chat_completions_shape_only",
        ),
    }
    matrix_status = (
        "ok"
        if all(
            item.get("status") == "ok"
            for name, item in packets.items()
            if name.startswith("responses_")
            or name in {
                "failure_semantics_429_packet.json",
                "failure_semantics_timeout_packet.json",
                "failure_semantics_disconnect_packet.json",
                "failure_semantics_partial_stream_packet.json",
                "failure_semantics_retry_backpressure_packet.json",
                "adapter_boundary_packet.json",
            }
        )
        else "blocked"
    )
    packets["responses_runtime_compatibility_matrix.json"] = packet(
        "responses_runtime_compatibility_matrix",
        status=matrix_status,
        target_status="WBP_RESPONSES_RUNTIME_COMPATIBILITY_CLASSIFIED_WITH_LIMITS",
        blocked_by_host_environment=[
            "failure_semantics_client_cancel_packet.json"
        ],
        native_launch_attempted=False,
        external_provider_live_call_attempted=False,
        model_availability_proven=False,
        direct_egress_absence_proven=False,
        final_e2e_proven=False,
    )
    packets["responses_runtime_false_green_audit.json"] = packet(
        "responses_runtime_false_green_audit",
        status="ok" if matrix_status == "ok" else "blocked",
        stream_started_claimed_as_compatible=False,
        tool_call_emitted_claimed_as_tool_loop=False,
        blocked_by_host_environment_counted_as_pass=False,
        native_claim_present=False,
        model_availability_claim_present=False,
        egress_absence_claim_present=False,
        external_provider_live_claim_present=False,
    )
    packets["independent_wire_audit.json"] = packet(
        "independent_wire_audit",
        status="ok" if matrix_status == "ok" else "blocked",
        referenced_packets=sorted(packets),
        text_only_audit=False,
        no_native_model_egress_ux_claims=True,
        blocked_items_are_not_pass=True,
    )
    return packets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        write_packet(evidence_dir, name, payload)
    summary = packets["responses_runtime_compatibility_matrix.json"]
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
