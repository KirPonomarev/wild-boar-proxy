# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .approved_handoff import (
    API_LANE_TRUTH_SOURCE_REQUIRED,
    DISPATCH_TRUTH_SOURCE_REQUIRED,
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    build_approved_handoff_packet,
    _canonical_json_digest,
    _safe_handoff_payload,
)
from .codex_transcript_delivery_observation import (
    CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
    OBSERVATION_PATH_CODEX_EXEC_JSON_MCP_TOOL_RESULT,
    build_codex_transcript_delivery_observation_packet,
)
from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import CONTROLLED_API_DISPATCH_PACKET_KIND
from .controlled_dispatch_handoff_proof import (
    CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
)
from .core import packets
from .observed_machine_handoff_delivery import (
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    build_observed_machine_handoff_delivery_packet,
)
from .official_mcp_handoff_source_proof import (
    OFFICIAL_MCP_HANDOFF_SOURCE_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_PACKET_KIND = (
    "wbp_official_mcp_transcript_tool_result_observation"
)

OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_OK = "OK"
OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_INVALID = (
    "WBP_OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_SOURCE_INVALID"
)
OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_DIGEST_MISMATCH = (
    "WBP_OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_SOURCE_DIGEST_MISMATCH"
)
OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_TRANSCRIPT_INVALID = (
    "WBP_OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_TRANSCRIPT_INVALID"
)
OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_UNSAFE_SOURCE"
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _safe_reasons(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


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
    except (OSError, UnicodeDecodeError):
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


def _source_required_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != OFFICIAL_MCP_HANDOFF_SOURCE_PACKET_KIND:
        failures.append("handoff_source_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("handoff_source_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("handoff_source_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("handoff_source_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("handoff_source_changed_files_not_empty")
    for field, reason in (
        ("dispatch_join_valid", "dispatch_join_not_valid"),
        ("official_natural_mcp_case_proven", "official_natural_mcp_case_not_proven"),
        ("dispatch_join_proven", "dispatch_join_not_proven"),
        ("dispatch_join_prompt_digest_bound", "dispatch_join_prompt_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_routes_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("api_lane_dispatch_admitted", "api_lane_dispatch_not_admitted"),
        ("api_lane_provider_called", "api_lane_provider_not_called"),
        ("provider_response_proven", "provider_response_not_proven"),
        (
            "controlled_provider_response_proven",
            "controlled_provider_response_not_proven",
        ),
        ("result_bound_to_dispatch", "result_not_bound_to_dispatch"),
        ("dispatch_attempted", "dispatch_not_attempted"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("real_ledger_bound_api_dispatch_proven", "real_dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("selected_api_route_id_present", "selected_api_route_id_missing"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("approved_handoff_surface_used", "approved_handoff_surface_not_used"),
        ("handoff_source_digest_bound", "handoff_source_digest_not_bound"),
        ("working_flow_source_bound", "working_flow_source_not_bound"),
        ("approved_working_flow_source_bound", "approved_working_flow_source_not_bound"),
        ("handoff_payload_prepared", "handoff_payload_not_prepared"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("prompt_digest", "prompt_digest_missing"),
        ("selected_api_route_id_sha256", "selected_api_route_digest_missing"),
        ("route_bound_request_sha256", "route_bound_request_digest_missing"),
        ("provider_response_digest", "provider_response_digest_missing"),
        (
            "controlled_provider_response_sha256",
            "controlled_provider_response_digest_missing",
        ),
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("expected_handoff_payload_digest", "expected_handoff_payload_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    provider_digest = _hex_sha256(source.get("provider_response_digest"))
    controlled_digest = _hex_sha256(source.get("controlled_provider_response_sha256"))
    if provider_digest and controlled_digest and provider_digest != controlled_digest:
        failures.append("provider_response_digest_mismatch")
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    expected_handoff_digest = _hex_sha256(source.get("expected_handoff_payload_digest"))
    if source.get("handoff_surface_kind") != HANDOFF_SURFACE_MCP_TOOL_RESPONSE:
        failures.append("handoff_surface_must_be_mcp_tool_response")
    return sorted(set(failures))


def _unsafe_source_claim_failures(source: Mapping[str, Any]) -> list[str]:
    checks = {
        "product_ready": "product_ready_must_not_be_claimed",
        "custom_codex_ui_visibility_proven": (
            "custom_codex_ui_visibility_must_not_be_claimed"
        ),
        "codex_working_flow_delivery_proven": (
            "codex_working_flow_delivery_must_not_be_claimed"
        ),
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "native_free_chat_router_product_ready": (
            "native_free_chat_router_product_ready_must_not_be_claimed"
        ),
        "native_free_chat_router_delivery_proven": (
            "native_free_chat_router_delivery_must_not_be_claimed"
        ),
        "handoff_file_written": "handoff_file_must_not_be_preclaimed",
        "handoff_delivered": "handoff_must_not_be_preclaimed",
        "delivery_observed": "delivery_must_not_be_preclaimed",
        "live_provider_proven": "live_provider_must_not_be_claimed",
        "live_provider_response_proven": "live_provider_response_must_not_be_claimed",
        "external_live_provider_response_proven": (
            "external_live_provider_response_must_not_be_claimed"
        ),
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "raw_jsonl_recorded": "raw_jsonl_recorded",
        "raw_prompt_recorded": "raw_prompt_recorded",
        "raw_task_recorded": "raw_task_recorded",
        "tool_call_arguments_recorded": "tool_call_arguments_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "raw_route_id_recorded": "raw_route_id_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "secrets_exposed": "secrets_exposed",
    }
    return sorted(
        {reason for field, reason in checks.items() if source.get(field) is True}
    )


def _normalized_controlled_dispatch(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "packet_kind": CONTROLLED_API_DISPATCH_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "dispatch_proven": source.get("dispatch_proven") is True,
        "dispatch_status": "proven",
        "hook_entry_proven": True,
        "route_bound_dispatch_proven": source.get("route_bound_dispatch_proven") is True,
        "provider_response_proven": source.get("provider_response_proven") is True,
        "controlled_provider_response_proven": (
            source.get("controlled_provider_response_proven") is True
        ),
        "allowed_api_route_ids_enforced": (
            source.get("allowed_api_route_ids_enforced") is True
        ),
        "selected_api_route_id_recorded": False,
        "selected_api_route_id_present": (
            source.get("selected_api_route_id_present") is True
        ),
        "route_bound_request_sent": True,
        "controlled_provider_response_digest_present": bool(
            _hex_sha256(source.get("controlled_provider_response_sha256"))
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            source.get("selected_api_route_id_sha256")
        ),
        "route_bound_request_sha256": _hex_sha256(
            source.get("route_bound_request_sha256")
        ),
        "provider_response_digest": _hex_sha256(source.get("provider_response_digest")),
        "controlled_provider_response_sha256": _hex_sha256(
            source.get("controlled_provider_response_sha256")
        ),
        "dispatch_truth_source": DISPATCH_TRUTH_SOURCE_REQUIRED,
        "api_lane_truth_source": API_LANE_TRUTH_SOURCE_REQUIRED,
        "prompt_digest": _hex_sha256(source.get("prompt_digest")),
        "selected_alias": _safe_text(source.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            source.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(source.get("selected_slot"), limit=64),
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "native_free_chat_router_proven": False,
        "command_origin_proven": False,
        "custom_codex_origin_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
    }


def _adapter_handoff_proof_packet(
    source: Mapping[str, Any],
) -> tuple[dict[str, Any], str, str]:
    normalized_dispatch = _normalized_controlled_dispatch(source)
    approved_packet = build_approved_handoff_packet(
        normalized_dispatch,
        handoff_surface_kind=HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    )
    handoff_payload = _safe_handoff_payload(
        normalized_dispatch,
        HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    )
    expected_handoff_digest = _canonical_json_digest(handoff_payload)
    source_handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    delivery_packet = build_observed_machine_handoff_delivery_packet(
        approved_packet,
        handoff_payload=handoff_payload,
        delivery_surface_kind=DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
        delivery_surface_observed=True,
    )
    adapter = {
        "schema_version": 1,
        "packet_kind": CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
        "status": "ok" if delivery_packet.get("status") == "ok" else "error",
        "machine_error_code": _safe_text(
            delivery_packet.get("machine_error_code") or "OK",
            limit=96,
        ),
        "effect": EFFECT_PROBE,
        "changed_files": [],
        "handoff_completed": delivery_packet.get("handoff_delivered") is True,
        "handoff_envelope_built": (
            delivery_packet.get("machine_response_envelope_observed") is True
        ),
        "machine_response_envelope_observed": (
            delivery_packet.get("machine_response_envelope_observed") is True
        ),
        "machine_response_structured_content_present": (
            delivery_packet.get("machine_response_structured_content_present") is True
        ),
        "handoff_surface_kind": HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        "handoff_payload_digest": source_handoff_digest,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
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
    return adapter, expected_handoff_digest, source_handoff_digest


def _machine_error_code(
    *,
    source_failures: Sequence[str],
    source_unsafe_failures: Sequence[str],
    source_digest_bound: bool,
    transcript_required_failures: Sequence[str],
    transcript_packet: Mapping[str, Any],
) -> str:
    if (
        not source_failures
        and not source_unsafe_failures
        and source_digest_bound
        and not transcript_required_failures
        and transcript_packet.get("status") == "ok"
    ):
        return OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_OK
    if source_unsafe_failures:
        return OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_UNSAFE_SOURCE
    if source_failures:
        return OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_INVALID
    if not source_digest_bound:
        return OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_DIGEST_MISMATCH
    if transcript_required_failures:
        return OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_TRANSCRIPT_INVALID
    if transcript_packet.get("machine_error_code"):
        return _safe_text(transcript_packet.get("machine_error_code"), limit=96)
    return OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_TRANSCRIPT_INVALID


def _transcript_required_failures(packet: Mapping[str, Any]) -> list[str]:
    if not packet:
        return ["transcript_observation_not_attempted"]
    failures: list[str] = []
    if packet.get("packet_kind") != CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND:
        failures.append("transcript_observation_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("transcript_observation_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("transcript_observation_machine_error_not_ok")
    for field, reason in (
        ("codex_transcript_delivery_observed", "codex_transcript_delivery_not_observed"),
        ("mcp_tool_result_observed", "mcp_tool_result_not_observed"),
        (
            "mcp_tool_result_structured_content_present",
            "mcp_tool_result_structured_content_missing",
        ),
        ("mcp_tool_result_server_allowed", "mcp_tool_result_server_not_allowed"),
        ("mcp_tool_result_name_allowed", "mcp_tool_result_name_not_allowed"),
        (
            "mcp_tool_result_content_text_present",
            "mcp_tool_result_content_text_missing",
        ),
        (
            "mcp_tool_result_content_text_json_mapping_present",
            "mcp_tool_result_content_text_json_mapping_missing",
        ),
        (
            "mcp_tool_result_content_text_json_matches_structured_content",
            "mcp_tool_result_content_text_not_bound",
        ),
        ("structured_content_matches_handoff", "structured_content_not_bound_to_handoff"),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    if packet.get("mcp_tool_result_is_error") is True:
        failures.append("mcp_tool_result_is_error")
    if not _hex_sha256(packet.get("structured_content_digest")):
        failures.append("structured_content_digest_missing")
    if not _hex_sha256(packet.get("codex_exec_transcript_sha256")):
        failures.append("codex_exec_transcript_digest_missing")
    return sorted(set(failures))


def build_official_mcp_transcript_tool_result_observation_packet(
    *,
    handoff_source_packet: Mapping[str, Any] | None,
    codex_exec_events: Sequence[Mapping[str, Any]] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(handoff_source_packet)
    metadata = dict(file_metadata or {})
    events = [dict(event) for event in codex_exec_events or []]
    source_failures = _source_required_failures(source)
    source_unsafe_failures = _unsafe_source_claim_failures(source)
    adapter_packet, expected_handoff_digest, source_handoff_digest = (
        _adapter_handoff_proof_packet(source)
    )
    source_digest_bound = bool(
        expected_handoff_digest
        and source_handoff_digest
        and expected_handoff_digest == source_handoff_digest
    )

    transcript_packet: Mapping[str, Any] = {}
    if not source_failures and not source_unsafe_failures and source_digest_bound:
        transcript_packet = build_codex_transcript_delivery_observation_packet(
            adapter_packet,
            events,
            file_metadata=metadata,
            secret_values=secret_values,
        )

    transcript_blocking_reasons = _safe_reasons(
        transcript_packet.get("blocking_reasons")
    )
    transcript_required_failures = _transcript_required_failures(transcript_packet)
    blocking_reasons = sorted(
        set(
            source_failures
            + source_unsafe_failures
            + ([] if source_digest_bound else ["handoff_source_digest_mismatch"])
            + transcript_required_failures
            + transcript_blocking_reasons
            + _safe_reasons(source.get("blocking_reasons"))
        )
    )
    ok = bool(
        not blocking_reasons
        and transcript_packet.get("status") == "ok"
        and transcript_packet.get("codex_transcript_delivery_observed") is True
        and transcript_packet.get("structured_content_matches_handoff") is True
        and not transcript_required_failures
    )
    machine_error_code = _machine_error_code(
        source_failures=source_failures,
        source_unsafe_failures=source_unsafe_failures,
        source_digest_bound=source_digest_bound,
        transcript_required_failures=transcript_required_failures,
        transcript_packet=transcript_packet,
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_PACKET_KIND,
        "proof_scope": (
            "official_handoff_source_to_codex_transcript_mcp_tool_result_observation"
        ),
        "handoff_source_packet_kind": _safe_text(source.get("packet_kind"), limit=96),
        "handoff_source_status": _safe_text(source.get("status"), limit=32),
        "handoff_source_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "handoff_source_valid": not source_failures,
        "handoff_source_failures": source_failures,
        "source_unsafe_claim_failures": source_unsafe_failures,
        "handoff_source_proven": bool(ok and source.get("status") == "ok"),
        "approved_handoff_ready": bool(
            ok and source.get("approved_handoff_ready") is True
        ),
        "approved_handoff_payload_sanitized": bool(
            ok and source.get("approved_handoff_payload_sanitized") is True
        ),
        "handoff_payload_digest": source_handoff_digest if ok else "",
        "expected_handoff_payload_digest": expected_handoff_digest if ok else "",
        "handoff_payload_digest_bound": bool(ok and source_digest_bound),
        "handoff_source_digest_bound": bool(ok and source_digest_bound),
        "working_flow_source_bound": bool(
            ok and source.get("working_flow_source_bound") is True
        ),
        "adapter_handoff_proof_kind": _safe_text(
            adapter_packet.get("packet_kind"),
            limit=80,
        ),
        "adapter_handoff_completed": bool(
            adapter_packet.get("handoff_completed") is True
        ),
        "adapter_handoff_envelope_built": bool(
            adapter_packet.get("handoff_envelope_built") is True
        ),
        "transcript_observation_packet_kind": _safe_text(
            transcript_packet.get("packet_kind"),
            limit=96,
        ),
        "transcript_observation_status": _safe_text(
            transcript_packet.get("status"),
            limit=32,
        ),
        "transcript_observation_machine_error_code": _safe_text(
            transcript_packet.get("machine_error_code"),
            limit=96,
        ),
        "transcript_observation_valid": bool(
            ok
            and transcript_packet.get("packet_kind")
            == CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND
            and transcript_packet.get("status") == "ok"
            and transcript_packet.get("machine_error_code") == "OK"
        ),
        "transcript_required_failures": transcript_required_failures,
        "observation_path": _safe_text(
            transcript_packet.get("observation_path")
            or OBSERVATION_PATH_CODEX_EXEC_JSON_MCP_TOOL_RESULT,
            limit=96,
        ),
        "codex_exec_json_events_observed": bool(
            transcript_packet.get("codex_exec_json_events_observed") is True
        ),
        "codex_exec_transcript_sha256": _hex_sha256(
            transcript_packet.get("codex_exec_transcript_sha256")
        )
        if ok
        else "",
        "mcp_tool_result_observed": bool(
            ok and transcript_packet.get("mcp_tool_result_observed") is True
        ),
        "mcp_tool_result_structured_content_present": bool(
            ok
            and transcript_packet.get("mcp_tool_result_structured_content_present")
            is True
        ),
        "mcp_tool_result_is_error": bool(
            transcript_packet.get("mcp_tool_result_is_error") is True
        ),
        "mcp_server_allowed": bool(
            ok and transcript_packet.get("mcp_tool_result_server_allowed") is True
        ),
        "mcp_tool_allowed": bool(
            ok and transcript_packet.get("mcp_tool_result_name_allowed") is True
        ),
        "content_text_json_matches_structured_content": bool(
            ok
            and transcript_packet.get(
                "mcp_tool_result_content_text_json_matches_structured_content"
            )
            is True
        ),
        "structured_content_digest": _hex_sha256(
            transcript_packet.get("structured_content_digest")
        )
        if ok
        else "",
        "declared_handoff_payload_digest": _hex_sha256(
            transcript_packet.get("declared_handoff_payload_digest")
        )
        if ok
        else "",
        "observed_handoff_payload_digest": _hex_sha256(
            transcript_packet.get("observed_handoff_payload_digest")
        )
        if ok
        else "",
        "structured_content_matches_handoff": bool(
            ok and transcript_packet.get("structured_content_matches_handoff") is True
        ),
        "transcript_tool_result_observed": ok,
        "codex_transcript_delivery_observed": bool(
            ok and transcript_packet.get("codex_transcript_delivery_observed") is True
        ),
        "assistant_continuation_proven": False,
        "codex_exec_assistant_continuation_proven": False,
        "codex_working_flow_delivery_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "does_not_prove_assistant_continuation": True,
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
            "WBP observed official handoff source as a digest-bound MCP tool result."
            if ok
            else "WBP blocked official handoff transcript observation before proof."
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


def run_official_mcp_transcript_tool_result_observation_command(
    *,
    handoff_source_file: str,
    codex_exec_jsonl_file: str,
) -> dict[str, Any]:
    handoff_source_packet, source_metadata = _read_json_mapping_file(
        Path(handoff_source_file).expanduser(),
        prefix="handoff_source",
    )
    events, jsonl_metadata = _read_jsonl_events_file(
        Path(codex_exec_jsonl_file).expanduser()
    )
    return build_official_mcp_transcript_tool_result_observation_packet(
        handoff_source_packet=handoff_source_packet,
        codex_exec_events=events,
        file_metadata={**source_metadata, **jsonl_metadata},
    )
