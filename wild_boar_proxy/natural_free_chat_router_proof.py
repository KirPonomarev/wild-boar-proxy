# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .mcp_delegate import (
    build_codex_exec_tool_call_observation_packet,
    build_prompt_observation_packet,
)
from .official_mcp_admission_proof import explicit_tool_instruction_used
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


NATURAL_FREE_CHAT_ROUTER_PROOF_PACKET_KIND = "wbp_natural_free_chat_router_proof"
NATIVE_MODEL_DID_NOT_CALL_WBP_TOOL = "NATIVE_MODEL_DID_NOT_CALL_WBP_TOOL"
NATURAL_PROMPT_NOT_OBSERVED = "NATURAL_PROMPT_NOT_OBSERVED"
USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN = "USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN"
ALIAS_INTENT_NOT_RECOGNIZED = "ALIAS_INTENT_NOT_RECOGNIZED"
NATURAL_MCP_TOOL_CALL_NOT_BOUND = "NATURAL_MCP_TOOL_CALL_NOT_BOUND"
NATURAL_FREE_CHAT_API_LANE_NOT_PROVEN = "NATURAL_FREE_CHAT_API_LANE_NOT_PROVEN"
NATURAL_FREE_CHAT_HANDOFF_NOT_PROVEN = "NATURAL_FREE_CHAT_HANDOFF_NOT_PROVEN"
NATURAL_FREE_CHAT_LOCAL_IMPERSONATION_BLOCKED = (
    "NATURAL_FREE_CHAT_LOCAL_IMPERSONATION_BLOCKED"
)
NATURAL_FREE_CHAT_SECRET_EXPOSURE_BLOCKED = (
    "NATURAL_FREE_CHAT_SECRET_EXPOSURE_BLOCKED"
)
NATURAL_FREE_CHAT_ROUTER_NOT_PROVEN = "NATURAL_FREE_CHAT_ROUTER_NOT_PROVEN"


def _safe_text(value: object, *, limit: int = 4096) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=128)
    return text if len(text) == 64 and all(ch in "0123456789abcdef" for ch in text) else ""


def _packet_sha256(packet: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(packet, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    )


def _read_json_mapping_file(path: Path, *, prefix: str) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_present": path.exists(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_sha256": "",
        f"{prefix}_file_path_recorded": False,
    }
    if not path.exists():
        return {}, metadata
    try:
        text = path.read_text(encoding="utf-8")
        parsed = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    metadata[f"{prefix}_file_sha256"] = _sha256_text(text)
    if not isinstance(parsed, Mapping):
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _read_text_file(path: Path, *, prefix: str) -> tuple[str, dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_present": path.exists(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_sha256": "",
        f"{prefix}_file_path_recorded": False,
    }
    if not path.exists():
        return "", metadata
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "", metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_sha256"] = _sha256_text(text)
    return text, metadata


