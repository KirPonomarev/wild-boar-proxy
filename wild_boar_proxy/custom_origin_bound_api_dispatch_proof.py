# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_ui_origin_admission import (
    CUSTOM_UI_ORIGIN_ADMISSION_OK,
    CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND,
    run_custom_ui_origin_admission_command,
)
from .real_ledger_bound_api_dispatch_proof import (
    REAL_LEDGER_BOUND_API_DISPATCH_OK,
    REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND,
    run_real_ledger_bound_api_dispatch_proof_command,
)
from .router_hook_entry import _safe_text
from .runtime import RuntimePaths


CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND = (
    "wbp_custom_origin_bound_api_dispatch_proof"
)

CUSTOM_ORIGIN_BOUND_API_DISPATCH_OK = "OK"
CUSTOM_ORIGIN_BOUND_API_DISPATCH_ORIGIN_NOT_PROVEN = (
    "WBP_CUSTOM_ORIGIN_BOUND_API_DISPATCH_ORIGIN_NOT_PROVEN"
)
CUSTOM_ORIGIN_BOUND_API_DISPATCH_DISPATCH_NOT_PROVEN = (
    "WBP_CUSTOM_ORIGIN_BOUND_API_DISPATCH_DISPATCH_NOT_PROVEN"
)
CUSTOM_ORIGIN_BOUND_API_DISPATCH_DIGEST_MISMATCH = (
    "WBP_CUSTOM_ORIGIN_BOUND_API_DISPATCH_DIGEST_MISMATCH"
)
CUSTOM_ORIGIN_BOUND_API_DISPATCH_UNSAFE_SOURCE = (
    "WBP_CUSTOM_ORIGIN_BOUND_API_DISPATCH_UNSAFE_SOURCE"
)
CUSTOM_ORIGIN_BOUND_API_DISPATCH_INVALID = (
    "WBP_CUSTOM_ORIGIN_BOUND_API_DISPATCH_INVALID"
)

LAUNCH_SURFACE_LAUNCHSERVICES_PROOF_HARNESS = "launchservices_proof_harness"
LAUNCH_SURFACE_MANUAL_CUSTOM_CODEX_UI = "manual_custom_codex_ui"
LAUNCH_SURFACE_CUSTOM_LAUNCHER = "custom_launcher"
LAUNCH_SURFACE_CODEX_DESKTOP_CUSTOM_PROFILE = "codex_desktop_custom_profile"

ADMITTED_CUSTOM_ORIGIN_BOUND_LAUNCH_SURFACES = {
    LAUNCH_SURFACE_LAUNCHSERVICES_PROOF_HARNESS,
    LAUNCH_SURFACE_MANUAL_CUSTOM_CODEX_UI,
    LAUNCH_SURFACE_CUSTOM_LAUNCHER,
    LAUNCH_SURFACE_CODEX_DESKTOP_CUSTOM_PROFILE,
}


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


def _launch_surface_failures(launch_surface: object) -> tuple[str, list[str]]:
    surface = _safe_text(launch_surface, limit=80)
    if surface not in ADMITTED_CUSTOM_ORIGIN_BOUND_LAUNCH_SURFACES:
        return "", ["launch_surface_not_admitted"]
    return surface, []


