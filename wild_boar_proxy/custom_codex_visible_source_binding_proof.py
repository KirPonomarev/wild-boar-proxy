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
    _codex_exec_transcript_digest,
    _hex_sha256,
    _mapping,
    _read_jsonl_events_file,
    _unsafe_flag_failures,
)
from .codex_working_flow_delivery_proof import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_origin_bound_live_provider_join import _route_secret_values
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths


CUSTOM_CODEX_VISIBLE_SOURCE_BINDING_PACKET_KIND = (
    "wbp_custom_codex_visible_source_binding_proof"
)

VISIBLE_SOURCE_BINDING_OK = "OK"
VISIBLE_SOURCE_BINDING_WORKING_FLOW_INVALID = (
    "WBP_VISIBLE_SOURCE_BINDING_WORKING_FLOW_INVALID"
)
VISIBLE_SOURCE_BINDING_SOURCE_NOT_ALLOWED = (
    "WBP_VISIBLE_SOURCE_BINDING_SOURCE_NOT_ALLOWED"
)
VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED = (
    "WBP_VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED"
)
VISIBLE_SOURCE_BINDING_NOT_BOUND = "WBP_VISIBLE_SOURCE_BINDING_NOT_BOUND"
VISIBLE_SOURCE_BINDING_PAYLOAD_UNSAFE = "WBP_VISIBLE_SOURCE_BINDING_PAYLOAD_UNSAFE"

VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT = "codex_exec_json_assistant_output"
APPROVED_VISIBLE_SOURCE_KINDS = frozenset(
    {VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT}
)


def _read_working_flow_delivery_proof_file(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "working_flow_delivery_proof_file_required": True,
        "working_flow_delivery_proof_file_present": path.exists(),
        "working_flow_delivery_proof_file_read": False,
        "working_flow_delivery_proof_file_valid_json": False,
        "working_flow_delivery_proof_file_mapping": False,
        "working_flow_delivery_proof_file_error_code": "",
        "working_flow_delivery_proof_file_path_recorded": False,
    }
    if not path.exists():
        metadata["working_flow_delivery_proof_file_error_code"] = (
            "working_flow_delivery_proof_file_missing"
        )
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata["working_flow_delivery_proof_file_error_code"] = (
            "working_flow_delivery_proof_file_invalid"
        )
        return {}, metadata
    metadata["working_flow_delivery_proof_file_read"] = True
    metadata["working_flow_delivery_proof_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["working_flow_delivery_proof_file_error_code"] = (
            "working_flow_delivery_proof_file_not_mapping"
        )
        return {}, metadata
    metadata["working_flow_delivery_proof_file_mapping"] = True
    return dict(parsed), metadata


def _source_sequence_failures(value: object, reason: str) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if list(value):
            return [reason]
    elif value:
        return [reason]
    return []


def _working_flow_source_unsafe_failures(source: Mapping[str, Any]) -> list[str]:
    checks = {
        "custom_codex_ui_visibility_proven": (
            "custom_codex_ui_visibility_must_not_be_claimed"
        ),
        "delivery_counts_as_custom_codex_ui": (
            "delivery_counts_as_custom_codex_ui_must_not_be_claimed"
        ),
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
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
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "state_written": "state_write_not_allowed",
        "evidence_written": "evidence_write_not_allowed",
        "file_mutation_attempted": "file_mutation_not_allowed",
    }
    failures = [
        reason
        for field, reason in checks.items()
        if source.get(field) is True
    ]
    failures.extend(
        _source_sequence_failures(
            source.get("integrated_live_provider_proof_failures"),
            "integrated_live_provider_proof_failures_not_empty",
        )
    )
    failures.extend(
        _source_sequence_failures(
            source.get("transcript_delivery_failures"),
            "transcript_delivery_failures_not_empty",
        )
    )
    failures.extend(
        _source_sequence_failures(
            source.get("assistant_binding_failures"),
            "assistant_binding_failures_not_empty",
        )
    )
    failures.extend(
        _source_sequence_failures(
            source.get("command_execution_delivery_failures"),
            "command_execution_delivery_failures_not_empty",
        )
    )
    failures.extend(
        _source_sequence_failures(
            source.get("command_assistant_binding_failures"),
            "command_assistant_binding_failures_not_empty",
        )
    )
    failures.extend(
        _source_sequence_failures(
            source.get("blocking_reasons"),
            "working_flow_blocking_reasons_not_empty",
        )
    )
    return sorted(set(failures))


