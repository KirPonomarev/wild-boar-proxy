# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .controlled_dispatch_handoff_proof import (
    CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
)
from .core import packets
from .observed_machine_handoff_delivery import (
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    DELIVERY_TRUTH_SOURCE_PROVEN,
    MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND,
    _canonical_json_digest,
)
from .router_hook_entry import _safe_text


CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND = (
    "wbp_codex_transcript_delivery_observation"
)

OBSERVATION_PATH_CODEX_EXEC_JSON_MCP_TOOL_RESULT = (
    "codex_exec_json_mcp_tool_result"
)
DELEGATE_TO_DIP_TOOL = "delegate_to_dip"
_ALLOWED_WBP_MCP_SERVER_NAMES = frozenset({"", "wbp", "wild_boar_proxy", "wild-boar-proxy"})

CODEX_TRANSCRIPT_DELIVERY_HANDOFF_PROOF_INVALID = (
    "WBP_CODEX_TRANSCRIPT_DELIVERY_HANDOFF_PROOF_INVALID"
)
CODEX_TRANSCRIPT_DELIVERY_TRANSCRIPT_NOT_OBSERVED = (
    "WBP_CODEX_TRANSCRIPT_DELIVERY_TRANSCRIPT_NOT_OBSERVED"
)
CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH = (
    "WBP_CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH"
)
CODEX_TRANSCRIPT_DELIVERY_PAYLOAD_UNSAFE = (
    "WBP_CODEX_TRANSCRIPT_DELIVERY_PAYLOAD_UNSAFE"
)


