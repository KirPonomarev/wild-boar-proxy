# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256, _mapping
from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_codex_visible_source_binding_proof import (
    CUSTOM_CODEX_VISIBLE_SOURCE_BINDING_PACKET_KIND,
)
from .router_hook_entry import _safe_text


CUSTOM_CODEX_UI_VISIBILITY_PACKET_KIND = "wbp_custom_codex_ui_visibility_proof"

CUSTOM_CODEX_UI_VISIBILITY_OK = "OK"
CUSTOM_CODEX_UI_VISIBILITY_SOURCE_INVALID = (
    "WBP_CUSTOM_CODEX_UI_VISIBILITY_SOURCE_INVALID"
)
CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_SOURCE_NOT_ALLOWED = (
    "WBP_CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_SOURCE_NOT_ALLOWED"
)
CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED = (
    "WBP_CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED"
)
CUSTOM_CODEX_UI_VISIBILITY_NOT_BOUND = "WBP_CUSTOM_CODEX_UI_VISIBILITY_NOT_BOUND"
CUSTOM_CODEX_UI_VISIBILITY_PAYLOAD_UNSAFE = (
    "WBP_CUSTOM_CODEX_UI_VISIBILITY_PAYLOAD_UNSAFE"
)

NATIVE_UI_SOURCE_CUSTOM_CODEX_NATIVE_PROMPT_SUBMIT = "custom_codex_native_prompt_submit"
APPROVED_NATIVE_UI_VISIBILITY_SOURCE_KINDS = frozenset(
    {NATIVE_UI_SOURCE_CUSTOM_CODEX_NATIVE_PROMPT_SUBMIT}
)
APPROVED_NATIVE_UI_OBSERVER_SOURCES = frozenset({"bounded_cdp_response_token_scan"})
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


def _valid_request_id(value: object) -> bool:
    return isinstance(value, str) and bool(_REQUEST_ID_RE.fullmatch(value))


def _read_json_packet_file(path: Path, *, prefix: str) -> tuple[dict[str, Any], dict[str, Any]]:
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


def _sequence_not_empty(value: object) -> bool:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(list(value))
    return bool(value)


def _true_flag_failures(
    source: Mapping[str, Any],
    checks: Mapping[str, str],
) -> list[str]:
    return sorted({reason for field, reason in checks.items() if source.get(field) is True})


def _source_file_backed(metadata: Mapping[str, Any]) -> bool:
    return bool(
        metadata.get("visible_source_binding_proof_file_read") is True
        and metadata.get("visible_source_binding_proof_file_valid_json") is True
        and metadata.get("visible_source_binding_proof_file_mapping") is True
    )


def _native_file_backed(metadata: Mapping[str, Any]) -> bool:
    return bool(
        metadata.get("native_ui_observer_packet_file_read") is True
        and metadata.get("native_ui_observer_packet_file_valid_json") is True
        and metadata.get("native_ui_observer_packet_file_mapping") is True
    )


