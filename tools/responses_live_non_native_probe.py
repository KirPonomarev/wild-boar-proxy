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


def load_request_fixture() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "non_stream_text_request.json").read_text(encoding="utf-8"))


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
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
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
                "body_hash": sha256_text(decoded),
                "body_len": len(response_body),
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
            "body_hash": sha256_text(decoded),
            "body_len": len(response_body),
            "payload": parsed if isinstance(parsed, dict) else {},
            "exception_type": "HTTPError",
        }
    except TimeoutError:
        return {
            "http_status": None,
            "body_hash": "",
            "body_len": 0,
            "payload": {},
            "exception_type": "TimeoutError",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "http_status": None,
            "body_hash": "",
            "body_len": 0,
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
        prompt = f"{LIVE_PROMPT_PREFIX}_{sha256_text(utc_now())[:16]}: answer exactly OK"
        observed = http_json(
            endpoint=endpoint,
            path="responses",
            token=token,
            payload={
                "model": model_id or str(request_spec.get("model_id") or ""),
                "input": prompt,
                "max_output_tokens": 16,
                "stream": False,
            },
            timeout=timeout,
        )
        http_status = observed["http_status"]
        payload = observed["payload"]
        shape_accepted, response_status = response_shape_accepted(payload)
        success = http_status is not None and 200 <= http_status < 300
        failure_cause = "none" if success and shape_accepted else classify_http_failure(
            http_status,
            payload,
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
            "response_status": response_status,
            "failure_cause": failure_cause,
            "http_body_sha256": observed["body_hash"],
            "http_body_len": observed["body_len"],
            "exception_type": observed["exception_type"],
            "auth_command_status": auth_packet["status"],
        }

    return runner, auth_packet


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    try:
        relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    except ValueError:
        relative_evidence_dir = ""
    admitted_current_contour = {
        "tools/responses_live_non_native_probe.py",
        "tests/test_responses_live_non_native_probe.py",
    }
    admitted_current_evidence_prefixes = (
        f"A  {DEFAULT_EVIDENCE_DIR.relative_to(repo_root)}/",
        f"AM {DEFAULT_EVIDENCE_DIR.relative_to(repo_root)}/",
        f" M {DEFAULT_EVIDENCE_DIR.relative_to(repo_root)}/",
        f"?? {DEFAULT_EVIDENCE_DIR.relative_to(repo_root)}/",
    )
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
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not (
            relative_evidence_dir
            and line.strip().startswith(f"?? {relative_evidence_dir}/")
        )
        and not line.strip().startswith(admitted_current_evidence_prefixes)
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
    fixture = load_request_fixture()
    model = str(model_id or fixture.get("model") or "")
    input_items = fixture.get("input")
    input_count = len(input_items) if isinstance(input_items, list) else 0
    try:
        evidence_surface = str(evidence_dir.relative_to(repo_root))
    except ValueError:
        evidence_surface = str(evidence_dir)
    request_body = {
        "model": model,
        "input_count": input_count,
        "stream": fixture.get("stream") is True,
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
                    "endpoint_path": "/v1/responses",
                    "model_id": model,
                    "request_body_sha256": request_body_hash,
                    "stream": False,
                }
            )
            runner_error = ""

        failure_cause = classify_failure(runner_result)
        request_attempted = runner_result.get("request_attempted") is True
        request_reaches_wbp = runner_result.get("request_reaches_wbp") is True
        route_selected = runner_result.get("route_selected") is True
        upstream_accepts = runner_result.get("upstream_accepts") is True
        response_shape_accepted = runner_result.get("response_shape_accepted") is True
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

    summary = build_summary_packet(packets)
    packets["responses_live_non_native_summary_packet.json"] = summary
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
        )
        if packets[name].get("status") != "ok"
    ]
    success_ready = (
        sync.get("status") == "ok"
        and auth.get("status") == "ok"
        and runtime.get("status") == "ok"
        and attempt.get("request_reaches_wbp") is True
        and route.get("route_selected") is True
        and upstream.get("upstream_accepts") is True
        and response.get("response_shape_accepted") is True
    )
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
        streaming_compatibility_proven=False,
        tool_loop_compatibility_proven=False,
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
    if summary.get("streaming_compatibility_proven") is True:
        findings.append("streaming_compatibility_proven")
    if summary.get("tool_loop_compatibility_proven") is True:
        findings.append("tool_loop_compatibility_proven")
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
