# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end dispatch mode matrix gate.

This module joins existing machine-readable proof packets. It does not run live
dispatch, does not invoke DIP, and does not infer success from chat narrative.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .command_effects import EFFECT_MUTATE, EFFECT_READ
from .core import packets
from .runtime import RuntimePaths, write_json_atomic
from .runtime_dispatch_mode_truth import (
    DISPATCH_MODE_API_ONLY,
    DISPATCH_MODE_CHATGPT_API,
    DISPATCH_MODE_CHATGPT_ONLY,
    EXECUTOR_API_ROUTE,
    EXECUTOR_CHATGPT,
    EXECUTOR_DIP_API_ROUTE,
    ORCHESTRATOR_API_ROUTE,
    ORCHESTRATOR_CHATGPT,
)


E2E_MODE_MATRIX_PACKET_KIND = "wbp_e2e_mode_matrix"
E2E_MODE_MATRIX_FILE_NAME = "e2e-mode-matrix.packet.json"
E2E_MODE_MATRIX_OK = "OK"
E2E_MODE_MATRIX_BLOCKED = "WBP_E2E_MODE_MATRIX_BLOCKED"
E2E_MODE_MATRIX_UNSAFE_PACKET = "WBP_E2E_MODE_MATRIX_UNSAFE_PACKET"

GPT_PACKET_KIND = "custom_codex_native_response_matrix"
API_PACKET_KIND = "wbp_controlled_api_dispatch_proof"
GPT_API_PACKET_KIND = "wbp_gpt_api_dip_acceptance_gate"
DIP_PACKET_KIND = "wbp_dip_working_tool_run"

ROW_GPT = "gpt"
ROW_API = "api"
ROW_GPT_API = "gpt_api"
ROW_DIP_PING = "dip_ping"
ROW_DIP_REPO_AUDIT_DUMMY = "dip_repo_audit_dummy"
ROW_DIP_REPO_AUDIT_WBP = "dip_repo_audit_wbp"
ROW_DIP_CODE_EDIT_TESTS_DUMMY = "dip_code_edit_tests_dummy"

REQUIRED_ROWS = (
    ROW_GPT,
    ROW_API,
    ROW_GPT_API,
    ROW_DIP_PING,
    ROW_DIP_REPO_AUDIT_DUMMY,
    ROW_DIP_REPO_AUDIT_WBP,
    ROW_DIP_CODE_EDIT_TESTS_DUMMY,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_text(value: object, *, limit: int = 160) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
    packet: Mapping[str, Any],
    field: str,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) is not True:
        failures.append(f"{prefix}_{field}_not_true")


def _check_false(
    packet: Mapping[str, Any],
    field: str,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) is not False:
        failures.append(f"{prefix}_{field}_not_false")


def _check_equals(
    packet: Mapping[str, Any],
    field: str,
    expected: object,
    failures: list[str],
    prefix: str,
) -> None:
    if packet.get(field) != expected:
        failures.append(f"{prefix}_{field}_not_expected")


def _check_positive_int(
    packet: Mapping[str, Any],
    field: str,
    failures: list[str],
    prefix: str,
) -> None:
    if _safe_int(packet.get(field)) <= 0:
        failures.append(f"{prefix}_{field}_not_positive")


def _check_common_packet(
    packet: Mapping[str, Any],
    failures: list[str],
    prefix: str,
    *,
    expected_kind: str,
    expected_mode: str,
    expected_orchestrator: str,
    expected_executor: str,
    chatgpt_lane_called: bool,
    api_route_called: bool,
) -> None:
    _check_equals(packet, "packet_kind", expected_kind, failures, prefix)
    _check_equals(packet, "status", "ok", failures, prefix)
    _check_equals(packet, "machine_error_code", "OK", failures, prefix)
    _check_true(packet, "runtime_dispatch_mode_truth_recorded", failures, prefix)
    _check_true(packet, "dispatch_mode_truth_proven", failures, prefix)
    _check_equals(packet, "execution_mode", expected_mode, failures, prefix)
    _check_equals(packet, "selected_mode", expected_mode, failures, prefix)
    _check_equals(packet, "orchestrator", expected_orchestrator, failures, prefix)
    _check_equals(packet, "executor", expected_executor, failures, prefix)
    _check_equals(
        packet,
        "chatgpt_lane_called",
        chatgpt_lane_called,
        failures,
        prefix,
    )
    _check_equals(
        packet,
        "api_route_called",
        api_route_called,
        failures,
        prefix,
    )
    _check_equals(
        packet,
        "chatgpt_lane_selected",
        chatgpt_lane_called,
        failures,
        prefix,
    )
    _check_equals(
        packet,
        "api_route_selected",
        api_route_called,
        failures,
        prefix,
    )