def _visible_source_failures(
    source: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    if metadata.get("visible_source_binding_proof_file_read") is not True:
        failures.append("visible_source_binding_proof_file_not_read")
    if metadata.get("visible_source_binding_proof_file_valid_json") is not True:
        failures.append("visible_source_binding_proof_file_json_not_valid")
    if metadata.get("visible_source_binding_proof_file_mapping") is not True:
        failures.append("visible_source_binding_proof_file_not_mapping")
    if source.get("packet_kind") != CUSTOM_CODEX_VISIBLE_SOURCE_BINDING_PACKET_KIND:
        failures.append("visible_source_binding_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("visible_source_binding_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("visible_source_binding_machine_error_code_not_ok")
    if source.get("effect") != EFFECT_PROBE:
        failures.append("visible_source_binding_effect_not_probe")
    if source.get("changed_files") not in ([], ()):
        failures.append("visible_source_binding_changed_files_not_empty")
    for field, reason in (
        ("visible_source_binding_proven", "visible_source_binding_not_proven"),
        (
            "custom_codex_visible_source_binding_proven",
            "custom_codex_visible_source_binding_not_proven",
        ),
        ("visible_source_observed", "visible_source_not_observed"),
        ("visible_source_bound_to_handoff", "visible_source_not_bound_to_handoff"),
        ("visible_source_after_delivery", "visible_source_not_after_delivery"),
        ("handoff_payload_digest_present", "handoff_payload_digest_not_present"),
        ("working_flow_delivery_proven", "working_flow_delivery_not_proven"),
        ("codex_working_flow_delivery_proven", "codex_working_flow_delivery_not_proven"),
        ("approved_delivery_surface_proven", "approved_delivery_surface_not_proven"),
        ("mcp_delivery_surface_proven", "mcp_delivery_surface_not_proven"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
        (
            "codex_exec_assistant_continuation_proven",
            "assistant_continuation_not_proven",
        ),
        (
            "assistant_response_bound_to_handoff_digest",
            "assistant_response_not_bound_to_handoff_digest",
        ),
        (
            "live_provider_response_digest_bound_to_handoff",
            "live_provider_response_not_bound_to_handoff",
        ),
        ("route_secret_screening_proven", "route_secret_screening_not_proven"),
        ("no_secret_exposed", "source_no_secret_exposed_not_proven"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    if not handoff_digest:
        failures.append("handoff_payload_digest_missing")
    marker_digest = _hex_sha256(source.get("visible_source_marker_digest"))
    if marker_digest and handoff_digest and marker_digest != handoff_digest:
        failures.append("visible_source_marker_digest_not_handoff_digest")
    if _sequence_not_empty(source.get("blocking_reasons")):
        failures.append("visible_source_binding_blocking_reasons_not_empty")
    if _sequence_not_empty(source.get("working_flow_delivery_failures")):
        failures.append("working_flow_delivery_failures_not_empty")
    if _sequence_not_empty(source.get("source_unsafe_claim_failures")):
        failures.append("source_unsafe_claim_failures_not_empty")
    if _sequence_not_empty(source.get("visible_source_event_unsafe_failures")):
        failures.append("visible_source_event_unsafe_failures_not_empty")

    unsafe_failures = _true_flag_failures(
        source,
        {
            "custom_codex_ui_visibility_proven": "source_preclaimed_ui_visibility",
            "delivery_counts_as_custom_codex_ui": "source_preclaimed_custom_codex_ui",
            "native_free_chat_router_proven": "source_preclaimed_native_router",
            "product_ready": "source_preclaimed_product_ready",
            "fallback_used": "source_fallback_used",
            "local_imitation_used": "source_local_imitation_used",
            "native_codex_subagent_used_as_dip": "source_native_subagent_used_as_dip",
            "codex_native_subagent_used_as_dip": "source_native_subagent_used_as_dip",
            "raw_prompt_recorded": "source_raw_prompt_recorded",
            "prompt_text_recorded": "source_prompt_text_recorded",
            "natural_phrase_recorded": "source_natural_phrase_recorded",
            "raw_jsonl_recorded": "source_raw_jsonl_recorded",
            "tool_call_arguments_recorded": "source_tool_call_arguments_recorded",
            "route_candidate_recorded": "source_route_candidate_recorded",
            "raw_route_id_recorded": "source_raw_route_id_recorded",
            "selected_api_route_id_recorded": "source_selected_api_route_id_recorded",
            "raw_provider_response_recorded": "source_raw_provider_response_recorded",
            "provider_response_text_recorded": "source_provider_response_text_recorded",
            "provider_response_preview_recorded": "source_provider_response_preview_recorded",
            "raw_backend_details_exposed": "source_raw_backend_details_exposed",
            "secret_value_exposed": "source_secret_value_exposed",
            "visible_source_secret_value_present": "source_secret_value_present",
            "visible_source_route_secret_value_present": "source_route_secret_value_present",
            "state_written": "source_state_written",
            "evidence_written": "source_evidence_written",
            "file_mutation_attempted": "source_file_mutation_attempted",
        },
    )
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures


def _native_ui_failures(
    native: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    expected_visible_text_sha256: str,
    request_id: str,
) -> tuple[list[str], list[str], bool]:
    failures: list[str] = []
    if metadata.get("native_ui_observer_packet_file_read") is not True:
        failures.append("native_ui_observer_packet_file_not_read")
    if metadata.get("native_ui_observer_packet_file_valid_json") is not True:
        failures.append("native_ui_observer_packet_file_json_not_valid")
    if metadata.get("native_ui_observer_packet_file_mapping") is not True:
        failures.append("native_ui_observer_packet_file_not_mapping")

    native_source_kind = _safe_text(native.get("packet_kind"), limit=80)
    source_allowed = native_source_kind in APPROVED_NATIVE_UI_VISIBILITY_SOURCE_KINDS
    if not source_allowed:
        failures.append("native_ui_source_kind_not_allowed")
    if native.get("status") != "ok":
        failures.append("native_ui_packet_not_ok")
    if native.get("machine_error_code") != "OK":
        failures.append("native_ui_machine_error_code_not_ok")
    if native.get("request_id") != request_id:
        failures.append("native_ui_request_id_not_bound")
    if native.get("native_free_text_observer_machine_error_code") != "OK":
        failures.append("native_ui_observer_machine_error_code_not_ok")
    if native.get("native_free_text_observer_source") not in APPROVED_NATIVE_UI_OBSERVER_SOURCES:
        failures.append("native_ui_observer_source_not_allowed")

    for field, reason in (
        ("cdp_port_owner_bound_to_custom_profile", "custom_codex_process_not_bound"),
        ("cdp_localhost_only", "cdp_not_localhost_only"),
        ("cdp_endpoint_redacted", "cdp_endpoint_not_redacted"),
        ("cdp_target_bound_to_custom_launch", "cdp_target_not_bound_to_custom_launch"),
        ("native_window_observed", "custom_codex_window_not_observed"),
        ("input_capable_ui_observed", "input_capable_ui_not_observed"),
        ("native_app_usable", "native_app_not_usable"),
        ("input_text_insert_attempted", "native_prompt_insert_not_attempted"),
        ("input_text_insert_succeeded", "native_prompt_insert_not_succeeded"),
        ("prompt_submitted", "native_prompt_not_submitted"),
        ("custom_response_observer_attempted", "custom_response_observer_not_attempted"),
        (
            "custom_response_observer_scan_performed",
            "custom_response_observer_scan_not_performed",
        ),
        (
            "custom_response_text_read_without_storing",
            "custom_response_text_read_without_storing_not_proven",
        ),
        (
            "custom_codex_response_text_read_proven",
            "custom_codex_response_text_not_read",
        ),
        ("custom_response_exact_token_observed", "custom_response_exact_token_not_observed"),
        ("custom_response_bound_to_request", "custom_response_not_bound_to_request"),
        (
            "native_codex_subagent_absence_proven",
            "native_codex_subagent_absence_not_proven",
        ),
    ):
        if native.get(field) is not True:
            failures.append(reason)
    if native.get("native_codex_subagent_used_as_dip") is not False:
        failures.append("native_codex_subagent_used_as_dip")

    native_expected_sha = _hex_sha256(native.get("custom_response_expected_sha256"))
    expected_sha_match = bool(
        native_expected_sha and native_expected_sha == expected_visible_text_sha256
    )
    if not expected_sha_match:
        failures.append("custom_response_expected_sha256_mismatch")
    for field, reason in (
        (
            "custom_response_exact_token_candidate_count",
            "custom_response_exact_token_candidate_missing",
        ),
        (
            "custom_response_like_candidate_count",
            "custom_response_like_candidate_missing",
        ),
    ):
        value = native.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            failures.append(reason)
    if _sequence_not_empty(native.get("blocking_reasons")):
        failures.append("native_ui_blocking_reasons_not_empty")

    unsafe_failures = _true_flag_failures(
        native,
        {
            "raw_dom_exposed": "native_raw_dom_exposed",
            "raw_ax_tree_exposed": "native_raw_ax_tree_exposed",
            "browser_cdp_authority_widened": "native_browser_cdp_authority_widened",
            "prompt_text_recorded": "native_prompt_text_recorded",
            "raw_prompt_recorded": "native_raw_prompt_recorded",
            "text_value_captured": "native_text_value_captured",
            "secret_value_exposed": "native_secret_value_exposed",
            "raw_backend_details_exposed": "native_raw_backend_details_exposed",
            "raw_provider_response_recorded": "native_raw_provider_response_recorded",
            "provider_response_text_recorded": "native_provider_response_text_recorded",
            "provider_response_preview_recorded": "native_provider_response_preview_recorded",
            "custom_codex_ui_visibility_proven": "native_preclaimed_ui_visibility",
            "delivery_counts_as_custom_codex_ui": "native_preclaimed_custom_codex_ui",
            "native_free_chat_router_proven": "native_preclaimed_native_router",
            "product_ready": "native_preclaimed_product_ready",
            "fallback_used": "native_fallback_used",
            "local_imitation_used": "native_local_imitation_used",
        },
    )
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures, source_allowed


def build_custom_codex_ui_visibility_proof_packet(
    visible_source_binding_packet: Mapping[str, Any] | None,
    native_ui_observer_packet: Mapping[str, Any] | None,
    *,
    expected_visible_text: str,
    request_id: str,
    file_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = _mapping(visible_source_binding_packet)
    native = _mapping(native_ui_observer_packet)
    metadata = dict(file_metadata or {})
    expected_text = str(expected_visible_text or "")
    expected_text_sha256 = hashlib.sha256(expected_text.encode("utf-8")).hexdigest() if expected_text else ""
    request_token = str(request_id or "")
    request_id_valid = _valid_request_id(request_token)
    handoff_digest = _hex_sha256(source.get("handoff_payload_digest"))
    native_expected_sha = _hex_sha256(native.get("custom_response_expected_sha256"))

    source_failures, source_unsafe_failures = _visible_source_failures(source, metadata)
    native_failures, native_unsafe_failures, native_source_allowed = _native_ui_failures(
        native,
        metadata,
        expected_visible_text_sha256=expected_text_sha256,
        request_id=request_token,
    )

    expected_text_present = bool(expected_text)
    expected_text_contains_handoff_digest = bool(
        expected_text_present and handoff_digest and handoff_digest in expected_text
    )
    expected_text_contains_request_id = bool(
        expected_text_present and request_token and request_token in expected_text
    )
    request_bound = native.get("custom_response_bound_to_request") is True
    expected_sha_match = bool(
        expected_text_sha256 and native_expected_sha == expected_text_sha256
    )

    binding_failures: list[str] = []
    if not expected_text_present:
        binding_failures.append("expected_visible_text_required")
    if not request_token:
        binding_failures.append("request_id_required")
    if request_token and not request_id_valid:
        binding_failures.append("request_id_invalid")
    if not expected_text_contains_handoff_digest:
        binding_failures.append("expected_visible_text_not_bound_to_handoff_digest")
    if not expected_text_contains_request_id:
        binding_failures.append("expected_visible_text_not_bound_to_request_id")
    if not expected_sha_match:
        binding_failures.append("native_expected_text_sha256_not_bound")
    if not request_bound:
        binding_failures.append("native_response_not_request_bound")

    unsafe_failures = sorted(set(source_unsafe_failures + native_unsafe_failures))
    blocking_reasons = sorted(set(source_failures + native_failures + binding_failures))

    visible_response_observed = bool(
        native.get("custom_codex_response_text_read_proven") is True
        and native.get("custom_response_exact_token_observed") is True
        and native.get("native_free_text_observer_machine_error_code") == "OK"
    )
    visible_response_bound_to_handoff = bool(
        visible_response_observed
        and expected_sha_match
        and expected_text_contains_handoff_digest
        and handoff_digest
    )
    stale_visibility_rejected = bool(
        visible_response_bound_to_handoff and expected_text_contains_request_id and request_bound
    )
    visible_response_after_dispatch = bool(
        source.get("visible_source_after_delivery") is True
        and source.get("handoff_delivered") is True
        and visible_response_bound_to_handoff
        and stale_visibility_rejected
    )
    custom_codex_ui_visibility_proven = bool(
        not blocking_reasons
        and _source_file_backed(metadata)
        and _native_file_backed(metadata)
        and native_source_allowed
        and visible_response_bound_to_handoff
        and visible_response_after_dispatch
    )

    if custom_codex_ui_visibility_proven:
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_OK
    elif unsafe_failures:
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_PAYLOAD_UNSAFE
    elif source_failures:
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_SOURCE_INVALID
    elif not _native_file_backed(metadata):
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED
    elif not native_source_allowed:
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_SOURCE_NOT_ALLOWED
    elif native_failures:
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED
    else:
        machine_error_code = CUSTOM_CODEX_UI_VISIBILITY_NOT_BOUND

    effective_secret_values = [
        str(secret)
        for secret in [expected_text, *(secret_values or [])]
        if str(secret)
    ]
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_UI_VISIBILITY_PACKET_KIND,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=80),
        "source_packet_status": _safe_text(source.get("status"), limit=32),
        "source_machine_error_code": _safe_text(source.get("machine_error_code"), limit=96),
        "source_packet_file_backed": _source_file_backed(metadata),
        "visible_source_binding_valid": not source_failures,
        "visible_source_binding_failures": source_failures,
        "source_unsafe_claim_failures": source_unsafe_failures,
        "visible_source_binding_proven": source.get("visible_source_binding_proven") is True,
        "custom_codex_visible_source_binding_proven": (
            source.get("custom_codex_visible_source_binding_proven") is True
        ),
        "visible_source_bound_to_handoff": source.get("visible_source_bound_to_handoff") is True,
        "visible_source_after_delivery": source.get("visible_source_after_delivery") is True,
        "working_flow_delivery_proven": source.get("working_flow_delivery_proven") is True,
        "codex_working_flow_delivery_proven": (
            source.get("codex_working_flow_delivery_proven") is True
        ),
        "handoff_payload_digest": handoff_digest,
        "handoff_payload_digest_present": bool(handoff_digest),
        "native_ui_source_packet_kind": _safe_text(native.get("packet_kind"), limit=80),
        "native_ui_source_allowed": native_source_allowed,
        "native_ui_observer_file_backed": _native_file_backed(metadata),
        "native_ui_packet_status": _safe_text(native.get("status"), limit=32),
        "native_ui_machine_error_code": _safe_text(native.get("machine_error_code"), limit=96),
        "native_ui_observer_machine_error_code": _safe_text(
            native.get("native_free_text_observer_machine_error_code"),
            limit=96,
        ),
        "native_ui_failures": native_failures,
        "native_ui_unsafe_failures": native_unsafe_failures,
        "custom_codex_process_bound": (
            native.get("cdp_port_owner_bound_to_custom_profile") is True
        ),
        "custom_codex_window_observed": native.get("native_window_observed") is True,
        "custom_codex_profile_bound": (
            native.get("cdp_port_owner_bound_to_custom_profile") is True
            and native.get("cdp_target_bound_to_custom_launch") is True
        ),
        "custom_codex_native_app_usable": native.get("native_app_usable") is True,
        "input_capable_ui_observed": native.get("input_capable_ui_observed") is True,
        "native_prompt_submitted": native.get("prompt_submitted") is True,
        "native_ui_observer_source": _safe_text(
            native.get("native_free_text_observer_source"),
            limit=96,
        ),
        "visible_response_observed": visible_response_observed,
        "visible_response_bound_to_handoff": visible_response_bound_to_handoff,
        "visible_response_after_dispatch": visible_response_after_dispatch,
        "visible_response_request_bound": request_bound,
        "stale_visibility_rejected": stale_visibility_rejected,
        "custom_response_exact_token_observed": (
            native.get("custom_response_exact_token_observed") is True
        ),
        "custom_response_text_read_without_storing": (
            native.get("custom_response_text_read_without_storing") is True
        ),
        "custom_response_expected_sha256": native_expected_sha,
        "expected_visible_text_sha256": expected_text_sha256,
        "expected_visible_text_recorded": False,
        "expected_visible_text_contains_handoff_digest": (
            expected_text_contains_handoff_digest
        ),
        "expected_visible_text_contains_request_id": expected_text_contains_request_id,
        "request_id": request_token if request_id_valid else "",
        "request_id_sha256": hashlib.sha256(request_token.encode("utf-8")).hexdigest()
        if request_token
        else "",
        "request_id_valid": request_id_valid,
        "request_id_recorded": bool(request_token and request_id_valid),
        "native_request_id_bound": native.get("request_id") == request_token,
        "custom_response_exact_token_candidate_count": int(
            native.get("custom_response_exact_token_candidate_count") or 0
        ),
        "custom_response_like_candidate_count": int(
            native.get("custom_response_like_candidate_count") or 0
        ),
        "custom_response_token_leaf_candidate_count": int(
            native.get("custom_response_token_leaf_candidate_count") or 0
        ),
        "custom_response_prompt_echo_candidate_count": int(
            native.get("custom_response_prompt_echo_candidate_count") or 0
        ),
        "custom_response_prompt_suffix_echo_candidate_count": int(
            native.get("custom_response_prompt_suffix_echo_candidate_count") or 0
        ),
        "native_codex_subagent_absence_proven": (
            native.get("native_codex_subagent_absence_proven") is True
        ),
        "native_codex_subagent_used_as_dip": (
            native.get("native_codex_subagent_used_as_dip") is True
        ),
        "custom_codex_ui_visibility_proven": custom_codex_ui_visibility_proven,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
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
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=custom_codex_ui_visibility_proven,
        human_message=(
            "WBP proved the handoff-bound response is visible in the real Custom Codex UI."
            if custom_codex_ui_visibility_proven
            else "WBP blocked Custom Codex UI visibility proof before a safe binding."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if custom_codex_ui_visibility_proven else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=effective_secret_values,
        extra=extra,
    )


def run_custom_codex_ui_visibility_proof_command(
    *,
    visible_source_binding_proof_file: str,
    native_ui_observer_packet_file: str,
    expected_visible_text: str,
    request_id: str,
) -> dict[str, Any]:
    source_path = Path(visible_source_binding_proof_file).expanduser()
    native_path = Path(native_ui_observer_packet_file).expanduser()
    source_packet, source_metadata = _read_json_packet_file(
        source_path,
        prefix="visible_source_binding_proof",
    )
    native_packet, native_metadata = _read_json_packet_file(
        native_path,
        prefix="native_ui_observer_packet",
    )
    return build_custom_codex_ui_visibility_proof_packet(
        source_packet,
        native_packet,
        expected_visible_text=expected_visible_text,
        request_id=request_id,
        file_metadata={**source_metadata, **native_metadata},
    )
