# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import (
    CONTROLLED_API_DISPATCH_PACKET_KIND,
    build_controlled_api_dispatch_packet,
)
from .core import packets
from .custom_codex_ingress_proof import CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND
from .router_hook_entry import (
    HOOK_SURFACE_PROMPT_PREPROCESSOR,
    _safe_text,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND = (
    "wbp_controlled_ingress_api_dispatch_proof"
)

CONTROLLED_INGRESS_API_DISPATCH_INGRESS_NOT_PROVEN = (
    "WBP_CONTROLLED_INGRESS_API_DISPATCH_INGRESS_NOT_PROVEN"
)
CONTROLLED_INGRESS_API_DISPATCH_DIGEST_MISMATCH = (
    "WBP_CONTROLLED_INGRESS_API_DISPATCH_DIGEST_MISMATCH"
)
CONTROLLED_INGRESS_API_DISPATCH_NOT_PROVEN = (
    "WBP_CONTROLLED_INGRESS_API_DISPATCH_NOT_PROVEN"
)
CONTROLLED_INGRESS_API_DISPATCH_UNSAFE_SOURCE = (
    "WBP_CONTROLLED_INGRESS_API_DISPATCH_UNSAFE_SOURCE"
)

DISPATCH_STATUS_PROVEN = "proven"
DISPATCH_STATUS_BLOCKED = "blocked"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _route_secret_values(runtime_context: Mapping[str, Any] | None) -> list[str]:
    context = _mapping(runtime_context)
    values: list[str] = []
    allowed = context.get("allowed_api_route_ids")
    if isinstance(allowed, list):
        values.extend(str(route) for route in allowed if route)
    routes = context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        values.extend(str(route) for route in routes.values() if route)
    for binding in context.get("agent_bindings", []):
        if isinstance(binding, Mapping) and binding.get("route_id"):
            values.append(str(binding["route_id"]))
    return sorted(set(values))


def _ingress_file_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "ingress_proof_file_required": True,
        "ingress_proof_file_present": path.exists(),
        "ingress_proof_file_read": False,
        "ingress_proof_file_valid_json": False,
        "ingress_proof_file_mapping": False,
        "ingress_proof_file_error_code": "",
        "ingress_proof_file_path_recorded": False,
    }
    if not path.exists():
        metadata["ingress_proof_file_error_code"] = "ingress_proof_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["ingress_proof_file_error_code"] = "ingress_proof_file_invalid"
        return {}, metadata
    metadata["ingress_proof_file_read"] = True
    metadata["ingress_proof_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["ingress_proof_file_error_code"] = "ingress_proof_file_not_mapping"
        return {}, metadata
    metadata["ingress_proof_file_mapping"] = True
    return dict(parsed), metadata


def _unsafe_ingress_claim_failures(ingress: Mapping[str, Any]) -> list[str]:
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
        "api_lane_called": "ingress_must_not_claim_api_lane_called",
        "dispatch_proven": "ingress_must_not_claim_dispatch_proven",
        "native_free_chat_router_proven": (
            "ingress_must_not_claim_native_free_chat_router"
        ),
        "product_ready": "ingress_must_not_claim_product_ready",
        "command_origin_proven": "ingress_must_not_claim_command_origin",
        "custom_codex_origin_proven": "ingress_must_not_claim_custom_codex_origin",
        "native_custom_codex_flow_proven": (
            "ingress_must_not_claim_native_custom_codex_flow"
        ),
        "native_router_hook_observed": "ingress_must_not_claim_native_router_hook",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "codex_native_subagent_used_as_dip": "codex_native_subagent_used_as_dip",
        "local_codex_subagent_used_as_dip": "codex_native_subagent_used_as_dip",
        "native_codex_subagent_used_as_dip": "codex_native_subagent_used_as_dip",
    }
    return sorted(
        {reason for field, reason in checks.items() if ingress.get(field) is True}
    )


