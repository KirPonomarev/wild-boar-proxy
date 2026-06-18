# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256, _unsafe_flag_failures
from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_codex_approved_visible_source_observation import (
    VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
)
from .official_mcp_approved_codex_exec_source_observation import (
    OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_DELIVERY_CANDIDATE_JOIN_PACKET_KIND = (
    "wbp_official_mcp_delivery_candidate_join"
)

OFFICIAL_MCP_DELIVERY_CANDIDATE_OK = "OK"
OFFICIAL_MCP_DELIVERY_CANDIDATE_SOURCE_INVALID = (
    "WBP_OFFICIAL_MCP_DELIVERY_CANDIDATE_SOURCE_INVALID"
)
OFFICIAL_MCP_DELIVERY_CANDIDATE_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_DELIVERY_CANDIDATE_UNSAFE_SOURCE"
)
OFFICIAL_MCP_DELIVERY_CANDIDATE_NOT_BOUND = (
    "WBP_OFFICIAL_MCP_DELIVERY_CANDIDATE_NOT_BOUND"
)

DELIVERY_CANDIDATE_TRUTH_SOURCE = (
    "file_backed_official_approved_codex_exec_source_observation"
)
DELIVERY_CANDIDATE_CLAIM_CEILING = (
    "delivery_candidate_only_no_working_flow_no_custom_ui_no_product"
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


def _sequence_nonempty(value: object) -> bool:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(list(value))
    return bool(value)


def _safe_reasons(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _source_contract_failures(
    source: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_approved_exec_source_file_read") is not True:
        failures.append("official_approved_exec_source_file_not_read")
    if metadata.get("official_approved_exec_source_file_valid_json") is not True:
        failures.append("official_approved_exec_source_file_json_not_valid")
    if metadata.get("official_approved_exec_source_file_mapping") is not True:
        failures.append("official_approved_exec_source_file_not_mapping")
    if (
        source.get("packet_kind")
        != OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_PACKET_KIND
    ):
        failures.append("approved_exec_source_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("approved_exec_source_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("approved_exec_source_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("approved_exec_source_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("approved_exec_source_changed_files_not_empty")
    for field, reason in (
        ("source_valid", "approved_exec_source_source_not_valid"),
        (
            "official_assistant_continuation_observation_valid",
            "official_assistant_continuation_observation_not_valid",
        ),
        ("transcript_tool_result_observed", "transcript_tool_result_not_observed"),
        ("assistant_continuation_observed", "assistant_continuation_not_observed"),
        (
            "assistant_response_after_tool_result",
            "assistant_response_after_tool_result_not_observed",
        ),
        (
            "assistant_continuation_bound_to_tool_result",
            "assistant_continuation_not_bound_to_tool_result",
        ),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_not_proven",
        ),
        ("approved_source_kind_allowed", "approved_source_kind_not_allowed"),
        (
            "approved_codex_exec_source_observed",
            "approved_codex_exec_source_not_observed",
        ),
        ("approved_source_events_observed", "approved_source_events_not_observed"),
        ("approved_source_digest_bound", "approved_source_digest_not_bound"),
        (
            "approved_source_digest_matches_continuation",
            "approved_source_digest_not_bound_to_continuation",
        ),
        ("matching_mcp_tool_result_observed", "matching_mcp_tool_result_not_observed"),
        (
            "approved_source_assistant_output_observed",
            "approved_source_assistant_output_not_observed",
        ),
        ("approved_source_marker_observed", "approved_source_marker_not_observed"),
        (
            "approved_source_marker_bound_to_handoff_digest",
            "approved_source_marker_not_bound_to_handoff_digest",
        ),
        ("assistant_continuation_source_bound", "assistant_continuation_source_not_bound"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    if source.get("approved_source_kind") != VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT:
        failures.append("approved_source_kind_invalid")
    if source.get("approved_source_marker_digest_mismatch") is True:
        failures.append("approved_source_marker_digest_mismatch")
    for field, reason in (
        ("source_failures", "source_failures_not_empty"),
        ("source_unsafe_claim_failures", "source_unsafe_claim_failures_not_empty"),
        ("approved_source_failures", "approved_source_failures_not_empty"),
        ("approved_source_unsafe_failures", "approved_source_unsafe_failures_not_empty"),
        ("blocking_reasons", "approved_exec_source_blocking_reasons_not_empty"),
    ):
        if _sequence_nonempty(source.get(field)):
            failures.append(reason)
    return sorted(set(failures))


def _binding_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    transcript_digest = _hex_sha256(source.get("codex_exec_transcript_sha256"))
    approved_source_digest = _hex_sha256(source.get("approved_source_digest"))
    assistant_source_digest = _hex_sha256(
        source.get("assistant_continuation_source_digest")
    )
    marker_digest = _hex_sha256(source.get("approved_source_marker_digest"))
    for value, reason in (
        (handoff_digest, "handoff_payload_digest_missing"),
        (transcript_digest, "codex_exec_transcript_digest_missing"),
        (approved_source_digest, "approved_source_digest_missing"),
        (assistant_source_digest, "assistant_continuation_source_digest_missing"),
        (marker_digest, "approved_source_marker_digest_missing"),
    ):
        if not value:
            failures.append(reason)
    if transcript_digest and approved_source_digest and transcript_digest != approved_source_digest:
        failures.append("approved_source_digest_not_bound_to_transcript")
    if transcript_digest and assistant_source_digest and transcript_digest != assistant_source_digest:
        failures.append("assistant_source_digest_not_bound_to_transcript")
    if handoff_digest and marker_digest and handoff_digest != marker_digest:
        failures.append("approved_source_marker_not_bound_to_handoff_digest")
    return sorted(set(failures))


def _source_unsafe_claim_failures(
    source: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None,
) -> list[str]:
    failures = set(_unsafe_flag_failures(source))
    for field, reason in (
        (
            "codex_working_flow_delivery_proven",
            "codex_working_flow_delivery_must_not_be_preclaimed",
        ),
        (
            "delivery_counts_as_custom_codex_ui",
            "delivery_counts_as_custom_ui_must_not_be_claimed",
        ),
        (
            "custom_codex_ui_visibility_proven",
            "custom_codex_ui_visibility_must_not_be_claimed",
        ),
        ("native_free_chat_router_proven", "native_free_chat_router_must_not_be_claimed"),
        (
            "native_free_chat_router_product_ready",
            "native_free_chat_router_product_ready_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_delivery_proven",
            "native_free_chat_router_delivery_must_not_be_claimed",
        ),
        ("live_provider_proven", "live_provider_must_not_be_claimed"),
        ("live_provider_response_proven", "live_provider_response_must_not_be_claimed"),
        (
            "external_live_provider_response_proven",
            "external_live_provider_response_must_not_be_claimed",
        ),
        ("product_ready", "product_ready_must_not_be_claimed"),
        ("fallback_used", "fallback_used"),
        ("local_imitation_used", "local_imitation_used"),
        ("native_codex_subagent_used_as_dip", "native_codex_subagent_used_as_dip"),
        ("codex_native_subagent_used_as_dip", "native_codex_subagent_used_as_dip"),
        ("approved_source_secret_value_present", "secret_value_present_in_approved_source"),
        ("state_written", "state_write_not_allowed"),
        ("evidence_written", "evidence_write_not_allowed"),
        ("file_mutation_attempted", "file_mutation_not_allowed"),
    ):
        if source.get(field) is True:
            failures.add(reason)
    if packets.command_packet_has_secret_leak(
        source,
        secret_values=list(secret_values or []),
    ):
        failures.add("approved_exec_source_packet_secret_leak")
    return sorted(failures)


def _machine_error_code(
    *,
    source_failures: Sequence[str],
    binding_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if not source_failures and not binding_failures and not unsafe_failures:
        return OFFICIAL_MCP_DELIVERY_CANDIDATE_OK
    if unsafe_failures:
        return OFFICIAL_MCP_DELIVERY_CANDIDATE_UNSAFE_SOURCE
    if source_failures:
        return OFFICIAL_MCP_DELIVERY_CANDIDATE_SOURCE_INVALID
    return OFFICIAL_MCP_DELIVERY_CANDIDATE_NOT_BOUND


def build_official_mcp_delivery_candidate_join_packet(
    *,
    approved_exec_source_observation_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(approved_exec_source_observation_packet)
    metadata = dict(file_metadata or {})
    source_failures = _source_contract_failures(source, metadata)
    binding_failures = _binding_failures(source)
    unsafe_failures = _source_unsafe_claim_failures(
        source,
        secret_values=secret_values,
    )
    blocking_reasons = sorted(
        set(
            source_failures
            + binding_failures
            + unsafe_failures
            + _safe_reasons(source.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest")) if ok else ""
    transcript_digest = _hex_sha256(source.get("codex_exec_transcript_sha256"))
    approved_source_digest = _hex_sha256(source.get("approved_source_digest"))
    assistant_source_digest = _hex_sha256(
        source.get("assistant_continuation_source_digest")
    )
    marker_digest = _hex_sha256(source.get("approved_source_marker_digest"))

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_DELIVERY_CANDIDATE_JOIN_PACKET_KIND,
        "proof_scope": "official_approved_exec_source_to_delivery_candidate",
        "delivery_candidate_truth_source": DELIVERY_CANDIDATE_TRUTH_SOURCE,
        "source_kind_claim_ceiling": DELIVERY_CANDIDATE_CLAIM_CEILING,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=96),
        "source_status": _safe_text(source.get("status"), limit=32),
        "source_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "source_valid": not source_failures,
        "source_failures": source_failures,
        "source_binding_failures": binding_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "approved_exec_source_delivery_candidate": ok,
        "delivery_candidate_source_file_backed": metadata.get(
            "official_approved_exec_source_file_read"
        )
        is True,
        "official_approved_exec_source_observation_valid": not source_failures,
        "approved_codex_exec_source_observed": bool(
            ok and source.get("approved_codex_exec_source_observed") is True
        ),
        "assistant_continuation_source_bound": bool(
            ok and source.get("assistant_continuation_source_bound") is True
        ),
        "codex_exec_assistant_continuation_proven": bool(
            ok and source.get("codex_exec_assistant_continuation_proven") is True
        ),
        "transcript_tool_result_observed": bool(
            ok and source.get("transcript_tool_result_observed") is True
        ),
        "assistant_continuation_observed": bool(
            ok and source.get("assistant_continuation_observed") is True
        ),
        "approved_source_kind": _safe_text(source.get("approved_source_kind"), limit=80)
        if ok
        else "",
        "approved_source_kind_allowed": bool(
            ok and source.get("approved_source_kind_allowed") is True
        ),
        "approved_source_events_observed": bool(
            ok and source.get("approved_source_events_observed") is True
        ),
        "approved_source_assistant_output_observed": bool(
            ok and source.get("approved_source_assistant_output_observed") is True
        ),
        "matching_mcp_tool_result_observed": bool(
            ok and source.get("matching_mcp_tool_result_observed") is True
        ),
        "handoff_payload_digest": handoff_digest,
        "codex_exec_transcript_sha256": transcript_digest if ok else "",
        "approved_source_digest": approved_source_digest if ok else "",
        "assistant_continuation_source_digest": assistant_source_digest if ok else "",
        "approved_source_marker_digest": marker_digest if ok else "",
        "approved_source_digest_bound_to_transcript": bool(
            ok and transcript_digest and approved_source_digest == transcript_digest
        ),
        "assistant_source_digest_bound_to_transcript": bool(
            ok and transcript_digest and assistant_source_digest == transcript_digest
        ),
        "approved_source_marker_bound_to_handoff_digest": bool(
            ok and handoff_digest and marker_digest == handoff_digest
        ),
        "working_flow_delivery_candidate_only": True,
        "codex_working_flow_delivery_proven": False,
        "working_flow_delivery_proven": False,
        "custom_codex_ui_visibility_proven": False,
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
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP promoted the official approved exec source to a delivery candidate."
            if ok
            else "WBP blocked the official approved exec source before delivery candidate."
        ),
        machine_error_code=_machine_error_code(
            source_failures=source_failures,
            binding_failures=binding_failures,
            unsafe_failures=unsafe_failures,
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_official_mcp_delivery_candidate_join_command(
    *,
    approved_exec_source_observation_file: str,
) -> dict[str, Any]:
    source_packet, source_metadata = _read_json_mapping_file(
        Path(approved_exec_source_observation_file).expanduser(),
        prefix="official_approved_exec_source",
    )
    return build_official_mcp_delivery_candidate_join_packet(
        approved_exec_source_observation_packet=source_packet,
        file_metadata=source_metadata,
    )
