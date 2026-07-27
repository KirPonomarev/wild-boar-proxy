# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .natural_intent_contract import (
    DISPATCH_STATUS_NOT_ATTEMPTED,
    SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
    build_natural_intent_parser_packet,
)
from .runtime import RuntimePaths


ROUTER_HOOK_ENTRY_PACKET_KIND = "wbp_router_hook_entry"
ROUTER_HOOK_ENTRY_SURFACE_NOT_ADMITTED = "WBP_ROUTER_HOOK_SURFACE_NOT_ADMITTED"
ROUTER_HOOK_ENTRY_CONTEXT_FILE_INVALID = "WBP_ROUTER_HOOK_CONTEXT_FILE_INVALID"
ROUTER_HOOK_ENTRY_PARSER_UNSAFE_CLAIM = "WBP_ROUTER_HOOK_PARSER_UNSAFE_CLAIM"

HOOK_SURFACE_PROMPT_PREPROCESSOR = "prompt_preprocessor"
HOOK_SURFACE_USER_PROMPT_SUBMIT = "user_prompt_submit_hook"
HOOK_SURFACE_LAUNCHER_OWNED_BRIDGE = "launcher_owned_bridge"
HOOK_SURFACE_FILE_BRIDGE = "file_bridge"
HOOK_SURFACE_LOCAL_PROOF_COMMAND = "local_proof_command"

ADMITTED_HOOK_SURFACES = frozenset(
    {
        HOOK_SURFACE_PROMPT_PREPROCESSOR,
        HOOK_SURFACE_USER_PROMPT_SUBMIT,
        HOOK_SURFACE_LAUNCHER_OWNED_BRIDGE,
        HOOK_SURFACE_FILE_BRIDGE,
        HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    }
)

RUNTIME_CONTEXT_FILENAME = "wbp-agent-runtime-context.json"

_COMMAND_PACKET_CORE_FIELDS = frozenset(
    packets.COMMAND_PACKET_REQUIRED_FIELDS
    + [
        "effect",
        "human_message",
        "machine_error_code",
        "status",
        "exit_code",
        "liveness",
        "severity",
        "operator_action",
    ]
)
_PARSER_FIELD_DENYLIST = frozenset(
    {
        "api_lane_called",
        "command_origin_proven",
        "custom_codex_flow_proven",
        "custom_codex_origin_proven",
        "custom_codex_ui_visibility_proven",
        "dispatch_proven",
        "dispatch_status",
        "external_live_provider_response_proven",
        "fallback_used",
        "live_provider_proven",
        "live_provider_response_proven",
        "local_imitation_used",
        "native_codex_subagent_used",
        "native_codex_subagent_used_as_dip",
        "native_custom_codex_flow_proven",
        "native_free_chat_router_proven",
        "native_router_hook_observed",
        "product_ready",
        "raw_backend_details_exposed",
        "router_dispatch_admitted",
        "router_owned_dispatch_decision_bound",
        "secret_value_exposed",
        "server_owned_file_bridge",
    }
)
_PARSER_EXPECTED_FIELD_ALLOWLIST = frozenset(
    {
        "alias_bound",
        "alias_candidate",
        "alias_candidate_present",
        "alias_context_read",
        "alias_match_status",
        "allowed_api_route_ids_count",
        "allowed_api_route_ids_enforced",
        "ambiguous_intent",
        "api_lane_called",
        "blocking_reasons",
        "browser_can_supply_route_authority",
        "command_origin_proven",
        "contract_preflight_status",
        "custom_codex_flow_observed",
        "dispatch_proven",
        "dispatch_status",
        "does_not_prove_dispatch",
        "does_not_prove_native_free_chat_router",
        "fallback_used",
        "forbidden_stale_route_ids_count",
        "forbidden_stale_route_ids_enforced",
        "intent_status",
        "lane_candidate",
        "local_imitation_used",
        "native_codex_subagent_used",
        "native_codex_subagent_used_as_dip",
        "native_free_chat_router_proven",
        "natural_alias_command_detected",
        "natural_api_alias_command_detected",
        "natural_phrase_recorded",
        "packet_kind",
        "parser_agent_match_count",
        "parser_alias_match_count",
        "parser_api_alias_match_count",
        "parser_api_target_present",
        "parser_blocking_reasons",
        "parser_does_not_dispatch",
        "parser_primary_address_present",
        "parser_primary_alias_match_count",
        "parser_prompt_text_recorded",
        "parser_raw_prompt_recorded",
        "parser_selected_alias_from_runtime_context",
        "parser_status",
        "parser_target_selection_rule",
        "parser_used",
        "parser_version",
        "product_ready",
        "prompt_digest",
        "prompt_digest_present",
        "prompt_text_recorded",
        "raw_backend_details_exposed",
        "raw_prompt_recorded",
        "route_candidate",
        "route_candidate_present",
        "route_id_allowed",
        "router_dispatch_admitted",
        "router_owned_dispatch_decision_bound",
        "router_preflight_admitted",
        "runtime_context_file_required",
        "runtime_context_kind_valid",
        "runtime_context_present",
        "runtime_context_source",
        "schema_version",
        "secret_value_exposed",
        "slot_candidate",
        "slot_candidate_present",
        "source_surface",
        "source_surface_allowed",
        "source_surface_observed",
        "stale_route_guard_present",
    }
)
_PARSER_UNSAFE_CLAIM_REASONS = {
    "api_lane_called": "parser_api_lane_called",
    "command_origin_proven": "parser_command_origin_proven",
    "custom_codex_flow_proven": "parser_custom_codex_flow_proven",
    "custom_codex_origin_proven": "parser_custom_codex_origin_proven",
    "custom_codex_ui_visibility_proven": "parser_custom_codex_ui_visibility_proven",
    "dispatch_proven": "parser_dispatch_proven",
    "external_live_provider_response_proven": (
        "parser_external_live_provider_response_proven"
    ),
    "fallback_used": "parser_fallback_used",
    "live_provider_proven": "parser_live_provider_proven",
    "live_provider_response_proven": "parser_live_provider_response_proven",
    "local_imitation_used": "parser_local_imitation_used",
    "native_codex_subagent_used": "parser_native_codex_subagent_used",
    "native_codex_subagent_used_as_dip": "parser_native_codex_subagent_used_as_dip",
    "native_custom_codex_flow_proven": "parser_native_custom_codex_flow_proven",
    "native_free_chat_router_proven": "parser_native_free_chat_router_proven",
    "native_router_hook_observed": "parser_native_router_hook_observed",
    "product_ready": "parser_product_ready",
    "raw_backend_details_exposed": "parser_raw_backend_details_exposed",
    "router_dispatch_admitted": "parser_router_dispatch_admitted",
    "router_owned_dispatch_decision_bound": (
        "parser_router_owned_dispatch_decision_bound"
    ),
    "secret_value_exposed": "parser_secret_value_exposed",
    "server_owned_file_bridge": "parser_server_owned_file_bridge",
}


