# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .official_e2e_working_flow_proof_join import (
    OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_OK,
    OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND,
    _read_json_mapping_file,
    run_official_e2e_working_flow_proof_join_command,
)
from .router_hook_entry import _safe_text


OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND = (
    "wbp_official_e2e_working_flow_proof_runner_inputs"
)
OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND = (
    "wbp_official_e2e_working_flow_proof_runner"
)

OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_OK = "OK"
OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID"
)
OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_JOIN_INVALID = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_JOIN_INVALID"
)
OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE"
)

_INPUT_ALLOWED_FIELDS = {
    "schema_version",
    "packet_kind",
    "proof_run_id",
    "real_custom_hook_proof_file",
    "official_working_flow_delivery_join_file",
}
_INPUT_RAW_OR_SECRET_FIELDS = {
    "prompt",
    "raw_prompt",
    "prompt_text",
    "natural_phrase",
    "task",
    "raw_task",
    "route_id",
    "raw_route_id",
    "selected_api_route_id",
    "route_candidate",
    "provider_response",
    "raw_provider_response",
    "provider_response_text",
    "provider_response_preview",
    "backend_details",
    "raw_backend_details",
    "api_key",
    "authorization",
    "bearer_token",
    "secret",
    "token",
}
_JOIN_REQUIRED_TRUE_FIELDS = (
    "official_e2e_working_flow_proven",
    "custom_codex_hook_to_official_working_flow_bound",
    "custom_codex_flow_origin_proven",
    "hook_producer_ledger_proven",
    "user_prompt_submit_hook_ran",
    "hook_ledger_written",
    "hook_prompt_digest_bound",
    "hook_runtime_context_digest_bound",
    "thread_or_turn_digest_bound",
    "working_flow_hook_prompt_digest_bound",
    "working_flow_hook_runtime_context_digest_bound",
    "prompt_digest_bound_to_working_flow",
    "runtime_context_digest_bound_to_working_flow",
    "alias_context_read",
    "allowed_api_route_ids_enforced",
    "route_id_allowed",
    "api_lane_called",
    "dispatch_proven",
    "route_bound_dispatch_proven",
    "provider_response_proven",
    "live_provider_proven",
    "live_provider_response_proven",
    "external_live_provider_response_proven",
    "live_provider_response_bound_to_working_flow",
    "controlled_provider_response_bound_to_working_flow",
    "approved_handoff_ready",
    "approved_handoff_payload_sanitized",
    "handoff_delivered",
    "delivery_observed",
    "handoff_payload_bound_to_working_flow",
    "approved_exec_source_delivery_candidate",
    "approved_delivery_surface_proven",
    "codex_exec_assistant_continuation_proven",
    "codex_working_flow_delivery_proven",
    "official_mcp_delivery_candidate_joined_to_working_flow",
)
_JOIN_REQUIRED_FALSE_FIELDS = (
    "custom_codex_ui_visibility_proven",
    "delivery_counts_as_custom_codex_ui",
    "native_free_chat_router_proven",
    "native_free_chat_router_product_ready",
    "native_free_chat_router_delivery_proven",
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip",
    "raw_jsonl_recorded",
    "raw_prompt_recorded",
    "raw_task_recorded",
    "tool_call_arguments_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "route_candidate_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "state_written",
    "evidence_written",
    "file_mutation_attempted",
)
_JOIN_REQUIRED_EMPTY_SEQUENCE_FIELDS = (
    "real_custom_hook_failures",
    "official_working_flow_delivery_join_failures",
    "source_unsafe_claim_failures",
    "digest_binding_failures",
    "blocking_reasons",
    "changed_files",
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _file_sha256(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _input_contract_failures(
    inputs: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_e2e_runner_inputs_file_read") is not True:
        failures.append("runner_inputs_file_not_read")
    if metadata.get("official_e2e_runner_inputs_file_valid_json") is not True:
        failures.append("runner_inputs_file_json_not_valid")
    if metadata.get("official_e2e_runner_inputs_file_mapping") is not True:
        failures.append("runner_inputs_file_not_mapping")
    if inputs.get("packet_kind") != OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND:
        failures.append("runner_inputs_packet_kind_invalid")
    if inputs.get("schema_version") != 1:
        failures.append("runner_inputs_schema_version_invalid")
    unknown_fields = sorted(set(inputs) - _INPUT_ALLOWED_FIELDS)
    if unknown_fields:
        failures.append("runner_inputs_unknown_fields")
    for key in _INPUT_RAW_OR_SECRET_FIELDS:
        if key in inputs:
            failures.append(f"runner_inputs_{key}_not_allowed")
    if not isinstance(inputs.get("real_custom_hook_proof_file"), str):
        failures.append("real_custom_hook_proof_file_not_string")
    elif not inputs.get("real_custom_hook_proof_file"):
        failures.append("real_custom_hook_proof_file_empty")
    if not isinstance(inputs.get("official_working_flow_delivery_join_file"), str):
        failures.append("official_working_flow_delivery_join_file_not_string")
    elif not inputs.get("official_working_flow_delivery_join_file"):
        failures.append("official_working_flow_delivery_join_file_empty")
    proof_run_id = inputs.get("proof_run_id")
    if proof_run_id is not None and not packets.is_command_value_token(proof_run_id):
        failures.append("proof_run_id_not_machine_token")
    return sorted(set(failures))


def _input_unsafe_failures(
    inputs: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None = None,
) -> list[str]:
    failures: list[str] = []
    for field in (
        "product_ready",
        "custom_codex_ui_visibility_proven",
        "native_free_chat_router_proven",
        "native_free_chat_router_product_ready",
    ):
        if inputs.get(field) is True:
            failures.append(f"runner_inputs_{field}_claim")
    if packets.command_packet_has_secret_leak(inputs, secret_values=list(secret_values or [])):
        failures.append("runner_inputs_secret_material_present")
    return sorted(set(failures))


def _join_contract_failures(join_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if join_packet.get("packet_kind") != OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND:
        failures.append("official_e2e_join_packet_kind_invalid")
    if join_packet.get("status") != "ok":
        failures.append("official_e2e_join_packet_not_ok")
    if join_packet.get("machine_error_code") != OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_OK:
        failures.append("official_e2e_join_machine_error_not_ok")
    if join_packet.get("effect") != EFFECT_PROBE:
        failures.append("official_e2e_join_effect_not_probe")
    for field in _JOIN_REQUIRED_TRUE_FIELDS:
        if join_packet.get(field) is not True:
            failures.append(f"official_e2e_join_{field}_not_true")
    for field in _JOIN_REQUIRED_FALSE_FIELDS:
        if join_packet.get(field) is not False:
            failures.append(f"official_e2e_join_{field}_not_false")
    for field in _JOIN_REQUIRED_EMPTY_SEQUENCE_FIELDS:
        if join_packet.get(field) not in ([], ()):
            failures.append(f"official_e2e_join_{field}_not_empty")
    for field in (
        "prompt_digest",
        "runtime_context_digest",
        "selected_api_route_id_sha256",
        "route_bound_request_sha256",
        "live_provider_response_digest",
        "controlled_provider_response_digest",
        "handoff_payload_digest",
        "codex_exec_transcript_sha256",
    ):
        value = join_packet.get(field)
        if not isinstance(value, str) or not value:
            failures.append(f"official_e2e_join_{field}_missing")
    return sorted(set(failures))


def _machine_error_code(
    *,
    input_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    join_failures: Sequence[str],
) -> str:
    if unsafe_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE
    if input_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID
    if join_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_JOIN_INVALID
    return OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_OK


def _resolve_declared_file(*, inputs_file: Path, declared: object) -> str:
    if not isinstance(declared, str):
        return ""
    path = Path(declared).expanduser()
    if not path.is_absolute():
        path = inputs_file.parent / path
    return str(path)


def build_official_e2e_working_flow_proof_runner_packet(
    *,
    runner_inputs_packet: Mapping[str, Any] | None,
    official_e2e_join_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    inputs = _mapping(runner_inputs_packet)
    join_packet = _mapping(official_e2e_join_packet)
    metadata = dict(file_metadata or {})
    input_failures = _input_contract_failures(inputs, metadata)
    unsafe_failures = _input_unsafe_failures(inputs, secret_values=secret_values)
    join_failures = [] if input_failures or unsafe_failures else _join_contract_failures(join_packet)
    blocking_reasons = sorted(
        set(
            input_failures
            + unsafe_failures
            + join_failures
            + _safe_reasons(join_packet.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        input_failures=input_failures,
        unsafe_failures=unsafe_failures,
        join_failures=join_failures,
    )
    proof_run_id = _safe_text(inputs.get("proof_run_id"), limit=96)

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND,
        "proof_scope": "repeatable_official_e2e_working_flow_proof_runner",
        "proof_run_id": proof_run_id if packets.is_command_value_token(proof_run_id) else "",
        "runner_inputs_packet_kind": _safe_text(inputs.get("packet_kind"), limit=96),
        "runner_inputs_schema_version": inputs.get("schema_version")
        if isinstance(inputs.get("schema_version"), int)
        and not isinstance(inputs.get("schema_version"), bool)
        else 0,
        "runner_inputs_valid": not input_failures,
        "runner_inputs_unsafe": bool(unsafe_failures),
        "runner_input_failures": input_failures,
        "runner_unsafe_failures": unsafe_failures,
        "official_e2e_join_packet_kind": _safe_text(
            join_packet.get("packet_kind"),
            limit=96,
        ),
        "official_e2e_join_status": _safe_text(join_packet.get("status"), limit=32),
        "official_e2e_join_machine_error_code": _safe_text(
            join_packet.get("machine_error_code"),
            limit=96,
        ),
        "official_e2e_join_valid": (
            not join_failures and not input_failures and not unsafe_failures
        ),
        "official_e2e_join_failures": join_failures,
        "official_e2e_working_flow_proven": bool(
            ok and join_packet.get("official_e2e_working_flow_proven") is True
        ),
        "custom_codex_hook_to_official_working_flow_bound": bool(
            ok
            and join_packet.get("custom_codex_hook_to_official_working_flow_bound")
            is True
        ),
        "custom_codex_flow_origin_proven": bool(
            ok and join_packet.get("custom_codex_flow_origin_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and join_packet.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": bool(
            ok and join_packet.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and join_packet.get("hook_runtime_context_digest_bound") is True
        ),
        "api_lane_called": bool(ok and join_packet.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and join_packet.get("dispatch_proven") is True),
        "live_provider_response_proven": bool(
            ok and join_packet.get("live_provider_response_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and join_packet.get("codex_working_flow_delivery_proven") is True
        ),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_jsonl_recorded": False,
        "raw_prompt_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP repeatably ran the official E2E working-flow proof."
            if ok
            else "WBP blocked repeatable official E2E working-flow proof runner."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_official_e2e_working_flow_proof_runner_command(
    *,
    inputs_file: str,
) -> dict[str, Any]:
    inputs_path = Path(inputs_file).expanduser()
    inputs_packet, inputs_metadata = _read_json_mapping_file(
        inputs_path,
        prefix="official_e2e_runner_inputs",
    )
    metadata = {
        **inputs_metadata,
        "official_e2e_runner_inputs_file_sha256": _file_sha256(inputs_path),
    }
    input_failures = _input_contract_failures(inputs_packet, metadata)
    unsafe_failures = _input_unsafe_failures(inputs_packet)
    join_packet: dict[str, Any] = {}
    if not input_failures and not unsafe_failures:
        join_packet = run_official_e2e_working_flow_proof_join_command(
            real_custom_hook_proof_file=_resolve_declared_file(
                inputs_file=inputs_path,
                declared=inputs_packet.get("real_custom_hook_proof_file"),
            ),
            official_working_flow_delivery_join_file=_resolve_declared_file(
                inputs_file=inputs_path,
                declared=inputs_packet.get("official_working_flow_delivery_join_file"),
            ),
        )
    return build_official_e2e_working_flow_proof_runner_packet(
        runner_inputs_packet=inputs_packet,
        official_e2e_join_packet=join_packet,
        file_metadata=metadata,
    )
