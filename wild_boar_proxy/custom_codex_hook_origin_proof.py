# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .codex_working_flow_delivery_proof import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
)
from .command_effects import EFFECT_PROBE
from .core import packets
from .proof_seal import (
    PROOF_SEAL_OK,
    default_seal_path,
    verify_proof_seal,
)
from .real_custom_codex_hook_proof import (
    COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW,
    HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN,
    HOOK_TRUST_SOURCE_CODEX_EXECUTION,
    ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
    REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
    USER_PROMPT_SUBMIT_HOOK_LEDGER_PACKET_KIND,
    runtime_context_digest,
)
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths
from .user_prompt_submit_hook_producer import (
    _canonical_json_digest,
    _features_hooks_disabled,
    _find_hook_definition,
    _read_hooks_json,
    hook_command_for_paths,
    hook_definition_digest,
    hook_ledger_path,
    hook_script_path,
    hooks_json_path,
)


CUSTOM_CODEX_HOOK_ORIGIN_PROOF_PACKET_KIND = "wbp_custom_codex_hook_origin_proof"

CUSTOM_CODEX_HOOK_ORIGIN_SOURCE_INVALID = "WBP_CUSTOM_CODEX_HOOK_ORIGIN_SOURCE_INVALID"
CUSTOM_CODEX_HOOK_ORIGIN_DELIVERY_INVALID = (
    "WBP_CUSTOM_CODEX_HOOK_ORIGIN_DELIVERY_INVALID"
)
CUSTOM_CODEX_HOOK_ORIGIN_PROFILE_INVALID = (
    "WBP_CUSTOM_CODEX_HOOK_ORIGIN_PROFILE_INVALID"
)
CUSTOM_CODEX_HOOK_ORIGIN_JOIN_INVALID = "WBP_CUSTOM_CODEX_HOOK_ORIGIN_JOIN_INVALID"
CUSTOM_CODEX_HOOK_ORIGIN_SEAL_INVALID = "WBP_CUSTOM_CODEX_HOOK_ORIGIN_SEAL_INVALID"
CUSTOM_CODEX_HOOK_ORIGIN_UNSAFE_CLAIM = "WBP_CUSTOM_CODEX_HOOK_ORIGIN_UNSAFE_CLAIM"

CUSTOM_CODEX_HOOK_ORIGIN_TRUTH_SOURCE = (
    "file_backed_custom_codex_user_prompt_submit_hook_profile_identity_join"
)


_UNSAFE_TRUE_FIELDS = {
    "raw_prompt_recorded": "raw_prompt_recorded",
    "prompt_text_recorded": "prompt_text_recorded",
    "natural_phrase_recorded": "natural_phrase_recorded",
    "raw_jsonl_recorded": "raw_jsonl_recorded",
    "tool_call_arguments_recorded": "tool_call_arguments_recorded",
    "route_candidate_recorded": "route_candidate_recorded",
    "raw_route_id_recorded": "raw_route_id_recorded",
    "selected_api_route_id_recorded": "selected_api_route_id_recorded",
    "raw_provider_response_recorded": "raw_provider_response_recorded",
    "provider_response_text_recorded": "provider_response_text_recorded",
    "provider_response_preview_recorded": "provider_response_preview_recorded",
    "raw_expected_text_recorded": "raw_expected_text_recorded",
    "expected_text_recorded": "expected_text_recorded",
    "raw_backend_details_exposed": "raw_backend_details_exposed",
    "secret_value_exposed": "secret_value_exposed",
    "fallback_used": "fallback_used",
    "local_imitation_used": "local_imitation_used",
    "provider_route_fallback_used": "provider_route_fallback_used",
    "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
    "custom_codex_ui_visibility_proven": "custom_codex_ui_visibility_must_not_be_claimed",
    "delivery_counts_as_custom_codex_ui": "delivery_counts_as_custom_ui_must_not_be_claimed",
    "native_free_chat_router_proven": "native_free_chat_router_must_not_be_claimed",
    "product_ready": "product_ready_must_not_be_claimed",
    "state_written": "state_write_not_allowed",
    "evidence_written": "evidence_write_not_allowed",
    "file_mutation_attempted": "file_mutation_not_allowed",
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _path_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


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
        f"{prefix}_file_path_recorded": False,
        f"{prefix}_file_sha256": "",
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, json.JSONDecodeError):
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


def _sequence_not_empty(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(list(value))


def _unsafe_claim_failures(packet: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            reason
            for field, reason in _UNSAFE_TRUE_FIELDS.items()
            if packet.get(field) is True
        }
    )


def _packet_shape_failures(packet: Mapping[str, Any], *, prefix: str) -> list[str]:
    if not isinstance(packet, dict):
        return [f"{prefix}_packet_not_mapping"]
    return [
        f"{prefix}_packet_semantics_invalid:{violation['field']}:{violation['code']}"
        for violation in packets.inspect_command_packet_semantics(packet)
    ]


