# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded dispatch packet builders for native Codex launch contours.

This module does not execute OS launch commands. It models the owner packet
surface used by a later live runner and keeps dispatch truth separate from
prompt, routing, and native app completion claims.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CUSTOM_LAUNCH_MODE = "CODEX_CUSTOM_NATIVE_APP"
ORIGINAL_LAUNCH_MODE = "ORIGINAL_CODEX_VIA_WBP"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_native_dispatch_authorization_packet(
    *,
    owner_authorized: bool,
    admission_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    admission_ok = _admission_ok(admission_packet, expected_mode=CUSTOM_LAUNCH_MODE)
    authorized = owner_authorized and admission_ok
    return {
        **_base_packet(packet_kind="native_dispatch_authorization"),
        "status": "ok" if authorized else "blocked",
        "machine_error_code": "OK" if authorized else _authorization_block_code(
            owner_authorized=owner_authorized,
            admission_ok=admission_ok,
        ),
        "owner_authorized": owner_authorized,
        "admission_consumed": admission_ok,
        "live_dispatch_allowed": authorized,
        "blocked_reason_class": "" if authorized else _authorization_block_reason(
            owner_authorized=owner_authorized,
            admission_ok=admission_ok,
        ),
    }


def build_native_custom_dispatch_packet(
    *,
    owner_authorized: bool,
    admission_packet: dict[str, Any] | None,
    dispatch_result: dict[str, Any] | None = None,
    process_observation: dict[str, Any] | None = None,
    window_observation: dict[str, Any] | None = None,
    usability_observation: dict[str, Any] | None = None,
    protection_packet: dict[str, Any] | None = None,
    cleanup_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth = build_native_dispatch_authorization_packet(
        owner_authorized=owner_authorized,
        admission_packet=admission_packet,
    )
    base = {
        **_base_packet(packet_kind="native_custom_dispatch"),
        "launch_mode": CUSTOM_LAUNCH_MODE,
        "admission_consumed": auth["admission_consumed"],
        "owner_authorized": owner_authorized,
        "target_candidate_source_admitted": _safe_admission_field(
            admission_packet,
            "target_candidate_source",
        ),
        "isolated_home_used": _safe_admission_bool(admission_packet, "isolated_home_plan"),
        "isolated_codex_home_used": _safe_admission_bool(admission_packet, "isolated_codex_home_plan"),
        "isolated_profile_data_dir_used": _safe_admission_bool(
            admission_packet,
            "isolated_profile_data_dir_plan",
        ),
        "server_owned_route_endpoint_carried": _safe_admission_bool(
            admission_packet,
            "server_planned_route_endpoint",
        ),
        "native_window_usable": False,
        "native_window_usable_claimed": False,
        "native_launch_complete": False,
        "prompt_attempted": False,
        "route_trace_bound": False,
        "route_inference_attempted": False,
        "web_workbench_substituted": False,
    }
    if auth["status"] != "ok":
        return {
            **base,
            "status": "blocked",
            "machine_error_code": auth["machine_error_code"],
            "dispatch_attempted": False,
            "dispatch_observed": False,
            "process_observed": False,
            "window_observed": False,
            "window_observation_blocked_with_reason": False,
            "current_codex_touched": False,
            "cleanup_or_rollback_status": "not_attempted",
            "blocked_reason_class": auth["blocked_reason_class"],
        }

    dispatch_result = dispatch_result if isinstance(dispatch_result, dict) else {}
    process_observation = process_observation if isinstance(process_observation, dict) else {}
    window_observation = window_observation if isinstance(window_observation, dict) else {}
    usability_observation = usability_observation if isinstance(usability_observation, dict) else {}
    protection_packet = protection_packet if isinstance(protection_packet, dict) else {}
    cleanup_packet = cleanup_packet if isinstance(cleanup_packet, dict) else {}
    dispatch_attempted = dispatch_result.get("dispatch_attempted") is True
    dispatch_observed = dispatch_result.get("dispatch_observed") is True
    process_observed = process_observation.get("process_observed") is True
    window_observed = window_observation.get("window_observed") is True
    window_blocked = bool(window_observation.get("blocked_reason_class"))
    native_window_usable = usability_observation.get("native_window_usable") is True
    usability_claimed = usability_observation.get("native_window_usable_claimed") is True
    usability_blocked = bool(usability_observation.get("blocked_reason_class"))
    current_codex_touched = protection_packet.get("current_codex_touched") is True
    cleanup_status = str(cleanup_packet.get("cleanup_or_rollback_status") or "not_attempted")
    slice_pass = (
        dispatch_observed
        and process_observed
        and (window_observed or window_blocked)
        and native_window_usable
        and not current_codex_touched
        and cleanup_status == "ok"
    )
    failed_checks = _dispatch_failed_checks(
        dispatch_observed=dispatch_observed,
        process_observed=process_observed,
        window_observed=window_observed,
        window_blocked=window_blocked,
        native_window_usable=native_window_usable,
        current_codex_touched=current_codex_touched,
        cleanup_status=cleanup_status,
    )
    return {
        **base,
        "status": "ok" if slice_pass else "blocked",
        "machine_error_code": "OK" if slice_pass else "NATIVE_CUSTOM_DISPATCH_SLICE_BLOCKED",
        "dispatch_attempted": dispatch_attempted,
        "dispatch_observed": dispatch_observed,
        "process_observed": process_observed,
        "window_observed": window_observed,
        "window_observation_blocked_with_reason": window_blocked,
        "window_observation_blocked_reason_class": str(
            window_observation.get("blocked_reason_class") or ""
        ),
        "native_window_usable": native_window_usable,
        "native_window_usable_claimed": usability_claimed,
        "usability_blocked_with_reason": usability_blocked,
        "usability_blocked_reason_class": str(
            usability_observation.get("blocked_reason_class") or ""
        ),
        "current_codex_touched": current_codex_touched,
        "cleanup_or_rollback_status": cleanup_status,
        "dispatch_slice_pass": slice_pass,
        "failed_checks": failed_checks,
    }


def build_native_custom_dispatch_blocked_packet(
    *,
    owner_authorized: bool,
    admission_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        **build_native_custom_dispatch_packet(
            owner_authorized=owner_authorized,
            admission_packet=admission_packet,
        ),
        "packet_kind": "native_custom_dispatch_blocked",
    }


def build_native_original_dispatch_deferred_packet(
    *,
    reason_class: str = "out_of_scope_custom_first",
) -> dict[str, Any]:
    return {
        **_base_packet(packet_kind="native_original_dispatch_deferred"),
        "status": "blocked",
        "machine_error_code": "NATIVE_ORIGINAL_DISPATCH_DEFERRED",
        "launch_mode": ORIGINAL_LAUNCH_MODE,
        "original_contract_preserved": True,
        "original_live_dispatch_attempted": False,
        "reason_class": reason_class,
        "native_launch_complete": False,
        "route_trace_bound": False,
        "reversibility_proof_claimed": False,
    }


def build_native_process_observation_packet(
    *,
    dispatch_observed: bool,
    process_observed: bool,
    observation_blocked_reason: str = "",
) -> dict[str, Any]:
    status = "ok" if process_observed else "blocked"
    return {
        **_base_packet(packet_kind="native_process_observation"),
        "status": status,
        "machine_error_code": "OK" if process_observed else "NATIVE_PROCESS_NOT_OBSERVED",
        "dispatch_observed": dispatch_observed,
        "process_observed": process_observed,
        "observation_blocked_reason_class": observation_blocked_reason,
        "native_launch_complete": False,
        "prompt_attempted": False,
        "route_trace_bound": False,
    }


def build_native_window_observation_packet(
    *,
    window_observed: bool,
    blocked_reason_class: str = "",
) -> dict[str, Any]:
    honest = window_observed or bool(blocked_reason_class)
    return {
        **_base_packet(packet_kind="native_window_observation"),
        "status": "ok" if honest else "blocked",
        "machine_error_code": "OK" if honest else "NATIVE_WINDOW_OBSERVATION_MISSING",
        "window_observed": window_observed,
        "window_observation_blocked_with_reason": bool(blocked_reason_class),
        "blocked_reason_class": blocked_reason_class,
        "native_window_usable": False,
        "native_window_usable_claimed": False,
        "native_launch_complete": False,
        "prompt_attempted": False,
        "route_trace_bound": False,
    }


def build_native_window_usability_packet(
    *,
    window_observed: bool,
    input_capable_ui_observed: bool,
    blocked_reason_class: str = "",
) -> dict[str, Any]:
    native_window_usable = window_observed and input_capable_ui_observed
    honest = native_window_usable or bool(blocked_reason_class)
    return {
        **_base_packet(packet_kind="native_window_usability"),
        "status": "ok" if honest else "blocked",
        "machine_error_code": "OK" if honest else "NATIVE_WINDOW_USABILITY_NOT_PROVEN",
        "window_observed": window_observed,
        "input_capable_ui_observed": input_capable_ui_observed,
        "native_window_usable": native_window_usable,
        "native_window_usable_claimed": native_window_usable,
        "usability_blocked_with_reason": bool(blocked_reason_class),
        "blocked_reason_class": blocked_reason_class,
        "prompt_attempted": False,
        "route_trace_bound": False,
        "route_inference_attempted": False,
        "native_launch_complete": False,
    }


def build_native_current_codex_protection_packet(
    *,
    before_snapshot_captured: bool,
    after_snapshot_captured: bool,
    current_codex_touched: bool,
    protection_basis: str = "",
) -> dict[str, Any]:
    protected = not current_codex_touched and (
        (before_snapshot_captured and after_snapshot_captured) or bool(protection_basis)
    )
    return {
        **_base_packet(packet_kind="native_current_codex_protection"),
        "status": "ok" if protected else "blocked",
        "machine_error_code": "OK" if protected else "CURRENT_CODEX_PROTECTION_NOT_PROVEN",
        "before_snapshot_captured": before_snapshot_captured,
        "after_snapshot_captured": after_snapshot_captured,
        "current_codex_touched": current_codex_touched,
        "current_codex_protected": protected,
        "protection_basis": protection_basis,
    }


def build_native_cleanup_rollback_execution_packet(
    *,
    cleanup_attempted: bool,
    rollback_attempted: bool,
    cleanup_or_rollback_status: str,
    cleanup_blocked_reason_class: str = "",
) -> dict[str, Any]:
    cleanup_ok = cleanup_or_rollback_status in {"ok", "ok_no_process_launched"}
    return {
        **_base_packet(packet_kind="native_cleanup_rollback_execution"),
        "status": "ok" if cleanup_ok else "blocked",
        "machine_error_code": "OK" if cleanup_ok else "NATIVE_CLEANUP_ROLLBACK_NOT_OK",
        "cleanup_attempted": cleanup_attempted,
        "rollback_attempted": rollback_attempted,
        "cleanup_or_rollback_status": cleanup_or_rollback_status,
        "cleanup_blocked_reason_class": cleanup_blocked_reason_class,
    }


def build_native_dispatch_false_green_audit(
    *,
    custom_dispatch_packet: dict[str, Any],
    original_deferred_packet: dict[str, Any],
) -> dict[str, Any]:
    usability_claim_invalid = custom_dispatch_packet.get("native_window_usable") is True and (
        custom_dispatch_packet.get("process_observed") is not True
        or custom_dispatch_packet.get("window_observed") is not True
        or custom_dispatch_packet.get("prompt_attempted") is True
        or custom_dispatch_packet.get("route_trace_bound") is True
        or custom_dispatch_packet.get("route_inference_attempted") is True
    )
    false_green = any(
        custom_dispatch_packet.get(field) is True
        for field in (
            "native_launch_complete",
            "prompt_attempted",
            "route_trace_bound",
            "route_inference_attempted",
        )
    )
    false_green = (
        false_green
        or usability_claim_invalid
        or original_deferred_packet.get("original_live_dispatch_attempted") is True
    )
    return {
        **_base_packet(packet_kind="native_dispatch_false_green_audit"),
        "status": "ok" if not false_green else "failed",
        "machine_error_code": "OK" if not false_green else "NATIVE_DISPATCH_FALSE_GREEN",
        "custom_dispatch_claims_bounded": not false_green,
        "original_deferred_honestly": (
            original_deferred_packet.get("original_live_dispatch_attempted") is False
            and original_deferred_packet.get("reversibility_proof_claimed") is False
        ),
        "no_prompt_attempted": custom_dispatch_packet.get("prompt_attempted") is False,
        "no_route_inference_attempted": custom_dispatch_packet.get("route_trace_bound") is False,
        "no_native_completion_claim": custom_dispatch_packet.get("native_launch_complete") is False,
        "native_window_usability_bounded": (
            custom_dispatch_packet.get("native_window_usable") is not True
            or (
                custom_dispatch_packet.get("process_observed") is True
                and custom_dispatch_packet.get("window_observed") is True
                and custom_dispatch_packet.get("prompt_attempted") is False
                and custom_dispatch_packet.get("route_trace_bound") is False
                and custom_dispatch_packet.get("route_inference_attempted") is False
            )
        ),
        "usability_not_upgraded_to_prompt_or_route": (
            custom_dispatch_packet.get("native_window_usable") is not True
            or (
                custom_dispatch_packet.get("prompt_attempted") is False
                and custom_dispatch_packet.get("route_trace_bound") is False
                and custom_dispatch_packet.get("route_inference_attempted") is False
            )
        ),
    }


def _authorization_block_code(*, owner_authorized: bool, admission_ok: bool) -> str:
    if not owner_authorized:
        return "NATIVE_DISPATCH_OWNER_AUTHORIZATION_MISSING"
    if not admission_ok:
        return "NATIVE_DISPATCH_ADMISSION_NOT_ADMITTED"
    return "NATIVE_DISPATCH_BLOCKED"


def _authorization_block_reason(*, owner_authorized: bool, admission_ok: bool) -> str:
    if not owner_authorized:
        return "owner_authorization_missing"
    if not admission_ok:
        return "custom_admission_missing_or_not_admitted"
    return "dispatch_blocked"


def _dispatch_failed_checks(
    *,
    dispatch_observed: bool,
    process_observed: bool,
    window_observed: bool,
    window_blocked: bool,
    native_window_usable: bool,
    current_codex_touched: bool,
    cleanup_status: str,
) -> list[str]:
    failed: list[str] = []
    if not dispatch_observed:
        failed.append("dispatch_observed_required")
    if not process_observed:
        failed.append("process_observed_required")
    if not window_observed and not window_blocked:
        failed.append("window_observation_or_blocked_reason_required")
    if not native_window_usable:
        failed.append("native_window_usability_required")
    if current_codex_touched:
        failed.append("current_codex_must_remain_untouched")
    if cleanup_status != "ok":
        failed.append("cleanup_or_rollback_ok_required")
    return failed


def _admission_ok(
    admission_packet: dict[str, Any] | None,
    *,
    expected_mode: str,
) -> bool:
    return bool(
        isinstance(admission_packet, dict)
        and admission_packet.get("status") == "ok"
        and admission_packet.get("admitted") is True
        and admission_packet.get("launch_mode") == expected_mode
    )


def _safe_admission_bool(admission_packet: dict[str, Any] | None, field: str) -> bool:
    return bool(isinstance(admission_packet, dict) and admission_packet.get(field) is True)


def _safe_admission_field(admission_packet: dict[str, Any] | None, field: str) -> str:
    if not isinstance(admission_packet, dict):
        return ""
    value = admission_packet.get(field)
    return value if isinstance(value, str) else ""


def _base_packet(*, packet_kind: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": packet_kind,
        "captured_at_utc": utc_now(),
        "dispatch_scope": "custom_first_bounded_dispatch",
        "live_runtime_surface": "bounded_dispatch_only",
        "ui_mutation_performed": False,
        "prompt_attempted": False,
        "route_trace_bound": False,
        "native_launch_complete": False,
        "product_status_upgraded": False,
    }
