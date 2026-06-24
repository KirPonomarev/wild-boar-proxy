# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Machine-readable acceptance join for GPT+API/DIP Custom Codex feature truth.

This module intentionally joins existing proof packets. It does not run live
dispatch, does not infer from logs/history, and does not upgrade product
readiness.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_READ
from .core import packets
from .runtime_dispatch_mode_truth import (
    DISPATCH_MODE_CHATGPT_API,
    EXECUTOR_DIP_API_ROUTE,
    ORCHESTRATOR_CHATGPT,
    dispatch_mode_truth_fields,
)
from .runtime import RuntimePaths, write_json_atomic


GPT_API_DIP_ACCEPTANCE_PACKET_KIND = "wbp_gpt_api_dip_acceptance_gate"
GPT_API_DIP_ACCEPTANCE_FILE_NAME = "gpt-api-dip-acceptance-gate.packet.json"
GPT_API_DIP_ACCEPTANCE_OK = "OK"
GPT_API_DIP_ACCEPTANCE_BLOCKED = "WBP_GPT_API_DIP_ACCEPTANCE_BLOCKED"
GPT_API_DIP_ACCEPTANCE_INPUT_INVALID = "WBP_GPT_API_DIP_ACCEPTANCE_INPUT_INVALID"
GPT_API_DIP_ACCEPTANCE_UNSAFE_PACKET = "WBP_GPT_API_DIP_ACCEPTANCE_UNSAFE_PACKET"
_FRESH_SEALED_PACKET_KIND = "wbp_fresh_sealed_e2e_proof"
_DIP_FEATURE_PACKET_KIND = "wbp_repeatable_real_custom_dip_proof_runner"
_DIP_ACTION_PACKET_KIND = "wbp_dip_working_tool_run"

_COMMON_REQUIRED_FALSE_BOOL_FIELDS = (
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
)

_FRESH_REQUIRED_FALSE_BOOL_FIELDS = (
    *_COMMON_REQUIRED_FALSE_BOOL_FIELDS,
    "codex_native_subagent_used_as_dip",
    "raw_jsonl_recorded",
    "tool_call_arguments_recorded",
    "route_candidate_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
)

_DIP_FEATURE_REQUIRED_FALSE_BOOL_FIELDS = (
    *_COMMON_REQUIRED_FALSE_BOOL_FIELDS,
    "codex_native_subagent_used_as_dip",
    "raw_task_recorded",
    "tool_call_arguments_recorded",
    "command_argv_recorded",
    "codex_stdout_recorded",
    "codex_stderr_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "live_result_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
)