def _source_failures(
    source: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unsafe = _unsafe_claim_failures(source)
    if metadata.get("integrated_live_provider_proof_file_read") is not True:
        failures.append("integrated_live_provider_proof_file_not_read")
    if metadata.get("integrated_live_provider_proof_file_valid_json") is not True:
        failures.append("integrated_live_provider_proof_file_json_not_valid")
    if metadata.get("integrated_live_provider_proof_file_mapping") is not True:
        failures.append("integrated_live_provider_proof_file_not_mapping")
    failures.extend(_packet_shape_failures(source, prefix="integrated_live_provider_proof"))
    if source.get("packet_kind") != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND:
        failures.append("integrated_proof_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("integrated_proof_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("integrated_proof_machine_error_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("integrated_proof_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("integrated_proof_changed_files_not_empty")
    live_source_kind = _safe_text(source.get("live_provider_source_kind"), limit=80)
    live_provider_file_backed = bool(
        live_source_kind == "file_backed_external_models_live_format_check"
        and source.get("live_provider_proof_file_read") is True
        and source.get("live_provider_proof_file_valid_json") is True
        and source.get("live_provider_proof_file_mapping") is True
    )
    live_provider_embedded_runtime_cli = (
        live_source_kind == "runtime_context_allowed_cli_command"
    )
    for field, reason in (
        ("runtime_context_file_read", "source_runtime_context_file_not_read"),
        ("runtime_context_file_valid_json", "source_runtime_context_file_json_not_valid"),
        ("runtime_context_file_mapping", "source_runtime_context_file_not_mapping"),
        ("hook_ledger_file_read", "source_hook_ledger_file_not_read"),
        ("hook_ledger_file_valid_json", "source_hook_ledger_file_json_not_valid"),
        ("hook_ledger_file_mapping", "source_hook_ledger_file_not_mapping"),
        ("hook_producer_ledger_proven", "hook_producer_ledger_not_proven"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("hook_config_digest_bound", "hook_config_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("live_provider_response_proven", "live_provider_response_not_proven"),
        ("external_live_provider_response_proven", "external_live_provider_response_not_proven"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    if source.get("custom_codex_flow_proven") is True:
        failures.append("integrated_proof_must_not_preclaim_custom_origin")
    if source.get("command_origin_proven") is True:
        failures.append("integrated_proof_must_not_preclaim_command_origin")
    if source.get("native_custom_codex_flow_proven") is True:
        failures.append("integrated_proof_must_not_preclaim_native_custom_flow")
    if _safe_text(source.get("origin_state"), limit=80) != ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN:
        failures.append("origin_state_not_custom_codex_flow_proven")
    if _safe_text(source.get("hook_producer_state"), limit=80) != HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN:
        failures.append("hook_producer_state_not_custom_codex_proven")
    if _safe_text(source.get("hook_trust_source"), limit=80) != HOOK_TRUST_SOURCE_CODEX_EXECUTION:
        failures.append("hook_trust_source_not_codex_execution")
    if not live_provider_file_backed and not live_provider_embedded_runtime_cli:
        failures.append("live_provider_source_not_file_backed_or_runtime_cli")
    if live_source_kind == "file_backed_external_models_live_format_check":
        for field, reason in (
            ("live_provider_proof_file_read", "source_live_provider_proof_file_not_read"),
            (
                "live_provider_proof_file_valid_json",
                "source_live_provider_proof_file_json_not_valid",
            ),
            (
                "live_provider_proof_file_mapping",
                "source_live_provider_proof_file_not_mapping",
            ),
        ):
            if source.get(field) is not True:
                failures.append(reason)
    if source.get("hook_ledger_file_path_recorded") is True:
        failures.append("source_hook_ledger_path_must_not_be_recorded")
    if source.get("runtime_context_file_path_recorded") is True:
        failures.append("source_runtime_context_path_must_not_be_recorded")
    if source.get("live_provider_proof_file_path_recorded") is True:
        failures.append("source_live_provider_proof_path_must_not_be_recorded")
    for field, reason in (
        ("prompt_digest", "prompt_digest_missing"),
        ("hook_prompt_digest", "hook_prompt_digest_missing"),
        ("runtime_context_digest", "runtime_context_digest_missing"),
        ("hook_runtime_context_digest", "hook_runtime_context_digest_missing"),
        ("trusted_hook_config_sha256", "trusted_hook_config_digest_missing"),
        ("loaded_hook_config_sha256", "loaded_hook_config_digest_missing"),
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
        ("machine_response_envelope_sha256", "machine_response_envelope_digest_missing"),
        ("live_provider_response_digest", "live_provider_response_digest_missing"),
        ("provider_response_digest", "provider_response_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    for field, reason in (
        ("hook_ledger_failures", "hook_ledger_failures_not_empty"),
        ("dispatch_failures", "dispatch_failures_not_empty"),
        ("handoff_failures", "handoff_failures_not_empty"),
        ("live_provider_failures", "live_provider_failures_not_empty"),
        ("blocking_reasons", "integrated_blocking_reasons_not_empty"),
    ):
        if _sequence_not_empty(source.get(field)):
            failures.append(reason)
    failures.extend(unsafe)
    return sorted(set(failures)), unsafe


def _working_flow_failures(
    working_flow: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unsafe = _unsafe_claim_failures(working_flow)
    if metadata.get("working_flow_delivery_proof_file_read") is not True:
        failures.append("working_flow_delivery_proof_file_not_read")
    if metadata.get("working_flow_delivery_proof_file_valid_json") is not True:
        failures.append("working_flow_delivery_proof_file_json_not_valid")
    if metadata.get("working_flow_delivery_proof_file_mapping") is not True:
        failures.append("working_flow_delivery_proof_file_not_mapping")
    failures.extend(_packet_shape_failures(working_flow, prefix="working_flow_delivery_proof"))
    if working_flow.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_packet_kind_invalid")
    if working_flow.get("status") != "ok":
        failures.append("working_flow_not_ok")
    if working_flow.get("machine_error_code") != "OK":
        failures.append("working_flow_machine_error_not_ok")
    if working_flow.get("effect") != EFFECT_PROBE:
        failures.append("working_flow_effect_not_probe")
    if working_flow.get("changed_files") not in ([], ()):
        failures.append("working_flow_changed_files_not_empty")
    for field, reason in (
        ("integrated_live_provider_proof_valid", "working_flow_source_not_valid"),
        ("hook_producer_ledger_proven", "working_flow_hook_ledger_not_proven"),
        ("user_prompt_submit_hook_ran", "working_flow_hook_not_run"),
        ("hook_prompt_digest_bound", "working_flow_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "working_flow_context_digest_not_bound"),
        ("api_lane_called", "working_flow_api_lane_not_called"),
        ("dispatch_proven", "working_flow_dispatch_not_proven"),
        ("route_bound_dispatch_proven", "working_flow_route_dispatch_not_proven"),
        ("live_provider_response_proven", "working_flow_live_provider_not_proven"),
        ("external_live_provider_response_proven", "working_flow_external_live_provider_not_proven"),
        ("live_provider_response_digest_bound_to_handoff", "working_flow_live_digest_not_bound"),
        ("controlled_provider_response_digest_bound_to_handoff", "working_flow_controlled_digest_not_bound"),
        ("approved_handoff_ready", "working_flow_approved_handoff_not_ready"),
        ("handoff_delivered", "working_flow_handoff_not_delivered"),
        ("delivery_observed", "working_flow_delivery_not_observed"),
        ("matching_mcp_tool_result_observed", "working_flow_tool_result_not_observed"),
        ("mcp_tool_result_name_allowed", "working_flow_tool_name_not_allowed"),
        ("mcp_tool_result_server_allowed", "working_flow_server_not_allowed"),
        ("mcp_tool_result_structured_content_present", "working_flow_structured_content_missing"),
        ("mcp_tool_result_content_text_json_matches_structured_content", "working_flow_content_text_mismatch"),
        ("assistant_response_observed", "working_flow_assistant_response_not_observed"),
        ("assistant_response_after_tool_result", "working_flow_assistant_not_after_tool"),
        ("assistant_response_bound_to_handoff_digest", "working_flow_assistant_not_bound"),
        ("codex_exec_assistant_continuation_proven", "working_flow_assistant_continuation_not_proven"),
        ("codex_working_flow_delivery_proven", "working_flow_delivery_not_proven"),
    ):
        if working_flow.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("blocking_reasons", "working_flow_blocking_reasons_not_empty"),
        ("integrated_live_provider_proof_failures", "working_flow_source_failures_not_empty"),
        ("transcript_delivery_failures", "working_flow_transcript_failures_not_empty"),
        ("assistant_binding_failures", "working_flow_assistant_binding_failures_not_empty"),
        ("source_unsafe_claim_failures", "working_flow_source_unsafe_failures_not_empty"),
        ("transcript_unsafe_claim_failures", "working_flow_transcript_unsafe_failures_not_empty"),
    ):
        if _sequence_not_empty(working_flow.get(field)):
            failures.append(reason)
    failures.extend(unsafe)
    return sorted(set(failures)), unsafe


def _profile_identity(
    *,
    paths: RuntimePaths,
    source: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    failures: list[str] = []
    unsafe: list[str] = []

    context_path = runtime_context_path(paths=paths, runtime_context_file=None)
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    profile_runtime_context_digest = runtime_context_digest(runtime_context)

    hooks_document, hooks_metadata = _read_hooks_json(hooks_json_path(paths))
    hooks_disabled, config_metadata = _features_hooks_disabled(paths.config_toml)
    command = hook_command_for_paths(paths)
    expected_hook_definition_digest = hook_definition_digest(command)
    hook_definition = _find_hook_definition(hooks_document, command=command)
    loaded_hook_definition_digest = (
        _canonical_json_digest(hook_definition) if hook_definition else ""
    )
    script = hook_script_path(paths)
    script_present = script.exists()
    script_executable = bool(script_present and os.access(script, os.X_OK))

    profile_ledger, profile_ledger_metadata = _read_json_mapping_file(
        hook_ledger_path(paths),
        prefix="profile_hook_ledger",
    )
    unsafe.extend(_unsafe_claim_failures(profile_ledger))

    source_runtime_context_digest = _hex_sha256(source.get("runtime_context_digest"))
    source_hook_runtime_context_digest = _hex_sha256(
        source.get("hook_runtime_context_digest")
    )
    source_prompt_digest = _hex_sha256(source.get("prompt_digest"))
    source_hook_prompt_digest = _hex_sha256(source.get("hook_prompt_digest"))
    source_trusted_hook_digest = _hex_sha256(source.get("trusted_hook_config_sha256"))
    source_loaded_hook_digest = _hex_sha256(source.get("loaded_hook_config_sha256"))

    if not paths.profile_dir.exists():
        failures.append("custom_profile_dir_missing")
    if context_metadata.get("runtime_context_file_read") is not True:
        failures.append("profile_runtime_context_file_not_read")
    if context_metadata.get("runtime_context_file_valid_json") is not True:
        failures.append("profile_runtime_context_file_json_not_valid")
    if context_metadata.get("runtime_context_file_mapping") is not True:
        failures.append("profile_runtime_context_file_not_mapping")
    if not profile_runtime_context_digest:
        failures.append("profile_runtime_context_digest_missing")
    if (
        profile_runtime_context_digest
        and source_runtime_context_digest
        and profile_runtime_context_digest != source_runtime_context_digest
    ):
        failures.append("profile_runtime_context_digest_mismatch")
    if (
        profile_runtime_context_digest
        and source_hook_runtime_context_digest
        and profile_runtime_context_digest != source_hook_runtime_context_digest
    ):
        failures.append("profile_hook_runtime_context_digest_mismatch")

    if hooks_disabled:
        failures.append("profile_hooks_feature_disabled")
    if hooks_metadata.get("hooks_json_read") is not True:
        failures.append("profile_hooks_json_not_read")
    if hooks_metadata.get("hooks_json_valid_json") is not True:
        failures.append("profile_hooks_json_not_valid")
    if hooks_metadata.get("hooks_json_mapping") is not True:
        failures.append("profile_hooks_json_not_mapping")
    if not hook_definition:
        failures.append("profile_user_prompt_submit_hook_definition_missing")
    if not loaded_hook_definition_digest:
        failures.append("profile_loaded_hook_definition_digest_missing")
    if (
        loaded_hook_definition_digest
        and expected_hook_definition_digest
        and loaded_hook_definition_digest != expected_hook_definition_digest
    ):
        failures.append("profile_hook_config_digest_mismatch")
    for digest_value, reason in (
        (source_trusted_hook_digest, "source_trusted_hook_config_digest_missing"),
        (source_loaded_hook_digest, "source_loaded_hook_config_digest_missing"),
    ):
        if not digest_value:
            failures.append(reason)
    if (
        loaded_hook_definition_digest
        and source_trusted_hook_digest
        and loaded_hook_definition_digest != source_trusted_hook_digest
    ):
        failures.append("profile_trusted_hook_config_digest_mismatch")
    if (
        loaded_hook_definition_digest
        and source_loaded_hook_digest
        and loaded_hook_definition_digest != source_loaded_hook_digest
    ):
        failures.append("profile_loaded_hook_config_digest_mismatch")
    if not script_present:
        failures.append("profile_hook_script_missing")
    if script_present and not script_executable:
        failures.append("profile_hook_script_not_executable")

    if profile_ledger_metadata.get("profile_hook_ledger_file_read") is not True:
        failures.append("profile_hook_ledger_file_not_read")
    if profile_ledger_metadata.get("profile_hook_ledger_file_valid_json") is not True:
        failures.append("profile_hook_ledger_file_json_not_valid")
    if profile_ledger_metadata.get("profile_hook_ledger_file_mapping") is not True:
        failures.append("profile_hook_ledger_file_not_mapping")
    if profile_ledger.get("packet_kind") != USER_PROMPT_SUBMIT_HOOK_LEDGER_PACKET_KIND:
        failures.append("profile_hook_ledger_packet_kind_invalid")
    if _safe_text(profile_ledger.get("origin_state"), limit=80) != ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN:
        failures.append("profile_hook_ledger_origin_state_not_custom")
    if _safe_text(profile_ledger.get("hook_event_name"), limit=80) != "UserPromptSubmit":
        failures.append("profile_hook_ledger_event_not_user_prompt_submit")
    if _safe_text(profile_ledger.get("hook_producer_state"), limit=80) != HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN:
        failures.append("profile_hook_ledger_producer_state_not_custom")
    if _safe_text(profile_ledger.get("hook_trust_source"), limit=80) != HOOK_TRUST_SOURCE_CODEX_EXECUTION:
        failures.append("profile_hook_ledger_trust_source_not_codex")
    for field, reason in (
        ("hook_config_present", "profile_hook_config_missing"),
        ("hook_enabled", "profile_hook_disabled"),
        ("hook_trusted", "profile_hook_untrusted"),
        ("hook_hash_current", "profile_hook_hash_not_current"),
        ("hook_runnable", "profile_hook_not_runnable"),
        ("user_prompt_submit_hook_ran", "profile_user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "profile_hook_ledger_not_written"),
    ):
        if profile_ledger.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("thread_digest", "profile_hook_thread_digest_missing"),
        ("turn_digest", "profile_hook_turn_digest_missing"),
        ("session_digest", "profile_hook_session_digest_missing"),
        ("cwd_digest", "profile_hook_cwd_digest_missing"),
        ("hook_event_digest", "profile_hook_event_digest_missing"),
    ):
        if not _hex_sha256(profile_ledger.get(field)):
            failures.append(reason)
    profile_prompt_digest = _hex_sha256(profile_ledger.get("prompt_digest"))
    profile_context_digest = _hex_sha256(profile_ledger.get("runtime_context_digest"))
    profile_trusted_hook_digest = _hex_sha256(
        profile_ledger.get("trusted_hook_config_sha256")
    )
    profile_loaded_hook_digest = _hex_sha256(
        profile_ledger.get("loaded_hook_config_sha256")
    )
    if not profile_prompt_digest:
        failures.append("profile_hook_prompt_digest_missing")
    if (
        profile_prompt_digest
        and source_prompt_digest
        and profile_prompt_digest != source_prompt_digest
    ):
        failures.append("profile_prompt_digest_mismatch")
    if (
        profile_prompt_digest
        and source_hook_prompt_digest
        and profile_prompt_digest != source_hook_prompt_digest
    ):
        failures.append("profile_hook_prompt_digest_mismatch")
    if not profile_context_digest:
        failures.append("profile_hook_context_digest_missing")
    if (
        profile_context_digest
        and profile_runtime_context_digest
        and profile_context_digest != profile_runtime_context_digest
    ):
        failures.append("profile_ledger_runtime_context_digest_mismatch")
    if not profile_trusted_hook_digest:
        failures.append("profile_hook_trusted_digest_missing")
    if not profile_loaded_hook_digest:
        failures.append("profile_hook_loaded_digest_missing")
    if (
        profile_trusted_hook_digest
        and loaded_hook_definition_digest
        and profile_trusted_hook_digest != loaded_hook_definition_digest
    ):
        failures.append("profile_ledger_trusted_hook_config_digest_mismatch")
    if (
        profile_loaded_hook_digest
        and loaded_hook_definition_digest
        and profile_loaded_hook_digest != loaded_hook_definition_digest
    ):
        failures.append("profile_ledger_loaded_hook_config_digest_mismatch")
    if profile_trusted_hook_digest and profile_loaded_hook_digest and profile_trusted_hook_digest != profile_loaded_hook_digest:
        failures.append("profile_ledger_hook_config_digest_mismatch")

    failures.extend(unsafe)
    command_origin_surface = _safe_text(
        profile_ledger.get("command_origin_surface"),
        limit=80,
    )
    profile_hook_command_origin_surface_declared = (
        command_origin_surface == COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW
    )
    extra = {
        **context_metadata,
        **hooks_metadata,
        **config_metadata,
        **profile_ledger_metadata,
        "custom_profile_dir_present": paths.profile_dir.exists(),
        "custom_profile_dir_path_recorded": False,
        "profile_runtime_context_digest": profile_runtime_context_digest,
        "profile_runtime_context_digest_bound": bool(
            profile_runtime_context_digest
            and profile_runtime_context_digest == source_runtime_context_digest
            and profile_runtime_context_digest == source_hook_runtime_context_digest
        ),
        "profile_hooks_feature_disabled": hooks_disabled,
        "profile_user_prompt_submit_hook_definition_present": bool(hook_definition),
        "profile_expected_hook_definition_sha256": expected_hook_definition_digest,
        "profile_loaded_hook_definition_sha256": loaded_hook_definition_digest,
        "profile_hook_config_digest_bound": bool(
            loaded_hook_definition_digest
            and loaded_hook_definition_digest == expected_hook_definition_digest
            and loaded_hook_definition_digest == source_trusted_hook_digest
            and loaded_hook_definition_digest == source_loaded_hook_digest
        ),
        "profile_hook_script_present": script_present,
        "profile_hook_script_executable": script_executable,
        "profile_hook_script_sha256": _path_sha256(script),
        "profile_hook_script_path_recorded": False,
        "profile_hook_ledger_packet_kind": _safe_text(
            profile_ledger.get("packet_kind"),
            limit=80,
        ),
        "profile_hook_ledger_origin_state": _safe_text(
            profile_ledger.get("origin_state"),
            limit=80,
        ),
        "profile_hook_ledger_producer_state": _safe_text(
            profile_ledger.get("hook_producer_state"),
            limit=80,
        ),
        "profile_hook_ledger_trust_source": _safe_text(
            profile_ledger.get("hook_trust_source"),
            limit=80,
        ),
        "profile_hook_command_origin_surface_declared": (
            profile_hook_command_origin_surface_declared
        ),
        "profile_hook_prompt_digest": profile_prompt_digest,
        "profile_hook_runtime_context_digest": profile_context_digest,
        "profile_hook_trusted_config_sha256": profile_trusted_hook_digest,
        "profile_hook_loaded_config_sha256": profile_loaded_hook_digest,
        "profile_hook_ledger_matches_source": bool(
            profile_prompt_digest
            and profile_prompt_digest == source_prompt_digest
            and profile_context_digest
            and profile_context_digest == source_runtime_context_digest
            and profile_trusted_hook_digest
            and profile_trusted_hook_digest == source_trusted_hook_digest
            and profile_loaded_hook_digest
            and profile_loaded_hook_digest == source_loaded_hook_digest
        ),
        "profile_identity_failures": sorted(set(failures)),
        "profile_unsafe_claim_failures": sorted(set(unsafe)),
    }
    return extra, sorted(set(failures)), sorted(set(unsafe))


def _join_failures(
    source: Mapping[str, Any],
    working_flow: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    comparisons = (
        ("live_provider_response_digest", "live_provider_response_digest", "live_provider_response_digest_mismatch"),
        ("provider_response_digest", "controlled_provider_response_digest", "controlled_provider_response_digest_mismatch"),
        ("handoff_payload_digest", "source_handoff_payload_digest", "source_handoff_payload_digest_mismatch"),
        ("machine_response_envelope_sha256", "machine_response_envelope_sha256", "machine_response_envelope_digest_mismatch"),
    )
    for source_field, working_field, reason in comparisons:
        source_digest = _hex_sha256(source.get(source_field))
        working_digest = _hex_sha256(working_flow.get(working_field))
        if not source_digest or not working_digest or source_digest != working_digest:
            failures.append(reason)
    if working_flow.get("custom_codex_flow_proven") is True:
        failures.append("working_flow_must_not_preclaim_custom_origin")
    if working_flow.get("command_origin_proven") is True:
        failures.append("working_flow_must_not_preclaim_command_origin")
    return sorted(set(failures))


def _machine_error_code(
    *,
    source_failures: Sequence[str],
    working_flow_failures: Sequence[str],
    profile_failures: Sequence[str],
    join_failures: Sequence[str],
    seal_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if (
        not source_failures
        and not working_flow_failures
        and not profile_failures
        and not join_failures
        and not seal_failures
        and not unsafe_failures
    ):
        return "OK"
    if unsafe_failures:
        return CUSTOM_CODEX_HOOK_ORIGIN_UNSAFE_CLAIM
    if source_failures:
        return CUSTOM_CODEX_HOOK_ORIGIN_SOURCE_INVALID
    if working_flow_failures:
        return CUSTOM_CODEX_HOOK_ORIGIN_DELIVERY_INVALID
    if profile_failures:
        return CUSTOM_CODEX_HOOK_ORIGIN_PROFILE_INVALID
    if seal_failures:
        return CUSTOM_CODEX_HOOK_ORIGIN_SEAL_INVALID
    return CUSTOM_CODEX_HOOK_ORIGIN_JOIN_INVALID


def _seal_failures(
    *,
    strict_sealed_evidence: bool,
    source_seal_packet: Mapping[str, Any] | None,
    working_flow_seal_packet: Mapping[str, Any] | None,
) -> tuple[list[str], dict[str, Any]]:
    if not strict_sealed_evidence:
        return [], {
            "strict_sealed_evidence": False,
            "source_file_seal_verified": False,
            "working_flow_file_seal_verified": False,
            "source_file_authenticity_proven": False,
            "source_file_unforgeable": False,
            "cryptographic_authenticity_proven": False,
        }
    source_seal = source_seal_packet if isinstance(source_seal_packet, Mapping) else {}
    working_seal = (
        working_flow_seal_packet if isinstance(working_flow_seal_packet, Mapping) else {}
    )
    failures: list[str] = []
    if source_seal.get("machine_error_code") != PROOF_SEAL_OK:
        failures.append("source_proof_seal_not_ok")
    if source_seal.get("proof_seal_verified") is not True:
        failures.append("source_proof_seal_not_verified")
    if working_seal.get("machine_error_code") != PROOF_SEAL_OK:
        failures.append("working_flow_proof_seal_not_ok")
    if working_seal.get("proof_seal_verified") is not True:
        failures.append("working_flow_proof_seal_not_verified")
    for field, reason in (
        ("source_file_unforgeable", "seal_must_not_claim_source_unforgeable"),
        (
            "cryptographic_authenticity_proven",
            "seal_must_not_claim_cryptographic_authenticity",
        ),
        ("product_ready", "seal_must_not_claim_product_ready"),
        (
            "custom_codex_ui_visibility_proven",
            "seal_must_not_claim_custom_codex_ui",
        ),
        ("native_free_chat_router_proven", "seal_must_not_claim_native_router"),
    ):
        if source_seal.get(field) is True or working_seal.get(field) is True:
            failures.append(reason)
    source_seal_failures = source_seal.get("proof_seal_failures")
    working_seal_failures = working_seal.get("proof_seal_failures")
    if _sequence_not_empty(source_seal_failures):
        failures.append("source_proof_seal_failures_not_empty")
    if _sequence_not_empty(working_seal_failures):
        failures.append("working_flow_proof_seal_failures_not_empty")
    return sorted(set(failures)), {
        "strict_sealed_evidence": True,
        "source_file_seal_verified": source_seal.get("proof_seal_verified") is True,
        "working_flow_file_seal_verified": (
            working_seal.get("proof_seal_verified") is True
        ),
        "source_file_authenticity_proven": not failures,
        "source_file_unforgeable": False,
        "cryptographic_authenticity_proven": False,
        "source_proof_seal_machine_error_code": _safe_text(
            source_seal.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_proof_seal_machine_error_code": _safe_text(
            working_seal.get("machine_error_code"),
            limit=96,
        ),
        "source_proof_seal_failures": (
            list(source_seal_failures)
            if isinstance(source_seal_failures, Sequence)
            and not isinstance(source_seal_failures, (str, bytes))
            else []
        ),
        "working_flow_proof_seal_failures": (
            list(working_seal_failures)
            if isinstance(working_seal_failures, Sequence)
            and not isinstance(working_seal_failures, (str, bytes))
            else []
        ),
    }


def build_custom_codex_hook_origin_proof_packet(
    *,
    paths: RuntimePaths,
    integrated_live_provider_proof: Mapping[str, Any],
    working_flow_delivery_proof: Mapping[str, Any],
    file_metadata: Mapping[str, Any] | None = None,
    strict_sealed_evidence: bool = False,
    source_seal_packet: Mapping[str, Any] | None = None,
    working_flow_seal_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(file_metadata or {})
    source = (
        integrated_live_provider_proof
        if isinstance(integrated_live_provider_proof, Mapping)
        else {}
    )
    working_flow = (
        working_flow_delivery_proof
        if isinstance(working_flow_delivery_proof, Mapping)
        else {}
    )
    source_failures, source_unsafe = _source_failures(source, metadata)
    working_flow_failures, working_flow_unsafe = _working_flow_failures(
        working_flow,
        metadata,
    )
    profile_extra, profile_failures, profile_unsafe = _profile_identity(
        paths=paths,
        source=source,
    )
    join_failures = _join_failures(source, working_flow)
    seal_failures, seal_extra = _seal_failures(
        strict_sealed_evidence=strict_sealed_evidence,
        source_seal_packet=source_seal_packet,
        working_flow_seal_packet=working_flow_seal_packet,
    )
    unsafe_failures = sorted(set(source_unsafe + working_flow_unsafe + profile_unsafe))
    blocking_reasons = sorted(
        set(
            source_failures
            + working_flow_failures
            + profile_failures
            + join_failures
            + seal_failures
        )
    )
    ok = not blocking_reasons and not unsafe_failures
    machine_error_code = _machine_error_code(
        source_failures=source_failures,
        working_flow_failures=working_flow_failures,
        profile_failures=profile_failures,
        join_failures=join_failures,
        seal_failures=seal_failures,
        unsafe_failures=unsafe_failures,
    )
    prompt_digest = _hex_sha256(source.get("prompt_digest"))
    runtime_digest = _hex_sha256(source.get("runtime_context_digest"))
    live_provider_response_digest = _hex_sha256(
        working_flow.get("live_provider_response_digest")
    )

    extra = {
        **metadata,
        **profile_extra,
        **seal_extra,
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_HOOK_ORIGIN_PROOF_PACKET_KIND,
        "hook_origin_truth_source": (
            CUSTOM_CODEX_HOOK_ORIGIN_TRUTH_SOURCE if ok else "not_proven"
        ),
        "integrated_live_provider_proof_kind": _safe_text(
            source.get("packet_kind"),
            limit=80,
        ),
        "integrated_live_provider_proof_status": _safe_text(
            source.get("status"),
            limit=32,
        ),
        "integrated_live_provider_proof_machine_error_code": _safe_text(
            source.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_delivery_proof_kind": _safe_text(
            working_flow.get("packet_kind"),
            limit=80,
        ),
        "working_flow_delivery_proof_status": _safe_text(
            working_flow.get("status"),
            limit=32,
        ),
        "working_flow_delivery_proof_machine_error_code": _safe_text(
            working_flow.get("machine_error_code"),
            limit=96,
        ),
        "custom_profile_identity_bound": ok,
        "custom_profile_identity_inputs_valid": not profile_failures,
        "source_file_authenticity_proven": bool(
            strict_sealed_evidence and not seal_failures
        ),
        "source_file_authentication_scope": (
            "sealed_file_backed_command_packet_semantics_and_profile_digest_join_no_signature"
            if strict_sealed_evidence
            else "file_backed_command_packet_semantics_and_profile_digest_join_no_signature"
        ),
        "does_not_prove_source_file_unforgeable": True,
        "command_origin_surface": (
            COMMAND_ORIGIN_SURFACE_CUSTOM_CODEX_FLOW if ok else ""
        ),
        "command_origin_proven": ok,
        "custom_codex_flow_proven": ok,
        "custom_codex_origin_proven": ok,
        "native_custom_codex_flow_proven": ok,
        "native_router_hook_observed": ok,
        "user_prompt_submit_hook_observed": ok,
        "hook_producer_ledger_proven": source.get("hook_producer_ledger_proven") is True,
        "user_prompt_submit_hook_ran": source.get("user_prompt_submit_hook_ran") is True,
        "hook_ledger_written": source.get("hook_ledger_written") is True,
        "hook_prompt_digest_bound": source.get("hook_prompt_digest_bound") is True,
        "hook_runtime_context_digest_bound": (
            source.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": source.get("thread_or_turn_digest_bound") is True,
        "hook_config_digest_bound": source.get("hook_config_digest_bound") is True,
        "prompt_digest": prompt_digest,
        "hook_prompt_digest": _hex_sha256(source.get("hook_prompt_digest")),
        "runtime_context_digest": runtime_digest,
        "hook_runtime_context_digest": _hex_sha256(
            source.get("hook_runtime_context_digest")
        ),
        "trusted_hook_config_sha256": _hex_sha256(
            source.get("trusted_hook_config_sha256")
        ),
        "loaded_hook_config_sha256": _hex_sha256(
            source.get("loaded_hook_config_sha256")
        ),
        "source_live_provider_source_kind": _safe_text(
            source.get("live_provider_source_kind"),
            limit=80,
        ),
        "source_live_provider_file_backed": bool(
            _safe_text(source.get("live_provider_source_kind"), limit=80)
            == "file_backed_external_models_live_format_check"
            and source.get("live_provider_proof_file_read") is True
            and source.get("live_provider_proof_file_valid_json") is True
            and source.get("live_provider_proof_file_mapping") is True
        ),
        "source_live_provider_embedded_runtime_cli": (
            _safe_text(source.get("live_provider_source_kind"), limit=80)
            == "runtime_context_allowed_cli_command"
        ),
        "alias_context_read": source.get("alias_context_read") is True,
        "allowed_api_route_ids_enforced": (
            source.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": source.get("route_id_allowed") is True,
        "api_lane_called": (
            source.get("api_lane_called") is True
            and working_flow.get("api_lane_called") is True
        ),
        "dispatch_status": _safe_text(source.get("dispatch_status"), limit=32),
        "dispatch_proven": source.get("dispatch_proven") is True,
        "route_bound_dispatch_proven": (
            source.get("route_bound_dispatch_proven") is True
        ),
        "live_provider_response_proven": (
            source.get("live_provider_response_proven") is True
            and working_flow.get("live_provider_response_proven") is True
        ),
        "external_live_provider_response_proven": (
            source.get("external_live_provider_response_proven") is True
            and working_flow.get("external_live_provider_response_proven") is True
        ),
        "live_provider_response_digest": live_provider_response_digest,
        "live_provider_response_digest_bound_to_handoff": (
            working_flow.get("live_provider_response_digest_bound_to_handoff") is True
        ),
        "approved_handoff_ready": source.get("approved_handoff_ready") is True,
        "handoff_delivered": (
            source.get("handoff_delivered") is True
            and working_flow.get("handoff_delivered") is True
        ),
        "delivery_observed": (
            source.get("delivery_observed") is True
            and working_flow.get("delivery_observed") is True
        ),
        "codex_working_flow_delivery_proven": (
            working_flow.get("codex_working_flow_delivery_proven") is True
        ),
        "codex_exec_assistant_continuation_proven": (
            working_flow.get("codex_exec_assistant_continuation_proven") is True
        ),
        "codex_exec_transcript_sha256": _hex_sha256(
            working_flow.get("codex_exec_transcript_sha256")
        ),
        "assistant_binding_digest": _hex_sha256(
            working_flow.get("assistant_binding_digest")
        ),
        "source_handoff_payload_digest": _hex_sha256(
            working_flow.get("source_handoff_payload_digest")
        ),
        "working_flow_handoff_payload_digest": _hex_sha256(
            working_flow.get("working_flow_handoff_payload_digest")
        ),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_expected_text_recorded": False,
        "expected_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "browser_can_supply_hook_origin_authority": False,
        "browser_can_supply_profile_identity_authority": False,
        "source_failures": source_failures,
        "working_flow_failures": working_flow_failures,
        "profile_failures": profile_failures,
        "join_failures": join_failures,
        "seal_failures": seal_failures,
        "unsafe_claim_failures": unsafe_failures,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved Custom Codex UserPromptSubmit hook origin, live API lane dispatch, and Codex working-flow delivery."
            if ok
            else "WBP blocked Custom Codex hook-origin proof before origin promotion."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=[],
        extra=extra,
    )


def run_custom_codex_hook_origin_proof_command(
    *,
    paths: RuntimePaths,
    integrated_live_provider_proof_file: str,
    working_flow_delivery_proof_file: str,
    strict_sealed_evidence: bool = False,
    integrated_live_provider_proof_seal_file: str | None = None,
    working_flow_delivery_proof_seal_file: str | None = None,
) -> dict[str, Any]:
    source_path = Path(integrated_live_provider_proof_file).expanduser()
    working_flow_path = Path(working_flow_delivery_proof_file).expanduser()
    source_packet, source_metadata = _read_json_mapping_file(
        source_path,
        prefix="integrated_live_provider_proof",
    )
    working_flow_packet, working_flow_metadata = _read_json_mapping_file(
        working_flow_path,
        prefix="working_flow_delivery_proof",
    )
    source_seal_packet: Mapping[str, Any] = {}
    working_flow_seal_packet: Mapping[str, Any] = {}
    if strict_sealed_evidence:
        source_expected_inputs: dict[str, str] = {}
        working_expected_inputs = {
            _safe_text(source_packet.get("packet_kind"), limit=120): _hex_sha256(
                source_metadata.get("integrated_live_provider_proof_file_sha256")
            )
        }
        source_seal_packet, _ = verify_proof_seal(
            packet_file=source_path,
            seal_file=integrated_live_provider_proof_seal_file
            or default_seal_path(source_path),
            expected_packet_kind=REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
            expected_input_packet_hashes=source_expected_inputs,
            expected_runtime_context_digest=_hex_sha256(
                source_packet.get("runtime_context_digest")
            ),
            expected_hook_ledger_digest=_path_sha256(hook_ledger_path(paths)),
            expected_profile_hook_config_digest=_hex_sha256(
                source_packet.get("loaded_hook_config_sha256")
            ),
        )
        working_flow_seal_packet, _ = verify_proof_seal(
            packet_file=working_flow_path,
            seal_file=working_flow_delivery_proof_seal_file
            or default_seal_path(working_flow_path),
            expected_packet_kind=CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
            expected_input_packet_hashes=working_expected_inputs,
        )
    return build_custom_codex_hook_origin_proof_packet(
        paths=paths,
        integrated_live_provider_proof=source_packet,
        working_flow_delivery_proof=working_flow_packet,
        file_metadata={**source_metadata, **working_flow_metadata},
        strict_sealed_evidence=strict_sealed_evidence,
        source_seal_packet=source_seal_packet,
        working_flow_seal_packet=working_flow_seal_packet,
    )
