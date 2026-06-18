# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .real_custom_codex_hook_proof import (
    COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW,
    HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN,
    HOOK_TRUST_SOURCE_CODEX_EXECUTION,
    ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
    USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX,
    USER_PROMPT_SUBMIT_UNSAFE_CLAIM,
    _hex_sha256,
    _hook_ledger_failures,
    _ledger_file_metadata,
    _runtime_secret_values,
    runtime_context_digest,
)
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths
from .user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    build_user_prompt_submit_readiness_packet,
    hook_ledger_path,
)


REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND = (
    "wbp_real_user_prompt_submit_ledger_proof"
)

REAL_USER_PROMPT_SUBMIT_LEDGER_OK = "OK"
REAL_USER_PROMPT_SUBMIT_LEDGER_INVALID = (
    "WBP_REAL_USER_PROMPT_SUBMIT_LEDGER_INVALID"
)
REAL_USER_PROMPT_SUBMIT_LEDGER_READINESS_NOT_TRUSTED = (
    "WBP_REAL_USER_PROMPT_SUBMIT_LEDGER_READINESS_NOT_TRUSTED"
)
REAL_USER_PROMPT_SUBMIT_LEDGER_TRANSPORT_NOT_HOOK_STDIN = (
    "WBP_REAL_USER_PROMPT_SUBMIT_LEDGER_TRANSPORT_NOT_HOOK_STDIN"
)
REAL_USER_PROMPT_SUBMIT_LEDGER_PROFILE_PATH_INVALID = (
    "WBP_REAL_USER_PROMPT_SUBMIT_LEDGER_PROFILE_PATH_INVALID"
)


def _normalized_path(path: Path) -> str:
    return str(path.expanduser().absolute())


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _readiness_failures(readiness: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if readiness.get("status") != "ok":
        failures.append("hook_readiness_packet_not_ok")
    if readiness.get("machine_error_code") != HOOK_CONFIG_OK:
        failures.append("hook_readiness_machine_error_not_ok")
    for field, reason in (
        ("hook_config_present", "hook_config_missing"),
        ("hook_enabled", "hook_disabled"),
        ("hook_command_path_resolves", "hook_command_path_not_resolved"),
        ("hook_script_executable", "hook_script_not_executable"),
        ("hook_config_digest_bound", "hook_config_digest_not_bound"),
        ("codex_hook_trusted_by_profile_state", "codex_hook_trust_state_not_proven"),
        ("hook_trusted", "hook_untrusted"),
    ):
        if readiness.get(field) is not True:
            failures.append(reason)
    blocking = readiness.get("blocking_reasons")
    if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes)):
        if list(blocking):
            failures.append("hook_readiness_blocking_reasons_not_empty")
    for field, reason in (
        ("raw_prompt_recorded", "readiness_raw_prompt_recorded"),
        ("raw_route_id_recorded", "readiness_raw_route_id_recorded"),
        ("secret_value_exposed", "readiness_secret_value_exposed"),
        ("product_ready", "readiness_product_ready_must_not_be_claimed"),
    ):
        if readiness.get(field) is True:
            failures.append(reason)
    return sorted(set(failures))


def _profile_owned_ledger_failures(
    *,
    paths: RuntimePaths,
    ledger_path: Path,
) -> list[str]:
    expected = _normalized_path(hook_ledger_path(paths))
    actual = _normalized_path(ledger_path)
    return [] if expected == actual else ["hook_ledger_not_profile_owned"]


def _transport_failures(ledger: Mapping[str, Any]) -> list[str]:
    transport = _safe_text(ledger.get("hook_event_transport"), limit=80)
    return [] if transport == "stdin" else ["hook_event_transport_not_stdin"]


