# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from typing import Any

from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import (
    CONTROLLED_API_DISPATCH_PACKET_KIND,
    DISPATCH_STATUS_PROVEN,
    build_controlled_api_dispatch_packet,
)
from .core import packets
from .real_user_prompt_submit_ledger_proof import (
    REAL_USER_PROMPT_SUBMIT_LEDGER_OK,
    REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
    run_real_user_prompt_submit_ledger_proof_command,
)
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND = (
    "wbp_real_ledger_bound_api_dispatch_proof"
)

REAL_LEDGER_BOUND_API_DISPATCH_OK = "OK"
REAL_LEDGER_BOUND_API_DISPATCH_LEDGER_NOT_PROVEN = (
    "WBP_REAL_LEDGER_BOUND_API_DISPATCH_LEDGER_NOT_PROVEN"
)
REAL_LEDGER_BOUND_API_DISPATCH_DIGEST_MISMATCH = (
    "WBP_REAL_LEDGER_BOUND_API_DISPATCH_DIGEST_MISMATCH"
)
REAL_LEDGER_BOUND_API_DISPATCH_NOT_PROVEN = (
    "WBP_REAL_LEDGER_BOUND_API_DISPATCH_NOT_PROVEN"
)
REAL_LEDGER_BOUND_API_DISPATCH_UNSAFE_SOURCE = (
    "WBP_REAL_LEDGER_BOUND_API_DISPATCH_UNSAFE_SOURCE"
)

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
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        values.extend(str(route) for route in allowed if route)
    routes = context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        values.extend(str(route) for route in routes.values() if route)
    bindings = context.get("agent_bindings")
    if isinstance(bindings, Sequence) and not isinstance(bindings, (str, bytes)):
        for binding in bindings:
            if isinstance(binding, Mapping) and binding.get("route_id"):
                values.append(str(binding["route_id"]))
    return sorted(set(values))