_DIP_ACTION_REQUIRED_FALSE_BOOL_FIELDS = (
    *_COMMON_REQUIRED_FALSE_BOOL_FIELDS,
    "command_argv_recorded",
    "codex_stdout_recorded",
    "codex_stderr_recorded",
    "live_result_route_id_recorded",
    "live_result_raw_backend_details_exposed",
    "live_result_secret_value_exposed",
    "wrapper_substitution_used",
    "wrapper_substitution_detected",
    "wrapper_substitution_allowed",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_packet(path: str | Path | None) -> tuple[dict[str, Any], str, str]:
    if path is None or not str(path).strip():
        return {}, "", "missing_path"
    packet_path = Path(path).expanduser()
    try:
        data = json.loads(packet_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, "", "file_missing"
    except json.JSONDecodeError:
        return {}, "", "invalid_json"
    if not isinstance(data, dict):
        return {}, "", "not_json_object"
    return data, _sha256_file(packet_path), ""


def _check_true(
    packet: dict[str, Any],
    field: str,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) is not True:
        failures.append(f"{prefix}_{field}_not_true")


def _check_false(
    packet: dict[str, Any],
    field: str,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) is not False:
        failures.append(f"{prefix}_{field}_not_false")


def _check_equals(
    packet: dict[str, Any],
    field: str,
    expected: object,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) != expected:
        failures.append(f"{prefix}_{field}_not_expected")


def _check_empty_list(
    packet: dict[str, Any],
    field: str,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) != []:
        failures.append(f"{prefix}_{field}_not_empty")


def _check_common_no_overclaim(
    packet: dict[str, Any],
    failures: list[str],
    prefix: str,
    *,
    required_false_fields: tuple[str, ...],
) -> None:
    _check_false(packet, "product_ready", failures, prefix)
    for field in required_false_fields:
        _check_false(packet, field, failures, prefix)


def _fresh_sealed_failures(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    _check_equals(
        packet,
        "packet_kind",
        _FRESH_SEALED_PACKET_KIND,
        failures,
        "fresh_sealed",
    )
    for field in (
        "fresh_sealed_e2e_proven",
        "fresh_runtime_proof_sealed",
        "core_dispatch_proven",
        "core_runtime_proof_sealed",
        "fresh_live_custom_codex_e2e_proven",
        "full_runtime_diagnostics_passed",
        "native_custom_codex_visible_flow_proven",
        "full_runtime_dispatch_proven",
        "custom_codex_flow_proven",
        "user_prompt_submit_hook_ran",
        "api_lane_called",
        "dispatch_proven",
        "codex_working_flow_delivery_proven",
        "custom_codex_ui_visibility_proven",
        "strict_admission_proven",
        "external_freshness_proven",
        "proof_admission_sealed",
        "feature_runtime_proof_sealed",
        "wrong_digest_negative_proven",
        "freshness_anchor_bound_to_runner",
        "freshness_anchor_bound_to_admission",
        "freshness_anchor_bound_to_seal",
    ):
        _check_true(packet, field, failures, "fresh_sealed")
    _check_equals(packet, "status", "ok", failures, "fresh_sealed")
    _check_equals(packet, "machine_error_code", "OK", failures, "fresh_sealed")
    _check_empty_list(packet, "blocking_reasons", failures, "fresh_sealed")
    _check_empty_list(
        packet,
        "full_runtime_diagnostic_blocking_reasons",
        failures,
        "fresh_sealed",
    )
    _check_common_no_overclaim(
        packet,
        failures,
        "fresh_sealed",
        required_false_fields=_FRESH_REQUIRED_FALSE_BOOL_FIELDS,
    )
    return failures


def _dip_feature_failures(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    _check_equals(
        packet,
        "packet_kind",
        _DIP_FEATURE_PACKET_KIND,
        failures,
        "dip_feature",
    )
    for field in (
        "api_backed_custom_codex_auth_session_proven",
        "api_backed_custom_codex_flow_proven",
        "api_backed_custom_codex_flow_is_not_ui_session",
        "custom_codex_dip_feature_ready",
        "feature_ready",
        "feature_ready_does_not_require_ui_session",
        "feature_ready_does_not_prove_product_ready",
        "api_key_only",
        "auth_session_api_key_only",
        "auth_session_hook_ready",
        "auth_session_expected_user_data_observed",
        "auth_session_app_server_bound_to_expected_user_data",
        "work_mode_proven",
        "work_mode_uses_full_dip_work_mode",
        "delegate_to_dip_proven",
        "api_lane_called",
        "route_bound_dispatch_proven",
        "live_result_available",
        "direct_provider_auth_proven",
        "direct_provider_response_observed",
        "provider_auth_ok",
        "positive_provider_proof_gate_satisfied",
    ):
        _check_true(packet, field, failures, "dip_feature")
    _check_equals(packet, "status", "ok", failures, "dip_feature")
    _check_equals(packet, "machine_error_code", "OK", failures, "dip_feature")
    _check_equals(
        packet,
        "feature_ready_mode",
        "api_key_backed_custom_codex_dip",
        failures,
        "dip_feature",
    )
    _check_equals(
        packet,
        "auth_session_machine_error_code",
        "WBP_CUSTOM_CODEX_API_KEY_ONLY",
        failures,
        "dip_feature",
    )
    for field in (
        "api_key_only_counts_as_ui_session",
        "auth_session_logged_in_ui_session_proven",
        "logged_in_ui_session_proven",
        "custom_codex_ui_session_ready",
        "custom_codex_ui_visibility_proven",
        "delivery_counts_as_custom_codex_ui",
    ):
        _check_false(packet, field, failures, "dip_feature")
    _check_empty_list(packet, "blocking_reasons", failures, "dip_feature")
    _check_empty_list(
        packet,
        "api_backed_custom_codex_gate_failures",
        failures,
        "dip_feature",
    )
    _check_common_no_overclaim(
        packet,
        failures,
        "dip_feature",
        required_false_fields=_DIP_FEATURE_REQUIRED_FALSE_BOOL_FIELDS,
    )
    return failures


def _dip_action_failures(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    _check_equals(
        packet,
        "packet_kind",
        _DIP_ACTION_PACKET_KIND,
        failures,
        "dip_action",
    )
    for field in (
        "delegate_to_dip_proven",
        "api_lane_called",
        "route_bound_dispatch_proven",
        "live_result_available",
        "direct_provider_auth_proven",
        "direct_provider_response_observed",
        "provider_auth_ok",
        "positive_provider_proof_gate_satisfied",
        "dip_repo_tool_bridge_required",
        "dip_repo_tool_bridge_available",
        "dip_repo_tool_bridge_used",
        "dip_action_bridge_required",
        "dip_action_bridge_available",
        "dip_action_bridge_used",
        "dip_action_mutation_applied",
        "dip_action_tests_run",
        "dip_action_patch_applied",
        "dip_code_written",
        "dip_code_patch_applied",
        "dip_code_verified",
        "repo_bridge_mutation_allowed",
        "repo_bridge_mutation_controlled",
        "runtime_dispatch_mode_truth_recorded",
        "dispatch_mode_truth_proven",
        "chatgpt_plus_api_mode_proven",
        "gpt_api_mode_proven",
        "chatgpt_lane_selected",
        "api_route_selected",
        "chatgpt_lane_called",
        "api_route_called",
    ):
        _check_true(packet, field, failures, "dip_action")
    _check_equals(
        packet,
        "execution_mode",
        DISPATCH_MODE_CHATGPT_API,
        failures,
        "dip_action",
    )
    _check_equals(
        packet,
        "selected_mode",
        DISPATCH_MODE_CHATGPT_API,
        failures,
        "dip_action",
    )
    _check_equals(
        packet,
        "orchestrator",
        ORCHESTRATOR_CHATGPT,
        failures,
        "dip_action",
    )
    _check_equals(
        packet,
        "executor",
        EXECUTOR_DIP_API_ROUTE,
        failures,
        "dip_action",
    )
    _check_equals(packet, "status", "ok", failures, "dip_action")
    _check_equals(packet, "machine_error_code", "OK", failures, "dip_action")
    if int(packet.get("dip_action_successful_tool_call_count") or 0) <= 0:
        failures.append("dip_action_successful_tool_call_count_not_positive")
    if int(packet.get("repo_bridge_successful_tool_call_count") or 0) <= 0:
        failures.append("dip_action_repo_bridge_successful_tool_call_count_not_positive")
    _check_false(packet, "dip_repo_direct_access", failures, "dip_action")
    _check_false(packet, "repo_bridge_readonly", failures, "dip_action")
    _check_false(packet, "repo_bridge_direct_shell_access", failures, "dip_action")
    _check_false(packet, "dip_action_raw_patch_recorded", failures, "dip_action")
    _check_false(packet, "dip_action_raw_command_recorded", failures, "dip_action")
    _check_false(packet, "repo_bridge_context_pack_recorded", failures, "dip_action")
    _check_false(packet, "repo_bridge_raw_tool_results_recorded", failures, "dip_action")
    _check_common_no_overclaim(
        packet,
        failures,
        "dip_action",
        required_false_fields=_DIP_ACTION_REQUIRED_FALSE_BOOL_FIELDS,
    )
    return failures


def build_gpt_api_dip_acceptance_gate_packet(
    *,
    fresh_sealed_packet: dict[str, Any],
    dip_feature_packet: dict[str, Any],
    dip_action_packet: dict[str, Any],
    fresh_sealed_sha256: str = "",
    dip_feature_sha256: str = "",
    dip_action_sha256: str = "",
    input_failures: list[str] | None = None,
    evidence_written: bool = False,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    input_failures = input_failures or []
    fresh_failures = _fresh_sealed_failures(fresh_sealed_packet) if fresh_sealed_packet else []
    feature_failures = _dip_feature_failures(dip_feature_packet) if dip_feature_packet else []
    action_failures = _dip_action_failures(dip_action_packet) if dip_action_packet else []
    if not fresh_sealed_packet:
        fresh_failures.append("fresh_sealed_packet_missing")
    if not dip_feature_packet:
        feature_failures.append("dip_feature_packet_missing")
    if not dip_action_packet:
        action_failures.append("dip_action_packet_missing")
    blocking_reasons = sorted(
        set(input_failures + fresh_failures + feature_failures + action_failures)
    )
    unsafe = any(
        packets.command_packet_has_secret_leak(packet)
        for packet in (fresh_sealed_packet, dip_feature_packet, dip_action_packet)
        if packet
    )
    if unsafe:
        blocking_reasons.append("acceptance_input_packet_secret_leak")
    ok = not blocking_reasons
    extra = {
        "schema_version": 1,
        "packet_kind": GPT_API_DIP_ACCEPTANCE_PACKET_KIND,
        "proof_scope": "gpt_api_dip_custom_codex_technical_acceptance_gate",
        "operator_command_surface": "wild-boar-proxy codex-runner gpt-api-dip-acceptance-gate",
        "operator_command_mode": "join",
        "gate_source": "existing_machine_readable_proof_packets",
        "gate_runs_live_dispatch": False,
        "gate_reads_audit_history": False,
        "feature_ready": ok,
        "feature_ready_mode": "gpt_api_dip_custom_codex" if ok else "blocked",
        "gpt_api_dip_ready": ok,
        **dispatch_mode_truth_fields(
            execution_mode=DISPATCH_MODE_CHATGPT_API,
            truth_source="gpt_api_dip_acceptance_gate_join",
            orchestrator=ORCHESTRATOR_CHATGPT,
            executor=EXECUTOR_DIP_API_ROUTE,
            mode_proven=ok,
            chatgpt_lane_selected=dip_action_packet.get("chatgpt_lane_selected") is True,
            api_route_selected=dip_action_packet.get("api_route_selected") is True,
            chatgpt_lane_called=dip_action_packet.get("chatgpt_lane_called") is True,
            api_route_called=dip_action_packet.get("api_route_called") is True,
            target_repo_required=dip_action_packet.get("target_repo_required") is True,
            target_repo_available=dip_action_packet.get("target_repo_available") is True,
            target_repo_fallback_used=dip_action_packet.get("target_repo_fallback_used")
            is True,
        ),
        "dip_action_bridge_proven": not action_failures,
        "dip_code_written": dip_action_packet.get("dip_code_written") is True,
        "dip_code_verified": dip_action_packet.get("dip_code_verified") is True,
        "custom_codex_ui_visibility_proven": (
            fresh_sealed_packet.get("custom_codex_ui_visibility_proven") is True
        ),
        "native_custom_codex_visible_flow_proven": (
            fresh_sealed_packet.get("native_custom_codex_visible_flow_proven") is True
        ),
        "full_runtime_dispatch_proven": (
            fresh_sealed_packet.get("full_runtime_dispatch_proven") is True
        ),
        "fresh_sealed_e2e_proven": (
            fresh_sealed_packet.get("fresh_sealed_e2e_proven") is True
        ),
        "api_backed_custom_codex_dip_feature_ready": (
            dip_feature_packet.get("custom_codex_dip_feature_ready") is True
        ),
        "api_backed_custom_codex_auth_session_proven": (
            dip_feature_packet.get("api_backed_custom_codex_auth_session_proven")
            is True
        ),
        "api_key_only": dip_feature_packet.get("api_key_only") is True,
        "api_key_only_counts_as_ui_session": False,
        "logged_in_ui_session_proven": False,
        "custom_codex_ui_session_ready": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "fresh_sealed_packet_sha256": fresh_sealed_sha256,
        "dip_feature_packet_sha256": dip_feature_sha256,
        "dip_action_packet_sha256": dip_action_sha256,
        "input_file_paths_recorded": False,
        "fresh_sealed_failures": fresh_failures,
        "dip_feature_failures": feature_failures,
        "dip_action_failures": action_failures,
        "blocking_reasons": blocking_reasons,
        "evidence_written": evidence_written,
        "created_at_utc": _utc_now(),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP GPT+API/DIP technical acceptance gate passed."
            if ok
            else "WBP GPT+API/DIP technical acceptance gate is BLOCKED."
        ),
        machine_error_code=(
            GPT_API_DIP_ACCEPTANCE_OK
            if ok
            else GPT_API_DIP_ACCEPTANCE_UNSAFE_PACKET
            if unsafe
            else GPT_API_DIP_ACCEPTANCE_BLOCKED
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files or [],
        effect=EFFECT_MUTATE if evidence_written else EFFECT_READ,
        extra=extra,
    )


def run_gpt_api_dip_acceptance_gate_command(
    *,
    paths: RuntimePaths,
    fresh_sealed_proof_file: str,
    dip_feature_proof_file: str,
    dip_action_proof_file: str,
    proof_dir: str | None = None,
) -> dict[str, Any]:
    del paths
    fresh, fresh_sha, fresh_error = _load_json_packet(fresh_sealed_proof_file)
    feature, feature_sha, feature_error = _load_json_packet(dip_feature_proof_file)
    action, action_sha, action_error = _load_json_packet(dip_action_proof_file)
    input_failures = []
    for prefix, error in (
        ("fresh_sealed", fresh_error),
        ("dip_feature", feature_error),
        ("dip_action", action_error),
    ):
        if error:
            input_failures.append(f"{prefix}_{error}")
    changed_files: list[str] = []
    evidence_written = False
    packet = build_gpt_api_dip_acceptance_gate_packet(
        fresh_sealed_packet=fresh,
        dip_feature_packet=feature,
        dip_action_packet=action,
        fresh_sealed_sha256=fresh_sha,
        dip_feature_sha256=feature_sha,
        dip_action_sha256=action_sha,
        input_failures=input_failures,
        evidence_written=False,
        changed_files=[],
    )
    if proof_dir:
        output_dir = Path(proof_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / GPT_API_DIP_ACCEPTANCE_FILE_NAME
        evidence_written = True
        changed_files = [str(output_file)]
        packet = build_gpt_api_dip_acceptance_gate_packet(
            fresh_sealed_packet=fresh,
            dip_feature_packet=feature,
            dip_action_packet=action,
            fresh_sealed_sha256=fresh_sha,
            dip_feature_sha256=feature_sha,
            dip_action_sha256=action_sha,
            input_failures=input_failures,
            evidence_written=evidence_written,
            changed_files=changed_files,
        )
        write_json_atomic(output_file, packet)
    return packet
