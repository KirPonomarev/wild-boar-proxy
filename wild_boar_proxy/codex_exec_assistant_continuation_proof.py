# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any

from .codex_transcript_delivery_observation import (
    CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
    _codex_exec_mcp_tool_result_candidates,
    _codex_exec_transcript_digest,
    _hex_sha256,
    _iter_mappings,
    _mapping,
    _read_jsonl_events_file,
    _selected_candidate,
    _unsafe_flag_failures,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .observed_machine_handoff_delivery import _canonical_json_digest
from .router_hook_entry import _safe_text


CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND = (
    "wbp_codex_exec_assistant_continuation_proof"
)

CODEX_EXEC_ASSISTANT_CONTINUATION_OBSERVATION_INVALID = (
    "WBP_CODEX_EXEC_ASSISTANT_CONTINUATION_OBSERVATION_INVALID"
)
CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED = (
    "WBP_CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED"
)
CODEX_EXEC_ASSISTANT_CONTINUATION_NOT_BOUND = (
    "WBP_CODEX_EXEC_ASSISTANT_CONTINUATION_NOT_BOUND"
)
CODEX_EXEC_ASSISTANT_CONTINUATION_PAYLOAD_UNSAFE = (
    "WBP_CODEX_EXEC_ASSISTANT_CONTINUATION_PAYLOAD_UNSAFE"
)

BINDING_METHOD_SAFE_DIGEST_METADATA = "safe_digest_metadata"
BINDING_METHOD_SAFE_DIGEST_MARKER = "safe_digest_marker"

_DIGEST_MARKER_PATTERN = re.compile(
    r"\b(?:wbp_handoff_digest|handoff_payload_digest|handoff_receipt_sha256)="
    r"([0-9a-f]{64})\b"
)
_ASSISTANT_ITEM_HINTS = ("assistant", "output_text", "output-message", "output_message")
_DIP_ALIAS_PATTERN = re.compile(r"(?i)\b(dip|agent\s*2)\b")


def _read_observation_file(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "transcript_observation_file_required": True,
        "transcript_observation_file_present": path.exists(),
        "transcript_observation_file_read": False,
        "transcript_observation_file_valid_json": False,
        "transcript_observation_file_mapping": False,
        "transcript_observation_file_error_code": "",
        "transcript_observation_file_path_recorded": False,
    }
    if not path.exists():
        metadata["transcript_observation_file_error_code"] = (
            "transcript_observation_file_missing"
        )
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["transcript_observation_file_error_code"] = (
            "transcript_observation_file_invalid"
        )
        return {}, metadata
    metadata["transcript_observation_file_read"] = True
    metadata["transcript_observation_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["transcript_observation_file_error_code"] = (
            "transcript_observation_file_not_mapping"
        )
        return {}, metadata
    metadata["transcript_observation_file_mapping"] = True
    return dict(parsed), metadata


def _observation_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND:
        failures.append("transcript_observation_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("transcript_observation_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("transcript_observation_machine_error_code_not_ok")
    if source.get("codex_transcript_delivery_observed") is not True:
        failures.append("transcript_delivery_not_observed")
    if source.get("structured_content_matches_handoff") is not True:
        failures.append("structured_content_not_bound_to_handoff")
    if source.get("mcp_tool_result_observed") is not True:
        failures.append("mcp_tool_result_not_observed")
    if source.get("mcp_tool_result_structured_content_present") is not True:
        failures.append("mcp_tool_result_structured_content_missing")
    if not _hex_sha256(source.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_missing")
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


def _matching_tool_result_index(
    events: Sequence[Mapping[str, Any]],
    expected_digest: str,
) -> tuple[int | None, Mapping[str, Any]]:
    for index, event in enumerate(events):
        candidates = _codex_exec_mcp_tool_result_candidates([event])
        selected = _selected_candidate(candidates, expected_digest)
        structured = _mapping(selected.get("structured_content"))
        payload = structured.get("handoff_payload")
        if isinstance(payload, Mapping) and _canonical_json_digest(payload) == expected_digest:
            return index, selected
    return None, {}


def _text_fields(mapping: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for field in ("text", "content", "message", "output_text", "summary"):
        value = mapping.get(field)
        if isinstance(value, str):
            text = _safe_text(value, limit=65536)
            if text:
                texts.append(text)
    return texts


def _marker_from_mapping(
    mapping: Mapping[str, Any],
    expected_digest: str,
) -> tuple[bool, bool, str, str]:
    marker_observed = False
    digest_mismatch = False
    for nested in _iter_mappings(mapping):
        for field in (
            "wbp_handoff_digest",
            "handoff_payload_digest",
            "handoff_receipt_sha256",
        ):
            digest = _hex_sha256(nested.get(field))
            if not digest:
                continue
            marker_observed = True
            if digest == expected_digest:
                return True, False, BINDING_METHOD_SAFE_DIGEST_METADATA, digest
            digest_mismatch = True
        for text in _text_fields(nested):
            for match in _DIGEST_MARKER_PATTERN.finditer(text):
                digest = _hex_sha256(match.group(1))
                if not digest:
                    continue
                marker_observed = True
                if digest == expected_digest:
                    return True, False, BINDING_METHOD_SAFE_DIGEST_MARKER, digest
                digest_mismatch = True
    return marker_observed, digest_mismatch, "", ""


def _mapping_is_assistant_output(event_type: str, mapping: Mapping[str, Any]) -> bool:
    item_type = _safe_text(
        mapping.get("type") or mapping.get("kind") or mapping.get("item_type"),
        limit=128,
    ).casefold()
    role = _safe_text(mapping.get("role"), limit=64).casefold()
    event_type_key = event_type.casefold()
    if "mcp" in item_type or "tool" in item_type:
        return False
    if "subagent" in item_type or item_type == "agent_message":
        return False
    if role == "assistant":
        return True
    if any(hint in item_type for hint in _ASSISTANT_ITEM_HINTS):
        return True
    return event_type_key.startswith("response.output")


def _assistant_output_candidates_after(
    events: Sequence[Mapping[str, Any]],
    *,
    after_index: int | None,
    expected_digest: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if after_index is None:
        return candidates
    for index, event in enumerate(events):
        if index <= after_index:
            continue
        event_type = _safe_text(event.get("type"), limit=128)
        for mapping in _iter_mappings(event):
            if not _mapping_is_assistant_output(event_type, mapping):
                continue
            (
                marker_observed,
                marker_digest_mismatch,
                binding_method,
                binding_digest,
            ) = _marker_from_mapping(mapping, expected_digest)
            candidates.append(
                {
                    "event_index": index,
                    "event_type": event_type,
                    "item_type": _safe_text(
                        mapping.get("type")
                        or mapping.get("kind")
                        or mapping.get("item_type"),
                        limit=128,
                    ),
                    "role": _safe_text(mapping.get("role"), limit=64),
                    "machine_marker_observed": marker_observed,
                    "machine_marker_digest_mismatch": marker_digest_mismatch,
                    "binding_method": binding_method,
                    "binding_digest": binding_digest,
                }
            )
    return candidates


def _select_bound_assistant_candidate(
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    for candidate in candidates:
        if candidate.get("binding_digest"):
            return candidate
    return candidates[0] if candidates else {}


def _local_subagent_used_as_dip(events: Sequence[Mapping[str, Any]]) -> bool:
    for event in events:
        for mapping in _iter_mappings(event):
            item_type = _safe_text(
                mapping.get("type") or mapping.get("kind") or mapping.get("item_type"),
                limit=128,
            )
            name = _safe_text(
                mapping.get("name")
                or mapping.get("agent_name")
                or mapping.get("display_name"),
                limit=128,
            )
            combined = " ".join([item_type, name, *_text_fields(mapping)])
            if not combined.strip():
                continue
            if "subagent" in item_type.casefold() and _DIP_ALIAS_PATTERN.search(combined):
                return True
    return False


def _contains_secret_value(value: Any, secret_values: Sequence[str] | None) -> bool:
    needles = [str(secret) for secret in secret_values or [] if str(secret)]
    if not needles:
        return False
    if isinstance(value, str):
        return any(needle in value for needle in needles)
    if isinstance(value, Mapping):
        return any(_contains_secret_value(item, needles) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_value(item, needles) for item in value)
    return False


def build_codex_exec_assistant_continuation_proof_packet(
    transcript_observation_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    *,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(transcript_observation_packet)
    events = [dict(event) for event in codex_exec_events or []]
    metadata = dict(file_metadata or {})
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    current_transcript_digest = _codex_exec_transcript_digest(events) if events else ""
    observation_transcript_digest = _hex_sha256(
        source.get("codex_exec_transcript_sha256")
    )
    same_codex_exec_jsonl_bound = bool(
        current_transcript_digest
        and observation_transcript_digest
        and current_transcript_digest == observation_transcript_digest
    )

    observation_failures = _observation_failures(source)
    tool_result_index, tool_result = _matching_tool_result_index(events, handoff_digest)
    assistant_candidates = _assistant_output_candidates_after(
        events,
        after_index=tool_result_index,
        expected_digest=handoff_digest,
    )
    selected_assistant = _select_bound_assistant_candidate(assistant_candidates)

    local_subagent_used_as_dip = _local_subagent_used_as_dip(events)
    transcript_secret_value_present = _contains_secret_value(events, secret_values)
    unsafe_failures = sorted(set(_unsafe_flag_failures(events) + _unsafe_flag_failures(source)))
    if local_subagent_used_as_dip:
        unsafe_failures.append("native_codex_subagent_used_as_dip")
    if transcript_secret_value_present:
        unsafe_failures.append("secret_value_present_in_transcript")
    unsafe_failures = sorted(set(unsafe_failures))

    transcript_failures: list[str] = []
    if metadata.get("codex_exec_jsonl_file_present") is False:
        transcript_failures.append("codex_exec_jsonl_file_missing")
    if metadata.get("codex_exec_jsonl_file_read") is False:
        transcript_failures.append("codex_exec_jsonl_file_not_read")
    if metadata.get("codex_exec_jsonl_parse_error_count"):
        transcript_failures.append("codex_exec_jsonl_parse_error")
    if not events:
        transcript_failures.append("codex_exec_json_events_not_observed")
    if not observation_transcript_digest:
        transcript_failures.append("transcript_observation_digest_missing")
    elif current_transcript_digest and current_transcript_digest != observation_transcript_digest:
        transcript_failures.append("codex_exec_transcript_digest_mismatch")
    if tool_result_index is None:
        transcript_failures.append("matching_mcp_tool_result_not_observed")
    assistant_response_observed = bool(assistant_candidates)
    assistant_response_after_tool_result = bool(
        tool_result_index is not None and assistant_candidates
    )
    if not assistant_response_observed:
        transcript_failures.append("assistant_response_after_tool_result_not_observed")

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
    if assistant_response_observed and not assistant_machine_marker_observed:
        binding_failures.append("assistant_response_machine_digest_marker_missing")
    if assistant_marker_digest_mismatch and not assistant_response_bound_to_handoff_digest:
        binding_failures.append("assistant_response_handoff_digest_mismatch")
    if assistant_response_observed and not assistant_response_bound_to_handoff_digest:
        binding_failures.append("assistant_response_not_bound_to_handoff_digest")

    blocking_reasons = sorted(
        set(observation_failures + transcript_failures + binding_failures + unsafe_failures)
    )
    ok = bool(
        not blocking_reasons
        and assistant_response_after_tool_result
        and assistant_response_bound_to_handoff_digest
    )

    if ok:
        machine_error_code = "OK"
    elif observation_failures:
        machine_error_code = CODEX_EXEC_ASSISTANT_CONTINUATION_OBSERVATION_INVALID
    elif unsafe_failures:
        machine_error_code = CODEX_EXEC_ASSISTANT_CONTINUATION_PAYLOAD_UNSAFE
    elif transcript_failures:
        machine_error_code = CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED
    else:
        machine_error_code = CODEX_EXEC_ASSISTANT_CONTINUATION_NOT_BOUND

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
        "transcript_observation_kind": _safe_text(source.get("packet_kind"), limit=80),
        "transcript_observation_status": _safe_text(source.get("status"), limit=32),
        "transcript_observation_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "transcript_observation_valid": not observation_failures,
        "transcript_observation_failures": observation_failures,
        "transcript_delivery_observed": (
            source.get("codex_transcript_delivery_observed") is True
        ),
        "mcp_tool_result_observed": source.get("mcp_tool_result_observed") is True,
        "mcp_tool_result_structured_content_present": (
            source.get("mcp_tool_result_structured_content_present") is True
        ),
        "structured_content_matches_handoff": (
            source.get("structured_content_matches_handoff") is True
        ),
        "handoff_payload_digest": handoff_digest,
        "codex_exec_json_events_observed": bool(events),
        "codex_exec_transcript_sha256": current_transcript_digest,
        "transcript_observation_codex_exec_transcript_sha256": (
            observation_transcript_digest
        ),
        "same_codex_exec_jsonl_bound": same_codex_exec_jsonl_bound,
        "same_codex_exec_jsonl_digest_matches": same_codex_exec_jsonl_bound,
        "matching_mcp_tool_result_observed": tool_result_index is not None,
        "matching_mcp_tool_result_event_index_present": tool_result_index is not None,
        "mcp_tool_result_event_type": _safe_text(tool_result.get("event_type"), limit=128),
        "mcp_tool_result_item_type": _safe_text(tool_result.get("item_type"), limit=128),
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
        "codex_exec_assistant_continuation_proven": ok,
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
        "transcript_secret_value_present": transcript_secret_value_present,
        "browser_can_supply_handoff_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved Codex exec assistant continuation after a digest-bound MCP result."
            if ok
            else "WBP blocked Codex exec assistant continuation before proof."
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


def run_codex_exec_assistant_continuation_proof_command(
    *,
    transcript_observation_file: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    observation_path = Path(transcript_observation_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    observation_packet, observation_metadata = _read_observation_file(observation_path)
    events, jsonl_metadata = _read_jsonl_events_file(jsonl_path)
    return build_codex_exec_assistant_continuation_proof_packet(
        observation_packet,
        events,
        file_metadata={**observation_metadata, **jsonl_metadata},
    )
