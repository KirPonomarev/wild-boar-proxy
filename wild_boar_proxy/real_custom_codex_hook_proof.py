# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

from .approved_handoff import (
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    build_approved_handoff_packet,
    _safe_handoff_payload,
)
from .command_effects import EFFECT_PROBE
from .controlled_api_dispatch import (
    CONTROLLED_API_DISPATCH_PACKET_KIND,
    build_controlled_api_dispatch_packet,
)
from .core import packets
from .external_models import run_external_models_command
from .observed_machine_handoff_delivery import (
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    build_observed_machine_handoff_delivery_packet,
)
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    build_router_hook_entry_packet,
    _safe_text,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND = "wbp_real_custom_codex_hook_proof"
USER_PROMPT_SUBMIT_HOOK_LEDGER_PACKET_KIND = "wbp_user_prompt_submit_hook_ledger"

ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN = "custom_codex_flow_proven"
ORIGIN_STATE_CONTROLLED_CODEX_EXEC_FLOW = "controlled_codex_exec_flow"
ORIGIN_STATE_APP_SERVER_CHILD_FLOW = "app_server_child_flow"
ORIGIN_STATE_SYNTHETIC_HOOK_FLOW = "synthetic_hook_flow"
ORIGIN_STATE_BLOCKED_ORIGIN_UNPROVEN = "blocked_origin_unproven"

COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW = "custom_codex_flow"
HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN = "HOOK_RAN_CUSTOM_CODEX_PROVEN"
HOOK_TRUST_SOURCE_CODEX_EXECUTION = "codex_non_managed_hook_execution"

ALLOWED_ORIGIN_STATES = frozenset(
    {
        ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
        ORIGIN_STATE_CONTROLLED_CODEX_EXEC_FLOW,
        ORIGIN_STATE_APP_SERVER_CHILD_FLOW,
        ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
        ORIGIN_STATE_BLOCKED_ORIGIN_UNPROVEN,
    }
)

USER_PROMPT_SUBMIT_LEDGER_MISSING = "WBP_USER_PROMPT_SUBMIT_LEDGER_MISSING"
USER_PROMPT_SUBMIT_LEDGER_INVALID = "WBP_USER_PROMPT_SUBMIT_LEDGER_INVALID"
USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN = "WBP_USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN"
USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX = (
    "WBP_USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX"
)
USER_PROMPT_SUBMIT_UNSAFE_CLAIM = "WBP_USER_PROMPT_SUBMIT_UNSAFE_CLAIM"
USER_PROMPT_SUBMIT_DISPATCH_NOT_PROVEN = "WBP_USER_PROMPT_SUBMIT_DISPATCH_NOT_PROVEN"
USER_PROMPT_SUBMIT_HANDOFF_NOT_PROVEN = "WBP_USER_PROMPT_SUBMIT_HANDOFF_NOT_PROVEN"
USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN = (
    "WBP_USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN"
)

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

_EXPECTED_TEXT_MARKER_RE = re.compile(r"^[A-Z0-9_]{1,128}$")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_mapping_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(encoded)