def _check_base_safety(
    packet: Mapping[str, Any],
    failures: list[str],
    prefix: str,
) -> None:
    for field in (
        "product_ready",
        "fallback_used",
        "local_imitation_used",
        "raw_prompt_recorded",
        "prompt_text_recorded",
        "raw_backend_details_exposed",
        "secret_value_exposed",
        "active_project_root_path_recorded",
        "active_project_root_fallback_used",
        "wrapper_substitution_used",
        "wrapper_substitution_detected",
        "wrapper_substitution_allowed",
    ):
        _check_false(packet, field, failures, prefix)


def _check_active_project_root(
    packet: Mapping[str, Any],
    failures: list[str],
    prefix: str,
    *,
    required: bool,
    available: bool,
    is_wbp_repo: bool | None = None,
) -> None:
    _check_equals(
        packet,
        "active_project_root_required",
        required,
        failures,
        prefix,
    )
    _check_equals(
        packet,
        "active_project_root_available",
        available,
        failures,
        prefix,
    )
    _check_false(packet, "active_project_root_path_recorded", failures, prefix)
    _check_false(packet, "active_project_root_fallback_used", failures, prefix)
    _check_false(
        packet,
        "active_project_root_legacy_target_repo_alias_used",
        failures,
        prefix,
    )
    if required:
        _check_equals(packet, "active_project_root_status", "ok", failures, prefix)
        if not _safe_text(packet.get("active_project_root_sha256")):
            failures.append(f"{prefix}_active_project_root_sha256_missing")
    if is_wbp_repo is not None:
        _check_equals(
            packet,
            "active_project_root_is_wbp_repo",
            is_wbp_repo,
            failures,
            prefix,
        )


def _check_target_repo(
    packet: Mapping[str, Any],
    failures: list[str],
    prefix: str,
    *,
    required: bool,
    available: bool,
    is_wbp_repo: bool | None = None,
) -> None:
    _check_equals(packet, "target_repo_required", required, failures, prefix)
    _check_equals(packet, "target_repo_available", available, failures, prefix)
    _check_false(packet, "target_repo_path_recorded", failures, prefix)
    _check_false(packet, "target_repo_fallback_used", failures, prefix)
    if required:
        _check_equals(packet, "target_repo_status", "ok", failures, prefix)
        if not _safe_text(packet.get("target_repo_sha256")):
            failures.append(f"{prefix}_target_repo_sha256_missing")
    if is_wbp_repo is not None:
        _check_equals(packet, "target_repo_is_wbp_repo", is_wbp_repo, failures, prefix)


def _gpt_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    prefix = ROW_GPT
    _check_common_packet(
        packet,
        failures,
        prefix,
        expected_kind=GPT_PACKET_KIND,
        expected_mode=DISPATCH_MODE_CHATGPT_ONLY,
        expected_orchestrator=ORCHESTRATOR_CHATGPT,
        expected_executor=EXECUTOR_CHATGPT,
        chatgpt_lane_called=True,
        api_route_called=False,
    )
    _check_true(packet, "native_response_matrix_proven", failures, prefix)
    _check_positive_int(packet, "positive_case_count", failures, prefix)
    _check_true(packet, "chatgpt_only_mode_proven", failures, prefix)
    _check_false(packet, "api_only_mode_proven", failures, prefix)
    _check_false(packet, "gpt_api_mode_proven", failures, prefix)
    _check_base_safety(packet, failures, prefix)
    for field in (
        "raw_dom_exposed",
        "text_value_captured",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
    ):
        _check_false(packet, field, failures, prefix)
    return failures