def _secret_failures(
    *,
    prompt_text: object,
    runtime_context: Mapping[str, Any],
    ledger: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> list[str]:
    secret_values = [str(prompt_text or ""), *_runtime_secret_values(runtime_context)]
    leaked = packets.command_packet_has_secret_leak(
        {
            "hook_ledger": dict(ledger),
            "hook_readiness": dict(readiness),
        },
        secret_values=secret_values,
    )
    return ["source_file_secret_leak"] if leaked else []


def _machine_error_code(
    *,
    readiness_failures: Sequence[str],
    profile_failures: Sequence[str],
    ledger_failures: Sequence[str],
    unsafe_ledger_failures: Sequence[str],
    transport_failures: Sequence[str],
    secret_failures: Sequence[str],
) -> str:
    if not (
        readiness_failures
        or profile_failures
        or ledger_failures
        or unsafe_ledger_failures
        or transport_failures
        or secret_failures
    ):
        return REAL_USER_PROMPT_SUBMIT_LEDGER_OK
    if unsafe_ledger_failures or secret_failures:
        return USER_PROMPT_SUBMIT_UNSAFE_CLAIM
    if readiness_failures:
        return REAL_USER_PROMPT_SUBMIT_LEDGER_READINESS_NOT_TRUSTED
    if profile_failures:
        return REAL_USER_PROMPT_SUBMIT_LEDGER_PROFILE_PATH_INVALID
    if "origin_state_not_custom_codex_flow_proven" in ledger_failures:
        return USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX
    if transport_failures:
        return REAL_USER_PROMPT_SUBMIT_LEDGER_TRANSPORT_NOT_HOOK_STDIN
    return REAL_USER_PROMPT_SUBMIT_LEDGER_INVALID


def build_real_user_prompt_submit_ledger_proof_packet(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None,
    hook_ledger: Mapping[str, Any] | None,
    readiness_packet: Mapping[str, Any] | None,
    context_file_metadata: Mapping[str, Any] | None = None,
    hook_ledger_file_metadata: Mapping[str, Any] | None = None,
    hook_ledger_file: Path | None = None,
) -> dict[str, Any]:
    context = runtime_context if isinstance(runtime_context, Mapping) else {}
    ledger = hook_ledger if isinstance(hook_ledger, Mapping) else {}
    readiness = readiness_packet if isinstance(readiness_packet, Mapping) else {}
    context_metadata = (
        dict(context_file_metadata)
        if isinstance(context_file_metadata, Mapping)
        else {}
    )
    ledger_metadata = (
        dict(hook_ledger_file_metadata)
        if isinstance(hook_ledger_file_metadata, Mapping)
        else {}
    )
    entry_packet = build_router_hook_entry_packet(
        prompt_text=prompt_text,
        runtime_context=context,
        hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
        secret_values=[str(prompt_text or ""), *_runtime_secret_values(context)],
    )
    expected_prompt_digest = _hex_sha256(entry_packet.get("prompt_digest"))
    expected_context_digest = runtime_context_digest(context)
    ledger_failures, unsafe_ledger_failures = _hook_ledger_failures(
        ledger,
        expected_prompt_digest=expected_prompt_digest,
        expected_runtime_context_digest=expected_context_digest,
        context_file_metadata=context_metadata,
        hook_ledger_file_metadata=ledger_metadata,
    )
    readiness_failures = _readiness_failures(readiness)
    ledger_path = hook_ledger_file or hook_ledger_path(paths)
    profile_failures = _profile_owned_ledger_failures(
        paths=paths,
        ledger_path=ledger_path,
    )
    transport_failures = _transport_failures(ledger)
    secret_failures = _secret_failures(
        prompt_text=prompt_text,
        runtime_context=context,
        ledger=ledger,
        readiness=readiness,
    )
    blocking_reasons = sorted(
        set(
            readiness_failures
            + profile_failures
            + ledger_failures
            + transport_failures
            + secret_failures
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        readiness_failures=readiness_failures,
        profile_failures=profile_failures,
        ledger_failures=ledger_failures,
        unsafe_ledger_failures=unsafe_ledger_failures,
        transport_failures=transport_failures,
        secret_failures=secret_failures,
    )
    trusted_hook_config_sha256 = _hex_sha256(
        ledger.get("trusted_hook_config_sha256")
    )
    loaded_hook_config_sha256 = _hex_sha256(ledger.get("loaded_hook_config_sha256"))
    extra = {
        **context_metadata,
        **ledger_metadata,
        "schema_version": 1,
        "packet_kind": REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        "proof_scope": "trusted_user_prompt_submit_hook_to_file_backed_ledger_only",
        "origin_authentication_scope": (
            "trusted_profile_file_backed_hook_ledger_no_signature"
            if ok
            else "not_proven"
        ),
        "source_file_unforgeable": False,
        "cryptographic_origin_proven": False,
        "does_not_prove_source_file_unforgeable": True,
        "hook_readiness_packet_kind": _safe_text(
            readiness.get("packet_kind"),
            limit=80,
        ),
        "hook_readiness_packet_status": _safe_text(
            readiness.get("status"),
            limit=32,
        ),
        "hook_readiness_machine_error_code": _safe_text(
            readiness.get("machine_error_code"),
            limit=96,
        ),
        "hook_readiness_ok": readiness.get("status") == "ok",
        "hook_config_present": ledger.get("hook_config_present") is True,
        "hook_enabled": ledger.get("hook_enabled") is True,
        "hook_trusted": ledger.get("hook_trusted") is True,
        "hook_hash_current": ledger.get("hook_hash_current") is True,
        "hook_config_digest_bound": bool(
            trusted_hook_config_sha256
            and loaded_hook_config_sha256
            and trusted_hook_config_sha256 == loaded_hook_config_sha256
        ),
        "codex_hook_trusted_by_profile_state": (
            readiness.get("codex_hook_trusted_by_profile_state") is True
        ),
        "codex_hook_trust_state_matches_hook_slot": (
            readiness.get("codex_hook_trust_state_matches_hook_slot") is True
        ),
        "hook_command_path_resolves": (
            readiness.get("hook_command_path_resolves") is True
        ),
        "hook_script_executable": readiness.get("hook_script_executable") is True,
        "trusted_hook_config_sha256": trusted_hook_config_sha256,
        "loaded_hook_config_sha256": loaded_hook_config_sha256,
        "hook_ledger_file_profile_owned": not profile_failures,
        "hook_ledger_packet_kind": _safe_text(ledger.get("packet_kind"), limit=80),
        "hook_ledger_packet_valid": not ledger_failures,
        "hook_producer_ledger_proven": not ledger_failures,
        "real_user_prompt_submit_ledger_proven": ok,
        "hook_producer_state": _safe_text(
            ledger.get("hook_producer_state"),
            limit=80,
        ),
        "hook_producer_state_custom_codex": (
            ledger.get("hook_producer_state") == HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN
        ),
        "origin_state": _safe_text(ledger.get("origin_state"), limit=80),
        "origin_state_custom_codex_flow_proven": (
            ledger.get("origin_state") == ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN
        ),
        "command_origin_surface": (
            COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW if ok else ""
        ),
        "command_origin_proven": ok,
        "custom_codex_flow_proven": ok,
        "custom_codex_origin_proven": ok,
        "native_custom_codex_flow_proven": ok,
        "native_router_hook_observed": ok,
        "user_prompt_submit_hook_observed": ok,
        "user_prompt_submit_hook_ran": ledger.get("user_prompt_submit_hook_ran") is True,
        "hook_ledger_written": ledger.get("hook_ledger_written") is True,
        "hook_event_digest": _hex_sha256(ledger.get("hook_event_digest")),
        "hook_event_transport": _safe_text(
            ledger.get("hook_event_transport"),
            limit=80,
        ),
        "hook_event_transport_stdin": ledger.get("hook_event_transport") == "stdin",
        "hook_trust_source": _safe_text(ledger.get("hook_trust_source"), limit=80),
        "hook_trust_source_codex_execution": (
            ledger.get("hook_trust_source") == HOOK_TRUST_SOURCE_CODEX_EXECUTION
        ),
        "prompt_digest": expected_prompt_digest,
        "hook_prompt_digest": _hex_sha256(ledger.get("prompt_digest")),
        "hook_prompt_digest_bound": (
            _hex_sha256(ledger.get("prompt_digest")) == expected_prompt_digest
            and bool(expected_prompt_digest)
        ),
        "runtime_context_digest": expected_context_digest,
        "hook_runtime_context_digest": _hex_sha256(
            ledger.get("runtime_context_digest")
        ),
        "hook_runtime_context_digest_bound": (
            _hex_sha256(ledger.get("runtime_context_digest"))
            == expected_context_digest
            and bool(expected_context_digest)
        ),
        "thread_digest_present": bool(_hex_sha256(ledger.get("thread_digest"))),
        "turn_digest_present": bool(_hex_sha256(ledger.get("turn_digest"))),
        "thread_or_turn_digest_bound": bool(
            _hex_sha256(ledger.get("thread_digest"))
            or _hex_sha256(ledger.get("turn_digest"))
        ),
        "hook_parent_process_chain_observed": (
            ledger.get("hook_parent_process_chain_observed") is True
        ),
        "hook_parent_process_chain_path_proven": (
            ledger.get("hook_parent_process_chain_path_proven") is True
        ),
        "hook_parent_process_chain_exact_path_classified": (
            ledger.get("hook_parent_process_chain_exact_path_classified") is True
        ),
        "hook_parent_process_chain_digest": _hex_sha256(
            ledger.get("hook_parent_process_chain_digest")
        ),
        "hook_parent_process_chain_length": _safe_int(
            ledger.get("hook_parent_process_chain_length")
        ),
        "hook_parent_process_chain_custom_wbp_clean_app": (
            ledger.get("hook_parent_process_chain_custom_wbp_clean_app") is True
        ),
        "hook_parent_process_chain_app_server": (
            ledger.get("hook_parent_process_chain_app_server") is True
        ),
        "hook_parent_process_chain_clean_root": (
            ledger.get("hook_parent_process_chain_clean_root") is True
        ),
        "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound": (
            ledger.get(
                "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound"
            )
            is True
        ),
        "hook_parent_process_chain_app_server_executable_path_bound": (
            ledger.get("hook_parent_process_chain_app_server_executable_path_bound")
            is True
        ),
        "hook_parent_process_chain_clean_root_executable_path_bound": (
            ledger.get("hook_parent_process_chain_clean_root_executable_path_bound")
            is True
        ),
        "hook_parent_process_chain_stock_codex_app": (
            ledger.get("hook_parent_process_chain_stock_codex_app") is True
        ),
        "hook_parent_process_chain_command_text_substring_only": (
            ledger.get("hook_parent_process_chain_command_text_substring_only") is True
        ),
        "hook_parent_process_raw_lines_recorded": (
            ledger.get("hook_parent_process_raw_lines_recorded") is True
        ),
        "readiness_failures": readiness_failures,
        "profile_failures": profile_failures,
        "hook_ledger_failures": ledger_failures,
        "hook_ledger_unsafe_claim_failures": unsafe_ledger_failures,
        "transport_failures": transport_failures,
        "secret_failures": secret_failures,
        "api_lane_called": False,
        "api_response_received": False,
        "dispatch_attempted": False,
        "dispatch_status": "not_attempted",
        "dispatch_proven": False,
        "route_bound_dispatch_proven": False,
        "provider_response_proven": False,
        "controlled_provider_response_proven": False,
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "does_not_prove_dispatch": True,
        "does_not_prove_handoff": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
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
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a real UserPromptSubmit hook ledger without dispatch."
            if ok
            else "WBP blocked real UserPromptSubmit ledger proof before dispatch."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=[str(prompt_text or ""), *_runtime_secret_values(context)],
        extra=extra,
    )


def run_real_user_prompt_submit_ledger_proof_command(
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
    ledger_path = (
        Path(hook_ledger_file).expanduser()
        if hook_ledger_file
        else hook_ledger_path(paths)
    )
    hook_ledger, ledger_metadata = _ledger_file_metadata(ledger_path)
    readiness_packet = build_user_prompt_submit_readiness_packet(
        paths=paths,
        probe_codex_app_server=True,
    )
    return build_real_user_prompt_submit_ledger_proof_packet(
        paths=paths,
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        hook_ledger=hook_ledger,
        readiness_packet=readiness_packet,
        context_file_metadata=context_metadata,
        hook_ledger_file_metadata=ledger_metadata,
        hook_ledger_file=ledger_path,
    )
