# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .approved_handoff import (
    APPROVED_HANDOFF_PACKET_KIND,
    APPROVED_HANDOFF_SURFACES,
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    build_approved_handoff_packet,
    _safe_handoff_payload,
)
from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import CONTROLLED_API_DISPATCH_PACKET_KIND
from .controlled_ingress_api_dispatch_proof import (
    CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND,
)
from .core import packets
from .observed_machine_handoff_delivery import (
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    OBSERVED_MACHINE_HANDOFF_DELIVERY_PACKET_KIND,
    build_observed_machine_handoff_delivery_packet,
)
from .router_hook_entry import _safe_text


CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND = "wbp_controlled_dispatch_handoff_proof"

CONTROLLED_DISPATCH_HANDOFF_DISPATCH_PROOF_INVALID = (
    "WBP_CONTROLLED_DISPATCH_HANDOFF_DISPATCH_PROOF_INVALID"
)
CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_ALLOWED = (
    "WBP_CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_ALLOWED"
)
CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_SUPPORTED = (
    "WBP_CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_SUPPORTED"
)
CONTROLLED_DISPATCH_HANDOFF_PAYLOAD_UNSAFE = (
    "WBP_CONTROLLED_DISPATCH_HANDOFF_PAYLOAD_UNSAFE"
)
CONTROLLED_DISPATCH_HANDOFF_NOT_OBSERVED = "WBP_CONTROLLED_DISPATCH_HANDOFF_NOT_OBSERVED"


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _proof_file_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "dispatch_proof_file_required": True,
        "dispatch_proof_file_present": path.exists(),
        "dispatch_proof_file_read": False,
        "dispatch_proof_file_valid_json": False,
        "dispatch_proof_file_mapping": False,
        "dispatch_proof_file_error_code": "",
        "dispatch_proof_file_path_recorded": False,
    }
    if not path.exists():
        metadata["dispatch_proof_file_error_code"] = "dispatch_proof_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["dispatch_proof_file_error_code"] = "dispatch_proof_file_invalid"
        return {}, metadata
    metadata["dispatch_proof_file_read"] = True
    metadata["dispatch_proof_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["dispatch_proof_file_error_code"] = "dispatch_proof_file_not_mapping"
        return {}, metadata
    metadata["dispatch_proof_file_mapping"] = True
    return dict(parsed), metadata


def _unsafe_dispatch_claim_failures(dispatch: Mapping[str, Any]) -> list[str]:
    checks = {
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "raw_jsonl_recorded": "raw_jsonl_recorded",
        "tool_call_arguments_recorded": "tool_call_arguments_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "state_written": "state_written",
        "evidence_written": "evidence_written",
        "file_mutation_attempted": "file_mutation_attempted",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "live_provider_proven": "live_provider_must_not_be_claimed",
        "live_provider_response_proven": "live_provider_response_must_not_be_claimed",
        "external_live_provider_response_proven": (
            "external_live_provider_response_must_not_be_claimed"
        ),
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
        "command_origin_proven": "command_origin_must_not_be_claimed",
        "custom_codex_origin_proven": "custom_codex_origin_must_not_be_claimed",
        "native_custom_codex_flow_proven": (
            "native_custom_codex_flow_must_not_be_claimed"
        ),
        "native_router_hook_observed": "native_router_hook_must_not_be_claimed",
    }
    return sorted(
        {reason for field, reason in checks.items() if dispatch.get(field) is True}
    )


def _dispatch_proof_failures(dispatch: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch.get("packet_kind") != CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND:
        failures.append("dispatch_proof_packet_kind_invalid")
    if dispatch.get("status") != "ok":
        failures.append("dispatch_proof_packet_not_ok")
    if dispatch.get("machine_error_code") != "OK":
        failures.append("dispatch_proof_machine_error_not_ok")
    if dispatch.get("ingress_proven") is not True:
        failures.append("ingress_not_proven")
    if dispatch.get("controlled_ingress_proven") is not True:
        failures.append("controlled_ingress_not_proven")
    if dispatch.get("dispatch_proven") is not True:
        failures.append("dispatch_not_proven")
    if dispatch.get("dispatch_status") != "proven":
        failures.append("dispatch_status_not_proven")
    if dispatch.get("api_lane_called") is not True:
        failures.append("api_lane_not_called")
    if dispatch.get("api_response_received") is not True:
        failures.append("api_response_not_received")
    if dispatch.get("response_bound_to_proof") is not True:
        failures.append("response_not_bound_to_proof")
    if dispatch.get("provider_like_response_only") is not True:
        failures.append("provider_like_response_only_not_declared")
    if dispatch.get("route_bound_dispatch_proven") is not True:
        failures.append("route_bound_dispatch_not_proven")
    if dispatch.get("provider_response_proven") is not True:
        failures.append("provider_response_not_proven")
    if dispatch.get("controlled_provider_response_proven") is not True:
        failures.append("controlled_provider_response_not_proven")
    if dispatch.get("allowed_api_route_ids_enforced") is not True:
        failures.append("allowed_api_route_ids_not_enforced")
    if dispatch.get("forbidden_stale_route_ids_enforced") is not True:
        failures.append("stale_route_guard_missing")
    if int(dispatch.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("stale_route_guard_missing")
    if dispatch.get("selected_api_route_id_present") is not True:
        failures.append("selected_api_route_id_missing")
    if dispatch.get("selected_api_route_id_recorded") is not False:
        failures.append("selected_api_route_id_must_not_be_recorded")
    if not _hex_sha256(dispatch.get("selected_api_route_id_sha256")):
        failures.append("selected_api_route_digest_missing")
    if not _hex_sha256(dispatch.get("route_bound_request_sha256")):
        failures.append("route_bound_request_digest_missing")
    if not _hex_sha256(dispatch.get("provider_response_digest")):
        failures.append("provider_response_digest_missing")
    if not _hex_sha256(dispatch.get("controlled_provider_response_sha256")):
        failures.append("controlled_provider_response_digest_missing")
    if (
        _hex_sha256(dispatch.get("provider_response_digest"))
        and _hex_sha256(dispatch.get("controlled_provider_response_sha256"))
        and dispatch.get("provider_response_digest")
        != dispatch.get("controlled_provider_response_sha256")
    ):
        failures.append("provider_response_digest_not_bound")
    return sorted(set(failures))


def _normalized_controlled_dispatch_packet(
    dispatch: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "packet_kind": CONTROLLED_API_DISPATCH_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "dispatch_proven": dispatch.get("dispatch_proven") is True,
        "dispatch_status": _safe_text(dispatch.get("dispatch_status"), limit=32),
        "hook_entry_proven": dispatch.get("controlled_ingress_proven") is True,
        "route_bound_dispatch_proven": dispatch.get("route_bound_dispatch_proven")
        is True,
        "provider_response_proven": dispatch.get("provider_response_proven") is True,
        "controlled_provider_response_proven": dispatch.get(
            "controlled_provider_response_proven"
        )
        is True,
        "allowed_api_route_ids_enforced": dispatch.get(
            "allowed_api_route_ids_enforced"
        )
        is True,
        "selected_api_route_id_recorded": False,
        "selected_api_route_id_present": dispatch.get(
            "selected_api_route_id_present"
        )
        is True,
        "route_bound_request_sent": dispatch.get("route_bound_request_sent") is True,
        "controlled_provider_response_digest_present": bool(
            _hex_sha256(dispatch.get("controlled_provider_response_sha256"))
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            dispatch.get("selected_api_route_id_sha256")
        ),
        "route_bound_request_sha256": _hex_sha256(
            dispatch.get("route_bound_request_sha256")
        ),
        "provider_response_digest": _hex_sha256(
            dispatch.get("provider_response_digest")
        ),
        "controlled_provider_response_sha256": _hex_sha256(
            dispatch.get("controlled_provider_response_sha256")
        ),
        "dispatch_truth_source": _safe_text(
            dispatch.get("dispatch_truth_source"),
            limit=80,
        ),
        "api_lane_truth_source": _safe_text(
            dispatch.get("approved_api_lane_truth_source"),
            limit=80,
        ),
        "prompt_digest": _hex_sha256(dispatch.get("prompt_digest")),
        "selected_alias": _safe_text(
            dispatch.get("selected_alias") or dispatch.get("alias"),
            limit=80,
        ),
        "selected_alias_lane": "api_route",
        "selected_slot": _safe_text(
            dispatch.get("selected_slot") or dispatch.get("slot"),
            limit=64,
        ),
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


def build_controlled_dispatch_handoff_proof_packet(
    dispatch_proof_packet: Mapping[str, Any] | None,
    *,
    handoff_surface_kind: str = HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    handoff_surface_observed: bool = True,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(dispatch_proof_packet)
    surface_kind = _safe_text(handoff_surface_kind, limit=80)
    surface_allowed = surface_kind in APPROVED_HANDOFF_SURFACES
    surface_supports_observed_delivery = surface_kind == HANDOFF_SURFACE_MCP_TOOL_RESPONSE
    dispatch_failures = _dispatch_proof_failures(source)
    unsafe_failures = _unsafe_dispatch_claim_failures(source)

    normalized_dispatch = _normalized_controlled_dispatch_packet(source)
    approved_packet: Mapping[str, Any] = {}
    delivery_packet: Mapping[str, Any] = {}
    handoff_payload: Mapping[str, Any] = {}
    if not dispatch_failures and not unsafe_failures and surface_allowed:
        approved_packet = build_approved_handoff_packet(
            normalized_dispatch,
            handoff_surface_kind=surface_kind,
            secret_values=secret_values,
        )
        handoff_payload = _safe_handoff_payload(normalized_dispatch, surface_kind)
        if approved_packet.get("status") == "ok" and surface_supports_observed_delivery:
            delivery_packet = build_observed_machine_handoff_delivery_packet(
                approved_packet,
                handoff_payload=handoff_payload,
                delivery_surface_kind=DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
                delivery_surface_observed=handoff_surface_observed,
                secret_values=secret_values,
            )

    blocking_reasons: list[str] = []
    blocking_reasons.extend(dispatch_failures)
    blocking_reasons.extend(unsafe_failures)
    if not surface_allowed:
        blocking_reasons.append("handoff_surface_not_allowed")
    elif not surface_supports_observed_delivery:
        blocking_reasons.append("handoff_surface_does_not_support_observed_delivery")
    blocking_reasons.extend(
        str(reason) for reason in approved_packet.get("blocking_reasons", [])
    )
    blocking_reasons.extend(
        str(reason) for reason in delivery_packet.get("blocking_reasons", [])
    )
    blocking_reasons = sorted(set(blocking_reasons))

    ok = bool(
        not blocking_reasons
        and approved_packet.get("status") == "ok"
        and delivery_packet.get("status") == "ok"
        and delivery_packet.get("handoff_delivered") is True
        and delivery_packet.get("delivery_observed") is True
    )
    if ok:
        machine_error_code = "OK"
    elif dispatch_failures:
        machine_error_code = CONTROLLED_DISPATCH_HANDOFF_DISPATCH_PROOF_INVALID
    elif unsafe_failures:
        machine_error_code = CONTROLLED_DISPATCH_HANDOFF_PAYLOAD_UNSAFE
    elif not surface_allowed:
        machine_error_code = CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_ALLOWED
    elif not surface_supports_observed_delivery:
        machine_error_code = CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_SUPPORTED
    else:
        machine_error_code = CONTROLLED_DISPATCH_HANDOFF_NOT_OBSERVED

    metadata = dict(file_metadata or {})
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
        "dispatch_proof_kind": _safe_text(source.get("packet_kind"), limit=80),
        "dispatch_proof_status": _safe_text(source.get("status"), limit=32),
        "dispatch_proof_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "dispatch_proof_valid": not dispatch_failures,
        "dispatch_proof_failures": dispatch_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "ingress_proven": source.get("ingress_proven") is True,
        "controlled_ingress_proven": source.get("controlled_ingress_proven") is True,
        "dispatch_proven": source.get("dispatch_proven") is True and ok,
        "source_dispatch_proven": source.get("dispatch_proven") is True,
        "api_lane_called": source.get("api_lane_called") is True and ok,
        "source_api_lane_called": source.get("api_lane_called") is True,
        "api_response_received": source.get("api_response_received") is True and ok,
        "source_api_response_received": source.get("api_response_received") is True,
        "response_bound_to_proof": source.get("response_bound_to_proof") is True and ok,
        "source_response_bound_to_proof": source.get("response_bound_to_proof") is True,
        "provider_like_response_only": source.get("provider_like_response_only") is True,
        "allowed_api_route_ids_enforced": (
            source.get("allowed_api_route_ids_enforced") is True
        ),
        "forbidden_stale_route_ids_enforced": (
            source.get("forbidden_stale_route_ids_enforced") is True
        ),
        "forbidden_stale_route_ids_count": int(
            source.get("forbidden_stale_route_ids_count") or 0
        ),
        "route_bound_dispatch_proven": source.get("route_bound_dispatch_proven") is True,
        "controlled_provider_response_proven": (
            source.get("controlled_provider_response_proven") is True
        ),
        "handoff_surface_kind": surface_kind,
        "handoff_surface_allowed": surface_allowed,
        "handoff_surface_supports_observed_delivery": (
            surface_supports_observed_delivery
        ),
        "approved_handoff_surface_used": approved_packet.get("handoff_surface_allowed")
        is True,
        "approved_handoff_packet_kind": _safe_text(
            approved_packet.get("packet_kind"),
            limit=80,
        ),
        "approved_handoff_ready": approved_packet.get("handoff_ready") is True,
        "approved_handoff_payload_sanitized": (
            approved_packet.get("handoff_payload_sanitized") is True
        ),
        "handoff_payload_digest": _hex_sha256(
            approved_packet.get("handoff_payload_sha256")
        ),
        "handoff_payload_prepared": approved_packet.get("handoff_payload_prepared")
        is True,
        "handoff_envelope_built": delivery_packet.get(
            "machine_response_envelope_observed"
        )
        is True,
        "handoff_observed": delivery_packet.get("delivery_observed") is True,
        "handoff_completed": delivery_packet.get("handoff_delivered") is True,
        "delivery_packet_kind": _safe_text(
            delivery_packet.get("packet_kind"),
            limit=80,
        ),
        "delivery_surface_kind": _safe_text(
            delivery_packet.get("delivery_surface_kind"),
            limit=80,
        ),
        "delivery_surface_allowed": delivery_packet.get("delivery_surface_allowed")
        is True,
        "machine_response_envelope_observed": delivery_packet.get(
            "machine_response_envelope_observed"
        )
        is True,
        "machine_response_envelope_sha256": _hex_sha256(
            delivery_packet.get("machine_response_envelope_sha256")
        ),
        "machine_response_structured_content_present": delivery_packet.get(
            "machine_response_structured_content_present"
        )
        is True,
        "machine_response_content_text_recorded": False,
        "machine_response_raw_recorded": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
        "does_not_prove_product_ready": True,
        "fallback_used": source.get("fallback_used") is True,
        "local_imitation_used": source.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": (
            source.get("native_codex_subagent_used_as_dip") is True
        ),
        "codex_native_subagent_used_as_dip": (
            source.get("native_codex_subagent_used_as_dip") is True
        ),
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
        "no_secret_exposed": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "browser_can_supply_handoff_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved controlled dispatch handoff through an approved observed surface."
            if ok
            else "WBP blocked controlled dispatch handoff before proof."
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


def run_controlled_dispatch_handoff_proof_command(
    *,
    dispatch_proof_file: str,
    handoff_surface_kind: str = HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
) -> dict[str, Any]:
    dispatch_path = Path(dispatch_proof_file).expanduser()
    dispatch_packet, metadata = _proof_file_metadata(dispatch_path)
    return build_controlled_dispatch_handoff_proof_packet(
        dispatch_packet,
        handoff_surface_kind=handoff_surface_kind,
        file_metadata=metadata,
    )
