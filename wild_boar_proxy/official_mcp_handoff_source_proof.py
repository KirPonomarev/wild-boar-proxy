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
from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import CONTROLLED_API_DISPATCH_PACKET_KIND
from .core import packets
from .official_mcp_ledger_bound_dispatch_join import (
    OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_HANDOFF_SOURCE_PACKET_KIND = (
    "wbp_official_mcp_handoff_source_proof"
)

OFFICIAL_MCP_HANDOFF_SOURCE_OK = "OK"
OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID = (
    "WBP_OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID"
)
OFFICIAL_MCP_HANDOFF_SOURCE_HANDOFF_NOT_READY = (
    "WBP_OFFICIAL_MCP_HANDOFF_SOURCE_HANDOFF_NOT_READY"
)
OFFICIAL_MCP_HANDOFF_SOURCE_DIGEST_MISMATCH = (
    "WBP_OFFICIAL_MCP_HANDOFF_SOURCE_DIGEST_MISMATCH"
)
OFFICIAL_MCP_HANDOFF_SOURCE_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_HANDOFF_SOURCE_UNSAFE_SOURCE"
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


def _packet_file_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "dispatch_join_file_required": True,
        "dispatch_join_file_present": path.exists(),
        "dispatch_join_file_read": False,
        "dispatch_join_file_valid_json": False,
        "dispatch_join_file_mapping": False,
        "dispatch_join_file_error_code": "",
        "dispatch_join_file_path_recorded": False,
    }
    if not path.exists():
        metadata["dispatch_join_file_error_code"] = "dispatch_join_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["dispatch_join_file_error_code"] = "dispatch_join_file_invalid"
        return {}, metadata
    metadata["dispatch_join_file_read"] = True
    metadata["dispatch_join_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["dispatch_join_file_error_code"] = "dispatch_join_file_not_mapping"
        return {}, metadata
    metadata["dispatch_join_file_mapping"] = True
    return dict(parsed), metadata


def _dispatch_join_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_PACKET_KIND:
        failures.append("dispatch_join_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("dispatch_join_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("dispatch_join_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("dispatch_join_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("dispatch_join_changed_files_not_empty")
    for field, reason in (
        ("official_natural_mcp_case_proven", "official_natural_mcp_case_not_proven"),
        (
            "prompt_digest_bound_to_official_mcp_and_ledger_dispatch",
            "prompt_digest_not_bound",
        ),
        ("official_dispatch_alias_bound", "official_dispatch_alias_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_routes_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("real_user_prompt_submit_ledger_proven", "ledger_not_proven"),
        ("custom_codex_origin_proven", "custom_codex_origin_not_proven"),
        ("native_custom_codex_flow_proven", "native_custom_codex_flow_not_proven"),
        ("native_router_hook_observed", "native_router_hook_not_observed"),
        ("ledger_bound_dispatch_admitted", "ledger_bound_dispatch_not_admitted"),
        ("api_lane_called", "api_lane_not_called"),
        ("api_lane_dispatch_admitted", "api_lane_dispatch_not_admitted"),
        ("api_lane_provider_called", "api_lane_provider_not_called"),
        ("provider_response_proven", "provider_response_not_proven"),
        (
            "controlled_provider_response_proven",
            "controlled_provider_response_not_proven",
        ),
        ("response_digest_bound", "response_digest_not_bound"),
        ("response_bound_to_proof", "response_not_bound_to_proof"),
        ("dispatch_attempted", "dispatch_not_attempted"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("real_ledger_bound_api_dispatch_proven", "real_dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("route_bound_request_sent", "route_bound_request_not_sent"),
        ("selected_api_route_id_present", "selected_api_route_id_missing"),
        ("provider_like_response_only", "provider_like_response_only_not_declared"),
        ("forbidden_stale_route_ids_enforced", "stale_route_guard_missing"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    if int(source.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("stale_route_guard_missing")
    for field, reason in (
        ("prompt_digest", "prompt_digest_missing"),
        ("selected_api_route_id_sha256", "selected_api_route_digest_missing"),
        ("route_bound_request_sha256", "route_bound_request_digest_missing"),
        ("provider_response_digest", "provider_response_digest_missing"),
        (
            "controlled_provider_response_sha256",
            "controlled_provider_response_digest_missing",
        ),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    provider_digest = _hex_sha256(source.get("provider_response_digest"))
    controlled_digest = _hex_sha256(source.get("controlled_provider_response_sha256"))
    if provider_digest and controlled_digest and provider_digest != controlled_digest:
        failures.append("provider_response_digest_mismatch")
    if source.get("dispatch_truth_source") != DISPATCH_TRUTH_SOURCE_REQUIRED:
        failures.append("dispatch_truth_source_invalid")
    if source.get("api_lane_truth_source") != API_LANE_TRUTH_SOURCE_REQUIRED:
        failures.append("api_lane_truth_source_invalid")
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
        "hook_entry_proven": source.get("native_router_hook_observed") is True,
        "route_bound_dispatch_proven": (
            source.get("route_bound_dispatch_proven") is True
        ),
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
        "route_bound_request_sent": source.get("route_bound_request_sent") is True,
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
        "dispatch_truth_source": _safe_text(
            source.get("dispatch_truth_source"),
            limit=80,
        ),
        "api_lane_truth_source": _safe_text(
            source.get("api_lane_truth_source"),
            limit=80,
        ),
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


def _machine_error_code(
    *,
    dispatch_join_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    approved_handoff_failures: Sequence[str],
    handoff_source_digest_bound: bool,
) -> str:
    if not (
        dispatch_join_failures
        or unsafe_failures
        or approved_handoff_failures
        or not handoff_source_digest_bound
    ):
        return OFFICIAL_MCP_HANDOFF_SOURCE_OK
    if unsafe_failures:
        return OFFICIAL_MCP_HANDOFF_SOURCE_UNSAFE_SOURCE
    if dispatch_join_failures:
        return OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID
    if not handoff_source_digest_bound:
        return OFFICIAL_MCP_HANDOFF_SOURCE_DIGEST_MISMATCH
    return OFFICIAL_MCP_HANDOFF_SOURCE_HANDOFF_NOT_READY


def build_official_mcp_handoff_source_proof_packet(
    *,
    dispatch_join_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(dispatch_join_packet)
    metadata = dict(file_metadata or {})
    dispatch_failures = _dispatch_join_failures(source)
    unsafe_failures = _unsafe_source_claim_failures(source)
    normalized_dispatch = _normalized_controlled_dispatch(source)

    approved_packet: Mapping[str, Any] = {}
    handoff_payload: Mapping[str, Any] = {}
    expected_handoff_digest = ""
    approved_handoff_digest = ""
    if not dispatch_failures and not unsafe_failures:
        approved_packet = build_approved_handoff_packet(
            normalized_dispatch,
            handoff_surface_kind=HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
            secret_values=secret_values,
        )
        handoff_payload = _safe_handoff_payload(
            normalized_dispatch,
            HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        )
        expected_handoff_digest = _canonical_json_digest(handoff_payload)
        approved_handoff_digest = _hex_sha256(
            approved_packet.get("handoff_payload_sha256")
        )

    approved_failures = _safe_reasons(approved_packet.get("blocking_reasons"))
    handoff_source_digest_bound = bool(
        expected_handoff_digest
        and approved_handoff_digest
        and expected_handoff_digest == approved_handoff_digest
    )
    blocking_reasons = sorted(
        set(
            dispatch_failures
            + unsafe_failures
            + approved_failures
            + (
                []
                if handoff_source_digest_bound or dispatch_failures or unsafe_failures
                else ["handoff_source_digest_mismatch"]
            )
            + _safe_reasons(source.get("blocking_reasons"))
        )
    )
    ok = bool(
        not blocking_reasons
        and approved_packet.get("status") == "ok"
        and approved_packet.get("handoff_ready") is True
        and approved_packet.get("handoff_payload_sanitized") is True
        and handoff_source_digest_bound
    )
    machine_error_code = _machine_error_code(
        dispatch_join_failures=dispatch_failures,
        unsafe_failures=unsafe_failures,
        approved_handoff_failures=approved_failures,
        handoff_source_digest_bound=handoff_source_digest_bound,
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_HANDOFF_SOURCE_PACKET_KIND,
        "proof_scope": "official_mcp_dispatch_join_to_approved_handoff_source",
        "dispatch_join_packet_kind": _safe_text(source.get("packet_kind"), limit=96),
        "dispatch_join_status": _safe_text(source.get("status"), limit=32),
        "dispatch_join_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "dispatch_join_valid": not dispatch_failures,
        "dispatch_join_failures": dispatch_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "approved_handoff_failures": approved_failures,
        "official_natural_mcp_case_proven": bool(
            ok and source.get("official_natural_mcp_case_proven") is True
        ),
        "dispatch_join_proven": ok,
        "dispatch_join_prompt_digest_bound": bool(
            ok
            and source.get("prompt_digest_bound_to_official_mcp_and_ledger_dispatch")
            is True
        ),
        "prompt_digest": _hex_sha256(source.get("prompt_digest")) if ok else "",
        "selected_alias": _safe_text(source.get("selected_alias"), limit=80) if ok else "",
        "selected_alias_lane": _safe_text(
            source.get("selected_alias_lane"),
            limit=32,
        )
        if ok
        else "",
        "selected_slot": _safe_text(source.get("selected_slot"), limit=64) if ok else "",
        "alias_context_read": bool(ok and source.get("alias_context_read") is True),
        "allowed_api_route_ids_enforced": bool(
            ok and source.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": bool(ok and source.get("route_id_allowed") is True),
        "api_lane_called": bool(ok and source.get("api_lane_called") is True),
        "api_lane_dispatch_admitted": bool(
            ok and source.get("api_lane_dispatch_admitted") is True
        ),
        "api_lane_provider_called": bool(
            ok and source.get("api_lane_provider_called") is True
        ),
        "provider_response_proven": bool(
            ok and source.get("provider_response_proven") is True
        ),
        "controlled_provider_response_proven": bool(
            ok and source.get("controlled_provider_response_proven") is True
        ),
        "result_bound_to_dispatch": bool(
            ok and source.get("response_bound_to_proof") is True
        ),
        "dispatch_attempted": bool(ok and source.get("dispatch_attempted") is True),
        "dispatch_proven": bool(ok and source.get("dispatch_proven") is True),
        "real_ledger_bound_api_dispatch_proven": bool(
            ok and source.get("real_ledger_bound_api_dispatch_proven") is True
        ),
        "route_bound_dispatch_proven": bool(
            ok and source.get("route_bound_dispatch_proven") is True
        ),
        "selected_api_route_id_present": bool(
            ok and source.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            source.get("selected_api_route_id_sha256")
        )
        if ok
        else "",
        "route_bound_request_sha256": _hex_sha256(
            source.get("route_bound_request_sha256")
        )
        if ok
        else "",
        "provider_response_digest": _hex_sha256(source.get("provider_response_digest"))
        if ok
        else "",
        "controlled_provider_response_sha256": _hex_sha256(
            source.get("controlled_provider_response_sha256")
        )
        if ok
        else "",
        "normalized_dispatch_packet_kind": _safe_text(
            normalized_dispatch.get("packet_kind"),
            limit=80,
        )
        if ok
        else "",
        "approved_handoff_packet_kind": _safe_text(
            approved_packet.get("packet_kind"),
            limit=80,
        ),
        "approved_handoff_status": _safe_text(approved_packet.get("status"), limit=32),
        "approved_handoff_machine_error_code": _safe_text(
            approved_packet.get("machine_error_code"),
            limit=96,
        ),
        "approved_handoff_ready": bool(
            ok and approved_packet.get("handoff_ready") is True
        ),
        "approved_handoff_payload_sanitized": bool(
            ok and approved_packet.get("handoff_payload_sanitized") is True
        ),
        "approved_handoff_surface_used": bool(
            ok and approved_packet.get("handoff_surface_allowed") is True
        ),
        "handoff_surface_kind": HANDOFF_SURFACE_MCP_TOOL_RESPONSE if ok else "",
        "handoff_source_digest_bound": bool(ok and handoff_source_digest_bound),
        "working_flow_source_bound": bool(ok and handoff_source_digest_bound),
        "approved_working_flow_source_bound": bool(ok and handoff_source_digest_bound),
        "approved_visible_source_bound": False,
        "handoff_payload_digest": approved_handoff_digest if ok else "",
        "expected_handoff_payload_digest": expected_handoff_digest if ok else "",
        "handoff_payload_prepared": bool(
            ok and approved_packet.get("handoff_payload_prepared") is True
        ),
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "live_provider_status": "not_attempted",
        "product_ready": False,
        "does_not_prove_handoff_delivery": True,
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
            "WBP proved official MCP dispatch bound to an approved handoff source."
            if ok
            else "WBP blocked official MCP dispatch to approved handoff source proof."
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


def run_official_mcp_handoff_source_proof_command(
    *,
    dispatch_join_file: str,
) -> dict[str, Any]:
    dispatch_join_packet, metadata = _packet_file_metadata(
        Path(dispatch_join_file).expanduser()
    )
    return build_official_mcp_handoff_source_proof_packet(
        dispatch_join_packet=dispatch_join_packet,
        file_metadata=metadata,
    )