def _api_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    prefix = ROW_API
    _check_common_packet(
        packet,
        failures,
        prefix,
        expected_kind=API_PACKET_KIND,
        expected_mode=DISPATCH_MODE_API_ONLY,
        expected_orchestrator=ORCHESTRATOR_API_ROUTE,
        expected_executor=EXECUTOR_API_ROUTE,
        chatgpt_lane_called=False,
        api_route_called=True,
    )
    for field in (
        "dispatch_proven",
        "router_dispatch_admitted",
        "api_lane_adapter_called",
        "api_lane_dispatch_admitted",
        "route_bound_dispatch_attempted",
        "route_bound_dispatch_proven",
        "controlled_provider_called",
        "controlled_provider_response_proven",
        "provider_response_proven",
    ):
        _check_true(packet, field, failures, prefix)
    _check_true(packet, "api_only_mode_proven", failures, prefix)
    _check_false(packet, "chatgpt_only_mode_proven", failures, prefix)
    _check_false(packet, "gpt_api_mode_proven", failures, prefix)
    _check_base_safety(packet, failures, prefix)
    for field in (
        "route_candidate_recorded",
        "selected_api_route_id_recorded",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
        "state_written",
        "evidence_written",
        "file_mutation_attempted",
        "native_codex_subagent_used_as_dip",
    ):
        _check_false(packet, field, failures, prefix)
    return failures


def _gpt_api_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    prefix = ROW_GPT_API
    _check_common_packet(
        packet,
        failures,
        prefix,
        expected_kind=GPT_API_PACKET_KIND,
        expected_mode=DISPATCH_MODE_CHATGPT_API,
        expected_orchestrator=ORCHESTRATOR_CHATGPT,
        expected_executor=EXECUTOR_DIP_API_ROUTE,
        chatgpt_lane_called=True,
        api_route_called=True,
    )
    for field in (
        "feature_ready",
        "gpt_api_dip_ready",
        "dip_action_bridge_proven",
        "dip_code_written",
        "dip_code_verified",
        "api_backed_custom_codex_dip_feature_ready",
        "gpt_api_mode_proven",
    ):
        _check_true(packet, field, failures, prefix)
    _check_false(packet, "chatgpt_only_mode_proven", failures, prefix)
    _check_false(packet, "api_only_mode_proven", failures, prefix)
    _check_base_safety(packet, failures, prefix)
    _check_active_project_root(
        packet,
        failures,
        prefix,
        required=True,
        available=True,
    )
    for field in (
        "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip",
        "raw_jsonl_recorded",
        "tool_call_arguments_recorded",
        "raw_route_id_recorded",
        "selected_api_route_id_recorded",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
    ):
        _check_false(packet, field, failures, prefix)
    if packet.get("blocking_reasons") != []:
        failures.append(f"{prefix}_blocking_reasons_not_empty")
    return failures


def _check_dip_common(packet: Mapping[str, Any], failures: list[str], prefix: str) -> None:
    _check_common_packet(
        packet,
        failures,
        prefix,
        expected_kind=DIP_PACKET_KIND,
        expected_mode=DISPATCH_MODE_CHATGPT_API,
        expected_orchestrator=ORCHESTRATOR_CHATGPT,
        expected_executor=EXECUTOR_DIP_API_ROUTE,
        chatgpt_lane_called=True,
        api_route_called=True,
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
        "gpt_api_mode_proven",
    ):
        _check_true(packet, field, failures, prefix)
    _check_false(packet, "chatgpt_only_mode_proven", failures, prefix)
    _check_false(packet, "api_only_mode_proven", failures, prefix)
    _check_base_safety(packet, failures, prefix)
    for field in (
        "native_codex_subagent_used_as_dip",
        "command_argv_recorded",
        "codex_stdout_recorded",
        "codex_stderr_recorded",
        "dip_repo_direct_access",
        "repo_bridge_direct_shell_access",
        "dip_action_raw_patch_recorded",
        "dip_action_raw_command_recorded",
        "repo_bridge_context_pack_recorded",
        "repo_bridge_raw_tool_results_recorded",
        "live_result_route_id_recorded",
        "live_result_raw_backend_details_exposed",
        "live_result_secret_value_exposed",
    ):
        _check_false(packet, field, failures, prefix)
    if packet.get("blocking_reasons") != []:
        failures.append(f"{prefix}_blocking_reasons_not_empty")


