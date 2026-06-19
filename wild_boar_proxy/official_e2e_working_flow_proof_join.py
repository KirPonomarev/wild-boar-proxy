# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256
from .command_effects import EFFECT_PROBE
from .core import packets
from .official_mcp_working_flow_delivery_join import (
    OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_PACKET_KIND,
)
from .real_custom_codex_hook_proof import (
    HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN,
    REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND = (
    "wbp_official_e2e_working_flow_proof_join"
)

OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_OK = "OK"
OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_HOOK_INVALID = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_HOOK_INVALID"
)
OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_DELIVERY_INVALID = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_DELIVERY_INVALID"
)
OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_UNSAFE_SOURCE"
)
OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_NOT_BOUND = (
    "WBP_OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_NOT_BOUND"
)

E2E_WORKING_FLOW_TRUTH_SOURCE = (
    "file_backed_real_custom_hook_proof_plus_official_working_flow_delivery_join"
)
E2E_WORKING_FLOW_CLAIM_CEILING = (
    "custom_codex_hook_to_codex_working_flow_delivery_no_custom_ui_no_product"
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


def _real_hook_contract_failures(
    source: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("real_custom_hook_proof_file_read") is not True:
        failures.append("real_custom_hook_proof_file_not_read")
    if metadata.get("real_custom_hook_proof_file_valid_json") is not True:
        failures.append("real_custom_hook_proof_file_json_not_valid")
    if metadata.get("real_custom_hook_proof_file_mapping") is not True:
        failures.append("real_custom_hook_proof_file_not_mapping")
    if source.get("packet_kind") != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND:
        failures.append("real_custom_hook_proof_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("real_custom_hook_proof_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("real_custom_hook_proof_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("real_custom_hook_proof_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("real_custom_hook_proof_changed_files_not_empty")
    if _safe_text(source.get("hook_producer_state"), limit=80) != (
        HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN
    ):
        failures.append("hook_producer_state_not_custom_codex_proven")
    for field, reason in (
        ("hook_ledger_packet_valid", "hook_ledger_packet_not_valid"),
        ("hook_producer_ledger_proven", "hook_producer_ledger_not_proven"),
        ("hook_config_present", "hook_config_not_present"),
        ("hook_enabled", "hook_not_enabled"),
        ("hook_trusted", "hook_not_trusted"),
        ("hook_hash_current", "hook_hash_not_current"),
        ("hook_config_digest_bound", "hook_config_digest_not_bound"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_routes_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("provider_response_proven", "provider_response_not_proven"),
        ("controlled_provider_response_proven", "controlled_provider_response_not_proven"),
        ("selected_api_route_id_present", "selected_route_not_present"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("machine_response_envelope_observed", "machine_response_envelope_not_observed"),
        (
            "machine_response_structured_content_present",
            "machine_response_structured_content_not_present",
        ),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
        ("live_provider_requested", "live_provider_not_requested"),
        ("live_provider_attempted", "live_provider_not_attempted"),
        ("live_provider_cli_command_declared", "live_provider_cli_not_declared"),
        ("live_provider_cli_command_route_bound", "live_provider_cli_not_route_bound"),
        ("live_provider_route_bound_to_context", "live_provider_route_not_context_bound"),
        ("live_provider_network_dependent", "live_provider_not_network_dependent"),
        ("expected_text_observed", "expected_text_not_observed"),
        (
            "live_provider_response_bound_to_expected_text",
            "live_provider_response_not_expected_bound",
        ),
        ("live_provider_response_bound_to_route", "live_provider_response_not_route_bound"),
        ("live_provider_changed_files_empty", "live_provider_changed_files_not_empty"),
        ("live_provider_proven", "live_provider_not_proven"),
        ("live_provider_response_proven", "live_provider_response_not_proven"),
        (
            "external_live_provider_response_proven",
            "external_live_provider_response_not_proven",
        ),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    if _safe_text(source.get("dispatch_status"), limit=32) != "proven":
        failures.append("dispatch_status_not_proven")
    for field, reason in (
        ("hook_ledger_failures", "hook_ledger_failures_not_empty"),
        ("hook_ledger_unsafe_claim_failures", "hook_ledger_unsafe_claims_not_empty"),
        ("dispatch_failures", "dispatch_failures_not_empty"),
        ("handoff_failures", "handoff_failures_not_empty"),
        ("live_provider_failures", "live_provider_failures_not_empty"),
        ("blocking_reasons", "real_custom_hook_blocking_reasons_not_empty"),
    ):
        if _sequence_nonempty(source.get(field)):
            failures.append(reason)
    for field, reason in (
        ("prompt_digest", "prompt_digest_missing"),
        ("runtime_context_digest", "runtime_context_digest_missing"),
        ("hook_prompt_digest", "hook_prompt_digest_missing"),
        ("hook_runtime_context_digest", "hook_runtime_context_digest_missing"),
        ("selected_api_route_id_sha256", "selected_route_digest_missing"),
        ("route_bound_request_sha256", "route_bound_request_digest_missing"),
        ("provider_response_digest", "controlled_provider_response_digest_missing"),
        ("controlled_provider_response_sha256", "controlled_provider_response_sha_missing"),
        ("live_provider_response_digest", "live_provider_response_digest_missing"),
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("machine_response_envelope_sha256", "machine_response_envelope_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    if not (
        _hex_sha256(source.get("hook_thread_digest"))
        or _hex_sha256(source.get("hook_turn_digest"))
    ):
        failures.append("hook_thread_or_turn_digest_missing")
    if not _hex_sha256(source.get("hook_event_digest")):
        failures.append("hook_event_digest_missing")
    if not _hex_sha256(source.get("hook_session_digest")):
        failures.append("hook_session_digest_missing")
    return sorted(set(failures))


def _delivery_join_contract_failures(
    delivery: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_working_flow_delivery_join_file_read") is not True:
        failures.append("official_working_flow_delivery_join_file_not_read")
    if metadata.get("official_working_flow_delivery_join_file_valid_json") is not True:
        failures.append("official_working_flow_delivery_join_file_json_not_valid")
    if metadata.get("official_working_flow_delivery_join_file_mapping") is not True:
        failures.append("official_working_flow_delivery_join_file_not_mapping")
    if delivery.get("packet_kind") != OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_PACKET_KIND:
        failures.append("official_working_flow_delivery_join_packet_kind_invalid")
    if delivery.get("status") != "ok":
        failures.append("official_working_flow_delivery_join_packet_not_ok")
    if delivery.get("machine_error_code") != "OK":
        failures.append("official_working_flow_delivery_join_machine_error_not_ok")
    if delivery.get("effect") != EFFECT_PROBE:
        failures.append("official_working_flow_delivery_join_effect_not_probe")
    if delivery.get("changed_files") not in ([], ()):
        failures.append("official_working_flow_delivery_join_changed_files_not_empty")
    for field, reason in (
        ("official_delivery_candidate_valid", "official_delivery_candidate_not_valid"),
        ("canonical_working_flow_delivery_valid", "canonical_working_flow_delivery_not_valid"),
        ("candidate_bound_to_working_flow", "candidate_not_bound_to_working_flow"),
        ("approved_exec_source_delivery_candidate", "approved_exec_source_not_candidate"),
        ("delivery_candidate_source_file_backed", "delivery_candidate_source_not_file_backed"),
        (
            "official_approved_exec_source_observation_valid",
            "official_approved_exec_source_observation_not_valid",
        ),
        ("approved_codex_exec_source_observed", "approved_codex_exec_source_not_observed"),
        ("approved_delivery_surface_proven", "approved_delivery_surface_not_proven"),
        ("live_provider_proven", "working_flow_live_provider_not_proven"),
        ("live_provider_response_proven", "working_flow_live_provider_response_not_proven"),
        (
            "external_live_provider_response_proven",
            "working_flow_external_live_provider_response_not_proven",
        ),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_not_proven",
        ),
        ("handoff_delivered", "working_flow_handoff_not_delivered"),
        ("delivery_observed", "working_flow_delivery_not_observed"),
        ("approved_handoff_ready", "working_flow_approved_handoff_not_ready"),
        (
            "approved_handoff_payload_sanitized",
            "working_flow_approved_handoff_payload_not_sanitized",
        ),
        (
            "candidate_transcript_bound_to_working_flow",
            "candidate_transcript_not_bound_to_working_flow",
        ),
        (
            "candidate_approved_source_bound_to_working_flow_transcript",
            "candidate_approved_source_not_bound_to_working_flow",
        ),
        (
            "candidate_assistant_source_bound_to_working_flow_transcript",
            "candidate_assistant_source_not_bound_to_working_flow",
        ),
        (
            "candidate_handoff_bound_to_working_flow_handoff",
            "candidate_handoff_not_bound_to_working_flow",
        ),
        (
            "candidate_marker_bound_to_working_flow_handoff",
            "candidate_marker_not_bound_to_working_flow",
        ),
        ("codex_working_flow_delivery_proven", "codex_working_flow_delivery_not_proven"),
        ("working_flow_delivery_proven", "working_flow_delivery_not_proven"),
        (
            "official_mcp_delivery_candidate_joined_to_working_flow",
            "official_mcp_delivery_candidate_not_joined_to_working_flow",
        ),
        ("working_flow_hook_producer_ledger_proven", "working_flow_hook_ledger_not_proven"),
        ("working_flow_user_prompt_submit_hook_ran", "working_flow_user_prompt_hook_not_run"),
        ("working_flow_hook_ledger_written", "working_flow_hook_ledger_not_written"),
        (
            "working_flow_hook_prompt_digest_bound",
            "working_flow_hook_prompt_digest_not_bound",
        ),
        (
            "working_flow_hook_runtime_context_digest_bound",
            "working_flow_hook_runtime_context_digest_not_bound",
        ),
        (
            "working_flow_thread_or_turn_digest_bound",
            "working_flow_thread_or_turn_digest_not_bound",
        ),
    ):
        if delivery.get(field) is not True:
            failures.append(reason)
    if delivery.get("does_not_prove_live_provider") is not False:
        failures.append("working_flow_live_provider_claim_contradiction")
    for field, reason in (
        ("candidate_failures", "candidate_failures_not_empty"),
        ("working_flow_failures", "working_flow_failures_not_empty"),
        ("binding_failures", "delivery_binding_failures_not_empty"),
        ("source_unsafe_claim_failures", "delivery_source_unsafe_claims_not_empty"),
        ("blocking_reasons", "delivery_join_blocking_reasons_not_empty"),
    ):
        if _sequence_nonempty(delivery.get(field)):
            failures.append(reason)
    for field, reason in (
        ("candidate_handoff_payload_digest", "candidate_handoff_payload_digest_missing"),
        ("working_flow_handoff_payload_digest", "working_flow_handoff_payload_digest_missing"),
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("codex_exec_transcript_sha256", "codex_exec_transcript_digest_missing"),
        (
            "working_flow_codex_exec_transcript_sha256",
            "working_flow_transcript_digest_missing",
        ),
        ("working_flow_source_prompt_digest", "working_flow_source_prompt_digest_missing"),
        (
            "working_flow_source_runtime_context_digest",
            "working_flow_source_runtime_context_digest_missing",
        ),
        (
            "working_flow_source_hook_event_digest",
            "working_flow_source_hook_event_digest_missing",
        ),
        (
            "working_flow_source_hook_session_digest",
            "working_flow_source_hook_session_digest_missing",
        ),
        (
            "working_flow_selected_api_route_id_sha256",
            "working_flow_selected_route_digest_missing",
        ),
        (
            "working_flow_route_bound_request_sha256",
            "working_flow_route_bound_request_digest_missing",
        ),
        (
            "working_flow_live_provider_response_digest",
            "working_flow_live_provider_response_digest_missing",
        ),
        (
            "working_flow_controlled_provider_response_digest",
            "working_flow_controlled_provider_response_digest_missing",
        ),
    ):
        if not _hex_sha256(delivery.get(field)):
            failures.append(reason)
    if not (
        _hex_sha256(delivery.get("working_flow_source_hook_thread_digest"))
        or _hex_sha256(delivery.get("working_flow_source_hook_turn_digest"))
    ):
        failures.append("working_flow_source_hook_thread_or_turn_digest_missing")
    return sorted(set(failures))


def _source_unsafe_claim_failures(
    *,
    real_hook: Mapping[str, Any],
    delivery: Mapping[str, Any],
    secret_values: Sequence[str] | None,
) -> list[str]:
    failures: list[str] = []
    source_checks = {
        "custom_codex_ui_visibility_proven": "real_hook_custom_codex_ui_visibility_claimed",
        "codex_working_flow_delivery_proven": "real_hook_working_flow_preclaimed",
        "delivery_counts_as_custom_codex_ui": "real_hook_custom_ui_delivery_claimed",
        "native_free_chat_router_proven": "real_hook_native_router_claimed",
        "native_free_chat_router_product_ready": "real_hook_native_router_product_ready",
        "product_ready": "real_hook_product_ready",
        "fallback_used": "real_hook_fallback_used",
        "local_imitation_used": "real_hook_local_imitation_used",
        "native_codex_subagent_used_as_dip": "real_hook_native_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "real_hook_native_subagent_used_as_dip",
        "raw_prompt_recorded": "real_hook_raw_prompt_recorded",
        "prompt_text_recorded": "real_hook_prompt_text_recorded",
        "natural_phrase_recorded": "real_hook_natural_phrase_recorded",
        "raw_task_recorded": "real_hook_raw_task_recorded",
        "raw_jsonl_recorded": "real_hook_raw_jsonl_recorded",
        "tool_call_arguments_recorded": "real_hook_tool_arguments_recorded",
        "route_candidate_recorded": "real_hook_route_candidate_recorded",
        "raw_route_id_recorded": "real_hook_raw_route_id_recorded",
        "selected_api_route_id_recorded": "real_hook_selected_route_recorded",
        "raw_provider_response_recorded": "real_hook_raw_provider_response_recorded",
        "provider_response_text_recorded": "real_hook_provider_response_text_recorded",
        "provider_response_preview_recorded": "real_hook_provider_response_preview_recorded",
        "raw_backend_details_exposed": "real_hook_raw_backend_details_exposed",
        "secret_value_exposed": "real_hook_secret_value_exposed",
        "state_written": "real_hook_state_written",
        "evidence_written": "real_hook_evidence_written",
        "file_mutation_attempted": "real_hook_file_mutation_attempted",
    }
    delivery_checks = {
        "custom_codex_ui_visibility_proven": "delivery_custom_codex_ui_visibility_claimed",
        "delivery_counts_as_custom_codex_ui": "delivery_counts_as_custom_codex_ui",
        "native_free_chat_router_proven": "delivery_native_router_claimed",
        "native_free_chat_router_product_ready": "delivery_native_router_product_ready",
        "native_free_chat_router_delivery_proven": "delivery_native_router_delivery_claimed",
        "product_ready": "delivery_product_ready",
        "fallback_used": "delivery_fallback_used",
        "local_imitation_used": "delivery_local_imitation_used",
        "native_codex_subagent_used_as_dip": "delivery_native_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "delivery_native_subagent_used_as_dip",
        "raw_prompt_recorded": "delivery_raw_prompt_recorded",
        "prompt_text_recorded": "delivery_prompt_text_recorded",
        "natural_phrase_recorded": "delivery_natural_phrase_recorded",
        "raw_task_recorded": "delivery_raw_task_recorded",
        "raw_jsonl_recorded": "delivery_raw_jsonl_recorded",
        "tool_call_arguments_recorded": "delivery_tool_arguments_recorded",
        "route_candidate_recorded": "delivery_route_candidate_recorded",
        "raw_route_id_recorded": "delivery_raw_route_id_recorded",
        "selected_api_route_id_recorded": "delivery_selected_route_recorded",
        "raw_provider_response_recorded": "delivery_raw_provider_response_recorded",
        "provider_response_text_recorded": "delivery_provider_response_text_recorded",
        "provider_response_preview_recorded": "delivery_provider_response_preview_recorded",
        "raw_backend_details_exposed": "delivery_raw_backend_details_exposed",
        "secret_value_exposed": "delivery_secret_value_exposed",
        "state_written": "delivery_state_written",
        "evidence_written": "delivery_evidence_written",
        "file_mutation_attempted": "delivery_file_mutation_attempted",
    }
    failures.extend(
        reason for field, reason in source_checks.items() if real_hook.get(field) is True
    )
    failures.extend(
        reason for field, reason in delivery_checks.items() if delivery.get(field) is True
    )
    if packets.command_packet_has_secret_leak(real_hook, secret_values=secret_values):
        failures.append("real_hook_packet_secret_leak")
    if packets.command_packet_has_secret_leak(delivery, secret_values=secret_values):
        failures.append("delivery_join_packet_secret_leak")
    return sorted(set(failures))


def _digest_binding_failures(
    real_hook: Mapping[str, Any],
    delivery: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    bindings = (
        (
            "prompt_digest",
            "working_flow_source_prompt_digest",
            "prompt_digest_mismatch",
        ),
        (
            "runtime_context_digest",
            "working_flow_source_runtime_context_digest",
            "runtime_context_digest_mismatch",
        ),
        (
            "selected_api_route_id_sha256",
            "working_flow_selected_api_route_id_sha256",
            "selected_route_digest_mismatch",
        ),
        (
            "route_bound_request_sha256",
            "working_flow_route_bound_request_sha256",
            "route_bound_request_digest_mismatch",
        ),
        (
            "live_provider_response_digest",
            "working_flow_live_provider_response_digest",
            "live_provider_response_digest_mismatch",
        ),
        (
            "provider_response_digest",
            "working_flow_controlled_provider_response_digest",
            "controlled_provider_response_digest_mismatch",
        ),
        (
            "hook_event_digest",
            "working_flow_source_hook_event_digest",
            "hook_event_digest_mismatch",
        ),
        (
            "hook_session_digest",
            "working_flow_source_hook_session_digest",
            "hook_session_digest_mismatch",
        ),
    )
    for source_field, delivery_field, reason in bindings:
        source_digest = _hex_sha256(real_hook.get(source_field))
        delivery_digest = _hex_sha256(delivery.get(delivery_field))
        if not source_digest:
            failures.append(f"{source_field}_missing")
        elif not delivery_digest:
            failures.append(f"{delivery_field}_missing")
        elif source_digest != delivery_digest:
            failures.append(reason)
    hook_thread_digest = _hex_sha256(real_hook.get("hook_thread_digest"))
    hook_turn_digest = _hex_sha256(real_hook.get("hook_turn_digest"))
    working_flow_thread_digest = _hex_sha256(
        delivery.get("working_flow_source_hook_thread_digest")
    )
    working_flow_turn_digest = _hex_sha256(
        delivery.get("working_flow_source_hook_turn_digest")
    )
    thread_bound = bool(hook_thread_digest and hook_thread_digest == working_flow_thread_digest)
    turn_bound = bool(hook_turn_digest and hook_turn_digest == working_flow_turn_digest)
    if hook_thread_digest and working_flow_thread_digest and not thread_bound:
        failures.append("hook_thread_digest_mismatch")
    if hook_turn_digest and working_flow_turn_digest and not turn_bound:
        failures.append("hook_turn_digest_mismatch")
    if not (thread_bound or turn_bound):
        failures.append("hook_thread_or_turn_digest_mismatch")
    return sorted(set(failures))


def _machine_error_code(
    *,
    real_hook_failures: Sequence[str],
    delivery_join_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    binding_failures: Sequence[str],
) -> str:
    if real_hook_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_HOOK_INVALID
    if delivery_join_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_DELIVERY_INVALID
    if unsafe_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_UNSAFE_SOURCE
    if binding_failures:
        return OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_NOT_BOUND
    return OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_OK


def build_official_e2e_working_flow_proof_join_packet(
    *,
    real_custom_hook_proof_packet: Mapping[str, Any] | None,
    official_working_flow_delivery_join_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    real_hook = _mapping(real_custom_hook_proof_packet)
    delivery = _mapping(official_working_flow_delivery_join_packet)
    metadata = dict(file_metadata or {})
    real_hook_failures = _real_hook_contract_failures(real_hook, metadata)
    delivery_join_failures = _delivery_join_contract_failures(delivery, metadata)
    unsafe_failures = _source_unsafe_claim_failures(
        real_hook=real_hook,
        delivery=delivery,
        secret_values=secret_values,
    )
    binding_failures = _digest_binding_failures(real_hook, delivery)
    blocking_reasons = sorted(
        set(
            real_hook_failures
            + delivery_join_failures
            + unsafe_failures
            + binding_failures
            + _safe_reasons(real_hook.get("blocking_reasons"))
            + _safe_reasons(delivery.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons

    prompt_digest = _hex_sha256(real_hook.get("prompt_digest"))
    runtime_context_digest = _hex_sha256(real_hook.get("runtime_context_digest"))
    selected_route_digest = _hex_sha256(real_hook.get("selected_api_route_id_sha256"))
    route_bound_request_digest = _hex_sha256(
        real_hook.get("route_bound_request_sha256")
    )
    live_response_digest = _hex_sha256(real_hook.get("live_provider_response_digest"))
    controlled_response_digest = _hex_sha256(real_hook.get("provider_response_digest"))
    source_handoff_digest = _hex_sha256(real_hook.get("handoff_payload_digest"))
    working_flow_handoff_digest = _hex_sha256(
        delivery.get("working_flow_handoff_payload_digest")
    )
    transcript_digest = _hex_sha256(delivery.get("codex_exec_transcript_sha256"))
    hook_event_digest = _hex_sha256(real_hook.get("hook_event_digest"))
    hook_thread_digest = _hex_sha256(real_hook.get("hook_thread_digest"))
    hook_turn_digest = _hex_sha256(real_hook.get("hook_turn_digest"))
    hook_session_digest = _hex_sha256(real_hook.get("hook_session_digest"))

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND,
        "proof_scope": "real_custom_codex_hook_to_official_codex_working_flow_delivery",
        "e2e_working_flow_truth_source": E2E_WORKING_FLOW_TRUTH_SOURCE
        if ok
        else "not_proven",
        "source_kind_claim_ceiling": E2E_WORKING_FLOW_CLAIM_CEILING,
        "real_custom_hook_packet_kind": _safe_text(real_hook.get("packet_kind"), limit=96),
        "real_custom_hook_status": _safe_text(real_hook.get("status"), limit=32),
        "real_custom_hook_machine_error_code": _safe_text(
            real_hook.get("machine_error_code"),
            limit=96,
        ),
        "official_working_flow_delivery_join_packet_kind": _safe_text(
            delivery.get("packet_kind"),
            limit=96,
        ),
        "official_working_flow_delivery_join_status": _safe_text(
            delivery.get("status"),
            limit=32,
        ),
        "official_working_flow_delivery_join_machine_error_code": _safe_text(
            delivery.get("machine_error_code"),
            limit=96,
        ),
        "real_custom_hook_valid": not real_hook_failures,
        "official_working_flow_delivery_join_valid": not delivery_join_failures,
        "real_custom_hook_failures": real_hook_failures,
        "official_working_flow_delivery_join_failures": delivery_join_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "digest_binding_failures": binding_failures,
        "official_e2e_working_flow_proven": ok,
        "custom_codex_hook_to_official_working_flow_bound": ok,
        "custom_codex_flow_origin_proven": bool(
            ok and real_hook.get("hook_producer_state") == HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN
        ),
        "hook_producer_ledger_proven": bool(
            ok and real_hook.get("hook_producer_ledger_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and real_hook.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_ledger_written": bool(ok and real_hook.get("hook_ledger_written") is True),
        "hook_prompt_digest_bound": bool(
            ok and real_hook.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and real_hook.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": bool(
            ok and real_hook.get("thread_or_turn_digest_bound") is True
        ),
        "hook_event_digest": hook_event_digest if ok else "",
        "hook_thread_digest": hook_thread_digest if ok else "",
        "hook_turn_digest": hook_turn_digest if ok else "",
        "hook_session_digest": hook_session_digest if ok else "",
        "hook_event_digest_bound_to_working_flow": bool(
            ok
            and hook_event_digest
            == _hex_sha256(delivery.get("working_flow_source_hook_event_digest"))
        ),
        "hook_thread_or_turn_digest_bound_to_working_flow": bool(
            ok
            and (
                (
                    hook_thread_digest
                    and hook_thread_digest
                    == _hex_sha256(delivery.get("working_flow_source_hook_thread_digest"))
                )
                or (
                    hook_turn_digest
                    and hook_turn_digest
                    == _hex_sha256(delivery.get("working_flow_source_hook_turn_digest"))
                )
            )
        ),
        "hook_session_digest_bound_to_working_flow": bool(
            ok
            and hook_session_digest
            == _hex_sha256(delivery.get("working_flow_source_hook_session_digest"))
        ),
        "working_flow_hook_prompt_digest_bound": bool(
            ok and delivery.get("working_flow_hook_prompt_digest_bound") is True
        ),
        "working_flow_hook_runtime_context_digest_bound": bool(
            ok and delivery.get("working_flow_hook_runtime_context_digest_bound") is True
        ),
        "prompt_digest": prompt_digest if ok else "",
        "runtime_context_digest": runtime_context_digest if ok else "",
        "prompt_digest_bound_to_working_flow": bool(
            ok and prompt_digest == _hex_sha256(delivery.get("working_flow_source_prompt_digest"))
        ),
        "runtime_context_digest_bound_to_working_flow": bool(
            ok
            and runtime_context_digest
            == _hex_sha256(delivery.get("working_flow_source_runtime_context_digest"))
        ),
        "alias_context_read": bool(ok and real_hook.get("alias_context_read") is True),
        "allowed_api_route_ids_enforced": bool(
            ok and real_hook.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": bool(ok and real_hook.get("route_id_allowed") is True),
        "selected_api_route_id_sha256": selected_route_digest if ok else "",
        "route_bound_request_sha256": route_bound_request_digest if ok else "",
        "selected_route_bound_to_working_flow": bool(
            ok
            and selected_route_digest
            == _hex_sha256(delivery.get("working_flow_selected_api_route_id_sha256"))
        ),
        "route_bound_request_bound_to_working_flow": bool(
            ok
            and route_bound_request_digest
            == _hex_sha256(delivery.get("working_flow_route_bound_request_sha256"))
        ),
        "api_lane_called": bool(ok and real_hook.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and real_hook.get("dispatch_proven") is True),
        "route_bound_dispatch_proven": bool(
            ok and real_hook.get("route_bound_dispatch_proven") is True
        ),
        "provider_response_proven": bool(
            ok and real_hook.get("provider_response_proven") is True
        ),
        "live_provider_proven": bool(ok and delivery.get("live_provider_proven") is True),
        "live_provider_response_proven": bool(
            ok and delivery.get("live_provider_response_proven") is True
        ),
        "external_live_provider_response_proven": bool(
            ok and delivery.get("external_live_provider_response_proven") is True
        ),
        "live_provider_response_digest": live_response_digest if ok else "",
        "controlled_provider_response_digest": controlled_response_digest if ok else "",
        "live_provider_response_bound_to_working_flow": bool(
            ok
            and live_response_digest
            == _hex_sha256(delivery.get("working_flow_live_provider_response_digest"))
        ),
        "controlled_provider_response_bound_to_working_flow": bool(
            ok
            and controlled_response_digest
            == _hex_sha256(delivery.get("working_flow_controlled_provider_response_digest"))
        ),
        "approved_handoff_ready": bool(
            ok
            and real_hook.get("approved_handoff_ready") is True
            and delivery.get("approved_handoff_ready") is True
        ),
        "approved_handoff_payload_sanitized": bool(
            ok
            and real_hook.get("approved_handoff_payload_sanitized") is True
            and delivery.get("approved_handoff_payload_sanitized") is True
        ),
        "handoff_delivered": bool(
            ok
            and real_hook.get("handoff_delivered") is True
            and delivery.get("handoff_delivered") is True
        ),
        "delivery_observed": bool(
            ok
            and real_hook.get("delivery_observed") is True
            and delivery.get("delivery_observed") is True
        ),
        "source_handoff_payload_digest": source_handoff_digest if ok else "",
        "working_flow_handoff_payload_digest": working_flow_handoff_digest if ok else "",
        "handoff_payload_digest": working_flow_handoff_digest if ok else "",
        "handoff_payload_bound_to_working_flow": bool(
            ok and delivery.get("candidate_handoff_bound_to_working_flow_handoff") is True
        ),
        "codex_exec_transcript_sha256": transcript_digest if ok else "",
        "approved_exec_source_delivery_candidate": bool(
            ok and delivery.get("approved_exec_source_delivery_candidate") is True
        ),
        "approved_delivery_surface_proven": bool(
            ok and delivery.get("approved_delivery_surface_proven") is True
        ),
        "codex_exec_assistant_continuation_proven": bool(
            ok and delivery.get("codex_exec_assistant_continuation_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and delivery.get("codex_working_flow_delivery_proven") is True
        ),
        "official_mcp_delivery_candidate_joined_to_working_flow": bool(
            ok and delivery.get("official_mcp_delivery_candidate_joined_to_working_flow")
            is True
        ),
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
            "WBP joined real Custom Codex hook proof to official Codex working-flow delivery."
            if ok
            else "WBP blocked official E2E working-flow proof join."
        ),
        machine_error_code=_machine_error_code(
            real_hook_failures=real_hook_failures,
            delivery_join_failures=delivery_join_failures,
            unsafe_failures=unsafe_failures,
            binding_failures=binding_failures,
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_official_e2e_working_flow_proof_join_command(
    *,
    real_custom_hook_proof_file: str,
    official_working_flow_delivery_join_file: str,
) -> dict[str, Any]:
    real_hook_packet, real_hook_metadata = _read_json_mapping_file(
        Path(real_custom_hook_proof_file).expanduser(),
        prefix="real_custom_hook_proof",
    )
    delivery_packet, delivery_metadata = _read_json_mapping_file(
        Path(official_working_flow_delivery_join_file).expanduser(),
        prefix="official_working_flow_delivery_join",
    )
    return build_official_e2e_working_flow_proof_join_packet(
        real_custom_hook_proof_packet=real_hook_packet,
        official_working_flow_delivery_join_packet=delivery_packet,
        file_metadata={**real_hook_metadata, **delivery_metadata},
    )
