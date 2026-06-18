# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_origin_bound_api_dispatch_proof import (
    CUSTOM_ORIGIN_BOUND_API_DISPATCH_OK,
    CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND,
)
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths


CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_PACKET_KIND = (
    "wbp_custom_origin_bound_live_provider_join"
)

CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_OK = "OK"
CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_CONTEXT_INVALID = (
    "WBP_CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_CONTEXT_INVALID"
)
CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_DISPATCH_NOT_PROVEN = (
    "WBP_CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_DISPATCH_NOT_PROVEN"
)
CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_DIGEST_MISMATCH = (
    "WBP_CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_DIGEST_MISMATCH"
)
CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_ROUTE_MISMATCH = (
    "WBP_CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_ROUTE_MISMATCH"
)
CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_LIVE_PROVIDER_NOT_PROVEN = (
    "WBP_CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_NOT_PROVEN"
)
CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_UNSAFE_SOURCE = (
    "WBP_CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_UNSAFE_SOURCE"
)

_EXPECTED_TEXT_MARKER_RE = re.compile(r"^[A-Z0-9_]{1,128}$")


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _packet_file_metadata(path: Path, *, prefix: str) -> tuple[dict[str, Any], dict[str, Any]]:
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


def _allowed_route_ids(runtime_context: Mapping[str, Any]) -> set[str]:
    allowed = runtime_context.get("allowed_api_route_ids")
    if not isinstance(allowed, Sequence) or isinstance(allowed, (str, bytes)):
        return set()
    return {route for route in allowed if isinstance(route, str) and route}


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


def _safe_expected_text_marker(value: str) -> bool:
    return bool(_EXPECTED_TEXT_MARKER_RE.fullmatch(value))


