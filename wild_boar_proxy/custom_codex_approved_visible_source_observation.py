# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_exec_assistant_continuation_proof import (
    CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
    _assistant_output_candidates_after,
    _contains_secret_value,
    _local_subagent_used_as_dip,
    _matching_tool_result_index,
    _read_observation_file,
    _select_bound_assistant_candidate,
)
from .codex_transcript_delivery_observation import (
    _codex_exec_transcript_digest,
    _hex_sha256,
    _mapping,
    _read_jsonl_events_file,
    _unsafe_flag_failures,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .router_hook_entry import _safe_text


CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_PACKET_KIND = (
    "wbp_custom_codex_approved_visible_source_observation"
)

VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT = "codex_exec_json_assistant_output"
APPROVED_VISIBLE_SOURCE_KINDS = frozenset(
    {VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT}
)

VISIBLE_SOURCE_OBSERVATION_CONTINUATION_INVALID = (
    "WBP_VISIBLE_SOURCE_OBSERVATION_CONTINUATION_INVALID"
)
VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_ALLOWED = (
    "WBP_VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_ALLOWED"
)
VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_OBSERVED = (
    "WBP_VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_OBSERVED"
)
VISIBLE_SOURCE_OBSERVATION_NOT_BOUND = "WBP_VISIBLE_SOURCE_OBSERVATION_NOT_BOUND"
VISIBLE_SOURCE_OBSERVATION_PAYLOAD_UNSAFE = (
    "WBP_VISIBLE_SOURCE_OBSERVATION_PAYLOAD_UNSAFE"
)


def _read_continuation_proof_file(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source, metadata = _read_observation_file(path)
    renamed = {
        key.replace("transcript_observation_file", "assistant_continuation_proof_file"): value
        for key, value in metadata.items()
    }
    return source, renamed


def _continuation_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND:
        failures.append("assistant_continuation_proof_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("assistant_continuation_proof_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("assistant_continuation_proof_machine_error_code_not_ok")
    if source.get("codex_exec_assistant_continuation_proven") is not True:
        failures.append("assistant_continuation_not_proven")
    if source.get("assistant_response_bound_to_handoff_digest") is not True:
        failures.append("assistant_response_not_bound_to_handoff_digest")
    if source.get("assistant_response_after_tool_result") is not True:
        failures.append("assistant_response_not_after_tool_result")
    if source.get("same_codex_exec_jsonl_bound") is not True:
        failures.append("same_codex_exec_jsonl_not_bound")
    if not _hex_sha256(source.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_missing")
    if not _hex_sha256(source.get("codex_exec_transcript_sha256")):
        failures.append("codex_exec_transcript_digest_missing")
    if source.get("custom_codex_ui_visibility_proven") is not False:
        failures.append("custom_codex_ui_visibility_must_not_be_preclaimed")
    if source.get("codex_working_flow_delivery_proven") is not False:
        failures.append("codex_working_flow_delivery_must_not_be_preclaimed")
    if source.get("native_free_chat_router_proven") is not False:
        failures.append("native_free_chat_router_must_not_be_preclaimed")
    if source.get("live_provider_proven") is not False:
        failures.append("live_provider_must_not_be_preclaimed")
    if source.get("product_ready") is not False:
        failures.append("product_ready_must_not_be_preclaimed")
    if source.get("state_written") is not False:
        failures.append("state_write_not_allowed")
    if source.get("evidence_written") is not False:
        failures.append("evidence_write_not_allowed")
    if source.get("file_mutation_attempted") is not False:
        failures.append("file_mutation_not_allowed")
    failures.extend(_unsafe_flag_failures(source))
    return sorted(set(failures))


def build_custom_codex_approved_visible_source_observation_packet(
    assistant_continuation_proof_packet: Mapping[str, Any] | None,
    visible_source_events: Sequence[Mapping[str, Any]] | None,
    *,
    visible_source_kind: str = VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(assistant_continuation_proof_packet)
    events = [dict(event) for event in visible_source_events or []]
    metadata = dict(file_metadata or {})
    source_kind = _safe_text(visible_source_kind, limit=80)
    source_allowed = source_kind in APPROVED_VISIBLE_SOURCE_KINDS
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    continuation_transcript_digest = _hex_sha256(
        source.get("codex_exec_transcript_sha256")
    )
    visible_source_digest = _codex_exec_transcript_digest(events) if events else ""
    visible_source_digest_bound = bool(
        visible_source_digest
        and continuation_transcript_digest
        and visible_source_digest == continuation_transcript_digest
    )

    continuation_failures = _continuation_failures(source)
    tool_result_index, _tool_result = _matching_tool_result_index(events, handoff_digest)
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
    visible_source_marker_bound_to_handoff_digest = bool(
        visible_source_marker_digest and visible_source_marker_digest == handoff_digest
    )

    local_subagent_used_as_dip = _local_subagent_used_as_dip(events)
    visible_source_secret_value_present = _contains_secret_value(events, secret_values)
    unsafe_failures = sorted(set(_unsafe_flag_failures(events) + _unsafe_flag_failures(source)))
    if local_subagent_used_as_dip:
        unsafe_failures.append("native_codex_subagent_used_as_dip")
    if visible_source_secret_value_present:
        unsafe_failures.append("secret_value_present_in_visible_source")
    unsafe_failures = sorted(set(unsafe_failures))

    source_failures: list[str] = []
    if metadata.get("codex_exec_jsonl_file_present") is False:
        source_failures.append("visible_source_file_missing")
    if metadata.get("codex_exec_jsonl_file_read") is False:
        source_failures.append("visible_source_file_not_read")
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

    binding_failures: list[str] = []
    if assistant_candidates and not visible_source_marker_observed:
        binding_failures.append("visible_source_marker_missing")
    if (
        visible_source_marker_digest_mismatch
        and not visible_source_marker_bound_to_handoff_digest
    ):
        binding_failures.append("visible_source_marker_digest_mismatch")
    if assistant_candidates and not visible_source_marker_bound_to_handoff_digest:
        binding_failures.append("visible_source_marker_not_bound_to_handoff_digest")

    blocking_reasons = sorted(
        set(
            continuation_failures
            + ([] if source_allowed else ["approved_visible_source_kind_not_allowed"])
            + source_failures
            + binding_failures
            + unsafe_failures
        )
    )
    ok = bool(
        not blocking_reasons
        and source_allowed
        and visible_source_digest_bound
        and visible_source_marker_bound_to_handoff_digest
    )

    if ok:
        machine_error_code = "OK"
    elif continuation_failures:
        machine_error_code = VISIBLE_SOURCE_OBSERVATION_CONTINUATION_INVALID
    elif not source_allowed:
        machine_error_code = VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_ALLOWED
    elif unsafe_failures:
        machine_error_code = VISIBLE_SOURCE_OBSERVATION_PAYLOAD_UNSAFE
    elif source_failures:
        machine_error_code = VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_OBSERVED
    else:
        machine_error_code = VISIBLE_SOURCE_OBSERVATION_NOT_BOUND

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_PACKET_KIND,
        "assistant_continuation_proof_kind": _safe_text(
            source.get("packet_kind"),
            limit=80,
        ),
        "assistant_continuation_proof_status": _safe_text(
            source.get("status"),
            limit=32,
        ),
        "assistant_continuation_proof_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "assistant_continuation_proof_valid": not continuation_failures,
        "assistant_continuation_proof_failures": continuation_failures,
        "codex_exec_assistant_continuation_proven": (
            source.get("codex_exec_assistant_continuation_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": (
            source.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "same_codex_exec_jsonl_bound": source.get("same_codex_exec_jsonl_bound") is True,
        "handoff_payload_digest": handoff_digest,
        "approved_visible_source_kind": source_kind,
        "approved_visible_source_allowed": source_allowed,
        "approved_visible_source_kinds_count": len(APPROVED_VISIBLE_SOURCE_KINDS),
        "visible_source_read": metadata.get("codex_exec_jsonl_file_read") is True,
        "visible_source_events_observed": bool(events),
        "visible_source_digest": visible_source_digest,
        "assistant_continuation_source_digest": continuation_transcript_digest,
        "visible_source_digest_bound": visible_source_digest_bound,
        "visible_source_digest_matches_continuation": visible_source_digest_bound,
        "matching_mcp_tool_result_observed": tool_result_index is not None,
        "visible_source_assistant_output_observed": bool(assistant_candidates),
        "visible_source_marker_observed": visible_source_marker_observed,
        "visible_source_marker_digest_mismatch": visible_source_marker_digest_mismatch,
        "visible_source_marker_digest": visible_source_marker_digest,
        "visible_source_marker_binding_method": visible_source_marker_binding_method,
        "visible_source_marker_bound_to_handoff_digest": (
            visible_source_marker_bound_to_handoff_digest
        ),
        "custom_codex_approved_visible_source_observed": ok,
        "custom_codex_visible_flow_observed": ok,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
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
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP observed the digest-bound continuation in an approved visible source."
            if ok
            else "WBP blocked approved visible-source observation before proof."
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


def run_custom_codex_approved_visible_source_observation_command(
    *,
    assistant_continuation_proof_file: str,
    visible_source_kind: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    proof_path = Path(assistant_continuation_proof_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    proof_packet, proof_metadata = _read_continuation_proof_file(proof_path)
    events, source_metadata = _read_jsonl_events_file(jsonl_path)
    return build_custom_codex_approved_visible_source_observation_packet(
        proof_packet,
        events,
        visible_source_kind=visible_source_kind,
        file_metadata={**proof_metadata, **source_metadata},
    )
