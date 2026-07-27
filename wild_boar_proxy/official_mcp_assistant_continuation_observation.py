# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_exec_assistant_continuation_proof import (
    CODEX_EXEC_ASSISTANT_CONTINUATION_NOT_BOUND,
    CODEX_EXEC_ASSISTANT_CONTINUATION_OBSERVATION_INVALID,
    CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
    CODEX_EXEC_ASSISTANT_CONTINUATION_PAYLOAD_UNSAFE,
    build_codex_exec_assistant_continuation_proof_packet,
)
from .codex_transcript_delivery_observation import (
    CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
    _hex_sha256,
    _read_jsonl_events_file,
    _unsafe_flag_failures,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .official_mcp_transcript_tool_result_observation import (
    OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_PACKET_KIND = (
    "wbp_official_mcp_assistant_continuation_observation"
)

OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_OK = "OK"
OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_SOURCE_INVALID = (
    "WBP_OFFICIAL_MCP_ASSISTANT_CONTINUATION_SOURCE_INVALID"
)
OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_ASSISTANT_CONTINUATION_UNSAFE_SOURCE"
)
OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_INVALID = (
    "WBP_OFFICIAL_MCP_ASSISTANT_CONTINUATION_TRANSCRIPT_INVALID"
)
OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_UNSAFE = (
    "WBP_OFFICIAL_MCP_ASSISTANT_CONTINUATION_TRANSCRIPT_UNSAFE"
)
OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_NOT_BOUND = (
    "WBP_OFFICIAL_MCP_ASSISTANT_CONTINUATION_NOT_BOUND"
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _safe_reasons(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _source_required_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_PACKET_KIND:
        failures.append("official_transcript_observation_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("official_transcript_observation_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("official_transcript_observation_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("official_transcript_observation_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("official_transcript_observation_changed_files_not_empty")
    for field, reason in (
        ("handoff_source_proven", "handoff_source_not_proven"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("handoff_payload_digest_bound", "handoff_payload_digest_not_bound"),
        ("handoff_source_digest_bound", "handoff_source_digest_not_bound"),
        ("working_flow_source_bound", "working_flow_source_not_bound"),
        ("adapter_handoff_completed", "adapter_handoff_not_completed"),
        ("adapter_handoff_envelope_built", "adapter_handoff_envelope_not_built"),
        ("transcript_observation_valid", "transcript_observation_not_valid"),
        ("codex_exec_json_events_observed", "codex_exec_json_events_not_observed"),
        ("mcp_tool_result_observed", "mcp_tool_result_not_observed"),
        (
            "mcp_tool_result_structured_content_present",
            "mcp_tool_result_structured_content_missing",
        ),
        ("mcp_server_allowed", "mcp_server_not_allowed"),
        ("mcp_tool_allowed", "mcp_tool_not_allowed"),
        (
            "content_text_json_matches_structured_content",
            "content_text_not_bound_to_structured_content",
        ),
        ("structured_content_matches_handoff", "structured_content_not_bound_to_handoff"),
        ("transcript_tool_result_observed", "transcript_tool_result_not_observed"),
        ("codex_transcript_delivery_observed", "codex_transcript_delivery_not_observed"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("expected_handoff_payload_digest", "expected_handoff_payload_digest_missing"),
        ("structured_content_digest", "structured_content_digest_missing"),
        ("declared_handoff_payload_digest", "declared_handoff_payload_digest_missing"),
        ("observed_handoff_payload_digest", "observed_handoff_payload_digest_missing"),
        ("codex_exec_transcript_sha256", "codex_exec_transcript_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    if source.get("mcp_tool_result_is_error") is True:
        failures.append("mcp_tool_result_is_error")
    if source.get("assistant_continuation_proven") is not False:
        failures.append("assistant_continuation_must_not_be_preclaimed")
    if source.get("codex_exec_assistant_continuation_proven") is not False:
        failures.append("codex_exec_assistant_continuation_must_not_be_preclaimed")
    if source.get("does_not_prove_assistant_continuation") is not True:
        failures.append("source_must_state_assistant_continuation_not_proven")
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    expected_digest = _hex_sha256(source.get("expected_handoff_payload_digest"))
    observed_digest = _hex_sha256(source.get("observed_handoff_payload_digest"))
    declared_digest = _hex_sha256(source.get("declared_handoff_payload_digest"))
    for label, digest in (
        ("expected_handoff_payload_digest_mismatch", expected_digest),
        ("observed_handoff_payload_digest_mismatch", observed_digest),
        ("declared_handoff_payload_digest_mismatch", declared_digest),
    ):
        if handoff_digest and digest and handoff_digest != digest:
            failures.append(label)
    return sorted(set(failures))


def _source_unsafe_claim_failures(source: Mapping[str, Any]) -> list[str]:
    failures = set(_unsafe_flag_failures(source))
    for field, reason in (
        ("assistant_continuation_proven", "assistant_continuation_must_not_be_preclaimed"),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_must_not_be_preclaimed",
        ),
        (
            "native_free_chat_router_product_ready",
            "native_free_chat_router_product_ready_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_delivery_proven",
            "native_free_chat_router_delivery_must_not_be_claimed",
        ),
        ("state_written", "state_write_not_allowed"),
        ("evidence_written", "evidence_write_not_allowed"),
        ("file_mutation_attempted", "file_mutation_not_allowed"),
    ):
        if source.get(field) is True:
            failures.add(reason)
    return sorted(failures)


def _adapter_transcript_observation(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "effect": EFFECT_PROBE,
        "changed_files": [],
        "codex_transcript_delivery_observed": (
            source.get("codex_transcript_delivery_observed") is True
        ),
        "structured_content_matches_handoff": (
            source.get("structured_content_matches_handoff") is True
        ),
        "mcp_tool_result_observed": source.get("mcp_tool_result_observed") is True,
        "mcp_tool_result_structured_content_present": (
            source.get("mcp_tool_result_structured_content_present") is True
        ),
        "mcp_tool_result_is_error": source.get("mcp_tool_result_is_error") is True,
        "mcp_tool_result_server_allowed": source.get("mcp_server_allowed") is True,
        "mcp_tool_result_name_allowed": source.get("mcp_tool_allowed") is True,
        "mcp_tool_result_content_text_json_matches_structured_content": (
            source.get("content_text_json_matches_structured_content") is True
        ),
        "handoff_payload_digest": _hex_sha256(source.get("handoff_payload_digest")),
        "codex_exec_transcript_sha256": _hex_sha256(
            source.get("codex_exec_transcript_sha256")
        ),
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
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
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
    }


def _continuation_required_failures(packet: Mapping[str, Any]) -> list[str]:
    if not packet:
        return ["assistant_continuation_not_attempted"]
    failures: list[str] = []
    if packet.get("packet_kind") != CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND:
        failures.append("assistant_continuation_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("assistant_continuation_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("assistant_continuation_machine_error_not_ok")
    for field, reason in (
        ("transcript_observation_valid", "transcript_observation_not_valid"),
        ("transcript_delivery_observed", "transcript_delivery_not_observed"),
        ("mcp_tool_result_observed", "mcp_tool_result_not_observed"),
        (
            "mcp_tool_result_structured_content_present",
            "mcp_tool_result_structured_content_missing",
        ),
        ("structured_content_matches_handoff", "structured_content_not_bound_to_handoff"),
        ("same_codex_exec_jsonl_bound", "same_codex_exec_jsonl_not_bound"),
        ("matching_mcp_tool_result_observed", "matching_mcp_tool_result_not_observed"),
        ("assistant_response_observed", "assistant_response_not_observed"),
        (
            "assistant_response_after_tool_result",
            "assistant_response_after_tool_result_not_observed",
        ),
        ("assistant_machine_marker_observed", "assistant_machine_marker_not_observed"),
        (
            "assistant_response_bound_to_handoff_digest",
            "assistant_response_not_bound_to_handoff_digest",
        ),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_not_proven",
        ),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(packet.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_missing")
    if not _hex_sha256(packet.get("codex_exec_transcript_sha256")):
        failures.append("codex_exec_transcript_digest_missing")
    if packet.get("assistant_marker_digest_mismatch") is True:
        failures.append("assistant_marker_digest_mismatch")
    return sorted(set(failures))


def _continuation_unsafe_failures(packet: Mapping[str, Any]) -> list[str]:
    failures = set(_unsafe_flag_failures(packet))
    if packet.get("transcript_secret_value_present") is True:
        failures.add("secret_value_present_in_transcript")
    return sorted(failures)


def _machine_error_code(
    *,
    source_failures: Sequence[str],
    source_unsafe_failures: Sequence[str],
    continuation_failures: Sequence[str],
    continuation_unsafe_failures: Sequence[str],
    continuation_packet: Mapping[str, Any],
) -> str:
    if (
        not source_failures
        and not source_unsafe_failures
        and not continuation_failures
        and not continuation_unsafe_failures
        and continuation_packet.get("status") == "ok"
    ):
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_OK
    if source_unsafe_failures:
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_UNSAFE_SOURCE
    if source_failures:
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_SOURCE_INVALID
    if continuation_unsafe_failures:
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_UNSAFE
    if continuation_packet.get("machine_error_code") in {
        CODEX_EXEC_ASSISTANT_CONTINUATION_NOT_BOUND,
    }:
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_NOT_BOUND
    if continuation_packet.get("machine_error_code") in {
        CODEX_EXEC_ASSISTANT_CONTINUATION_PAYLOAD_UNSAFE,
    }:
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_UNSAFE
    if continuation_packet.get("machine_error_code") in {
        CODEX_EXEC_ASSISTANT_CONTINUATION_OBSERVATION_INVALID,
    }:
        return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_SOURCE_INVALID
    return OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_INVALID


def build_official_mcp_assistant_continuation_observation_packet(
    *,
    transcript_observation_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(transcript_observation_packet)
    events = [dict(event) for event in codex_exec_events or []]
    metadata = dict(file_metadata or {})

    source_failures = _source_required_failures(source)
    source_unsafe_failures = _source_unsafe_claim_failures(source)
    adapter_packet = _adapter_transcript_observation(source)

    continuation_packet: Mapping[str, Any] = {}
    if not source_failures and not source_unsafe_failures:
        continuation_packet = build_codex_exec_assistant_continuation_proof_packet(
            adapter_packet,
            events,
            file_metadata=metadata,
            secret_values=secret_values,
        )
    continuation_failures = _continuation_required_failures(continuation_packet)
    continuation_unsafe_failures = _continuation_unsafe_failures(continuation_packet)
    blocking_reasons = sorted(
        set(
            source_failures
            + source_unsafe_failures
            + continuation_failures
            + continuation_unsafe_failures
            + _safe_reasons(source.get("blocking_reasons"))
            + _safe_reasons(continuation_packet.get("blocking_reasons"))
        )
    )
    ok = bool(
        not blocking_reasons
        and continuation_packet.get("status") == "ok"
        and continuation_packet.get("codex_exec_assistant_continuation_proven") is True
    )
    machine_error_code = _machine_error_code(
        source_failures=source_failures,
        source_unsafe_failures=source_unsafe_failures,
        continuation_failures=continuation_failures,
        continuation_unsafe_failures=continuation_unsafe_failures,
        continuation_packet=continuation_packet,
    )
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_PACKET_KIND,
        "proof_scope": (
            "official_mcp_transcript_tool_result_to_assistant_continuation_observation"
        ),
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=96),
        "source_status": _safe_text(source.get("status"), limit=32),
        "source_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "source_valid": not source_failures,
        "source_failures": source_failures,
        "source_unsafe_claim_failures": source_unsafe_failures,
        "official_mcp_transcript_tool_result_observation_valid": (
            not source_failures and not source_unsafe_failures
        ),
        "transcript_tool_result_observed": bool(
            ok and source.get("transcript_tool_result_observed") is True
        ),
        "codex_transcript_delivery_observed": bool(
            ok and source.get("codex_transcript_delivery_observed") is True
        ),
        "mcp_tool_result_observed": bool(
            ok and source.get("mcp_tool_result_observed") is True
        ),
        "mcp_tool_result_structured_content_present": bool(
            ok and source.get("mcp_tool_result_structured_content_present") is True
        ),
        "structured_content_matches_handoff": bool(
            ok and source.get("structured_content_matches_handoff") is True
        ),
        "handoff_payload_digest": _hex_sha256(source.get("handoff_payload_digest"))
        if ok
        else "",
        "codex_exec_transcript_sha256": _hex_sha256(
            continuation_packet.get("codex_exec_transcript_sha256")
        )
        if ok
        else "",
        "adapter_transcript_observation_kind": _safe_text(
            adapter_packet.get("packet_kind"),
            limit=96,
        ),
        "continuation_packet_kind": _safe_text(
            continuation_packet.get("packet_kind"),
            limit=96,
        ),
        "continuation_status": _safe_text(
            continuation_packet.get("status"),
            limit=32,
        ),
        "continuation_machine_error_code": _safe_text(
            continuation_packet.get("machine_error_code"),
            limit=96,
        ),
        "continuation_valid": bool(
            ok
            and continuation_packet.get("packet_kind")
            == CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND
            and continuation_packet.get("status") == "ok"
            and continuation_packet.get("machine_error_code") == "OK"
        ),
        "continuation_failures": continuation_failures,
        "continuation_unsafe_failures": continuation_unsafe_failures,
        "same_codex_exec_jsonl_bound": bool(
            ok and continuation_packet.get("same_codex_exec_jsonl_bound") is True
        ),
        "matching_mcp_tool_result_observed": bool(
            ok and continuation_packet.get("matching_mcp_tool_result_observed") is True
        ),
        "assistant_continuation_observed": bool(
            ok and continuation_packet.get("assistant_response_observed") is True
        ),
        "assistant_response_after_tool_result": bool(
            ok and continuation_packet.get("assistant_response_after_tool_result") is True
        ),
        "assistant_machine_marker_observed": bool(
            ok and continuation_packet.get("assistant_machine_marker_observed") is True
        ),
        "assistant_marker_digest_mismatch": bool(
            continuation_packet.get("assistant_marker_digest_mismatch") is True
        ),
        "assistant_continuation_bound_to_tool_result": bool(
            ok
            and continuation_packet.get("assistant_response_bound_to_handoff_digest")
            is True
        ),
        "assistant_response_bound_to_handoff_digest": bool(
            ok
            and continuation_packet.get("assistant_response_bound_to_handoff_digest")
            is True
        ),
        "binding_method": _safe_text(
            continuation_packet.get("binding_method") if ok else "",
            limit=64,
        ),
        "assistant_binding_digest": _hex_sha256(
            continuation_packet.get("assistant_binding_digest")
        )
        if ok
        else "",
        "assistant_continuation_proven": ok,
        "codex_exec_assistant_continuation_proven": ok,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "does_not_prove_codex_working_flow_delivery": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
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
        "transcript_secret_value_present": bool(
            continuation_packet.get("transcript_secret_value_present") is True
        ),
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP observed official MCP assistant continuation after a digest-bound tool result."
            if ok
            else "WBP blocked official MCP assistant continuation before proof."
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


def run_official_mcp_assistant_continuation_observation_command(
    *,
    transcript_observation_file: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    source_packet, source_metadata = _read_json_mapping_file(
        Path(transcript_observation_file).expanduser(),
        prefix="official_transcript_observation",
    )
    events, jsonl_metadata = _read_jsonl_events_file(
        Path(codex_exec_jsonl_file).expanduser()
    )
    return build_official_mcp_assistant_continuation_observation_packet(
        transcript_observation_packet=source_packet,
        codex_exec_events=events,
        file_metadata={**source_metadata, **jsonl_metadata},
    )
