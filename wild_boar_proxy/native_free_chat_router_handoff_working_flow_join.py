# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .native_free_chat_router_dispatch_admission import (
    NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_PACKET_KIND,
    NATIVE_FREE_CHAT_ROUTER_DISPATCH_HANDOFF_PACKET_KIND,
)
from .observed_machine_handoff_delivery import _canonical_json_digest
from .router_hook_entry import _safe_text


HANDOFF_WORKING_FLOW_JOIN_PACKET_KIND = (
    "wbp_native_free_chat_router_handoff_working_flow_join"
)

HANDOFF_WORKING_FLOW_JOIN_OK = "OK"
HANDOFF_WORKING_FLOW_JOIN_DISPATCH_ADMISSION_INVALID = (
    "WBP_HANDOFF_WORKING_FLOW_JOIN_DISPATCH_ADMISSION_INVALID"
)
HANDOFF_WORKING_FLOW_JOIN_HANDOFF_INVALID = (
    "WBP_HANDOFF_WORKING_FLOW_JOIN_HANDOFF_INVALID"
)
HANDOFF_WORKING_FLOW_JOIN_TRANSCRIPT_NOT_OBSERVED = (
    "WBP_HANDOFF_WORKING_FLOW_JOIN_TRANSCRIPT_NOT_OBSERVED"
)
HANDOFF_WORKING_FLOW_JOIN_NOT_BOUND = "WBP_HANDOFF_WORKING_FLOW_JOIN_NOT_BOUND"
HANDOFF_WORKING_FLOW_JOIN_PAYLOAD_UNSAFE = (
    "WBP_HANDOFF_WORKING_FLOW_JOIN_PAYLOAD_UNSAFE"
)