def _dip_ping_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    prefix = ROW_DIP_PING
    _check_dip_common(packet, failures, prefix)
    _check_equals(packet, "active_project_root_required", False, failures, prefix)
    _check_equals(packet, "target_repo_required", False, failures, prefix)
    for field in (
        "dip_repo_tool_bridge_required",
        "dip_repo_tool_bridge_used",
        "dip_action_bridge_required",
        "dip_action_bridge_used",
        "dip_action_mutation_applied",
        "dip_action_tests_run",
        "dip_action_patch_applied",
        "dip_code_written",
        "dip_code_verified",
        "repo_bridge_readonly",
        "repo_bridge_mutation_allowed",
        "repo_bridge_mutation_controlled",
    ):
        _check_false(packet, field, failures, prefix)
    return failures


def _dip_repo_audit_failures(
    packet: Mapping[str, Any],
    *,
    prefix: str,
    is_wbp_repo: bool,
) -> list[str]:
    failures: list[str] = []
    _check_dip_common(packet, failures, prefix)
    _check_active_project_root(
        packet,
        failures,
        prefix,
        required=True,
        available=True,
        is_wbp_repo=is_wbp_repo,
    )
    _check_target_repo(
        packet,
        failures,
        prefix,
        required=True,
        available=True,
        is_wbp_repo=is_wbp_repo,
    )
    for field in (
        "dip_repo_tool_bridge_required",
        "dip_repo_tool_bridge_available",
        "dip_repo_tool_bridge_used",
        "repo_bridge_readonly",
    ):
        _check_true(packet, field, failures, prefix)
    _check_positive_int(packet, "repo_bridge_successful_tool_call_count", failures, prefix)
    for field in (
        "dip_action_bridge_required",
        "dip_action_bridge_used",
        "dip_action_mutation_applied",
        "dip_action_tests_run",
        "dip_action_patch_applied",
        "dip_code_written",
        "dip_code_verified",
        "repo_bridge_mutation_allowed",
        "repo_bridge_mutation_controlled",
    ):
        _check_false(packet, field, failures, prefix)
    return failures


def _dip_code_edit_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    prefix = ROW_DIP_CODE_EDIT_TESTS_DUMMY
    _check_dip_common(packet, failures, prefix)
    _check_active_project_root(
        packet,
        failures,
        prefix,
        required=True,
        available=True,
        is_wbp_repo=False,
    )
    _check_target_repo(
        packet,
        failures,
        prefix,
        required=True,
        available=True,
        is_wbp_repo=False,
    )
    for field in (
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
    ):
        _check_true(packet, field, failures, prefix)
    _check_positive_int(packet, "repo_bridge_successful_tool_call_count", failures, prefix)
    _check_positive_int(packet, "dip_action_successful_tool_call_count", failures, prefix)
    _check_false(packet, "repo_bridge_readonly", failures, prefix)
    if packet.get("active_project_root_is_wbp_repo") is True:
        failures.append(f"{prefix}_wbp_repo_mutation_not_allowed")
    if packet.get("target_repo_is_wbp_repo") is True:
        failures.append(f"{prefix}_target_wbp_repo_mutation_not_allowed")
    return failures