def _working_flow_failures(
    source: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    if metadata.get("working_flow_delivery_proof_file_read") is not True:
        failures.append("working_flow_delivery_proof_file_not_read")
    if metadata.get("working_flow_delivery_proof_file_valid_json") is not True:
        failures.append("working_flow_delivery_proof_file_json_not_valid")
    if metadata.get("working_flow_delivery_proof_file_mapping") is not True:
        failures.append("working_flow_delivery_proof_file_not_mapping")
    if source.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_delivery_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("working_flow_delivery_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("working_flow_delivery_machine_error_code_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("working_flow_delivery_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("working_flow_delivery_changed_files_not_empty")
    for field, reason in (
        ("codex_working_flow_delivery_proven", "working_flow_delivery_not_proven"),
        ("approved_delivery_surface_proven", "approved_delivery_surface_not_proven"),
        ("mcp_delivery_surface_proven", "mcp_delivery_surface_not_proven"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
        ("matching_mcp_tool_result_observed", "matching_mcp_tool_result_not_observed"),
        ("mcp_tool_result_structured_content_present", "mcp_tool_result_structured_content_missing"),
        ("structured_content_matches_handoff", "structured_content_not_bound_to_handoff"),
        ("assistant_response_observed", "assistant_response_not_observed"),
        ("assistant_response_after_tool_result", "assistant_response_not_after_tool_result"),
        ("assistant_response_bound_to_handoff_digest", "assistant_response_not_bound_to_handoff_digest"),
        ("codex_exec_assistant_continuation_proven", "assistant_continuation_not_proven"),
        ("live_provider_response_digest_bound_to_handoff", "live_provider_response_not_bound_to_handoff"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("codex_exec_transcript_sha256", "codex_exec_transcript_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    unsafe_failures = _working_flow_source_unsafe_failures(source)
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures


def build_custom_codex_visible_source_binding_proof_packet(
    working_flow_delivery_proof_packet: Mapping[str, Any] | None,
    visible_source_events: Sequence[Mapping[str, Any]] | None,
    *,
    visible_source_kind: str = VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
    route_secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(working_flow_delivery_proof_packet)
    events = [dict(event) for event in visible_source_events or []]
    metadata = dict(file_metadata or {})
    source_kind = _safe_text(visible_source_kind, limit=80)
    source_allowed = source_kind in APPROVED_VISIBLE_SOURCE_KINDS
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    source_transcript_digest = _hex_sha256(source.get("codex_exec_transcript_sha256"))
    visible_source_digest = _codex_exec_transcript_digest(events) if events else ""
    visible_source_digest_bound = bool(
        visible_source_digest
        and source_transcript_digest
        and visible_source_digest == source_transcript_digest
    )

    working_flow_failures, source_unsafe_failures = _working_flow_failures(
        source,
        metadata,
    )
    tool_result_index, tool_result = _matching_tool_result_index(events, handoff_digest)
    assistant_candidates = _assistant_output_candidates_after(
        events,
        after_index=tool_result_index,
        expected_digest=handoff_digest,
    )
    selected_assistant = _select_bound_assistant_candidate(assistant_candidates)

    visible_source_marker_observed = any(
        candidate.get("machine_marker_observed") is True
        for candidate in assistant_candidates
    )
    visible_source_marker_digest_mismatch = any(
        candidate.get("machine_marker_digest_mismatch") is True
        for candidate in assistant_candidates
    )
    visible_source_marker_binding_method = _safe_text(
        selected_assistant.get("binding_method"),
        limit=64,
    )
    visible_source_marker_digest = _hex_sha256(selected_assistant.get("binding_digest"))
    visible_source_bound_to_handoff = bool(
        visible_source_marker_digest and visible_source_marker_digest == handoff_digest
    )
    binding_method_allowed = visible_source_marker_binding_method in {
        BINDING_METHOD_SAFE_DIGEST_MARKER,
        BINDING_METHOD_SAFE_DIGEST_METADATA,
    }

    local_subagent_used_as_dip = _local_subagent_used_as_dip(events)
    route_secret_list = [
        str(secret) for secret in route_secret_values or [] if str(secret)
    ]
    secret_value_list = [
        str(secret) for secret in secret_values or [] if str(secret)
    ]
    effective_secret_values = sorted(set(secret_value_list + route_secret_list))
    visible_source_secret_value_present = _contains_secret_value(
        events,
        effective_secret_values,
    )
    visible_source_route_secret_value_present = _contains_secret_value(
        events,
        route_secret_list,
    )
    event_unsafe_failures = sorted(set(_unsafe_flag_failures(events)))
    if local_subagent_used_as_dip:
        event_unsafe_failures.append("native_codex_subagent_used_as_dip")
    if visible_source_secret_value_present:
        event_unsafe_failures.append("secret_value_present_in_visible_source")
    event_unsafe_failures = sorted(set(event_unsafe_failures))
    unsafe_failures = sorted(set(source_unsafe_failures + event_unsafe_failures))

    source_failures: list[str] = []
    if metadata.get("codex_exec_jsonl_file_present") is False:
        source_failures.append("visible_source_file_missing")
    if metadata.get("codex_exec_jsonl_file_read") is not True:
        source_failures.append("visible_source_file_not_read")
    if metadata.get("codex_exec_jsonl_file_valid_jsonl") is False:
        source_failures.append("visible_source_jsonl_not_valid")
    if metadata.get("codex_exec_jsonl_parse_error_count"):
        source_failures.append("visible_source_jsonl_parse_error")
    if not events:
        source_failures.append("visible_source_events_not_observed")
    if not visible_source_digest_bound:
        source_failures.append("visible_source_digest_not_bound")
    if tool_result_index is None:
        source_failures.append("matching_mcp_tool_result_not_observed")
    if not assistant_candidates:
        source_failures.append("visible_source_assistant_output_not_observed")

    assistant_event_index = selected_assistant.get("event_index")
    visible_source_after_delivery = bool(
        isinstance(tool_result_index, int)
        and isinstance(assistant_event_index, int)
        and assistant_event_index > tool_result_index
    )
    visible_source_observed = bool(
        events
        and visible_source_digest_bound
        and tool_result_index is not None
        and assistant_candidates
        and visible_source_after_delivery
    )

    binding_failures: list[str] = []
    if assistant_candidates and not visible_source_marker_observed:
        binding_failures.append("visible_source_marker_missing")
    if (
        visible_source_marker_digest_mismatch
        and not visible_source_bound_to_handoff
    ):
        binding_failures.append("visible_source_marker_digest_mismatch")
    if assistant_candidates and not visible_source_bound_to_handoff:
        binding_failures.append("visible_source_not_bound_to_handoff")
    if visible_source_marker_binding_method and not binding_method_allowed:
        binding_failures.append("visible_source_binding_method_invalid")
    if assistant_candidates and not visible_source_after_delivery:
        binding_failures.append("visible_source_not_after_delivery")

    blocking_reasons = sorted(
        set(
            working_flow_failures
            + ([] if source_allowed else ["approved_visible_source_kind_not_allowed"])
            + source_failures
            + binding_failures
            + unsafe_failures
        )
    )
    ok = bool(
        not blocking_reasons
        and source_allowed
        and visible_source_observed
        and visible_source_bound_to_handoff
        and visible_source_after_delivery
    )

    if ok:
        machine_error_code = VISIBLE_SOURCE_BINDING_OK
    elif working_flow_failures:
        machine_error_code = VISIBLE_SOURCE_BINDING_WORKING_FLOW_INVALID
    elif not source_allowed:
        machine_error_code = VISIBLE_SOURCE_BINDING_SOURCE_NOT_ALLOWED
    elif unsafe_failures:
        machine_error_code = VISIBLE_SOURCE_BINDING_PAYLOAD_UNSAFE
    elif source_failures:
        machine_error_code = VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED
    else:
        machine_error_code = VISIBLE_SOURCE_BINDING_NOT_BOUND

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_VISIBLE_SOURCE_BINDING_PACKET_KIND,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=80),
        "source_packet_status": _safe_text(source.get("status"), limit=32),
        "source_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "source_packet_file_backed": (
            metadata.get("working_flow_delivery_proof_file_read") is True
            and metadata.get("working_flow_delivery_proof_file_valid_json") is True
            and metadata.get("working_flow_delivery_proof_file_mapping") is True
        ),
        "working_flow_delivery_proof_valid": not working_flow_failures,
        "working_flow_delivery_failures": working_flow_failures,
        "source_unsafe_claim_failures": source_unsafe_failures,
        "working_flow_delivery_proven": (
            source.get("codex_working_flow_delivery_proven") is True
        ),
        "codex_working_flow_delivery_proven": (
            source.get("codex_working_flow_delivery_proven") is True
        ),
        "approved_delivery_surface_proven": (
            source.get("approved_delivery_surface_proven") is True
        ),
        "mcp_delivery_surface_proven": (
            source.get("mcp_delivery_surface_proven") is True
        ),
        "approved_handoff_ready": source.get("approved_handoff_ready") is True,
        "approved_handoff_payload_sanitized": (
            source.get("approved_handoff_payload_sanitized") is True
        ),
        "handoff_delivered": source.get("handoff_delivered") is True,
        "delivery_observed": source.get("delivery_observed") is True,
        "handoff_payload_digest": handoff_digest,
        "handoff_payload_digest_present": bool(handoff_digest),
        "codex_exec_assistant_continuation_proven": (
            source.get("codex_exec_assistant_continuation_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": (
            source.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "live_provider_response_proven": (
            source.get("live_provider_response_proven") is True
        ),
        "live_provider_response_digest_bound_to_handoff": (
            source.get("live_provider_response_digest_bound_to_handoff") is True
        ),
        "approved_visible_source_kind": source_kind,
        "approved_visible_source_allowed": source_allowed,
        "approved_visible_source_kinds_count": len(APPROVED_VISIBLE_SOURCE_KINDS),
        "visible_source_read": metadata.get("codex_exec_jsonl_file_read") is True,
        "visible_source_events_observed": bool(events),
        "visible_source_digest": visible_source_digest,
        "working_flow_codex_exec_transcript_sha256": source_transcript_digest,
        "visible_source_digest_bound": visible_source_digest_bound,
        "visible_source_digest_matches_working_flow": visible_source_digest_bound,
        "matching_mcp_tool_result_observed": tool_result_index is not None,
        "matching_mcp_tool_result_event_index_present": tool_result_index is not None,
        "mcp_tool_result_event_type": _safe_text(tool_result.get("event_type"), limit=128),
        "mcp_tool_result_item_type": _safe_text(tool_result.get("item_type"), limit=128),
        "visible_source_assistant_output_observed": bool(assistant_candidates),
        "visible_source_assistant_output_event_index_present": (
            isinstance(assistant_event_index, int)
        ),
        "visible_source_after_delivery": visible_source_after_delivery,
        "visible_source_marker_observed": visible_source_marker_observed,
        "visible_source_marker_digest_mismatch": visible_source_marker_digest_mismatch,
        "visible_source_marker_digest": visible_source_marker_digest,
        "visible_source_marker_binding_method": visible_source_marker_binding_method,
        "visible_source_bound_to_handoff": visible_source_bound_to_handoff,
        "visible_source_observed": visible_source_observed,
        "visible_source_binding_proven": ok,
        "custom_codex_visible_source_binding_proven": ok,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
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
        "visible_source_secret_value_present": visible_source_secret_value_present,
        "visible_source_route_secret_value_present": (
            visible_source_route_secret_value_present
        ),
        "route_secret_screening_values_count": len(route_secret_list),
        "route_secret_screening_proven": bool(route_secret_list),
        "visible_source_event_unsafe_failures": event_unsafe_failures,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved an approved visible source is digest-bound to the Codex working-flow handoff."
            if ok
            else "WBP blocked visible-source binding before proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=effective_secret_values,
        extra=extra,
    )


def run_custom_codex_visible_source_binding_proof_command(
    *,
    paths: RuntimePaths | None = None,
    working_flow_delivery_proof_file: str,
    visible_source_kind: str,
    codex_exec_jsonl_file: str,
    runtime_context_file: str | None = None,
) -> dict[str, Any]:
    proof_path = Path(working_flow_delivery_proof_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    proof_packet, proof_metadata = _read_working_flow_delivery_proof_file(proof_path)
    events, source_metadata = _read_jsonl_events_file(jsonl_path)
    context: dict[str, Any] = {}
    context_metadata: dict[str, Any] = {}
    if paths is not None or runtime_context_file:
        context_path = runtime_context_path(
            paths=paths or RuntimePaths.from_env(),
            runtime_context_file=runtime_context_file,
        )
        context, context_metadata = load_runtime_context_packet(context_path)
    return build_custom_codex_visible_source_binding_proof_packet(
        proof_packet,
        events,
        visible_source_kind=visible_source_kind,
        file_metadata={**proof_metadata, **source_metadata, **context_metadata},
        route_secret_values=_route_secret_values(context),
    )
