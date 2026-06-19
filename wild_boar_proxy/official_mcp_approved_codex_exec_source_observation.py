# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_exec_assistant_continuation_proof import (
    CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
)
from .codex_transcript_delivery_observation import (
    _hex_sha256,
    _read_jsonl_events_file,
    _unsafe_flag_failures,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_codex_approved_visible_source_observation import (
    APPROVED_VISIBLE_SOURCE_KINDS,
    CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_PACKET_KIND,
    VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    VISIBLE_SOURCE_OBSERVATION_NOT_BOUND,
    VISIBLE_SOURCE_OBSERVATION_PAYLOAD_UNSAFE,
    VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_ALLOWED,
    build_custom_codex_approved_visible_source_observation_packet,
)
from .official_mcp_assistant_continuation_observation import (
    OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_PACKET_KIND = (
    "wbp_official_mcp_approved_codex_exec_source_observation"
)

OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_OK = "OK"
OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_INVALID = (
    "WBP_OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_SOURCE_INVALID"
)
OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_UNSAFE_SOURCE"
)
OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_KIND_NOT_ALLOWED = (
    "WBP_OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_KIND_NOT_ALLOWED"
)
OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_INVALID = (
    "WBP_OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_INVALID"
)
OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_UNSAFE = (
    "WBP_OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_UNSAFE"
)
OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_NOT_BOUND = (
    "WBP_OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_NOT_BOUND"
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
    if source.get("packet_kind") != OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_PACKET_KIND:
        failures.append("official_assistant_continuation_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("official_assistant_continuation_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("official_assistant_continuation_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("official_assistant_continuation_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("official_assistant_continuation_changed_files_not_empty")
    for field, reason in (
        (
            "official_mcp_transcript_tool_result_observation_valid",
            "official_transcript_tool_result_observation_not_valid",
        ),
        ("transcript_tool_result_observed", "transcript_tool_result_not_observed"),
        ("codex_transcript_delivery_observed", "codex_transcript_delivery_not_observed"),
        ("mcp_tool_result_observed", "mcp_tool_result_not_observed"),
        (
            "mcp_tool_result_structured_content_present",
            "mcp_tool_result_structured_content_missing",
        ),
        ("structured_content_matches_handoff", "structured_content_not_bound_to_handoff"),
        ("continuation_valid", "assistant_continuation_not_valid"),
        ("same_codex_exec_jsonl_bound", "same_codex_exec_jsonl_not_bound"),
        ("matching_mcp_tool_result_observed", "matching_mcp_tool_result_not_observed"),
        ("assistant_continuation_observed", "assistant_continuation_not_observed"),
        (
            "assistant_response_after_tool_result",
            "assistant_response_after_tool_result_not_observed",
        ),
        ("assistant_machine_marker_observed", "assistant_machine_marker_not_observed"),
        (
            "assistant_continuation_bound_to_tool_result",
            "assistant_continuation_not_bound_to_tool_result",
        ),
        (
            "assistant_response_bound_to_handoff_digest",
            "assistant_response_not_bound_to_handoff_digest",
        ),
        ("assistant_continuation_proven", "assistant_continuation_not_proven"),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_not_proven",
        ),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("codex_exec_transcript_sha256", "codex_exec_transcript_digest_missing"),
        ("assistant_binding_digest", "assistant_binding_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    assistant_digest = _hex_sha256(source.get("assistant_binding_digest"))
    if handoff_digest and assistant_digest and handoff_digest != assistant_digest:
        failures.append("assistant_binding_digest_mismatch")
    if source.get("assistant_marker_digest_mismatch") is True:
        failures.append("assistant_marker_digest_mismatch")
    return sorted(set(failures))


def _file_backed_lineage_failures(
    metadata: Mapping[str, Any],
    exec_source_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_assistant_continuation_observation_file_read") is not True:
        failures.append("official_assistant_continuation_observation_file_not_read")
    if metadata.get("official_assistant_continuation_observation_file_valid_json") is not True:
        failures.append("official_assistant_continuation_observation_file_json_not_valid")
    if metadata.get("official_assistant_continuation_observation_file_mapping") is not True:
        failures.append("official_assistant_continuation_observation_file_not_mapping")
    if metadata.get("codex_exec_jsonl_file_read") is not True:
        failures.append("codex_exec_jsonl_file_not_read")
    if metadata.get("codex_exec_jsonl_file_valid_jsonl") is not True:
        failures.append("codex_exec_jsonl_file_jsonl_not_valid")
    if metadata.get("codex_exec_jsonl_parse_error_count") not in (0, None):
        failures.append("codex_exec_jsonl_file_jsonl_not_valid")
    if exec_source_packet.get("visible_source_read") is not True:
        failures.append("approved_exec_source_observation_not_file_backed")
    return sorted(set(failures))


def _source_unsafe_claim_failures(source: Mapping[str, Any]) -> list[str]:
    failures = set(_unsafe_flag_failures(source))
    for field, reason in (
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


def _adapter_assistant_continuation(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "effect": EFFECT_PROBE,
        "changed_files": [],
        "codex_exec_assistant_continuation_proven": (
            source.get("codex_exec_assistant_continuation_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": (
            source.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "assistant_response_after_tool_result": (
            source.get("assistant_response_after_tool_result") is True
        ),
        "same_codex_exec_jsonl_bound": source.get("same_codex_exec_jsonl_bound") is True,
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


def _exec_source_required_failures(packet: Mapping[str, Any]) -> list[str]:
    if not packet:
        return ["approved_codex_exec_source_not_attempted"]
    failures: list[str] = []
    if packet.get("packet_kind") != CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_PACKET_KIND:
        failures.append("approved_source_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("approved_source_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("approved_source_machine_error_not_ok")
    for field, reason in (
        ("assistant_continuation_proof_valid", "assistant_continuation_source_not_valid"),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_not_proven",
        ),
        (
            "assistant_response_bound_to_handoff_digest",
            "assistant_response_not_bound_to_handoff_digest",
        ),
        ("same_codex_exec_jsonl_bound", "same_codex_exec_jsonl_not_bound"),
        ("approved_visible_source_allowed", "approved_source_kind_not_allowed"),
        ("visible_source_events_observed", "approved_source_events_not_observed"),
        ("visible_source_digest_bound", "approved_source_digest_not_bound"),
        (
            "visible_source_digest_matches_continuation",
            "approved_source_digest_not_bound_to_continuation",
        ),
        ("matching_mcp_tool_result_observed", "matching_mcp_tool_result_not_observed"),
        (
            "visible_source_assistant_output_observed",
            "approved_source_assistant_output_not_observed",
        ),
        ("visible_source_marker_observed", "approved_source_marker_not_observed"),
        (
            "visible_source_marker_bound_to_handoff_digest",
            "approved_source_marker_not_bound_to_handoff_digest",
        ),
        (
            "custom_codex_approved_visible_source_observed",
            "approved_codex_exec_source_not_observed",
        ),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(packet.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_missing")
    if not _hex_sha256(packet.get("visible_source_digest")):
        failures.append("approved_source_digest_missing")
    if not _hex_sha256(packet.get("assistant_continuation_source_digest")):
        failures.append("assistant_continuation_source_digest_missing")
    if not _hex_sha256(packet.get("visible_source_marker_digest")):
        failures.append("approved_source_marker_digest_missing")
    handoff_digest = _hex_sha256(packet.get("handoff_payload_digest"))
    marker_digest = _hex_sha256(packet.get("visible_source_marker_digest"))
    if handoff_digest and marker_digest and handoff_digest != marker_digest:
        failures.append("visible_source_marker_digest_not_handoff_digest")
    if packet.get("visible_source_marker_digest_mismatch") is True:
        failures.append("visible_source_marker_digest_mismatch")
    return sorted(set(failures))


def _exec_source_unsafe_failures(packet: Mapping[str, Any]) -> list[str]:
    failures = set(_unsafe_flag_failures(packet))
    if packet.get("visible_source_secret_value_present") is True:
        failures.add("secret_value_present_in_approved_source")
    return sorted(failures)


def _machine_error_code(
    *,
    source_failures: Sequence[str],
    source_unsafe_failures: Sequence[str],
    exec_source_failures: Sequence[str],
    exec_source_unsafe_failures: Sequence[str],
    exec_source_packet: Mapping[str, Any],
) -> str:
    if (
        not source_failures
        and not source_unsafe_failures
        and not exec_source_failures
        and not exec_source_unsafe_failures
        and exec_source_packet.get("status") == "ok"
    ):
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_OK
    if source_unsafe_failures:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_UNSAFE_SOURCE
    if source_failures:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_INVALID
    if exec_source_unsafe_failures:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_UNSAFE
    if exec_source_packet.get("machine_error_code") == VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_ALLOWED:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_KIND_NOT_ALLOWED
    if exec_source_packet.get("machine_error_code") == VISIBLE_SOURCE_OBSERVATION_PAYLOAD_UNSAFE:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_UNSAFE
    if exec_source_packet.get("machine_error_code") == VISIBLE_SOURCE_OBSERVATION_NOT_BOUND:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_NOT_BOUND
    if exec_source_failures:
        return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_INVALID
    return OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_INVALID


def build_official_mcp_approved_codex_exec_source_observation_packet(
    *,
    assistant_continuation_observation_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    approved_source_kind: str = VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(assistant_continuation_observation_packet)
    events = [dict(event) for event in codex_exec_events or []]
    metadata = dict(file_metadata or {})
    source_kind = _safe_text(approved_source_kind, limit=80)

    source_contract_failures = _source_required_failures(source)
    source_unsafe_failures = _source_unsafe_claim_failures(source)
    adapter_packet = _adapter_assistant_continuation(source)

    exec_source_packet: Mapping[str, Any] = {}
    if not source_contract_failures and not source_unsafe_failures:
        exec_source_packet = build_custom_codex_approved_visible_source_observation_packet(
            adapter_packet,
            events,
            visible_source_kind=source_kind,
            file_metadata=metadata,
            secret_values=secret_values,
        )
    lineage_failures = _file_backed_lineage_failures(metadata, exec_source_packet)
    source_failures = sorted(set(source_contract_failures + lineage_failures))
    exec_source_failures = _exec_source_required_failures(exec_source_packet)
    exec_source_unsafe_failures = _exec_source_unsafe_failures(exec_source_packet)
    blocking_reasons = sorted(
        set(
            source_failures
            + source_unsafe_failures
            + exec_source_failures
            + exec_source_unsafe_failures
            + _safe_reasons(source.get("blocking_reasons"))
            + _safe_reasons(exec_source_packet.get("blocking_reasons"))
        )
    )
    ok = bool(
        not blocking_reasons
        and exec_source_packet.get("status") == "ok"
        and exec_source_packet.get("custom_codex_approved_visible_source_observed")
        is True
    )
    machine_error_code = _machine_error_code(
        source_failures=source_failures,
        source_unsafe_failures=source_unsafe_failures,
        exec_source_failures=exec_source_failures,
        exec_source_unsafe_failures=exec_source_unsafe_failures,
        exec_source_packet=exec_source_packet,
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_PACKET_KIND,
        "proof_scope": (
            "official_assistant_continuation_to_approved_codex_exec_source_observation"
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
        "official_observation_lineage_failures": lineage_failures,
        "official_assistant_continuation_observation_file_backed": bool(
            metadata.get("official_assistant_continuation_observation_file_read") is True
            and metadata.get("official_assistant_continuation_observation_file_valid_json")
            is True
            and metadata.get("official_assistant_continuation_observation_file_mapping")
            is True
        ),
        "official_codex_exec_jsonl_file_backed": bool(
            metadata.get("codex_exec_jsonl_file_read") is True
            and metadata.get("codex_exec_jsonl_file_valid_jsonl") is True
            and metadata.get("codex_exec_jsonl_parse_error_count") in (0, None)
        ),
        "official_observation_lineage_file_backed": not lineage_failures,
        "official_observation_lineage_proven": bool(ok and not lineage_failures),
        "official_assistant_continuation_observation_valid": (
            not source_failures and not source_unsafe_failures
        ),
        "transcript_tool_result_observed": bool(
            ok and source.get("transcript_tool_result_observed") is True
        ),
        "assistant_continuation_observed": bool(
            ok and source.get("assistant_continuation_observed") is True
        ),
        "assistant_response_after_tool_result": bool(
            ok and source.get("assistant_response_after_tool_result") is True
        ),
        "assistant_continuation_bound_to_tool_result": bool(
            ok and source.get("assistant_continuation_bound_to_tool_result") is True
        ),
        "codex_exec_assistant_continuation_proven": bool(
            ok and source.get("codex_exec_assistant_continuation_proven") is True
        ),
        "handoff_payload_digest": _hex_sha256(source.get("handoff_payload_digest"))
        if ok
        else "",
        "codex_exec_transcript_sha256": _hex_sha256(
            source.get("codex_exec_transcript_sha256")
        )
        if ok
        else "",
        "adapter_assistant_continuation_kind": _safe_text(
            adapter_packet.get("packet_kind"),
            limit=96,
        ),
        "underlying_visible_source_packet_kind": _safe_text(
            exec_source_packet.get("packet_kind"),
            limit=96,
        ),
        "underlying_visible_source_status": _safe_text(
            exec_source_packet.get("status"),
            limit=32,
        ),
        "underlying_visible_source_machine_error_code": _safe_text(
            exec_source_packet.get("machine_error_code"),
            limit=96,
        ),
        "approved_source_failures": exec_source_failures,
        "approved_source_unsafe_failures": exec_source_unsafe_failures,
        "approved_source_kind": source_kind,
        "approved_source_kind_allowed": source_kind in APPROVED_VISIBLE_SOURCE_KINDS,
        "approved_codex_exec_source_observed": bool(
            ok
            and exec_source_packet.get("custom_codex_approved_visible_source_observed")
            is True
        ),
        "approved_source_read": bool(
            exec_source_packet.get("visible_source_read") is True
        ),
        "approved_source_events_observed": bool(
            ok and exec_source_packet.get("visible_source_events_observed") is True
        ),
        "approved_source_digest": _hex_sha256(
            exec_source_packet.get("visible_source_digest")
        )
        if ok
        else "",
        "assistant_continuation_source_digest": _hex_sha256(
            exec_source_packet.get("assistant_continuation_source_digest")
        )
        if ok
        else "",
        "approved_source_digest_bound": bool(
            ok and exec_source_packet.get("visible_source_digest_bound") is True
        ),
        "approved_source_digest_matches_continuation": bool(
            ok
            and exec_source_packet.get("visible_source_digest_matches_continuation")
            is True
        ),
        "matching_mcp_tool_result_observed": bool(
            ok and exec_source_packet.get("matching_mcp_tool_result_observed") is True
        ),
        "approved_source_assistant_output_observed": bool(
            ok
            and exec_source_packet.get("visible_source_assistant_output_observed")
            is True
        ),
        "approved_source_marker_observed": bool(
            ok and exec_source_packet.get("visible_source_marker_observed") is True
        ),
        "approved_source_marker_digest_mismatch": bool(
            exec_source_packet.get("visible_source_marker_digest_mismatch") is True
        ),
        "approved_source_marker_digest": _hex_sha256(
            exec_source_packet.get("visible_source_marker_digest")
        )
        if ok
        else "",
        "approved_source_marker_binding_method": _safe_text(
            exec_source_packet.get("visible_source_marker_binding_method")
            if ok
            else "",
            limit=64,
        ),
        "approved_source_marker_bound_to_handoff_digest": bool(
            ok
            and exec_source_packet.get("visible_source_marker_bound_to_handoff_digest")
            is True
        ),
        "assistant_continuation_source_bound": bool(
            ok
            and exec_source_packet.get("visible_source_marker_bound_to_handoff_digest")
            is True
        ),
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
        "approved_source_secret_value_present": bool(
            exec_source_packet.get("visible_source_secret_value_present") is True
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
            "WBP observed the official continuation in an approved Codex exec source."
            if ok
            else "WBP blocked official approved Codex exec source before proof."
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


def run_official_mcp_approved_codex_exec_source_observation_command(
    *,
    assistant_continuation_observation_file: str,
    approved_source_kind: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    source_packet, source_metadata = _read_json_mapping_file(
        Path(assistant_continuation_observation_file).expanduser(),
        prefix="official_assistant_continuation_observation",
    )
    events, source_metadata_jsonl = _read_jsonl_events_file(
        Path(codex_exec_jsonl_file).expanduser()
    )
    return build_official_mcp_approved_codex_exec_source_observation_packet(
        assistant_continuation_observation_packet=source_packet,
        codex_exec_events=events,
        approved_source_kind=approved_source_kind,
        file_metadata={**source_metadata, **source_metadata_jsonl},
    )