def _context_failures(
    runtime_context: Mapping[str, Any],
    context_file_metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field, reason in (
        ("runtime_context_file_read", "runtime_context_file_not_read"),
        ("runtime_context_file_valid_json", "runtime_context_file_json_not_valid"),
        ("runtime_context_file_mapping", "runtime_context_file_not_mapping"),
    ):
        if context_file_metadata.get(field) is not True:
            failures.append(reason)
    if not _allowed_route_ids(runtime_context):
        failures.append("runtime_context_allowed_routes_missing")
    return sorted(set(failures))


def _dispatch_required_failures(dispatch_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if dispatch_packet.get("packet_kind") != CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND:
        failures.append("custom_origin_bound_dispatch_packet_kind_invalid")
    if dispatch_packet.get("status") != "ok":
        failures.append("custom_origin_bound_dispatch_packet_not_ok")
    if (
        dispatch_packet.get("machine_error_code")
        != CUSTOM_ORIGIN_BOUND_API_DISPATCH_OK
    ):
        failures.append("custom_origin_bound_dispatch_machine_error_not_ok")
    if dispatch_packet.get("changed_files") not in ([], ()):
        failures.append("custom_origin_bound_dispatch_changed_files_not_empty")
    if dispatch_packet.get("effect") != EFFECT_PROBE:
        failures.append("custom_origin_bound_dispatch_effect_not_probe")
    for field, reason in (
        ("custom_origin_bound", "custom_origin_not_bound"),
        ("custom_ui_origin_admitted", "custom_ui_origin_not_admitted"),
        ("custom_codex_flow_origin_admitted", "custom_codex_flow_origin_not_admitted"),
        ("real_ledger_bound_api_dispatch_proven", "ledger_bound_dispatch_not_proven"),
        ("prompt_digest_bound_to_custom_origin_and_dispatch", "prompt_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("alias_bound", "alias_not_bound"),
        ("alias_resolved", "alias_not_resolved"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("api_lane_called", "api_lane_not_called"),
        ("api_lane_dispatch_admitted", "api_lane_dispatch_not_admitted"),
        ("api_lane_provider_called", "api_lane_provider_not_called"),
        ("dispatch_attempted", "dispatch_not_attempted"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("provider_response_proven", "controlled_provider_response_not_proven"),
        ("controlled_provider_response_proven", "controlled_provider_response_not_proven"),
        ("selected_api_route_id_present", "selected_api_route_id_not_present"),
    ):
        if dispatch_packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(dispatch_packet.get("prompt_digest")):
        failures.append("custom_origin_bound_dispatch_prompt_digest_missing")
    if not _hex_sha256(dispatch_packet.get("selected_api_route_id_sha256")):
        failures.append("selected_api_route_id_digest_missing")
    return sorted(set(failures))


def _dispatch_unsafe_failures(dispatch_packet: Mapping[str, Any]) -> list[str]:
    checks = {
        "live_provider_proven": "source_must_not_claim_live_provider",
        "live_provider_response_proven": "source_must_not_claim_live_provider",
        "external_live_provider_response_proven": "source_must_not_claim_live_provider",
        "handoff_file_written": "source_must_not_claim_handoff",
        "handoff_delivered": "source_must_not_claim_handoff",
        "delivery_observed": "source_must_not_claim_delivery",
        "custom_codex_ui_visibility_proven": "source_must_not_claim_ui_visibility",
        "codex_working_flow_delivery_proven": "source_must_not_claim_working_flow",
        "native_free_chat_router_proven": "source_must_not_claim_native_router",
        "native_free_chat_router_product_ready": "source_must_not_claim_product_ready",
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
        {reason for field, reason in checks.items() if dispatch_packet.get(field) is True}
    )


def _live_provider_unsafe_failures(
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
        "raw_expected_text_recorded": "live_provider_raw_expected_text_recorded",
        "raw_backend_details_exposed": "live_provider_raw_backend_details_exposed",
        "secret_value_exposed": "live_provider_secret_value_exposed",
        "local_imitation_used": "live_provider_local_imitation_used",
        "native_codex_subagent_used_as_dip": (
            "live_provider_native_codex_subagent_used_as_dip"
        ),
        "handoff_delivered": "live_provider_must_not_claim_handoff",
        "custom_codex_ui_visibility_proven": (
            "live_provider_must_not_claim_ui_visibility"
        ),
        "product_ready": "live_provider_must_not_claim_product_ready",
    }
    failures = [
        reason
        for field, reason in checks.items()
        if live_provider_packet.get(field) is True or data_mapping.get(field) is True
    ]
    return sorted(set(failures))


def _live_provider_required_failures(
    *,
    live_provider_packet: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    dispatch_packet: Mapping[str, Any],
    expected_text: str,
) -> list[str]:
    failures: list[str] = []
    selected_route_id = _selected_route_id_from_context(runtime_context, dispatch_packet)
    selected_route_hash = _sha256_text(selected_route_id) if selected_route_id else ""
    dispatch_route_hash = _hex_sha256(dispatch_packet.get("selected_api_route_id_sha256"))
    allowed_route_ids = _allowed_route_ids(runtime_context)
    live_cli_declared, live_cli_route_bound = _runtime_context_declares_live_cli(
        runtime_context,
        selected_route_id,
    )

    if not expected_text:
        failures.append("live_provider_expected_text_missing")
    elif not _safe_expected_text_marker(expected_text):
        failures.append("live_provider_expected_text_not_safe_marker")
    if not selected_route_id:
        failures.append("live_provider_route_not_resolved")
    if selected_route_id and selected_route_id not in allowed_route_ids:
        failures.append("live_provider_route_not_allowed")
    if selected_route_hash and dispatch_route_hash and selected_route_hash != dispatch_route_hash:
        failures.append("dispatch_route_digest_mismatch")
    if not dispatch_route_hash:
        failures.append("dispatch_route_digest_missing")
    if not live_cli_declared:
        failures.append("live_provider_cli_command_not_declared")
    if not live_cli_route_bound:
        failures.append("live_provider_cli_command_not_route_bound")

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
    requested_model = _safe_text(data_mapping.get("requested_model"), limit=256)
    if selected_route_id and requested_model != selected_route_id:
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
    if data_mapping.get("fallback_used") is not False:
        failures.append("live_provider_fallback_used")
    fallback_chain = data_mapping.get("fallback_chain")
    if selected_route_id and fallback_chain != [selected_route_id]:
        failures.append("live_provider_fallback_chain_not_route_only")
    if data_mapping.get("request_count") != 1:
        failures.append("live_provider_request_count_invalid")
    if data_mapping.get("retry_count") not in (0, None):
        failures.append("live_provider_retry_count_invalid")
    if data_mapping.get("changed_files") not in ([], (), None):
        failures.append("live_provider_data_changed_files_not_empty")
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
    failures.extend(_live_provider_unsafe_failures(live_provider_packet))
    return sorted(set(failures))


def _machine_error_code(
    *,
    context_failures: Sequence[str],
    dispatch_failures: Sequence[str],
    prompt_digest_bound: bool,
    route_failures: Sequence[str],
    live_provider_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if not (
        context_failures
        or dispatch_failures
        or not prompt_digest_bound
        or route_failures
        or live_provider_failures
        or unsafe_failures
    ):
        return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_OK
    if unsafe_failures:
        return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_UNSAFE_SOURCE
    if context_failures:
        return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_CONTEXT_INVALID
    if dispatch_failures:
        return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_DISPATCH_NOT_PROVEN
    if not prompt_digest_bound:
        return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_DIGEST_MISMATCH
    if route_failures:
        return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_ROUTE_MISMATCH
    return CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_LIVE_PROVIDER_NOT_PROVEN


def build_custom_origin_bound_live_provider_join_packet(
    *,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None,
    custom_origin_bound_dispatch_packet: Mapping[str, Any] | None,
    live_provider_packet: Mapping[str, Any] | None,
    live_provider_expected_text: object,
    context_file_metadata: Mapping[str, Any] | None = None,
    dispatch_file_metadata: Mapping[str, Any] | None = None,
    live_provider_file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    context = _mapping(runtime_context)
    dispatch_packet = _mapping(custom_origin_bound_dispatch_packet)
    live_packet = _mapping(live_provider_packet)
    context_metadata = dict(context_file_metadata or {})
    dispatch_metadata = dict(dispatch_file_metadata or {})
    live_metadata = dict(live_provider_file_metadata or {})
    prompt = str(prompt_text or "")
    expected_text = _safe_text(live_provider_expected_text, limit=512)
    secret_list = [
        prompt,
        expected_text,
        *list(secret_values or []),
        *_route_secret_values(context),
    ]

    entry_packet = build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
        secret_values=secret_list,
    )
    expected_prompt_digest = _hex_sha256(entry_packet.get("prompt_digest"))
    dispatch_prompt_digest = _hex_sha256(dispatch_packet.get("prompt_digest"))
    prompt_digest_bound = bool(
        expected_prompt_digest
        and dispatch_prompt_digest
        and expected_prompt_digest == dispatch_prompt_digest
    )

    context_failures = _context_failures(context, context_metadata)
    dispatch_failures = _dispatch_required_failures(dispatch_packet)
    unsafe_failures = sorted(
        set(
            _dispatch_unsafe_failures(dispatch_packet)
            + _live_provider_unsafe_failures(live_packet)
        )
    )
    live_provider_failures: list[str] = []
    if not context_failures and not dispatch_failures and prompt_digest_bound:
        live_provider_failures = _live_provider_required_failures(
            live_provider_packet=live_packet,
            runtime_context=context,
            dispatch_packet=dispatch_packet,
            expected_text=expected_text,
        )

    selected_route_id = _selected_route_id_from_context(context, dispatch_packet)
    selected_route_hash = _sha256_text(selected_route_id) if selected_route_id else ""
    dispatch_route_hash = _hex_sha256(dispatch_packet.get("selected_api_route_id_sha256"))
    live_data = live_packet.get("data") if isinstance(live_packet.get("data"), Mapping) else {}
    live_requested_route = _safe_text(live_data.get("requested_model"), limit=256)
    live_route_hash = _sha256_text(live_requested_route) if live_requested_route else ""
    live_cli_command_parts = _runtime_context_live_cli_command_parts(context)
    live_cli_declared, live_cli_route_bound = _runtime_context_declares_live_cli(
        context,
        selected_route_id,
    )
    allowed_route_ids = _allowed_route_ids(context)
    route_failures: list[str] = []
    if selected_route_id and selected_route_id not in allowed_route_ids:
        route_failures.append("selected_route_not_allowed")
    if not selected_route_hash or selected_route_hash != dispatch_route_hash:
        route_failures.append("dispatch_route_digest_mismatch")
    if not live_route_hash or live_route_hash != selected_route_hash:
        route_failures.append("live_provider_route_digest_mismatch")
    route_failures = sorted(set(route_failures))

    response_preview = _safe_text(live_data.get("response_preview_bounded"), limit=512)
    expected_text_digest = _sha256_text(expected_text) if expected_text else ""
    live_response_digest = _sha256_text(response_preview) if response_preview else ""
    live_provider_response_proven = bool(
        not live_provider_failures
        and live_packet.get("status") == "ok"
        and live_data.get("expected_text_observed") is True
        and expected_text_digest
        and live_response_digest == expected_text_digest
        and live_route_hash
        and live_route_hash == selected_route_hash
    )

    blocking_reasons = sorted(
        set(
            context_failures
            + dispatch_failures
            + ([] if prompt_digest_bound else ["prompt_digest_mismatch"])
            + route_failures
            + live_provider_failures
            + unsafe_failures
            + _safe_reasons(dispatch_packet.get("blocking_reasons"))
            + _safe_reasons(live_packet.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        context_failures=context_failures,
        dispatch_failures=dispatch_failures,
        prompt_digest_bound=prompt_digest_bound,
        route_failures=route_failures,
        live_provider_failures=live_provider_failures,
        unsafe_failures=unsafe_failures,
    )

    extra = {
        **context_metadata,
        **dispatch_metadata,
        **live_metadata,
        "schema_version": 1,
        "packet_kind": CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_PACKET_KIND,
        "proof_scope": "custom_origin_bound_dispatch_to_live_provider_response",
        "router_entry_packet_kind": _safe_text(entry_packet.get("packet_kind"), limit=80),
        "router_entry_status": _safe_text(entry_packet.get("status"), limit=32),
        "router_entry_machine_error_code": _safe_text(
            entry_packet.get("machine_error_code"),
            limit=96,
        ),
        "custom_origin_bound_dispatch_packet_kind": _safe_text(
            dispatch_packet.get("packet_kind"),
            limit=96,
        ),
        "custom_origin_bound_dispatch_status": _safe_text(
            dispatch_packet.get("status"),
            limit=32,
        ),
        "custom_origin_bound_dispatch_machine_error_code": _safe_text(
            dispatch_packet.get("machine_error_code"),
            limit=96,
        ),
        "live_provider_packet_status": _safe_text(live_packet.get("status"), limit=32),
        "live_provider_packet_machine_error_code": _safe_text(
            live_packet.get("machine_error_code"),
            limit=96,
        ),
        "custom_origin_bound_dispatch_proven": bool(
            ok
            and dispatch_packet.get("custom_origin_bound") is True
            and dispatch_packet.get("dispatch_proven") is True
        ),
        "custom_origin_bound": bool(ok and dispatch_packet.get("custom_origin_bound") is True),
        "custom_ui_origin_admitted": bool(
            ok and dispatch_packet.get("custom_ui_origin_admitted") is True
        ),
        "custom_codex_flow_origin_admitted": bool(
            ok and dispatch_packet.get("custom_codex_flow_origin_admitted") is True
        ),
        "real_ledger_bound_api_dispatch_proven": bool(
            ok and dispatch_packet.get("real_ledger_bound_api_dispatch_proven") is True
        ),
        "prompt_digest": dispatch_prompt_digest if ok and prompt_digest_bound else "",
        "expected_prompt_digest_present": bool(expected_prompt_digest),
        "dispatch_prompt_digest_present": bool(dispatch_prompt_digest),
        "same_prompt_digest": bool(ok and prompt_digest_bound),
        "prompt_digest_bound_to_custom_origin_dispatch": bool(
            ok and dispatch_packet.get("prompt_digest_bound_to_custom_origin_and_dispatch") is True
        ),
        "alias_context_read": bool(ok and dispatch_packet.get("alias_context_read") is True),
        "alias_bound": bool(ok and dispatch_packet.get("alias_bound") is True),
        "alias_resolved": bool(ok and dispatch_packet.get("alias_resolved") is True),
        "selected_alias": _safe_text(dispatch_packet.get("selected_alias"), limit=80)
        if ok
        else "",
        "selected_alias_lane": _safe_text(
            dispatch_packet.get("selected_alias_lane"),
            limit=32,
        )
        if ok
        else "",
        "selected_slot": _safe_text(dispatch_packet.get("selected_slot"), limit=64)
        if ok
        else "",
        "route_id_allowed": bool(ok and dispatch_packet.get("route_id_allowed") is True),
        "allowed_api_route_ids_enforced": bool(
            ok and dispatch_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_count": len(allowed_route_ids) if ok else 0,
        "same_allowed_route_binding": bool(
            ok
            and selected_route_hash
            and dispatch_route_hash == selected_route_hash
            and live_route_hash == selected_route_hash
            and selected_route_id in allowed_route_ids
        ),
        "selected_api_route_id_present": bool(
            ok and dispatch_packet.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": dispatch_route_hash if ok else "",
        "live_provider_route_id_sha256": live_route_hash if ok else "",
        "live_provider_route_bound_to_context": bool(
            ok and selected_route_id and selected_route_id in allowed_route_ids
        ),
        "live_provider_cli_command_declared": bool(ok and live_cli_declared),
        "live_provider_cli_command_route_bound": bool(ok and live_cli_route_bound),
        "live_provider_cli_command_sha256": (
            _command_parts_sha256(live_cli_command_parts) if ok else ""
        ),
        "api_lane_called": bool(ok and dispatch_packet.get("api_lane_called") is True),
        "api_lane_dispatch_admitted": bool(
            ok and dispatch_packet.get("api_lane_dispatch_admitted") is True
        ),
        "api_lane_provider_called": bool(
            ok and dispatch_packet.get("api_lane_provider_called") is True
        ),
        "controlled_provider_response_proven": bool(
            ok and dispatch_packet.get("controlled_provider_response_proven") is True
        ),
        "controlled_provider_response_digest": (
            _hex_sha256(dispatch_packet.get("provider_response_digest")) if ok else ""
        ),
        "dispatch_attempted": bool(ok and dispatch_packet.get("dispatch_attempted") is True),
        "dispatch_status": "proven" if ok else "blocked",
        "dispatch_proven": bool(ok and dispatch_packet.get("dispatch_proven") is True),
        "route_bound_dispatch_proven": bool(
            ok and dispatch_packet.get("route_bound_dispatch_proven") is True
        ),
        "route_bound_request_sha256": (
            _hex_sha256(dispatch_packet.get("route_bound_request_sha256")) if ok else ""
        ),
        "live_provider_called": bool(ok and live_provider_response_proven),
        "live_provider_attempted": bool(live_packet),
        "live_provider_check_kind": _safe_text(live_data.get("check_kind"), limit=80)
        if ok
        else "",
        "live_provider_verification_scope": _safe_text(
            live_data.get("verification_scope"),
            limit=80,
        )
        if ok
        else "",
        "live_provider_route_state": _safe_text(live_data.get("route_state"), limit=80)
        if ok
        else "",
        "live_provider_network_dependent": bool(
            ok and live_data.get("network_dependent") is True
        ),
        "network_dependent": bool(ok and live_data.get("network_dependent") is True),
        "live_provider_request_count": int(live_data.get("request_count") or 0)
        if ok
        else 0,
        "expected_text_present": bool(expected_text),
        "expected_text_observed": bool(
            ok and live_data.get("expected_text_observed") is True
        ),
        "expected_text_digest": expected_text_digest if ok else "",
        "expected_text_recorded": False,
        "raw_expected_text_recorded": False,
        "live_provider_response_digest": live_response_digest if ok else "",
        "response_digest_bound": bool(ok and live_provider_response_proven),
        "response_digest_bound_to_expected_text": bool(
            ok and expected_text_digest and live_response_digest == expected_text_digest
        ),
        "live_provider_response_bound_to_expected_text": bool(
            ok and live_provider_response_proven
        ),
        "live_provider_response_bound_to_route": bool(
            ok and live_provider_response_proven and live_route_hash == selected_route_hash
        ),
        "live_provider_changed_files_empty": bool(
            ok
            and live_packet.get("changed_files") in ([], ())
            and live_data.get("changed_files") in ([], (), None)
        ),
        "live_provider_state_written": live_data.get("state_written") is True,
        "live_provider_evidence_written": live_data.get("evidence_written") is True,
        "live_provider_file_mutation_attempted": (
            live_data.get("file_mutation_attempted") is True
        ),
        "live_provider_codex_history_sent": live_data.get("codex_history_sent") is True,
        "live_provider_repo_context_sent": live_data.get("repo_context_sent") is True,
        "live_provider_status": "proven" if ok and live_provider_response_proven else "blocked",
        "live_provider_proven": bool(ok and live_provider_response_proven),
        "live_provider_response_proven": bool(ok and live_provider_response_proven),
        "external_live_provider_response_proven": bool(
            ok and live_provider_response_proven
        ),
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
        "does_not_prove_handoff": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "context_failures": context_failures,
        "dispatch_required_failures": dispatch_failures,
        "route_binding_failures": route_failures,
        "live_provider_failures": live_provider_failures,
        "unsafe_source_failures": unsafe_failures,
        "blocking_reasons": blocking_reasons,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "live_provider_route_id_recorded": False,
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
            "WBP proved Custom-origin-bound dispatch joined to a live provider response."
            if ok
            else "WBP blocked Custom-origin-bound live-provider join."
        ),
        machine_error_code=machine_error_code,
        liveness="network_dependent" if ok else "not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=secret_list,
        extra=extra,
    )


def run_custom_origin_bound_live_provider_join_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    custom_origin_bound_dispatch_proof_file: str,
    live_provider_proof_file: str,
    live_provider_expected_text: object,
    runtime_context_file: str | None = None,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    dispatch_packet, dispatch_metadata = _packet_file_metadata(
        Path(custom_origin_bound_dispatch_proof_file).expanduser(),
        prefix="custom_origin_bound_dispatch_proof",
    )
    live_packet, live_metadata = _packet_file_metadata(
        Path(live_provider_proof_file).expanduser(),
        prefix="live_provider_proof",
    )
    return build_custom_origin_bound_live_provider_join_packet(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        custom_origin_bound_dispatch_packet=dispatch_packet,
        live_provider_packet=live_packet,
        live_provider_expected_text=live_provider_expected_text,
        context_file_metadata=context_metadata,
        dispatch_file_metadata=dispatch_metadata,
        live_provider_file_metadata=live_metadata,
    )
