# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256, _unsafe_flag_failures
from .codex_working_flow_delivery_proof import CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND
from .command_effects import EFFECT_PROBE
from .core import packets
from .official_mcp_delivery_candidate_join import (
    OFFICIAL_MCP_DELIVERY_CANDIDATE_JOIN_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_PACKET_KIND = (
    "wbp_official_mcp_working_flow_delivery_join"
)

OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_OK = "OK"
OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_CANDIDATE_INVALID = (
    "WBP_OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_CANDIDATE_INVALID"
)
OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_WORKING_FLOW_INVALID = (
    "WBP_OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_WORKING_FLOW_INVALID"
)
OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_UNSAFE_SOURCE"
)
OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_NOT_BOUND = (
    "WBP_OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_NOT_BOUND"
)

WORKING_FLOW_JOIN_TRUTH_SOURCE = (
    "file_backed_official_delivery_candidate_plus_codex_working_flow_delivery"
)
WORKING_FLOW_JOIN_CLAIM_CEILING = "working_flow_delivery_only_no_custom_ui_no_product"


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


def _candidate_contract_failures(
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_delivery_candidate_file_read") is not True:
        failures.append("official_delivery_candidate_file_not_read")
    if metadata.get("official_delivery_candidate_file_valid_json") is not True:
        failures.append("official_delivery_candidate_file_json_not_valid")
    if metadata.get("official_delivery_candidate_file_mapping") is not True:
        failures.append("official_delivery_candidate_file_not_mapping")
    if candidate.get("packet_kind") != OFFICIAL_MCP_DELIVERY_CANDIDATE_JOIN_PACKET_KIND:
        failures.append("official_delivery_candidate_packet_kind_invalid")
    if candidate.get("status") != "ok":
        failures.append("official_delivery_candidate_packet_not_ok")
    if candidate.get("machine_error_code") != "OK":
        failures.append("official_delivery_candidate_machine_error_not_ok")
    if candidate.get("effect") != EFFECT_PROBE:
        failures.append("official_delivery_candidate_effect_not_probe")
    if candidate.get("changed_files") not in ([], ()):
        failures.append("official_delivery_candidate_changed_files_not_empty")
    for field, reason in (
        ("approved_exec_source_delivery_candidate", "approved_exec_source_delivery_candidate_not_true"),
        ("delivery_candidate_source_file_backed", "delivery_candidate_source_not_file_backed"),
        (
            "official_observation_lineage_file_backed",
            "official_observation_lineage_not_file_backed",
        ),
        (
            "official_observation_lineage_proven",
            "official_delivery_candidate_lineage_not_proven",
        ),
        (
            "official_approved_exec_source_observation_valid",
            "official_approved_exec_source_observation_not_valid",
        ),
        ("approved_codex_exec_source_observed", "approved_codex_exec_source_not_observed"),
        ("assistant_continuation_source_bound", "assistant_continuation_source_not_bound"),
        (
            "codex_exec_assistant_continuation_proven",
            "candidate_codex_exec_assistant_continuation_not_proven",
        ),
        ("transcript_tool_result_observed", "candidate_transcript_tool_result_not_observed"),
        ("assistant_continuation_observed", "candidate_assistant_continuation_not_observed"),
        ("approved_source_kind_allowed", "candidate_approved_source_kind_not_allowed"),
        ("approved_source_events_observed", "candidate_approved_source_events_not_observed"),
        (
            "approved_source_assistant_output_observed",
            "candidate_approved_source_assistant_output_not_observed",
        ),
        (
            "matching_mcp_tool_result_observed",
            "candidate_matching_mcp_tool_result_not_observed",
        ),
        (
            "approved_source_digest_bound_to_transcript",
            "candidate_approved_source_digest_not_bound_to_transcript",
        ),
        (
            "assistant_source_digest_bound_to_transcript",
            "candidate_assistant_source_digest_not_bound_to_transcript",
        ),
        (
            "approved_source_marker_bound_to_handoff_digest",
            "candidate_approved_source_marker_not_bound_to_handoff_digest",
        ),
    ):
        if candidate.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("source_failures", "candidate_source_failures_not_empty"),
        ("source_binding_failures", "candidate_source_binding_failures_not_empty"),
        ("source_unsafe_claim_failures", "candidate_source_unsafe_claim_failures_not_empty"),
        ("blocking_reasons", "candidate_blocking_reasons_not_empty"),
    ):
        if _sequence_nonempty(candidate.get(field)):
            failures.append(reason)
    return sorted(set(failures))


