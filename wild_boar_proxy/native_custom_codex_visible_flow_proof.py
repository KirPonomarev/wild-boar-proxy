# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .codex_working_flow_delivery_proof import CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND
from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_codex_ui_visibility_proof import _native_ui_failures
from .router_hook_entry import _safe_text


NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PACKET_KIND = (
    "wbp_native_custom_codex_visible_flow_proof"
)
NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PACKET_FILE_NAME = (
    "native-custom-codex-visible-flow-proof.packet.json"
)

NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_OK = "OK"
NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_WORKING_FLOW_INVALID = (
    "WBP_NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_WORKING_FLOW_INVALID"
)
NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NATIVE_UI_NOT_PROVEN = (
    "WBP_NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NATIVE_UI_NOT_PROVEN"
)
NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NOT_BOUND = (
    "WBP_NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NOT_BOUND"
)
NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PAYLOAD_UNSAFE = (
    "WBP_NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PAYLOAD_UNSAFE"
)

_HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


def _hex64(value: object) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip().lower()
    return candidate if _HEX64_RE.fullmatch(candidate) else ""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _file_backed(metadata: Mapping[str, Any], *, prefix: str) -> bool:
    return bool(
        metadata.get(f"{prefix}_file_read") is True
        and metadata.get(f"{prefix}_file_valid_json") is True
        and metadata.get(f"{prefix}_file_mapping") is True
    )


def _true_flag_failures(source: Mapping[str, Any], checks: Mapping[str, str]) -> list[str]:
    return sorted({reason for field, reason in checks.items() if source.get(field) is True})


def _working_flow_failures(
    working: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str], bool]:
    failures: list[str] = []
    if metadata.get("working_flow_delivery_proof_file_read") is not True:
        failures.append("working_flow_delivery_proof_file_not_read")
    if metadata.get("working_flow_delivery_proof_file_valid_json") is not True:
        failures.append("working_flow_delivery_proof_file_json_not_valid")
    if metadata.get("working_flow_delivery_proof_file_mapping") is not True:
        failures.append("working_flow_delivery_proof_file_not_mapping")
    if working.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_packet_kind_invalid")
    if working.get("status") != "ok":
        failures.append("working_flow_packet_not_ok")
    if working.get("machine_error_code") != "OK":
        failures.append("working_flow_machine_error_code_not_ok")
    if working.get("effect") != EFFECT_PROBE:
        failures.append("working_flow_effect_not_probe")
    if working.get("changed_files") not in ([], ()):
        failures.append("working_flow_changed_files_not_empty")

    for field, reason in (
        ("codex_working_flow_delivery_proven", "codex_working_flow_delivery_not_proven"),
        ("approved_delivery_surface_proven", "approved_delivery_surface_not_proven"),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_not_sanitized"),
        ("handoff_delivered", "handoff_not_delivered"),
        ("delivery_observed", "delivery_not_observed"),
        ("live_provider_response_digest_bound_to_handoff", "provider_digest_not_bound"),
        (
            "codex_exec_assistant_continuation_proven",
            "codex_exec_assistant_continuation_not_proven",
        ),
    ):
        if working.get(field) is not True:
            failures.append(reason)

    surface_accepted = bool(
        working.get("mcp_delivery_surface_proven") is True
        or working.get("command_execution_delivery_surface_proven") is True
    )
    if not surface_accepted:
        failures.append("working_flow_delivery_surface_not_accepted")
    if not _hex64(working.get("handoff_payload_digest")):
        failures.append("handoff_payload_digest_invalid")

    unsafe_failures = _true_flag_failures(
        working,
        {
            "custom_codex_ui_visibility_proven": "working_flow_preclaimed_ui_visibility",
            "delivery_counts_as_custom_codex_ui": "working_flow_preclaimed_custom_codex_ui",
            "native_free_chat_router_proven": "working_flow_preclaimed_native_router",
            "product_ready": "working_flow_preclaimed_product_ready",
            "fallback_used": "working_flow_fallback_used",
            "local_imitation_used": "working_flow_local_imitation_used",
            "native_codex_subagent_used_as_dip": "working_flow_native_subagent_used_as_dip",
            "codex_native_subagent_used_as_dip": "working_flow_codex_native_subagent_used_as_dip",
            "raw_prompt_recorded": "working_flow_raw_prompt_recorded",
            "prompt_text_recorded": "working_flow_prompt_text_recorded",
            "natural_phrase_recorded": "working_flow_natural_phrase_recorded",
            "raw_jsonl_recorded": "working_flow_raw_jsonl_recorded",
            "tool_call_arguments_recorded": "working_flow_tool_call_arguments_recorded",
            "raw_route_id_recorded": "working_flow_raw_route_id_recorded",
            "selected_api_route_id_recorded": "working_flow_selected_route_recorded",
            "raw_provider_response_recorded": "working_flow_raw_provider_response_recorded",
            "provider_response_text_recorded": "working_flow_provider_response_text_recorded",
            "provider_response_preview_recorded": "working_flow_provider_response_preview_recorded",
            "raw_backend_details_exposed": "working_flow_raw_backend_details_exposed",
            "secret_value_exposed": "working_flow_secret_value_exposed",
        },
    )
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures, surface_accepted