def runtime_context_digest(runtime_context: Mapping[str, Any] | None) -> str:
    if not isinstance(runtime_context, Mapping):
        return ""
    return _canonical_mapping_digest(runtime_context)


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _runtime_secret_values(runtime_context: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(runtime_context, Mapping):
        return []
    values: list[str] = []
    for route_id in runtime_context.get("allowed_api_route_ids", []):
        if isinstance(route_id, str) and route_id:
            values.append(route_id)
    routes = runtime_context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        for route_id in routes.values():
            if isinstance(route_id, str) and route_id:
                values.append(route_id)
    return sorted(set(values))


def build_user_prompt_submit_hook_ledger(
    *,
    prompt_digest: str,
    runtime_context_digest_value: str,
    origin_state: str = ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
    thread_digest: str = "",
    turn_digest: str = "",
    trusted_hook_config_sha256: str = "",
    loaded_hook_config_sha256: str = "",
    hook_config_present: bool = True,
    hook_enabled: bool = True,
    hook_trusted: bool = True,
    hook_hash_current: bool = True,
    hook_runnable: bool = True,
    user_prompt_submit_hook_ran: bool = True,
    hook_ledger_written: bool = True,
    hook_producer_state: str = "",
    hook_event_digest: str = "",
    session_digest: str = "",
    cwd_digest: str = "",
    admission_run_id_digest: str = "",
    hook_trust_source: str = "",
    hook_event_transport: str = "",
    hook_parent_process_chain_digest: str = "",
    hook_parent_process_chain_length: int = 0,
    hook_parent_process_chain_observed: bool = False,
    hook_parent_process_chain_path_proven: bool = False,
    hook_parent_process_chain_exact_path_classified: bool = False,
    hook_parent_process_chain_custom_wbp_clean_app: bool = False,
    hook_parent_process_chain_app_server: bool = False,
    hook_parent_process_chain_clean_root: bool = False,
    hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound: bool = False,
    hook_parent_process_chain_app_server_executable_path_bound: bool = False,
    hook_parent_process_chain_clean_root_executable_path_bound: bool = False,
    hook_parent_process_chain_stock_codex_app: bool = False,
    hook_parent_process_chain_command_text_substring_only: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": USER_PROMPT_SUBMIT_HOOK_LEDGER_PACKET_KIND,
        "origin_state": origin_state,
        "hook_event_name": "UserPromptSubmit",
        "hook_source_kind": "wbp_owned_user_prompt_submit_hook",
        "hook_config_present": bool(hook_config_present),
        "hook_enabled": bool(hook_enabled),
        "hook_trusted": bool(hook_trusted),
        "hook_hash_current": bool(hook_hash_current),
        "hook_runnable": bool(hook_runnable),
        "user_prompt_submit_hook_ran": bool(user_prompt_submit_hook_ran),
        "hook_ledger_written": bool(hook_ledger_written),
        "hook_producer_state": _safe_text(hook_producer_state, limit=80),
        "hook_event_digest": _hex_sha256(hook_event_digest),
        "hook_event_transport": _safe_text(hook_event_transport, limit=80),
        "session_digest": _hex_sha256(session_digest),
        "cwd_digest": _hex_sha256(cwd_digest),
        "admission_run_id_digest": _hex_sha256(admission_run_id_digest),
        "hook_parent_process_chain_digest": _hex_sha256(
            hook_parent_process_chain_digest
        ),
        "hook_parent_process_chain_length": max(
            0,
            int(hook_parent_process_chain_length or 0),
        ),
        "hook_parent_process_chain_observed": bool(
            hook_parent_process_chain_observed
        ),
        "hook_parent_process_chain_path_proven": bool(
            hook_parent_process_chain_path_proven
        ),
        "hook_parent_process_chain_exact_path_classified": bool(
            hook_parent_process_chain_exact_path_classified
        ),
        "hook_parent_process_chain_custom_wbp_clean_app": bool(
            hook_parent_process_chain_custom_wbp_clean_app
        ),
        "hook_parent_process_chain_app_server": bool(
            hook_parent_process_chain_app_server
        ),
        "hook_parent_process_chain_clean_root": bool(
            hook_parent_process_chain_clean_root
        ),
        "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound": bool(
            hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound
        ),
        "hook_parent_process_chain_app_server_executable_path_bound": bool(
            hook_parent_process_chain_app_server_executable_path_bound
        ),
        "hook_parent_process_chain_clean_root_executable_path_bound": bool(
            hook_parent_process_chain_clean_root_executable_path_bound
        ),
        "hook_parent_process_chain_stock_codex_app": bool(
            hook_parent_process_chain_stock_codex_app
        ),
        "hook_parent_process_chain_command_text_substring_only": bool(
            hook_parent_process_chain_command_text_substring_only
        ),
        "hook_parent_process_raw_lines_recorded": False,
        "hook_trust_source": _safe_text(hook_trust_source, limit=80),
        "trusted_hook_config_sha256": _hex_sha256(trusted_hook_config_sha256),
        "loaded_hook_config_sha256": _hex_sha256(loaded_hook_config_sha256),
        "prompt_digest": _hex_sha256(prompt_digest),
        "runtime_context_digest": _hex_sha256(runtime_context_digest_value),
        "thread_digest": _hex_sha256(thread_digest),
        "turn_digest": _hex_sha256(turn_digest),
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
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
    }


def _ledger_file_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "hook_ledger_file_required": True,
        "hook_ledger_file_present": path.exists(),
        "hook_ledger_file_read": False,
        "hook_ledger_file_valid_json": False,
        "hook_ledger_file_mapping": False,
        "hook_ledger_file_error_code": "",
        "hook_ledger_file_path_recorded": False,
    }
    if not path.exists():
        metadata["hook_ledger_file_error_code"] = "hook_ledger_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["hook_ledger_file_error_code"] = "hook_ledger_file_invalid"
        return {}, metadata
    metadata["hook_ledger_file_read"] = True
    metadata["hook_ledger_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["hook_ledger_file_error_code"] = "hook_ledger_file_not_mapping"
        return {}, metadata
    metadata["hook_ledger_file_mapping"] = True
    return dict(parsed), metadata


def _packet_file_metadata(
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
        f"{prefix}_file_path_recorded": False,
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _unsafe_ledger_claim_failures(ledger: Mapping[str, Any]) -> list[str]:
    checks = {
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
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "command_origin_proven": "ledger_must_not_preclaim_command_origin",
        "custom_codex_origin_proven": "ledger_must_not_preclaim_custom_origin",
        "native_custom_codex_flow_proven": "ledger_must_not_preclaim_native_flow",
        "native_router_hook_observed": "ledger_must_not_preclaim_native_hook",
        "custom_codex_ui_visibility_proven": "custom_codex_ui_visibility_must_not_be_claimed",
        "codex_working_flow_delivery_proven": "codex_working_flow_delivery_must_not_be_claimed",
        "delivery_counts_as_custom_codex_ui": "delivery_counts_as_custom_ui_must_not_be_claimed",
        "native_free_chat_router_proven": "native_free_chat_router_must_not_be_claimed",
        "live_provider_proven": "live_provider_must_not_be_claimed",
        "live_provider_response_proven": "live_provider_response_must_not_be_claimed",
        "external_live_provider_response_proven": (
            "external_live_provider_response_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
    }
    failures = [
        reason
        for field, reason in checks.items()
        if ledger.get(field) is True
    ]
    origin_state = _safe_text(ledger.get("origin_state"), limit=80)
    command_origin_surface = _safe_text(
        ledger.get("command_origin_surface"),
        limit=80,
    )
    if (
        command_origin_surface == COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW
        and origin_state != ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN
    ):
        failures.append("custom_origin_surface_claim_without_custom_origin")
    return sorted(set(failures))


def _hook_ledger_failures(
    ledger: Mapping[str, Any],
    *,
    expected_prompt_digest: str,
    expected_runtime_context_digest: str,
    context_file_metadata: Mapping[str, Any],
    hook_ledger_file_metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unsafe_failures = _unsafe_ledger_claim_failures(ledger)
    if hook_ledger_file_metadata.get("hook_ledger_file_read") is not True:
        failures.append("hook_ledger_file_not_read")
    if hook_ledger_file_metadata.get("hook_ledger_file_valid_json") is not True:
        failures.append("hook_ledger_file_json_not_valid")
    if hook_ledger_file_metadata.get("hook_ledger_file_mapping") is not True:
        failures.append("hook_ledger_file_not_mapping")
    if context_file_metadata.get("runtime_context_file_read") is not True:
        failures.append("runtime_context_file_not_read")
    if context_file_metadata.get("runtime_context_file_valid_json") is not True:
        failures.append("runtime_context_file_json_not_valid")
    if context_file_metadata.get("runtime_context_file_mapping") is not True:
        failures.append("runtime_context_file_not_mapping")
    if ledger.get("packet_kind") != USER_PROMPT_SUBMIT_HOOK_LEDGER_PACKET_KIND:
        failures.append("hook_ledger_packet_kind_invalid")
    if ledger.get("schema_version") != 1:
        failures.append("hook_ledger_schema_version_invalid")
    if ledger.get("hook_event_name") != "UserPromptSubmit":
        failures.append("hook_event_name_invalid")
    origin_state = _safe_text(ledger.get("origin_state"), limit=80)
    if origin_state not in ALLOWED_ORIGIN_STATES:
        failures.append("origin_state_not_allowed")
    if origin_state != ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN:
        failures.append("origin_state_not_custom_codex_flow_proven")
    hook_producer_state = _safe_text(ledger.get("hook_producer_state"), limit=80)
    if hook_producer_state != HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN:
        failures.append("hook_producer_state_not_custom_codex_proven")
    if not _hex_sha256(ledger.get("hook_event_digest")):
        failures.append("hook_event_digest_missing")
    if (
        _safe_text(ledger.get("hook_trust_source"), limit=80)
        != HOOK_TRUST_SOURCE_CODEX_EXECUTION
    ):
        failures.append("hook_trust_source_not_codex_execution")
    for field, reason in (
        ("hook_config_present", "hook_config_missing"),
        ("hook_enabled", "hook_disabled"),
        ("hook_trusted", "hook_untrusted"),
        ("hook_hash_current", "hook_hash_not_current"),
        ("hook_runnable", "hook_not_runnable"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
    ):
        if ledger.get(field) is not True:
            failures.append(reason)
    trusted_hash = _hex_sha256(ledger.get("trusted_hook_config_sha256"))
    loaded_hash = _hex_sha256(ledger.get("loaded_hook_config_sha256"))
    if not trusted_hash:
        failures.append("trusted_hook_config_digest_missing")
    if not loaded_hash:
        failures.append("loaded_hook_config_digest_missing")
    if trusted_hash and loaded_hash and trusted_hash != loaded_hash:
        failures.append("hook_config_digest_mismatch")
    prompt_digest = _hex_sha256(ledger.get("prompt_digest"))
    if not prompt_digest:
        failures.append("hook_prompt_digest_missing")
    elif prompt_digest != expected_prompt_digest:
        failures.append("hook_prompt_digest_mismatch")
    context_digest = _hex_sha256(ledger.get("runtime_context_digest"))
    if not context_digest:
        failures.append("hook_runtime_context_digest_missing")
    elif context_digest != expected_runtime_context_digest:
        failures.append("hook_runtime_context_digest_mismatch")
    thread_digest = _hex_sha256(ledger.get("thread_digest"))
    turn_digest = _hex_sha256(ledger.get("turn_digest"))
    if not thread_digest or not turn_digest:
        failures.append("thread_or_turn_digest_missing")
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures


def _dispatch_failures(dispatch_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch_packet.get("packet_kind") != CONTROLLED_API_DISPATCH_PACKET_KIND:
        failures.append("dispatch_packet_kind_invalid")
    if dispatch_packet.get("status") != "ok":
        failures.append("dispatch_packet_not_ok")
    if dispatch_packet.get("machine_error_code") != "OK":
        failures.append("dispatch_machine_error_not_ok")
    for field, reason in (
        ("hook_entry_proven", "hook_entry_not_proven"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("controlled_provider_response_proven", "controlled_provider_response_not_proven"),
        ("provider_response_proven", "provider_response_not_proven"),
    ):
        if dispatch_packet.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("fallback_used", "fallback_used"),
        ("local_imitation_used", "local_imitation_used"),
        ("native_codex_subagent_used_as_dip", "native_codex_subagent_used_as_dip"),
        ("raw_prompt_recorded", "raw_prompt_recorded"),
        ("prompt_text_recorded", "prompt_text_recorded"),
        ("natural_phrase_recorded", "natural_phrase_recorded"),
        ("raw_route_id_recorded", "raw_route_id_recorded"),
        ("selected_api_route_id_recorded", "selected_api_route_id_recorded"),
        ("raw_backend_details_exposed", "raw_backend_details_exposed"),
        ("secret_value_exposed", "secret_value_exposed"),
        ("product_ready", "dispatch_must_not_claim_product_ready"),
        ("native_free_chat_router_proven", "dispatch_must_not_claim_native_router"),
    ):
        if dispatch_packet.get(field) is True:
            failures.append(reason)
    return sorted(set(failures))


def _handoff_failures(
    approved_packet: Mapping[str, Any],
    delivery_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if approved_packet.get("status") != "ok":
        failures.append("approved_handoff_not_ok")
    if approved_packet.get("handoff_ready") is not True:
        failures.append("approved_handoff_not_ready")
    if approved_packet.get("handoff_payload_sanitized") is not True:
        failures.append("approved_handoff_payload_not_sanitized")
    if delivery_packet.get("status") != "ok":
        failures.append("observed_handoff_not_ok")
    for field, reason in (
        ("delivery_surface_observed", "delivery_surface_not_observed"),
        ("machine_response_envelope_observed", "machine_response_envelope_not_observed"),
        ("machine_response_structured_content_present", "machine_response_structured_content_missing"),
        ("delivery_payload_digest_matches_approved_handoff", "delivery_payload_digest_mismatch"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
    ):
        if delivery_packet.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("machine_response_content_text_recorded", "machine_response_content_text_recorded"),
        ("machine_response_raw_recorded", "machine_response_raw_recorded"),
        ("delivery_counts_as_custom_codex_ui", "delivery_counts_as_custom_ui_must_not_be_claimed"),
        ("delivery_counts_as_native_free_chat_router", "delivery_counts_as_native_router_must_not_be_claimed"),
        ("delivery_counts_as_product_ready", "delivery_counts_as_product_ready_must_not_be_claimed"),
    ):
        if delivery_packet.get(field) is True:
            failures.append(reason)
    return sorted(set(failures))


def _selected_route_id_from_context(
    runtime_context: Mapping[str, Any],
    dispatch_packet: Mapping[str, Any],
) -> str:
    slot = _safe_text(dispatch_packet.get("selected_slot"), limit=64)
    agent_routes = runtime_context.get("agent_id_to_route")
    if isinstance(agent_routes, Mapping):
        route_id = agent_routes.get(slot)
        if isinstance(route_id, str) and route_id:
            return route_id
    bindings = runtime_context.get("agent_bindings")
    if isinstance(bindings, Sequence) and not isinstance(bindings, (str, bytes)):
        for binding in bindings:
            if not isinstance(binding, Mapping):
                continue
            if _safe_text(binding.get("agent_id"), limit=64) != slot:
                continue
            route_id = binding.get("route_id")
            if isinstance(route_id, str) and route_id:
                return route_id
    return ""


def _runtime_context_declares_live_cli(
    runtime_context: Mapping[str, Any],
    route_id: str,
) -> tuple[bool, bool]:
    command_parts = _runtime_context_live_cli_command_parts(runtime_context)
    if not command_parts:
        return False, False
    declared = bool(
        "external-models" in command_parts
        and "live-format-check" in command_parts
        and "--json" in command_parts
    )
    route_bound = False
    if declared and route_id:
        for index, part in enumerate(command_parts[:-1]):
            if part == "--route" and command_parts[index + 1] == route_id:
                route_bound = True
                break
    return declared, route_bound


def _runtime_context_live_cli_command_parts(
    runtime_context: Mapping[str, Any],
) -> list[str]:
    command = runtime_context.get("deepseek_live_format_check_cli_command")
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
        return []
    return [str(part) for part in command]


def _command_parts_sha256(command_parts: Sequence[str]) -> str:
    if not command_parts:
        return ""
    payload = json.dumps(
        list(command_parts),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return _sha256_text(payload)


def _is_safe_expected_text_marker(value: str) -> bool:
    return bool(_EXPECTED_TEXT_MARKER_RE.fullmatch(value))


def _live_provider_packet_unsafe_failures(
    live_provider_packet: Mapping[str, Any],
) -> list[str]:
    data = live_provider_packet.get("data")
    data_mapping = data if isinstance(data, Mapping) else {}
    checks = {
        "raw_prompt_recorded": "live_provider_raw_prompt_recorded",
        "prompt_text_recorded": "live_provider_prompt_text_recorded",
        "natural_phrase_recorded": "live_provider_natural_phrase_recorded",
        "raw_route_id_recorded": "live_provider_raw_route_id_recorded",
        "selected_api_route_id_recorded": "live_provider_selected_route_recorded",
        "raw_provider_response_recorded": "live_provider_raw_response_recorded",
        "provider_response_raw_recorded": "live_provider_raw_response_recorded",
        "provider_response_text_recorded": "live_provider_response_text_recorded",
        "raw_backend_details_exposed": "live_provider_raw_backend_details_exposed",
        "secret_value_exposed": "live_provider_secret_value_exposed",
        "fallback_used": "live_provider_fallback_used",
        "local_imitation_used": "live_provider_local_imitation_used",
        "native_codex_subagent_used_as_dip": (
            "live_provider_native_codex_subagent_used_as_dip"
        ),
    }
    failures = [
        reason
        for field, reason in checks.items()
        if live_provider_packet.get(field) is True or data_mapping.get(field) is True
    ]
    return sorted(set(failures))


def _live_provider_join_failures(
    *,
    live_provider_requested: bool,
    live_provider_packet: Mapping[str, Any],
    live_provider_file_metadata: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    dispatch_packet: Mapping[str, Any],
    expected_text: str,
) -> list[str]:
    if not live_provider_requested:
        return []
    failures: list[str] = []
    route_id = _selected_route_id_from_context(runtime_context, dispatch_packet)
    allowed_routes = runtime_context.get("allowed_api_route_ids")
    allowed_route_ids = (
        {route for route in allowed_routes if isinstance(route, str)}
        if isinstance(allowed_routes, Sequence)
        and not isinstance(allowed_routes, (str, bytes))
        else set()
    )
    cli_declared, cli_route_bound = _runtime_context_declares_live_cli(
        runtime_context,
        route_id,
    )
    if not expected_text:
        failures.append("live_provider_expected_text_missing")
    elif not _is_safe_expected_text_marker(expected_text):
        failures.append("live_provider_expected_text_not_safe_marker")
    if not route_id:
        failures.append("live_provider_route_not_resolved")
    if route_id and route_id not in allowed_route_ids:
        failures.append("live_provider_route_not_allowed")
    if not cli_declared:
        failures.append("live_provider_cli_command_not_declared")
    if not cli_route_bound:
        failures.append("live_provider_cli_command_not_route_bound")
    if live_provider_file_metadata:
        if live_provider_file_metadata.get("live_provider_proof_file_read") is not True:
            failures.append("live_provider_proof_file_not_read")
        if (
            live_provider_file_metadata.get("live_provider_proof_file_valid_json")
            is not True
        ):
            failures.append("live_provider_proof_file_json_not_valid")
        if live_provider_file_metadata.get("live_provider_proof_file_mapping") is not True:
            failures.append("live_provider_proof_file_not_mapping")
    if not live_provider_packet:
        failures.append("live_provider_packet_missing")
        return sorted(set(failures))
    data = live_provider_packet.get("data")
    data_mapping = data if isinstance(data, Mapping) else {}
    if live_provider_packet.get("status") != "ok":
        failures.append("live_provider_packet_not_ok")
    if live_provider_packet.get("machine_error_code") != "OK":
        failures.append("live_provider_machine_error_not_ok")
    if live_provider_packet.get("changed_files") not in ([], ()):
        failures.append("live_provider_changed_files_not_empty")
    if live_provider_packet.get("effect") != EFFECT_PROBE:
        failures.append("live_provider_effect_not_probe")
    if not isinstance(data, Mapping):
        failures.append("live_provider_data_not_mapping")
    if data_mapping.get("check_kind") != "api_only_live_route_format":
        failures.append("live_provider_check_kind_invalid")
    if data_mapping.get("verification_scope") != "route_provider_only_no_write":
        failures.append("live_provider_scope_invalid")
    if data_mapping.get("route_state") != "live_response_observed_no_write":
        failures.append("live_provider_route_state_not_live")
    if data_mapping.get("network_dependent") is not True:
        failures.append("live_provider_not_network_dependent")
    if route_id and data_mapping.get("requested_model") != route_id:
        failures.append("live_provider_route_mismatch")
    if data_mapping.get("expected_text_observed") is not True:
        failures.append("live_provider_expected_text_not_observed")
    response_preview = _safe_text(data_mapping.get("response_preview_bounded"), limit=512)
    if expected_text and response_preview != expected_text:
        failures.append("live_provider_response_preview_mismatch")
    try:
        response_text_length = int(data_mapping.get("response_text_length"))
    except (TypeError, ValueError):
        response_text_length = -1
    if expected_text and response_text_length != len(expected_text):
        failures.append("live_provider_response_length_mismatch")
    if data_mapping.get("fallback_used") is True:
        failures.append("live_provider_fallback_used")
    if data_mapping.get("request_count") != 1:
        failures.append("live_provider_request_count_invalid")
    for field, reason in (
        ("state_written", "live_provider_state_written"),
        ("evidence_written", "live_provider_evidence_written"),
        ("file_mutation_attempted", "live_provider_file_mutation_attempted"),
        ("commands_started_by_provider", "live_provider_commands_started"),
        ("codex_history_sent", "live_provider_codex_history_sent"),
        ("repo_context_sent", "live_provider_repo_context_sent"),
    ):
        if data_mapping.get(field) is not False:
            failures.append(reason)
    failures.extend(_live_provider_packet_unsafe_failures(live_provider_packet))
    return sorted(set(failures))


def _machine_error_code(
    *,
    ledger_metadata: Mapping[str, Any],
    ledger_failures: Sequence[str],
    unsafe_ledger_failures: Sequence[str],
    dispatch_failures: Sequence[str],
    handoff_failures: Sequence[str],
    live_provider_failures: Sequence[str],
) -> str:
    if (
        not ledger_failures
        and not dispatch_failures
        and not handoff_failures
        and not live_provider_failures
    ):
        return "OK"
    if ledger_metadata.get("hook_ledger_file_error_code") == "hook_ledger_file_missing":
        return USER_PROMPT_SUBMIT_LEDGER_MISSING
    if ledger_metadata.get("hook_ledger_file_error_code"):
        return USER_PROMPT_SUBMIT_LEDGER_INVALID
    if unsafe_ledger_failures:
        return USER_PROMPT_SUBMIT_UNSAFE_CLAIM
    if "origin_state_not_custom_codex_flow_proven" in ledger_failures:
        return USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX
    if ledger_failures:
        return USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN
    if dispatch_failures:
        return USER_PROMPT_SUBMIT_DISPATCH_NOT_PROVEN
    if live_provider_failures:
        return USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN
    return USER_PROMPT_SUBMIT_HANDOFF_NOT_PROVEN


def build_real_custom_codex_hook_proof_packet(
    *,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None,
    hook_ledger: Mapping[str, Any] | None,
    context_file_metadata: Mapping[str, Any] | None = None,
    hook_ledger_file_metadata: Mapping[str, Any] | None = None,
    live_provider_packet: Mapping[str, Any] | None = None,
    live_provider_file_metadata: Mapping[str, Any] | None = None,
    live_provider_expected_text: object = "",
    live_provider_source_kind: str = "",
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    context = runtime_context if isinstance(runtime_context, Mapping) else {}
    ledger = hook_ledger if isinstance(hook_ledger, Mapping) else {}
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
    secret_list = list(secret_values or []) + [str(prompt_text or "")]
    secret_list.extend(_runtime_secret_values(context))
    expected_text = _safe_text(live_provider_expected_text, limit=512)
    if expected_text:
        secret_list.append(expected_text)

    entry_packet = build_router_hook_entry_packet(
        prompt_text=prompt_text,
        runtime_context=context,
        hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
        secret_values=secret_list,
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
    dispatch_packet: Mapping[str, Any] = {}
    dispatch_attempted = not ledger_failures
    if dispatch_attempted:
        dispatch_packet = build_controlled_api_dispatch_packet(
            prompt_text=prompt_text,
            runtime_context=context,
            hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
            secret_values=secret_list,
        )
    dispatch_failures = _dispatch_failures(dispatch_packet) if dispatch_attempted else []
    live_packet = (
        live_provider_packet if isinstance(live_provider_packet, Mapping) else {}
    )
    live_metadata = (
        dict(live_provider_file_metadata)
        if isinstance(live_provider_file_metadata, Mapping)
        else {}
    )
    live_provider_requested = bool(
        expected_text or live_packet or live_metadata or live_provider_source_kind
    )
    live_provider_attempted = bool(live_packet)
    live_provider_failures: list[str] = []
    if not ledger_failures and not dispatch_failures:
        live_provider_failures = _live_provider_join_failures(
            live_provider_requested=live_provider_requested,
            live_provider_packet=live_packet,
            live_provider_file_metadata=live_metadata,
            runtime_context=context,
            dispatch_packet=dispatch_packet,
            expected_text=expected_text,
        )

    approved_packet: Mapping[str, Any] = {}
    delivery_packet: Mapping[str, Any] = {}
    handoff_payload: Mapping[str, Any] = {}
    handoff_failures: list[str] = []
    if not ledger_failures and not dispatch_failures and not live_provider_failures:
        approved_packet = build_approved_handoff_packet(
            dispatch_packet,
            handoff_surface_kind=HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
            secret_values=secret_list,
        )
        handoff_payload = _safe_handoff_payload(
            dispatch_packet,
            HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        )
        delivery_packet = build_observed_machine_handoff_delivery_packet(
            approved_packet,
            handoff_payload=handoff_payload,
            delivery_surface_kind=DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
            delivery_surface_observed=True,
            secret_values=secret_list,
        )
        handoff_failures = _handoff_failures(approved_packet, delivery_packet)

    blocking_reasons = sorted(
        set(
            ledger_failures
            + dispatch_failures
            + live_provider_failures
            + handoff_failures
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        ledger_metadata=ledger_metadata,
        ledger_failures=ledger_failures,
        unsafe_ledger_failures=unsafe_ledger_failures,
        dispatch_failures=dispatch_failures,
        handoff_failures=handoff_failures,
        live_provider_failures=live_provider_failures,
    )
    hook_producer_ledger_proven = not ledger_failures
    # File-backed hook evidence is enough to admit bounded dispatch/handoff,
    # but not enough to claim native Custom Codex origin or UI visibility.
    custom_origin_proven = False
    thread_digest = _hex_sha256(ledger.get("thread_digest"))
    turn_digest = _hex_sha256(ledger.get("turn_digest"))
    trusted_hook_config_sha256 = _hex_sha256(
        ledger.get("trusted_hook_config_sha256")
    )
    loaded_hook_config_sha256 = _hex_sha256(ledger.get("loaded_hook_config_sha256"))
    live_data = (
        live_packet.get("data") if isinstance(live_packet.get("data"), Mapping) else {}
    )
    selected_live_route_id = _selected_route_id_from_context(context, dispatch_packet)
    live_cli_declared, live_cli_route_bound = _runtime_context_declares_live_cli(
        context,
        selected_live_route_id,
    )
    live_cli_command_parts = _runtime_context_live_cli_command_parts(context)
    allowed_context_routes = context.get("allowed_api_route_ids")
    allowed_context_route_ids = (
        {route for route in allowed_context_routes if isinstance(route, str)}
        if isinstance(allowed_context_routes, Sequence)
        and not isinstance(allowed_context_routes, (str, bytes))
        else set()
    )
    live_provider_response_proven = bool(
        live_provider_requested
        and not live_provider_failures
        and live_packet.get("status") == "ok"
        and live_data.get("expected_text_observed") is True
    )
    provider_route_fallback_used = live_data.get("fallback_used") is True
    live_provider_response_preview = _safe_text(
        live_data.get("response_preview_bounded"),
        limit=512,
    )

    extra = {
        **context_metadata,
        **ledger_metadata,
        **live_metadata,
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
        "router_entry_packet_kind": _safe_text(entry_packet.get("packet_kind"), limit=80),
        "router_entry_status": _safe_text(entry_packet.get("status"), limit=32),
        "router_entry_machine_error_code": _safe_text(
            entry_packet.get("machine_error_code"),
            limit=96,
        ),
        "hook_ledger_packet_kind": _safe_text(ledger.get("packet_kind"), limit=80),
        "hook_ledger_packet_valid": not ledger_failures,
        "hook_producer_ledger_proven": hook_producer_ledger_proven,
        "hook_producer_state": _safe_text(
            ledger.get("hook_producer_state"),
            limit=80,
        ),
        "hook_event_digest": _hex_sha256(ledger.get("hook_event_digest")),
        "hook_session_digest": _hex_sha256(ledger.get("session_digest")),
        "hook_thread_digest": _hex_sha256(ledger.get("thread_digest")),
        "hook_turn_digest": _hex_sha256(ledger.get("turn_digest")),
        "hook_cwd_digest": _hex_sha256(ledger.get("cwd_digest")),
        "hook_admission_run_id_digest": _hex_sha256(
            ledger.get("admission_run_id_digest")
        ),
        "hook_trust_source": _safe_text(ledger.get("hook_trust_source"), limit=80),
        "hook_ledger_failures": ledger_failures,
        "hook_ledger_unsafe_claim_failures": unsafe_ledger_failures,
        "origin_state": _safe_text(ledger.get("origin_state"), limit=80),
        "origin_state_allowed": (
            _safe_text(ledger.get("origin_state"), limit=80) in ALLOWED_ORIGIN_STATES
        ),
        "command_origin_surface": "",
        "custom_codex_flow_proven": custom_origin_proven,
        "command_origin_proven": custom_origin_proven,
        "custom_codex_origin_proven": custom_origin_proven,
        "native_custom_codex_flow_proven": custom_origin_proven,
        "native_router_hook_observed": custom_origin_proven,
        "user_prompt_submit_hook_observed": custom_origin_proven,
        "hook_config_present": ledger.get("hook_config_present") is True,
        "hook_enabled": ledger.get("hook_enabled") is True,
        "hook_trusted": ledger.get("hook_trusted") is True,
        "hook_hash_current": ledger.get("hook_hash_current") is True,
        "hook_config_digest_bound": bool(
            trusted_hook_config_sha256
            and loaded_hook_config_sha256
            and trusted_hook_config_sha256 == loaded_hook_config_sha256
        ),
        "trusted_hook_config_sha256": trusted_hook_config_sha256,
        "loaded_hook_config_sha256": loaded_hook_config_sha256,
        "hook_runnable": ledger.get("hook_runnable") is True,
        "user_prompt_submit_hook_ran": ledger.get("user_prompt_submit_hook_ran") is True,
        "hook_ledger_written": ledger.get("hook_ledger_written") is True,
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
        "thread_digest_present": bool(thread_digest),
        "turn_digest_present": bool(turn_digest),
        "thread_or_turn_digest_bound": bool(thread_digest or turn_digest),
        "dispatch_packet_kind": _safe_text(dispatch_packet.get("packet_kind"), limit=80),
        "dispatch_packet_status": _safe_text(dispatch_packet.get("status"), limit=32),
        "dispatch_packet_machine_error_code": _safe_text(
            dispatch_packet.get("machine_error_code"),
            limit=96,
        ),
        "dispatch_truth_source": _safe_text(
            dispatch_packet.get("dispatch_truth_source"),
            limit=80,
        ),
        "provider_like_response_only": (
            dispatch_packet.get("provider_like_response_only") is True
        ),
        "dispatch_attempted": dispatch_attempted,
        "alias_context_read": dispatch_packet.get("alias_context_read") is True,
        "allowed_api_route_ids_enforced": (
            dispatch_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": dispatch_packet.get("route_id_allowed") is True,
        "api_lane_called": dispatch_packet.get("api_lane_called") is True,
        "api_response_received": (
            dispatch_packet.get("provider_response_proven") is True
        ),
        "response_bound_to_proof": (
            dispatch_packet.get("provider_response_proven") is True
            and bool(_hex_sha256(dispatch_packet.get("provider_response_digest")))
            and dispatch_packet.get("provider_response_digest")
            == dispatch_packet.get("controlled_provider_response_sha256")
        ),
        "dispatch_status": _safe_text(
            dispatch_packet.get("dispatch_status") or "not_attempted",
            limit=32,
        ),
        "dispatch_proven": dispatch_packet.get("dispatch_proven") is True,
        "route_bound_dispatch_proven": (
            dispatch_packet.get("route_bound_dispatch_proven") is True
        ),
        "provider_response_proven": (
            dispatch_packet.get("provider_response_proven") is True
        ),
        "controlled_provider_response_proven": (
            dispatch_packet.get("controlled_provider_response_proven") is True
        ),
        "selected_api_route_id_present": (
            dispatch_packet.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            dispatch_packet.get("selected_api_route_id_sha256")
        ),
        "route_bound_request_sha256": _hex_sha256(
            dispatch_packet.get("route_bound_request_sha256")
        ),
        "provider_response_digest": _hex_sha256(
            dispatch_packet.get("provider_response_digest")
        ),
        "controlled_provider_response_sha256": _hex_sha256(
            dispatch_packet.get("controlled_provider_response_sha256")
        ),
        "selected_alias": _safe_text(dispatch_packet.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            dispatch_packet.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(dispatch_packet.get("selected_slot"), limit=64),
        "dispatch_failures": dispatch_failures,
        "approved_handoff_packet_kind": _safe_text(
            approved_packet.get("packet_kind"),
            limit=80,
        ),
        "approved_handoff_ready": approved_packet.get("handoff_ready") is True,
        "approved_handoff_payload_sanitized": (
            approved_packet.get("handoff_payload_sanitized") is True
        ),
        "observed_handoff_packet_kind": _safe_text(
            delivery_packet.get("packet_kind"),
            limit=80,
        ),
        "observed_handoff_status": _safe_text(
            delivery_packet.get("status"),
            limit=32,
        ),
        "machine_response_envelope_observed": (
            delivery_packet.get("machine_response_envelope_observed") is True
        ),
        "machine_response_envelope_sha256": _hex_sha256(
            delivery_packet.get("machine_response_envelope_sha256")
        ),
        "machine_response_structured_content_present": (
            delivery_packet.get("machine_response_structured_content_present") is True
        ),
        "handoff_payload_digest": _hex_sha256(
            approved_packet.get("handoff_payload_sha256")
        ),
        "handoff_delivered": delivery_packet.get("handoff_delivered") is True,
        "delivery_observed": delivery_packet.get("delivery_observed") is True,
        "handoff_failures": handoff_failures,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_readiness": (
            "HOOK_PRODUCER_DISPATCH_HANDOFF_PROVEN_ORIGIN_NOT_PROMOTED"
            if ok
            else "HOOK_DISPATCH_HANDOFF_NOT_PROVEN"
        ),
        "live_provider_requested": live_provider_requested,
        "live_provider_attempted": live_provider_attempted,
        "live_provider_source_kind": _safe_text(live_provider_source_kind, limit=80),
        "live_provider_packet_status": _safe_text(
            live_packet.get("status"),
            limit=32,
        ),
        "live_provider_packet_machine_error_code": _safe_text(
            live_packet.get("machine_error_code"),
            limit=96,
        ),
        "live_provider_cli_command_declared": live_cli_declared,
        "live_provider_cli_command_route_bound": live_cli_route_bound,
        "live_provider_cli_command_sha256": _command_parts_sha256(
            live_cli_command_parts
        ),
        "live_provider_route_bound_to_context": bool(
            selected_live_route_id
            and selected_live_route_id in allowed_context_route_ids
        ),
        "live_provider_route_id_sha256": _sha256_text(selected_live_route_id)
        if selected_live_route_id
        else "",
        "live_provider_route_id_recorded": False,
        "live_provider_check_kind": _safe_text(live_data.get("check_kind"), limit=80),
        "live_provider_verification_scope": _safe_text(
            live_data.get("verification_scope"),
            limit=80,
        ),
        "live_provider_route_state": _safe_text(live_data.get("route_state"), limit=80),
        "live_provider_network_dependent": live_data.get("network_dependent") is True,
        "live_provider_request_count": int(live_data.get("request_count") or 0),
        "live_provider_expected_text_digest": _sha256_text(expected_text)
        if expected_text
        else "",
        "expected_text_observed": live_data.get("expected_text_observed") is True,
        "expected_text_present": bool(expected_text),
        "expected_text_recorded": False,
        "raw_expected_text_recorded": False,
        "provider_route_fallback_used": provider_route_fallback_used,
        "live_provider_response_digest": _sha256_text(live_provider_response_preview)
        if live_provider_response_preview
        else "",
        "live_provider_response_bound_to_expected_text": bool(
            live_provider_response_proven and expected_text
        ),
        "live_provider_response_bound_to_route": bool(
            live_provider_response_proven
            and selected_live_route_id
            and live_data.get("requested_model") == selected_live_route_id
        ),
        "live_provider_changed_files_empty": live_packet.get("changed_files")
        in ([], ()),
        "live_provider_state_written": live_data.get("state_written") is True,
        "live_provider_evidence_written": live_data.get("evidence_written") is True,
        "live_provider_file_mutation_attempted": (
            live_data.get("file_mutation_attempted") is True
        ),
        "live_provider_codex_history_sent": live_data.get("codex_history_sent") is True,
        "live_provider_repo_context_sent": live_data.get("repo_context_sent") is True,
        "live_provider_failures": live_provider_failures,
        "live_provider_proven": live_provider_response_proven,
        "live_provider_response_proven": live_provider_response_proven,
        "external_live_provider_response_proven": live_provider_response_proven,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_custom_codex_origin": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": not live_provider_response_proven,
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
        "browser_can_supply_hook_authority": False,
        "browser_can_supply_prompt_authority": False,
        "browser_can_supply_route_authority": False,
        "browser_can_supply_handoff_authority": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a UserPromptSubmit hook-produced ledger, controlled dispatch, live provider response, and observed handoff."
            if ok and live_provider_response_proven
            else "WBP proved a UserPromptSubmit hook-produced ledger, controlled dispatch, and observed handoff."
            if ok
            else "WBP blocked UserPromptSubmit hook proof before bounded dispatch."
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


def run_real_custom_codex_hook_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    hook_ledger_file: str,
    runtime_context_file: str | None = None,
    live_provider_expected_text: object = "",
    live_provider_proof_file: str | None = None,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    ledger_path = Path(hook_ledger_file).expanduser()
    hook_ledger, ledger_metadata = _ledger_file_metadata(ledger_path)
    live_packet: Mapping[str, Any] = {}
    live_metadata: Mapping[str, Any] = {}
    live_source_kind = ""
    expected_text = _safe_text(live_provider_expected_text, limit=512)
    if live_provider_proof_file:
        live_path = Path(live_provider_proof_file).expanduser()
        live_packet, live_metadata = _packet_file_metadata(
            live_path,
            prefix="live_provider_proof",
        )
        live_source_kind = "file_backed_external_models_live_format_check"
    elif expected_text:
        preliminary = build_real_custom_codex_hook_proof_packet(
            prompt_text=prompt_text,
            runtime_context=runtime_context,
            hook_ledger=hook_ledger,
            context_file_metadata=context_metadata,
            hook_ledger_file_metadata=ledger_metadata,
        )
        if preliminary.get("status") == "ok":
            route_id = _selected_route_id_from_context(runtime_context, preliminary)
            cli_declared, cli_route_bound = _runtime_context_declares_live_cli(
                runtime_context,
                route_id,
            )
            expected_marker_safe = _is_safe_expected_text_marker(expected_text)
            live_source_kind = (
                "runtime_context_allowed_cli_command"
                if cli_declared and cli_route_bound and expected_marker_safe
                else "live_provider_expected_text_not_safe_marker"
                if not expected_marker_safe
                else "runtime_context_cli_command_not_admitted"
            )
            if cli_declared and cli_route_bound and expected_marker_safe:
                live_packet = run_external_models_command(
                    SimpleNamespace(
                        external_models_command="live-format-check",
                        route=route_id,
                        prompt=f"Answer exactly one line: {expected_text}",
                        expected_text=expected_text,
                        json=True,
                    )
                )
        else:
            live_source_kind = "base_hook_dispatch_not_proven"
    return build_real_custom_codex_hook_proof_packet(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        hook_ledger=hook_ledger,
        context_file_metadata=context_metadata,
        hook_ledger_file_metadata=ledger_metadata,
        live_provider_packet=live_packet,
        live_provider_file_metadata=live_metadata,
        live_provider_expected_text=expected_text,
        live_provider_source_kind=live_source_kind,
    )