def _working_flow_contract_failures(
    working_flow: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("working_flow_delivery_proof_file_read") is not True:
        failures.append("working_flow_delivery_proof_file_not_read")
    if metadata.get("working_flow_delivery_proof_file_valid_json") is not True:
        failures.append("working_flow_delivery_proof_file_json_not_valid")
    if metadata.get("working_flow_delivery_proof_file_mapping") is not True:
        failures.append("working_flow_delivery_proof_file_not_mapping")
    if working_flow.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_delivery_packet_kind_invalid")
    if working_flow.get("status") != "ok":
        failures.append("working_flow_delivery_packet_not_ok")
    if working_flow.get("machine_error_code") != "OK":
        failures.append("working_flow_delivery_machine_error_not_ok")
    if working_flow.get("effect") != EFFECT_PROBE:
        failures.append("working_flow_delivery_effect_not_probe")
    if working_flow.get("changed_files") not in ([], ()):
        failures.append("working_flow_delivery_changed_files_not_empty")
    for field, reason in (
        ("codex_working_flow_delivery_proven", "codex_working_flow_delivery_not_proven"),
        ("approved_delivery_surface_proven", "approved_delivery_surface_not_proven"),
        ("live_provider_proven", "working_flow_live_provider_not_proven"),
        (
            "live_provider_response_proven",
            "working_flow_live_provider_response_not_proven",
        ),
        (
            "external_live_provider_response_proven",
            "working_flow_external_live_provider_response_not_proven",
        ),
        (
            "codex_exec_assistant_continuation_proven",
            "working_flow_codex_exec_assistant_continuation_not_proven",
        ),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
    ):
        if working_flow.get(field) is not True:
            failures.append(reason)
    if not (
        working_flow.get("assistant_response_bound_to_handoff_digest") is True
        or working_flow.get("command_assistant_response_bound_to_live_provider_digest")
        is True
    ):
        failures.append("working_flow_assistant_response_not_digest_bound")
    if not _hex_sha256(working_flow.get("live_provider_response_digest")):
        failures.append("working_flow_live_provider_response_digest_missing")
    for field, reason in (
        ("integrated_live_provider_proof_failures", "working_flow_integrated_failures_not_empty"),
        ("transcript_delivery_failures", "working_flow_transcript_failures_not_empty"),
        ("assistant_binding_failures", "working_flow_assistant_binding_failures_not_empty"),
        (
            "command_execution_delivery_failures",
            "working_flow_command_delivery_failures_not_empty",
        ),
        (
            "command_assistant_binding_failures",
            "working_flow_command_assistant_binding_failures_not_empty",
        ),
        ("blocking_reasons", "working_flow_blocking_reasons_not_empty"),
    ):
        if _sequence_nonempty(working_flow.get(field)):
            failures.append(reason)
    return sorted(set(failures))


def _binding_failures(
    candidate: Mapping[str, Any],
    working_flow: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    candidate_handoff_digest = _hex_sha256(candidate.get("handoff_payload_digest"))
    candidate_transcript_digest = _hex_sha256(candidate.get("codex_exec_transcript_sha256"))
    candidate_source_digest = _hex_sha256(candidate.get("approved_source_digest"))
    candidate_assistant_digest = _hex_sha256(
        candidate.get("assistant_continuation_source_digest")
    )
    candidate_marker_digest = _hex_sha256(candidate.get("approved_source_marker_digest"))
    working_flow_handoff_digest = _hex_sha256(working_flow.get("handoff_payload_digest"))
    working_flow_transcript_digest = _hex_sha256(
        working_flow.get("codex_exec_transcript_sha256")
    )
    for value, reason in (
        (candidate_handoff_digest, "candidate_handoff_payload_digest_missing"),
        (candidate_transcript_digest, "candidate_codex_exec_transcript_digest_missing"),
        (candidate_source_digest, "candidate_approved_source_digest_missing"),
        (
            candidate_assistant_digest,
            "candidate_assistant_continuation_source_digest_missing",
        ),
        (candidate_marker_digest, "candidate_approved_source_marker_digest_missing"),
        (working_flow_handoff_digest, "working_flow_handoff_payload_digest_missing"),
        (working_flow_transcript_digest, "working_flow_codex_exec_transcript_digest_missing"),
    ):
        if not value:
            failures.append(reason)
    if (
        candidate_transcript_digest
        and working_flow_transcript_digest
        and candidate_transcript_digest != working_flow_transcript_digest
    ):
        failures.append("candidate_transcript_not_bound_to_working_flow_transcript")
    if (
        candidate_source_digest
        and working_flow_transcript_digest
        and candidate_source_digest != working_flow_transcript_digest
    ):
        failures.append("candidate_approved_source_not_bound_to_working_flow_transcript")
    if (
        candidate_assistant_digest
        and working_flow_transcript_digest
        and candidate_assistant_digest != working_flow_transcript_digest
    ):
        failures.append("candidate_assistant_source_not_bound_to_working_flow_transcript")
    if (
        candidate_handoff_digest
        and working_flow_handoff_digest
        and candidate_handoff_digest != working_flow_handoff_digest
    ):
        failures.append("candidate_handoff_not_bound_to_working_flow_handoff")
    if (
        candidate_marker_digest
        and working_flow_handoff_digest
        and candidate_marker_digest != working_flow_handoff_digest
    ):
        failures.append("candidate_marker_not_bound_to_working_flow_handoff")
    return sorted(set(failures))


def _candidate_unsafe_claim_failures(
    candidate: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None,
) -> list[str]:
    failures = set(_unsafe_flag_failures(candidate))
    for field, reason in (
        (
            "codex_working_flow_delivery_proven",
            "candidate_codex_working_flow_delivery_must_not_be_preclaimed",
        ),
        (
            "working_flow_delivery_proven",
            "candidate_working_flow_delivery_must_not_be_preclaimed",
        ),
        (
            "delivery_counts_as_custom_codex_ui",
            "candidate_delivery_counts_as_custom_ui_must_not_be_claimed",
        ),
        (
            "custom_codex_ui_visibility_proven",
            "candidate_custom_codex_ui_visibility_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_proven",
            "candidate_native_free_chat_router_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_product_ready",
            "candidate_native_free_chat_router_product_ready_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_delivery_proven",
            "candidate_native_free_chat_router_delivery_must_not_be_claimed",
        ),
        ("product_ready", "candidate_product_ready_must_not_be_claimed"),
        ("fallback_used", "candidate_fallback_used"),
        ("local_imitation_used", "candidate_local_imitation_used"),
        (
            "native_codex_subagent_used_as_dip",
            "candidate_native_codex_subagent_used_as_dip",
        ),
        (
            "codex_native_subagent_used_as_dip",
            "candidate_native_codex_subagent_used_as_dip",
        ),
        ("state_written", "candidate_state_write_not_allowed"),
        ("evidence_written", "candidate_evidence_write_not_allowed"),
        ("file_mutation_attempted", "candidate_file_mutation_not_allowed"),
    ):
        if candidate.get(field) is True:
            failures.add(reason)
    if packets.command_packet_has_secret_leak(
        candidate,
        secret_values=list(secret_values or []),
    ):
        failures.add("candidate_packet_secret_leak")
    return sorted(failures)


def _working_flow_unsafe_claim_failures(
    working_flow: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None,
) -> list[str]:
    live_provider_claim_allowed = bool(
        working_flow.get("codex_working_flow_delivery_proven") is True
        and working_flow.get("approved_delivery_surface_proven") is True
        and working_flow.get("live_provider_proven") is True
        and working_flow.get("live_provider_response_proven") is True
        and working_flow.get("external_live_provider_response_proven") is True
        and _hex_sha256(working_flow.get("live_provider_response_digest"))
        and working_flow.get("does_not_prove_live_provider") is False
    )
    target_proof_reasons = {
        "codex_working_flow_delivery_must_not_be_claimed",
    }
    if live_provider_claim_allowed:
        target_proof_reasons.update(
            {
                "live_provider_must_not_be_claimed",
                "live_provider_response_must_not_be_claimed",
                "external_live_provider_response_must_not_be_claimed",
            }
        )
    failures = {
        reason
        for reason in _unsafe_flag_failures(working_flow)
        if reason not in target_proof_reasons
    }
    for field, reason in (
        (
            "delivery_counts_as_custom_codex_ui",
            "working_flow_delivery_counts_as_custom_ui_must_not_be_claimed",
        ),
        (
            "custom_codex_ui_visibility_proven",
            "working_flow_custom_codex_ui_visibility_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_proven",
            "working_flow_native_free_chat_router_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_product_ready",
            "working_flow_native_free_chat_router_product_ready_must_not_be_claimed",
        ),
        (
            "native_free_chat_router_delivery_proven",
            "working_flow_native_free_chat_router_delivery_must_not_be_claimed",
        ),
        ("product_ready", "working_flow_product_ready_must_not_be_claimed"),
        ("fallback_used", "working_flow_fallback_used"),
        ("local_imitation_used", "working_flow_local_imitation_used"),
        (
            "native_codex_subagent_used_as_dip",
            "working_flow_native_codex_subagent_used_as_dip",
        ),
        (
            "codex_native_subagent_used_as_dip",
            "working_flow_native_codex_subagent_used_as_dip",
        ),
        ("state_written", "working_flow_state_write_not_allowed"),
        ("evidence_written", "working_flow_evidence_write_not_allowed"),
        ("file_mutation_attempted", "working_flow_file_mutation_not_allowed"),
    ):
        if working_flow.get(field) is True:
            failures.add(reason)
    if packets.command_packet_has_secret_leak(
        working_flow,
        secret_values=list(secret_values or []),
    ):
        failures.add("working_flow_packet_secret_leak")
    return sorted(failures)


def _machine_error_code(
    *,
    candidate_failures: Sequence[str],
    working_flow_failures: Sequence[str],
    binding_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if (
        not candidate_failures
        and not working_flow_failures
        and not binding_failures
        and not unsafe_failures
    ):
        return OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_OK
    if unsafe_failures:
        return OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_UNSAFE_SOURCE
    if candidate_failures:
        return OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_CANDIDATE_INVALID
    if working_flow_failures:
        return OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_WORKING_FLOW_INVALID
    return OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_NOT_BOUND


def build_official_mcp_working_flow_delivery_join_packet(
    *,
    official_delivery_candidate_packet: Mapping[str, Any] | None,
    working_flow_delivery_proof_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidate = _mapping(official_delivery_candidate_packet)
    working_flow = _mapping(working_flow_delivery_proof_packet)
    metadata = dict(file_metadata or {})
    candidate_failures = _candidate_contract_failures(candidate, metadata)
    working_flow_failures = _working_flow_contract_failures(working_flow, metadata)
    binding_failures = _binding_failures(candidate, working_flow)
    unsafe_failures = sorted(
        set(
            _candidate_unsafe_claim_failures(candidate, secret_values=secret_values)
            + _working_flow_unsafe_claim_failures(
                working_flow,
                secret_values=secret_values,
            )
        )
    )
    blocking_reasons = sorted(
        set(
            candidate_failures
            + working_flow_failures
            + binding_failures
            + unsafe_failures
            + _safe_reasons(candidate.get("blocking_reasons"))
            + _safe_reasons(working_flow.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons

    candidate_handoff_digest = _hex_sha256(candidate.get("handoff_payload_digest"))
    candidate_transcript_digest = _hex_sha256(candidate.get("codex_exec_transcript_sha256"))
    candidate_source_digest = _hex_sha256(candidate.get("approved_source_digest"))
    candidate_assistant_digest = _hex_sha256(
        candidate.get("assistant_continuation_source_digest")
    )
    candidate_marker_digest = _hex_sha256(candidate.get("approved_source_marker_digest"))
    working_flow_handoff_digest = _hex_sha256(working_flow.get("handoff_payload_digest"))
    working_flow_transcript_digest = _hex_sha256(
        working_flow.get("codex_exec_transcript_sha256")
    )
    working_flow_source_prompt_digest = _hex_sha256(
        working_flow.get("source_prompt_digest")
    )
    working_flow_source_runtime_context_digest = _hex_sha256(
        working_flow.get("source_runtime_context_digest")
    )
    working_flow_source_hook_event_digest = _hex_sha256(
        working_flow.get("source_hook_event_digest")
    )
    working_flow_source_hook_thread_digest = _hex_sha256(
        working_flow.get("source_hook_thread_digest")
    )
    working_flow_source_hook_turn_digest = _hex_sha256(
        working_flow.get("source_hook_turn_digest")
    )
    working_flow_source_hook_session_digest = _hex_sha256(
        working_flow.get("source_hook_session_digest")
    )
    working_flow_selected_route_digest = _hex_sha256(
        working_flow.get("selected_api_route_id_sha256")
    )
    working_flow_route_bound_request_digest = _hex_sha256(
        working_flow.get("route_bound_request_sha256")
    )
    working_flow_live_provider_response_digest = _hex_sha256(
        working_flow.get("live_provider_response_digest")
    )
    working_flow_controlled_provider_response_digest = _hex_sha256(
        working_flow.get("controlled_provider_response_digest")
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_PACKET_KIND,
        "proof_scope": "official_delivery_candidate_to_canonical_working_flow_delivery",
        "working_flow_join_truth_source": WORKING_FLOW_JOIN_TRUTH_SOURCE if ok else "not_proven",
        "source_kind_claim_ceiling": WORKING_FLOW_JOIN_CLAIM_CEILING,
        "official_delivery_candidate_packet_kind": _safe_text(
            candidate.get("packet_kind"),
            limit=96,
        ),
        "official_delivery_candidate_status": _safe_text(candidate.get("status"), limit=32),
        "official_delivery_candidate_machine_error_code": _safe_text(
            candidate.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_delivery_packet_kind": _safe_text(
            working_flow.get("packet_kind"),
            limit=96,
        ),
        "working_flow_delivery_status": _safe_text(working_flow.get("status"), limit=32),
        "working_flow_delivery_machine_error_code": _safe_text(
            working_flow.get("machine_error_code"),
            limit=96,
        ),
        "official_delivery_candidate_valid": not candidate_failures,
        "canonical_working_flow_delivery_valid": not working_flow_failures,
        "candidate_bound_to_working_flow": bool(ok),
        "candidate_failures": candidate_failures,
        "working_flow_failures": working_flow_failures,
        "binding_failures": binding_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "approved_exec_source_delivery_candidate": bool(
            ok and candidate.get("approved_exec_source_delivery_candidate") is True
        ),
        "delivery_candidate_source_file_backed": bool(
            ok and candidate.get("delivery_candidate_source_file_backed") is True
        ),
        "official_observation_lineage_file_backed": bool(
            ok and candidate.get("official_observation_lineage_file_backed") is True
        ),
        "official_delivery_candidate_lineage_proven": bool(
            ok and candidate.get("official_observation_lineage_proven") is True
        ),
        "official_approved_exec_source_observation_valid": bool(
            ok and candidate.get("official_approved_exec_source_observation_valid") is True
        ),
        "approved_codex_exec_source_observed": bool(
            ok and candidate.get("approved_codex_exec_source_observed") is True
        ),
        "approved_delivery_surface_proven": bool(
            ok and working_flow.get("approved_delivery_surface_proven") is True
        ),
        "live_provider_proven": bool(
            ok and working_flow.get("live_provider_proven") is True
        ),
        "live_provider_response_proven": bool(
            ok and working_flow.get("live_provider_response_proven") is True
        ),
        "external_live_provider_response_proven": bool(
            ok and working_flow.get("external_live_provider_response_proven") is True
        ),
        "does_not_prove_live_provider": bool(
            not ok or working_flow.get("does_not_prove_live_provider") is not False
        ),
        "codex_exec_assistant_continuation_proven": bool(
            ok
            and candidate.get("codex_exec_assistant_continuation_proven") is True
            and working_flow.get("codex_exec_assistant_continuation_proven") is True
        ),
        "handoff_delivered": bool(ok and working_flow.get("handoff_delivered") is True),
        "delivery_observed": bool(ok and working_flow.get("delivery_observed") is True),
        "approved_handoff_ready": bool(
            ok and working_flow.get("approved_handoff_ready") is True
        ),
        "approved_handoff_payload_sanitized": bool(
            ok and working_flow.get("approved_handoff_payload_sanitized") is True
        ),
        "candidate_handoff_payload_digest": candidate_handoff_digest if ok else "",
        "candidate_codex_exec_transcript_sha256": (
            candidate_transcript_digest if ok else ""
        ),
        "candidate_approved_source_digest": candidate_source_digest if ok else "",
        "candidate_assistant_continuation_source_digest": (
            candidate_assistant_digest if ok else ""
        ),
        "candidate_approved_source_marker_digest": candidate_marker_digest if ok else "",
        "working_flow_handoff_payload_digest": working_flow_handoff_digest if ok else "",
        "working_flow_codex_exec_transcript_sha256": (
            working_flow_transcript_digest if ok else ""
        ),
        "working_flow_source_prompt_digest": (
            working_flow_source_prompt_digest if ok else ""
        ),
        "working_flow_source_runtime_context_digest": (
            working_flow_source_runtime_context_digest if ok else ""
        ),
        "working_flow_source_hook_event_digest": (
            working_flow_source_hook_event_digest if ok else ""
        ),
        "working_flow_source_hook_thread_digest": (
            working_flow_source_hook_thread_digest if ok else ""
        ),
        "working_flow_source_hook_turn_digest": (
            working_flow_source_hook_turn_digest if ok else ""
        ),
        "working_flow_source_hook_session_digest": (
            working_flow_source_hook_session_digest if ok else ""
        ),
        "working_flow_selected_api_route_id_sha256": (
            working_flow_selected_route_digest if ok else ""
        ),
        "working_flow_route_bound_request_sha256": (
            working_flow_route_bound_request_digest if ok else ""
        ),
        "working_flow_live_provider_response_digest": (
            working_flow_live_provider_response_digest if ok else ""
        ),
        "working_flow_controlled_provider_response_digest": (
            working_flow_controlled_provider_response_digest if ok else ""
        ),
        "working_flow_hook_producer_ledger_proven": bool(
            ok and working_flow.get("hook_producer_ledger_proven") is True
        ),
        "working_flow_user_prompt_submit_hook_ran": bool(
            ok and working_flow.get("user_prompt_submit_hook_ran") is True
        ),
        "working_flow_hook_ledger_written": bool(
            ok and working_flow.get("hook_ledger_written") is True
        ),
        "working_flow_hook_prompt_digest_bound": bool(
            ok and working_flow.get("hook_prompt_digest_bound") is True
        ),
        "working_flow_hook_runtime_context_digest_bound": bool(
            ok and working_flow.get("hook_runtime_context_digest_bound") is True
        ),
        "working_flow_thread_or_turn_digest_bound": bool(
            ok and working_flow.get("thread_or_turn_digest_bound") is True
        ),
        "handoff_payload_digest": working_flow_handoff_digest if ok else "",
        "codex_exec_transcript_sha256": working_flow_transcript_digest if ok else "",
        "candidate_transcript_bound_to_working_flow": bool(
            ok and candidate_transcript_digest == working_flow_transcript_digest
        ),
        "candidate_approved_source_bound_to_working_flow_transcript": bool(
            ok and candidate_source_digest == working_flow_transcript_digest
        ),
        "candidate_assistant_source_bound_to_working_flow_transcript": bool(
            ok and candidate_assistant_digest == working_flow_transcript_digest
        ),
        "candidate_handoff_bound_to_working_flow_handoff": bool(
            ok and candidate_handoff_digest == working_flow_handoff_digest
        ),
        "candidate_marker_bound_to_working_flow_handoff": bool(
            ok and candidate_marker_digest == working_flow_handoff_digest
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and working_flow.get("codex_working_flow_delivery_proven") is True
        ),
        "working_flow_delivery_proven": bool(
            ok and working_flow.get("codex_working_flow_delivery_proven") is True
        ),
        "official_mcp_delivery_candidate_joined_to_working_flow": bool(ok),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
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
            "WBP joined the official delivery candidate to canonical Codex working-flow delivery."
            if ok
            else "WBP blocked the official delivery candidate before working-flow delivery join."
        ),
        machine_error_code=_machine_error_code(
            candidate_failures=candidate_failures,
            working_flow_failures=working_flow_failures,
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


def run_official_mcp_working_flow_delivery_join_command(
    *,
    delivery_candidate_file: str,
    working_flow_delivery_proof_file: str,
) -> dict[str, Any]:
    candidate_packet, candidate_metadata = _read_json_mapping_file(
        Path(delivery_candidate_file).expanduser(),
        prefix="official_delivery_candidate",
    )
    working_flow_packet, working_flow_metadata = _read_json_mapping_file(
        Path(working_flow_delivery_proof_file).expanduser(),
        prefix="working_flow_delivery_proof",
    )
    return build_official_mcp_working_flow_delivery_join_packet(
        official_delivery_candidate_packet=candidate_packet,
        working_flow_delivery_proof_packet=working_flow_packet,
        file_metadata={**candidate_metadata, **working_flow_metadata},
    )