def _row_result(
    *,
    row: str,
    packet: Mapping[str, Any],
    packet_sha256: str,
    failures: list[str],
    input_failure: str = "",
) -> dict[str, Any]:
    row_failures = sorted(
        set(([f"{row}_{input_failure}"] if input_failure else []) + failures)
    )
    return {
        "row": row,
        "status": "ok" if not row_failures else "error",
        "machine_error_code": "OK" if not row_failures else E2E_MODE_MATRIX_BLOCKED,
        "packet_kind": _safe_text(packet.get("packet_kind"), limit=120),
        "packet_sha256": packet_sha256,
        "packet_file_path_recorded": False,
        "execution_mode": _safe_text(packet.get("execution_mode"), limit=80),
        "orchestrator": _safe_text(packet.get("orchestrator"), limit=80),
        "executor": _safe_text(packet.get("executor"), limit=80),
        "active_project_root_required": (
            packet.get("active_project_root_required") is True
        ),
        "active_project_root_available": (
            packet.get("active_project_root_available") is True
        ),
        "active_project_root_sha256": _safe_text(
            packet.get("active_project_root_sha256"),
            limit=80,
        ),
        "active_project_root_is_wbp_repo": (
            packet.get("active_project_root_is_wbp_repo") is True
        ),
        "target_repo_required": packet.get("target_repo_required") is True,
        "target_repo_available": packet.get("target_repo_available") is True,
        "target_repo_sha256": _safe_text(packet.get("target_repo_sha256"), limit=80),
        "target_repo_is_wbp_repo": packet.get("target_repo_is_wbp_repo") is True,
        "fallback_used": packet.get("fallback_used") is True,
        "local_imitation_used": packet.get("local_imitation_used") is True,
        "wrapper_substitution_used": packet.get("wrapper_substitution_used") is True,
        "blocking_reasons": row_failures,
    }


