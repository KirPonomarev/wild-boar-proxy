# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any

from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import (
    CONTROLLED_API_DISPATCH_PACKET_KIND,
    run_controlled_api_dispatch_command,
)
from .core import packets
from .router_hook_entry import HOOK_SURFACE_LOCAL_PROOF_COMMAND, _safe_text
from .runtime import RuntimePaths


APPROVED_HANDOFF_PACKET_KIND = "wbp_approved_handoff_proof"

HANDOFF_SURFACE_FILE_BRIDGE = "file_bridge"
HANDOFF_SURFACE_PASTE_BRIDGE = "paste_bridge"
HANDOFF_SURFACE_MCP_TOOL_RESPONSE = "mcp_tool_response"
HANDOFF_SURFACE_EXEC_WRAPPER_OUTPUT = "exec_wrapper_output"
HANDOFF_SURFACE_LOCAL_PROOF_COMMAND = "local_proof_command"

APPROVED_HANDOFF_SURFACES = frozenset(
    {
        HANDOFF_SURFACE_FILE_BRIDGE,
        HANDOFF_SURFACE_PASTE_BRIDGE,
        HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        HANDOFF_SURFACE_EXEC_WRAPPER_OUTPUT,
        HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
    }
)

APPROVED_HANDOFF_DISPATCH_PROOF_INVALID = "WBP_APPROVED_HANDOFF_DISPATCH_PROOF_INVALID"
APPROVED_HANDOFF_SURFACE_NOT_ALLOWED = "WBP_APPROVED_HANDOFF_SURFACE_NOT_ALLOWED"
APPROVED_HANDOFF_PAYLOAD_UNSAFE = "WBP_APPROVED_HANDOFF_PAYLOAD_UNSAFE"
APPROVED_HANDOFF_DELIVERY_NOT_OBSERVED = (
    "WBP_APPROVED_HANDOFF_DELIVERY_NOT_OBSERVED"
)

