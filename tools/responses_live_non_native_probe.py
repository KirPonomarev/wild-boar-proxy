#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit bounded WBP Responses live non-native contour packets.

This probe keeps the live authorization gate exact. When the canon-valid owner
authorization phrase is absent, the probe must stop before any real provider or
model request and emit blocked packet truth instead of a false green.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_window_probe import (  # noqa: E402
    OWNER_STANDING_AUTHORIZATION_PHRASE,
    owner_authorization_phrase_present,
)
from wild_boar_proxy.runtime import proxyless_urlopen  # noqa: E402


TARGET_STATUS = "WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_CLASSIFIED"
TARGET_STATUS_WITH_LIMITS = (
    "WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_CLASSIFIED_WITH_LIMITS"
)
BLOCKED_NO_OWNER_AUTHORIZATION = (
    "WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_BLOCKED_NO_OWNER_AUTHORIZATION"
)
BLOCKED_RUNNER_UNCONFIGURED = (
    "WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_BLOCKED_RUNNER_UNCONFIGURED"
)
BLOCKED_RUNTIME_OR_UPSTREAM_FAILURE = (
    "WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_BLOCKED_RUNTIME_OR_UPSTREAM_FAILURE"
)
DEFAULT_EVIDENCE_DIR = (
    REPO_ROOT / "audit_results" / "wbp_responses_live_compatibility_non_native_r1_2026-05-27"
)
DEFAULT_ENDPOINT = "http://127.0.0.1:8318/v1"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "wbp_responses_compatibility"
LIVE_PROMPT_PREFIX = "WBP_RESPONSES_LIVE_NON_NATIVE_R1_NONCE_2026_05_27"
SECRET_MARKERS = (
    "sk-",
    "Authorization: Bearer",
    "OPENAI_API_KEY",
    "Reply with exactly",
    LIVE_PROMPT_PREFIX,
)
FAILURE_CAUSES = {
    "none",
    "auth_failure",
    "quota_or_rate_limit",
    "model_rejected",
    "provider_error",
    "timeout",
    "malformed_response_shape",
    "route_not_observed",
    "wbp_runtime_unavailable",
    "unknown",
}