def _ingress_failures(ingress: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if ingress.get("packet_kind") != CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND:
        failures.append("ingress_proof_packet_kind_invalid")
    if ingress.get("status") != "ok":
        failures.append("ingress_proof_packet_not_ok")
    if ingress.get("machine_error_code") != "OK":
        failures.append("ingress_proof_machine_error_not_ok")
    if ingress.get("ingress_proven") is not True:
        failures.append("ingress_not_proven")
    if ingress.get("controlled_ingress_proven") is not True:
        failures.append("controlled_ingress_not_proven")
    if ingress.get("prompt_digest_bound_to_ingress") is not True:
        failures.append("prompt_digest_not_bound_to_ingress")
    if ingress.get("alias_context_read") is not True:
        failures.append("alias_context_not_read")
    if ingress.get("alias_bound") is not True:
        failures.append("alias_not_bound")
    if ingress.get("route_id_allowed") is not True:
        failures.append("ingress_route_id_not_allowed")
    if ingress.get("allowed_api_route_ids_enforced") is not True:
        failures.append("ingress_allowed_api_route_ids_not_enforced")
    if int(ingress.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("ingress_stale_route_guard_missing")
    if not _hex_sha256(ingress.get("prompt_digest")):
        failures.append("ingress_prompt_digest_missing")
    if not _safe_text(ingress.get("alias_candidate"), limit=80):
        failures.append("ingress_alias_missing")
    if not _safe_text(ingress.get("slot_candidate"), limit=80):
        failures.append("ingress_slot_missing")
    if ingress.get("dispatch_status") != "not_attempted":
        failures.append("ingress_dispatch_status_not_not_attempted")
    failures.extend(_unsafe_ingress_claim_failures(ingress))
    return sorted(set(failures))


def _dispatch_failures(dispatch: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch.get("packet_kind") != CONTROLLED_API_DISPATCH_PACKET_KIND:
        failures.append("controlled_dispatch_packet_kind_invalid")
    if dispatch.get("status") != "ok":
        failures.append("controlled_dispatch_packet_not_ok")
    if dispatch.get("dispatch_proven") is not True:
        failures.append("controlled_dispatch_not_proven")
    if dispatch.get("dispatch_status") != DISPATCH_STATUS_PROVEN:
        failures.append("controlled_dispatch_status_not_proven")
    if dispatch.get("api_lane_called") is not True:
        failures.append("api_lane_not_called")
    if dispatch.get("route_bound_dispatch_proven") is not True:
        failures.append("route_bound_dispatch_not_proven")
    if int(dispatch.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("stale_route_guard_missing")
    if dispatch.get("provider_response_proven") is not True:
        failures.append("api_response_not_proven")
    if dispatch.get("controlled_provider_response_proven") is not True:
        failures.append("controlled_provider_response_not_proven")
    if dispatch.get("fallback_used") is True:
        failures.append("fallback_used")
    if dispatch.get("local_imitation_used") is True:
        failures.append("local_imitation_used")
    if dispatch.get("native_codex_subagent_used_as_dip") is True:
        failures.append("codex_native_subagent_used_as_dip")
    if dispatch.get("raw_prompt_recorded") is True:
        failures.append("raw_prompt_recorded")
    if dispatch.get("prompt_text_recorded") is True:
        failures.append("prompt_text_recorded")
    if dispatch.get("raw_provider_response_recorded") is True:
        failures.append("raw_provider_response_recorded")
    if dispatch.get("provider_response_text_recorded") is True:
        failures.append("provider_response_text_recorded")
    if dispatch.get("raw_backend_details_exposed") is True:
        failures.append("raw_backend_details_exposed")
    if dispatch.get("secret_value_exposed") is True:
        failures.append("secret_value_exposed")
    if dispatch.get("product_ready") is True:
        failures.append("product_ready_must_not_be_claimed")
    if dispatch.get("native_free_chat_router_proven") is True:
        failures.append("native_free_chat_router_must_not_be_claimed")
    return sorted(set(failures))


def build_controlled_ingress_api_dispatch_proof_packet(
    *,
    ingress_proof_packet: Mapping[str, Any] | None,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None = None,
    hook_surface_kind: str = HOOK_SURFACE_PROMPT_PREPROCESSOR,
    ingress_file_metadata: Mapping[str, Any] | None = None,
    runtime_context_file_metadata: Mapping[str, Any] | None = None,
    api_lane_adapter_available: bool = True,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    ingress = _mapping(ingress_proof_packet)
    context = _mapping(runtime_context)
    prompt = str(prompt_text or "")
    prompt_digest = _sha256_text(prompt) if prompt else ""
    ingress_prompt_digest = _hex_sha256(ingress.get("prompt_digest"))
    prompt_digest_bound_to_ingress_proof = bool(
        prompt_digest and ingress_prompt_digest and prompt_digest == ingress_prompt_digest
    )

    ingress_failures = _ingress_failures(ingress)
    blocking_reasons: list[str] = list(ingress_failures)
    if not prompt:
        blocking_reasons.append("prompt_required")
    if not prompt_digest_bound_to_ingress_proof:
        blocking_reasons.append("prompt_digest_mismatch")

    dispatch_packet: Mapping[str, Any] = {}
    preliminary_ok = not blocking_reasons
    if preliminary_ok:
        dispatch_packet = build_controlled_api_dispatch_packet(
            prompt_text=prompt,
            runtime_context=context,
            hook_surface_kind=hook_surface_kind,
            context_file_metadata=runtime_context_file_metadata,
            api_lane_adapter_available=api_lane_adapter_available,
            controlled_provider_available=controlled_provider_available,
            controlled_provider_error_code=controlled_provider_error_code,
            secret_values=[
                prompt,
                *list(secret_values or []),
                *_route_secret_values(context),
            ],
        )
        dispatch_failures = _dispatch_failures(dispatch_packet)
        blocking_reasons.extend(dispatch_failures)
        blocking_reasons.extend(
            str(reason) for reason in dispatch_packet.get("blocking_reasons", [])
        )

    blocking_reasons = sorted(set(blocking_reasons))
    ok = not blocking_reasons
    unsafe_failures = _unsafe_ingress_claim_failures(ingress)
    if ok:
        machine_error_code = "OK"
    elif unsafe_failures:
        machine_error_code = CONTROLLED_INGRESS_API_DISPATCH_UNSAFE_SOURCE
    elif ingress_failures:
        machine_error_code = CONTROLLED_INGRESS_API_DISPATCH_INGRESS_NOT_PROVEN
    elif not prompt_digest_bound_to_ingress_proof:
        machine_error_code = CONTROLLED_INGRESS_API_DISPATCH_DIGEST_MISMATCH
    elif dispatch_packet.get("machine_error_code"):
        machine_error_code = _safe_text(dispatch_packet["machine_error_code"], limit=96)
    else:
        machine_error_code = CONTROLLED_INGRESS_API_DISPATCH_NOT_PROVEN

    api_lane_called = dispatch_packet.get("api_lane_called") is True
    api_response_received = dispatch_packet.get("provider_response_proven") is True
    response_bound_to_proof = bool(
        ok
        and prompt_digest_bound_to_ingress_proof
        and dispatch_packet.get("route_bound_request_sha256")
        and dispatch_packet.get("provider_response_digest")
    )
    alias = _safe_text(ingress.get("alias_candidate"), limit=80)
    slot = _safe_text(ingress.get("slot_candidate"), limit=80)
    selected_alias = _safe_text(dispatch_packet.get("selected_alias"), limit=80)
    selected_slot = _safe_text(dispatch_packet.get("selected_slot"), limit=80)
    alias_matches_dispatch = bool(ok and alias and selected_alias and alias == selected_alias)
    slot_matches_dispatch = bool(ok and slot and selected_slot and slot == selected_slot)
    metadata = {
        **dict(ingress_file_metadata or {}),
        **dict(runtime_context_file_metadata or {}),
    }
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND,
        "ingress_proof_kind": _safe_text(ingress.get("packet_kind"), limit=80),
        "ingress_status": _safe_text(ingress.get("status"), limit=80),
        "ingress_machine_error_code": _safe_text(
            ingress.get("machine_error_code"),
            limit=96,
        ),
        "ingress_proven": ingress.get("ingress_proven") is True,
        "controlled_ingress_proven": ingress.get("controlled_ingress_proven") is True,
        "prompt_digest": prompt_digest if prompt_digest_bound_to_ingress_proof else "",
        "prompt_digest_present": bool(prompt_digest),
        "ingress_prompt_digest_present": bool(ingress_prompt_digest),
        "prompt_digest_bound_to_ingress_proof": (
            prompt_digest_bound_to_ingress_proof
        ),
        "prompt_digest_bound_to_dispatch": bool(
            ok and dispatch_packet.get("prompt_digest") == prompt_digest
        ),
        "prompt_digest_bound_to_proof": response_bound_to_proof,
        "alias": alias,
        "alias_candidate": alias,
        "selected_alias": selected_alias,
        "alias_matches_dispatch": alias_matches_dispatch,
        "slot": slot,
        "slot_candidate": slot,
        "selected_slot": selected_slot,
        "slot_matches_dispatch": slot_matches_dispatch,
        "alias_context_read": bool(
            ingress.get("alias_context_read") is True
            and dispatch_packet.get("alias_context_read") is True
        ),
        "alias_bound": bool(
            ingress.get("alias_bound") is True
            and dispatch_packet.get("selected_alias") == alias
        ),
        "route_id_allowed": dispatch_packet.get("route_id_allowed") is True,
        "ingress_route_id_allowed": ingress.get("route_id_allowed") is True,
        "ingress_forbidden_stale_route_ids_enforced": int(
            ingress.get("forbidden_stale_route_ids_count") or 0
        )
        > 0,
        "ingress_forbidden_stale_route_ids_count": int(
            ingress.get("forbidden_stale_route_ids_count") or 0
        ),
        "allowed_api_route_ids_enforced": (
            dispatch_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "forbidden_stale_route_ids_enforced": int(
            dispatch_packet.get("forbidden_stale_route_ids_count") or 0
        )
        > 0,
        "forbidden_stale_route_ids_count": int(
            dispatch_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "api_lane_called": api_lane_called,
        "api_lane_adapter_called": dispatch_packet.get("api_lane_adapter_called") is True,
        "api_lane_dispatch_admitted": (
            dispatch_packet.get("api_lane_dispatch_admitted") is True
        ),
        "api_response_received": api_response_received,
        "provider_response_proven": api_response_received,
        "controlled_provider_called": (
            dispatch_packet.get("controlled_provider_called") is True
        ),
        "controlled_provider_response_proven": (
            dispatch_packet.get("controlled_provider_response_proven") is True
        ),
        "response_bound_to_proof": response_bound_to_proof,
        "dispatch_proven": ok,
        "dispatch_status": DISPATCH_STATUS_PROVEN if ok else DISPATCH_STATUS_BLOCKED,
        "controlled_dispatch_packet_kind": _safe_text(
            dispatch_packet.get("packet_kind"),
            limit=80,
        ),
        "controlled_dispatch_status": _safe_text(
            dispatch_packet.get("status"),
            limit=80,
        ),
        "controlled_dispatch_machine_error_code": _safe_text(
            dispatch_packet.get("machine_error_code"),
            limit=96,
        ),
        "route_bound_dispatch_attempted": (
            dispatch_packet.get("route_bound_dispatch_attempted") is True
        ),
        "route_bound_dispatch_proven": (
            dispatch_packet.get("route_bound_dispatch_proven") is True
        ),
        "route_bound_request_sent": (
            dispatch_packet.get("route_bound_request_sent") is True
        ),
        "route_bound_request_sha256": _safe_text(
            dispatch_packet.get("route_bound_request_sha256"),
            limit=80,
        ),
        "selected_api_route_id_present": (
            dispatch_packet.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": _safe_text(
            dispatch_packet.get("selected_api_route_id_sha256"),
            limit=80,
        ),
        "provider_response_digest": _safe_text(
            dispatch_packet.get("provider_response_digest"),
            limit=80,
        ),
        "controlled_provider_response_sha256": _safe_text(
            dispatch_packet.get("controlled_provider_response_sha256"),
            limit=80,
        ),
        "approved_api_lane_truth_source": _safe_text(
            dispatch_packet.get("api_lane_truth_source") or "not_proven",
            limit=80,
        ),
        "dispatch_truth_source": _safe_text(
            dispatch_packet.get("dispatch_truth_source") or "not_proven",
            limit=80,
        ),
        "provider_like_response_only": dispatch_packet.get(
            "provider_like_response_only"
        )
        is True,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "live_provider_status": "not_attempted",
        "network_dependent": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "does_not_prove_live_provider": True,
        "fallback_used": dispatch_packet.get("fallback_used") is True,
        "local_imitation_used": dispatch_packet.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": (
            dispatch_packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "codex_native_subagent_used_as_dip": (
            dispatch_packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "blocking_reasons": blocking_reasons,
        "ingress_blocking_reasons": ingress_failures,
        "source_unsafe_claim_failures": unsafe_failures,
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
        "browser_can_supply_route_authority": False,
        "browser_can_supply_prompt_authority": False,
        "browser_can_supply_ingress_authority": False,
        "changed_files": [],
    }
    all_secret_values = [
        prompt,
        *list(secret_values or []),
        *_route_secret_values(context),
    ]
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved API dispatch from a positive controlled ingress proof."
            if ok
            else "WBP blocked API dispatch from controlled ingress before proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=all_secret_values,
        extra=extra,
    )


def run_controlled_ingress_api_dispatch_proof_command(
    *,
    paths: RuntimePaths,
    ingress_proof_file: str,
    prompt_text: object,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_PROMPT_PREPROCESSOR,
) -> dict[str, Any]:
    ingress_path = Path(ingress_proof_file).expanduser()
    ingress_packet, ingress_metadata = _ingress_file_metadata(ingress_path)
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    return build_controlled_ingress_api_dispatch_proof_packet(
        ingress_proof_packet=ingress_packet,
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        hook_surface_kind=hook_surface_kind,
        ingress_file_metadata=ingress_metadata,
        runtime_context_file_metadata=context_metadata,
    )