HANDOFF_TRUTH_SOURCE_PROVEN = "server_owned_controlled_dispatch"
HANDOFF_TRUTH_SOURCE_NOT_PROVEN = "not_proven"
DISPATCH_TRUTH_SOURCE_REQUIRED = "server_owned_controlled_provider_no_live_network"
API_LANE_TRUTH_SOURCE_REQUIRED = "server_owned_controlled_route_bound_dispatch"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(encoded)


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _expected_controlled_provider_response_sha256(
    *,
    route_bound_request_sha256: str,
    selected_api_route_id_sha256: str,
) -> str:
    response_fingerprint = json.dumps(
        {
            "controlled_provider": "wbp_controlled_route_bound_provider",
            "request_sha256": route_bound_request_sha256,
            "route_id_sha256": selected_api_route_id_sha256,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(response_fingerprint)


def _dispatch_proof_failures(dispatch_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch_packet.get("packet_kind") != CONTROLLED_API_DISPATCH_PACKET_KIND:
        failures.append("dispatch_packet_kind_invalid")
    if dispatch_packet.get("status") != "ok":
        failures.append("dispatch_packet_not_ok")
    if dispatch_packet.get("hook_entry_proven") is not True:
        failures.append("hook_entry_not_proven")
    if dispatch_packet.get("route_bound_dispatch_proven") is not True:
        failures.append("route_bound_dispatch_not_proven")
    if dispatch_packet.get("provider_response_proven") is not True:
        failures.append("provider_response_not_proven")
    if dispatch_packet.get("controlled_provider_response_proven") is not True:
        failures.append("controlled_provider_response_not_proven")
    if dispatch_packet.get("allowed_api_route_ids_enforced") is not True:
        failures.append("allowed_api_route_ids_not_enforced")
    if dispatch_packet.get("selected_api_route_id_recorded") is not False:
        failures.append("selected_api_route_id_must_not_be_recorded")
    if dispatch_packet.get("selected_api_route_id_present") is not True:
        failures.append("selected_api_route_id_missing")
    if dispatch_packet.get("route_bound_request_sent") is not True:
        failures.append("route_bound_request_not_sent")
    if dispatch_packet.get("controlled_provider_response_digest_present") is not True:
        failures.append("controlled_provider_response_digest_missing")
    selected_api_route_id_sha256 = _hex_sha256(
        dispatch_packet.get("selected_api_route_id_sha256")
    )
    route_bound_request_sha256 = _hex_sha256(
        dispatch_packet.get("route_bound_request_sha256")
    )
    provider_response_digest = _hex_sha256(
        dispatch_packet.get("provider_response_digest")
    )
    controlled_provider_response_sha256 = _hex_sha256(
        dispatch_packet.get("controlled_provider_response_sha256")
    )
    if not selected_api_route_id_sha256:
        failures.append("selected_api_route_digest_missing")
    if not route_bound_request_sha256:
        failures.append("route_bound_request_digest_missing")
    if not provider_response_digest:
        failures.append("provider_response_digest_missing")
    if not controlled_provider_response_sha256:
        failures.append("controlled_provider_response_digest_missing")
    if (
        provider_response_digest
        and controlled_provider_response_sha256
        and provider_response_digest != controlled_provider_response_sha256
    ):
        failures.append("provider_response_digest_not_bound")
    if (
        route_bound_request_sha256
        and selected_api_route_id_sha256
        and controlled_provider_response_sha256
        and controlled_provider_response_sha256
        != _expected_controlled_provider_response_sha256(
            route_bound_request_sha256=route_bound_request_sha256,
            selected_api_route_id_sha256=selected_api_route_id_sha256,
        )
    ):
        failures.append("controlled_provider_response_digest_invalid")
    if dispatch_packet.get("dispatch_truth_source") != DISPATCH_TRUTH_SOURCE_REQUIRED:
        failures.append("dispatch_truth_source_invalid")
    if dispatch_packet.get("api_lane_truth_source") != API_LANE_TRUTH_SOURCE_REQUIRED:
        failures.append("api_lane_truth_source_invalid")
    return failures


def _unsafe_source_claim_failures(dispatch_packet: Mapping[str, Any]) -> list[str]:
    checks = {
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "live_provider_response_proven": "live_provider_response_must_not_be_claimed",
        "external_live_provider_response_proven": (
            "external_live_provider_response_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "command_origin_proven": "command_origin_must_not_be_claimed",
        "custom_codex_origin_proven": "custom_codex_origin_must_not_be_claimed",
        "native_custom_codex_flow_proven": (
            "native_custom_codex_flow_must_not_be_claimed"
        ),
        "native_router_hook_observed": "native_router_hook_must_not_be_claimed",
    }
    return [
        reason
        for field, reason in checks.items()
        if dispatch_packet.get(field) is True
    ]


def _safe_handoff_payload(dispatch_packet: Mapping[str, Any], surface_kind: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_packet_kind": _safe_text(dispatch_packet.get("packet_kind"), limit=80),
        "source_prompt_digest": _safe_text(
            dispatch_packet.get("prompt_digest"),
            limit=80,
        ),
        "selected_alias": _safe_text(dispatch_packet.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            dispatch_packet.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(dispatch_packet.get("selected_slot"), limit=64),
        "selected_api_route_id_sha256": _safe_text(
            dispatch_packet.get("selected_api_route_id_sha256"),
            limit=80,
        ),
        "route_bound_request_sha256": _safe_text(
            dispatch_packet.get("route_bound_request_sha256"),
            limit=80,
        ),
        "provider_response_digest": _safe_text(
            dispatch_packet.get("provider_response_digest")
            or dispatch_packet.get("controlled_provider_response_sha256"),
            limit=80,
        ),
        "dispatch_truth_source": _safe_text(
            dispatch_packet.get("dispatch_truth_source"),
            limit=80,
        ),
        "api_lane_truth_source": _safe_text(
            dispatch_packet.get("api_lane_truth_source"),
            limit=80,
        ),
        "handoff_surface_kind": surface_kind,
    }


def build_approved_handoff_packet(
    dispatch_packet: Mapping[str, Any] | None,
    *,
    handoff_surface_kind: str = HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
    handoff_delivered: bool = False,
    handoff_delivery_observed: bool = False,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = dispatch_packet if isinstance(dispatch_packet, Mapping) else {}
    surface_kind = _safe_text(handoff_surface_kind, limit=80)
    surface_allowed = surface_kind in APPROVED_HANDOFF_SURFACES
    dispatch_failures = _dispatch_proof_failures(source)
    unsafe_failures = _unsafe_source_claim_failures(source)
    delivery_claim_invalid = bool(handoff_delivered and not handoff_delivery_observed)
    blocking_reasons: list[str] = []
    blocking_reasons.extend(dispatch_failures)
    if not surface_allowed:
        blocking_reasons.append("handoff_surface_not_allowed")
    blocking_reasons.extend(unsafe_failures)
    if delivery_claim_invalid:
        blocking_reasons.append("handoff_delivery_not_observed")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif dispatch_failures:
        machine_error_code = APPROVED_HANDOFF_DISPATCH_PROOF_INVALID
    elif not surface_allowed:
        machine_error_code = APPROVED_HANDOFF_SURFACE_NOT_ALLOWED
    elif unsafe_failures:
        machine_error_code = APPROVED_HANDOFF_PAYLOAD_UNSAFE
    else:
        machine_error_code = APPROVED_HANDOFF_DELIVERY_NOT_OBSERVED

    payload = _safe_handoff_payload(source, surface_kind)
    payload_digest = _canonical_json_digest(payload) if ok else ""
    extra = {
        "schema_version": 1,
        "packet_kind": APPROVED_HANDOFF_PACKET_KIND,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=80),
        "source_packet_status": _safe_text(source.get("status"), limit=32),
        "source_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "source_dispatch_packet_valid": not dispatch_failures,
        "source_dispatch_failures": dispatch_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "hook_entry_proven": source.get("hook_entry_proven") is True,
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
        "handoff_surface_kind": surface_kind,
        "handoff_surface_allowed": surface_allowed,
        "handoff_surface_allowlist_enforced": True,
        "approved_handoff_surfaces_count": len(APPROVED_HANDOFF_SURFACES),
        "handoff_payload_prepared": ok,
        "handoff_ready": ok,
        "handoff_payload_sanitized": ok,
        "handoff_payload_sha256": payload_digest,
        "handoff_payload_field_count": len(payload) if ok else 0,
        "handoff_payload_text_recorded": False,
        "handoff_payload_raw_recorded": False,
        "handoff_truth_source": (
            HANDOFF_TRUTH_SOURCE_PROVEN if ok else HANDOFF_TRUTH_SOURCE_NOT_PROVEN
        ),
        "handoff_delivered_requested": bool(handoff_delivered),
        "handoff_delivery_observed": bool(handoff_delivery_observed),
        "handoff_delivered": bool(ok and handoff_delivered and handoff_delivery_observed),
        "handoff_counts_as_native_free_chat_router": False,
        "handoff_counts_as_live_provider_proof": False,
        "handoff_counts_as_product_ready": False,
        "command_origin_proven": False,
        "custom_codex_origin_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
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
        "browser_can_supply_handoff_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP approved handoff proof prepared a sanitized handoff payload."
            if ok
            else "WBP approved handoff proof blocked before handoff readiness."
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


def run_approved_handoff_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    handoff_surface_kind: str = HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
) -> dict[str, Any]:
    dispatch_packet = run_controlled_api_dispatch_command(
        paths=paths,
        prompt_text=prompt_text,
        runtime_context_file=runtime_context_file,
        hook_surface_kind=hook_surface_kind,
    )
    return build_approved_handoff_packet(
        dispatch_packet,
        handoff_surface_kind=handoff_surface_kind,
        secret_values=[str(prompt_text or "")],
    )
