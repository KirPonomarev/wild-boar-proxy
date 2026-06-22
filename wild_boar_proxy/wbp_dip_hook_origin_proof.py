# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .real_user_prompt_submit_ledger_proof import (
    REAL_USER_PROMPT_SUBMIT_LEDGER_OK,
    REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
)
from .router_hook_entry import _safe_text
from .wbp_dip_tool import WBP_DIP_TOOL_OK, WBP_DIP_TOOL_PACKET_KIND


WBP_DIP_HOOK_ORIGIN_PROOF_PACKET_KIND = "wbp_dip_hook_origin_dispatch_proof"

WBP_DIP_HOOK_ORIGIN_OK = "OK"
WBP_DIP_HOOK_ORIGIN_LEDGER_NOT_PROVEN = (
    "WBP_DIP_HOOK_ORIGIN_LEDGER_NOT_PROVEN"
)
WBP_DIP_HOOK_ORIGIN_DIP_NOT_PROVEN = "WBP_DIP_HOOK_ORIGIN_DIP_NOT_PROVEN"
WBP_DIP_HOOK_ORIGIN_DIGEST_MISMATCH = "WBP_DIP_HOOK_ORIGIN_DIGEST_MISMATCH"
WBP_DIP_HOOK_ORIGIN_ALIAS_MISMATCH = "WBP_DIP_HOOK_ORIGIN_ALIAS_MISMATCH"
WBP_DIP_HOOK_ORIGIN_UNSAFE_SOURCE = "WBP_DIP_HOOK_ORIGIN_UNSAFE_SOURCE"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_nonempty(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(
        list(value)
    )


def _safe_reasons(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _read_json_mapping_file(
    path: Path,
    *,
    prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_required": True,
        f"{prefix}_file_present": path.exists(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_error_code": "",
        f"{prefix}_file_sha256": "",
        f"{prefix}_file_path_recorded": False,
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_sha256"] = hashlib.sha256(raw).hexdigest()
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _ledger_failures(
    ledger: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("ledger_proof_file_read") is not True:
        failures.append("ledger_proof_file_not_read")
    if metadata.get("ledger_proof_file_valid_json") is not True:
        failures.append("ledger_proof_file_json_not_valid")
    if metadata.get("ledger_proof_file_mapping") is not True:
        failures.append("ledger_proof_file_not_mapping")
    if ledger.get("packet_kind") != REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND:
        failures.append("ledger_proof_packet_kind_invalid")
    if ledger.get("status") != "ok":
        failures.append("ledger_proof_not_ok")
    if ledger.get("machine_error_code") != REAL_USER_PROMPT_SUBMIT_LEDGER_OK:
        failures.append("ledger_proof_machine_error_not_ok")
    if ledger.get("effect") != EFFECT_PROBE:
        failures.append("ledger_proof_effect_not_probe")
    if ledger.get("changed_files") not in ([], ()):
        failures.append("ledger_proof_changed_files_not_empty")
    for field, reason in (
        (
            "real_user_prompt_submit_ledger_proven",
            "real_user_prompt_submit_ledger_not_proven",
        ),
        ("custom_codex_flow_proven", "custom_codex_flow_not_proven"),
        ("custom_codex_origin_proven", "custom_codex_origin_not_proven"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        (
            "hook_runtime_context_digest_bound",
            "hook_runtime_context_digest_not_bound",
        ),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("hook_config_digest_bound", "hook_config_digest_not_bound"),
        ("hook_event_transport_stdin", "hook_event_transport_not_stdin"),
    ):
        if ledger.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(ledger.get("prompt_digest")):
        failures.append("ledger_prompt_digest_missing")
    if not _hex_sha256(ledger.get("hook_prompt_digest")):
        failures.append("ledger_hook_prompt_digest_missing")
    if ledger.get("prompt_digest") != ledger.get("hook_prompt_digest"):
        failures.append("ledger_prompt_digest_mismatch")
    if _sequence_nonempty(ledger.get("blocking_reasons")):
        failures.append("ledger_blocking_reasons_not_empty")
    return sorted(set(failures + _safe_reasons(ledger.get("blocking_reasons"))))


def _dip_failures(
    dip: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("wbp_dip_proof_file_read") is not True:
        failures.append("wbp_dip_proof_file_not_read")
    if metadata.get("wbp_dip_proof_file_valid_json") is not True:
        failures.append("wbp_dip_proof_file_json_not_valid")
    if metadata.get("wbp_dip_proof_file_mapping") is not True:
        failures.append("wbp_dip_proof_file_not_mapping")
    if dip.get("packet_kind") != WBP_DIP_TOOL_PACKET_KIND:
        failures.append("wbp_dip_packet_kind_invalid")
    if dip.get("status") != "ok":
        failures.append("wbp_dip_not_ok")
    if dip.get("machine_error_code") != WBP_DIP_TOOL_OK:
        failures.append("wbp_dip_machine_error_not_ok")
    for field, reason in (
        ("delegate_to_dip_proven", "delegate_to_dip_not_proven"),
        ("api_lane_called", "api_lane_not_called"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("live_result_available", "live_result_not_available"),
        ("live_result_provider_called", "live_result_provider_not_called"),
        ("live_result_route_allowed", "live_result_route_not_allowed"),
        ("live_result_required", "live_result_not_required"),
        ("direct_provider_auth_proven", "direct_provider_auth_not_proven"),
        (
            "direct_provider_response_observed",
            "direct_provider_response_not_observed",
        ),
        (
            "positive_provider_proof_gate_satisfied",
            "positive_provider_proof_gate_not_satisfied",
        ),
    ):
        if dip.get(field) is not True:
            failures.append(reason)
    if dip.get("bridge_green_counts_as_provider_proof") is not False:
        failures.append("bridge_green_counts_as_provider_proof_not_false")
    if dip.get("live_result_bridge_or_file_bridge_used") is True:
        failures.append("bridge_or_file_bridge_used_for_direct_provider_proof")
    if not _hex_sha256(dip.get("task_sha256")):
        failures.append("wbp_dip_task_digest_missing")
    if not _hex_sha256(dip.get("live_result_text_sha256")):
        failures.append("wbp_dip_live_result_digest_missing")
    if _sequence_nonempty(dip.get("blocking_reasons")):
        failures.append("wbp_dip_blocking_reasons_not_empty")
    return sorted(set(failures + _safe_reasons(dip.get("blocking_reasons"))))


def _unsafe_claim_failures(
    packet: Mapping[str, Any],
    *,
    prefix: str,
    allow_custom_origin: bool = False,
    allow_live_result_text: bool = False,
) -> list[str]:
    checks = {
        "product_ready": "product_ready",
        "custom_codex_ui_visibility_proven": "custom_codex_ui_visibility_proven",
        "delivery_counts_as_custom_codex_ui": "delivery_counts_as_custom_ui",
        "native_free_chat_router_proven": "native_free_chat_router_proven",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "raw_task_recorded": "raw_task_recorded",
        "tool_call_arguments_recorded": "tool_call_arguments_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "raw_route_id_recorded": "raw_route_id_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "live_result_route_id_recorded": "live_result_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "live_result_raw_backend_details_exposed": (
            "live_result_raw_backend_details_exposed"
        ),
        "live_result_secret_value_exposed": "live_result_secret_value_exposed",
        "command_argv_recorded": "command_argv_recorded",
        "codex_stdout_recorded": "codex_stdout_recorded",
        "codex_stderr_recorded": "codex_stderr_recorded",
    }
    if not allow_custom_origin:
        checks.update(
            {
                "custom_codex_flow_proven": "custom_codex_flow_proven",
                "custom_codex_origin_proven": "custom_codex_origin_proven",
                "native_custom_codex_flow_proven": "native_custom_codex_flow_proven",
                "native_router_hook_observed": "native_router_hook_observed",
            }
        )
    if not allow_live_result_text:
        checks["live_result_text_recorded"] = "live_result_text_recorded"
    return sorted(
        {
            f"{prefix}_{reason}"
            for field, reason in checks.items()
            if packet.get(field) is True
        }
    )


def _machine_error_code(
    *,
    ledger_failures: Sequence[str],
    dip_failures: Sequence[str],
    digest_failures: Sequence[str],
    alias_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if not (
        ledger_failures
        or dip_failures
        or digest_failures
        or alias_failures
        or unsafe_failures
    ):
        return WBP_DIP_HOOK_ORIGIN_OK
    if unsafe_failures:
        return WBP_DIP_HOOK_ORIGIN_UNSAFE_SOURCE
    if ledger_failures:
        return WBP_DIP_HOOK_ORIGIN_LEDGER_NOT_PROVEN
    if dip_failures:
        return WBP_DIP_HOOK_ORIGIN_DIP_NOT_PROVEN
    if digest_failures:
        return WBP_DIP_HOOK_ORIGIN_DIGEST_MISMATCH
    return WBP_DIP_HOOK_ORIGIN_ALIAS_MISMATCH


def build_wbp_dip_hook_origin_proof_packet(
    *,
    prompt_text: object,
    expected_alias: object = "DIP",
    ledger_proof_packet: Mapping[str, Any] | None,
    wbp_dip_packet: Mapping[str, Any] | None,
    ledger_proof_file_metadata: Mapping[str, Any] | None = None,
    wbp_dip_file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    ledger = _mapping(ledger_proof_packet)
    dip = _mapping(wbp_dip_packet)
    ledger_metadata = dict(ledger_proof_file_metadata or {})
    dip_metadata = dict(wbp_dip_file_metadata or {})
    prompt = _safe_text(prompt_text, limit=8192)
    alias = _safe_text(expected_alias, limit=80) or "DIP"
    expected_prompt_digest = _sha256_text(prompt) if prompt else ""
    ledger_prompt_digest = _hex_sha256(ledger.get("prompt_digest"))
    dip_task_digest = _hex_sha256(dip.get("task_sha256"))
    ledger_errors = _ledger_failures(ledger, ledger_metadata)
    dip_errors = _dip_failures(dip, dip_metadata)
    digest_failures: list[str] = []
    if not expected_prompt_digest:
        digest_failures.append("expected_prompt_digest_missing")
    if ledger_prompt_digest != expected_prompt_digest:
        digest_failures.append("ledger_prompt_digest_not_bound_to_prompt")
    if dip_task_digest != expected_prompt_digest:
        digest_failures.append("wbp_dip_task_digest_not_bound_to_prompt")
    alias_failures = []
    if _safe_text(dip.get("expected_alias"), limit=80) != alias:
        alias_failures.append("wbp_dip_expected_alias_mismatch")
    unsafe_failures = sorted(
        set(
            _unsafe_claim_failures(
                ledger,
                prefix="ledger",
                allow_custom_origin=True,
            )
            + _unsafe_claim_failures(
                dip,
                prefix="wbp_dip",
                allow_live_result_text=True,
            )
        )
    )
    secret_list = list(secret_values or []) + [str(prompt_text or "")]
    if packets.command_packet_has_secret_leak(
        {"ledger": dict(ledger), "wbp_dip": dict(dip)},
        secret_values=secret_list,
    ):
        unsafe_failures.append("source_file_secret_leak")
    blocking_reasons = sorted(
        set(
            ledger_errors
            + dip_errors
            + digest_failures
            + alias_failures
            + unsafe_failures
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        ledger_failures=ledger_errors,
        dip_failures=dip_errors,
        digest_failures=digest_failures,
        alias_failures=alias_failures,
        unsafe_failures=unsafe_failures,
    )
    live_result_text_sha256 = _hex_sha256(dip.get("live_result_text_sha256"))
    extra = {
        **ledger_metadata,
        **dip_metadata,
        "schema_version": 1,
        "packet_kind": WBP_DIP_HOOK_ORIGIN_PROOF_PACKET_KIND,
        "proof_scope": "real_user_prompt_submit_hook_origin_to_wbp_dip_live_dispatch",
        "origin_authentication_scope": "trusted_profile_file_backed_hook_ledger_no_signature"
        if ok
        else "not_proven",
        "source_file_unforgeable": False,
        "cryptographic_origin_proven": False,
        "does_not_prove_source_file_unforgeable": True,
        "ledger_proof_packet_kind": _safe_text(ledger.get("packet_kind"), limit=80),
        "ledger_proof_status": _safe_text(ledger.get("status"), limit=32),
        "ledger_proof_machine_error_code": _safe_text(
            ledger.get("machine_error_code"),
            limit=96,
        ),
        "wbp_dip_packet_kind": _safe_text(dip.get("packet_kind"), limit=80),
        "wbp_dip_status": _safe_text(dip.get("status"), limit=32),
        "wbp_dip_machine_error_code": _safe_text(
            dip.get("machine_error_code"),
            limit=96,
        ),
        "custom_codex_flow_proven": bool(
            ok and ledger.get("custom_codex_flow_proven") is True
        ),
        "custom_codex_origin_proven": bool(
            ok and ledger.get("custom_codex_origin_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and ledger.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_ledger_written": bool(ok and ledger.get("hook_ledger_written") is True),
        "hook_prompt_digest_bound": bool(
            ok and ledger.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and ledger.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": bool(
            ok and ledger.get("thread_or_turn_digest_bound") is True
        ),
        "prompt_digest": expected_prompt_digest if ok else "",
        "hook_prompt_digest": ledger_prompt_digest if ok else "",
        "prompt_digest_bound_to_hook_ledger": bool(
            ok and ledger_prompt_digest == expected_prompt_digest
        ),
        "prompt_digest_bound_to_wbp_dip_task": bool(
            ok and dip_task_digest == expected_prompt_digest
        ),
        "expected_alias": alias if ok else "",
        "selected_alias": _safe_text(dip.get("expected_alias"), limit=80) if ok else "",
        "expected_alias_bound": bool(ok and not alias_failures),
        "delegate_to_dip_proven": bool(ok and dip.get("delegate_to_dip_proven") is True),
        "api_lane_called": bool(ok and dip.get("api_lane_called") is True),
        "route_bound_dispatch_proven": bool(
            ok and dip.get("route_bound_dispatch_proven") is True
        ),
        "live_result_available": bool(ok and dip.get("live_result_available") is True),
        "live_result_provider_called": bool(
            ok and dip.get("live_result_provider_called") is True
        ),
        "direct_provider_auth_proven": bool(
            ok and dip.get("direct_provider_auth_proven") is True
        ),
        "direct_provider_response_observed": bool(
            ok and dip.get("direct_provider_response_observed") is True
        ),
        "provider_auth_ok": bool(ok and dip.get("provider_auth_ok") is True),
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": bool(
            ok and dip.get("positive_provider_proof_gate_satisfied") is True
        ),
        "live_result_bridge_or_file_bridge_used": bool(
            ok and dip.get("live_result_bridge_or_file_bridge_used") is True
        ),
        "live_result_runtime_context_bridge_used": bool(
            ok and dip.get("live_result_runtime_context_bridge_used") is True
        ),
        "live_result_runtime_context_file_bridge_used": bool(
            ok and dip.get("live_result_runtime_context_file_bridge_used") is True
        ),
        "live_result_bridge_attempted": bool(
            ok and dip.get("live_result_bridge_attempted") is True
        ),
        "live_result_file_bridge_attempted": bool(
            ok and dip.get("live_result_file_bridge_attempted") is True
        ),
        "live_result_route_allowed": bool(
            ok and dip.get("live_result_route_allowed") is True
        ),
        "live_result_route_id_recorded": False,
        "live_result_text_recorded": False,
        "live_result_text_sha256": live_result_text_sha256 if ok else "",
        "live_result_text_length": int(dip.get("live_result_text_length") or 0)
        if ok
        else 0,
        "live_result_digest_bound": bool(ok and live_result_text_sha256),
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": not unsafe_failures,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "ledger_failures": ledger_errors,
        "wbp_dip_failures": dip_errors,
        "digest_failures": digest_failures,
        "alias_failures": alias_failures,
        "unsafe_source_failures": sorted(set(unsafe_failures)),
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved real UserPromptSubmit hook origin joined to wbp_dip live dispatch."
            if ok
            else "WBP blocked hook-origin to wbp_dip dispatch proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=secret_list,
        extra=extra,
    )


def run_wbp_dip_hook_origin_proof_command(
    *,
    prompt_text: object,
    ledger_proof_file: str,
    wbp_dip_proof_file: str,
    expected_alias: object = "DIP",
) -> dict[str, Any]:
    ledger_packet, ledger_metadata = _read_json_mapping_file(
        Path(ledger_proof_file).expanduser(),
        prefix="ledger_proof",
    )
    dip_packet, dip_metadata = _read_json_mapping_file(
        Path(wbp_dip_proof_file).expanduser(),
        prefix="wbp_dip_proof",
    )
    return build_wbp_dip_hook_origin_proof_packet(
        prompt_text=prompt_text,
        expected_alias=expected_alias,
        ledger_proof_packet=ledger_packet,
        wbp_dip_packet=dip_packet,
        ledger_proof_file_metadata=ledger_metadata,
        wbp_dip_file_metadata=dip_metadata,
    )
