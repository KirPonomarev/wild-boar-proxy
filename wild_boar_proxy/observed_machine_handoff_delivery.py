# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any

from .approved_handoff import (
    APPROVED_HANDOFF_PACKET_KIND,
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    HANDOFF_TRUTH_SOURCE_PROVEN,
    build_approved_handoff_packet,
    _safe_handoff_payload,
)
from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import run_controlled_api_dispatch_command
from .core import packets
from .router_hook_entry import HOOK_SURFACE_LOCAL_PROOF_COMMAND, _safe_text
from .runtime import RuntimePaths


OBSERVED_MACHINE_HANDOFF_DELIVERY_PACKET_KIND = (
    "wbp_observed_machine_handoff_delivery"
)
MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND = "wbp_machine_handoff_delivery_payload"

DELIVERY_SURFACE_MCP_TOOL_RESPONSE = "mcp_tool_response"
APPROVED_DELIVERY_SURFACES = frozenset({DELIVERY_SURFACE_MCP_TOOL_RESPONSE})

DELIVERY_TRUTH_SOURCE_PROVEN = "server_owned_mcp_tool_response_envelope"
DELIVERY_TRUTH_SOURCE_NOT_PROVEN = "not_proven"

OBSERVED_MACHINE_HANDOFF_APPROVED_HANDOFF_INVALID = (
    "WBP_OBSERVED_MACHINE_HANDOFF_APPROVED_HANDOFF_INVALID"
)
OBSERVED_MACHINE_HANDOFF_SURFACE_NOT_ALLOWED = (
    "WBP_OBSERVED_MACHINE_HANDOFF_SURFACE_NOT_ALLOWED"
)
OBSERVED_MACHINE_HANDOFF_NOT_OBSERVED = "WBP_OBSERVED_MACHINE_HANDOFF_NOT_OBSERVED"
OBSERVED_MACHINE_HANDOFF_PAYLOAD_UNSAFE = "WBP_OBSERVED_MACHINE_HANDOFF_PAYLOAD_UNSAFE"
OBSERVED_MACHINE_HANDOFF_DIGEST_MISMATCH = (
    "WBP_OBSERVED_MACHINE_HANDOFF_DIGEST_MISMATCH"
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _canonical_json_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(encoded)


def build_mcp_tool_response_handoff_envelope(
    handoff_payload: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(handoff_payload)
    text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": False,
    }


def _approved_handoff_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != APPROVED_HANDOFF_PACKET_KIND:
        failures.append("approved_handoff_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("approved_handoff_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("approved_handoff_machine_error_code_not_ok")
    if source.get("source_dispatch_packet_valid") is not True:
        failures.append("source_dispatch_packet_not_valid")
    if source.get("hook_entry_proven") is not True:
        failures.append("hook_entry_not_proven")
    if source.get("route_bound_dispatch_proven") is not True:
        failures.append("route_bound_dispatch_not_proven")
    if source.get("provider_response_proven") is not True:
        failures.append("provider_response_not_proven")
    if source.get("controlled_provider_response_proven") is not True:
        failures.append("controlled_provider_response_not_proven")
    if source.get("allowed_api_route_ids_enforced") is not True:
        failures.append("allowed_api_route_ids_not_enforced")
    if source.get("handoff_surface_kind") != HANDOFF_SURFACE_MCP_TOOL_RESPONSE:
        failures.append("handoff_surface_must_be_mcp_tool_response")
    if source.get("handoff_surface_allowed") is not True:
        failures.append("handoff_surface_not_allowed")
    if source.get("handoff_surface_allowlist_enforced") is not True:
        failures.append("handoff_surface_allowlist_not_enforced")
    if source.get("handoff_payload_prepared") is not True:
        failures.append("handoff_payload_not_prepared")
    if source.get("handoff_ready") is not True:
        failures.append("handoff_not_ready")
    if source.get("handoff_payload_sanitized") is not True:
        failures.append("handoff_payload_not_sanitized")
    if not _hex_sha256(source.get("handoff_payload_sha256")):
        failures.append("handoff_payload_digest_missing")
    if source.get("handoff_truth_source") != HANDOFF_TRUTH_SOURCE_PROVEN:
        failures.append("handoff_truth_source_invalid")
    if source.get("handoff_delivered") is not False:
        failures.append("handoff_must_not_be_previously_delivered")
    if source.get("handoff_delivery_observed") is not False:
        failures.append("handoff_delivery_observation_must_be_created_here")
    return failures


def _unsafe_source_claim_failures(source: Mapping[str, Any]) -> list[str]:
    checks = {
        "handoff_payload_text_recorded": "handoff_payload_text_recorded",
        "handoff_payload_raw_recorded": "handoff_payload_raw_recorded",
        "handoff_counts_as_native_free_chat_router": (
            "handoff_counts_as_native_free_chat_router"
        ),
        "handoff_counts_as_live_provider_proof": (
            "handoff_counts_as_live_provider_proof"
        ),
        "handoff_counts_as_product_ready": "handoff_counts_as_product_ready",
        "command_origin_proven": "command_origin_must_not_be_claimed",
        "custom_codex_origin_proven": "custom_codex_origin_must_not_be_claimed",
        "native_custom_codex_flow_proven": (
            "native_custom_codex_flow_must_not_be_claimed"
        ),
        "native_router_hook_observed": "native_router_hook_must_not_be_claimed",
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "live_provider_proven": "live_provider_must_not_be_claimed",
        "live_provider_response_proven": "live_provider_response_must_not_be_claimed",
        "external_live_provider_response_proven": (
            "external_live_provider_response_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
    }
    return [reason for field, reason in checks.items() if source.get(field) is True]


def _safe_delivery_payload(
    handoff_payload: Mapping[str, Any],
    *,
    delivery_surface_kind: str,
) -> dict[str, Any]:
    payload = dict(handoff_payload)
    return {
        "schema_version": 1,
        "packet_kind": MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND,
        "handoff_payload": payload,
        "handoff_payload_sha256": _canonical_json_digest(payload),
        "handoff_surface_kind": _safe_text(
            payload.get("handoff_surface_kind"),
            limit=80,
        ),
        "delivery_surface_kind": delivery_surface_kind,
        "delivery_truth_source": DELIVERY_TRUTH_SOURCE_PROVEN,
    }


def build_observed_machine_handoff_delivery_packet(
    approved_handoff_packet: Mapping[str, Any] | None,
    *,
    handoff_payload: Mapping[str, Any] | None = None,
    delivery_surface_kind: str = DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    delivery_surface_observed: bool = True,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = approved_handoff_packet if isinstance(approved_handoff_packet, Mapping) else {}
    surface_kind = _safe_text(delivery_surface_kind, limit=80)
    surface_allowed = surface_kind in APPROVED_DELIVERY_SURFACES
    approved_failures = _approved_handoff_failures(source)
    unsafe_failures = _unsafe_source_claim_failures(source)
    payload_available = isinstance(handoff_payload, Mapping)
    safe_payload = (
        _safe_delivery_payload(handoff_payload, delivery_surface_kind=surface_kind)
        if payload_available
        else {}
    )
    delivery_payload_sha256 = (
        _canonical_json_digest(safe_payload["handoff_payload"])
        if safe_payload
        else ""
    )
    approved_payload_sha256 = _hex_sha256(source.get("handoff_payload_sha256"))
    payload_digest_matches = bool(
        delivery_payload_sha256
        and approved_payload_sha256
        and delivery_payload_sha256 == approved_payload_sha256
    )
    delivery_preconditions_met = bool(
        not approved_failures
        and not unsafe_failures
        and surface_allowed
        and payload_available
        and payload_digest_matches
    )
    envelope = (
        build_mcp_tool_response_handoff_envelope(safe_payload)
        if delivery_preconditions_met and delivery_surface_observed
        else {}
    )
    envelope_observed = bool(envelope)
    envelope_sha256 = _canonical_json_digest(envelope) if envelope else ""

    blocking_reasons: list[str] = []
    blocking_reasons.extend(approved_failures)
    blocking_reasons.extend(unsafe_failures)
    if not surface_allowed:
        blocking_reasons.append("delivery_surface_not_allowed")
    if not delivery_surface_observed:
        blocking_reasons.append("delivery_surface_not_observed")
    if not payload_available:
        blocking_reasons.append("handoff_payload_missing")
    elif not payload_digest_matches:
        blocking_reasons.append("handoff_payload_digest_mismatch")
    if not envelope_observed:
        blocking_reasons.append("machine_response_envelope_not_observed")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif approved_failures:
        machine_error_code = OBSERVED_MACHINE_HANDOFF_APPROVED_HANDOFF_INVALID
    elif unsafe_failures:
        machine_error_code = OBSERVED_MACHINE_HANDOFF_PAYLOAD_UNSAFE
    elif not surface_allowed:
        machine_error_code = OBSERVED_MACHINE_HANDOFF_SURFACE_NOT_ALLOWED
    elif payload_available and not payload_digest_matches:
        machine_error_code = OBSERVED_MACHINE_HANDOFF_DIGEST_MISMATCH
    elif not delivery_surface_observed or not envelope_observed:
        machine_error_code = OBSERVED_MACHINE_HANDOFF_NOT_OBSERVED
    else:
        machine_error_code = OBSERVED_MACHINE_HANDOFF_DIGEST_MISMATCH

    extra = {
        "schema_version": 1,
        "packet_kind": OBSERVED_MACHINE_HANDOFF_DELIVERY_PACKET_KIND,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=80),
        "source_packet_status": _safe_text(source.get("status"), limit=32),
        "source_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "approved_handoff_packet_valid": not approved_failures,
        "approved_handoff_failures": approved_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "handoff_ready": source.get("handoff_ready") is True,
        "handoff_payload_sanitized": source.get("handoff_payload_sanitized") is True,
        "handoff_truth_source": _safe_text(
            source.get("handoff_truth_source"),
            limit=80,
        ),
        "handoff_surface_kind": _safe_text(
            source.get("handoff_surface_kind"),
            limit=80,
        ),
        "approved_handoff_payload_sha256": approved_payload_sha256,
        "delivery_surface_kind": surface_kind,
        "delivery_surface_allowed": surface_allowed,
        "delivery_surface_allowlist_enforced": True,
        "approved_delivery_surfaces_count": len(APPROVED_DELIVERY_SURFACES),
        "delivery_attempted": delivery_preconditions_met,
        "delivery_surface_observed": bool(delivery_surface_observed),
        "machine_response_envelope_observed": envelope_observed,
        "machine_response_envelope_sha256": envelope_sha256,
        "machine_response_structured_content_present": bool(envelope),
        "machine_response_structured_content_sha256": (
            _canonical_json_digest(safe_payload) if envelope else ""
        ),
        "machine_response_content_text_present": bool(envelope),
        "machine_response_content_text_recorded": False,
        "machine_response_raw_recorded": False,
        "mcp_tool_response_is_error": bool(envelope.get("isError")) if envelope else False,
        "delivery_payload_kind": (
            MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND if delivery_preconditions_met else ""
        ),
        "delivery_payload_prepared": delivery_preconditions_met,
        "delivery_payload_sanitized": delivery_preconditions_met,
        "delivery_payload_sha256": delivery_payload_sha256,
        "delivery_payload_digest_matches_approved_handoff": payload_digest_matches,
        "delivery_payload_text_recorded": False,
        "delivery_payload_raw_recorded": False,
        "handoff_delivered": ok,
        "delivery_observed": ok,
        "delivery_truth_source": (
            DELIVERY_TRUTH_SOURCE_PROVEN if ok else DELIVERY_TRUTH_SOURCE_NOT_PROVEN
        ),
        "delivery_counts_as_machine_handoff": ok,
        "delivery_counts_as_custom_codex_ui": False,
        "delivery_counts_as_native_free_chat_router": False,
        "delivery_counts_as_live_provider_proof": False,
        "delivery_counts_as_product_ready": False,
        "command_origin_proven": False,
        "custom_codex_origin_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
        "does_not_prove_product_ready": True,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
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
        "browser_can_supply_route_authority": False,
        "browser_can_supply_delivery_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP observed a sanitized approved handoff in an MCP tool response envelope."
            if ok
            else "WBP blocked observed machine handoff delivery before proof."
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


def run_observed_machine_handoff_delivery_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    delivery_surface_kind: str = DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
) -> dict[str, Any]:
    dispatch_packet = run_controlled_api_dispatch_command(
        paths=paths,
        prompt_text=prompt_text,
        runtime_context_file=runtime_context_file,
        hook_surface_kind=hook_surface_kind,
    )
    approved_packet = build_approved_handoff_packet(
        dispatch_packet,
        handoff_surface_kind=HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        secret_values=[str(prompt_text or "")],
    )
    handoff_payload = _safe_handoff_payload(
        dispatch_packet,
        HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    )
    return build_observed_machine_handoff_delivery_packet(
        approved_packet,
        handoff_payload=handoff_payload,
        delivery_surface_kind=delivery_surface_kind,
        secret_values=[str(prompt_text or "")],
    )