_UNSAFE_TRUE_FIELDS = {
    "raw_prompt_recorded": "raw_prompt_recorded",
    "prompt_text_recorded": "prompt_text_recorded",
    "natural_phrase_recorded": "natural_phrase_recorded",
    "raw_jsonl_recorded": "raw_jsonl_recorded",
    "tool_call_arguments_recorded": "tool_call_arguments_recorded",
    "route_candidate_recorded": "route_candidate_recorded",
    "selected_api_route_id_recorded": "selected_api_route_id_recorded",
    "raw_provider_response_recorded": "raw_provider_response_recorded",
    "provider_response_text_recorded": "provider_response_text_recorded",
    "provider_response_preview_recorded": "provider_response_preview_recorded",
    "raw_backend_details_exposed": "raw_backend_details_exposed",
    "secret_value_exposed": "secret_value_exposed",
    "fallback_used": "fallback_used",
    "local_imitation_used": "local_imitation_used",
    "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
    "live_provider_proven": "live_provider_must_not_be_claimed",
    "live_provider_response_proven": "live_provider_response_must_not_be_claimed",
    "external_live_provider_response_proven": (
        "external_live_provider_response_must_not_be_claimed"
    ),
    "native_free_chat_router_proven": (
        "native_free_chat_router_must_not_be_claimed"
    ),
    "product_ready": "product_ready_must_not_be_claimed",
    "command_origin_proven": "command_origin_must_not_be_claimed",
    "custom_codex_origin_proven": "custom_codex_origin_must_not_be_claimed",
    "native_custom_codex_flow_proven": (
        "native_custom_codex_flow_must_not_be_claimed"
    ),
    "native_router_hook_observed": "native_router_hook_must_not_be_claimed",
    "custom_codex_ui_visibility_proven": (
        "custom_codex_ui_visibility_must_not_be_claimed"
    ),
    "codex_working_flow_delivery_proven": (
        "codex_working_flow_delivery_must_not_be_claimed"
    ),
    "delivery_counts_as_custom_codex_ui": (
        "delivery_counts_as_custom_codex_ui_must_not_be_claimed"
    ),
}


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read_json_mapping_file(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "handoff_proof_file_required": True,
        "handoff_proof_file_present": path.exists(),
        "handoff_proof_file_read": False,
        "handoff_proof_file_valid_json": False,
        "handoff_proof_file_mapping": False,
        "handoff_proof_file_error_code": "",
        "handoff_proof_file_path_recorded": False,
    }
    if not path.exists():
        metadata["handoff_proof_file_error_code"] = "handoff_proof_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["handoff_proof_file_error_code"] = "handoff_proof_file_invalid"
        return {}, metadata
    metadata["handoff_proof_file_read"] = True
    metadata["handoff_proof_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["handoff_proof_file_error_code"] = "handoff_proof_file_not_mapping"
        return {}, metadata
    metadata["handoff_proof_file_mapping"] = True
    return dict(parsed), metadata


def _read_jsonl_events_file(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": path.exists(),
        "codex_exec_jsonl_file_read": False,
        "codex_exec_jsonl_file_valid_jsonl": False,
        "codex_exec_jsonl_file_error_code": "",
        "codex_exec_jsonl_file_path_recorded": False,
        "codex_exec_jsonl_parse_error_count": 0,
        "codex_exec_event_count": 0,
    }
    if not path.exists():
        metadata["codex_exec_jsonl_file_error_code"] = "codex_exec_jsonl_file_missing"
        return [], metadata
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        metadata["codex_exec_jsonl_file_error_code"] = "codex_exec_jsonl_file_unreadable"
        return [], metadata

    metadata["codex_exec_jsonl_file_read"] = True
    events: list[dict[str, Any]] = []
    parse_error_count = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            parse_error_count += 1
            continue
        if isinstance(parsed, Mapping):
            events.append(dict(parsed))
        else:
            parse_error_count += 1
    metadata["codex_exec_jsonl_parse_error_count"] = parse_error_count
    metadata["codex_exec_event_count"] = len(events)
    metadata["codex_exec_jsonl_file_valid_jsonl"] = parse_error_count == 0
    if parse_error_count:
        metadata["codex_exec_jsonl_file_error_code"] = "codex_exec_jsonl_invalid"
    return events, metadata


def _iter_mappings(value: Any, *, depth: int = 0) -> list[Mapping[str, Any]]:
    if depth > 8:
        return []
    if isinstance(value, Mapping):
        mappings: list[Mapping[str, Any]] = [value]
        for nested in value.values():
            mappings.extend(_iter_mappings(nested, depth=depth + 1))
        return mappings
    if isinstance(value, list):
        mappings = []
        for nested in value:
            mappings.extend(_iter_mappings(nested, depth=depth + 1))
        return mappings
    return []


def _first_text_field(mapping: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        text = _safe_text(mapping.get(field), limit=128)
        if text:
            return text
    return ""


def _structured_content_from_mapping(
    mapping: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for container in (
        mapping,
        mapping.get("result"),
        mapping.get("output"),
        mapping.get("response"),
        mapping.get("tool_result"),
        mapping.get("toolResult"),
    ):
        if not isinstance(container, Mapping):
            continue
        structured = container.get("structuredContent")
        if not isinstance(structured, Mapping):
            structured = container.get("structured_content")
        if isinstance(structured, Mapping):
            return structured
    return None


def _content_text_from_mapping(mapping: Mapping[str, Any]) -> str:
    for container in (
        mapping,
        mapping.get("result"),
        mapping.get("output"),
        mapping.get("response"),
        mapping.get("tool_result"),
        mapping.get("toolResult"),
    ):
        if not isinstance(container, Mapping):
            continue
        content = container.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, Mapping):
                    continue
                if _safe_text(part.get("type"), limit=32) != "text":
                    continue
                text = _safe_text(part.get("text"), limit=65536)
                if text:
                    return text
    return ""


def _json_mapping_from_text(text: str) -> Mapping[str, Any] | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _codex_exec_mcp_tool_result_candidates(
    events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for event in events:
        event_type = _safe_text(event.get("type"), limit=128)
        for mapping in _iter_mappings(event):
            structured = _structured_content_from_mapping(mapping)
            if not isinstance(structured, Mapping):
                continue
            item_type = _first_text_field(
                mapping,
                ("type", "kind", "item_type", "itemType"),
            )
            tool_name = _first_text_field(
                mapping,
                ("tool_name", "toolName", "tool", "name"),
            )
            server_name = _first_text_field(
                mapping,
                ("server_name", "serverName", "mcp_server", "mcpServer", "server"),
            )
            item_type_key = item_type.casefold()
            delivery_payload = (
                structured.get("packet_kind") == MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND
            )
            structured_mcp_result = bool(
                "mcp" in item_type_key
                and "tool" in item_type_key
                and (
                    "result" in item_type_key
                    or "response" in item_type_key
                    or delivery_payload
                )
            )
            tool_bound_result = bool(
                delivery_payload
                and (tool_name or server_name)
                and ("tool" in item_type_key or "result" in item_type_key)
            )
            if not delivery_payload and not structured_mcp_result:
                continue
            if delivery_payload and not structured_mcp_result and not tool_bound_result:
                continue
            content_text = _content_text_from_mapping(mapping)
            content_mapping = _json_mapping_from_text(content_text)
            content_digest = (
                _canonical_json_digest(content_mapping)
                if isinstance(content_mapping, Mapping)
                else ""
            )
            structured_digest = _canonical_json_digest(structured)
            is_error = False
            result = mapping.get("result")
            output = mapping.get("output")
            for container in (mapping, result, output):
                if isinstance(container, Mapping) and container.get("isError") is True:
                    is_error = True
            candidates.append(
                {
                    "event_type": event_type,
                    "item_type": item_type,
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "is_error": is_error,
                    "content_text_present": bool(content_text),
                    "content_text_json_mapping_present": isinstance(
                        content_mapping,
                        Mapping,
                    ),
                    "content_text_structured_content_digest": content_digest,
                    "content_text_json_matches_structured_content": bool(
                        content_digest and content_digest == structured_digest
                    ),
                    "structured_content": dict(structured),
                }
            )
    return candidates


def _unsafe_flag_failures(value: Any) -> list[str]:
    failures: set[str] = set()
    for mapping in _iter_mappings(value):
        for field, reason in _UNSAFE_TRUE_FIELDS.items():
            if mapping.get(field) is True:
                failures.add(reason)
    return sorted(failures)


def _codex_exec_transcript_digest(events: Sequence[Mapping[str, Any]]) -> str:
    return _canonical_json_digest({"events": [dict(event) for event in events]})


def _handoff_proof_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND:
        failures.append("handoff_proof_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("handoff_proof_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("handoff_proof_machine_error_code_not_ok")
    if source.get("handoff_completed") is not True:
        failures.append("handoff_not_completed")
    if source.get("handoff_envelope_built") is not True:
        failures.append("handoff_envelope_not_built")
    if source.get("machine_response_envelope_observed") is not True:
        failures.append("machine_response_envelope_not_observed")
    if source.get("machine_response_structured_content_present") is not True:
        failures.append("machine_response_structured_content_not_present")
    if source.get("handoff_surface_kind") != DELIVERY_SURFACE_MCP_TOOL_RESPONSE:
        failures.append("handoff_surface_must_be_mcp_tool_response")
    if not _hex_sha256(source.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_missing")
    if source.get("codex_working_flow_delivery_proven") is not False:
        failures.append("codex_working_flow_delivery_must_not_be_preclaimed")
    if source.get("delivery_counts_as_custom_codex_ui") is not False:
        failures.append("custom_codex_ui_delivery_must_not_be_preclaimed")
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


def _selected_candidate(
    candidates: Sequence[Mapping[str, Any]],
    expected_digest: str,
) -> Mapping[str, Any]:
    for candidate in reversed(candidates):
        structured = _mapping(candidate.get("structured_content"))
        payload = structured.get("handoff_payload")
        if isinstance(payload, Mapping) and _canonical_json_digest(payload) == expected_digest:
            return candidate
    return candidates[-1] if candidates else {}


def build_codex_transcript_delivery_observation_packet(
    handoff_proof_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    *,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(handoff_proof_packet)
    events = [dict(event) for event in codex_exec_events or []]
    metadata = dict(file_metadata or {})
    expected_handoff_payload_digest = _hex_sha256(source.get("handoff_payload_digest"))

    handoff_failures = _handoff_proof_failures(source)
    event_unsafe_failures = _unsafe_flag_failures(events)
    candidates = _codex_exec_mcp_tool_result_candidates(events)
    selected = _selected_candidate(candidates, expected_handoff_payload_digest)
    structured_content = _mapping(selected.get("structured_content"))

    declared_handoff_payload_digest = _hex_sha256(
        structured_content.get("handoff_payload_sha256")
    )
    observed_handoff_payload = structured_content.get("handoff_payload")
    observed_handoff_payload_digest = (
        _canonical_json_digest(observed_handoff_payload)
        if isinstance(observed_handoff_payload, Mapping)
        else ""
    )
    structured_content_digest = (
        _canonical_json_digest(structured_content) if structured_content else ""
    )
    structured_content_matches_handoff = bool(
        expected_handoff_payload_digest
        and observed_handoff_payload_digest
        and declared_handoff_payload_digest
        and observed_handoff_payload_digest == expected_handoff_payload_digest
        and declared_handoff_payload_digest == expected_handoff_payload_digest
    )

    transcript_failures: list[str] = []
    if metadata.get("codex_exec_jsonl_file_present") is False:
        transcript_failures.append("codex_exec_jsonl_file_missing")
    if metadata.get("codex_exec_jsonl_file_read") is False:
        transcript_failures.append("codex_exec_jsonl_file_not_read")
    if metadata.get("codex_exec_jsonl_parse_error_count"):
        transcript_failures.append("codex_exec_jsonl_parse_error")
    if not events:
        transcript_failures.append("codex_exec_json_events_not_observed")
    if not candidates:
        transcript_failures.append("mcp_tool_result_not_observed")
    if candidates and not structured_content:
        transcript_failures.append("mcp_tool_result_structured_content_missing")

    payload_failures: list[str] = []
    if structured_content:
        server_name = _safe_text(selected.get("server_name"), limit=128)
        tool_name = _safe_text(selected.get("tool_name"), limit=128)
        if not server_name or server_name not in _ALLOWED_WBP_MCP_SERVER_NAMES:
            payload_failures.append("mcp_tool_result_server_not_wbp")
        if tool_name != DELEGATE_TO_DIP_TOOL:
            payload_failures.append("mcp_tool_result_tool_name_invalid")
        if selected.get("content_text_present") is True:
            if selected.get("content_text_json_mapping_present") is not True:
                payload_failures.append("mcp_tool_result_content_text_not_json_mapping")
            elif selected.get("content_text_json_matches_structured_content") is not True:
                payload_failures.append(
                    "mcp_tool_result_content_text_structured_content_mismatch"
                )
        if structured_content.get("packet_kind") != MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND:
            payload_failures.append("delivery_payload_kind_invalid")
        if structured_content.get("delivery_surface_kind") != DELIVERY_SURFACE_MCP_TOOL_RESPONSE:
            payload_failures.append("delivery_surface_must_be_mcp_tool_response")
        if structured_content.get("delivery_truth_source") != DELIVERY_TRUTH_SOURCE_PROVEN:
            payload_failures.append("delivery_truth_source_invalid")
        if not isinstance(observed_handoff_payload, Mapping):
            payload_failures.append("handoff_payload_missing")
        if not declared_handoff_payload_digest:
            payload_failures.append("handoff_payload_declared_digest_missing")
        if observed_handoff_payload_digest and declared_handoff_payload_digest:
            if observed_handoff_payload_digest != declared_handoff_payload_digest:
                payload_failures.append("handoff_payload_declared_digest_mismatch")
        if (
            expected_handoff_payload_digest
            and observed_handoff_payload_digest
            and observed_handoff_payload_digest != expected_handoff_payload_digest
        ):
            payload_failures.append("handoff_payload_digest_mismatch")
        if selected.get("is_error") is True:
            payload_failures.append("mcp_tool_result_is_error")

    unsafe_failures = sorted(set(event_unsafe_failures + _unsafe_flag_failures(structured_content)))
    blocking_reasons = sorted(
        set(handoff_failures + transcript_failures + payload_failures + unsafe_failures)
    )
    ok = bool(
        not blocking_reasons
        and structured_content_matches_handoff
        and bool(structured_content)
    )

    if ok:
        machine_error_code = "OK"
    elif handoff_failures:
        machine_error_code = CODEX_TRANSCRIPT_DELIVERY_HANDOFF_PROOF_INVALID
    elif unsafe_failures:
        machine_error_code = CODEX_TRANSCRIPT_DELIVERY_PAYLOAD_UNSAFE
    elif transcript_failures:
        machine_error_code = CODEX_TRANSCRIPT_DELIVERY_TRANSCRIPT_NOT_OBSERVED
    else:
        machine_error_code = CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
        "handoff_proof_kind": _safe_text(source.get("packet_kind"), limit=80),
        "handoff_proof_status": _safe_text(source.get("status"), limit=32),
        "handoff_proof_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "handoff_proof_valid": not handoff_failures,
        "handoff_proof_failures": handoff_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "handoff_completed": source.get("handoff_completed") is True,
        "handoff_envelope_built": source.get("handoff_envelope_built") is True,
        "machine_response_envelope_observed": (
            source.get("machine_response_envelope_observed") is True
        ),
        "machine_response_structured_content_present": (
            source.get("machine_response_structured_content_present") is True
        ),
        "handoff_surface_kind": _safe_text(source.get("handoff_surface_kind"), limit=80),
        "handoff_payload_digest": expected_handoff_payload_digest,
        "observation_path": OBSERVATION_PATH_CODEX_EXEC_JSON_MCP_TOOL_RESULT,
        "codex_exec_json_events_observed": bool(events),
        "codex_exec_transcript_sha256": (
            _codex_exec_transcript_digest(events) if events else ""
        ),
        "mcp_tool_result_observed": bool(candidates),
        "mcp_tool_result_structured_content_present": bool(structured_content),
        "mcp_tool_result_event_type": _safe_text(selected.get("event_type"), limit=128),
        "mcp_tool_result_item_type": _safe_text(selected.get("item_type"), limit=128),
        "mcp_server_name_observed": _safe_text(selected.get("server_name"), limit=128),
        "mcp_tool_name_observed": _safe_text(selected.get("tool_name"), limit=128),
        "mcp_tool_result_is_error": selected.get("is_error") is True,
        "mcp_tool_result_name_allowed": _safe_text(
            selected.get("tool_name"),
            limit=128,
        )
        == DELEGATE_TO_DIP_TOOL,
        "mcp_tool_result_server_allowed": _safe_text(
            selected.get("server_name"),
            limit=128,
        )
        in _ALLOWED_WBP_MCP_SERVER_NAMES,
        "mcp_tool_result_content_text_present": selected.get("content_text_present")
        is True,
        "mcp_tool_result_content_text_json_mapping_present": selected.get(
            "content_text_json_mapping_present"
        )
        is True,
        "mcp_tool_result_content_text_json_matches_structured_content": selected.get(
            "content_text_json_matches_structured_content"
        )
        is True,
        "content_text_structured_content_digest": _hex_sha256(
            selected.get("content_text_structured_content_digest")
        ),
        "structured_content_kind": _safe_text(
            structured_content.get("packet_kind"),
            limit=80,
        ),
        "structured_content_digest": structured_content_digest,
        "declared_handoff_payload_digest": declared_handoff_payload_digest,
        "observed_handoff_payload_digest": observed_handoff_payload_digest,
        "structured_content_matches_handoff": structured_content_matches_handoff,
        "codex_transcript_delivery_observed": ok,
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
        "browser_can_supply_handoff_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP observed the approved handoff payload in a Codex exec JSON MCP result."
            if ok
            else "WBP blocked Codex transcript delivery observation before proof."
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


def run_codex_transcript_delivery_observation_command(
    *,
    handoff_proof_file: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    handoff_path = Path(handoff_proof_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    handoff_packet, handoff_metadata = _read_json_mapping_file(handoff_path)
    events, jsonl_metadata = _read_jsonl_events_file(jsonl_path)
    return build_codex_transcript_delivery_observation_packet(
        handoff_packet,
        events,
        file_metadata={**handoff_metadata, **jsonl_metadata},
    )
