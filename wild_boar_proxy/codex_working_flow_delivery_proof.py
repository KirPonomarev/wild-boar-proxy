# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_exec_assistant_continuation_proof import (
    BINDING_METHOD_SAFE_DIGEST_MARKER,
    BINDING_METHOD_SAFE_DIGEST_METADATA,
    _assistant_output_candidates_after,
    _contains_secret_value,
    _local_subagent_used_as_dip,
    _matching_tool_result_index,
    _select_bound_assistant_candidate,
)
from .codex_transcript_delivery_observation import (
    DELEGATE_TO_DIP_TOOL,
    _ALLOWED_WBP_MCP_SERVER_NAMES,
    _codex_exec_transcript_digest,
    _hex_sha256,
    _mapping,
    _read_jsonl_events_file,
    _unsafe_flag_failures,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .observed_machine_handoff_delivery import (
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    DELIVERY_TRUTH_SOURCE_PROVEN,
    MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND,
    _canonical_json_digest,
)
from .real_custom_codex_hook_proof import REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
from .router_hook_entry import _safe_text


CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND = "wbp_codex_working_flow_delivery_proof"

CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID = (
    "WBP_CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID"
)
CODEX_WORKING_FLOW_TRANSCRIPT_NOT_OBSERVED = (
    "WBP_CODEX_WORKING_FLOW_TRANSCRIPT_NOT_OBSERVED"
)
CODEX_WORKING_FLOW_DELIVERY_NOT_BOUND = "WBP_CODEX_WORKING_FLOW_DELIVERY_NOT_BOUND"
CODEX_WORKING_FLOW_PAYLOAD_UNSAFE = "WBP_CODEX_WORKING_FLOW_PAYLOAD_UNSAFE"

WORKING_FLOW_DELIVERY_TRUTH_SOURCE = (
    "file_backed_integrated_live_provider_plus_codex_exec_continuation"
)
LIVE_PROVIDER_HANDOFF_TRUTH_SOURCE = "server_owned_external_live_provider_response"


def _read_json_mapping_file(
    path: Path,
    *,
    prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_required": True,
        f"{prefix}_file_present": path.exists(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_error_code": "",
        f"{prefix}_file_path_recorded": False,
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _source_unsafe_claim_failures(source: Mapping[str, Any]) -> list[str]:
    checks = {
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "raw_jsonl_recorded": "raw_jsonl_recorded",
        "tool_call_arguments_recorded": "tool_call_arguments_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "raw_route_id_recorded": "raw_route_id_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_expected_text_recorded": "raw_expected_text_recorded",
        "expected_text_recorded": "expected_text_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "provider_route_fallback_used": "provider_route_fallback_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "custom_codex_ui_visibility_proven": (
            "custom_codex_ui_visibility_must_not_be_claimed"
        ),
        "codex_working_flow_delivery_proven": (
            "codex_working_flow_delivery_must_not_be_preclaimed"
        ),
        "delivery_counts_as_custom_codex_ui": (
            "delivery_counts_as_custom_ui_must_not_be_claimed"
        ),
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
        "state_written": "state_write_not_allowed",
        "evidence_written": "evidence_write_not_allowed",
        "file_mutation_attempted": "file_mutation_not_allowed",
    }
    failures = [
        reason
        for field, reason in checks.items()
        if source.get(field) is True
    ]
    if source.get("live_provider_state_written") is True:
        failures.append("live_provider_state_written")
    if source.get("live_provider_evidence_written") is True:
        failures.append("live_provider_evidence_written")
    if source.get("live_provider_file_mutation_attempted") is True:
        failures.append("live_provider_file_mutation_attempted")
    return sorted(set(failures))


def _integrated_source_failures(
    source: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unsafe_failures = _source_unsafe_claim_failures(source)
    if metadata.get("integrated_live_provider_proof_file_read") is not True:
        failures.append("integrated_live_provider_proof_file_not_read")
    if metadata.get("integrated_live_provider_proof_file_valid_json") is not True:
        failures.append("integrated_live_provider_proof_file_json_not_valid")
    if metadata.get("integrated_live_provider_proof_file_mapping") is not True:
        failures.append("integrated_live_provider_proof_file_not_mapping")
    if source.get("packet_kind") != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND:
        failures.append("integrated_proof_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("integrated_proof_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("integrated_proof_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("integrated_proof_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("integrated_proof_changed_files_not_empty")
    for field, reason in (
        ("hook_producer_ledger_proven", "hook_producer_ledger_not_proven"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("provider_response_proven", "provider_response_not_proven"),
        ("live_provider_requested", "live_provider_not_requested"),
        ("live_provider_attempted", "live_provider_not_attempted"),
        ("live_provider_cli_command_declared", "live_provider_cli_not_declared"),
        ("live_provider_cli_command_route_bound", "live_provider_cli_not_route_bound"),
        ("live_provider_route_bound_to_context", "live_provider_route_not_context_bound"),
        ("live_provider_network_dependent", "live_provider_not_network_dependent"),
        ("expected_text_observed", "live_provider_expected_text_not_observed"),
        ("live_provider_response_bound_to_expected_text", "live_provider_not_expected_bound"),
        ("live_provider_response_bound_to_route", "live_provider_not_route_bound"),
        ("live_provider_changed_files_empty", "live_provider_changed_files_not_empty"),
        ("live_provider_proven", "live_provider_not_proven"),
        ("live_provider_response_proven", "live_provider_response_not_proven"),
        ("external_live_provider_response_proven", "external_live_provider_response_not_proven"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("machine_response_envelope_observed", "machine_response_envelope_not_observed"),
        ("machine_response_structured_content_present", "machine_response_structured_content_missing"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    if _safe_text(source.get("dispatch_status"), limit=32) != "proven":
        failures.append("dispatch_status_not_proven")
    for field, reason in (
        ("hook_ledger_failures", "hook_ledger_failures_not_empty"),
        ("dispatch_failures", "dispatch_failures_not_empty"),
        ("handoff_failures", "handoff_failures_not_empty"),
        ("live_provider_failures", "live_provider_failures_not_empty"),
        ("blocking_reasons", "integrated_proof_blocking_reasons_not_empty"),
    ):
        value = source.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if list(value):
                failures.append(reason)
        elif value:
            failures.append(reason)
    if not _hex_sha256(source.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_missing")
    if not _hex_sha256(source.get("machine_response_envelope_sha256")):
        failures.append("machine_response_envelope_digest_missing")
    if not _hex_sha256(source.get("live_provider_response_digest")):
        failures.append("live_provider_response_digest_missing")
    if not _hex_sha256(source.get("provider_response_digest")):
        failures.append("controlled_provider_response_digest_missing")
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures


def _safe_working_flow_handoff_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    live_provider_response_digest = _hex_sha256(
        source.get("live_provider_response_digest")
    )
    return {
        "schema_version": 1,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=80),
        "source_dispatch_packet_kind": _safe_text(
            source.get("dispatch_packet_kind"),
            limit=80,
        ),
        "source_prompt_digest": _hex_sha256(source.get("prompt_digest")),
        "selected_alias": _safe_text(source.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            source.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(source.get("selected_slot"), limit=64),
        "selected_api_route_id_sha256": _hex_sha256(
            source.get("selected_api_route_id_sha256")
        ),
        "route_bound_request_sha256": _hex_sha256(
            source.get("route_bound_request_sha256")
        ),
        "controlled_provider_response_digest": _hex_sha256(
            source.get("provider_response_digest")
        ),
        "live_provider_response_digest": live_provider_response_digest,
        "provider_response_digest": live_provider_response_digest,
        "dispatch_truth_source": _safe_text(
            source.get("dispatch_truth_source"),
            limit=80,
        ),
        "live_provider_truth_source": LIVE_PROVIDER_HANDOFF_TRUTH_SOURCE,
        "handoff_surface_kind": DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    }


def _safe_working_flow_delivery_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    handoff_payload = _safe_working_flow_handoff_payload(source)
    return {
        "schema_version": 1,
        "packet_kind": MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND,
        "handoff_payload": handoff_payload,
        "handoff_payload_sha256": _canonical_json_digest(handoff_payload),
        "handoff_surface_kind": DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
        "delivery_surface_kind": DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
        "delivery_truth_source": DELIVERY_TRUTH_SOURCE_PROVEN,
    }


def _transcript_delivery_failures(
    *,
    events: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    expected_handoff_digest: str,
    expected_live_provider_response_digest: str,
    expected_controlled_provider_response_digest: str,
    selected_tool_result: Mapping[str, Any],
    tool_result_index: int | None,
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    if metadata.get("codex_exec_jsonl_file_read") is not True:
        failures.append("codex_exec_jsonl_file_not_read")
    if metadata.get("codex_exec_jsonl_file_valid_jsonl") is not True:
        failures.append("codex_exec_jsonl_file_not_valid_jsonl")
    if metadata.get("codex_exec_jsonl_parse_error_count"):
        failures.append("codex_exec_jsonl_parse_error")
    if not events:
        failures.append("codex_exec_json_events_not_observed")
    if tool_result_index is None:
        failures.append("matching_mcp_tool_result_not_observed")

    structured_content = _mapping(selected_tool_result.get("structured_content"))
    observed_handoff_payload = structured_content.get("handoff_payload")
    observed_handoff_payload_digest = (
        _canonical_json_digest(observed_handoff_payload)
        if isinstance(observed_handoff_payload, Mapping)
        else ""
    )
    observed_handoff_payload_mapping = (
        observed_handoff_payload if isinstance(observed_handoff_payload, Mapping) else {}
    )
    declared_handoff_payload_digest = _hex_sha256(
        structured_content.get("handoff_payload_sha256")
    )
    structured_content_digest = (
        _canonical_json_digest(structured_content) if structured_content else ""
    )
    if tool_result_index is not None and not structured_content:
        failures.append("mcp_tool_result_structured_content_missing")
    if structured_content:
        server_name = _safe_text(selected_tool_result.get("server_name"), limit=128)
        tool_name = _safe_text(selected_tool_result.get("tool_name"), limit=128)
        if not server_name or server_name not in _ALLOWED_WBP_MCP_SERVER_NAMES:
            failures.append("mcp_tool_result_server_not_wbp")
        if tool_name != DELEGATE_TO_DIP_TOOL:
            failures.append("mcp_tool_result_tool_name_invalid")
        if selected_tool_result.get("content_text_present") is True:
            if selected_tool_result.get("content_text_json_mapping_present") is not True:
                failures.append("mcp_tool_result_content_text_not_json_mapping")
            elif (
                selected_tool_result.get(
                    "content_text_json_matches_structured_content"
                )
                is not True
            ):
                failures.append("mcp_tool_result_content_text_structured_content_mismatch")
        if structured_content.get("packet_kind") != MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND:
            failures.append("delivery_payload_kind_invalid")
        if structured_content.get("delivery_surface_kind") != DELIVERY_SURFACE_MCP_TOOL_RESPONSE:
            failures.append("delivery_surface_must_be_mcp_tool_response")
        if structured_content.get("delivery_truth_source") != DELIVERY_TRUTH_SOURCE_PROVEN:
            failures.append("delivery_truth_source_invalid")
        if not isinstance(observed_handoff_payload, Mapping):
            failures.append("handoff_payload_missing")
        if not declared_handoff_payload_digest:
            failures.append("handoff_payload_declared_digest_missing")
        if (
            declared_handoff_payload_digest
            and observed_handoff_payload_digest
            and declared_handoff_payload_digest != observed_handoff_payload_digest
        ):
            failures.append("handoff_payload_declared_digest_mismatch")
        if (
            expected_handoff_digest
            and observed_handoff_payload_digest
            and observed_handoff_payload_digest != expected_handoff_digest
        ):
            failures.append("handoff_payload_digest_mismatch")
        observed_live_provider_response_digest = _hex_sha256(
            observed_handoff_payload_mapping.get("live_provider_response_digest")
        )
        observed_provider_response_digest = _hex_sha256(
            observed_handoff_payload_mapping.get("provider_response_digest")
        )
        observed_controlled_provider_response_digest = _hex_sha256(
            observed_handoff_payload_mapping.get("controlled_provider_response_digest")
        )
        if not observed_live_provider_response_digest:
            failures.append("live_provider_response_digest_missing_from_handoff")
        elif observed_live_provider_response_digest != expected_live_provider_response_digest:
            failures.append("live_provider_response_digest_mismatch")
        if not observed_provider_response_digest:
            failures.append("provider_response_digest_missing_from_handoff")
        elif observed_provider_response_digest != expected_live_provider_response_digest:
            failures.append("provider_response_digest_not_bound_to_live_provider")
        if not observed_controlled_provider_response_digest:
            failures.append("controlled_provider_response_digest_missing_from_handoff")
        elif (
            observed_controlled_provider_response_digest
            != expected_controlled_provider_response_digest
        ):
            failures.append("controlled_provider_response_digest_mismatch")
        if selected_tool_result.get("is_error") is True:
            failures.append("mcp_tool_result_is_error")

    structured_content_matches_handoff = bool(
        expected_handoff_digest
        and declared_handoff_payload_digest
        and observed_handoff_payload_digest
        and expected_live_provider_response_digest
        and declared_handoff_payload_digest == expected_handoff_digest
        and observed_handoff_payload_digest == expected_handoff_digest
        and _hex_sha256(observed_handoff_payload_mapping.get("provider_response_digest"))
        == expected_live_provider_response_digest
        and _hex_sha256(
            observed_handoff_payload_mapping.get("live_provider_response_digest")
        )
        == expected_live_provider_response_digest
    )
    if not structured_content_matches_handoff:
        failures.append("structured_content_not_bound_to_integrated_handoff")
    details = {
        "structured_content": dict(structured_content),
        "structured_content_digest": structured_content_digest,
        "declared_handoff_payload_digest": declared_handoff_payload_digest,
        "observed_handoff_payload_digest": observed_handoff_payload_digest,
        "structured_content_matches_handoff": structured_content_matches_handoff,
        "observed_live_provider_response_digest": _hex_sha256(
            observed_handoff_payload_mapping.get("live_provider_response_digest")
        ),
        "observed_provider_response_digest": _hex_sha256(
            observed_handoff_payload_mapping.get("provider_response_digest")
        ),
        "observed_controlled_provider_response_digest": _hex_sha256(
            observed_handoff_payload_mapping.get("controlled_provider_response_digest")
        ),
    }
    return sorted(set(failures)), details


def _machine_error_code(
    *,
    source_failures: Sequence[str],
    transcript_failures: Sequence[str],
    binding_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if (
        not source_failures
        and not transcript_failures
        and not binding_failures
        and not unsafe_failures
    ):
        return "OK"
    if source_failures:
        return CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID
    if unsafe_failures:
        return CODEX_WORKING_FLOW_PAYLOAD_UNSAFE
    if transcript_failures:
        return CODEX_WORKING_FLOW_TRANSCRIPT_NOT_OBSERVED
    return CODEX_WORKING_FLOW_DELIVERY_NOT_BOUND


def build_codex_working_flow_delivery_proof_packet(
    integrated_live_provider_proof_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    *,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(integrated_live_provider_proof_packet)
    events = [dict(event) for event in codex_exec_events or []]
    metadata = dict(file_metadata or {})
    source_handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    working_flow_delivery_payload = _safe_working_flow_delivery_payload(source)
    handoff_digest = _hex_sha256(
        working_flow_delivery_payload.get("handoff_payload_sha256")
    )
    live_provider_response_digest = _hex_sha256(
        source.get("live_provider_response_digest")
    )
    controlled_provider_response_digest = _hex_sha256(
        source.get("provider_response_digest")
    )

    source_failures, source_unsafe_failures = _integrated_source_failures(
        source,
        metadata,
    )
    tool_result_index, tool_result = _matching_tool_result_index(events, handoff_digest)
    transcript_failures, transcript_details = _transcript_delivery_failures(
        events=events,
        metadata=metadata,
        expected_handoff_digest=handoff_digest,
        expected_live_provider_response_digest=live_provider_response_digest,
        expected_controlled_provider_response_digest=controlled_provider_response_digest,
        selected_tool_result=tool_result,
        tool_result_index=tool_result_index,
    )
    assistant_candidates = _assistant_output_candidates_after(
        events,
        after_index=tool_result_index,
        expected_digest=handoff_digest,
    )
    selected_assistant = _select_bound_assistant_candidate(assistant_candidates)
    assistant_response_observed = bool(assistant_candidates)
    assistant_response_after_tool_result = bool(
        tool_result_index is not None and assistant_candidates
    )
    assistant_machine_marker_observed = any(
        candidate.get("machine_marker_observed") is True
        for candidate in assistant_candidates
    )
    assistant_marker_digest_mismatch = any(
        candidate.get("machine_marker_digest_mismatch") is True
        for candidate in assistant_candidates
    )
    binding_method = _safe_text(selected_assistant.get("binding_method"), limit=64)
    assistant_binding_digest = _hex_sha256(selected_assistant.get("binding_digest"))
    assistant_response_bound_to_handoff_digest = bool(
        assistant_binding_digest and assistant_binding_digest == handoff_digest
    )

    binding_failures: list[str] = []
    if not assistant_response_observed:
        transcript_failures.append("assistant_response_after_tool_result_not_observed")
    if assistant_response_observed and not assistant_response_after_tool_result:
        transcript_failures.append("assistant_response_not_after_tool_result")
    if assistant_response_observed and not assistant_machine_marker_observed:
        binding_failures.append("assistant_response_machine_digest_marker_missing")
    if assistant_marker_digest_mismatch and not assistant_response_bound_to_handoff_digest:
        binding_failures.append("assistant_response_handoff_digest_mismatch")
    if assistant_response_observed and not assistant_response_bound_to_handoff_digest:
        binding_failures.append("assistant_response_not_bound_to_handoff_digest")
    if binding_method and binding_method not in {
        BINDING_METHOD_SAFE_DIGEST_MARKER,
        BINDING_METHOD_SAFE_DIGEST_METADATA,
    }:
        binding_failures.append("assistant_response_binding_method_invalid")

    local_subagent_used_as_dip = _local_subagent_used_as_dip(events)
    transcript_secret_value_present = _contains_secret_value(events, secret_values)
    transcript_unsafe_failures = _unsafe_flag_failures(events)
    if local_subagent_used_as_dip:
        transcript_unsafe_failures.append("native_codex_subagent_used_as_dip")
    if transcript_secret_value_present:
        transcript_unsafe_failures.append("secret_value_present_in_codex_exec_transcript")
    unsafe_failures = sorted(
        set(source_unsafe_failures + transcript_unsafe_failures)
    )

    source_failures = sorted(set(source_failures))
    transcript_failures = sorted(set(transcript_failures))
    binding_failures = sorted(set(binding_failures))
    blocking_reasons = sorted(
        set(source_failures + transcript_failures + binding_failures + unsafe_failures)
    )
    ok = bool(
        not blocking_reasons
        and source.get("external_live_provider_response_proven") is True
        and live_provider_response_digest
        and transcript_details.get("structured_content_matches_handoff") is True
        and assistant_response_bound_to_handoff_digest
    )
    machine_error_code = _machine_error_code(
        source_failures=source_failures,
        transcript_failures=transcript_failures,
        binding_failures=binding_failures,
        unsafe_failures=unsafe_failures,
    )
    codex_exec_transcript_sha256 = _codex_exec_transcript_digest(events) if events else ""
    live_provider_response_proven = bool(
        not source_failures
        and source.get("live_provider_response_proven") is True
        and source.get("external_live_provider_response_proven") is True
        and live_provider_response_digest
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        "working_flow_delivery_truth_source": (
            WORKING_FLOW_DELIVERY_TRUTH_SOURCE if ok else "not_proven"
        ),
        "integrated_live_provider_proof_kind": _safe_text(
            source.get("packet_kind"),
            limit=80,
        ),
        "integrated_live_provider_proof_status": _safe_text(
            source.get("status"),
            limit=32,
        ),
        "integrated_live_provider_proof_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "integrated_live_provider_proof_valid": not source_failures,
        "integrated_live_provider_proof_failures": source_failures,
        "source_unsafe_claim_failures": source_unsafe_failures,
        "hook_producer_ledger_proven": (
            source.get("hook_producer_ledger_proven") is True
        ),
        "user_prompt_submit_hook_ran": source.get("user_prompt_submit_hook_ran") is True,
        "hook_ledger_written": source.get("hook_ledger_written") is True,
        "hook_prompt_digest_bound": source.get("hook_prompt_digest_bound") is True,
        "hook_runtime_context_digest_bound": (
            source.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": (
            source.get("thread_or_turn_digest_bound") is True
        ),
        "custom_codex_flow_proven": False,
        "command_origin_proven": False,
        "custom_codex_origin_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
        "alias_context_read": source.get("alias_context_read") is True,
        "allowed_api_route_ids_enforced": (
            source.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": source.get("route_id_allowed") is True,
        "api_lane_called": source.get("api_lane_called") is True,
        "dispatch_status": _safe_text(source.get("dispatch_status"), limit=32),
        "dispatch_proven": source.get("dispatch_proven") is True,
        "route_bound_dispatch_proven": (
            source.get("route_bound_dispatch_proven") is True
        ),
        "provider_response_proven": source.get("provider_response_proven") is True,
        "live_provider_requested": source.get("live_provider_requested") is True,
        "live_provider_attempted": source.get("live_provider_attempted") is True,
        "live_provider_cli_command_declared": (
            source.get("live_provider_cli_command_declared") is True
        ),
        "live_provider_cli_command_route_bound": (
            source.get("live_provider_cli_command_route_bound") is True
        ),
        "live_provider_route_bound_to_context": (
            source.get("live_provider_route_bound_to_context") is True
        ),
        "live_provider_network_dependent": (
            source.get("live_provider_network_dependent") is True
        ),
        "expected_text_observed": source.get("expected_text_observed") is True,
        "expected_text_recorded": False,
        "raw_expected_text_recorded": False,
        "provider_route_fallback_used": False,
        "live_provider_response_bound_to_expected_text": (
            source.get("live_provider_response_bound_to_expected_text") is True
        ),
        "live_provider_response_bound_to_route": (
            source.get("live_provider_response_bound_to_route") is True
        ),
        "live_provider_changed_files_empty": (
            source.get("live_provider_changed_files_empty") is True
        ),
        "source_live_provider_proven": source.get("live_provider_proven") is True,
        "source_live_provider_response_proven": (
            source.get("live_provider_response_proven") is True
        ),
        "source_external_live_provider_response_proven": (
            source.get("external_live_provider_response_proven") is True
        ),
        "live_provider_proven": live_provider_response_proven,
        "live_provider_response_proven": live_provider_response_proven,
        "external_live_provider_response_proven": live_provider_response_proven,
        "approved_handoff_ready": source.get("approved_handoff_ready") is True,
        "approved_handoff_payload_sanitized": (
            source.get("approved_handoff_payload_sanitized") is True
        ),
        "source_handoff_payload_digest": source_handoff_digest,
        "working_flow_handoff_payload_digest": handoff_digest,
        "handoff_payload_digest": handoff_digest,
        "machine_response_envelope_observed": (
            source.get("machine_response_envelope_observed") is True
        ),
        "machine_response_envelope_sha256": _hex_sha256(
            source.get("machine_response_envelope_sha256")
        ),
        "machine_response_structured_content_present": (
            source.get("machine_response_structured_content_present") is True
        ),
        "handoff_delivered": source.get("handoff_delivered") is True,
        "delivery_observed": source.get("delivery_observed") is True,
        "live_provider_response_digest": live_provider_response_digest,
        "controlled_provider_response_digest": controlled_provider_response_digest,
        "live_provider_response_digest_bound_to_handoff": (
            transcript_details.get("observed_live_provider_response_digest")
            == live_provider_response_digest
            and transcript_details.get("observed_provider_response_digest")
            == live_provider_response_digest
        ),
        "controlled_provider_response_digest_bound_to_handoff": (
            transcript_details.get("observed_controlled_provider_response_digest")
            == controlled_provider_response_digest
        ),
        "codex_exec_json_events_observed": bool(events),
        "codex_exec_transcript_sha256": codex_exec_transcript_sha256,
        "matching_mcp_tool_result_observed": tool_result_index is not None,
        "matching_mcp_tool_result_event_index_present": tool_result_index is not None,
        "mcp_tool_result_event_type": _safe_text(tool_result.get("event_type"), limit=128),
        "mcp_tool_result_item_type": _safe_text(tool_result.get("item_type"), limit=128),
        "mcp_server_name_observed": _safe_text(tool_result.get("server_name"), limit=128),
        "mcp_tool_name_observed": _safe_text(tool_result.get("tool_name"), limit=128),
        "mcp_tool_result_name_allowed": _safe_text(
            tool_result.get("tool_name"),
            limit=128,
        )
        == DELEGATE_TO_DIP_TOOL,
        "mcp_tool_result_server_allowed": _safe_text(
            tool_result.get("server_name"),
            limit=128,
        )
        in _ALLOWED_WBP_MCP_SERVER_NAMES,
        "mcp_tool_result_is_error": tool_result.get("is_error") is True,
        "mcp_tool_result_structured_content_present": bool(
            transcript_details.get("structured_content")
        ),
        "mcp_tool_result_content_text_present": (
            tool_result.get("content_text_present") is True
        ),
        "mcp_tool_result_content_text_json_mapping_present": (
            tool_result.get("content_text_json_mapping_present") is True
        ),
        "mcp_tool_result_content_text_json_matches_structured_content": (
            tool_result.get("content_text_json_matches_structured_content") is True
        ),
        "structured_content_kind": _safe_text(
            _mapping(transcript_details.get("structured_content")).get("packet_kind"),
            limit=80,
        ),
        "structured_content_digest": _hex_sha256(
            transcript_details.get("structured_content_digest")
        ),
        "declared_handoff_payload_digest": _hex_sha256(
            transcript_details.get("declared_handoff_payload_digest")
        ),
        "observed_handoff_payload_digest": _hex_sha256(
            transcript_details.get("observed_handoff_payload_digest")
        ),
        "observed_live_provider_response_digest": _hex_sha256(
            transcript_details.get("observed_live_provider_response_digest")
        ),
        "observed_provider_response_digest": _hex_sha256(
            transcript_details.get("observed_provider_response_digest")
        ),
        "observed_controlled_provider_response_digest": _hex_sha256(
            transcript_details.get("observed_controlled_provider_response_digest")
        ),
        "structured_content_matches_handoff": (
            transcript_details.get("structured_content_matches_handoff") is True
        ),
        "assistant_response_observed": assistant_response_observed,
        "assistant_response_after_tool_result": assistant_response_after_tool_result,
        "assistant_response_event_index_present": bool(selected_assistant),
        "assistant_response_event_type": _safe_text(
            selected_assistant.get("event_type"),
            limit=128,
        ),
        "assistant_response_item_type": _safe_text(
            selected_assistant.get("item_type"),
            limit=128,
        ),
        "assistant_response_role": _safe_text(
            selected_assistant.get("role"),
            limit=64,
        ),
        "assistant_machine_marker_observed": assistant_machine_marker_observed,
        "assistant_marker_digest_mismatch": assistant_marker_digest_mismatch,
        "assistant_response_bound_to_handoff_digest": (
            assistant_response_bound_to_handoff_digest
        ),
        "binding_method": binding_method,
        "assistant_binding_digest": assistant_binding_digest,
        "codex_exec_assistant_continuation_proven": bool(
            assistant_response_after_tool_result
            and assistant_response_bound_to_handoff_digest
            and not binding_failures
        ),
        "codex_working_flow_delivery_proven": ok,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": not live_provider_response_proven,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": local_subagent_used_as_dip,
        "native_codex_subagent_used_as_dip": local_subagent_used_as_dip,
        "codex_native_subagent_used_as_dip": local_subagent_used_as_dip,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
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
        "browser_can_supply_working_flow_authority": False,
        "transcript_secret_value_present": transcript_secret_value_present,
        "transcript_unsafe_claim_failures": sorted(set(transcript_unsafe_failures)),
        "transcript_delivery_failures": transcript_failures,
        "assistant_binding_failures": binding_failures,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved live provider output was delivered into a digest-bound Codex working flow."
            if ok
            else "WBP blocked Codex working-flow delivery before proof."
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


def run_codex_working_flow_delivery_proof_command(
    *,
    integrated_live_provider_proof_file: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    source_path = Path(integrated_live_provider_proof_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    source_packet, source_metadata = _read_json_mapping_file(
        source_path,
        prefix="integrated_live_provider_proof",
    )
    events, jsonl_metadata = _read_jsonl_events_file(jsonl_path)
    return build_codex_working_flow_delivery_proof_packet(
        source_packet,
        events,
        file_metadata={**source_metadata, **jsonl_metadata},
    )