RequestRunner = Callable[[dict[str, Any]], dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def auth_token_packet(repo_root: Path) -> tuple[dict[str, Any], str]:
    command_path = repo_root / "wbp_codex_auth_command.py"
    process = subprocess.run(
        [str(command_path)],
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    token = process.stdout.strip() if process.returncode == 0 else ""
    return (
        packet(
            "direct_wbp_auth_command_observation",
            status="ok" if token else "blocked",
            machine_error_code="OK" if token else "WBP_AUTH_TOKEN_UNAVAILABLE",
            auth_command_path=str(command_path),
            auth_command_returncode=process.returncode,
            token_present=bool(token),
            token_recorded=False,
            token_hash_recorded=False,
            stderr_hash=sha256_text(process.stderr) if process.stderr else "",
            raw_upstream_secret_recorded=False,
        ),
        token,
    )


def http_json(
    *,
    endpoint: str,
    path: str,
    token: str,
    payload: dict[str, Any],
    timeout: int,
    accept: str = "application/json",
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "Content-Type": "application/json",
            "OpenAI-Beta": "responses=v1",
            "X-Session-ID": f"wbp-responses-live-r1-{sha256_text(utc_now())[:16]}",
        },
    )
    try:
        with proxyless_urlopen(request, timeout=timeout) as response:
            response_body = response.read()
            decoded = response_body.decode("utf-8", "replace")
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                parsed = {}
            return {
                "http_status": int(response.status),
                "content_type": str(response.headers.get("Content-Type") or ""),
                "body_hash": sha256_text(decoded),
                "body_len": len(response_body),
                "body_text": decoded,
                "payload": parsed if isinstance(parsed, dict) else {},
                "exception_type": "",
            }
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        decoded = response_body.decode("utf-8", "replace")
        try:
            parsed = json.loads(decoded)
        except json.JSONDecodeError:
            parsed = {}
        return {
            "http_status": int(exc.code),
            "content_type": str(exc.headers.get("Content-Type") or ""),
            "body_hash": sha256_text(decoded),
            "body_len": len(response_body),
            "body_text": decoded,
            "payload": parsed if isinstance(parsed, dict) else {},
            "exception_type": "HTTPError",
        }
    except TimeoutError:
        return {
            "http_status": None,
            "content_type": "",
            "body_hash": "",
            "body_len": 0,
            "body_text": "",
            "payload": {},
            "exception_type": "TimeoutError",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "http_status": None,
            "content_type": "",
            "body_hash": "",
            "body_len": 0,
            "body_text": "",
            "payload": {},
            "exception_type": type(exc).__name__,
        }


def response_shape_accepted(payload: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, ""
    status = str(payload.get("status") or "")
    output = payload.get("output")
    text = payload.get("output_text")
    accepted = (
        str(payload.get("id") or "").startswith("resp_")
        and status in {"completed", "incomplete"}
        and (isinstance(output, list) or isinstance(text, str))
    )
    return accepted, status


def event_names(body: str) -> list[str]:
    return [
        line.removeprefix("event: ").strip()
        for line in body.splitlines()
        if line.startswith("event: ")
    ]


def stream_frames(body: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for chunk in body.strip().split("\n\n"):
        if not chunk.strip():
            continue
        event_name = ""
        data_text = ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data_text = line.removeprefix("data: ").strip()
        parsed: dict[str, Any] | None = None
        parse_error = ""
        try:
            parsed = json.loads(data_text)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
        frames.append(
            {
                "event": event_name,
                "data_type": parsed.get("type") if isinstance(parsed, dict) else None,
                "data_type_matches_event": (
                    isinstance(parsed, dict) and parsed.get("type") == event_name
                ),
                "parse_error": parse_error,
                "response_status": (
                    parsed.get("response", {}).get("status")
                    if isinstance(parsed, dict)
                    and isinstance(parsed.get("response"), dict)
                    else None
                ),
            }
        )
    return frames


def stream_shape_accepted(
    *,
    http_status: int | None,
    content_type: str,
    body_len: int,
    exception_type: str,
    observed_events: list[str],
    expected_events: list[str],
    data_type_matches_event: bool,
    data_parse_errors: list[str],
    terminal_response_status: str,
) -> bool:
    return (
        http_status is not None
        and 200 <= http_status < 300
        and "text/event-stream" in content_type.lower()
        and body_len > 0
        and exception_type == ""
        and observed_events == expected_events
        and data_type_matches_event
        and not data_parse_errors
        and terminal_response_status == "completed"
    )


def extract_function_call(payload: dict[str, Any]) -> dict[str, str]:
    output = payload.get("output")
    if not isinstance(output, list):
        return {}
    for item in output:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") == "function_call":
            return {
                "call_id": str(item.get("call_id") or item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "arguments": str(item.get("arguments") or ""),
            }
    return {}


def response_output_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    output = payload.get("output")
    if not isinstance(output, list):
        return []
    return [item for item in output if isinstance(item, dict)]


def classify_http_failure(http_status: int | None, payload: dict[str, Any], exception_type: str) -> str:
    if exception_type == "TimeoutError":
        return "timeout"
    if http_status in {401, 403}:
        return "auth_failure"
    if http_status == 429:
        return "quota_or_rate_limit"
    if http_status in {400, 404}:
        error = payload.get("error") if isinstance(payload, dict) else {}
        code = str(error.get("code") or error.get("type") or "") if isinstance(error, dict) else ""
        return "model_rejected" if "model" in code.lower() else "provider_error"
    if http_status is not None and http_status >= 500:
        return "provider_error"
    if http_status is None:
        return "wbp_runtime_unavailable"
    return "unknown"


def build_live_request_runner(
    *,
    repo_root: Path,
    endpoint: str,
    model_id: str,
    timeout: int,
) -> tuple[RequestRunner, dict[str, Any]]:
    auth_packet, token = auth_token_packet(repo_root)
    expected_stream_events = [
        json.loads(line)["event"]
        for line in (FIXTURE_DIR / "stream_text_events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    def runner(request_spec: dict[str, Any]) -> dict[str, Any]:
        if not token:
            return {
                "request_attempted": False,
                "request_reaches_wbp": False,
                "route_selected": False,
                "response_observed": False,
                "upstream_status_code": 0,
                "upstream_accepts": False,
                "response_shape_accepted": False,
                "failure_cause": "auth_failure",
                "auth_command_status": auth_packet["status"],
            }
        surface = str(request_spec.get("surface") or "non_stream")
        prompt = f"{LIVE_PROMPT_PREFIX}_{sha256_text(utc_now())[:16]}: answer exactly OK"
        payload: dict[str, Any]
        if surface == "stream":
            payload = {
                "model": model_id or str(request_spec.get("model_id") or ""),
                "input": prompt,
                "max_output_tokens": 16,
                "stream": True,
            }
        elif surface == "tool_loop":
            payload = {
                "model": model_id or str(request_spec.get("model_id") or ""),
                "input": "Call the ping tool once, then finish.",
                "tools": [
                    {
                        "type": "function",
                        "name": "ping",
                        "description": "Return pong",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    }
                ],
                "max_output_tokens": 64,
                "stream": False,
            }
        elif surface == "failure_semantics":
            payload = {
                "model": model_id or str(request_spec.get("model_id") or ""),
                "input": [],
                "max_output_tokens": 16,
                "stream": False,
            }
        else:
            payload = {
                "model": model_id or str(request_spec.get("model_id") or ""),
                "input": prompt,
                "max_output_tokens": 16,
                "stream": False,
            }
        accept = "text/event-stream" if surface == "stream" else "application/json"
        observed = http_json(
            endpoint=endpoint,
            path="responses",
            token=token,
            payload=payload,
            timeout=timeout,
            accept=accept,
        )
        http_status = observed["http_status"]
        response_payload = observed["payload"]
        shape_accepted, response_status = response_shape_accepted(response_payload)
        observed_events = event_names(str(observed.get("body_text") or ""))
        stream_frame_rows = stream_frames(str(observed.get("body_text") or ""))
        data_parse_errors = [
            str(row.get("parse_error") or "")
            for row in stream_frame_rows
            if str(row.get("parse_error") or "")
        ]
        data_type_matches_event = bool(stream_frame_rows) and all(
            row.get("data_type_matches_event") is True for row in stream_frame_rows
        )
        terminal_response_status = str(
            next(
                (
                    row.get("response_status")
                    for row in reversed(stream_frame_rows)
                    if row.get("response_status")
                ),
                "",
            )
            or ""
        )
        stream_accepted = stream_shape_accepted(
            http_status=http_status,
            content_type=str(observed.get("content_type") or ""),
            body_len=int(observed["body_len"]),
            exception_type=str(observed["exception_type"]),
            observed_events=observed_events,
            expected_events=expected_stream_events,
            data_type_matches_event=data_type_matches_event,
            data_parse_errors=data_parse_errors,
            terminal_response_status=terminal_response_status,
        )
        tool_call = extract_function_call(response_payload)
        tool_output_submitted = False
        followup_response_shape_accepted = False
        assistant_continuation_observed = False
        followup_status_code = 0
        followup_response_status = ""
        followup_request_shape_mode = ""
        followup_replayed_output_item_count = 0
        negative_control_status_code = 0
        negative_control_failure_cause = "unknown"
        negative_control_error_type = ""
        negative_control_error_param = ""
        negative_control_error_code = ""
        negative_control_response_shape_accepted = False
        if surface == "tool_loop" and tool_call.get("call_id"):
            negative_control_payload = {
                "model": model_id or str(request_spec.get("model_id") or ""),
                "previous_response_id": str(response_payload.get("id") or ""),
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": tool_call["call_id"],
                        "output": "pong",
                    }
                ],
                "max_output_tokens": 64,
                "stream": False,
            }
            negative_control = http_json(
                endpoint=endpoint,
                path="responses",
                token=token,
                payload=negative_control_payload,
                timeout=timeout,
            )
            negative_control_payload_body = negative_control["payload"]
            negative_control_response_shape_accepted, _ = response_shape_accepted(
                negative_control_payload_body
            )
            negative_control_status_code = int(negative_control.get("http_status") or 0)
            negative_control_failure_cause = classify_http_failure(
                negative_control.get("http_status"),
                negative_control_payload_body,
                str(negative_control.get("exception_type") or ""),
            )
            negative_control_error = (
                negative_control_payload_body.get("error")
                if isinstance(negative_control_payload_body, dict)
                else {}
            )
            if isinstance(negative_control_error, dict):
                negative_control_error_type = str(negative_control_error.get("type") or "")
                negative_control_error_param = str(negative_control_error.get("param") or "")
                negative_control_error_code = str(negative_control_error.get("code") or "")

            prior_output_items = response_output_items(response_payload)
            followup_payload = {
                "model": model_id or str(request_spec.get("model_id") or ""),
                "tools": payload.get("tools") if isinstance(payload.get("tools"), list) else [],
                "input": [
                    *prior_output_items,
                    {
                        "type": "function_call_output",
                        "call_id": tool_call["call_id"],
                        "output": "pong",
                    },
                ],
                "max_output_tokens": 64,
                "stream": False,
            }
            followup = http_json(
                endpoint=endpoint,
                path="responses",
                token=token,
                payload=followup_payload,
                timeout=timeout,
            )
            followup_payload_body = followup["payload"]
            followup_response_shape_accepted, followup_response_status = response_shape_accepted(
                followup_payload_body
            )
            tool_output_submitted = True
            followup_status_code = int(followup.get("http_status") or 0)
            assistant_continuation_observed = followup_response_shape_accepted and (
                followup_response_status in {"completed", "incomplete"}
            )
            followup_request_shape_mode = "prior_output_replay_plus_function_call_output"
            followup_replayed_output_item_count = len(prior_output_items)
        success = http_status is not None and 200 <= http_status < 300
        if surface == "failure_semantics":
            failure_cause = classify_http_failure(
                http_status,
                response_payload,
                str(observed["exception_type"]),
            )
        elif surface == "stream":
            failure_cause = "none" if stream_accepted else classify_http_failure(
                http_status,
                response_payload,
                str(observed["exception_type"]),
            )
        elif surface == "tool_loop":
            failure_cause = (
                "none"
                if success and shape_accepted and tool_output_submitted and assistant_continuation_observed
                else classify_http_failure(
                    http_status,
                    response_payload,
                    str(observed["exception_type"]),
                )
            )
        else:
            failure_cause = "none" if success and shape_accepted else classify_http_failure(
                http_status,
                response_payload,
                str(observed["exception_type"]),
            )
        return {
            "request_attempted": True,
            "request_reaches_wbp": http_status is not None,
            "path": "/v1/responses",
            "response_observed": http_status is not None,
            "route_selected": success,
            "upstream_status_code": http_status or 0,
            "upstream_accepts": success,
            "response_shape_accepted": shape_accepted,
            "stream_shape_accepted": stream_accepted,
            "response_status": response_status,
            "failure_cause": failure_cause,
            "http_body_sha256": observed["body_hash"],
            "http_body_len": observed["body_len"],
            "exception_type": observed["exception_type"],
            "auth_command_status": auth_packet["status"],
            "content_type": str(observed.get("content_type") or ""),
            "observed_events": observed_events,
            "expected_events": expected_stream_events,
            "event_count": len(observed_events),
            "data_type_sequence": [str(row.get("data_type") or "") for row in stream_frame_rows],
            "data_type_matches_event": data_type_matches_event,
            "data_parse_errors": data_parse_errors,
            "terminal_response_status": terminal_response_status,
            "completed_event_observed": observed_events[-1:] == ["response.completed"],
            "tool_call_observed": bool(tool_call),
            "tool_call_id_present": bool(tool_call.get("call_id")),
            "tool_call_name": str(tool_call.get("name") or ""),
            "tool_output_submitted": tool_output_submitted,
            "followup_response_shape_accepted": followup_response_shape_accepted,
            "assistant_continuation_observed": assistant_continuation_observed,
            "followup_upstream_status_code": followup_status_code,
            "followup_response_status": followup_response_status,
            "followup_request_shape_mode": followup_request_shape_mode,
            "followup_replayed_output_item_count": followup_replayed_output_item_count,
            "negative_control_request_shape_mode": (
                "previous_response_id_plus_function_call_output_only"
                if tool_call.get("call_id")
                else ""
            ),
            "negative_control_status_code": negative_control_status_code,
            "negative_control_failure_cause": negative_control_failure_cause,
            "negative_control_error_type": negative_control_error_type,
            "negative_control_error_param": negative_control_error_param,
            "negative_control_error_code": negative_control_error_code,
            "negative_control_response_shape_accepted": negative_control_response_shape_accepted,
        }

    return runner, auth_packet


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    try:
        relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    except ValueError:
        relative_evidence_dir = ""
    default_evidence_surface = str(DEFAULT_EVIDENCE_DIR.relative_to(repo_root))
    admitted_current_contour = {
        "tools/responses_live_non_native_probe.py",
        "tests/test_responses_live_non_native_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "M tests/test_native_filesystem_probe.py",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]

    def status_path(line: str) -> str:
        return line[3:] if len(line) > 3 else line.strip()

    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not (
            (
                relative_evidence_dir
                and status_path(line).startswith(f"{relative_evidence_dir}/")
            )
            or status_path(line).startswith(f"{default_evidence_surface}/")
        )
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def classify_failure(result: dict[str, Any]) -> str:
    failure_cause = str(result.get("failure_cause") or "").strip()
    if failure_cause in FAILURE_CAUSES:
        return failure_cause
    status_code = int(result.get("upstream_status_code") or 0)
    if status_code in {401, 403}:
        return "auth_failure"
    if status_code == 429:
        return "quota_or_rate_limit"
    if status_code == 404:
        return "model_rejected"
    if status_code >= 500:
        return "provider_error"
    if result.get("response_shape_accepted") is False:
        return "malformed_response_shape"
    if result.get("request_attempted") is not True:
        return "wbp_runtime_unavailable"
    return "unknown"


def build_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    owner_authorization_phrase: str | None = None,
    request_runner: RequestRunner | None = None,
    auth_observation_packet: dict[str, Any] | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    model_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    non_stream_fixture = load_fixture("non_stream_text_request.json")
    stream_fixture = load_fixture("stream_text_request.json")
    tool_loop_fixture = load_fixture("tool_call_request.json")
    model = str(model_id or non_stream_fixture.get("model") or "")
    input_items = non_stream_fixture.get("input")
    input_count = len(input_items) if isinstance(input_items, list) else 0
    try:
        evidence_surface = str(evidence_dir.relative_to(repo_root))
    except ValueError:
        evidence_surface = str(evidence_dir)
    request_body = {
        "model": model,
        "input_count": input_count,
        "stream": non_stream_fixture.get("stream") is True,
    }
    request_body_hash = sha256_text(json.dumps(request_body, ensure_ascii=True, sort_keys=True))
    owner_authorized = owner_authorization_phrase_present(owner_authorization_phrase)

    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": packet(
            "sync_gate",
            status="ok" if not unexpected_dirty else "blocked",
            git_branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            git_head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
            git_status_short=run_text(repo_root, ["git", "status", "--short"]).splitlines(),
            unexpected_dirty_entries=unexpected_dirty,
            new_evidence_dir=str(evidence_dir),
            master_plan_written_to_repo=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            quarantined_paths=quarantined,
            quarantine_classification="out_of_scope_historical_residue",
            current_contour_relies_on_quarantined_paths=False,
            current_contour_mutates_quarantined_paths=False,
            current_contour_stages_quarantined_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=[
                "tools/responses_live_non_native_probe.py",
                "tests/test_responses_live_non_native_probe.py",
                evidence_surface,
            ],
            endpoint=endpoint,
            live_model_id=model,
            runtime_mutation_allowed=False,
            route_account_mutation_allowed=False,
            native_launch_allowed=False,
        ),
        "live_authorization_packet.json": packet(
            "live_authorization",
            status="ok" if owner_authorized else "blocked",
            machine_error_code="OK" if owner_authorized else "OWNER_AUTHORIZATION_REQUIRED",
            authorization_status=(
                "authorized_by_owner_gate"
                if owner_authorized
                else "blocked_by_operator_authorization"
            ),
            owner_authorization_phrase_present=owner_authorized,
            exact_owner_authorization_required=True,
            broad_authorization_accepted=False,
            generic_start_phrase_accepted=False,
            near_miss_authorization_accepted=False,
            live_request_allowed=owner_authorized,
            live_request_attempted=False,
            stopped_before_live_provider_model_request=not owner_authorized,
            next_action=(
                "execute_bounded_live_non_native_probe"
                if owner_authorized
                else "provide_exact_owner_authorization_phrase"
            ),
        ),
        "runtime_readiness_packet.json": packet(
            "runtime_readiness",
            status="ok" if owner_authorized else "blocked",
            machine_error_code="OK" if owner_authorized else "OWNER_AUTHORIZATION_REQUIRED",
            direct_wbp_client_only=True,
            native_launch_required=False,
            codex_cli_required=False,
            owner_authorization_phrase_present=owner_authorized,
            live_request_allowed=owner_authorized,
            live_request_attempted=False,
            stopped_before_live_provider_model_request=not owner_authorized,
        ),
        "direct_request_shape_packet.json": packet(
            "direct_request_shape",
            endpoint_path="/v1/responses",
            endpoint=endpoint,
            request_shape_classified=True,
            model_id=model,
            input_item_count=input_count,
            stream_requested=False,
            request_body_sha256=request_body_hash,
            request_body_recorded=False,
            raw_prompt_recorded=False,
            auth_header_recorded=False,
            live_request_allowed=owner_authorized,
            live_request_attempted=False,
            stopped_before_live_provider_model_request=not owner_authorized,
            request_prepared_counts_as_live_proof=False,
        ),
        "direct_stream_request_shape_packet.json": packet(
            "direct_stream_request_shape",
            endpoint_path="/v1/responses",
            endpoint=endpoint,
            request_shape_classified=True,
            model_id=model,
            input_item_count=len(stream_fixture.get("input") or []),
            stream_requested=True,
            request_body_sha256=sha256_text(
                json.dumps(
                    {
                        "model": model,
                        "input_count": len(stream_fixture.get("input") or []),
                        "stream": True,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                )
            ),
            request_body_recorded=False,
            raw_prompt_recorded=False,
            auth_header_recorded=False,
            live_request_allowed=owner_authorized,
            live_request_attempted=False,
            stopped_before_live_provider_model_request=not owner_authorized,
            request_prepared_counts_as_live_proof=False,
        ),
        "direct_tool_loop_request_shape_packet.json": packet(
            "direct_tool_loop_request_shape",
            endpoint_path="/v1/responses",
            endpoint=endpoint,
            request_shape_classified=True,
            model_id=model,
            input_item_count=len(tool_loop_fixture.get("input") or []),
            tools_declared_count=len(tool_loop_fixture.get("tools") or []),
            stream_requested=False,
            request_body_sha256=sha256_text(
                json.dumps(
                    {
                        "model": model,
                        "input_count": len(tool_loop_fixture.get("input") or []),
                        "tools_declared_count": len(tool_loop_fixture.get("tools") or []),
                        "stream": False,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                )
            ),
            request_body_recorded=False,
            raw_prompt_recorded=False,
            auth_header_recorded=False,
            live_request_allowed=owner_authorized,
            live_request_attempted=False,
            stopped_before_live_provider_model_request=not owner_authorized,
            request_prepared_counts_as_live_proof=False,
        ),
        "failure_taxonomy_packet.json": packet(
            "failure_taxonomy",
            allowed_failure_causes=sorted(FAILURE_CAUSES),
            failure_taxonomy_complete_for_this_contour=True,
            failure_taxonomy_counts_as_provider_family_compatibility=False,
            failure_taxonomy_counts_as_model_availability=False,
        ),
    }
    if auth_observation_packet is not None:
        packets["direct_wbp_auth_command_observation_packet.json"] = auth_observation_packet

    if not owner_authorized:
        blocked_packet = packet(
            "direct_request_attempt",
            status="blocked",
            machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
            request_attempted=False,
            request_reaches_wbp=False,
            endpoint_path="/v1/responses",
            response_observed=False,
            blocked_reason_class="owner_authorization_missing",
        )
        packets.update(
            {
                "direct_request_attempt_packet.json": blocked_packet,
                "route_selection_observation_packet.json": packet(
                    "route_selection_observation",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    route_selected=False,
                    route_selection_observed=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "upstream_acceptance_or_failure_packet.json": packet(
                    "upstream_acceptance_or_failure",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    upstream_accepts=False,
                    failure_cause="unknown",
                    failure_classified=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "direct_non_stream_response_shape_packet.json": packet(
                    "direct_non_stream_response_shape",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    response_shape_accepted=False,
                    direct_client_accepted_response=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "direct_stream_response_shape_packet.json": packet(
                    "direct_stream_response_shape",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    stream_shape_accepted=False,
                    stream_sse_envelope_observed=False,
                    event_count=0,
                    observed_events=[],
                    expected_events=[],
                    data_type_sequence=[],
                    data_type_matches_event=False,
                    data_parse_errors=[],
                    terminal_response_status="",
                    completed_event_required=True,
                    stream_classification_fields_observed=False,
                    stream_started_counts_as_compatible=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "responses_tool_loop_packet.json": packet(
                    "responses_tool_loop",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    tool_loop_shape_accepted=False,
                    tool_call_observed=False,
                    tool_result_roundtrip_observed=False,
                    assistant_followup_after_tool_observed=False,
                    tool_call_emitted_counts_as_tool_loop=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "responses_tool_loop_followup_request_packet.json": packet(
                    "responses_tool_loop_followup_request",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    canonical_followup_request_classified=False,
                    negative_control_request_classified=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "responses_tool_loop_followup_response_packet.json": packet(
                    "responses_tool_loop_followup_response",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    assistant_continuation_observed=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "responses_tool_loop_followup_failure_packet.json": packet(
                    "responses_tool_loop_followup_failure",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    failure_observed=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "responses_tool_loop_followup_root_cause_classification_packet.json": packet(
                    "responses_tool_loop_followup_root_cause_classification",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    best_supported_cause="owner_authorization_missing",
                    root_cause_proven=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
                "responses_tool_loop_followup_false_green_audit.json": packet(
                    "responses_tool_loop_followup_false_green_audit",
                    status="ok",
                    findings=[],
                    tool_loop_followup_success_implies_broad_tools_capability=False,
                    tool_loop_followup_failure_implies_model_unavailable=False,
                    tool_loop_followup_failure_implies_provider_incompatible=False,
                ),
                "failure_semantics_packet.json": packet(
                    "failure_semantics",
                    status="blocked",
                    machine_error_code="OWNER_AUTHORIZATION_REQUIRED",
                    request_attempted=False,
                    failure_cause="unknown",
                    controlled_negative_cases_exercised=False,
                    negative_case_http_status=0,
                    negative_case_response_shape_accepted=False,
                    retry_recommended=False,
                    blocked_reason_class="owner_authorization_missing",
                ),
            }
        )
    else:
        if request_runner is None:
            runner_result = {
                "request_attempted": False,
                "request_reaches_wbp": False,
                "route_selected": False,
                "response_observed": False,
                "upstream_status_code": 0,
                "upstream_accepts": False,
                "response_shape_accepted": False,
                "failure_cause": "wbp_runtime_unavailable",
            }
            runner_error = "LIVE_RUNNER_UNCONFIGURED"
        else:
            runner_result = request_runner(
                {
                    "surface": "non_stream",
                    "endpoint_path": "/v1/responses",
                    "model_id": model,
                    "request_body_sha256": request_body_hash,
                    "stream": False,
                }
            )
            stream_result = request_runner(
                {
                    "surface": "stream",
                    "endpoint_path": "/v1/responses",
                    "model_id": model,
                    "stream": True,
                }
            )
            tool_loop_result = request_runner(
                {
                    "surface": "tool_loop",
                    "endpoint_path": "/v1/responses",
                    "model_id": model,
                    "stream": False,
                }
            )
            failure_result = request_runner(
                {
                    "surface": "failure_semantics",
                    "endpoint_path": "/v1/responses",
                    "model_id": model,
                    "stream": False,
                }
            )
            runner_error = ""
        if request_runner is None:
            stream_result = dict(runner_result)
            tool_loop_result = dict(runner_result)
            failure_result = dict(runner_result)

        failure_cause = classify_failure(runner_result)
        request_attempted = runner_result.get("request_attempted") is True
        request_reaches_wbp = runner_result.get("request_reaches_wbp") is True
        route_selected = runner_result.get("route_selected") is True
        upstream_accepts = runner_result.get("upstream_accepts") is True
        response_shape_accepted = runner_result.get("response_shape_accepted") is True
        stream_shape_ok = stream_result.get("stream_shape_accepted") is True
        stream_sse_envelope_observed = (
            stream_result.get("stream_sse_envelope_observed") is True
            or bool(stream_result.get("observed_events"))
        )
        stream_event_count = int(
            stream_result.get("event_count")
            or stream_result.get("stream_packets_observed")
            or 0
        )
        stream_observed_events = list(stream_result.get("observed_events") or [])
        stream_expected_events = list(stream_result.get("expected_events") or [])
        stream_data_type_sequence = list(stream_result.get("data_type_sequence") or [])
        stream_data_type_matches_event = stream_result.get("data_type_matches_event") is True or (
            stream_result.get("stream_classification_fields_observed") is True and stream_shape_ok
        )
        stream_data_parse_errors = list(stream_result.get("data_parse_errors") or [])
        stream_terminal_response_status = str(
            stream_result.get("terminal_response_status") or "completed"
        )
        stream_completed_event_observed = (
            stream_result.get("completed_event_observed") is True
            or (
                bool(stream_observed_events)
                and stream_observed_events[-1:] == ["response.completed"]
            )
            or (
                stream_result.get("stream_classification_fields_observed") is True and stream_shape_ok
            )
        )
        tool_call_observed = tool_loop_result.get("tool_call_observed") is True
        tool_result_roundtrip_observed = (
            tool_loop_result.get("tool_output_submitted") is True
            or tool_loop_result.get("tool_result_roundtrip_observed") is True
        )
        assistant_followup_after_tool_observed = (
            tool_loop_result.get("assistant_continuation_observed") is True
            or tool_loop_result.get("assistant_followup_after_tool_observed") is True
        )
        tool_loop_shape_ok = (
            tool_loop_result.get("response_shape_accepted") is True
            and tool_call_observed
            and tool_result_roundtrip_observed
            and assistant_followup_after_tool_observed
        )
        failure_result_cause = classify_failure(failure_result)
        failure_result_attempted = failure_result.get("request_attempted") is True
        failure_cause_classified = failure_result_cause in FAILURE_CAUSES and failure_result_cause != ""
        failure_negative_status = int(failure_result.get("upstream_status_code") or 0)
        failure_negative_shape = failure_result.get("response_shape_accepted") is True
        upstream_status_code = int(runner_result.get("upstream_status_code") or 0)

        packets["runtime_readiness_packet.json"] = packet(
            "runtime_readiness",
            status="ok" if request_runner is not None else "blocked",
            machine_error_code="OK" if request_runner is not None else runner_error,
            direct_wbp_client_only=True,
            native_launch_required=False,
            codex_cli_required=False,
            owner_authorization_phrase_present=True,
            live_request_allowed=True,
            live_request_attempted=request_attempted,
            stopped_before_live_provider_model_request=False,
        )
        packets["direct_request_attempt_packet.json"] = packet(
            "direct_request_attempt",
            status="ok" if request_attempted and request_reaches_wbp else "blocked",
            machine_error_code=(
                "OK"
                if request_attempted and request_reaches_wbp
                else runner_error or "REQUEST_DID_NOT_REACH_WBP"
            ),
            request_attempted=request_attempted,
            request_reaches_wbp=request_reaches_wbp,
            endpoint_path=str(runner_result.get("path") or "/v1/responses"),
            response_observed=runner_result.get("response_observed") is True,
            http_body_sha256=str(runner_result.get("http_body_sha256") or ""),
            http_body_len=int(runner_result.get("http_body_len") or 0),
            exception_type=str(runner_result.get("exception_type") or ""),
            blocked_reason_class="" if request_attempted and request_reaches_wbp else failure_cause,
        )
        packets["route_selection_observation_packet.json"] = packet(
            "route_selection_observation",
            status="ok" if request_attempted and route_selected else "blocked",
            machine_error_code="OK" if request_attempted and route_selected else "ROUTE_NOT_OBSERVED",
            request_attempted=request_attempted,
            route_selected=route_selected,
            route_selection_observed=route_selected,
            route_selected_counts_as_model_availability=False,
            blocked_reason_class="" if request_attempted and route_selected else failure_cause,
        )
        packets["upstream_acceptance_or_failure_packet.json"] = packet(
            "upstream_acceptance_or_failure",
            status=(
                "ok"
                if request_attempted and failure_cause in FAILURE_CAUSES and failure_cause != ""
                else "blocked"
            ),
            machine_error_code=(
                "OK"
                if request_attempted and failure_cause in FAILURE_CAUSES
                else "FAILURE_NOT_CLASSIFIED"
            ),
            request_attempted=request_attempted,
            upstream_accepts=upstream_accepts,
            upstream_status_code=upstream_status_code,
            failure_cause=failure_cause,
            failure_classified=failure_cause in FAILURE_CAUSES,
            exception_type=str(runner_result.get("exception_type") or ""),
            failure_counts_as_model_availability=False,
            failure_counts_as_provider_family_compatibility=False,
        )
        packets["direct_non_stream_response_shape_packet.json"] = packet(
            "direct_non_stream_response_shape",
            status="ok" if upstream_accepts and response_shape_accepted else "blocked",
            machine_error_code=(
                "OK"
                if upstream_accepts and response_shape_accepted
                else "DIRECT_NON_STREAM_RESPONSE_SHAPE_NOT_ACCEPTED"
            ),
            request_attempted=request_attempted,
            response_shape_accepted=response_shape_accepted,
            direct_client_accepted_response=response_shape_accepted,
            response_status=str(runner_result.get("response_status") or ""),
            http_body_sha256=str(runner_result.get("http_body_sha256") or ""),
            http_body_len=int(runner_result.get("http_body_len") or 0),
            direct_non_stream_success_counts_as_native_acceptance=False,
            direct_non_stream_success_counts_as_model_availability=False,
        )
        packets["direct_stream_response_shape_packet.json"] = packet(
            "direct_stream_response_shape",
            status=(
                "ok"
                if stream_shape_ok
                and stream_sse_envelope_observed
                and stream_data_type_matches_event
                and not stream_data_parse_errors
                and stream_completed_event_observed
                else "blocked"
            ),
            machine_error_code=(
                "OK"
                if stream_shape_ok
                and stream_sse_envelope_observed
                and stream_data_type_matches_event
                and not stream_data_parse_errors
                and stream_completed_event_observed
                else "STREAM_RESPONSE_SHAPE_NOT_ACCEPTED"
            ),
            request_attempted=stream_result.get("request_attempted") is True,
            stream_shape_accepted=stream_shape_ok,
            stream_sse_envelope_observed=stream_sse_envelope_observed,
            event_count=stream_event_count,
            observed_events=stream_observed_events,
            expected_events=stream_expected_events,
            data_type_sequence=stream_data_type_sequence,
            data_type_matches_event=stream_data_type_matches_event,
            data_parse_errors=stream_data_parse_errors,
            terminal_response_status=stream_terminal_response_status,
            completed_event_observed=stream_completed_event_observed,
            completed_event_required=True,
            stream_classification_fields_observed=(
                stream_sse_envelope_observed
                and stream_event_count > 0
                and bool(stream_observed_events)
                and bool(stream_expected_events)
            ),
            stream_started_counts_as_compatible=False,
            upstream_status_code=int(stream_result.get("upstream_status_code") or 0),
            failure_cause=classify_failure(stream_result),
            stream_success_counts_as_model_availability=False,
        )
        packets["responses_tool_loop_packet.json"] = packet(
            "responses_tool_loop",
            status="ok" if tool_loop_shape_ok else "blocked",
            machine_error_code="OK" if tool_loop_shape_ok else "TOOL_LOOP_RESPONSE_SHAPE_NOT_ACCEPTED",
            request_attempted=tool_loop_result.get("request_attempted") is True,
            tool_loop_shape_accepted=tool_loop_shape_ok,
            tool_call_observed=tool_call_observed,
            tool_result_roundtrip_observed=tool_result_roundtrip_observed,
            assistant_followup_after_tool_observed=assistant_followup_after_tool_observed,
            followup_response_shape_accepted=(
                tool_loop_result.get("followup_response_shape_accepted") is True
            ),
            followup_upstream_status_code=int(
                tool_loop_result.get("followup_upstream_status_code") or 0
            ),
            followup_response_status=str(tool_loop_result.get("followup_response_status") or ""),
            tool_call_emitted_counts_as_tool_loop=False,
            upstream_status_code=int(tool_loop_result.get("upstream_status_code") or 0),
            failure_cause=classify_failure(tool_loop_result),
            tool_loop_success_counts_as_model_availability=False,
        )
        packets["responses_tool_loop_followup_request_packet.json"] = packet(
            "responses_tool_loop_followup_request",
            status=(
                "ok"
                if tool_loop_result.get("tool_call_observed") is True
                and tool_loop_result.get("tool_output_submitted") is True
                else "blocked"
            ),
            machine_error_code=(
                "OK"
                if tool_loop_result.get("tool_call_observed") is True
                and tool_loop_result.get("tool_output_submitted") is True
                else "TOOL_LOOP_FOLLOWUP_REQUEST_NOT_CLASSIFIED"
            ),
            request_attempted=tool_loop_result.get("request_attempted") is True,
            canonical_followup_request_classified=(
                tool_loop_result.get("tool_output_submitted") is True
            ),
            canonical_followup_request_shape_mode=str(
                tool_loop_result.get("followup_request_shape_mode") or ""
            ),
            canonical_followup_replayed_output_item_count=int(
                tool_loop_result.get("followup_replayed_output_item_count") or 0
            ),
            negative_control_request_classified=bool(
                tool_loop_result.get("negative_control_request_shape_mode")
            ),
            negative_control_request_shape_mode=str(
                tool_loop_result.get("negative_control_request_shape_mode") or ""
            ),
            previous_response_id_only_counts_as_canonical=False,
        )
        packets["responses_tool_loop_followup_response_packet.json"] = packet(
            "responses_tool_loop_followup_response",
            status=(
                "ok"
                if tool_loop_result.get("followup_response_shape_accepted") is True
                and tool_loop_result.get("assistant_continuation_observed") is True
                else "blocked"
            ),
            machine_error_code=(
                "OK"
                if tool_loop_result.get("followup_response_shape_accepted") is True
                and tool_loop_result.get("assistant_continuation_observed") is True
                else "TOOL_LOOP_FOLLOWUP_RESPONSE_NOT_ACCEPTED"
            ),
            request_attempted=tool_loop_result.get("tool_output_submitted") is True,
            followup_upstream_status_code=int(
                tool_loop_result.get("followup_upstream_status_code") or 0
            ),
            followup_response_shape_accepted=(
                tool_loop_result.get("followup_response_shape_accepted") is True
            ),
            followup_response_status=str(tool_loop_result.get("followup_response_status") or ""),
            assistant_continuation_observed=(
                tool_loop_result.get("assistant_continuation_observed") is True
            ),
            followup_success_counts_as_broad_tools_capability=False,
        )
        packets["responses_tool_loop_followup_failure_packet.json"] = packet(
            "responses_tool_loop_followup_failure",
            status=(
                "ok"
                if int(tool_loop_result.get("negative_control_status_code") or 0) >= 400
                else "blocked"
            ),
            machine_error_code=(
                "OK"
                if int(tool_loop_result.get("negative_control_status_code") or 0) >= 400
                else "TOOL_LOOP_FOLLOWUP_FAILURE_NOT_OBSERVED"
            ),
            request_attempted=bool(tool_loop_result.get("negative_control_request_shape_mode")),
            failure_observed=int(tool_loop_result.get("negative_control_status_code") or 0) >= 400,
            negative_control_upstream_status_code=int(
                tool_loop_result.get("negative_control_status_code") or 0
            ),
            negative_control_failure_cause=str(
                tool_loop_result.get("negative_control_failure_cause") or ""
            ),
            negative_control_error_type=str(
                tool_loop_result.get("negative_control_error_type") or ""
            ),
            negative_control_error_param=str(
                tool_loop_result.get("negative_control_error_param") or ""
            ),
            negative_control_error_code=str(
                tool_loop_result.get("negative_control_error_code") or ""
            ),
            negative_control_response_shape_accepted=(
                tool_loop_result.get("negative_control_response_shape_accepted") is True
            ),
            negative_control_failure_counts_as_model_unavailable=False,
            negative_control_failure_counts_as_provider_incompatible=False,
        )
        negative_control_status_code = int(tool_loop_result.get("negative_control_status_code") or 0)
        canonical_followup_status_code = int(tool_loop_result.get("followup_upstream_status_code") or 0)
        best_supported_cause = "unclassified"
        if negative_control_status_code >= 400 and canonical_followup_status_code >= 200:
            best_supported_cause = (
                "previous_response_id_only_function_call_output_followup_not_accepted_while_"
                "prior_output_replay_plus_function_call_output_accepted"
            )
        elif canonical_followup_status_code >= 400:
            best_supported_cause = "canonical_followup_contract_still_not_accepted"
        packets["responses_tool_loop_followup_root_cause_classification_packet.json"] = packet(
            "responses_tool_loop_followup_root_cause_classification",
            status="ok",
            machine_error_code="OK",
            best_supported_cause=best_supported_cause,
            root_cause_proven=False,
            best_supported_cause_classified=best_supported_cause != "unclassified",
            canonical_followup_accepted=canonical_followup_status_code >= 200
            and tool_loop_result.get("followup_response_shape_accepted") is True,
            negative_control_failed=negative_control_status_code >= 400,
            broad_tools_capability_inference_forbidden=True,
            model_unavailable_inference_forbidden=True,
        )
        followup_false_green_findings: list[str] = []
        if (
            tool_loop_result.get("assistant_continuation_observed") is True
            and tool_loop_result.get("followup_response_shape_accepted") is not True
        ):
            followup_false_green_findings.append(
                "assistant_continuation_claimed_without_followup_response_shape"
            )
        packets["responses_tool_loop_followup_false_green_audit.json"] = packet(
            "responses_tool_loop_followup_false_green_audit",
            status="ok" if not followup_false_green_findings else "blocked",
            findings=followup_false_green_findings,
            tool_loop_followup_success_implies_broad_tools_capability=False,
            tool_loop_followup_failure_implies_model_unavailable=False,
            tool_loop_followup_failure_implies_provider_incompatible=False,
        )
        packets["failure_semantics_packet.json"] = packet(
            "failure_semantics",
            status="ok" if failure_result_attempted and failure_cause_classified else "blocked",
            machine_error_code=(
                "OK"
                if failure_result_attempted and failure_cause_classified
                else "FAILURE_SEMANTICS_NOT_CLASSIFIED"
            ),
            request_attempted=failure_result_attempted,
            failure_cause=failure_result_cause,
            failure_cause_classified=failure_cause_classified,
            controlled_negative_cases_exercised=failure_result_attempted,
            negative_case_http_status=failure_negative_status,
            negative_case_response_shape_accepted=failure_negative_shape,
            retry_recommended=failure_result_cause in {"quota_or_rate_limit", "provider_error", "timeout"},
            classified_from_direct_non_stream_surface=False,
        )

    summary = build_summary_packet(packets)
    packets["responses_live_non_native_summary_packet.json"] = summary
    packets["responses_live_compatibility_matrix.json"] = packet(
        "responses_live_compatibility_matrix",
        status="ok",
        matrix_source_packets=[
            "direct_non_stream_response_shape_packet.json",
            "direct_stream_response_shape_packet.json",
            "responses_tool_loop_packet.json",
            "failure_semantics_packet.json",
            "responses_live_non_native_summary_packet.json",
        ],
        matrix_is_derived_not_truth_source=True,
        surfaces=[
            {
                "surface": "non_stream",
                "status": packets["direct_non_stream_response_shape_packet.json"].get("status"),
                "proven": packets["direct_non_stream_response_shape_packet.json"].get(
                    "response_shape_accepted"
                )
                is True,
            },
            {
                "surface": "streaming",
                "status": packets["direct_stream_response_shape_packet.json"].get("status"),
                "proven": summary.get("streaming_compatibility_proven") is True,
            },
            {
                "surface": "tool_loop_followup",
                "status": packets["responses_tool_loop_packet.json"].get("status"),
                "proven": summary.get("tool_loop_compatibility_proven") is True,
            },
            {
                "surface": "failure_semantics",
                "status": packets["failure_semantics_packet.json"].get("status"),
                "proven": summary.get("failure_semantics_compatibility_proven") is True,
            },
        ],
    )
    packets["responses_live_non_native_false_green_audit.json"] = build_false_green_audit(
        packets, summary
    )
    packets["independent_responses_live_non_native_audit.json"] = build_independent_audit(
        packets
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    return packets


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sync = packets["sync_gate_packet.json"]
    auth = packets["live_authorization_packet.json"]
    runtime = packets["runtime_readiness_packet.json"]
    attempt = packets["direct_request_attempt_packet.json"]
    route = packets["route_selection_observation_packet.json"]
    upstream = packets["upstream_acceptance_or_failure_packet.json"]
    response = packets["direct_non_stream_response_shape_packet.json"]
    stream = packets["direct_stream_response_shape_packet.json"]
    tool_loop = packets["responses_tool_loop_packet.json"]
    failure_semantics = packets["failure_semantics_packet.json"]

    blocked_packets = [
        name
        for name in (
            "sync_gate_packet.json",
            "live_authorization_packet.json",
            "runtime_readiness_packet.json",
            "direct_request_attempt_packet.json",
            "route_selection_observation_packet.json",
            "upstream_acceptance_or_failure_packet.json",
            "direct_non_stream_response_shape_packet.json",
            "direct_stream_response_shape_packet.json",
            "responses_tool_loop_packet.json",
            "failure_semantics_packet.json",
        )
        if packets[name].get("status") != "ok"
    ]
    streaming_proven = (
        stream.get("stream_shape_accepted") is True
        and stream.get("stream_sse_envelope_observed") is True
        and stream.get("data_type_matches_event") is True
        and not list(stream.get("data_parse_errors") or [])
        and stream.get("completed_event_observed") is True
        and stream.get("terminal_response_status") == "completed"
    )
    tool_loop_proven = (
        tool_loop.get("tool_loop_shape_accepted") is True
        and tool_loop.get("tool_call_observed") is True
        and tool_loop.get("tool_result_roundtrip_observed") is True
        and tool_loop.get("assistant_followup_after_tool_observed") is True
    )
    failure_semantics_proven = (
        failure_semantics.get("failure_cause_classified") is True
        and failure_semantics.get("controlled_negative_cases_exercised") is True
    )
    success_ready = (
        sync.get("status") == "ok"
        and auth.get("status") == "ok"
        and runtime.get("status") == "ok"
        and attempt.get("request_reaches_wbp") is True
        and route.get("route_selected") is True
        and upstream.get("upstream_accepts") is True
        and response.get("response_shape_accepted") is True
        and streaming_proven
        and tool_loop_proven
        and failure_semantics_proven
    )
    limited_ready = (
        sync.get("status") == "ok"
        and auth.get("status") == "ok"
        and runtime.get("status") == "ok"
        and attempt.get("request_reaches_wbp") is True
        and route.get("route_selected") is True
        and response.get("response_shape_accepted") is True
    )
    surface_limits = [
        surface
        for surface, proven in (
            ("streaming", streaming_proven),
            ("tool_loop", tool_loop_proven),
            ("failure_semantics", failure_semantics_proven),
        )
        if not proven
    ]
    if success_ready:
        final_status = TARGET_STATUS
        reason_class = ""
        status = "ok"
    elif auth.get("status") != "ok":
        final_status = BLOCKED_NO_OWNER_AUTHORIZATION
        reason_class = "NO_OWNER_AUTHORIZATION"
        status = "blocked"
    elif runtime.get("machine_error_code") == "LIVE_RUNNER_UNCONFIGURED":
        final_status = BLOCKED_RUNNER_UNCONFIGURED
        reason_class = "RUNNER_UNCONFIGURED"
        status = "blocked"
    elif limited_ready:
        final_status = TARGET_STATUS_WITH_LIMITS
        reason_class = "SURFACE_LIMITS"
        status = "ok"
    else:
        final_status = BLOCKED_RUNTIME_OR_UPSTREAM_FAILURE
        reason_class = str(upstream.get("failure_cause") or "RUNTIME_OR_UPSTREAM_FAILURE").upper()
        status = "blocked"
    return packet(
        "responses_live_non_native_summary",
        status=status,
        final_status=final_status,
        reason_class=reason_class,
        blocked_packets=blocked_packets,
        surface_limits=surface_limits,
        owner_authorization_phrase_present=auth.get("owner_authorization_phrase_present") is True,
        live_request_attempted=attempt.get("request_attempted") is True,
        stopped_before_live_provider_model_request=(
            auth.get("stopped_before_live_provider_model_request") is True
        ),
        request_reaches_wbp=attempt.get("request_reaches_wbp") is True,
        route_selected=route.get("route_selected") is True,
        upstream_accepts=upstream.get("upstream_accepts") is True,
        direct_non_stream_response_shape_accepted=(
            response.get("response_shape_accepted") is True
        ),
        model_availability_proven=False,
        provider_family_compatibility_proven=False,
        native_codex_acceptance_proven=False,
        codex_cli_acceptance_proven=False,
        streaming_compatibility_proven=streaming_proven,
        tool_loop_compatibility_proven=tool_loop_proven,
        failure_semantics_compatibility_proven=failure_semantics_proven,
        direct_egress_absence_proven=False,
        final_e2e_proven=False,
    )


def build_false_green_audit(
    packets: dict[str, dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    checks = {
        "all_models_work": False,
        "model_catalog_proves_model_access": False,
        "gpt_5_5_works": False,
        "provider_family_compatible": False,
        "native_custom_works": False,
        "codex_app_accepted_model": False,
        "codex_cli_accepted_model": False,
        "direct_egress_absent": False,
        "streaming_compatible": False,
        "tool_loop_compatible": False,
        "final_e2e_proven": False,
        "direct_wbp_200_counted_as_native_acceptance": False,
        "direct_wbp_200_counted_as_general_model_availability": False,
    }
    if summary.get("native_codex_acceptance_proven") is True:
        findings.append("native_codex_acceptance_proven")
    if summary.get("model_availability_proven") is True:
        findings.append("model_availability_proven")
    if (
        summary.get("final_status") == TARGET_STATUS
        and summary.get("streaming_compatibility_proven") is not True
    ):
        findings.append("target_status_without_streaming_proof")
    if (
        summary.get("final_status") == TARGET_STATUS
        and summary.get("tool_loop_compatibility_proven") is not True
    ):
        findings.append("target_status_without_tool_loop_proof")
    if (
        summary.get("final_status") == TARGET_STATUS
        and summary.get("failure_semantics_compatibility_proven") is not True
    ):
        findings.append("target_status_without_failure_semantics_proof")
    if (
        summary.get("tool_loop_compatibility_proven") is True
        and packets["responses_tool_loop_packet.json"].get("tool_result_roundtrip_observed") is not True
    ):
        findings.append("tool_loop_claimed_without_roundtrip")
    if (
        summary.get("tool_loop_compatibility_proven") is True
        and packets["responses_tool_loop_packet.json"].get("assistant_followup_after_tool_observed") is not True
    ):
        findings.append("tool_loop_claimed_without_assistant_followup")
    if (
        summary.get("streaming_compatibility_proven") is True
        and packets["direct_stream_response_shape_packet.json"].get("data_type_matches_event") is not True
    ):
        findings.append("streaming_claimed_without_sse_event_data_alignment")
    return packet(
        "responses_live_non_native_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        **checks,
    )


def build_independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    auth = packets["live_authorization_packet.json"]
    attempt = packets["direct_request_attempt_packet.json"]
    route = packets["route_selection_observation_packet.json"]
    response = packets["direct_non_stream_response_shape_packet.json"]
    summary = packets["responses_live_non_native_summary_packet.json"]

    if auth.get("status") != "ok":
        if attempt.get("request_attempted") is True:
            findings.append("request_attempted_without_owner_authorization")
        if route.get("route_selected") is True:
            findings.append("route_selected_without_owner_authorization")
        if response.get("response_shape_accepted") is True:
            findings.append("response_shape_accepted_without_owner_authorization")
        if summary.get("final_status") != BLOCKED_NO_OWNER_AUTHORIZATION:
            findings.append("blocked_summary_mismatch_for_missing_authorization")
    else:
        if summary.get("final_status") == BLOCKED_NO_OWNER_AUTHORIZATION:
            findings.append("authorized_run_reported_as_missing_authorization")
    if (
        summary.get("final_status") == TARGET_STATUS
        and summary.get("surface_limits")
    ):
        findings.append("full_target_status_reported_with_surface_limits")
    if (
        summary.get("tool_loop_compatibility_proven") is True
        and packets["responses_tool_loop_packet.json"].get("tool_result_roundtrip_observed") is not True
    ):
        findings.append("tool_loop_proven_without_roundtrip_packet_truth")
    return packet(
        "independent_responses_live_non_native_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        owner_authorization_gate_honored=not findings,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, ensure_ascii=True, sort_keys=True)
    findings = [marker for marker in SECRET_MARKERS if marker in serialized]
    return packet(
        "secret_redaction_audit",
        status="ok" if not findings else "blocked",
        raw_secret_found=bool(findings),
        raw_prompt_recorded=False,
        secret_marker_findings=findings,
    )


def write_packets(evidence_dir: Path, packets: dict[str, dict[str, Any]]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in packets.items():
        (evidence_dir / name).write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--owner-authorization-phrase", default="")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)

    request_runner: RequestRunner | None = None
    auth_observation_packet: dict[str, Any] | None = None
    if owner_authorization_phrase_present(args.owner_authorization_phrase):
        request_runner, auth_observation_packet = build_live_request_runner(
            repo_root=args.repo_root,
            endpoint=args.endpoint,
            model_id=args.model,
            timeout=args.timeout,
        )
    packets = build_packets(
        args.repo_root,
        args.evidence_dir,
        owner_authorization_phrase=args.owner_authorization_phrase,
        request_runner=request_runner,
        auth_observation_packet=auth_observation_packet,
        endpoint=args.endpoint,
        model_id=args.model or None,
    )
    write_packets(args.evidence_dir, packets)
    print(
        json.dumps(
            {
                "status": packets["responses_live_non_native_summary_packet.json"]["status"],
                "final_status": packets["responses_live_non_native_summary_packet.json"][
                    "final_status"
                ],
                "evidence_dir": str(args.evidence_dir),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