def _safe_text(value: object, *, limit: int = 256) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def runtime_context_path(
    *,
    paths: RuntimePaths,
    runtime_context_file: str | None = None,
) -> Path:
    if runtime_context_file:
        return Path(runtime_context_file).expanduser()
    return paths.profile_dir / RUNTIME_CONTEXT_FILENAME


def load_runtime_context_packet(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "runtime_context_file_required": True,
        "runtime_context_file_present": path.exists(),
        "runtime_context_file_read": False,
        "runtime_context_file_valid_json": False,
        "runtime_context_file_mapping": False,
        "runtime_context_file_error_code": "",
        "runtime_context_file_path_recorded": False,
    }
    if not path.exists():
        metadata["runtime_context_file_error_code"] = "runtime_context_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["runtime_context_file_error_code"] = "runtime_context_file_invalid"
        return {}, metadata
    metadata["runtime_context_file_read"] = True
    metadata["runtime_context_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["runtime_context_file_error_code"] = "runtime_context_file_not_mapping"
        return {}, metadata
    metadata["runtime_context_file_mapping"] = True
    return dict(parsed), metadata


def _parser_unsafe_claim_failures(parser_packet: Mapping[str, Any]) -> list[str]:
    failures = [
        reason
        for field, reason in _PARSER_UNSAFE_CLAIM_REASONS.items()
        if parser_packet.get(field) is True
    ]
    for raw_key in parser_packet:
        key = _safe_text(raw_key, limit=80)
        if (
            key
            and key not in _COMMAND_PACKET_CORE_FIELDS
            and key not in _PARSER_EXPECTED_FIELD_ALLOWLIST
        ):
            failures.append(f"parser_unexpected_field_{key}")
    if parser_packet.get("dispatch_status") not in (
        "",
        DISPATCH_STATUS_NOT_ATTEMPTED,
        None,
    ):
        failures.append("parser_dispatch_status_claimed")
    return sorted(set(failures))


def build_router_hook_entry_packet(
    *,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    context_file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    normalized_surface = _safe_text(hook_surface_kind, limit=80)
    hook_surface_admitted = normalized_surface in ADMITTED_HOOK_SURFACES
    context_metadata = (
        dict(context_file_metadata)
        if isinstance(context_file_metadata, Mapping)
        else {}
    )
    parser_packet = build_natural_intent_parser_packet(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        source_surface=SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
        secret_values=secret_values,
    )
    parser_ok = parser_packet.get("status") == "ok"
    parser_unsafe_claim_failures = _parser_unsafe_claim_failures(parser_packet)
    ok = bool(hook_surface_admitted and parser_ok and not parser_unsafe_claim_failures)
    if ok:
        machine_error_code = "OK"
    elif not hook_surface_admitted:
        machine_error_code = ROUTER_HOOK_ENTRY_SURFACE_NOT_ADMITTED
    elif parser_unsafe_claim_failures:
        machine_error_code = ROUTER_HOOK_ENTRY_PARSER_UNSAFE_CLAIM
    else:
        machine_error_code = str(parser_packet.get("machine_error_code") or "")
    parser_fields = {
        key: value
        for key, value in parser_packet.items()
        if key not in _COMMAND_PACKET_CORE_FIELDS
        and key in _PARSER_EXPECTED_FIELD_ALLOWLIST
        and key not in _PARSER_FIELD_DENYLIST
    }
    parser_no_dispatch_claims = bool(
        parser_packet.get("dispatch_status") == DISPATCH_STATUS_NOT_ATTEMPTED
        and parser_packet.get("api_lane_called") is False
        and parser_packet.get("dispatch_proven") is False
        and parser_packet.get("fallback_used") is False
        and parser_packet.get("local_imitation_used") is False
        and parser_packet.get("native_codex_subagent_used") is False
        and parser_packet.get("native_codex_subagent_used_as_dip") is False
        and parser_packet.get("product_ready") is False
        and parser_packet.get("native_free_chat_router_proven") is False
        and parser_packet.get("does_not_prove_dispatch") is True
        and parser_packet.get("does_not_prove_native_free_chat_router") is True
    )
    no_dispatch_enforced = bool(parser_no_dispatch_claims or parser_unsafe_claim_failures)
    extra = {
        **parser_fields,
        "packet_kind": ROUTER_HOOK_ENTRY_PACKET_KIND,
        "schema_version": 1,
        "hook_entry_observed": hook_surface_admitted,
        "hook_entry_proven": ok,
        "hook_surface_kind": normalized_surface if hook_surface_admitted else "",
        "hook_surface_admitted": hook_surface_admitted,
        "hook_source_kind": "wbp_owned_router_hook_entry",
        "hook_source_effect": EFFECT_PROBE,
        "hook_surface_can_dispatch": False,
        "hook_dispatch_attempted": False,
        "hook_does_not_prove_dispatch": True,
        "hook_does_not_prove_api_lane": True,
        "custom_codex_origin_proven": False,
        "custom_codex_origin_claimed": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
        "parser_packet_kind": parser_packet.get("packet_kind", ""),
        "parser_packet_status": parser_packet.get("status", ""),
        "parser_machine_error_code": parser_packet.get("machine_error_code", ""),
        "parser_unsafe_claim_failures": parser_unsafe_claim_failures,
        "router_hook_entry_result": (
            "preflight_passed"
            if ok
            else "observed_blocked"
            if hook_surface_admitted
            else "blocked"
        ),
        "router_hook_entry_preflight_passed": ok,
        "router_hook_entry_no_dispatch_enforced": no_dispatch_enforced,
        "natural_alias_command_detected": (
            parser_packet.get("natural_alias_command_detected") is True
        ),
        "natural_api_alias_command_detected": (
            parser_packet.get("natural_api_alias_command_detected") is True
        ),
        "router_preflight_admitted": ok,
        "router_dispatch_admitted": False,
        "router_owned_dispatch_decision_bound": False,
        "router_dispatch_decision_scope": "preflight_only_no_dispatch",
        "browser_can_supply_hook_authority": False,
        "browser_can_supply_prompt_authority": False,
        "browser_can_supply_route_authority": False,
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "natural_phrase_recorded": False,
        "dispatch_status": DISPATCH_STATUS_NOT_ATTEMPTED,
        "api_lane_called": False,
        "dispatch_proven": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used": False,
        "native_codex_subagent_used_as_dip": False,
        "command_origin_proven": False,
        "custom_codex_flow_proven": False,
        "custom_codex_origin_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "external_live_provider_response_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_free_chat_router_proven": False,
        "native_router_hook_observed": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "product_ready": False,
        "does_not_prove_dispatch": True,
        "does_not_prove_native_free_chat_router": True,
        "blocking_reasons": sorted(
            set(
                [
                    *(
                        str(reason)
                        for reason in parser_packet.get("blocking_reasons", [])
                    ),
                    *parser_unsafe_claim_failures,
                ]
            )
        ),
        "changed_files": [],
    }
    if context_metadata:
        extra.update(
            {
                "runtime_context_file_required": bool(
                    context_metadata.get("runtime_context_file_required", True)
                ),
                "runtime_context_file_present": bool(
                    context_metadata.get("runtime_context_file_present", False)
                ),
                "runtime_context_file_read": bool(
                    context_metadata.get("runtime_context_file_read", False)
                ),
                "runtime_context_file_valid_json": bool(
                    context_metadata.get("runtime_context_file_valid_json", False)
                ),
                "runtime_context_file_mapping": bool(
                    context_metadata.get("runtime_context_file_mapping", False)
                ),
                "runtime_context_file_error_code": _safe_text(
                    context_metadata.get("runtime_context_file_error_code", ""),
                    limit=80,
                ),
                "runtime_context_file_path_recorded": False,
            }
        )
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP router hook entry observed parser/preflight truth without dispatch."
            if ok
            else "WBP router hook entry blocked before dispatch."
        ),
        machine_error_code=machine_error_code or ROUTER_HOOK_ENTRY_CONTEXT_FILE_INVALID,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_router_hook_entry_command(
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
    return build_router_hook_entry_packet(
        prompt_text=prompt_text,
        runtime_context=context,
        hook_surface_kind=hook_surface_kind,
        context_file_metadata=metadata,
    )
