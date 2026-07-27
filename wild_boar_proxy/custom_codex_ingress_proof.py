# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from . import mcp_delegate
from .router_hook_entry import (
    HOOK_SURFACE_PROMPT_PREPROCESSOR,
    ROUTER_HOOK_ENTRY_PACKET_KIND,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND = "wbp_custom_codex_ingress_proof"

CUSTOM_CODEX_INGRESS_NOT_PROVEN = "WBP_CUSTOM_CODEX_INGRESS_NOT_PROVEN"
CUSTOM_CODEX_INGRESS_CODEX_TOOL_CALL_NOT_PROVEN = (
    "WBP_CUSTOM_CODEX_INGRESS_CODEX_TOOL_CALL_NOT_PROVEN"
)
CUSTOM_CODEX_INGRESS_ROUTER_ENTRY_NOT_PROVEN = (
    "WBP_CUSTOM_CODEX_INGRESS_ROUTER_ENTRY_NOT_PROVEN"
)
CUSTOM_CODEX_INGRESS_DIGEST_NOT_BOUND = "WBP_CUSTOM_CODEX_INGRESS_DIGEST_NOT_BOUND"
CUSTOM_CODEX_INGRESS_UNSAFE_SOURCE = "WBP_CUSTOM_CODEX_INGRESS_UNSAFE_SOURCE"
CUSTOM_CODEX_INGRESS_CODEX_SUBAGENT_USED_AS_DIP = (
    "WBP_CUSTOM_CODEX_INGRESS_CODEX_SUBAGENT_USED_AS_DIP"
)

INGRESS_TRUTH_SOURCE_PROVEN = "codex_tool_call_transcript_and_wbp_router_entry"
INGRESS_TRUTH_SOURCE_NOT_PROVEN = "not_proven"


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _prompt_observation_failures(prompt_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if prompt_packet.get("packet_kind") != mcp_delegate.PROMPT_OBSERVATION_PACKET_KIND:
        failures.append("prompt_observation_packet_kind_invalid")
    if prompt_packet.get("prompt_digest_present") is not True:
        failures.append("prompt_digest_missing")
    if not _hex_sha256(prompt_packet.get("prompt_sha256")):
        failures.append("prompt_sha256_missing")
    if prompt_packet.get("raw_prompt_recorded") is True:
        failures.append("raw_prompt_recorded")
    if prompt_packet.get("prompt_text_recorded") is True:
        failures.append("prompt_text_recorded")
    if prompt_packet.get("expected_delegate_arguments_recorded") is True:
        failures.append("expected_delegate_arguments_recorded")
    if prompt_packet.get("raw_backend_details_exposed") is True:
        failures.append("raw_backend_details_exposed")
    if prompt_packet.get("secret_value_exposed") is True:
        failures.append("secret_value_exposed")
    return failures


def _codex_tool_call_failures(codex_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if codex_packet.get("packet_kind") != mcp_delegate.CODEX_EXEC_TOOL_CALL_PACKET_KIND:
        failures.append("codex_tool_call_packet_kind_invalid")
    if codex_packet.get("status") != "ok":
        failures.append("codex_tool_call_packet_not_ok")
    if (
        codex_packet.get("producer_built_by")
        != "build_codex_exec_tool_call_observation_packet"
    ):
        failures.append("codex_tool_call_observation_producer_invalid")
    claim_sha256 = _hex_sha256(codex_packet.get("codex_tool_call_claim_sha256"))
    claim_digest_present = bool(
        codex_packet.get("codex_tool_call_claim_digest_present") is True
        and claim_sha256
    )
    if not claim_digest_present:
        failures.append("codex_tool_call_observation_claim_digest_missing")
    elif (
        claim_sha256
        != mcp_delegate._codex_exec_tool_call_observation_claim_sha256(codex_packet)
    ):
        failures.append("codex_tool_call_observation_claim_digest_mismatch")
    if codex_packet.get("codex_exec_json_events_observed") is not True:
        failures.append("codex_exec_json_events_not_observed")
    if codex_packet.get("real_codex_prompt_executed") is not True:
        failures.append("real_codex_prompt_not_executed")
    if codex_packet.get("delegate_to_dip_tool_called") is not True:
        failures.append("delegate_to_dip_tool_call_not_observed")
    if codex_packet.get("codex_delegate_to_dip_tool_called") is not True:
        failures.append("codex_delegate_to_dip_tool_call_not_observed")
    if codex_packet.get("delegate_to_dip_tool_call_completed") is not True:
        failures.append("delegate_to_dip_tool_call_not_completed")
    if codex_packet.get("delegate_to_dip_tool_call_failed") is True:
        failures.append("delegate_to_dip_tool_call_failed")
    if codex_packet.get("prompt_to_mcp_call_bound") is not True:
        failures.append("prompt_not_bound_to_codex_mcp_tool_call")
    if not _hex_sha256(codex_packet.get("prompt_sha256")):
        failures.append("codex_prompt_sha256_missing")
    if not _hex_sha256(codex_packet.get("tool_call_sha256")):
        failures.append("tool_call_sha256_missing")
    if int(codex_packet.get("browser_authority_field_count") or 0) != 0:
        failures.append("codex_tool_call_forbidden_authority_field")
    return failures


def _router_entry_failures(router_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if router_packet.get("packet_kind") != ROUTER_HOOK_ENTRY_PACKET_KIND:
        failures.append("router_hook_entry_packet_kind_invalid")
    if router_packet.get("status") != "ok":
        failures.append("router_hook_entry_packet_not_ok")
    if router_packet.get("hook_entry_proven") is not True:
        failures.append("router_hook_entry_not_proven")
    if router_packet.get("router_hook_entry_preflight_passed") is not True:
        failures.append("router_hook_entry_preflight_not_passed")
    if router_packet.get("router_hook_entry_no_dispatch_enforced") is not True:
        failures.append("router_hook_entry_no_dispatch_not_enforced")
    if router_packet.get("alias_context_read") is not True:
        failures.append("alias_context_not_read")
    if router_packet.get("alias_bound") is not True:
        failures.append("alias_not_bound")
    if router_packet.get("route_id_allowed") is not True:
        failures.append("route_id_not_allowed")
    if router_packet.get("allowed_api_route_ids_enforced") is not True:
        failures.append("allowed_api_route_ids_not_enforced")
    if int(router_packet.get("forbidden_stale_route_ids_count") or 0) <= 0:
        failures.append("stale_route_guard_missing")
    if not _safe_text(router_packet.get("alias_candidate"), limit=80):
        failures.append("alias_candidate_missing")
    if not _safe_text(router_packet.get("slot_candidate"), limit=80):
        failures.append("slot_candidate_missing")
    if not _hex_sha256(router_packet.get("prompt_digest")):
        failures.append("router_prompt_digest_missing")
    return failures


def _unsafe_source_claim_failures(
    packets_to_scan: Sequence[Mapping[str, Any]],
) -> list[str]:
    checks = {
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "expected_delegate_arguments_recorded": "expected_delegate_arguments_recorded",
        "tool_call_arguments_recorded": "tool_call_arguments_recorded",
        "raw_jsonl_recorded": "raw_jsonl_recorded",
        "raw_stderr_recorded": "raw_stderr_recorded",
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
        "api_lane_called": "api_lane_call_must_not_be_claimed",
        "dispatch_proven": "dispatch_must_not_be_claimed",
        "native_free_chat_router_proven": "native_free_chat_router_must_not_be_claimed",
        "product_ready": "product_ready_must_not_be_claimed",
        "command_origin_proven": "command_origin_must_not_be_claimed",
        "custom_codex_origin_proven": "custom_codex_origin_must_not_be_claimed",
        "native_custom_codex_flow_proven": (
            "native_custom_codex_flow_must_not_be_claimed"
        ),
        "native_router_hook_observed": "native_router_hook_must_not_be_claimed",
        "fallback_used": "fallback_used",
    }
    failures: list[str] = []
    for packet in packets_to_scan:
        for field, reason in checks.items():
            if packet.get(field) is True:
                failures.append(reason)
        if (
            packet.get("local_imitation_used") is True
            or packet.get("codex_subagent_used_as_dip") is True
            or packet.get("local_codex_subagent_used_as_dip") is True
            or packet.get("native_codex_subagent_used_as_dip") is True
        ):
            failures.append("local_imitation_used")
            failures.append("codex_native_subagent_used_as_dip")
    return sorted(set(failures))


def build_custom_codex_ingress_proof_packet(
    *,
    prompt_packet: Mapping[str, Any] | None,
    codex_tool_call_packet: Mapping[str, Any] | None,
    router_hook_entry_packet: Mapping[str, Any] | None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    prompt = prompt_packet if isinstance(prompt_packet, Mapping) else {}
    codex = (
        codex_tool_call_packet if isinstance(codex_tool_call_packet, Mapping) else {}
    )
    router = (
        router_hook_entry_packet if isinstance(router_hook_entry_packet, Mapping) else {}
    )

    prompt_failures = _prompt_observation_failures(prompt)
    codex_failures = _codex_tool_call_failures(codex)
    router_failures = _router_entry_failures(router)
    unsafe_failures = _unsafe_source_claim_failures((prompt, codex, router))

    prompt_digest = _hex_sha256(prompt.get("prompt_sha256"))
    codex_prompt_digest = _hex_sha256(codex.get("prompt_sha256"))
    router_prompt_digest = _hex_sha256(router.get("prompt_digest"))
    prompt_digest_bound_to_codex_tool_call = bool(
        prompt_digest
        and codex_prompt_digest
        and prompt_digest == codex_prompt_digest
        and codex.get("prompt_to_mcp_call_bound") is True
    )
    prompt_digest_bound_to_router_entry = bool(
        prompt_digest and router_prompt_digest and prompt_digest == router_prompt_digest
    )
    prompt_digest_bound_to_ingress = bool(
        prompt_digest_bound_to_codex_tool_call and prompt_digest_bound_to_router_entry
    )
    codex_subagent_used_as_dip = bool(
        codex.get("codex_subagent_used_as_dip") is True
        or codex.get("local_codex_subagent_used_as_dip") is True
        or router.get("native_codex_subagent_used_as_dip") is True
    )
    fallback_used = bool(
        prompt.get("fallback_used") is True
        or codex.get("fallback_used") is True
        or router.get("fallback_used") is True
    )
    local_imitation_used = bool(
        codex_subagent_used_as_dip
        or prompt.get("local_imitation_used") is True
        or codex.get("local_imitation_used") is True
        or router.get("local_imitation_used") is True
    )

    blocking_reasons: list[str] = []
    blocking_reasons.extend(prompt_failures)
    blocking_reasons.extend(codex_failures)
    blocking_reasons.extend(router_failures)
    blocking_reasons.extend(unsafe_failures)
    if not prompt_digest_bound_to_codex_tool_call:
        blocking_reasons.append("prompt_digest_not_bound_to_codex_tool_call")
    if not prompt_digest_bound_to_router_entry:
        blocking_reasons.append("prompt_digest_not_bound_to_router_entry")
    if not prompt_digest_bound_to_ingress:
        blocking_reasons.append("prompt_digest_not_bound_to_ingress")
    blocking_reasons = sorted(set(blocking_reasons))

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif "codex_native_subagent_used_as_dip" in blocking_reasons:
        machine_error_code = CUSTOM_CODEX_INGRESS_CODEX_SUBAGENT_USED_AS_DIP
    elif unsafe_failures:
        machine_error_code = CUSTOM_CODEX_INGRESS_UNSAFE_SOURCE
    elif prompt_failures or codex_failures:
        machine_error_code = CUSTOM_CODEX_INGRESS_CODEX_TOOL_CALL_NOT_PROVEN
    elif router_failures:
        machine_error_code = CUSTOM_CODEX_INGRESS_ROUTER_ENTRY_NOT_PROVEN
    elif not prompt_digest_bound_to_ingress:
        machine_error_code = CUSTOM_CODEX_INGRESS_DIGEST_NOT_BOUND
    else:
        machine_error_code = CUSTOM_CODEX_INGRESS_NOT_PROVEN

    ingress_proven = ok
    extra = {
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND,
        "ingress_proven": ingress_proven,
        "controlled_ingress_proven": ingress_proven,
        "custom_codex_origin_proven": False,
        "codex_tool_call_transcript_observed": (
            codex.get("codex_exec_json_events_observed") is True
        ),
        "mcp_tool_call_observed": codex.get("delegate_to_dip_tool_called") is True,
        "mcp_tool_call_completed": (
            codex.get("delegate_to_dip_tool_call_completed") is True
        ),
        "prompt_packet_kind": _safe_text(prompt.get("packet_kind"), limit=80),
        "codex_tool_call_packet_kind": _safe_text(codex.get("packet_kind"), limit=80),
        "router_hook_entry_packet_kind": _safe_text(
            router.get("packet_kind"),
            limit=80,
        ),
        "prompt_digest": prompt_digest,
        "prompt_digest_present": bool(prompt_digest),
        "prompt_digest_bound_to_codex_tool_call": (
            prompt_digest_bound_to_codex_tool_call
        ),
        "prompt_digest_bound_to_router_entry": prompt_digest_bound_to_router_entry,
        "prompt_digest_bound_to_ingress": prompt_digest_bound_to_ingress,
        "tool_call_digest_present": bool(_hex_sha256(codex.get("tool_call_sha256"))),
        "tool_call_sha256": _hex_sha256(codex.get("tool_call_sha256")),
        "alias_context_read": router.get("alias_context_read") is True,
        "alias_bound": router.get("alias_bound") is True,
        "alias_candidate": _safe_text(router.get("alias_candidate"), limit=80),
        "slot_candidate": _safe_text(router.get("slot_candidate"), limit=80),
        "route_id_allowed": router.get("route_id_allowed") is True,
        "allowed_api_route_ids_enforced": (
            router.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_count": int(
            router.get("allowed_api_route_ids_count") or 0
        ),
        "forbidden_stale_route_ids_enforced": int(
            router.get("forbidden_stale_route_ids_count") or 0
        )
        > 0,
        "forbidden_stale_route_ids_count": int(
            router.get("forbidden_stale_route_ids_count") or 0
        ),
        "wbp_controlled_entry_called": ingress_proven,
        "router_hook_entry_preflight_passed": (
            router.get("router_hook_entry_preflight_passed") is True
        ),
        "codex_native_subagent_used_as_dip": codex_subagent_used_as_dip,
        "local_codex_subagent_used_as_dip": codex_subagent_used_as_dip,
        "fallback_used": fallback_used,
        "local_imitation_used": local_imitation_used,
        "dispatch_proven": False,
        "dispatch_status": "not_attempted",
        "api_lane_called": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_dispatch": True,
        "does_not_prove_api_lane_provider_dispatch": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_custom_codex_origin": True,
        "does_not_prove_product_ready": True,
        "ingress_truth_source": (
            INGRESS_TRUTH_SOURCE_PROVEN
            if ingress_proven
            else INGRESS_TRUTH_SOURCE_NOT_PROVEN
        ),
        "prompt_observation_failures": prompt_failures,
        "codex_tool_call_failures": codex_failures,
        "router_hook_entry_failures": router_failures,
        "source_unsafe_claim_failures": unsafe_failures,
        "blocking_reasons": blocking_reasons,
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
        "browser_can_supply_ingress_authority": False,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a prompt-bound Codex-side MCP ingress into router entry."
            if ok
            else "WBP did not prove Custom Codex ingress into router entry."
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


def run_custom_codex_ingress_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_exec_jsonl_file: str,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_PROMPT_PREPROCESSOR,
) -> dict[str, Any]:
    prompt = str(prompt_text or "")
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    try:
        jsonl_text = jsonl_path.read_text(encoding="utf-8")
    except OSError:
        jsonl_text = ""
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        prompt,
        source="codex_exec_json",
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        jsonl_text,
        prompt_packet=prompt_packet,
    )
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    router_packet = build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=runtime_context,
        hook_surface_kind=hook_surface_kind,
        context_file_metadata=context_metadata,
        secret_values=[prompt],
    )
    packet = build_custom_codex_ingress_proof_packet(
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        router_hook_entry_packet=router_packet,
        secret_values=[prompt],
    )
    packet["codex_exec_jsonl_file_read"] = bool(jsonl_text)
    packet["codex_exec_jsonl_file_path_recorded"] = False
    return packet