DELEGATE_TO_DIP_TOOL = "delegate_to_dip"
ALLOWED_WBP_MCP_SERVER_NAMES = frozenset({"", "wbp", "wild_boar_proxy", "wild-boar-proxy"})
ASSISTANT_BINDING_FIELDS = (
    "handoff_evidence_digest",
    "wbp_handoff_evidence_digest",
)
ASSISTANT_BINDING_PATTERN = re.compile(
    r"\b(?:handoff_evidence_digest|wbp_handoff_evidence_digest)=([0-9a-f]{64})\b"
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _path_sha256(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return ""


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


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


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _json_mapping_from_text(text: str) -> Mapping[str, Any]:
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


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


def _structured_content_from_mapping(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
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
    return {}


def _first_text_field(mapping: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        text = _safe_text(mapping.get(field), limit=128)
        if text:
            return text
    return ""


def _text_fields(mapping: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for field in ("text", "content", "message", "output_text", "summary"):
        value = mapping.get(field)
        if isinstance(value, str):
            text = _safe_text(value, limit=65536)
            if text:
                texts.append(text)
    return texts


def _unsafe_flag_failures(value: Any) -> list[str]:
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
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "custom_codex_ui_visibility_proven": (
            "custom_codex_ui_visibility_must_not_be_claimed"
        ),
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "native_free_chat_router_product_ready": (
            "native_free_chat_router_product_ready_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
    }
    failures: set[str] = set()
    for mapping in _iter_mappings(value):
        for field, reason in checks.items():
            if mapping.get(field) is True:
                failures.add(reason)
    return sorted(failures)


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


def _subagent_used_as_dip(events: Sequence[Mapping[str, Any]]) -> bool:
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
            if "subagent" in item_type.casefold() and re.search(
                r"(?i)\b(dip|agent\s*2)\b",
                combined,
            ):
                return True
    return False


def _computed_handoff_evidence_digest(handoff: Mapping[str, Any]) -> str:
    payload = dict(handoff)
    payload.pop("handoff_evidence_digest", None)
    return _canonical_json_digest(payload)


def _dispatch_admission_failures(
    packet: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("dispatch_admission_file_read") is not True:
        failures.append("dispatch_admission_file_not_read")
    if metadata.get("dispatch_admission_file_valid_json") is not True:
        failures.append("dispatch_admission_file_json_not_valid")
    if metadata.get("dispatch_admission_file_mapping") is not True:
        failures.append("dispatch_admission_file_not_mapping")
    if packet.get("packet_kind") != NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_PACKET_KIND:
        failures.append("dispatch_admission_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("dispatch_admission_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("dispatch_admission_machine_error_not_ok")
    if packet.get("effect") != "mutate":
        failures.append("dispatch_admission_effect_not_mutate")
    for field, reason in (
        (
            "native_free_chat_router_dispatch_admission_proven",
            "dispatch_admission_not_proven",
        ),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("natural_alias_command_detected", "natural_alias_command_not_detected"),
        (
            "natural_api_alias_command_detected",
            "natural_api_alias_command_not_detected",
        ),
        ("router_dispatch_admitted", "router_dispatch_not_admitted"),
        (
            "router_owned_dispatch_decision_bound",
            "router_owned_dispatch_decision_not_bound",
        ),
        ("api_lane_dispatch_admitted", "api_lane_dispatch_not_admitted"),
        ("api_lane_called", "api_lane_not_called"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("response_bound_to_proof", "response_not_bound_to_proof"),
        ("handoff_file_written", "handoff_file_not_written"),
        ("dispatch_result_digest_bound", "dispatch_result_digest_not_bound"),
        ("handoff_evidence_digest_bound", "handoff_evidence_digest_not_bound"),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    if packet.get("dispatch_status") != "proven":
        failures.append("dispatch_status_not_proven")
    for field, reason in (
        ("dispatch_result_digest", "dispatch_result_digest_missing"),
        ("handoff_evidence_digest", "handoff_evidence_digest_missing"),
        ("handoff_file_sha256", "handoff_file_digest_missing"),
        ("provider_response_digest", "provider_response_digest_missing"),
        (
            "controlled_provider_response_sha256",
            "controlled_provider_response_digest_missing",
        ),
    ):
        if not _hex_sha256(packet.get(field)):
            failures.append(reason)
    failures.extend(_unsafe_flag_failures(packet))
    return sorted(set(failures))


def _dispatch_handoff_failures(
    handoff: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("dispatch_handoff_file_read") is not True:
        failures.append("dispatch_handoff_file_not_read")
    if metadata.get("dispatch_handoff_file_valid_json") is not True:
        failures.append("dispatch_handoff_file_json_not_valid")
    if metadata.get("dispatch_handoff_file_mapping") is not True:
        failures.append("dispatch_handoff_file_not_mapping")
    if handoff.get("packet_kind") != NATIVE_FREE_CHAT_ROUTER_DISPATCH_HANDOFF_PACKET_KIND:
        failures.append("dispatch_handoff_packet_kind_invalid")
    for field, reason in (
        ("hook_prompt_digest_bound", "handoff_prompt_digest_not_bound"),
        (
            "hook_runtime_context_digest_bound",
            "handoff_runtime_context_digest_not_bound",
        ),
        ("alias_context_read", "handoff_alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "handoff_allowlist_not_enforced"),
        ("api_lane_called", "handoff_api_lane_not_called"),
        ("dispatch_proven", "handoff_dispatch_not_proven"),
        ("dispatch_result_digest_bound", "handoff_dispatch_result_not_bound"),
        ("response_bound_to_proof", "handoff_response_not_bound_to_proof"),
        ("route_bound_dispatch_proven", "handoff_route_bound_dispatch_not_proven"),
    ):
        if handoff.get(field) is not True:
            failures.append(reason)
    if handoff.get("dispatch_status") != "proven":
        failures.append("handoff_dispatch_status_not_proven")
    for field, reason in (
        ("dispatch_result_digest", "handoff_dispatch_result_digest_missing"),
        ("handoff_evidence_digest", "handoff_evidence_digest_missing"),
        ("provider_response_digest", "handoff_provider_response_digest_missing"),
        (
            "controlled_provider_response_sha256",
            "handoff_controlled_provider_response_digest_missing",
        ),
    ):
        if not _hex_sha256(handoff.get(field)):
            failures.append(reason)
    handoff_digest = _hex_sha256(handoff.get("handoff_evidence_digest"))
    computed_digest = _computed_handoff_evidence_digest(handoff) if handoff else ""
    if handoff_digest and computed_digest and handoff_digest != computed_digest:
        failures.append("handoff_evidence_digest_mismatch")
    failures.extend(_unsafe_flag_failures(handoff))
    return sorted(set(failures))


def _binding_failures(
    *,
    admission: Mapping[str, Any],
    handoff: Mapping[str, Any],
    handoff_file_sha256: str,
) -> list[str]:
    failures: list[str] = []
    for field, reason in (
        ("dispatch_result_digest", "dispatch_result_digest_mismatch"),
        ("handoff_evidence_digest", "handoff_evidence_digest_mismatch"),
        ("handoff_payload_digest", "handoff_payload_digest_mismatch"),
        ("provider_response_digest", "provider_response_digest_mismatch"),
        (
            "controlled_provider_response_sha256",
            "controlled_provider_response_digest_mismatch",
        ),
        ("selected_api_route_id_sha256", "selected_api_route_digest_mismatch"),
    ):
        left = _hex_sha256(admission.get(field))
        right = _hex_sha256(handoff.get(field))
        if left and right and left != right:
            failures.append(reason)
        elif not left or not right:
            failures.append(reason.replace("mismatch", "missing"))
    expected_file_digest = _hex_sha256(admission.get("handoff_file_sha256"))
    if expected_file_digest and handoff_file_sha256 and expected_file_digest != handoff_file_sha256:
        failures.append("handoff_file_sha256_mismatch")
    elif not expected_file_digest or not handoff_file_sha256:
        failures.append("handoff_file_sha256_missing")
    return sorted(set(failures))


def _tool_result_candidates(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_handoff: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_handoff_digest = _hex_sha256(expected_handoff.get("handoff_evidence_digest"))
    expected_structured_digest = _canonical_json_digest(dict(expected_handoff))
    candidates: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_type = _safe_text(event.get("type"), limit=128)
        for mapping in _iter_mappings(event):
            structured = _structured_content_from_mapping(mapping)
            if structured.get("packet_kind") != NATIVE_FREE_CHAT_ROUTER_DISPATCH_HANDOFF_PACKET_KIND:
                continue
            content_text = _content_text_from_mapping(mapping)
            content_mapping = _json_mapping_from_text(content_text)
            content_digest = (
                _canonical_json_digest(content_mapping)
                if isinstance(content_mapping, Mapping) and content_mapping
                else ""
            )
            structured_digest = _canonical_json_digest(dict(structured))
            handoff_digest = _hex_sha256(structured.get("handoff_evidence_digest"))
            candidates.append(
                {
                    "event_index": index,
                    "event_type": event_type,
                    "item_type": _first_text_field(
                        mapping,
                        ("type", "kind", "item_type", "itemType"),
                    ),
                    "server_name": _first_text_field(
                        mapping,
                        ("server_name", "serverName", "mcp_server", "mcpServer", "server"),
                    ),
                    "tool_name": _first_text_field(
                        mapping,
                        ("tool_name", "toolName", "tool", "name"),
                    ),
                    "is_error": any(
                        _mapping(container).get("isError") is True
                        for container in (mapping, mapping.get("result"), mapping.get("output"))
                    ),
                    "structured_content": dict(structured),
                    "structured_content_digest": structured_digest,
                    "structured_content_matches_handoff": bool(
                        structured_digest == expected_structured_digest
                        and handoff_digest == expected_handoff_digest
                    ),
                    "content_text_present": bool(content_text),
                    "content_text_json_mapping_present": bool(content_mapping),
                    "content_text_json_matches_structured_content": bool(
                        content_digest and content_digest == structured_digest
                    ),
                }
            )
    return candidates


def _selected_tool_result_candidate(
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    for candidate in candidates:
        if candidate.get("structured_content_matches_handoff") is True:
            return candidate
    return candidates[-1] if candidates else {}


def _assistant_mapping_is_output(event_type: str, mapping: Mapping[str, Any]) -> bool:
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
    return bool(
        role == "assistant"
        or "assistant" in item_type
        or event_type_key.startswith("response.output")
    )


def _assistant_binding_from_mapping(
    mapping: Mapping[str, Any],
    *,
    expected_digest: str,
) -> tuple[bool, bool, str, str]:
    marker_observed = False
    digest_mismatch = False
    for nested in _iter_mappings(mapping):
        for field in ASSISTANT_BINDING_FIELDS:
            digest = _hex_sha256(nested.get(field))
            if not digest:
                continue
            marker_observed = True
            if digest == expected_digest:
                return True, False, field, digest
            digest_mismatch = True
        for text in _text_fields(nested):
            for match in ASSISTANT_BINDING_PATTERN.finditer(text):
                digest = _hex_sha256(match.group(1))
                if not digest:
                    continue
                marker_observed = True
                if digest == expected_digest:
                    return True, False, "safe_text_digest_marker", digest
                digest_mismatch = True
    return marker_observed, digest_mismatch, "", ""


def _assistant_candidates_after(
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
            if not _assistant_mapping_is_output(event_type, mapping):
                continue
            marker_observed, digest_mismatch, binding_method, binding_digest = (
                _assistant_binding_from_mapping(mapping, expected_digest=expected_digest)
            )
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
                    "machine_marker_digest_mismatch": digest_mismatch,
                    "binding_method": binding_method,
                    "binding_digest": binding_digest,
                }
            )
    return candidates


def _selected_assistant_candidate(
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    for candidate in candidates:
        if _hex_sha256(candidate.get("binding_digest")):
            return candidate
    return candidates[0] if candidates else {}


def _transcript_failures(
    *,
    events: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    handoff: Mapping[str, Any],
    secret_values: Sequence[str],
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
    tool_candidates = _tool_result_candidates(events, expected_handoff=handoff)
    selected_tool = _selected_tool_result_candidate(tool_candidates)
    tool_result_index = (
        int(selected_tool["event_index"])
        if isinstance(selected_tool.get("event_index"), int)
        else None
    )
    if not tool_candidates:
        failures.append("dispatch_handoff_tool_result_not_observed")
    if selected_tool and selected_tool.get("structured_content_matches_handoff") is not True:
        failures.append("dispatch_handoff_tool_result_not_bound")
    if selected_tool:
        server_name = _safe_text(selected_tool.get("server_name"), limit=128)
        tool_name = _safe_text(selected_tool.get("tool_name"), limit=128)
        if server_name not in ALLOWED_WBP_MCP_SERVER_NAMES:
            failures.append("mcp_tool_result_server_not_wbp")
        if tool_name != DELEGATE_TO_DIP_TOOL:
            failures.append("mcp_tool_result_tool_name_invalid")
        if selected_tool.get("is_error") is True:
            failures.append("mcp_tool_result_is_error")
        if (
            selected_tool.get("content_text_present") is True
            and selected_tool.get("content_text_json_matches_structured_content")
            is not True
        ):
            failures.append("mcp_tool_result_content_text_structured_content_mismatch")

    expected_handoff_evidence_digest = _hex_sha256(handoff.get("handoff_evidence_digest"))
    assistant_candidates = _assistant_candidates_after(
        events,
        after_index=tool_result_index,
        expected_digest=expected_handoff_evidence_digest,
    )
    selected_assistant = _selected_assistant_candidate(assistant_candidates)
    assistant_response_observed = bool(assistant_candidates)
    assistant_response_after_handoff = bool(tool_result_index is not None and assistant_candidates)
    assistant_marker_observed = any(
        candidate.get("machine_marker_observed") is True for candidate in assistant_candidates
    )
    assistant_marker_digest_mismatch = any(
        candidate.get("machine_marker_digest_mismatch") is True
        for candidate in assistant_candidates
    )
    assistant_binding_digest = _hex_sha256(selected_assistant.get("binding_digest"))
    assistant_bound = bool(
        assistant_binding_digest
        and expected_handoff_evidence_digest
        and assistant_binding_digest == expected_handoff_evidence_digest
    )
    if not assistant_response_observed:
        failures.append("assistant_response_after_handoff_not_observed")
    if assistant_response_observed and not assistant_marker_observed:
        failures.append("assistant_response_handoff_marker_missing")
    if assistant_marker_digest_mismatch and not assistant_bound:
        failures.append("assistant_response_handoff_digest_mismatch")
    if assistant_response_observed and not assistant_bound:
        failures.append("assistant_response_not_bound_to_handoff")

    transcript_secret_value_present = _contains_secret_value(events, secret_values)
    unsafe_failures = _unsafe_flag_failures(events)
    if transcript_secret_value_present:
        unsafe_failures.append("secret_value_present_in_transcript")
    if _subagent_used_as_dip(events):
        unsafe_failures.append("native_codex_subagent_used_as_dip")
    failures.extend(sorted(set(unsafe_failures)))
    return sorted(set(failures)), {
        "codex_exec_json_events_observed": bool(events),
        "codex_exec_transcript_sha256": _canonical_json_digest(
            {"events": [dict(event) for event in events]}
        )
        if events
        else "",
        "dispatch_handoff_tool_result_observed": bool(tool_candidates),
        "dispatch_handoff_tool_result_bound": (
            selected_tool.get("structured_content_matches_handoff") is True
        ),
        "tool_result_event_index_present": tool_result_index is not None,
        "mcp_server_name_observed": _safe_text(
            selected_tool.get("server_name"),
            limit=128,
        ),
        "mcp_tool_name_observed": _safe_text(
            selected_tool.get("tool_name"),
            limit=128,
        ),
        "mcp_tool_result_content_text_present": (
            selected_tool.get("content_text_present") is True
        ),
        "mcp_tool_result_content_text_json_matches_structured_content": (
            selected_tool.get("content_text_json_matches_structured_content") is True
        ),
        "assistant_response_observed": assistant_response_observed,
        "assistant_response_after_handoff": assistant_response_after_handoff,
        "assistant_marker_observed": assistant_marker_observed,
        "assistant_marker_digest_mismatch": assistant_marker_digest_mismatch,
        "assistant_binding_method": _safe_text(
            selected_assistant.get("binding_method"),
            limit=80,
        ),
        "assistant_binding_digest": assistant_binding_digest,
        "assistant_continuation_bound_to_handoff": assistant_bound,
        "transcript_secret_value_present": transcript_secret_value_present,
        "transcript_unsafe_failures": sorted(set(unsafe_failures)),
    }


def _machine_error_code(
    *,
    dispatch_failures: Sequence[str],
    handoff_failures: Sequence[str],
    binding_failures: Sequence[str],
    transcript_failures: Sequence[str],
) -> str:
    if not dispatch_failures and not handoff_failures and not binding_failures and not transcript_failures:
        return HANDOFF_WORKING_FLOW_JOIN_OK
    unsafe_reasons = {
        "secret_value_present_in_transcript",
        "native_codex_subagent_used_as_dip",
        "fallback_used",
        "local_imitation_used",
        "raw_prompt_recorded",
        "raw_route_id_recorded",
        "raw_provider_response_recorded",
        "product_ready_must_not_be_claimed",
        "custom_codex_ui_visibility_must_not_be_claimed",
    }
    if any(reason in unsafe_reasons for reason in transcript_failures):
        return HANDOFF_WORKING_FLOW_JOIN_PAYLOAD_UNSAFE
    if dispatch_failures:
        return HANDOFF_WORKING_FLOW_JOIN_DISPATCH_ADMISSION_INVALID
    if handoff_failures:
        return HANDOFF_WORKING_FLOW_JOIN_HANDOFF_INVALID
    if transcript_failures and (
        "codex_exec_json_events_not_observed" in transcript_failures
        or "dispatch_handoff_tool_result_not_observed" in transcript_failures
        or "assistant_response_after_handoff_not_observed" in transcript_failures
    ):
        return HANDOFF_WORKING_FLOW_JOIN_TRANSCRIPT_NOT_OBSERVED
    return HANDOFF_WORKING_FLOW_JOIN_NOT_BOUND


def build_handoff_to_working_flow_join_packet(
    *,
    dispatch_admission_packet: Mapping[str, Any] | None,
    dispatch_handoff_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    dispatch_admission_file_metadata: Mapping[str, Any] | None = None,
    dispatch_handoff_file_metadata: Mapping[str, Any] | None = None,
    codex_exec_file_metadata: Mapping[str, Any] | None = None,
    dispatch_handoff_file_sha256: str = "",
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    admission = _mapping(dispatch_admission_packet)
    handoff = _mapping(dispatch_handoff_packet)
    events = [dict(event) for event in codex_exec_events or []]
    secret_list = list(secret_values or [])
    metadata = {
        **dict(dispatch_admission_file_metadata or {}),
        **dict(dispatch_handoff_file_metadata or {}),
        **dict(codex_exec_file_metadata or {}),
    }
    dispatch_failures = _dispatch_admission_failures(
        admission,
        dict(dispatch_admission_file_metadata or {}),
    )
    handoff_failures = _dispatch_handoff_failures(
        handoff,
        dict(dispatch_handoff_file_metadata or {}),
    )
    binding_failures = _binding_failures(
        admission=admission,
        handoff=handoff,
        handoff_file_sha256=dispatch_handoff_file_sha256,
    )
    transcript_failures, transcript_details = _transcript_failures(
        events=events,
        metadata=dict(codex_exec_file_metadata or {}),
        handoff=handoff,
        secret_values=secret_list,
    )
    source_secret_leak = packets.command_packet_has_secret_leak(
        {"dispatch_admission": dict(admission), "dispatch_handoff": dict(handoff)},
        secret_values=secret_list,
    )
    if source_secret_leak:
        binding_failures.append("source_file_secret_leak")
    blocking_reasons = sorted(
        set(dispatch_failures + handoff_failures + binding_failures + transcript_failures)
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        dispatch_failures=dispatch_failures,
        handoff_failures=handoff_failures,
        binding_failures=binding_failures,
        transcript_failures=transcript_failures,
    )
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": HANDOFF_WORKING_FLOW_JOIN_PACKET_KIND,
        "handoff_to_working_flow_join_proven": ok,
        "dispatch_admission_packet_kind": _safe_text(admission.get("packet_kind"), limit=80),
        "dispatch_admission_packet_status": _safe_text(admission.get("status"), limit=32),
        "dispatch_admission_packet_read": metadata.get("dispatch_admission_file_read")
        is True,
        "dispatch_handoff_packet_kind": _safe_text(handoff.get("packet_kind"), limit=80),
        "dispatch_handoff_file_read": metadata.get("dispatch_handoff_file_read") is True,
        "dispatch_admission_proven": (
            admission.get("native_free_chat_router_dispatch_admission_proven") is True
            and ok
        ),
        "natural_alias_command_detected": (
            admission.get("natural_alias_command_detected") is True and ok
        ),
        "natural_api_alias_command_detected": (
            admission.get("natural_api_alias_command_detected") is True and ok
        ),
        "router_dispatch_admitted": (
            admission.get("router_dispatch_admitted") is True and ok
        ),
        "router_owned_dispatch_decision_bound": (
            admission.get("router_owned_dispatch_decision_bound") is True and ok
        ),
        "router_dispatch_decision_truth_source": _safe_text(
            admission.get("router_dispatch_decision_truth_source"),
            limit=80,
        ),
        "api_lane_dispatch_admitted": (
            admission.get("api_lane_dispatch_admitted") is True and ok
        ),
        "handoff_file_written": admission.get("handoff_file_written") is True and ok,
        "handoff_file_sha256_bound": (
            _hex_sha256(admission.get("handoff_file_sha256"))
            and dispatch_handoff_file_sha256
            and admission.get("handoff_file_sha256") == dispatch_handoff_file_sha256
            and ok
        ),
        "dispatch_result_digest": _hex_sha256(handoff.get("dispatch_result_digest")),
        "admission_dispatch_result_digest": _hex_sha256(
            admission.get("dispatch_result_digest")
        ),
        "dispatch_result_digest_bound": (
            _hex_sha256(admission.get("dispatch_result_digest"))
            and _hex_sha256(handoff.get("dispatch_result_digest"))
            and admission.get("dispatch_result_digest") == handoff.get("dispatch_result_digest")
            and ok
        ),
        "handoff_evidence_digest": _hex_sha256(handoff.get("handoff_evidence_digest")),
        "admission_handoff_evidence_digest": _hex_sha256(
            admission.get("handoff_evidence_digest")
        ),
        "handoff_evidence_digest_bound": (
            _hex_sha256(admission.get("handoff_evidence_digest"))
            and _hex_sha256(handoff.get("handoff_evidence_digest"))
            and admission.get("handoff_evidence_digest") == handoff.get("handoff_evidence_digest")
            and ok
        ),
        "handoff_evidence_digest_recomputed": (
            _computed_handoff_evidence_digest(handoff)
            if handoff
            else ""
        ),
        "approved_handoff_source_used": (
            transcript_details.get("dispatch_handoff_tool_result_bound") is True and ok
        ),
        "codex_working_flow_delivery_proven": ok,
        "assistant_continuation_bound_to_handoff": (
            transcript_details.get("assistant_continuation_bound_to_handoff") is True
            and ok
        ),
        "assistant_response_observed": (
            transcript_details.get("assistant_response_observed") is True and ok
        ),
        "assistant_response_after_handoff": (
            transcript_details.get("assistant_response_after_handoff") is True and ok
        ),
        "codex_exec_json_events_observed": (
            transcript_details.get("codex_exec_json_events_observed") is True and ok
        ),
        "codex_exec_transcript_sha256": _hex_sha256(
            transcript_details.get("codex_exec_transcript_sha256")
        ),
        "dispatch_handoff_tool_result_observed": (
            transcript_details.get("dispatch_handoff_tool_result_observed") is True
            and ok
        ),
        "dispatch_handoff_tool_result_bound": (
            transcript_details.get("dispatch_handoff_tool_result_bound") is True and ok
        ),
        "tool_result_event_index_present": (
            transcript_details.get("tool_result_event_index_present") is True and ok
        ),
        "mcp_server_name_observed": _safe_text(
            transcript_details.get("mcp_server_name_observed"),
            limit=128,
        ),
        "mcp_tool_name_observed": _safe_text(
            transcript_details.get("mcp_tool_name_observed"),
            limit=128,
        ),
        "assistant_marker_observed": (
            transcript_details.get("assistant_marker_observed") is True and ok
        ),
        "assistant_marker_digest_mismatch": (
            transcript_details.get("assistant_marker_digest_mismatch") is True
        ),
        "assistant_binding_method": _safe_text(
            transcript_details.get("assistant_binding_method"),
            limit=80,
        ),
        "assistant_binding_digest": _hex_sha256(
            transcript_details.get("assistant_binding_digest")
        ),
        "source_file_secret_leak": source_secret_leak,
        "dispatch_admission_failures": dispatch_failures,
        "dispatch_handoff_failures": handoff_failures,
        "binding_failures": binding_failures,
        "transcript_failures": transcript_failures,
        "transcript_unsafe_failures": transcript_details.get("transcript_unsafe_failures", []),
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router_product_ready": True,
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
        "browser_can_supply_handoff_authority": False,
        "browser_can_supply_delivery_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a dispatch handoff joined into Codex working-flow assistant continuation."
            if ok
            else "WBP blocked dispatch handoff to working-flow join before proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=secret_list,
        extra=extra,
    )


def run_handoff_to_working_flow_join_command(
    *,
    dispatch_admission_file: str,
    dispatch_handoff_file: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    admission_path = Path(dispatch_admission_file).expanduser()
    handoff_path = Path(dispatch_handoff_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    admission_packet, admission_metadata = _read_json_mapping_file(
        admission_path,
        prefix="dispatch_admission",
    )
    handoff_packet, handoff_metadata = _read_json_mapping_file(
        handoff_path,
        prefix="dispatch_handoff",
    )
    events, jsonl_metadata = _read_jsonl_events_file(jsonl_path)
    return build_handoff_to_working_flow_join_packet(
        dispatch_admission_packet=admission_packet,
        dispatch_handoff_packet=handoff_packet,
        codex_exec_events=events,
        dispatch_admission_file_metadata=admission_metadata,
        dispatch_handoff_file_metadata=handoff_metadata,
        codex_exec_file_metadata=jsonl_metadata,
        dispatch_handoff_file_sha256=_path_sha256(handoff_path),
    )
