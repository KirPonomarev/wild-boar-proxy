# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256
from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_codex_ui_visibility_proof import CUSTOM_CODEX_UI_VISIBILITY_PACKET_KIND
from .official_e2e_working_flow_proof_join import (
    OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_OK,
    OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND,
)
from .router_hook_entry import _safe_text
from .runtime import write_json_atomic


FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND = "wbp_full_runtime_dispatch_proof"
FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME = "full-runtime-dispatch-proof.packet.json"

FULL_RUNTIME_DISPATCH_OK = "OK"
FULL_RUNTIME_DISPATCH_UPSTREAM_INVALID = "WBP_FULL_RUNTIME_DISPATCH_UPSTREAM_INVALID"
FULL_RUNTIME_DISPATCH_UI_INVALID = "WBP_FULL_RUNTIME_DISPATCH_UI_INVALID"
FULL_RUNTIME_DISPATCH_NOT_BOUND = "WBP_FULL_RUNTIME_DISPATCH_NOT_BOUND"
FULL_RUNTIME_DISPATCH_UNSAFE_SOURCE = "WBP_FULL_RUNTIME_DISPATCH_UNSAFE_SOURCE"

_UPSTREAM_REQUIRED_TRUE_FIELDS = (
    "official_e2e_working_flow_proven",
    "custom_codex_hook_to_official_working_flow_bound",
    "custom_codex_flow_origin_proven",
    "hook_producer_ledger_proven",
    "user_prompt_submit_hook_ran",
    "hook_ledger_written",
    "hook_prompt_digest_bound",
    "hook_runtime_context_digest_bound",
    "thread_or_turn_digest_bound",
    "hook_event_digest_bound_to_working_flow",
    "hook_thread_or_turn_digest_bound_to_working_flow",
    "hook_session_digest_bound_to_working_flow",
    "prompt_digest_bound_to_working_flow",
    "runtime_context_digest_bound_to_working_flow",
    "alias_context_read",
    "allowed_api_route_ids_enforced",
    "route_id_allowed",
    "api_lane_called",
    "dispatch_proven",
    "route_bound_dispatch_proven",
    "provider_response_proven",
    "live_provider_response_proven",
    "external_live_provider_response_proven",
    "approved_handoff_ready",
    "approved_handoff_payload_sanitized",
    "handoff_delivered",
    "delivery_observed",
    "handoff_payload_bound_to_working_flow",
    "official_delivery_candidate_lineage_proven",
    "official_observation_lineage_file_backed",
    "approved_delivery_surface_proven",
    "codex_exec_assistant_continuation_proven",
    "codex_working_flow_delivery_proven",
    "official_working_flow_delivery_joined_to_working_flow",
)
_UI_REQUIRED_TRUE_FIELDS = (
    "custom_codex_ui_visibility_proven",
    "visible_response_observed",
    "visible_response_bound_to_handoff",
    "visible_response_after_dispatch",
    "visible_response_request_bound",
    "stale_visibility_rejected",
    "source_packet_file_backed",
    "visible_source_binding_valid",
    "visible_source_binding_proven",
    "custom_codex_visible_source_binding_proven",
    "visible_source_bound_to_handoff",
    "visible_source_after_delivery",
    "working_flow_delivery_proven",
    "codex_working_flow_delivery_proven",
    "handoff_payload_digest_present",
    "native_ui_source_allowed",
    "native_ui_observer_file_backed",
    "custom_codex_process_bound",
    "custom_codex_window_observed",
    "custom_codex_profile_bound",
    "custom_codex_native_app_usable",
    "input_capable_ui_observed",
    "native_prompt_submitted",
    "assistant_turn_completed_observed",
    "custom_response_exact_token_observed",
    "custom_response_text_read_without_storing",
    "expected_visible_text_contains_handoff_digest",
    "expected_visible_text_contains_request_id",
    "request_id_valid",
    "native_request_id_bound",
    "native_codex_subagent_absence_proven",
)
_UPSTREAM_REQUIRED_FALSE_FIELDS = (
    "delivery_counts_as_custom_codex_ui",
    "native_free_chat_router_proven",
    "native_free_chat_router_product_ready",
    "native_free_chat_router_delivery_proven",
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "raw_jsonl_recorded",
    "tool_call_arguments_recorded",
    "route_candidate_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "state_written",
    "evidence_written",
    "file_mutation_attempted",
)
_UI_REQUIRED_FALSE_FIELDS = (
    "delivery_counts_as_custom_codex_ui",
    "native_free_chat_router_proven",
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "raw_dom_exposed",
    "raw_ax_tree_exposed",
    "raw_jsonl_recorded",
    "tool_call_arguments_recorded",
    "route_candidate_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "state_written",
    "evidence_written",
    "file_mutation_attempted",
)
_UPSTREAM_REQUIRED_EMPTY_FIELDS = (
    "real_custom_hook_failures",
    "official_working_flow_delivery_join_failures",
    "source_unsafe_claim_failures",
    "digest_binding_failures",
    "blocking_reasons",
    "changed_files",
)
_UI_REQUIRED_EMPTY_FIELDS = (
    "visible_source_binding_failures",
    "source_unsafe_claim_failures",
    "native_ui_failures",
    "native_ui_unsafe_failures",
    "blocking_reasons",
    "changed_files",
)
_UPSTREAM_REQUIRED_DIGEST_FIELDS = (
    "prompt_digest",
    "runtime_context_digest",
    "hook_event_digest",
    "hook_session_digest",
    "selected_api_route_id_sha256",
    "route_bound_request_sha256",
    "live_provider_response_digest",
    "controlled_provider_response_digest",
    "handoff_payload_digest",
    "codex_exec_transcript_sha256",
)
_UI_REQUIRED_DIGEST_FIELDS = (
    "handoff_payload_digest",
    "custom_response_expected_sha256",
    "expected_visible_text_sha256",
    "request_id_sha256",
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _file_sha256(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
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
        f"{prefix}_file_sha256": _file_sha256(path),
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _safe_reasons(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _sequence_nonempty(value: object) -> bool:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(list(value))
    return bool(value)


def _required_true_failures(
    packet: Mapping[str, Any],
    fields: Sequence[str],
    *,
    prefix: str,
) -> list[str]:
    return [f"{prefix}_{field}_not_true" for field in fields if packet.get(field) is not True]


def _required_false_failures(
    packet: Mapping[str, Any],
    fields: Sequence[str],
    *,
    prefix: str,
) -> list[str]:
    return [f"{prefix}_{field}_not_false" for field in fields if packet.get(field) is not False]


def _required_empty_failures(
    packet: Mapping[str, Any],
    fields: Sequence[str],
    *,
    prefix: str,
) -> list[str]:
    return [
        f"{prefix}_{field}_not_empty"
        for field in fields
        if _sequence_nonempty(packet.get(field))
    ]


def _required_digest_failures(
    packet: Mapping[str, Any],
    fields: Sequence[str],
    *,
    prefix: str,
) -> list[str]:
    return [
        f"{prefix}_{field}_missing"
        for field in fields
        if not _hex_sha256(packet.get(field))
    ]


def _upstream_failures(
    packet: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_e2e_working_flow_proof_file_read") is not True:
        failures.append("official_e2e_working_flow_proof_file_not_read")
    if metadata.get("official_e2e_working_flow_proof_file_valid_json") is not True:
        failures.append("official_e2e_working_flow_proof_file_json_not_valid")
    if metadata.get("official_e2e_working_flow_proof_file_mapping") is not True:
        failures.append("official_e2e_working_flow_proof_file_not_mapping")
    if packet.get("packet_kind") != OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND:
        failures.append("official_e2e_working_flow_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("official_e2e_working_flow_packet_not_ok")
    if packet.get("machine_error_code") != OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_OK:
        failures.append("official_e2e_working_flow_machine_error_not_ok")
    if packet.get("effect") != EFFECT_PROBE:
        failures.append("official_e2e_working_flow_effect_not_probe")
    failures.extend(
        _required_true_failures(
            packet,
            _UPSTREAM_REQUIRED_TRUE_FIELDS,
            prefix="official_e2e",
        )
    )
    failures.extend(
        _required_false_failures(
            packet,
            _UPSTREAM_REQUIRED_FALSE_FIELDS,
            prefix="official_e2e",
        )
    )
    failures.extend(
        _required_empty_failures(
            packet,
            _UPSTREAM_REQUIRED_EMPTY_FIELDS,
            prefix="official_e2e",
        )
    )
    failures.extend(
        _required_digest_failures(
            packet,
            _UPSTREAM_REQUIRED_DIGEST_FIELDS,
            prefix="official_e2e",
        )
    )
    if not (
        _hex_sha256(packet.get("hook_thread_digest"))
        or _hex_sha256(packet.get("hook_turn_digest"))
    ):
        failures.append("official_e2e_hook_thread_or_turn_digest_missing")
    return sorted(set(failures))


def _ui_failures(
    packet: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("custom_codex_ui_visibility_proof_file_read") is not True:
        failures.append("custom_codex_ui_visibility_proof_file_not_read")
    if metadata.get("custom_codex_ui_visibility_proof_file_valid_json") is not True:
        failures.append("custom_codex_ui_visibility_proof_file_json_not_valid")
    if metadata.get("custom_codex_ui_visibility_proof_file_mapping") is not True:
        failures.append("custom_codex_ui_visibility_proof_file_not_mapping")
    if packet.get("packet_kind") != CUSTOM_CODEX_UI_VISIBILITY_PACKET_KIND:
        failures.append("custom_codex_ui_visibility_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("custom_codex_ui_visibility_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("custom_codex_ui_visibility_machine_error_not_ok")
    if packet.get("effect") != EFFECT_PROBE:
        failures.append("custom_codex_ui_visibility_effect_not_probe")
    failures.extend(
        _required_true_failures(packet, _UI_REQUIRED_TRUE_FIELDS, prefix="ui_visibility")
    )
    failures.extend(
        _required_false_failures(packet, _UI_REQUIRED_FALSE_FIELDS, prefix="ui_visibility")
    )
    failures.extend(
        _required_empty_failures(
            packet,
            _UI_REQUIRED_EMPTY_FIELDS,
            prefix="ui_visibility",
        )
    )
    failures.extend(
        _required_digest_failures(packet, _UI_REQUIRED_DIGEST_FIELDS, prefix="ui_visibility")
    )
    exact_count = packet.get("custom_response_exact_token_candidate_count")
    if not isinstance(exact_count, int) or exact_count < 1:
        failures.append("ui_visibility_exact_token_candidate_count_missing")
    like_count = packet.get("custom_response_like_candidate_count")
    if not isinstance(like_count, int) or like_count < 1:
        failures.append("ui_visibility_like_candidate_count_missing")
    return sorted(set(failures))


def _unsafe_claim_failures(
    upstream: Mapping[str, Any],
    ui: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field in _UPSTREAM_REQUIRED_FALSE_FIELDS:
        if upstream.get(field) is True:
            failures.append(f"official_e2e_unsafe_{field}")
    for field in _UI_REQUIRED_FALSE_FIELDS:
        if ui.get(field) is True:
            failures.append(f"ui_visibility_unsafe_{field}")
    return sorted(set(failures))


def _binding_failures(
    upstream: Mapping[str, Any],
    ui: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    upstream_handoff = _hex_sha256(upstream.get("handoff_payload_digest"))
    ui_handoff = _hex_sha256(ui.get("handoff_payload_digest"))
    if not upstream_handoff:
        failures.append("official_e2e_handoff_payload_digest_missing")
    if not ui_handoff:
        failures.append("ui_visibility_handoff_payload_digest_missing")
    if upstream_handoff and ui_handoff and upstream_handoff != ui_handoff:
        failures.append("handoff_payload_digest_mismatch")
    if ui.get("visible_response_bound_to_handoff") is not True:
        failures.append("native_response_not_bound_to_handoff")
    if ui.get("visible_response_after_dispatch") is not True:
        failures.append("visible_response_not_after_dispatch")
    if upstream.get("codex_working_flow_delivery_proven") is not True:
        failures.append("official_e2e_working_flow_delivery_not_proven")
    if ui.get("working_flow_delivery_proven") is not True:
        failures.append("ui_visibility_working_flow_delivery_not_proven")
    return sorted(set(failures))


def _machine_error_code(
    *,
    upstream_failures: Sequence[str],
    ui_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    binding_failures: Sequence[str],
) -> str:
    if unsafe_failures:
        return FULL_RUNTIME_DISPATCH_UNSAFE_SOURCE
    if upstream_failures:
        return FULL_RUNTIME_DISPATCH_UPSTREAM_INVALID
    if ui_failures:
        return FULL_RUNTIME_DISPATCH_UI_INVALID
    if binding_failures:
        return FULL_RUNTIME_DISPATCH_NOT_BOUND
    return FULL_RUNTIME_DISPATCH_OK


def build_full_runtime_dispatch_proof_packet(
    *,
    official_e2e_working_flow_packet: Mapping[str, Any] | None,
    custom_codex_ui_visibility_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    upstream = _mapping(official_e2e_working_flow_packet)
    ui = _mapping(custom_codex_ui_visibility_packet)
    metadata = dict(file_metadata or {})
    upstream_failures = _upstream_failures(upstream, metadata)
    ui_failures = _ui_failures(ui, metadata)
    unsafe_failures = _unsafe_claim_failures(upstream, ui)
    binding_failures = _binding_failures(upstream, ui)
    blocking_reasons = sorted(
        set(
            upstream_failures
            + ui_failures
            + unsafe_failures
            + binding_failures
            + _safe_reasons(upstream.get("blocking_reasons"))
            + _safe_reasons(ui.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    handoff_digest = _hex_sha256(upstream.get("handoff_payload_digest"))
    prompt_digest = _hex_sha256(upstream.get("prompt_digest"))
    runtime_context_digest = _hex_sha256(upstream.get("runtime_context_digest"))
    selected_route_digest = _hex_sha256(upstream.get("selected_api_route_id_sha256"))
    live_response_digest = _hex_sha256(upstream.get("live_provider_response_digest"))
    controlled_response_digest = _hex_sha256(
        upstream.get("controlled_provider_response_digest")
    )
    transcript_digest = _hex_sha256(upstream.get("codex_exec_transcript_sha256"))
    machine_error_code = _machine_error_code(
        upstream_failures=upstream_failures,
        ui_failures=ui_failures,
        unsafe_failures=unsafe_failures,
        binding_failures=binding_failures,
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND,
        "proof_scope": "custom_codex_hook_alias_api_handoff_native_ui_visibility",
        "official_e2e_packet_kind": _safe_text(upstream.get("packet_kind"), limit=96),
        "official_e2e_status": _safe_text(upstream.get("status"), limit=32),
        "official_e2e_machine_error_code": _safe_text(
            upstream.get("machine_error_code"),
            limit=96,
        ),
        "custom_codex_ui_visibility_packet_kind": _safe_text(
            ui.get("packet_kind"),
            limit=96,
        ),
        "custom_codex_ui_visibility_status": _safe_text(ui.get("status"), limit=32),
        "custom_codex_ui_visibility_machine_error_code": _safe_text(
            ui.get("machine_error_code"),
            limit=96,
        ),
        "official_e2e_working_flow_valid": not upstream_failures,
        "custom_codex_ui_visibility_valid": not ui_failures,
        "full_runtime_binding_valid": not binding_failures,
        "unsafe_source_failures": unsafe_failures,
        "official_e2e_failures": upstream_failures,
        "custom_codex_ui_visibility_failures": ui_failures,
        "digest_binding_failures": binding_failures,
        "full_runtime_dispatch_proven": ok,
        "custom_codex_flow_proven": bool(
            ok and upstream.get("custom_codex_flow_origin_proven") is True
        ),
        "custom_codex_flow_origin_proven": bool(
            ok and upstream.get("custom_codex_flow_origin_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and upstream.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_ledger_written": bool(ok and upstream.get("hook_ledger_written") is True),
        "hook_prompt_digest_bound": bool(
            ok and upstream.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and upstream.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": bool(
            ok and upstream.get("thread_or_turn_digest_bound") is True
        ),
        "alias_resolved": bool(
            ok
            and upstream.get("alias_context_read") is True
            and upstream.get("route_id_allowed") is True
        ),
        "alias_context_read": bool(ok and upstream.get("alias_context_read") is True),
        "route_id_allowed": bool(ok and upstream.get("route_id_allowed") is True),
        "allowed_api_route_ids_enforced": bool(
            ok and upstream.get("allowed_api_route_ids_enforced") is True
        ),
        "api_lane_called": bool(ok and upstream.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and upstream.get("dispatch_proven") is True),
        "route_bound_dispatch_proven": bool(
            ok and upstream.get("route_bound_dispatch_proven") is True
        ),
        "provider_response_proven": bool(
            ok and upstream.get("provider_response_proven") is True
        ),
        "live_provider_response_proven": bool(
            ok and upstream.get("live_provider_response_proven") is True
        ),
        "external_live_provider_response_proven": bool(
            ok and upstream.get("external_live_provider_response_proven") is True
        ),
        "approved_handoff_ready": bool(
            ok and upstream.get("approved_handoff_ready") is True
        ),
        "approved_handoff_payload_sanitized": bool(
            ok and upstream.get("approved_handoff_payload_sanitized") is True
        ),
        "handoff_delivered": bool(ok and upstream.get("handoff_delivered") is True),
        "delivery_observed": bool(ok and upstream.get("delivery_observed") is True),
        "handoff_bound_to_dispatch": bool(
            ok and upstream.get("handoff_payload_bound_to_working_flow") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and upstream.get("codex_working_flow_delivery_proven") is True
        ),
        "native_response_bound_to_handoff": bool(
            ok and ui.get("visible_response_bound_to_handoff") is True
        ),
        "visible_response_observed": bool(
            ok and ui.get("visible_response_observed") is True
        ),
        "visible_response_after_dispatch": bool(
            ok and ui.get("visible_response_after_dispatch") is True
        ),
        "custom_codex_ui_visibility_proven": bool(
            ok and ui.get("custom_codex_ui_visibility_proven") is True
        ),
        "native_ui_observer_file_backed": bool(
            ok and ui.get("native_ui_observer_file_backed") is True
        ),
        "visible_source_binding_proven": bool(
            ok and ui.get("visible_source_binding_proven") is True
        ),
        "prompt_digest": prompt_digest if ok else "",
        "runtime_context_digest": runtime_context_digest if ok else "",
        "selected_api_route_id_sha256": selected_route_digest if ok else "",
        "live_provider_response_digest": live_response_digest if ok else "",
        "controlled_provider_response_digest": controlled_response_digest if ok else "",
        "handoff_payload_digest": handoff_digest if ok else "",
        "codex_exec_transcript_sha256": transcript_digest if ok else "",
        "custom_response_expected_sha256": (
            _hex_sha256(ui.get("custom_response_expected_sha256")) if ok else ""
        ),
        "custom_response_exact_token_candidate_count": int(
            ui.get("custom_response_exact_token_candidate_count") or 0
        )
        if ok
        else 0,
        "custom_response_like_candidate_count": int(
            ui.get("custom_response_like_candidate_count") or 0
        )
        if ok
        else 0,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "delivery_counts_as_custom_codex_ui": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
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
        "blocking_reasons": [] if ok else blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved the full Custom Codex alias/API dispatch chain to native UI visibility."
            if ok
            else "WBP blocked full runtime dispatch proof before a safe binding."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        extra=extra,
    )


def run_full_runtime_dispatch_proof_command(
    *,
    official_e2e_working_flow_proof_file: str,
    custom_codex_ui_visibility_proof_file: str,
    proof_dir: str | None = None,
) -> dict[str, Any]:
    upstream_path = Path(official_e2e_working_flow_proof_file).expanduser()
    ui_path = Path(custom_codex_ui_visibility_proof_file).expanduser()
    upstream_packet, upstream_metadata = _read_json_mapping_file(
        upstream_path,
        prefix="official_e2e_working_flow_proof",
    )
    ui_packet, ui_metadata = _read_json_mapping_file(
        ui_path,
        prefix="custom_codex_ui_visibility_proof",
    )
    packet = build_full_runtime_dispatch_proof_packet(
        official_e2e_working_flow_packet=upstream_packet,
        custom_codex_ui_visibility_packet=ui_packet,
        file_metadata={**upstream_metadata, **ui_metadata},
    )
    if proof_dir:
        proof_root = Path(proof_dir).expanduser()
        proof_root.mkdir(parents=True, exist_ok=True)
        packet = {**packet, "packet_file_written": True, "packet_file_path_recorded": False}
        write_json_atomic(proof_root / FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME, packet)
    return packet