def _machine_error_code(
    *,
    working_flow_failures: list[str],
    native_ui_failures: list[str],
    binding_failures: list[str],
    unsafe_failures: list[str],
) -> str:
    if unsafe_failures:
        return NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PAYLOAD_UNSAFE
    if working_flow_failures:
        return NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_WORKING_FLOW_INVALID
    if native_ui_failures:
        return NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NATIVE_UI_NOT_PROVEN
    if binding_failures:
        return NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NOT_BOUND
    return NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_OK


def build_native_custom_codex_visible_flow_proof_packet(
    working_flow_delivery_packet: Mapping[str, Any] | None,
    native_ui_observer_packet: Mapping[str, Any] | None,
    *,
    expected_visible_text: str,
    request_id: str,
    file_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    working = dict(working_flow_delivery_packet or {})
    native = dict(native_ui_observer_packet or {})
    metadata = dict(file_metadata or {})
    expected_sha256 = _sha256_text(expected_visible_text)
    handoff_digest = _hex64(working.get("handoff_payload_digest"))
    request_id_valid = bool(isinstance(request_id, str) and _REQUEST_ID_RE.fullmatch(request_id))
    expected_text_bound = bool(
        handoff_digest and request_id_valid and handoff_digest in expected_visible_text and request_id in expected_visible_text
    )

    working_failures, working_unsafe, surface_accepted = _working_flow_failures(
        working,
        metadata,
    )
    native_failures, native_unsafe, native_source_allowed = _native_ui_failures(
        native,
        metadata,
        expected_visible_text_sha256=expected_sha256,
        request_id=request_id,
    )
    binding_failures: list[str] = []
    if not request_id_valid:
        binding_failures.append("request_id_invalid")
    if not expected_text_bound:
        binding_failures.append("expected_visible_text_not_bound_to_handoff")
    if native.get("custom_response_expected_sha256") != expected_sha256:
        binding_failures.append("native_expected_text_sha256_not_bound")

    unsafe_failures = sorted(set(working_unsafe + native_unsafe))
    machine_error = _machine_error_code(
        working_flow_failures=working_failures,
        native_ui_failures=native_failures,
        binding_failures=binding_failures,
        unsafe_failures=unsafe_failures,
    )
    ok = machine_error == NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_OK
    blocking_reasons = sorted(
        set(working_failures + native_failures + binding_failures + unsafe_failures)
    )
    extra = {
        "schema_version": 1,
        "packet_kind": NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PACKET_KIND,
        "proof_scope": "native_custom_codex_visible_flow_after_core_handoff",
        "native_custom_codex_visible_flow_proven": ok,
        "custom_codex_ui_visibility_proven": ok,
        "visible_response_observed": ok,
        "visible_response_bound_to_handoff": bool(ok and expected_text_bound),
        "visible_response_after_dispatch": ok,
        "working_flow_delivery_file_backed": _file_backed(
            metadata,
            prefix="working_flow_delivery_proof",
        ),
        "native_ui_observer_file_backed": _file_backed(
            metadata,
            prefix="native_ui_observer_packet",
        ),
        "working_flow_packet_kind": _safe_text(working.get("packet_kind"), limit=96),
        "working_flow_status": _safe_text(working.get("status"), limit=32),
        "working_flow_machine_error_code": _safe_text(
            working.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_delivery_surface_kind": _safe_text(
            working.get("working_flow_delivery_surface_kind"),
            limit=96,
        ),
        "working_flow_delivery_surface_accepted": surface_accepted,
        "mcp_delivery_surface_accepted": working.get("mcp_delivery_surface_proven") is True,
        "command_execution_delivery_surface_accepted": (
            working.get("command_execution_delivery_surface_proven") is True
        ),
        "codex_working_flow_delivery_proven": (
            working.get("codex_working_flow_delivery_proven") is True
        ),
        "approved_delivery_surface_proven": (
            working.get("approved_delivery_surface_proven") is True
        ),
        "handoff_payload_digest": handoff_digest,
        "handoff_payload_digest_present": bool(handoff_digest),
        "native_ui_source_packet_kind": _safe_text(native.get("packet_kind"), limit=96),
        "native_ui_source_allowed": native_source_allowed,
        "native_ui_packet_status": _safe_text(native.get("status"), limit=32),
        "native_ui_machine_error_code": _safe_text(
            native.get("machine_error_code"),
            limit=96,
        ),
        "native_ui_request_id_bound": native.get("request_id") == request_id,
        "request_id_sha256": _sha256_text(request_id),
        "request_id_recorded": False,
        "expected_visible_text_sha256": expected_sha256,
        "expected_visible_text_recorded": False,
        "expected_visible_text_bound_to_handoff": expected_text_bound,
        "native_expected_text_sha256_bound": (
            native.get("custom_response_expected_sha256") == expected_sha256
        ),
        "custom_codex_process_bound": (
            native.get("cdp_port_owner_bound_to_custom_profile") is True
        ),
        "custom_codex_window_observed": native.get("native_window_observed") is True,
        "input_capable_ui_observed": native.get("input_capable_ui_observed") is True,
        "visible_native_response_exact_token_observed": (
            native.get("custom_response_exact_token_observed") is True
        ),
        "native_response_bound_to_request": (
            native.get("custom_response_bound_to_request") is True
        ),
        "working_flow_failures": working_failures,
        "native_ui_failures": native_failures,
        "binding_failures": binding_failures,
        "unsafe_failures": unsafe_failures,
        "blocking_reasons": blocking_reasons,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "Native Custom Codex visible flow proof is bound to the core handoff."
            if ok
            else "Native Custom Codex visible flow proof is not proven."
        ),
        machine_error_code=machine_error,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        extra=extra,
        secret_values=[expected_visible_text],
    )


def run_native_custom_codex_visible_flow_proof_command(
    *,
    working_flow_delivery_proof_file: str,
    native_ui_observer_packet_file: str,
    expected_visible_text: str,
    request_id: str,
) -> dict[str, Any]:
    working_path = Path(working_flow_delivery_proof_file).expanduser()
    native_path = Path(native_ui_observer_packet_file).expanduser()
    working, working_metadata = _read_json_packet_file(
        working_path,
        prefix="working_flow_delivery_proof",
    )
    native, native_metadata = _read_json_packet_file(
        native_path,
        prefix="native_ui_observer_packet",
    )
    return build_native_custom_codex_visible_flow_proof_packet(
        working,
        native,
        expected_visible_text=expected_visible_text,
        request_id=request_id,
        file_metadata={**working_metadata, **native_metadata},
    )
