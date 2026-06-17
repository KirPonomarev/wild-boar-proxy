# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .mcp_delegate import (
    build_api_lane_adapter_admission_packet,
    build_route_bound_controlled_dispatch_packet,
)
from .router_hook_entry import (
    HOOK_SURFACE_FILE_BRIDGE,
    HOOK_SURFACE_LAUNCHER_OWNED_BRIDGE,
    HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    HOOK_SURFACE_PROMPT_PREPROCESSOR,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


CONTROLLED_API_DISPATCH_PACKET_KIND = "wbp_controlled_api_dispatch_proof"

CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN = (
    "WBP_CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN"
)

DISPATCH_STATUS_PROVEN = "proven"
DISPATCH_STATUS_BLOCKED = "blocked"
LIVE_PROVIDER_STATUS_NOT_ATTEMPTED = "not_attempted"
BRIDGE_BACKED_HOOK_SURFACES = frozenset(
    {
        HOOK_SURFACE_FILE_BRIDGE,
        HOOK_SURFACE_LAUNCHER_OWNED_BRIDGE,
        HOOK_SURFACE_PROMPT_PREPROCESSOR,
    }
)


def build_controlled_api_dispatch_packet(
    *,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    context_file_metadata: Mapping[str, Any] | None = None,
    api_lane_adapter_available: bool = True,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    hook_packet = build_router_hook_entry_packet(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        hook_surface_kind=hook_surface_kind,
        context_file_metadata=context_file_metadata,
        secret_values=secret_values,
    )
    hook_entry_proven = bool(
        hook_packet.get("status") == "ok"
        and hook_packet.get("hook_entry_proven") is True
        and hook_packet.get("route_id_allowed") is True
    )
    route_id = _safe_text(hook_packet.get("route_candidate"), limit=80)
    slot = _safe_text(hook_packet.get("slot_candidate"), limit=64)
    alias = _safe_text(hook_packet.get("alias_candidate"), limit=80)
    lane = _safe_text(hook_packet.get("lane_candidate"), limit=32)
    admission_packet: Mapping[str, Any] = {}
    dispatch_packet: Mapping[str, Any] = {}
    if hook_entry_proven:
        admission_packet = build_api_lane_adapter_admission_packet(
            task=str(prompt_text or ""),
            selected_alias=alias,
            selected_alias_lane=lane,
            route_id=route_id,
            allowed_api_route_ids_enforced=(
                hook_packet.get("allowed_api_route_ids_enforced") is True
            ),
            route_allowed=hook_packet.get("route_id_allowed") is True,
            adapter_available=api_lane_adapter_available,
        )
        if admission_packet.get("status") == "ok":
            dispatch_packet = build_route_bound_controlled_dispatch_packet(
                task=str(prompt_text or ""),
                selected_alias=alias,
                selected_alias_lane=lane,
                route_id=route_id,
                admission_packet=admission_packet,
                controlled_provider_available=controlled_provider_available,
                controlled_provider_error_code=controlled_provider_error_code,
            )

    api_lane_adapter_called = admission_packet.get("api_lane_adapter_called") is True
    api_lane_dispatch_admitted = (
        admission_packet.get("api_lane_dispatch_admitted") is True
    )
    route_bound_dispatch_attempted = (
        dispatch_packet.get("route_bound_dispatch_attempted") is True
    )
    route_bound_dispatch_proven = (
        dispatch_packet.get("route_bound_dispatch_proven") is True
    )
    controlled_provider_called = (
        dispatch_packet.get("controlled_provider_called") is True
    )
    controlled_provider_response_proven = (
        dispatch_packet.get("controlled_provider_response_proven") is True
    )
    provider_response_proven = dispatch_packet.get("provider_response_proven") is True
    fallback_used = bool(
        hook_packet.get("fallback_used") is True
        or admission_packet.get("fallback_used") is True
        or dispatch_packet.get("fallback_used") is True
    )
    local_imitation_used = bool(
        hook_packet.get("local_imitation_used") is True
        or admission_packet.get("local_imitation_used") is True
        or dispatch_packet.get("local_imitation_used") is True
    )
    native_codex_subagent_used = bool(
        hook_packet.get("native_codex_subagent_used") is True
        or dispatch_packet.get("native_codex_subagent_used") is True
    )
    raw_backend_details_exposed = bool(
        hook_packet.get("raw_backend_details_exposed") is True
        or admission_packet.get("raw_backend_details_exposed") is True
        or dispatch_packet.get("raw_backend_details_exposed") is True
    )
    secret_value_exposed = bool(
        hook_packet.get("secret_value_exposed") is True
        or admission_packet.get("secret_value_exposed") is True
        or dispatch_packet.get("secret_value_exposed") is True
    )
    ok = bool(
        hook_entry_proven
        and api_lane_adapter_called
        and api_lane_dispatch_admitted
        and route_bound_dispatch_attempted
        and route_bound_dispatch_proven
        and controlled_provider_called
        and controlled_provider_response_proven
        and provider_response_proven
        and not fallback_used
        and not local_imitation_used
        and not native_codex_subagent_used
        and not raw_backend_details_exposed
        and not secret_value_exposed
    )
    if ok:
        machine_error_code = "OK"
    elif not hook_entry_proven:
        machine_error_code = CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN
    elif (
        admission_packet.get("machine_error_code")
        and admission_packet.get("machine_error_code") != "OK"
    ):
        machine_error_code = str(admission_packet["machine_error_code"])
    elif dispatch_packet.get("machine_error_code"):
        machine_error_code = str(dispatch_packet["machine_error_code"])
    else:
        machine_error_code = CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN

    blocking_reasons = []
    if not hook_entry_proven:
        blocking_reasons.append(
            str(
                hook_packet.get("machine_error_code")
                or CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN
            )
        )
        blocking_reasons.extend(
            str(reason) for reason in hook_packet.get("blocking_reasons", [])
        )
    blocking_reasons.extend(
        str(reason) for reason in admission_packet.get("blocking_reasons", [])
    )
    blocking_reasons.extend(
        str(reason) for reason in dispatch_packet.get("blocking_reasons", [])
    )
    hook_surface_kind = _safe_text(hook_packet.get("hook_surface_kind"), limit=80)
    bridge_backed_hook_surface = hook_surface_kind in BRIDGE_BACKED_HOOK_SURFACES
    api_lane_truth_source = (
        "server_owned_controlled_route_bound_dispatch"
        if route_bound_dispatch_proven
        else "not_proven"
    )
    extra = {
        "schema_version": 1,
        "packet_kind": CONTROLLED_API_DISPATCH_PACKET_KIND,
        "hook_entry_packet_kind": hook_packet.get("packet_kind", ""),
        "hook_entry_status": hook_packet.get("status", ""),
        "hook_entry_machine_error_code": hook_packet.get("machine_error_code", ""),
        "hook_entry_proven": hook_entry_proven,
        "hook_surface_kind": hook_surface_kind,
        "hook_surface_admitted": hook_packet.get("hook_surface_admitted") is True,
        "bridge_backed_hook_surface": bridge_backed_hook_surface,
        "parser_packet_kind": _safe_text(hook_packet.get("parser_packet_kind"), limit=80),
        "parser_packet_status": _safe_text(hook_packet.get("parser_packet_status"), limit=80),
        "parser_machine_error_code": _safe_text(
            hook_packet.get("parser_machine_error_code"),
            limit=96,
        ),
        "prompt_digest": _safe_text(hook_packet.get("prompt_digest"), limit=80),
        "prompt_digest_present": hook_packet.get("prompt_digest_present") is True,
        "alias_context_read": hook_packet.get("alias_context_read") is True,
        "runtime_context_source": _safe_text(
            hook_packet.get("runtime_context_source"),
            limit=80,
        ),
        "runtime_context_present": hook_packet.get("runtime_context_present") is True,
        "runtime_context_kind_valid": (
            hook_packet.get("runtime_context_kind_valid") is True
        ),
        "runtime_context_file_required": True,
        "runtime_context_file_present": (
            hook_packet.get("runtime_context_file_present") is True
        ),
        "runtime_context_file_read": (
            hook_packet.get("runtime_context_file_read") is True
        ),
        "runtime_context_file_path_recorded": False,
        "source_surface": _safe_text(hook_packet.get("source_surface"), limit=80),
        "source_surface_allowed": hook_packet.get("source_surface_allowed") is True,
        "source_surface_observed": False,
        "alias_candidate": alias,
        "alias_bound": hook_packet.get("alias_bound") is True,
        "slot_candidate": slot,
        "lane_candidate": lane,
        "route_candidate_present": hook_packet.get("route_candidate_present") is True,
        "route_candidate_recorded": False,
        "route_id_allowed": hook_packet.get("route_id_allowed") is True,
        "route_allowed": hook_packet.get("route_id_allowed") is True,
        "allowed_api_route_ids_enforced": (
            hook_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_count": int(
            hook_packet.get("allowed_api_route_ids_count") or 0
        ),
        "forbidden_stale_route_ids_count": int(
            hook_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "blocking_reasons": blocking_reasons,
        "dispatch_status": DISPATCH_STATUS_PROVEN if ok else DISPATCH_STATUS_BLOCKED,
        "dispatch_attempted": route_bound_dispatch_attempted,
        "dispatch_proven": ok,
        "api_lane_called": api_lane_dispatch_admitted,
        "api_lane_adapter_called": api_lane_adapter_called,
        "controlled_api_lane_adapter_called": api_lane_adapter_called,
        "api_lane_dispatch_admitted": api_lane_dispatch_admitted,
        "api_lane_adapter_packet_kind": _safe_text(
            admission_packet.get("packet_kind"),
            limit=80,
        ),
        "api_lane_adapter_result_status": _safe_text(
            admission_packet.get("result_status"),
            limit=80,
        ),
        "api_lane_adapter_machine_error_code": _safe_text(
            admission_packet.get("machine_error_code"),
            limit=96,
        ),
        "route_bound_dispatch_packet_kind": _safe_text(
            dispatch_packet.get("packet_kind"),
            limit=80,
        ),
        "route_bound_dispatch_result_status": _safe_text(
            dispatch_packet.get("result_status"),
            limit=80,
        ),
        "route_bound_dispatch_machine_error_code": _safe_text(
            dispatch_packet.get("machine_error_code"),
            limit=96,
        ),
        "route_bound_dispatch_attempted": route_bound_dispatch_attempted,
        "route_bound_dispatch_proven": route_bound_dispatch_proven,
        "route_bound_request_sent": (
            dispatch_packet.get("route_bound_request_sent") is True
        ),
        "route_bound_request_sha256": _safe_text(
            dispatch_packet.get("route_bound_request_sha256"),
            limit=80,
        ),
        "dispatch_truth_source": _safe_text(
            dispatch_packet.get("dispatch_truth_source") or "not_proven",
            limit=80,
        ),
        "api_lane_truth_source": api_lane_truth_source,
        "api_lane_provider_called": controlled_provider_called,
        "controlled_provider_called": controlled_provider_called,
        "controlled_provider_available": (
            dispatch_packet.get("controlled_provider_available") is True
        ),
        "controlled_provider_error_observed": (
            dispatch_packet.get("controlled_provider_error_observed") is True
        ),
        "controlled_provider_error_code_recorded": (
            dispatch_packet.get("controlled_provider_error_code_recorded") is True
        ),
        "controlled_provider_response_digest_present": (
            dispatch_packet.get("controlled_provider_response_digest_present") is True
        ),
        "controlled_provider_response_sha256": _safe_text(
            dispatch_packet.get("controlled_provider_response_sha256"),
            limit=80,
        ),
        "controlled_provider_response_proven": controlled_provider_response_proven,
        "provider_response_proven": provider_response_proven,
        "bridge_backed_provider_proof": bool(ok and bridge_backed_hook_surface),
        "bridge_backed_provider_response_proven": bool(ok and bridge_backed_hook_surface),
        "local_proof_command_dispatch_proven": bool(
            ok and hook_surface_kind == HOOK_SURFACE_LOCAL_PROOF_COMMAND
        ),
        "provider_like_response_only": True,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "live_provider_status": LIVE_PROVIDER_STATUS_NOT_ATTEMPTED,
        "network_dependent": False,
        "route_authority_source": "runtime_context",
        "selected_alias": alias,
        "selected_alias_lane": lane,
        "selected_slot": slot,
        "selected_api_route_id_present": bool(route_id),
        "selected_api_route_id_sha256": _safe_text(
            dispatch_packet.get("selected_api_route_id_sha256")
            or admission_packet.get("selected_api_route_id_sha256"),
            limit=80,
        ),
        "selected_api_route_id_recorded": False,
        "selected_route_id_allowed": hook_packet.get("route_id_allowed") is True,
        "expected_text_digest": "",
        "expected_text_present": False,
        "expected_text_recorded": False,
        "raw_expected_text_recorded": False,
        "provider_response_received": controlled_provider_response_proven,
        "provider_response_matched_expected": False,
        "provider_response_digest": _safe_text(
            dispatch_packet.get("controlled_provider_response_sha256"),
            limit=80,
        ),
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_raw_recorded": False,
        "fallback_used": fallback_used,
        "local_imitation_used": local_imitation_used,
        "native_codex_subagent_used": native_codex_subagent_used,
        "native_codex_subagent_used_as_dip": native_codex_subagent_used,
        "native_codex_subagent_not_used_as_dip": not native_codex_subagent_used,
        "custom_codex_origin_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
        "command_origin_proven": False,
        "product_ready": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
        "does_not_prove_product_ready": True,
        "browser_can_supply_route_authority": False,
        "browser_can_supply_prompt_authority": False,
        "browser_can_supply_expected_text_authority": False,
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "natural_phrase_recorded": False,
        "raw_backend_details_exposed": raw_backend_details_exposed,
        "secret_value_exposed": secret_value_exposed,
        "no_secret_exposed": not secret_value_exposed,
        "model_reasoning_claimed": False,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "changed_files": [],
    }
    packet_secret_values = list(secret_values or [])
    if route_id:
        packet_secret_values.append(route_id)
    prompt_for_redaction = str(prompt_text or "")
    if prompt_for_redaction:
        packet_secret_values.append(prompt_for_redaction)
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP controlled API dispatch proof observed a route-bound bridge-backed response."
            if ok
            else "WBP controlled API dispatch proof blocked before proven dispatch."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=packet_secret_values,
        extra=extra,
    )


def run_controlled_api_dispatch_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    context, metadata = load_runtime_context_packet(context_path)
    return build_controlled_api_dispatch_packet(
        prompt_text=prompt_text,
        runtime_context=context,
        hook_surface_kind=hook_surface_kind,
        context_file_metadata=metadata,
    )
