# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .official_mcp_admission_proof import OFFICIAL_MCP_ADMISSION_CASE_PACKET_KIND
from .real_ledger_bound_api_dispatch_proof import (
    REAL_LEDGER_BOUND_API_DISPATCH_OK,
    REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND,
)
from .router_hook_entry import _safe_text


OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_PACKET_KIND = (
    "wbp_official_mcp_ledger_bound_dispatch_join"
)

OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OK = "OK"
OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OFFICIAL_NOT_PROVEN = (
    "WBP_OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OFFICIAL_NOT_PROVEN"
)
OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DISPATCH_NOT_PROVEN = (
    "WBP_OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DISPATCH_NOT_PROVEN"
)
OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DIGEST_MISMATCH = (
    "WBP_OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DIGEST_MISMATCH"
)
OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_ALIAS_MISMATCH = (
    "WBP_OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_ALIAS_MISMATCH"
)
OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_UNSAFE_SOURCE"
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


def _packet_file_metadata(path: Path, *, prefix: str) -> tuple[dict[str, Any], dict[str, Any]]:
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


def _official_required_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("packet_kind") != OFFICIAL_MCP_ADMISSION_CASE_PACKET_KIND:
        failures.append("official_mcp_case_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("official_mcp_case_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("official_mcp_case_machine_error_not_ok")
    for field, reason in (
        ("expectation_met", "official_mcp_expectation_not_met"),
        ("positive_proof", "official_mcp_positive_proof_not_proven"),
        ("natural_prompt_used", "natural_prompt_not_used"),
        ("strict_natural_prompt", "strict_natural_prompt_not_proven"),
        ("natural_alias_intent_routed", "natural_alias_intent_not_routed"),
        ("expected_alias_present_in_prompt", "expected_alias_not_present_in_prompt"),
        ("codex_mcp_config_loaded", "codex_mcp_config_not_loaded"),
        ("codex_mcp_tool_called", "codex_mcp_tool_not_called"),
        (
            "delegate_to_dip_tool_call_completed",
            "delegate_to_dip_tool_call_not_completed",
        ),
        ("prompt_to_mcp_call_bound", "prompt_not_bound_to_mcp_call"),
        ("prompt_digest_bound_to_tool_call", "prompt_digest_not_bound_to_tool_call"),
        ("intent_claim_digest_present", "intent_claim_digest_missing"),
        ("intent_claim_digest_bound", "intent_claim_digest_not_bound"),
        ("tool_call_task_matches_intent", "tool_call_task_not_bound_to_intent"),
        ("alias_context_read", "official_alias_context_not_read"),
        ("selected_alias_matches_expected", "official_alias_mismatch"),
        ("allowed_api_route_ids_enforced", "official_allowed_routes_not_enforced"),
        ("api_lane_called", "official_api_lane_not_called"),
        ("route_bound_dispatch_proven", "official_route_dispatch_not_proven"),
        (
            "controlled_provider_response_proven",
            "official_controlled_provider_response_not_proven",
        ),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    if packet.get("explicit_tool_instruction_used") is True:
        failures.append("explicit_tool_instruction_used")
    if not _hex_sha256(packet.get("prompt_sha256")):
        failures.append("official_prompt_digest_missing")
    return sorted(set(failures))


def _dispatch_required_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("packet_kind") != REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND:
        failures.append("ledger_bound_dispatch_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("ledger_bound_dispatch_packet_not_ok")
    if packet.get("machine_error_code") != REAL_LEDGER_BOUND_API_DISPATCH_OK:
        failures.append("ledger_bound_dispatch_machine_error_not_ok")
    if packet.get("changed_files") not in ([], ()):
        failures.append("ledger_bound_dispatch_changed_files_not_empty")
    if packet.get("effect") != EFFECT_PROBE:
        failures.append("ledger_bound_dispatch_effect_not_probe")
    for field, reason in (
        ("real_ledger_bound_api_dispatch_proven", "ledger_bound_dispatch_not_proven"),
        ("ledger_bound_dispatch_admitted", "ledger_bound_dispatch_not_admitted"),
        ("real_user_prompt_submit_ledger_proven", "user_prompt_ledger_not_proven"),
        ("custom_codex_origin_proven", "custom_codex_origin_not_proven"),
        ("native_custom_codex_flow_proven", "native_custom_codex_flow_not_proven"),
        ("native_router_hook_observed", "native_router_hook_not_observed"),
        ("user_prompt_submit_hook_observed", "user_prompt_submit_hook_not_observed"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_event_transport_stdin", "hook_event_transport_not_stdin"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("prompt_digest_bound_to_ledger", "prompt_digest_not_bound_to_ledger"),
        ("prompt_digest_bound_to_dispatch", "prompt_digest_not_bound_to_dispatch"),
        ("alias_context_read", "dispatch_alias_context_not_read"),
        ("alias_bound", "dispatch_alias_not_bound"),
        ("route_id_allowed", "dispatch_route_not_allowed"),
        ("allowed_api_route_ids_enforced", "dispatch_allowed_routes_not_enforced"),
        ("api_lane_called", "dispatch_api_lane_not_called"),
        ("api_lane_dispatch_admitted", "dispatch_api_lane_not_admitted"),
        ("api_lane_provider_called", "dispatch_provider_not_called"),
        ("api_response_received", "dispatch_api_response_not_received"),
        ("provider_response_proven", "dispatch_provider_response_not_proven"),
        (
            "controlled_provider_response_proven",
            "dispatch_controlled_provider_response_not_proven",
        ),
        ("dispatch_attempted", "dispatch_not_attempted"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "dispatch_route_bound_not_proven"),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(packet.get("prompt_digest")):
        failures.append("dispatch_prompt_digest_missing")
    return sorted(set(failures))


def _unsafe_claim_failures(
    packet: Mapping[str, Any],
    *,
    prefix: str,
) -> list[str]:
    checks = {
        "product_ready": "product_ready",
        "custom_codex_ui_visibility_proven": "custom_codex_ui_visibility_proven",
        "codex_working_flow_delivery_proven": "codex_working_flow_delivery_proven",
        "native_free_chat_router_proven": "native_free_chat_router_proven",
        "native_free_chat_router_product_ready": "native_free_chat_router_product_ready",
        "handoff_file_written": "handoff_file_written",
        "handoff_delivered": "handoff_delivered",
        "delivery_observed": "delivery_observed",
        "live_provider_proven": "live_provider_proven",
        "live_provider_response_proven": "live_provider_response_proven",
        "external_live_provider_response_proven": "external_live_provider_response_proven",
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
        "uses_danger_full_access": "uses_danger_full_access",
        "uses_dangerously_bypass": "uses_dangerously_bypass",
    }
    return sorted(
        {
            f"{prefix}_{reason}"
            for field, reason in checks.items()
            if packet.get(field) is True
        }
    )


def _machine_error_code(
    *,
    official_failures: Sequence[str],
    dispatch_failures: Sequence[str],
    prompt_digest_bound: bool,
    alias_bound: bool,
    unsafe_failures: Sequence[str],
) -> str:
    if not (
        official_failures
        or dispatch_failures
        or not prompt_digest_bound
        or not alias_bound
        or unsafe_failures
    ):
        return OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OK
    if unsafe_failures:
        return OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_UNSAFE_SOURCE
    if official_failures:
        return OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OFFICIAL_NOT_PROVEN
    if dispatch_failures:
        return OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DISPATCH_NOT_PROVEN
    if not prompt_digest_bound:
        return OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DIGEST_MISMATCH
    return OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_ALIAS_MISMATCH


def build_official_mcp_ledger_bound_dispatch_join_packet(
    *,
    official_mcp_case_packet: Mapping[str, Any] | None,
    ledger_bound_dispatch_packet: Mapping[str, Any] | None,
    official_mcp_file_metadata: Mapping[str, Any] | None = None,
    ledger_bound_dispatch_file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    official = _mapping(official_mcp_case_packet)
    dispatch = _mapping(ledger_bound_dispatch_packet)
    official_metadata = dict(official_mcp_file_metadata or {})
    dispatch_metadata = dict(ledger_bound_dispatch_file_metadata or {})

    official_failures = _official_required_failures(official)
    dispatch_failures = _dispatch_required_failures(dispatch)
    unsafe_failures = sorted(
        set(
            _unsafe_claim_failures(official, prefix="official")
            + _unsafe_claim_failures(dispatch, prefix="dispatch")
        )
    )

    official_prompt_digest = _hex_sha256(official.get("prompt_sha256"))
    dispatch_prompt_digest = _hex_sha256(dispatch.get("prompt_digest"))
    prompt_digest_bound = bool(
        official_prompt_digest
        and dispatch_prompt_digest
        and official_prompt_digest == dispatch_prompt_digest
    )
    official_alias = _safe_text(official.get("selected_alias"), limit=80)
    dispatch_alias = _safe_text(dispatch.get("selected_alias"), limit=80)
    expected_alias = _safe_text(official.get("expected_alias"), limit=80)
    alias_bound = bool(
        official_alias
        and dispatch_alias
        and expected_alias
        and official_alias == dispatch_alias == expected_alias
    )

    blocking_reasons = sorted(
        set(
            official_failures
            + dispatch_failures
            + ([] if prompt_digest_bound else ["official_dispatch_prompt_digest_mismatch"])
            + ([] if alias_bound else ["official_dispatch_alias_mismatch"])
            + unsafe_failures
            + _safe_reasons(official.get("proof_blocking_reasons"))
            + _safe_reasons(dispatch.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        official_failures=official_failures,
        dispatch_failures=dispatch_failures,
        prompt_digest_bound=prompt_digest_bound,
        alias_bound=alias_bound,
        unsafe_failures=unsafe_failures,
    )

    extra = {
        **official_metadata,
        **dispatch_metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_PACKET_KIND,
        "proof_scope": (
            "official_natural_mcp_tool_call_to_real_user_prompt_submit_ledger_bound_dispatch"
        ),
        "official_mcp_case_packet_kind": _safe_text(
            official.get("packet_kind"),
            limit=96,
        ),
        "official_mcp_case_status": _safe_text(official.get("status"), limit=32),
        "official_mcp_case_machine_error_code": _safe_text(
            official.get("machine_error_code"),
            limit=96,
        ),
        "ledger_bound_dispatch_packet_kind": _safe_text(
            dispatch.get("packet_kind"),
            limit=96,
        ),
        "ledger_bound_dispatch_status": _safe_text(dispatch.get("status"), limit=32),
        "ledger_bound_dispatch_machine_error_code": _safe_text(
            dispatch.get("machine_error_code"),
            limit=96,
        ),
        "official_natural_mcp_case_proven": bool(
            ok and official.get("positive_proof") is True
        ),
        "official_natural_alias_intent_routed": bool(
            ok and official.get("natural_alias_intent_routed") is True
        ),
        "strict_natural_prompt": bool(ok and official.get("strict_natural_prompt") is True),
        "explicit_tool_instruction_used": bool(
            official.get("explicit_tool_instruction_used") is True
        ),
        "prompt_to_mcp_call_bound": bool(
            ok and official.get("prompt_to_mcp_call_bound") is True
        ),
        "intent_claim_digest_bound": bool(
            ok and official.get("intent_claim_digest_bound") is True
        ),
        "tool_call_task_matches_intent": bool(
            ok and official.get("tool_call_task_matches_intent") is True
        ),
        "official_prompt_digest_present": bool(official_prompt_digest),
        "dispatch_prompt_digest_present": bool(dispatch_prompt_digest),
        "prompt_digest": official_prompt_digest if ok else "",
        "prompt_digest_bound_to_official_mcp_case": bool(
            ok and official_prompt_digest
        ),
        "prompt_digest_bound_to_ledger": bool(
            ok and dispatch.get("prompt_digest_bound_to_ledger") is True
        ),
        "prompt_digest_bound_to_dispatch": bool(
            ok and dispatch.get("prompt_digest_bound_to_dispatch") is True
        ),
        "prompt_digest_bound_to_official_mcp_and_ledger_dispatch": bool(
            ok and prompt_digest_bound
        ),
        "selected_alias": official_alias if ok else "",
        "expected_alias": expected_alias if ok else "",
        "selected_alias_matches_expected": bool(
            ok and official.get("selected_alias_matches_expected") is True
        ),
        "official_dispatch_alias_bound": bool(ok and alias_bound),
        "selected_alias_lane": _safe_text(dispatch.get("selected_alias_lane"), limit=32)
        if ok
        else "",
        "selected_slot": _safe_text(dispatch.get("selected_slot"), limit=64)
        if ok
        else "",
        "alias_context_read": bool(
            ok
            and official.get("alias_context_read") is True
            and dispatch.get("alias_context_read") is True
        ),
        "alias_bound": bool(ok and dispatch.get("alias_bound") is True),
        "allowed_api_route_ids_enforced": bool(
            ok
            and official.get("allowed_api_route_ids_enforced") is True
            and dispatch.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": bool(ok and dispatch.get("route_id_allowed") is True),
        "user_prompt_submit_hook_ran": bool(
            ok and dispatch.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_ledger_written": bool(ok and dispatch.get("hook_ledger_written") is True),
        "real_user_prompt_submit_ledger_proven": bool(
            ok and dispatch.get("real_user_prompt_submit_ledger_proven") is True
        ),
        "custom_codex_origin_proven": bool(
            ok and dispatch.get("custom_codex_origin_proven") is True
        ),
        "native_custom_codex_flow_proven": bool(
            ok and dispatch.get("native_custom_codex_flow_proven") is True
        ),
        "native_router_hook_observed": bool(
            ok and dispatch.get("native_router_hook_observed") is True
        ),
        "ledger_bound_dispatch_admitted": bool(
            ok and dispatch.get("ledger_bound_dispatch_admitted") is True
        ),
        "api_lane_called": bool(
            ok
            and official.get("api_lane_called") is True
            and dispatch.get("api_lane_called") is True
        ),
        "api_lane_dispatch_admitted": bool(
            ok and dispatch.get("api_lane_dispatch_admitted") is True
        ),
        "api_lane_provider_called": bool(
            ok and dispatch.get("api_lane_provider_called") is True
        ),
        "provider_response_proven": bool(
            ok and dispatch.get("provider_response_proven") is True
        ),
        "controlled_provider_response_proven": bool(
            ok
            and official.get("controlled_provider_response_proven") is True
            and dispatch.get("controlled_provider_response_proven") is True
        ),
        "dispatch_attempted": bool(ok and dispatch.get("dispatch_attempted") is True),
        "dispatch_proven": ok,
        "real_ledger_bound_api_dispatch_proven": bool(
            ok and dispatch.get("real_ledger_bound_api_dispatch_proven") is True
        ),
        "route_bound_dispatch_proven": bool(
            ok
            and official.get("route_bound_dispatch_proven") is True
            and dispatch.get("route_bound_dispatch_proven") is True
        ),
        "official_required_failures": official_failures,
        "dispatch_required_failures": dispatch_failures,
        "unsafe_source_failures": unsafe_failures,
        "blocking_reasons": blocking_reasons,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "live_provider_status": "not_attempted",
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_live_provider": True,
        "does_not_prove_handoff": True,
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
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved official natural MCP admission bound to real ledger-backed API dispatch."
            if ok
            else "WBP blocked official natural MCP to ledger-backed API dispatch join."
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


def run_official_mcp_ledger_bound_dispatch_join_command(
    *,
    official_mcp_case_file: str,
    ledger_bound_dispatch_proof_file: str,
) -> dict[str, Any]:
    official_packet, official_metadata = _packet_file_metadata(
        Path(official_mcp_case_file).expanduser(),
        prefix="official_mcp_case",
    )
    dispatch_packet, dispatch_metadata = _packet_file_metadata(
        Path(ledger_bound_dispatch_proof_file).expanduser(),
        prefix="ledger_bound_dispatch_proof",
    )
    return build_official_mcp_ledger_bound_dispatch_join_packet(
        official_mcp_case_packet=official_packet,
        ledger_bound_dispatch_packet=dispatch_packet,
        official_mcp_file_metadata=official_metadata,
        ledger_bound_dispatch_file_metadata=dispatch_metadata,
    )