def _jsonl_event_objects(jsonl_text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in str(jsonl_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            events.append(dict(parsed))
    return events


def _iter_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for item in value.values():
            found.extend(_iter_mappings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_iter_mappings(item))
    return found


def _first_text_field(mapping: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        text = _safe_text(mapping.get(field), limit=256)
        if text:
            return text
    return ""


def _json_mapping_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _structured_packet_from_tool_result(mapping: Mapping[str, Any]) -> dict[str, Any]:
    for field in ("structuredContent", "structured_content"):
        candidate = _json_mapping_from_value(mapping.get(field))
        if candidate:
            return candidate
    result = _json_mapping_from_value(mapping.get("result"))
    for field in ("structuredContent", "structured_content"):
        candidate = _json_mapping_from_value(result.get(field))
        if candidate:
            return candidate
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            content_item = _json_mapping_from_value(item)
            candidate = _json_mapping_from_value(content_item.get("text"))
            if candidate:
                return candidate
    return {}


def _direct_mcp_tool_response_delivery_details(
    *,
    codex_exec_jsonl_text: str,
    entry_evidence_packet: Mapping[str, Any],
) -> dict[str, Any]:
    events = _jsonl_event_objects(codex_exec_jsonl_text)
    expected_delegate_sha256 = _hex_sha256(
        entry_evidence_packet.get("delegate_packet_sha256")
    )
    tool_result_index = -1
    tool_result_packet: dict[str, Any] = {}
    for index, event in enumerate(events):
        for mapping in _iter_mappings(event):
            item_type = _first_text_field(
                mapping,
                ("type", "kind", "item_type", "itemType"),
            ).casefold()
            tool_name = _first_text_field(
                mapping,
                ("tool_name", "toolName", "tool", "name"),
            )
            result_like_mapping = bool(
                "result" in item_type
                or isinstance(mapping.get("result"), (Mapping, str))
            )
            if "mcp" not in item_type or "tool" not in item_type or not result_like_mapping:
                continue
            if tool_name != "delegate_to_dip":
                continue
            candidate = _structured_packet_from_tool_result(mapping)
            if candidate:
                tool_result_index = index
                tool_result_packet = candidate
                break
        if tool_result_packet:
            break
    tool_result_sha256 = _packet_sha256(tool_result_packet) if tool_result_packet else ""
    tool_result_bound_to_entry = bool(
        tool_result_packet
        and expected_delegate_sha256
        and tool_result_sha256 == expected_delegate_sha256
    )
    tool_result_safe = bool(
        tool_result_packet.get("packet_kind") == "wbp_mcp_delegate_to_dip_reality"
        and tool_result_packet.get("status") == "ok"
        and tool_result_packet.get("delegate_to_dip_tool_called") is True
        and tool_result_packet.get("api_lane_called") is True
        and tool_result_packet.get("route_bound_dispatch_proven") is True
        and tool_result_packet.get("fallback_used") is False
        and tool_result_packet.get("local_imitation_used") is False
        and tool_result_packet.get("raw_backend_details_exposed") is False
        and tool_result_packet.get("secret_value_exposed") is False
    )
    assistant_after_result = False
    if tool_result_index >= 0:
        for event in events[tool_result_index + 1 :]:
            for mapping in _iter_mappings(event):
                item_type = _first_text_field(
                    mapping,
                    ("type", "kind", "item_type", "itemType"),
                ).casefold()
                role = _first_text_field(mapping, ("role", "author", "speaker")).casefold()
                text = _first_text_field(mapping, ("text", "message", "content"))
                if role == "assistant" or item_type in {"agent_message", "message"}:
                    if text or role == "assistant":
                        assistant_after_result = True
                        break
            if assistant_after_result:
                break
    return {
        "direct_mcp_tool_result_observed": bool(tool_result_packet),
        "direct_mcp_tool_result_sha256": tool_result_sha256,
        "direct_mcp_tool_result_bound_to_entry_evidence": tool_result_bound_to_entry,
        "direct_mcp_tool_result_safe": tool_result_safe,
        "assistant_response_after_direct_mcp_tool_result": assistant_after_result,
        "direct_mcp_tool_response_delivery_proven": bool(
            tool_result_bound_to_entry and tool_result_safe and assistant_after_result
        ),
    }


def _delegated_task_candidate_digests(prompt_text: object) -> list[str]:
    prompt = _safe_text(prompt_text)
    candidates: list[str] = []

    def add(candidate: str) -> None:
        normalized = " ".join(_safe_text(candidate).split())
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add(prompt)
    for separator in (":", "："):
        if separator in prompt:
            add(prompt.split(separator, 1)[1])
    return [_sha256_text(candidate) for candidate in candidates[:8]]


def _prompt_observation_packet(
    *,
    prompt_text: object,
    router_entry_packet: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_digests = _delegated_task_candidate_digests(prompt_text)
    intent_claim = {
        "intent_claim_sha256": _packet_sha256(
            {
                "packet_kind": router_entry_packet.get("packet_kind"),
                "prompt_digest": router_entry_packet.get("prompt_digest"),
                "alias_candidate": router_entry_packet.get("alias_candidate"),
                "slot_candidate": router_entry_packet.get("slot_candidate"),
                "lane_candidate": router_entry_packet.get("lane_candidate"),
                "route_id_allowed": router_entry_packet.get("route_id_allowed") is True,
                "natural_alias_command_detected": (
                    router_entry_packet.get("natural_alias_command_detected") is True
                ),
            }
        ),
        "alias": _safe_text(router_entry_packet.get("alias_candidate"), limit=80),
        "alias_from_runtime_context": (
            router_entry_packet.get("alias_bound") is True
            and router_entry_packet.get("alias_context_read") is True
        ),
        "natural_command_shape": "natural_alias_command",
        "binding_status": "runtime_context_alias_bound"
        if router_entry_packet.get("alias_bound") is True
        else "blocked",
        "delegated_task_sha256": candidate_digests[0] if candidate_digests else "",
        "delegated_task_candidate_sha256s": candidate_digests,
        "delegated_task_source": "natural_prompt_digest_candidates",
    }
    return build_prompt_observation_packet(
        _safe_text(prompt_text),
        source="custom_codex_user_prompt_submit",
        intent_claim=intent_claim,
    )


def _hook_prompt_digest_bound(
    hook_packet: Mapping[str, Any],
    router_entry_packet: Mapping[str, Any],
) -> bool:
    expected = _hex_sha256(router_entry_packet.get("prompt_digest"))
    if not expected:
        return False
    return bool(
        hook_packet.get("hook_prompt_digest_bound") is True
        and _hex_sha256(hook_packet.get("prompt_digest")) == expected
    )


def _any_true(field: str, *packets_: Mapping[str, Any]) -> bool:
    return any(packet.get(field) is True for packet in packets_ if isinstance(packet, Mapping))


def build_natural_free_chat_router_proof_packet(
    *,
    prompt_text: object,
    router_entry_packet: Mapping[str, Any],
    hook_proof_packet: Mapping[str, Any],
    codex_exec_jsonl_text: str,
    codex_exec_exit_code: int = 0,
    codex_exec_stderr_text: str = "",
    entry_evidence_packet: Mapping[str, Any] | None = None,
    handoff_working_flow_join_packet: Mapping[str, Any] | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    router_entry = dict(router_entry_packet)
    hook = dict(hook_proof_packet)
    entry = dict(entry_evidence_packet) if isinstance(entry_evidence_packet, Mapping) else {}
    handoff_join = (
        dict(handoff_working_flow_join_packet)
        if isinstance(handoff_working_flow_join_packet, Mapping)
        else {}
    )
    metadata = dict(source_metadata) if isinstance(source_metadata, Mapping) else {}
    prompt_packet = _prompt_observation_packet(
        prompt_text=prompt_text,
        router_entry_packet=router_entry,
    )
    codex_tool_call = build_codex_exec_tool_call_observation_packet(
        codex_exec_jsonl_text,
        prompt_packet=prompt_packet,
        exec_exit_code=codex_exec_exit_code,
        stderr_text=codex_exec_stderr_text,
    )
    direct_mcp_delivery = _direct_mcp_tool_response_delivery_details(
        codex_exec_jsonl_text=codex_exec_jsonl_text,
        entry_evidence_packet=entry,
    )
    explicit_tool_instruction = explicit_tool_instruction_used(_safe_text(prompt_text))
    natural_prompt_observed = bool(
        prompt_packet.get("prompt_digest_present") is True
        and router_entry.get("hook_entry_proven") is True
        and not explicit_tool_instruction
    )
    user_prompt_submit_hook_ran = bool(
        hook.get("status") == "ok"
        and hook.get("user_prompt_submit_hook_ran") is True
        and hook.get("hook_ledger_written") is True
        and _hook_prompt_digest_bound(hook, router_entry)
        and hook.get("hook_runtime_context_digest_bound") is True
        and hook.get("thread_or_turn_digest_bound") is True
    )
    alias_intent_recognized = bool(
        router_entry.get("natural_alias_command_detected") is True
        and router_entry.get("natural_api_alias_command_detected") is True
        and router_entry.get("alias_context_read") is True
        and router_entry.get("route_id_allowed") is True
        and router_entry.get("allowed_api_route_ids_enforced") is True
        and hook.get("natural_alias_command_detected") is True
        and hook.get("natural_api_alias_command_detected") is True
    )
    mcp_tool_call_attempted = (
        codex_tool_call.get("codex_delegate_to_dip_tool_call_attempted") is True
    )
    mcp_tool_call_observed = bool(
        codex_tool_call.get("delegate_to_dip_tool_call_completed") is True
        and codex_tool_call.get("prompt_to_mcp_call_bound") is True
        and codex_tool_call.get("local_codex_subagent_used_as_dip") is not True
    )
    api_lane_called = bool(
        entry.get("api_lane_called") is True
        or entry.get("route_bound_dispatch_proven") is True
        or handoff_join.get("api_lane_dispatch_admitted") is True
    )
    api_lane_proven = bool(
        api_lane_called
        and (
            entry.get("allowed_api_route_ids_enforced") is True
            or handoff_join.get("router_owned_dispatch_decision_bound") is True
        )
        and (
            entry.get("route_bound_dispatch_proven") is True
            or handoff_join.get("dispatch_admission_proven") is True
        )
    )
    approved_handoff_proven = bool(
        handoff_join.get("approved_handoff_source_used") is True
        or direct_mcp_delivery.get("direct_mcp_tool_result_bound_to_entry_evidence")
        is True
    )
    working_flow_delivery_proven = (
        handoff_join.get("codex_working_flow_delivery_proven") is True
        or direct_mcp_delivery.get("direct_mcp_tool_response_delivery_proven") is True
    )
    local_imitation_used = _any_true(
        "local_imitation_used",
        hook,
        entry,
        handoff_join,
        codex_tool_call,
    )
    fallback_used = _any_true("fallback_used", hook, entry, handoff_join, codex_tool_call)
    native_codex_subagent_used_as_dip = bool(
        _any_true(
            "native_codex_subagent_used_as_dip",
            hook,
            entry,
            handoff_join,
            codex_tool_call,
        )
        or _any_true(
            "codex_subagent_used_as_dip",
            hook,
            entry,
            handoff_join,
            codex_tool_call,
        )
        or _any_true(
            "local_codex_subagent_used_as_dip",
            hook,
            entry,
            handoff_join,
            codex_tool_call,
        )
    )
    secret_or_backend_exposed = bool(
        _any_true("secret_value_exposed", hook, entry, handoff_join, codex_tool_call)
        or _any_true(
            "raw_backend_details_exposed",
            hook,
            entry,
            handoff_join,
            codex_tool_call,
        )
    )
    positive_proof = bool(
        natural_prompt_observed
        and user_prompt_submit_hook_ran
        and alias_intent_recognized
        and mcp_tool_call_observed
        and api_lane_proven
        and approved_handoff_proven
        and working_flow_delivery_proven
        and not local_imitation_used
        and not fallback_used
        and not native_codex_subagent_used_as_dip
        and not secret_or_backend_exposed
    )
    blocking_reasons: list[str] = []
    if not natural_prompt_observed:
        blocking_reasons.append("natural_prompt_not_observed")
    if explicit_tool_instruction:
        blocking_reasons.append("explicit_tool_instruction_used")
    if not user_prompt_submit_hook_ran:
        blocking_reasons.append("user_prompt_submit_hook_not_proven")
    if not alias_intent_recognized:
        blocking_reasons.append("alias_intent_not_recognized")
    if not mcp_tool_call_attempted:
        blocking_reasons.append("native_model_did_not_call_wbp_tool")
    elif not mcp_tool_call_observed:
        blocking_reasons.append("mcp_tool_call_not_prompt_bound")
    if not api_lane_proven:
        blocking_reasons.append("api_lane_not_proven")
    if not approved_handoff_proven:
        blocking_reasons.append("approved_handoff_not_proven")
    if not working_flow_delivery_proven:
        blocking_reasons.append("codex_working_flow_delivery_not_proven")
    if local_imitation_used:
        blocking_reasons.append("local_imitation_used")
    if fallback_used:
        blocking_reasons.append("fallback_used")
    if native_codex_subagent_used_as_dip:
        blocking_reasons.append("native_codex_subagent_used_as_dip")
    if secret_or_backend_exposed:
        blocking_reasons.append("secret_or_backend_detail_exposed")

    negative_model_no_tool = bool(
        natural_prompt_observed
        and user_prompt_submit_hook_ran
        and alias_intent_recognized
        and not mcp_tool_call_attempted
        and not local_imitation_used
        and not fallback_used
        and not native_codex_subagent_used_as_dip
        and not secret_or_backend_exposed
    )
    if positive_proof:
        machine_error_code = "OK"
    elif not natural_prompt_observed:
        machine_error_code = NATURAL_PROMPT_NOT_OBSERVED
    elif not user_prompt_submit_hook_ran:
        machine_error_code = USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN
    elif not alias_intent_recognized:
        machine_error_code = ALIAS_INTENT_NOT_RECOGNIZED
    elif negative_model_no_tool:
        machine_error_code = NATIVE_MODEL_DID_NOT_CALL_WBP_TOOL
    elif mcp_tool_call_attempted and not mcp_tool_call_observed:
        machine_error_code = NATURAL_MCP_TOOL_CALL_NOT_BOUND
    elif local_imitation_used or fallback_used or native_codex_subagent_used_as_dip:
        machine_error_code = NATURAL_FREE_CHAT_LOCAL_IMPERSONATION_BLOCKED
    elif secret_or_backend_exposed:
        machine_error_code = NATURAL_FREE_CHAT_SECRET_EXPOSURE_BLOCKED
    elif not api_lane_proven:
        machine_error_code = NATURAL_FREE_CHAT_API_LANE_NOT_PROVEN
    elif not (approved_handoff_proven and working_flow_delivery_proven):
        machine_error_code = NATURAL_FREE_CHAT_HANDOFF_NOT_PROVEN
    else:
        machine_error_code = NATURAL_FREE_CHAT_ROUTER_NOT_PROVEN

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": NATURAL_FREE_CHAT_ROUTER_PROOF_PACKET_KIND,
        "natural_prompt_observed": natural_prompt_observed,
        "strict_natural_prompt": not explicit_tool_instruction,
        "explicit_tool_instruction_used": explicit_tool_instruction,
        "prompt_digest": _hex_sha256(router_entry.get("prompt_digest")),
        "prompt_digest_present": bool(_hex_sha256(router_entry.get("prompt_digest"))),
        "prompt_observation_sha256": _packet_sha256(prompt_packet),
        "delegated_task_candidate_digest_count": int(
            prompt_packet.get("delegated_task_candidate_digest_count") or 0
        ),
        "router_entry_proven": router_entry.get("status") == "ok",
        "router_entry_sha256": _packet_sha256(router_entry),
        "user_prompt_submit_hook_ran": user_prompt_submit_hook_ran,
        "hook_prompt_digest_bound": _hook_prompt_digest_bound(hook, router_entry),
        "hook_runtime_context_digest_bound": (
            hook.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": (
            hook.get("thread_or_turn_digest_bound") is True
        ),
        "hook_proof_sha256": _packet_sha256(hook) if hook else "",
        "alias_intent_recognized": alias_intent_recognized,
        "alias_context_read": (
            router_entry.get("alias_context_read") is True
            and hook.get("alias_context_read") is True
        ),
        "allowed_api_route_ids_enforced": (
            router_entry.get("allowed_api_route_ids_enforced") is True
            and hook.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": (
            router_entry.get("route_id_allowed") is True
            and hook.get("route_id_allowed") is True
        ),
        "natural_alias_command_detected": (
            router_entry.get("natural_alias_command_detected") is True
            and hook.get("natural_alias_command_detected") is True
        ),
        "natural_api_alias_command_detected": (
            router_entry.get("natural_api_alias_command_detected") is True
            and hook.get("natural_api_alias_command_detected") is True
        ),
        "mcp_tool_call_attempted": mcp_tool_call_attempted,
        "mcp_tool_call_observed": mcp_tool_call_observed,
        "delegate_to_dip_tool_call_completed": (
            codex_tool_call.get("delegate_to_dip_tool_call_completed") is True
        ),
        "prompt_to_mcp_call_bound": (
            codex_tool_call.get("prompt_to_mcp_call_bound") is True
        ),
        "codex_tool_call_observation_sha256": _packet_sha256(codex_tool_call),
        "api_lane_called": api_lane_called and api_lane_proven,
        "api_lane_proven": api_lane_proven,
        "entry_evidence_sha256": _packet_sha256(entry) if entry else "",
        "handoff_working_flow_join_sha256": (
            _packet_sha256(handoff_join) if handoff_join else ""
        ),
        "direct_mcp_tool_result_observed": (
            direct_mcp_delivery.get("direct_mcp_tool_result_observed") is True
        ),
        "direct_mcp_tool_result_sha256": _hex_sha256(
            direct_mcp_delivery.get("direct_mcp_tool_result_sha256")
        ),
        "direct_mcp_tool_result_bound_to_entry_evidence": (
            direct_mcp_delivery.get("direct_mcp_tool_result_bound_to_entry_evidence")
            is True
        ),
        "direct_mcp_tool_result_safe": (
            direct_mcp_delivery.get("direct_mcp_tool_result_safe") is True
        ),
        "assistant_response_after_direct_mcp_tool_result": (
            direct_mcp_delivery.get("assistant_response_after_direct_mcp_tool_result")
            is True
        ),
        "direct_mcp_tool_response_delivery_proven": (
            direct_mcp_delivery.get("direct_mcp_tool_response_delivery_proven") is True
        ),
        "approved_handoff_proven": approved_handoff_proven,
        "codex_working_flow_delivery_proven": working_flow_delivery_proven,
        "native_free_chat_router_proven": positive_proof,
        "natural_free_chat_router_proof_positive": positive_proof,
        "negative_model_no_tool_proof": negative_model_no_tool,
        "fallback_used": fallback_used,
        "local_imitation_used": local_imitation_used,
        "native_codex_subagent_used_as_dip": native_codex_subagent_used_as_dip,
        "codex_native_subagent_used_as_dip": native_codex_subagent_used_as_dip,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "does_not_prove_product_ready": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": not positive_proof,
        "intent_recognition_is_not_dispatch_proof": not positive_proof,
        "router_proven_is_not_product_ready": True,
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
        "blocking_reasons": [] if positive_proof else sorted(set(blocking_reasons)),
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=positive_proof,
        human_message=(
            "WBP proved natural Custom Codex free-chat routing through MCP/API/handoff."
            if positive_proof
            else "WBP did not prove natural Custom Codex free-chat routing."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if positive_proof else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=[_safe_text(prompt_text)],
        extra=extra,
    )


def run_natural_free_chat_router_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    hook_proof_file: str,
    codex_exec_jsonl_file: str,
    runtime_context_file: str | None = None,
    entry_evidence_file: str | None = None,
    handoff_working_flow_join_file: str | None = None,
    codex_exec_exit_code: int = 0,
    codex_exec_stderr_file: str | None = None,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    router_entry = build_router_hook_entry_packet(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
        context_file_metadata=context_metadata,
    )
    hook_packet, hook_metadata = _read_json_mapping_file(
        Path(hook_proof_file).expanduser(),
        prefix="hook_proof",
    )
    jsonl_text, jsonl_metadata = _read_text_file(
        Path(codex_exec_jsonl_file).expanduser(),
        prefix="codex_exec_jsonl",
    )
    stderr_text = ""
    stderr_metadata: dict[str, Any] = {}
    if codex_exec_stderr_file:
        stderr_text, stderr_metadata = _read_text_file(
            Path(codex_exec_stderr_file).expanduser(),
            prefix="codex_exec_stderr",
        )
    entry_packet: dict[str, Any] = {}
    entry_metadata: dict[str, Any] = {
        "entry_evidence_file_present": False,
        "entry_evidence_file_read": False,
        "entry_evidence_file_valid_json": False,
        "entry_evidence_file_mapping": False,
        "entry_evidence_file_sha256": "",
        "entry_evidence_file_path_recorded": False,
    }
    if entry_evidence_file:
        entry_packet, entry_metadata = _read_json_mapping_file(
            Path(entry_evidence_file).expanduser(),
            prefix="entry_evidence",
        )
    handoff_packet: dict[str, Any] = {}
    handoff_metadata: dict[str, Any] = {
        "handoff_working_flow_join_file_present": False,
        "handoff_working_flow_join_file_read": False,
        "handoff_working_flow_join_file_valid_json": False,
        "handoff_working_flow_join_file_mapping": False,
        "handoff_working_flow_join_file_sha256": "",
        "handoff_working_flow_join_file_path_recorded": False,
    }
    if handoff_working_flow_join_file:
        handoff_packet, handoff_metadata = _read_json_mapping_file(
            Path(handoff_working_flow_join_file).expanduser(),
            prefix="handoff_working_flow_join",
        )
    return build_natural_free_chat_router_proof_packet(
        prompt_text=prompt_text,
        router_entry_packet=router_entry,
        hook_proof_packet=hook_packet,
        codex_exec_jsonl_text=jsonl_text,
        codex_exec_exit_code=codex_exec_exit_code,
        codex_exec_stderr_text=stderr_text,
        entry_evidence_packet=entry_packet,
        handoff_working_flow_join_packet=handoff_packet,
        source_metadata={
            **context_metadata,
            **hook_metadata,
            **jsonl_metadata,
            **stderr_metadata,
            **entry_metadata,
            **handoff_metadata,
        },
    )
