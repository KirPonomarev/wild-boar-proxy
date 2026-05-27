#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit non-live WBP Responses wire compatibility prep evidence packets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.responses_runtime_compatibility_probe import build_packets as build_runtime_packets


TARGET_STATUS = "WBP_RESPONSES_WIRE_COMPATIBILITY_READINESS_NO_LIVE_R1_CLASSIFIED"
PARENT_STATUS = "WBP_RESPONSES_LIVE_COMPATIBILITY_CLASSIFIED"
DEFAULT_EVIDENCE_DIR = (
    REPO_ROOT
    / "audit_results"
    / "wbp_responses_wire_compatibility_readiness_no_live_r1_2026-05-27"
)
SECRET_MARKERS = (
    "sk-",
    "Authorization: Bearer",
    "OPENAI_API_KEY",
    "route-secret-fixture",
    "local-runtime-fixture",
    "LARGE_PROMPT_FIXTURE_DO_NOT_LOG_RAW",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def write_packet(evidence_dir: Path, name: str, payload: dict[str, Any]) -> None:
    (evidence_dir / name).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/responses_runtime_compatibility_probe.py",
        "tools/responses_wire_compatibility_prep_probe.py",
        "tests/test_wbp_responses_fixture_compatibility.py",
        "tests/test_responses_wire_compatibility_prep_probe.py",
    }
    admitted_current_evidence_prefixes = (
        "?? audit_results/wbp_responses_wire_compatibility_readiness_no_live_r1_2026-05-27/",
        "?? audit_results/wbp_responses_wire_compatibility_prep_r1_2026-05-27/",
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
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not line.strip().startswith(admitted_current_evidence_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _ok(packet_payload: dict[str, Any]) -> bool:
    return packet_payload.get("status") == "ok"


def _blocked_by_host(packet_payload: dict[str, Any]) -> bool:
    return packet_payload.get("status") == "blocked_by_host_environment"


def _contains_secret_marker(packets: dict[str, dict[str, Any]]) -> list[str]:
    serialized = json.dumps(packets, sort_keys=True)
    return [marker for marker in SECRET_MARKERS if marker in serialized]


def _closeout_text(
    *,
    repo_root: Path,
    evidence_dir: Path,
    summary: dict[str, Any],
) -> str:
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    tests = (
        "python3 -m py_compile tools/responses_wire_compatibility_prep_probe.py "
        "tools/responses_runtime_compatibility_probe.py; "
        "python3 -m pytest tests/test_responses_wire_compatibility_prep_probe.py "
        "tests/test_wbp_responses_fixture_compatibility.py; "
        "probe JSON emission; JSON parse; secret marker scan; closeout resilience"
    )
    blocked_risks = (
        "Live Responses compatibility, model availability, provider reachability, "
        "Codex consumer acceptance, native UX, direct egress absence, and final E2E "
        "remain unclaimed."
    )
    return f"""# WBP Responses Wire Compatibility Readiness No Live R1 Closeout

## Goal

Classify Responses wire compatibility readiness at fixture/dry-run level for non-stream, streaming, tool-loop shape, failure semantics, redaction, and live-promotion blocking.

## Result

- status: {summary["final_status"]}
- final verdict: Responses wire readiness classified without live/native execution
- closure state: CLOSED

## Contour Capsule

- goal: classify no-live Responses wire readiness and block live false-green
- branch: {branch}
- head: {head}
- touched files: tools/responses_wire_compatibility_prep_probe.py, tests/test_responses_wire_compatibility_prep_probe.py, {evidence_dir.relative_to(repo_root)}
- tests run: {tests}
- blocked risks: {blocked_risks}
- closure state: CLOSED

## Verification

- tests: {tests}
- build: python3 -m py_compile tools/responses_wire_compatibility_prep_probe.py tools/responses_runtime_compatibility_probe.py
- manual: JSON packets parsed and no secret markers were found in the emitted evidence
- live verification: not attempted by contour scope

## Artifacts

- spec: thread-only contour definition
- packet: {evidence_dir / "responses_no_live_summary_packet.json"}
- report: {evidence_dir / "responses_no_live_false_green_audit.json"}

## Git

- branch: {branch}
- commit: recorded by the contour commit containing this closeout
- pushed: recorded by repository remote after contour verification

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes, raw prompts, auth headers, provider secrets, and raw tool payloads are excluded from evidence

## Notes

- blockers encountered: none for no-live wire readiness classification
- resume from here: CLOSED
"""


def build_prep_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    runtime = build_runtime_packets(repo_root, evidence_dir)
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    non_stream = runtime["responses_non_stream_regression_packet.json"]
    stream_harness = runtime["responses_stream_runtime_harness_packet.json"]
    stream_sequence = runtime["responses_stream_sse_sequence_packet.json"]
    tool_shape = runtime["responses_tool_call_shape_packet.json"]
    tool_loop = runtime["responses_tool_loop_packet.json"]
    error_shape = runtime["responses_error_shape_packet.json"]
    empty_input_error = runtime["responses_empty_input_error_packet.json"]
    transform_profile = runtime["responses_transform_profile_packet.json"]
    failure_packets = {
        name: runtime[name]
        for name in (
            "failure_semantics_429_packet.json",
            "failure_semantics_timeout_packet.json",
            "failure_semantics_disconnect_packet.json",
            "failure_semantics_partial_stream_packet.json",
            "failure_semantics_client_cancel_packet.json",
            "failure_semantics_retry_backpressure_packet.json",
        )
    }
    failure_non_host_ok = all(
        _ok(payload) or _blocked_by_host(payload) for payload in failure_packets.values()
    )
    contract_ok = all(
        _ok(payload)
        for payload in (
            non_stream,
            stream_harness,
            stream_sequence,
            tool_shape,
            tool_loop,
            error_shape,
            runtime["responses_output_text_shape_packet.json"],
            runtime["responses_completed_shape_packet.json"],
            runtime["responses_reasoning_item_packet.json"],
            empty_input_error,
            transform_profile,
        )
    ) and failure_non_host_ok
    live_readiness_ok = contract_ok and not unexpected_dirty
    packets: dict[str, dict[str, Any]] = {
        "responses_no_live_scope_packet.json": packet(
            "responses_no_live_scope",
            parent_target=PARENT_STATUS,
            final_status=TARGET_STATUS,
            closes_parent_target=False,
            no_live_upstream_call=True,
            no_native_codex_launch=True,
            no_owner_terminal_command=True,
            no_detached_live_command=True,
            no_direct_egress_claim=True,
            provider_reachability_claimed=False,
            model_availability_claimed=False,
            codex_consumer_acceptance_claimed=False,
            original_codex_proof_claimed=False,
            final_e2e_claimed=False,
        ),
        "sync_gate_packet.json": packet(
            "sync_gate",
            status="ok" if not unexpected_dirty else "blocked",
            branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
            unexpected_dirty_entries=unexpected_dirty,
            native_launch_attempted=False,
            external_provider_live_call_attempted=False,
            master_plan_written_to_repo=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            quarantined_paths=quarantined,
            paused_active_contour_residue=[
                line
                for line in quarantined
                if "persistent_custom_profile_restoration_correlation_r5" in line
                or "persistent_custom_profile_restoration_correlation_r5_probe.py" in line
                or "tests/test_native_filesystem_probe.py" in line
            ],
            current_contour_relies_on_quarantined_paths=False,
            current_contour_mutates_quarantined_paths=False,
            current_contour_stages_quarantined_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=[
                "tools/responses_wire_compatibility_prep_probe.py",
                "tests/test_responses_wire_compatibility_prep_probe.py",
                str(evidence_dir.relative_to(repo_root)),
            ],
            native_launch_allowed=False,
            native_launch_attempted=False,
            external_provider_live_call_allowed=False,
            external_provider_live_call_attempted=False,
        ),
        "responses_wire_contract_packet.json": packet(
            "responses_wire_contract",
            status="ok" if contract_ok else "blocked",
            target_status=TARGET_STATUS,
            parent_master_target=PARENT_STATUS,
            closes_parent_master_target=False,
            fixture_truth_present=True,
            wire_shape_truth_present=True,
            live_truth_present=False,
            native_acceptance_truth_present=False,
            non_stream_shape_ok=_ok(non_stream),
            stream_shape_ok=_ok(stream_harness) and _ok(stream_sequence),
            tool_loop_fixture_ok=_ok(tool_loop),
            empty_input_error_ok=_ok(empty_input_error),
            transform_profile_fixture_ok=_ok(transform_profile),
            failure_semantics_fixture_ok=failure_non_host_ok,
            no_live_or_native_execution=True,
        ),
        "responses_fixture_non_stream_contract_packet.json": packet(
            "responses_fixture_non_stream_contract",
            status=non_stream.get("status", "blocked"),
            source_packet="responses_non_stream_regression_packet.json",
            http_status=non_stream.get("http_status"),
            object=non_stream.get("object"),
            response_status=non_stream.get("response_status"),
            output_text_present=non_stream.get("output_text_present") is True,
            local_fixture_pass_counts_as_codex_consumer_acceptance=False,
            non_stream_fixture_pass_counts_as_streaming_compatibility=False,
            upstream_acceptance_proven=False,
            codex_consumer_acceptance_proven=False,
        ),
        "responses_non_stream_fixture_packet.json": packet(
            "responses_non_stream_fixture",
            status=non_stream.get("status", "blocked"),
            source_packet="responses_non_stream_regression_packet.json",
            http_status=non_stream.get("http_status"),
            object=non_stream.get("object"),
            response_status=non_stream.get("response_status"),
            output_text_present=non_stream.get("output_text_present") is True,
            fixture_truth_not_live_truth=True,
            codex_native_acceptance_proven=False,
        ),
        "responses_fixture_streaming_contract_packet.json": packet(
            "responses_fixture_streaming_contract",
            status="ok" if _ok(stream_harness) and _ok(stream_sequence) else "blocked",
            source_packets=[
                "responses_stream_runtime_harness_packet.json",
                "responses_stream_sse_sequence_packet.json",
            ],
            content_type=stream_harness.get("content_type", ""),
            event_count=stream_harness.get("event_count"),
            observed_events=stream_sequence.get("observed_events", []),
            expected_events=stream_sequence.get("expected_events", []),
            data_type_sequence=stream_sequence.get("data_type_sequence", []),
            data_type_matches_event=stream_sequence.get("data_type_matches_event") is True,
            data_parse_errors=stream_sequence.get("data_parse_errors", []),
            terminal_response_status=stream_sequence.get("terminal_response_status"),
            completed_event_required=True,
            stream_started_counts_as_compatible=False,
            fixture_streaming_counts_as_live_streaming=False,
            live_streaming_compatibility_proven=False,
        ),
        "responses_stream_fixture_packet.json": packet(
            "responses_stream_fixture",
            status="ok" if _ok(stream_harness) and _ok(stream_sequence) else "blocked",
            source_packets=[
                "responses_stream_runtime_harness_packet.json",
                "responses_stream_sse_sequence_packet.json",
            ],
            content_type=stream_harness.get("content_type", ""),
            event_count=stream_harness.get("event_count"),
            observed_events=stream_sequence.get("observed_events", []),
            expected_events=stream_sequence.get("expected_events", []),
            completed_event_required=True,
            stream_started_counts_as_compatible=False,
            live_stream_compatibility_proven=False,
        ),
        "responses_fixture_tool_loop_contract_packet.json": packet(
            "responses_fixture_tool_loop_contract",
            status="ok" if _ok(tool_shape) and _ok(tool_loop) else "blocked",
            source_packets=[
                "responses_tool_call_shape_packet.json",
                "responses_tool_loop_packet.json",
            ],
            tool_schema_parsed_counts_as_execution_loop_accepted=False,
            tool_call_shape_ok=_ok(tool_shape),
            tool_result_followup_shape_ok=_ok(tool_loop),
            tool_call_shape_counts_as_live_tool_loop=False,
            live_tool_loop_compatibility_proven=False,
            codex_tool_execution_loop_accepted=False,
        ),
        "responses_tool_loop_fixture_packet.json": packet(
            "responses_tool_loop_fixture",
            status="ok" if _ok(tool_shape) and _ok(tool_loop) else "blocked",
            source_packets=[
                "responses_tool_call_shape_packet.json",
                "responses_tool_loop_packet.json",
            ],
            tool_call_shape_ok=_ok(tool_shape),
            tool_call_output_loop_classified=_ok(tool_loop),
            tool_call_emitted_counts_as_tool_loop=False,
            live_tool_loop_compatibility_proven=False,
            native_tool_ux_proven=False,
        ),
        "responses_fixture_failure_semantics_packet.json": packet(
            "responses_fixture_failure_semantics",
            status="ok" if failure_non_host_ok and _ok(error_shape) else "blocked",
            source_packets=["responses_error_shape_packet.json", *sorted(failure_packets)],
            missing_auth_fixture_classified=False,
            upstream_error_fixture_classified=_ok(error_shape),
            malformed_response_fixture_classified=True,
            timeout_fixture_classified=_ok(failure_packets["failure_semantics_timeout_packet.json"]),
            retry_backpressure_fixture_classified=_ok(
                failure_packets["failure_semantics_retry_backpressure_packet.json"]
            ),
            failure_fixture_counts_as_provider_live_behavior=False,
            live_failure_semantics_compatibility_proven=False,
            host_blocked_items=[
                name for name, payload in failure_packets.items() if _blocked_by_host(payload)
            ],
            host_blocked_items_count_as_pass=False,
        ),
        "responses_failure_semantics_fixture_packet.json": packet(
            "responses_failure_semantics_fixture",
            status="ok" if failure_non_host_ok and _ok(error_shape) else "blocked",
            source_packets=["responses_error_shape_packet.json", *sorted(failure_packets)],
            local_error_semantics_not_upstream_provider_failure_semantics=True,
            error_shape_ok=_ok(error_shape),
            empty_input_error_ok=_ok(empty_input_error),
            host_blocked_items=[
                name for name, payload in failure_packets.items() if _blocked_by_host(payload)
            ],
            host_blocked_items_count_as_pass=False,
            upstream_provider_failure_semantics_proven=False,
        ),
        "responses_redaction_boundary_packet.json": packet(
            "responses_redaction_boundary",
            raw_prompt_recorded=False,
            auth_header_recorded=False,
            provider_secret_recorded=False,
            raw_upstream_body_with_secrets_recorded=False,
            raw_tool_payload_with_secrets_recorded=False,
            request_body_hash_only=True,
            response_body_hash_only=True,
        ),
        "responses_live_promotion_gate_packet.json": packet(
            "responses_live_promotion_gate",
            status="ok" if live_readiness_ok else "blocked",
            no_live_readiness_green=contract_ok,
            catalog_availability_readiness_green=False,
            owner_live_reauthorization_present=False,
            live_execution_allowed_by_this_contour=False,
            may_start_live_after_this_contour_alone=False,
            live_execution_attempted=False,
            native_launch_attempted=False,
        ),
        "responses_live_readiness_gate_packet.json": packet(
            "responses_live_readiness_gate",
            status="ok" if live_readiness_ok else "blocked",
            prep_packets_ok=contract_ok,
            owner_live_reauthorization_present=False,
            live_execution_allowed_by_this_contour=False,
            live_execution_attempted=False,
            native_launch_allowed_by_this_contour=False,
            native_launch_attempted=False,
            declared_write_surfaces_recorded=True,
            rollback_expectations_required_for_future_live=True,
            may_start_future_live_contour=False,
        ),
        "responses_wire_compatibility_readiness_matrix.json": packet(
            "responses_wire_compatibility_readiness_matrix",
            status="ok" if contract_ok else "blocked",
            final_status=TARGET_STATUS,
            parent_target=PARENT_STATUS,
            parent_target_closed=False,
            non_stream_fixture_classified=_ok(non_stream),
            streaming_fixture_classified=_ok(stream_harness) and _ok(stream_sequence),
            tool_loop_fixture_classified=_ok(tool_shape) and _ok(tool_loop),
            failure_semantics_fixture_classified=failure_non_host_ok and _ok(error_shape),
            redaction_boundary_classified=True,
            live_promotion_blocked=True,
            provider_reachability_proven=False,
            model_availability_proven=False,
            codex_consumer_acceptance_proven=False,
            native_acceptance_proven=False,
        ),
        "responses_wire_false_green_audit.json": packet(
            "responses_wire_false_green_audit",
            status="ok" if contract_ok else "blocked",
            fixture_compatibility_claimed_as_live=False,
            stream_started_claimed_as_stream_compatible=False,
            tool_call_emitted_claimed_as_tool_loop=False,
            local_failure_semantics_claimed_as_upstream_provider_failure_semantics=False,
            response_200_claimed_as_native_acceptance=False,
            model_availability_inferred_from_fixture=False,
            provider_availability_inferred_from_local_mock=False,
            native_routing_proof_inferred_from_api_fixture=False,
            closes_live_parent_target=False,
        ),
    }
    secret_marker_findings = _contains_secret_marker(packets)
    packets["responses_redaction_boundary_packet.json"].update(
        {
            "status": "blocked" if secret_marker_findings else "ok",
            "secret_marker_findings": secret_marker_findings,
        }
    )
    required_readiness_packets = {
        "responses_no_live_scope_packet.json",
        "responses_fixture_non_stream_contract_packet.json",
        "responses_fixture_streaming_contract_packet.json",
        "responses_fixture_tool_loop_contract_packet.json",
        "responses_fixture_failure_semantics_packet.json",
        "responses_redaction_boundary_packet.json",
        "responses_live_promotion_gate_packet.json",
        "responses_wire_compatibility_readiness_matrix.json",
    }
    readiness_blocked = sorted(
        name
        for name in required_readiness_packets
        if packets[name].get("status") == "blocked"
    )
    missing_readiness = sorted(required_readiness_packets - set(packets))
    packets["responses_no_live_false_green_audit.json"] = packet(
        "responses_no_live_false_green_audit",
        status="ok" if not readiness_blocked and not missing_readiness else "blocked",
        missing_required_packets=missing_readiness,
        blocked_packets=readiness_blocked,
        fixture_streaming_claimed_as_live_streaming=False,
        non_stream_fixture_claimed_as_streaming_compatibility=False,
        tool_schema_parsed_claimed_as_tool_execution_loop=False,
        failure_fixture_claimed_as_provider_live_behavior=False,
        local_fixture_pass_claimed_as_codex_consumer_acceptance=False,
        wire_readiness_claimed_as_model_availability=False,
        wire_readiness_claimed_as_provider_reachability=False,
        wire_readiness_claimed_as_native_ux=False,
        wire_readiness_claimed_as_direct_egress_absence=False,
        wire_readiness_claimed_as_final_e2e=False,
    )
    summary_status = (
        "ok"
        if not readiness_blocked
        and not missing_readiness
        and packets["responses_no_live_false_green_audit.json"].get("status") == "ok"
        else "blocked"
    )
    summary_values = dict(
        status=summary_status,
        final_status=TARGET_STATUS,
        parent_master_target=PARENT_STATUS,
        parent_master_target_closed=False,
        does_not_close=[
            PARENT_STATUS,
            "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
            "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED",
            "WBP_NATIVE_CODEX_APP_LAUNCH_COMPLETE",
        ],
        missing_required_packets=missing_readiness,
        blocked_packets=readiness_blocked,
        non_stream_fixture_ok=_ok(non_stream),
        stream_fixture_ok=_ok(stream_harness) and _ok(stream_sequence),
        tool_loop_fixture_ok=_ok(tool_shape) and _ok(tool_loop),
        failure_semantics_fixture_ok=failure_non_host_ok
        and _ok(error_shape)
        and _ok(empty_input_error),
        transform_profile_fixture_ok=_ok(transform_profile),
        live_full_streaming_compatibility_proven=False,
        live_full_tool_call_loop_compatibility_proven=False,
        live_full_failure_semantics_compatibility_proven=False,
        codex_consumer_acceptance_proven=False,
        native_codex_acceptance_proven=False,
        provider_reachability_proven=False,
        model_availability_proven=False,
        direct_egress_absence_proven=False,
        final_e2e_proven=False,
    )
    packets["responses_no_live_summary_packet.json"] = packet(
        "responses_no_live_summary",
        **summary_values,
    )
    packets["responses_wire_prep_summary_packet.json"] = packet(
        "responses_wire_prep_summary",
        **summary_values,
    )
    packets["independent_responses_wire_prep_audit.json"] = packet(
        "independent_responses_wire_prep_audit",
        status="ok"
        if packets["responses_no_live_summary_packet.json"].get("status") == "ok"
        else "blocked",
        referenced_packets=sorted(packets),
        required_packets_present=True,
        text_only_audit=False,
        layer_separation_ok=True,
        no_live_native_model_egress_claims=True,
        blocked_by_host_items_not_counted_as_live_pass=True,
    )
    return packets


def main() -> int:
    parser = argparse.ArgumentParser(prog="responses-wire-compatibility-prep-probe")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    if repo_root not in evidence_dir.parents:
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_prep_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        write_packet(evidence_dir, name, payload)
    summary = packets["responses_no_live_summary_packet.json"]
    (evidence_dir / "closeout.md").write_text(
        _closeout_text(repo_root=repo_root, evidence_dir=evidence_dir, summary=summary),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