def _ledger_proof_required_failures(ledger_proof: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if ledger_proof.get("packet_kind") != REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND:
        failures.append("ledger_proof_packet_kind_invalid")
    if ledger_proof.get("status") != "ok":
        failures.append("ledger_proof_packet_not_ok")
    if ledger_proof.get("machine_error_code") != REAL_USER_PROMPT_SUBMIT_LEDGER_OK:
        failures.append("ledger_proof_machine_error_not_ok")
    for field, reason in (
        ("real_user_prompt_submit_ledger_proven", "real_ledger_not_proven"),
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
        ("hook_ledger_file_profile_owned", "hook_ledger_not_profile_owned"),
        ("codex_hook_trusted_by_profile_state", "codex_hook_trust_state_not_proven"),
    ):
        if ledger_proof.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(ledger_proof.get("prompt_digest")):
        failures.append("ledger_prompt_digest_missing")
    if ledger_proof.get("dispatch_status") != "not_attempted":
        failures.append("ledger_dispatch_status_not_not_attempted")
    return sorted(set(failures))


def _unsafe_ledger_proof_claim_failures(
    ledger_proof: Mapping[str, Any],
) -> list[str]:
    checks = {
        "api_lane_called": "ledger_must_not_claim_api_lane_called",
        "api_response_received": "ledger_must_not_claim_api_response_received",
        "dispatch_attempted": "ledger_must_not_claim_dispatch_attempted",
        "dispatch_proven": "ledger_must_not_claim_dispatch_proven",
        "handoff_file_written": "ledger_must_not_claim_handoff_file_written",
        "handoff_delivered": "ledger_must_not_claim_handoff_delivered",
        "custom_codex_ui_visibility_proven": (
            "ledger_must_not_claim_custom_codex_ui_visibility"
        ),
        "codex_working_flow_delivery_proven": (
            "ledger_must_not_claim_codex_working_flow_delivery"
        ),
        "native_free_chat_router_proven": (
            "ledger_must_not_claim_native_free_chat_router"
        ),
        "native_free_chat_router_product_ready": (
            "ledger_must_not_claim_native_free_chat_router_product_ready"
        ),
        "live_provider_proven": "ledger_must_not_claim_live_provider",
        "product_ready": "ledger_must_not_claim_product_ready",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "raw_prompt_recorded": "raw_prompt_recorded",
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
        "state_written": "state_written",
        "evidence_written": "evidence_written",
        "file_mutation_attempted": "file_mutation_attempted",
    }
    return sorted(
        {reason for field, reason in checks.items() if ledger_proof.get(field) is True}
    )


def _controlled_dispatch_failures(dispatch: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch.get("packet_kind") != CONTROLLED_API_DISPATCH_PACKET_KIND:
        failures.append("controlled_dispatch_packet_kind_invalid")
    if dispatch.get("status") != "ok":
        failures.append("controlled_dispatch_packet_not_ok")
    if dispatch.get("hook_entry_proven") is not True:
        failures.append("dispatch_hook_entry_not_proven")
    if dispatch.get("alias_context_read") is not True:
        failures.append("alias_context_not_read")
    if dispatch.get("alias_bound") is not True:
        failures.append("alias_not_bound")
    if dispatch.get("route_id_allowed") is not True:
        failures.append("route_id_not_allowed")
    if dispatch.get("allowed_api_route_ids_enforced") is not True:
        failures.append("allowed_api_route_ids_not_enforced")
    if int(dispatch.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("stale_route_guard_missing")
    if dispatch.get("api_lane_called") is not True:
        failures.append("api_lane_not_called")
    if dispatch.get("api_lane_dispatch_admitted") is not True:
        failures.append("api_lane_dispatch_not_admitted")
    if dispatch.get("api_lane_provider_called") is not True:
        failures.append("api_lane_provider_not_called")
    if dispatch.get("route_bound_dispatch_proven") is not True:
        failures.append("route_bound_dispatch_not_proven")
    if dispatch.get("provider_response_proven") is not True:
        failures.append("api_response_not_proven")
    if dispatch.get("controlled_provider_response_proven") is not True:
        failures.append("controlled_provider_response_not_proven")
    if dispatch.get("fallback_used") is True:
        failures.append("fallback_used")
    if dispatch.get("local_imitation_used") is True:
        failures.append("local_imitation_used")
    if dispatch.get("native_codex_subagent_used_as_dip") is True:
        failures.append("native_codex_subagent_used_as_dip")
    if dispatch.get("raw_prompt_recorded") is True:
        failures.append("raw_prompt_recorded")
    if dispatch.get("raw_provider_response_recorded") is True:
        failures.append("raw_provider_response_recorded")
    if dispatch.get("raw_backend_details_exposed") is True:
        failures.append("raw_backend_details_exposed")
    if dispatch.get("secret_value_exposed") is True:
        failures.append("secret_value_exposed")
    if dispatch.get("product_ready") is True:
        failures.append("product_ready_must_not_be_claimed")
    if dispatch.get("native_free_chat_router_proven") is True:
        failures.append("native_free_chat_router_must_not_be_claimed")
    return sorted(set(failures))


def _machine_error_code(
    *,
    ledger_required_failures: Sequence[str],
    unsafe_ledger_failures: Sequence[str],
    prompt_digest_bound: bool,
    dispatch_packet: Mapping[str, Any],
    dispatch_failures: Sequence[str],
) -> str:
    if not (
        ledger_required_failures
        or unsafe_ledger_failures
        or not prompt_digest_bound
        or dispatch_failures
    ):
        return REAL_LEDGER_BOUND_API_DISPATCH_OK
    if unsafe_ledger_failures:
        return REAL_LEDGER_BOUND_API_DISPATCH_UNSAFE_SOURCE
    if ledger_required_failures:
        return REAL_LEDGER_BOUND_API_DISPATCH_LEDGER_NOT_PROVEN
    if not prompt_digest_bound:
        return REAL_LEDGER_BOUND_API_DISPATCH_DIGEST_MISMATCH
    if dispatch_packet.get("machine_error_code"):
        return _safe_text(dispatch_packet.get("machine_error_code"), limit=96)
    return REAL_LEDGER_BOUND_API_DISPATCH_NOT_PROVEN


def build_real_ledger_bound_api_dispatch_proof_packet(
    *,
    ledger_proof_packet: Mapping[str, Any] | None,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None = None,
    runtime_context_file_metadata: Mapping[str, Any] | None = None,
    api_lane_adapter_available: bool = True,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    ledger_proof = _mapping(ledger_proof_packet)
    context = _mapping(runtime_context)
    prompt = str(prompt_text or "")
    all_secret_values = [
        prompt,
        *list(secret_values or []),
        *_route_secret_values(context),
    ]
    prompt_entry_packet = build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
        secret_values=all_secret_values,
    )
    prompt_digest = _hex_sha256(prompt_entry_packet.get("prompt_digest"))
    ledger_prompt_digest = _hex_sha256(ledger_proof.get("prompt_digest"))
    prompt_digest_bound_to_ledger = bool(
        prompt_digest and ledger_prompt_digest and prompt_digest == ledger_prompt_digest
    )
    ledger_required_failures = _ledger_proof_required_failures(ledger_proof)
    unsafe_ledger_failures = _unsafe_ledger_proof_claim_failures(ledger_proof)
    blocking_reasons: list[str] = []
    blocking_reasons.extend(ledger_required_failures)
    blocking_reasons.extend(unsafe_ledger_failures)
    if not prompt:
        blocking_reasons.append("prompt_required")
    if not prompt_digest_bound_to_ledger:
        blocking_reasons.append("prompt_digest_mismatch")

    dispatch_packet: Mapping[str, Any] = {}
    preliminary_ok = not blocking_reasons
    if preliminary_ok:
        dispatch_packet = build_controlled_api_dispatch_packet(
            prompt_text=prompt,
            runtime_context=context,
            hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
            context_file_metadata=runtime_context_file_metadata,
            api_lane_adapter_available=api_lane_adapter_available,
            controlled_provider_available=controlled_provider_available,
            controlled_provider_error_code=controlled_provider_error_code,
            secret_values=all_secret_values,
        )
        dispatch_failures = _controlled_dispatch_failures(dispatch_packet)
        blocking_reasons.extend(dispatch_failures)
        blocking_reasons.extend(
            str(reason) for reason in dispatch_packet.get("blocking_reasons", [])
        )
    else:
        dispatch_failures = []

    blocking_reasons = sorted(set(blocking_reasons))
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        ledger_required_failures=ledger_required_failures,
        unsafe_ledger_failures=unsafe_ledger_failures,
        prompt_digest_bound=prompt_digest_bound_to_ledger,
        dispatch_packet=dispatch_packet,
        dispatch_failures=dispatch_failures,
    )
    ledger_bound_dispatch_admitted = bool(
        prompt_digest_bound_to_ledger
        and not ledger_required_failures
        and not unsafe_ledger_failures
        and dispatch_packet.get("api_lane_dispatch_admitted") is True
    )
    api_lane_called = dispatch_packet.get("api_lane_called") is True
    api_response_received = dispatch_packet.get("provider_response_proven") is True
    response_digest = _hex_sha256(dispatch_packet.get("provider_response_digest"))
    response_digest_bound = bool(
        ok
        and prompt_digest_bound_to_ledger
        and dispatch_packet.get("route_bound_request_sha256")
        and response_digest
    )
    metadata = dict(runtime_context_file_metadata or {})
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND,
        "proof_scope": (
            "real_user_prompt_submit_ledger_to_route_bound_controlled_api_dispatch"
        ),
        "ledger_proof_packet_kind": _safe_text(
            ledger_proof.get("packet_kind"),
            limit=80,
        ),
        "ledger_proof_status": _safe_text(ledger_proof.get("status"), limit=32),
        "ledger_proof_machine_error_code": _safe_text(
            ledger_proof.get("machine_error_code"),
            limit=96,
        ),
        "real_user_prompt_submit_ledger_proven": (
            ledger_proof.get("real_user_prompt_submit_ledger_proven") is True
        ),
        "custom_codex_origin_proven": bool(
            ok and ledger_proof.get("custom_codex_origin_proven") is True
        ),
        "native_custom_codex_flow_proven": bool(
            ok and ledger_proof.get("native_custom_codex_flow_proven") is True
        ),
        "native_router_hook_observed": bool(
            ok and ledger_proof.get("native_router_hook_observed") is True
        ),
        "user_prompt_submit_hook_observed": bool(
            ok and ledger_proof.get("user_prompt_submit_hook_observed") is True
        ),
        "user_prompt_submit_hook_ran": (
            ledger_proof.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_ledger_written": ledger_proof.get("hook_ledger_written") is True,
        "hook_event_transport": _safe_text(
            ledger_proof.get("hook_event_transport"),
            limit=80,
        ),
        "hook_event_transport_stdin": (
            ledger_proof.get("hook_event_transport_stdin") is True
        ),
        "hook_prompt_digest_bound": (
            ledger_proof.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": (
            ledger_proof.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": (
            ledger_proof.get("thread_or_turn_digest_bound") is True
        ),
        "codex_hook_trusted_by_profile_state": (
            ledger_proof.get("codex_hook_trusted_by_profile_state") is True
        ),
        "prompt_digest": prompt_digest if prompt_digest_bound_to_ledger else "",
        "prompt_digest_present": bool(prompt_digest),
        "ledger_prompt_digest_present": bool(ledger_prompt_digest),
        "prompt_digest_bound_to_ledger": prompt_digest_bound_to_ledger,
        "prompt_digest_bound_to_dispatch": bool(
            ok and dispatch_packet.get("prompt_digest") == prompt_digest
        ),
        "ledger_bound_dispatch_admitted": ledger_bound_dispatch_admitted,
        "alias_context_read": bool(
            ledger_bound_dispatch_admitted
            and dispatch_packet.get("alias_context_read") is True
        ),
        "alias_bound": bool(
            ledger_bound_dispatch_admitted
            and dispatch_packet.get("alias_bound") is True
        ),
        "selected_alias": _safe_text(dispatch_packet.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            dispatch_packet.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(dispatch_packet.get("selected_slot"), limit=64),
        "route_id_allowed": dispatch_packet.get("route_id_allowed") is True,
        "allowed_route_enforced": (
            dispatch_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_enforced": (
            dispatch_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_count": int(
            dispatch_packet.get("allowed_api_route_ids_count") or 0
        ),
        "forbidden_stale_route_ids_enforced": int(
            dispatch_packet.get("forbidden_stale_route_ids_count") or 0
        )
        > 0,
        "forbidden_stale_route_ids_count": int(
            dispatch_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "api_lane_called": api_lane_called,
        "api_lane_adapter_called": (
            dispatch_packet.get("api_lane_adapter_called") is True
        ),
        "api_lane_dispatch_admitted": (
            dispatch_packet.get("api_lane_dispatch_admitted") is True
        ),
        "api_lane_provider_called": (
            dispatch_packet.get("api_lane_provider_called") is True
        ),
        "api_response_received": api_response_received,
        "provider_response_proven": api_response_received,
        "controlled_provider_called": (
            dispatch_packet.get("controlled_provider_called") is True
        ),
        "controlled_provider_response_proven": (
            dispatch_packet.get("controlled_provider_response_proven") is True
        ),
        "response_digest_bound": response_digest_bound,
        "response_bound_to_proof": response_digest_bound,
        "provider_response_digest": response_digest,
        "controlled_provider_response_sha256": _hex_sha256(
            dispatch_packet.get("controlled_provider_response_sha256")
        ),
        "dispatch_attempted": (
            dispatch_packet.get("route_bound_dispatch_attempted") is True
        ),
        "dispatch_proven": ok,
        "dispatch_status": DISPATCH_STATUS_PROVEN if ok else DISPATCH_STATUS_BLOCKED,
        "real_ledger_bound_api_dispatch_proven": ok,
        "controlled_dispatch_packet_kind": _safe_text(
            dispatch_packet.get("packet_kind"),
            limit=80,
        ),
        "controlled_dispatch_status": _safe_text(
            dispatch_packet.get("status"),
            limit=32,
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
        "route_bound_request_sha256": _hex_sha256(
            dispatch_packet.get("route_bound_request_sha256")
        ),
        "dispatch_truth_source": _safe_text(
            dispatch_packet.get("dispatch_truth_source") or "not_proven",
            limit=80,
        ),
        "api_lane_truth_source": _safe_text(
            dispatch_packet.get("api_lane_truth_source") or "not_proven",
            limit=80,
        ),
        "selected_api_route_id_present": (
            dispatch_packet.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            dispatch_packet.get("selected_api_route_id_sha256")
        ),
        "provider_like_response_only": (
            dispatch_packet.get("provider_like_response_only") is True
        ),
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "live_provider_status": "not_attempted",
        "network_dependent": False,
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_live_provider": True,
        "does_not_prove_handoff": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "fallback_used": dispatch_packet.get("fallback_used") is True,
        "local_imitation_used": dispatch_packet.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": (
            dispatch_packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "codex_native_subagent_used_as_dip": (
            dispatch_packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "blocking_reasons": blocking_reasons,
        "ledger_proof_required_failures": ledger_required_failures,
        "ledger_proof_unsafe_claim_failures": unsafe_ledger_failures,
        "controlled_dispatch_failures": dispatch_failures,
        "raw_prompt_recorded": False,
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
            "WBP proved real ledger-bound API dispatch without handoff or product readiness."
            if ok
            else "WBP blocked real ledger-bound API dispatch before proof."
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


def run_real_ledger_bound_api_dispatch_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    hook_ledger_file: str | None = None,
    runtime_context_file: str | None = None,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    ledger_proof_packet = run_real_user_prompt_submit_ledger_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        hook_ledger_file=hook_ledger_file,
        runtime_context_file=runtime_context_file,
    )
    return build_real_ledger_bound_api_dispatch_proof_packet(
        ledger_proof_packet=ledger_proof_packet,
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        runtime_context_file_metadata=context_metadata,
    )