def build_e2e_mode_matrix_packet(
    *,
    gpt_packet: dict[str, Any],
    api_packet: dict[str, Any],
    gpt_api_packet: dict[str, Any],
    dip_ping_packet: dict[str, Any],
    dip_repo_audit_dummy_packet: dict[str, Any],
    dip_repo_audit_wbp_packet: dict[str, Any],
    dip_code_edit_tests_dummy_packet: dict[str, Any],
    packet_sha256s: Mapping[str, str] | None = None,
    input_failures: Mapping[str, str] | None = None,
    evidence_written: bool = False,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    packet_sha256s = packet_sha256s or {}
    input_failures = input_failures or {}
    row_packets: dict[str, dict[str, Any]] = {
        ROW_GPT: gpt_packet,
        ROW_API: api_packet,
        ROW_GPT_API: gpt_api_packet,
        ROW_DIP_PING: dip_ping_packet,
        ROW_DIP_REPO_AUDIT_DUMMY: dip_repo_audit_dummy_packet,
        ROW_DIP_REPO_AUDIT_WBP: dip_repo_audit_wbp_packet,
        ROW_DIP_CODE_EDIT_TESTS_DUMMY: dip_code_edit_tests_dummy_packet,
    }
    row_failures: dict[str, list[str]] = {
        ROW_GPT: (
            _gpt_failures(gpt_packet)
            if gpt_packet
            else [f"{ROW_GPT}_packet_missing"]
        ),
        ROW_API: (
            _api_failures(api_packet)
            if api_packet
            else [f"{ROW_API}_packet_missing"]
        ),
        ROW_GPT_API: (
            _gpt_api_failures(gpt_api_packet)
            if gpt_api_packet
            else [f"{ROW_GPT_API}_packet_missing"]
        ),
        ROW_DIP_PING: (
            _dip_ping_failures(dip_ping_packet)
            if dip_ping_packet
            else [f"{ROW_DIP_PING}_packet_missing"]
        ),
        ROW_DIP_REPO_AUDIT_DUMMY: (
            _dip_repo_audit_failures(
                dip_repo_audit_dummy_packet,
                prefix=ROW_DIP_REPO_AUDIT_DUMMY,
                is_wbp_repo=False,
            )
            if dip_repo_audit_dummy_packet
            else [f"{ROW_DIP_REPO_AUDIT_DUMMY}_packet_missing"]
        ),
        ROW_DIP_REPO_AUDIT_WBP: (
            _dip_repo_audit_failures(
                dip_repo_audit_wbp_packet,
                prefix=ROW_DIP_REPO_AUDIT_WBP,
                is_wbp_repo=True,
            )
            if dip_repo_audit_wbp_packet
            else [f"{ROW_DIP_REPO_AUDIT_WBP}_packet_missing"]
        ),
        ROW_DIP_CODE_EDIT_TESTS_DUMMY: (
            _dip_code_edit_failures(dip_code_edit_tests_dummy_packet)
            if dip_code_edit_tests_dummy_packet
            else [f"{ROW_DIP_CODE_EDIT_TESTS_DUMMY}_packet_missing"]
        ),
    }
    rows = [
        _row_result(
            row=row,
            packet=row_packets[row],
            packet_sha256=packet_sha256s.get(row, ""),
            failures=row_failures[row],
            input_failure=input_failures.get(row, ""),
        )
        for row in REQUIRED_ROWS
    ]
    blocking_reasons = sorted(
        {
            reason
            for row in rows
            for reason in row["blocking_reasons"]
        }
    )
    unsafe = any(
        packets.command_packet_has_secret_leak(packet)
        for packet in row_packets.values()
        if packet
    )
    if unsafe:
        blocking_reasons.append("mode_matrix_input_packet_secret_leak")
    ok = not blocking_reasons
    row_status_by_name = {row["row"]: row["status"] for row in rows}
    dummy_root_sha = _safe_text(
        dip_repo_audit_dummy_packet.get("active_project_root_sha256")
        or dip_code_edit_tests_dummy_packet.get("active_project_root_sha256"),
        limit=80,
    )
    wbp_root_sha = _safe_text(
        dip_repo_audit_wbp_packet.get("active_project_root_sha256"),
        limit=80,
    )
    extra = {
        "schema_version": 1,
        "packet_kind": E2E_MODE_MATRIX_PACKET_KIND,
        "proof_scope": "e2e_mode_matrix_feature_gate",
        "operator_command_surface": "wild-boar-proxy codex-runner e2e-mode-matrix",
        "operator_command_mode": "join",
        "gate_source": "existing_machine_readable_proof_packets",
        "gate_runs_live_dispatch": False,
        "gate_reads_audit_history": False,
        "required_rows": list(REQUIRED_ROWS),
        "row_count": len(rows),
        "rows": rows,
        "row_status_by_name": row_status_by_name,
        "all_required_rows_present": all(row_packets[row] for row in REQUIRED_ROWS),
        "all_required_rows_green": ok,
        "e2e_mode_matrix_ready": ok,
        "feature_ready": ok,
        "feature_ready_mode": "e2e_mode_matrix" if ok else "blocked",
        "gpt_mode_ready": row_status_by_name.get(ROW_GPT) == "ok",
        "api_mode_ready": row_status_by_name.get(ROW_API) == "ok",
        "gpt_api_mode_ready": row_status_by_name.get(ROW_GPT_API) == "ok",
        "dip_ping_ready": row_status_by_name.get(ROW_DIP_PING) == "ok",
        "dip_repo_audit_dummy_ready": (
            row_status_by_name.get(ROW_DIP_REPO_AUDIT_DUMMY) == "ok"
        ),
        "dip_repo_audit_wbp_ready": (
            row_status_by_name.get(ROW_DIP_REPO_AUDIT_WBP) == "ok"
        ),
        "dip_code_edit_tests_dummy_ready": (
            row_status_by_name.get(ROW_DIP_CODE_EDIT_TESTS_DUMMY) == "ok"
        ),
        "dummy_active_project_root_sha256": dummy_root_sha,
        "wbp_active_project_root_sha256": wbp_root_sha,
        "dummy_and_wbp_roots_distinct": bool(
            dummy_root_sha and wbp_root_sha and dummy_root_sha != wbp_root_sha
        ),
        "wbp_repo_mutation_allowed": False,
        "wbp_repo_mutation_observed": (
            dip_code_edit_tests_dummy_packet.get("active_project_root_is_wbp_repo")
            is True
            or dip_code_edit_tests_dummy_packet.get("target_repo_is_wbp_repo") is True
        ),
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
        "input_file_paths_recorded": False,
        "blocking_reasons": blocking_reasons,
        "evidence_written": evidence_written,
        "created_at_utc": _utc_now(),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP E2E mode matrix passed."
            if ok
            else "WBP E2E mode matrix is BLOCKED."
        ),
        machine_error_code=(
            E2E_MODE_MATRIX_OK
            if ok
            else E2E_MODE_MATRIX_UNSAFE_PACKET
            if unsafe
            else E2E_MODE_MATRIX_BLOCKED
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files or [],
        effect=EFFECT_MUTATE if evidence_written else EFFECT_READ,
        extra=extra,
    )


def run_e2e_mode_matrix_command(
    *,
    paths: RuntimePaths,
    gpt_proof_file: str,
    api_proof_file: str,
    gpt_api_proof_file: str,
    dip_ping_proof_file: str,
    dip_repo_audit_dummy_proof_file: str,
    dip_repo_audit_wbp_proof_file: str,
    dip_code_edit_tests_dummy_proof_file: str,
    proof_dir: str | None = None,
) -> dict[str, Any]:
    del paths
    file_by_row = {
        ROW_GPT: gpt_proof_file,
        ROW_API: api_proof_file,
        ROW_GPT_API: gpt_api_proof_file,
        ROW_DIP_PING: dip_ping_proof_file,
        ROW_DIP_REPO_AUDIT_DUMMY: dip_repo_audit_dummy_proof_file,
        ROW_DIP_REPO_AUDIT_WBP: dip_repo_audit_wbp_proof_file,
        ROW_DIP_CODE_EDIT_TESTS_DUMMY: dip_code_edit_tests_dummy_proof_file,
    }
    packets_by_row: dict[str, dict[str, Any]] = {}
    sha_by_row: dict[str, str] = {}
    failures_by_row: dict[str, str] = {}
    for row, path in file_by_row.items():
        packet, packet_sha, error = _load_json_packet(path)
        packets_by_row[row] = packet
        sha_by_row[row] = packet_sha
        if error:
            failures_by_row[row] = error

    packet = build_e2e_mode_matrix_packet(
        gpt_packet=packets_by_row[ROW_GPT],
        api_packet=packets_by_row[ROW_API],
        gpt_api_packet=packets_by_row[ROW_GPT_API],
        dip_ping_packet=packets_by_row[ROW_DIP_PING],
        dip_repo_audit_dummy_packet=packets_by_row[ROW_DIP_REPO_AUDIT_DUMMY],
        dip_repo_audit_wbp_packet=packets_by_row[ROW_DIP_REPO_AUDIT_WBP],
        dip_code_edit_tests_dummy_packet=packets_by_row[
            ROW_DIP_CODE_EDIT_TESTS_DUMMY
        ],
        packet_sha256s=sha_by_row,
        input_failures=failures_by_row,
        evidence_written=False,
        changed_files=[],
    )
    if proof_dir:
        output_dir = Path(proof_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / E2E_MODE_MATRIX_FILE_NAME
        packet = build_e2e_mode_matrix_packet(
            gpt_packet=packets_by_row[ROW_GPT],
            api_packet=packets_by_row[ROW_API],
            gpt_api_packet=packets_by_row[ROW_GPT_API],
            dip_ping_packet=packets_by_row[ROW_DIP_PING],
            dip_repo_audit_dummy_packet=packets_by_row[ROW_DIP_REPO_AUDIT_DUMMY],
            dip_repo_audit_wbp_packet=packets_by_row[ROW_DIP_REPO_AUDIT_WBP],
            dip_code_edit_tests_dummy_packet=packets_by_row[
                ROW_DIP_CODE_EDIT_TESTS_DUMMY
            ],
            packet_sha256s=sha_by_row,
            input_failures=failures_by_row,
            evidence_written=True,
            changed_files=[str(output_file)],
        )
        write_json_atomic(output_file, packet)
    return packet