def _origin_required_failures(origin: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if origin.get("packet_kind") != CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND:
        failures.append("custom_origin_packet_kind_invalid")
    if origin.get("status") != "ok":
        failures.append("custom_origin_packet_not_ok")
    if origin.get("machine_error_code") != CUSTOM_UI_ORIGIN_ADMISSION_OK:
        failures.append("custom_origin_machine_error_not_ok")
    for field, reason in (
        ("custom_ui_origin_admitted", "custom_ui_origin_not_admitted"),
        ("custom_codex_flow_origin_admitted", "custom_codex_flow_origin_not_admitted"),
        ("fresh_user_prompt_submit_ledger_proven", "fresh_ledger_not_proven"),
        ("real_custom_app_submit_ledger_proven", "custom_app_submit_not_proven"),
        ("real_user_prompt_submit_ledger_proven", "user_prompt_ledger_not_proven"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("process_inventory_live", "custom_process_inventory_not_live"),
        ("wbp_clean_app_process_observed", "wbp_clean_app_process_not_observed"),
        (
            "wbp_clean_app_server_process_observed",
            "wbp_clean_app_server_process_not_observed",
        ),
    ):
        if origin.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(origin.get("prompt_digest")):
        failures.append("custom_origin_prompt_digest_missing")
    return sorted(set(failures))


def _dispatch_required_failures(dispatch: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch.get("packet_kind") != REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND:
        failures.append("ledger_bound_dispatch_packet_kind_invalid")
    if dispatch.get("status") != "ok":
        failures.append("ledger_bound_dispatch_packet_not_ok")
    if dispatch.get("machine_error_code") != REAL_LEDGER_BOUND_API_DISPATCH_OK:
        failures.append("ledger_bound_dispatch_machine_error_not_ok")
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
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("prompt_digest_bound_to_ledger", "prompt_digest_not_bound_to_ledger"),
        ("prompt_digest_bound_to_dispatch", "prompt_digest_not_bound_to_dispatch"),
        ("alias_context_read", "alias_context_not_read"),
        ("alias_bound", "alias_not_bound"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("api_lane_called", "api_lane_not_called"),
        ("api_lane_dispatch_admitted", "api_lane_dispatch_not_admitted"),
        ("api_lane_provider_called", "api_lane_provider_not_called"),
        ("api_response_received", "api_response_not_received"),
        ("provider_response_proven", "provider_response_not_proven"),
        (
            "controlled_provider_response_proven",
            "controlled_provider_response_not_proven",
        ),
        ("dispatch_attempted", "dispatch_not_attempted"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
    ):
        if dispatch.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(dispatch.get("prompt_digest")):
        failures.append("ledger_bound_dispatch_prompt_digest_missing")
    if int(dispatch.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("stale_route_guard_missing")
    return sorted(set(failures))


def _origin_unsafe_failures(origin: Mapping[str, Any]) -> list[str]:
    checks = {
        "api_lane_called": "origin_must_not_claim_api_lane_called",
        "api_response_received": "origin_must_not_claim_api_response",
        "dispatch_attempted": "origin_must_not_claim_dispatch_attempted",
        "dispatch_proven": "origin_must_not_claim_dispatch_proven",
        "route_bound_dispatch_proven": "origin_must_not_claim_route_bound_dispatch",
        "provider_response_proven": "origin_must_not_claim_provider_response",
        "handoff_file_written": "source_must_not_claim_handoff",
        "handoff_delivered": "source_must_not_claim_handoff",
        "delivery_observed": "source_must_not_claim_delivery",
        "custom_codex_ui_visibility_proven": "source_must_not_claim_ui_visibility",
        "codex_working_flow_delivery_proven": "source_must_not_claim_working_flow",
        "native_free_chat_router_proven": "source_must_not_claim_native_router",
        "native_free_chat_router_product_ready": "source_must_not_claim_product_ready",
        "live_provider_proven": "source_must_not_claim_live_provider",
        "product_ready": "source_must_not_claim_product_ready",
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
    }
    return sorted(
        {reason for field, reason in checks.items() if origin.get(field) is True}
    )


def _dispatch_unsafe_failures(dispatch: Mapping[str, Any]) -> list[str]:
    checks = {
        "handoff_file_written": "source_must_not_claim_handoff",
        "handoff_delivered": "source_must_not_claim_handoff",
        "delivery_observed": "source_must_not_claim_delivery",
        "custom_codex_ui_visibility_proven": "source_must_not_claim_ui_visibility",
        "codex_working_flow_delivery_proven": "source_must_not_claim_working_flow",
        "native_free_chat_router_proven": "source_must_not_claim_native_router",
        "native_free_chat_router_product_ready": "source_must_not_claim_product_ready",
        "live_provider_proven": "source_must_not_claim_live_provider",
        "live_provider_response_proven": "source_must_not_claim_live_provider",
        "external_live_provider_response_proven": "source_must_not_claim_live_provider",
        "product_ready": "source_must_not_claim_product_ready",
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
    }
    return sorted(
        {reason for field, reason in checks.items() if dispatch.get(field) is True}
    )


def _machine_error_code(
    *,
    launch_failures: Sequence[str],
    origin_failures: Sequence[str],
    dispatch_failures: Sequence[str],
    digest_bound: bool,
    unsafe_failures: Sequence[str],
) -> str:
    if not (
        launch_failures
        or origin_failures
        or dispatch_failures
        or not digest_bound
        or unsafe_failures
    ):
        return CUSTOM_ORIGIN_BOUND_API_DISPATCH_OK
    if unsafe_failures:
        return CUSTOM_ORIGIN_BOUND_API_DISPATCH_UNSAFE_SOURCE
    if launch_failures:
        return CUSTOM_ORIGIN_BOUND_API_DISPATCH_INVALID
    if origin_failures:
        return CUSTOM_ORIGIN_BOUND_API_DISPATCH_ORIGIN_NOT_PROVEN
    if not digest_bound:
        return CUSTOM_ORIGIN_BOUND_API_DISPATCH_DIGEST_MISMATCH
    return CUSTOM_ORIGIN_BOUND_API_DISPATCH_DISPATCH_NOT_PROVEN


def build_custom_origin_bound_api_dispatch_proof_packet(
    *,
    custom_origin_packet: Mapping[str, Any] | None,
    ledger_bound_dispatch_packet: Mapping[str, Any] | None,
    prompt_text: object,
    launch_surface: object,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    origin = _mapping(custom_origin_packet)
    dispatch = _mapping(ledger_bound_dispatch_packet)
    prompt = str(prompt_text or "")
    surface, launch_failures = _launch_surface_failures(launch_surface)
    origin_failures = _origin_required_failures(origin)
    dispatch_failures = _dispatch_required_failures(dispatch)
    unsafe_failures = sorted(
        set(_origin_unsafe_failures(origin) + _dispatch_unsafe_failures(dispatch))
    )

    origin_prompt_digest = _hex_sha256(origin.get("prompt_digest"))
    dispatch_prompt_digest = _hex_sha256(dispatch.get("prompt_digest"))
    digest_bound = bool(
        origin_prompt_digest
        and dispatch_prompt_digest
        and origin_prompt_digest == dispatch_prompt_digest
    )

    blocking_reasons = sorted(
        set(
            launch_failures
            + origin_failures
            + dispatch_failures
            + ([] if digest_bound else ["custom_origin_dispatch_digest_mismatch"])
            + unsafe_failures
            + _safe_reasons(origin.get("blocking_reasons"))
            + _safe_reasons(dispatch.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        launch_failures=launch_failures,
        origin_failures=origin_failures,
        dispatch_failures=dispatch_failures,
        digest_bound=digest_bound,
        unsafe_failures=unsafe_failures,
    )

    api_lane_called = bool(ok and dispatch.get("api_lane_called") is True)
    dispatch_attempted = bool(ok and dispatch.get("dispatch_attempted") is True)
    provider_response_proven = bool(ok and dispatch.get("provider_response_proven") is True)
    controlled_provider_response_proven = bool(
        ok and dispatch.get("controlled_provider_response_proven") is True
    )

    extra = {
        "schema_version": 1,
        "packet_kind": CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND,
        "proof_scope": "custom_codex_origin_bound_to_ledger_bound_api_dispatch",
        "launch_surface": surface,
        "launch_surface_explicit": bool(surface),
        "launch_surface_recorded": bool(surface),
        "custom_ui_origin_packet_kind": _safe_text(origin.get("packet_kind"), limit=96),
        "custom_ui_origin_status": _safe_text(origin.get("status"), limit=32),
        "custom_ui_origin_machine_error_code": _safe_text(
            origin.get("machine_error_code"),
            limit=96,
        ),
        "ledger_bound_dispatch_packet_kind": _safe_text(
            dispatch.get("packet_kind"),
            limit=96,
        ),
        "ledger_bound_dispatch_status": _safe_text(
            dispatch.get("status"),
            limit=32,
        ),
        "ledger_bound_dispatch_machine_error_code": _safe_text(
            dispatch.get("machine_error_code"),
            limit=96,
        ),
        "custom_ui_origin_admitted": bool(
            ok and origin.get("custom_ui_origin_admitted") is True
        ),
        "custom_codex_flow_origin_admitted": bool(
            ok and origin.get("custom_codex_flow_origin_admitted") is True
        ),
        "fresh_user_prompt_submit_ledger_proven": bool(
            ok and origin.get("fresh_user_prompt_submit_ledger_proven") is True
        ),
        "real_custom_app_submit_ledger_proven": bool(
            ok and origin.get("real_custom_app_submit_ledger_proven") is True
        ),
        "real_user_prompt_submit_ledger_proven": bool(
            ok and dispatch.get("real_user_prompt_submit_ledger_proven") is True
        ),
        "user_prompt_submit_hook_observed": bool(
            ok and dispatch.get("user_prompt_submit_hook_observed") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and dispatch.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_ledger_written": bool(ok and dispatch.get("hook_ledger_written") is True),
        "hook_prompt_digest_bound": bool(
            ok
            and origin.get("hook_prompt_digest_bound") is True
            and dispatch.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok
            and origin.get("hook_runtime_context_digest_bound") is True
            and dispatch.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": bool(
            ok
            and origin.get("thread_or_turn_digest_bound") is True
            and dispatch.get("thread_or_turn_digest_bound") is True
        ),
        "prompt_digest": origin_prompt_digest if digest_bound else "",
        "custom_origin_prompt_digest_present": bool(origin_prompt_digest),
        "ledger_bound_dispatch_prompt_digest_present": bool(dispatch_prompt_digest),
        "prompt_digest_bound_to_custom_origin": bool(ok and origin_prompt_digest),
        "prompt_digest_bound_to_ledger": bool(
            ok and dispatch.get("prompt_digest_bound_to_ledger") is True
        ),
        "prompt_digest_bound_to_dispatch": bool(
            ok and dispatch.get("prompt_digest_bound_to_dispatch") is True
        ),
        "prompt_digest_bound_to_custom_origin_and_dispatch": bool(ok and digest_bound),
        "custom_origin_bound": ok,
        "ledger_bound_dispatch_admitted": bool(
            ok and dispatch.get("ledger_bound_dispatch_admitted") is True
        ),
        "real_ledger_bound_api_dispatch_proven": bool(
            ok and dispatch.get("real_ledger_bound_api_dispatch_proven") is True
        ),
        "alias_context_read": bool(ok and dispatch.get("alias_context_read") is True),
        "alias_bound": bool(ok and dispatch.get("alias_bound") is True),
        "alias_resolved": bool(ok and dispatch.get("alias_bound") is True),
        "selected_alias": _safe_text(dispatch.get("selected_alias"), limit=80) if ok else "",
        "selected_alias_lane": _safe_text(
            dispatch.get("selected_alias_lane"),
            limit=32,
        ) if ok else "",
        "selected_slot": _safe_text(dispatch.get("selected_slot"), limit=64) if ok else "",
        "route_id_allowed": bool(ok and dispatch.get("route_id_allowed") is True),
        "allowed_api_route_ids_enforced": bool(
            ok and dispatch.get("allowed_api_route_ids_enforced") is True
        ),
        "selected_api_route_id_present": bool(
            ok and dispatch.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": (
            _hex_sha256(dispatch.get("selected_api_route_id_sha256")) if ok else ""
        ),
        "forbidden_stale_route_ids_enforced": bool(
            ok and int(dispatch.get("forbidden_stale_route_ids_count") or 0) > 0
        ),
        "forbidden_stale_route_ids_count": (
            int(dispatch.get("forbidden_stale_route_ids_count") or 0) if ok else 0
        ),
        "api_lane_called": api_lane_called,
        "api_lane_adapter_called": bool(
            ok and dispatch.get("api_lane_adapter_called") is True
        ),
        "api_lane_dispatch_admitted": bool(
            ok and dispatch.get("api_lane_dispatch_admitted") is True
        ),
        "api_lane_provider_called": bool(
            ok and dispatch.get("api_lane_provider_called") is True
        ),
        "api_response_received": provider_response_proven,
        "provider_response_proven": provider_response_proven,
        "controlled_provider_called": bool(
            ok and dispatch.get("controlled_provider_called") is True
        ),
        "controlled_provider_response_proven": controlled_provider_response_proven,
        "provider_like_response_only": bool(
            ok and dispatch.get("provider_like_response_only") is True
        ),
        "response_digest_bound": bool(ok and dispatch.get("response_digest_bound") is True),
        "response_bound_to_proof": bool(
            ok and dispatch.get("response_bound_to_proof") is True
        ),
        "provider_response_digest": (
            _hex_sha256(dispatch.get("provider_response_digest")) if ok else ""
        ),
        "controlled_provider_response_sha256": (
            _hex_sha256(dispatch.get("controlled_provider_response_sha256"))
            if ok
            else ""
        ),
        "dispatch_attempted": dispatch_attempted,
        "dispatch_status": "proven" if ok else "blocked",
        "dispatch_proven": ok,
        "route_bound_dispatch_attempted": bool(
            ok and dispatch.get("route_bound_dispatch_attempted") is True
        ),
        "route_bound_dispatch_proven": bool(
            ok and dispatch.get("route_bound_dispatch_proven") is True
        ),
        "route_bound_request_sent": bool(
            ok and dispatch.get("route_bound_request_sent") is True
        ),
        "route_bound_request_sha256": (
            _hex_sha256(dispatch.get("route_bound_request_sha256")) if ok else ""
        ),
        "dispatch_truth_source": _safe_text(
            dispatch.get("dispatch_truth_source") if ok else "not_proven",
            limit=80,
        ),
        "api_lane_truth_source": _safe_text(
            dispatch.get("api_lane_truth_source") if ok else "not_proven",
            limit=80,
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
        "origin_required_failures": origin_failures,
        "dispatch_required_failures": dispatch_failures,
        "unsafe_source_failures": unsafe_failures,
        "blocking_reasons": blocking_reasons,
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
            "WBP proved Custom Codex origin bound to ledger-backed API dispatch."
            if ok
            else "WBP blocked Custom-origin-bound API dispatch proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=[prompt, *list(secret_values or [])],
        extra=extra,
    )


def run_custom_origin_bound_api_dispatch_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    ledger_mtime_before_ns: int,
    launch_surface: object,
    hook_ledger_file: str | None = None,
    runtime_context_file: str | None = None,
    process_inventory_file: str | None = None,
    stock_app_path: str | None = None,
    custom_app_path: str | None = None,
    custom_profile_dir: str | None = None,
    custom_user_data_dir: str | None = None,
    custom_launcher_path: str | None = None,
) -> dict[str, Any]:
    custom_origin_packet = run_custom_ui_origin_admission_command(
        paths=paths,
        prompt_text=prompt_text,
        ledger_mtime_before_ns=ledger_mtime_before_ns,
        hook_ledger_file=hook_ledger_file,
        runtime_context_file=runtime_context_file,
        process_inventory_file=process_inventory_file,
        stock_app_path=stock_app_path,
        custom_app_path=custom_app_path,
        custom_profile_dir=custom_profile_dir,
        custom_user_data_dir=custom_user_data_dir,
        custom_launcher_path=custom_launcher_path,
    )
    ledger_bound_dispatch_packet = run_real_ledger_bound_api_dispatch_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        hook_ledger_file=hook_ledger_file,
        runtime_context_file=runtime_context_file,
    )
    return build_custom_origin_bound_api_dispatch_proof_packet(
        custom_origin_packet=custom_origin_packet,
        ledger_bound_dispatch_packet=ledger_bound_dispatch_packet,
        prompt_text=prompt_text,
        launch_surface=launch_surface,
    )
