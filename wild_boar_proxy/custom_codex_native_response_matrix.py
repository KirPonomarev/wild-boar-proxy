# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .active_project_root import active_project_root_fields_from_mapping
from .custom_codex_native_ui_observer_proof import run_native_ui_observer_proof_command
from .native_window_probe import DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID
from .runtime import RuntimePaths, write_json_atomic
from .runtime_dispatch_mode_truth import (
    DISPATCH_MODE_CHATGPT_ONLY,
    EXECUTOR_CHATGPT,
    ORCHESTRATOR_CHATGPT,
    dispatch_mode_truth_fields,
)


NATIVE_RESPONSE_MATRIX_PACKET_FILE_NAME = "native-response-matrix.packet.json"
DEFAULT_NATIVE_RESPONSE_MATRIX_EXPECTED_PREFIX = "WBP_NATIVE_VISIBLE_RESPONSE"
DEFAULT_NATIVE_RESPONSE_MATRIX_REQUEST_PREFIX = "native-response"


@dataclass(frozen=True)
class NativeResponsePromptVariant:
    name: str
    template: str


def default_native_response_prompt_variants() -> list[NativeResponsePromptVariant]:
    return [
        NativeResponsePromptVariant(
            name="exact_one_line",
            template="Reply with exactly this single line and nothing else:\n{expected_text}",
        ),
        NativeResponsePromptVariant(
            name="repeat_exact",
            template=(
                "Return exactly the next line as plain text. Do not add quotes, "
                "markdown, commentary, or any other characters:\n{expected_text}"
            ),
        ),
        NativeResponsePromptVariant(
            name="plain_text_only",
            template=(
                "Reply with exactly this plain-text line and nothing else. "
                "No markdown, no quotes, no explanation:\n{expected_text}"
            ),
        ),
        NativeResponsePromptVariant(
            name="bare_marker",
            template="{expected_text}",
        ),
    ]


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "codex-runner" / "native-response-matrix" / stamp


def _safe_marker(value: str, *, default: str, limit: int = 96) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())[:limit]
    text = text.strip("_")
    return text or default


def _case_expected_text(*, expected_prefix: str, request_id: str) -> str:
    safe_prefix = _safe_marker(
        expected_prefix,
        default=DEFAULT_NATIVE_RESPONSE_MATRIX_EXPECTED_PREFIX,
        limit=160,
    )
    safe_request_id = _safe_marker(request_id, default="case", limit=96)
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]
    return f"{safe_prefix}_{safe_request_id}_{digest}"


def _case_summary(
    *,
    variant: NativeResponsePromptVariant,
    index: int,
    request_id: str,
    expected_text: str,
    prompt_text: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    return {
        "variant": variant.name,
        "case_index": index,
        "request_id": request_id,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "prompt_length": len(prompt_text),
        "prompt_text_recorded": False,
        "expected_text_sha256": hashlib.sha256(expected_text.encode("utf-8")).hexdigest(),
        "expected_text_recorded": False,
        "packet_file_written": packet.get("native_ui_observer_packet_file_written") is True,
        "packet_file_path_recorded": False,
        "native_ui_observer_packet_proven": (
            packet.get("native_ui_observer_packet_proven") is True
        ),
        "exit_code": int(packet.get("exit_code") or 0),
        "status": str(packet.get("status") or ""),
        "machine_error_code": str(packet.get("machine_error_code") or ""),
        "native_prompt_turn_accepted": packet.get("native_prompt_turn_accepted") is True,
        "assistant_turn_activity_observed": (
            packet.get("assistant_turn_activity_observed") is True
        ),
        "assistant_turn_completed_observed": (
            packet.get("assistant_turn_completed_observed") is True
        ),
        "assistant_turn_machine_error_code": str(
            packet.get("assistant_turn_machine_error_code") or ""
        ),
        "native_free_text_observer_machine_error_code": str(
            packet.get("native_free_text_observer_machine_error_code") or ""
        ),
        "custom_response_exact_token_observed": (
            packet.get("custom_response_exact_token_observed") is True
        ),
        "custom_response_bound_to_request": (
            packet.get("custom_response_bound_to_request") is True
        ),
        "custom_response_candidate_map_available": (
            packet.get("custom_response_candidate_map_available") is True
        ),
        "custom_response_candidate_map_candidate_count": int(
            packet.get("custom_response_candidate_map_candidate_count") or 0
        ),
        "custom_response_prompt_echo_candidate_count": int(
            packet.get("custom_response_prompt_echo_candidate_count") or 0
        ),
        "custom_response_prompt_suffix_echo_candidate_count": int(
            packet.get("custom_response_prompt_suffix_echo_candidate_count") or 0
        ),
        "custom_response_exact_token_candidate_count": int(
            packet.get("custom_response_exact_token_candidate_count") or 0
        ),
        "custom_response_like_candidate_count": int(
            packet.get("custom_response_like_candidate_count") or 0
        ),
        "response_surface_candidate_count": int(
            packet.get("response_surface_candidate_count") or 0
        ),
        "native_codex_subagent_used_as_dip": (
            packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "custom_codex_ui_visibility_proven": (
            packet.get("custom_codex_ui_visibility_proven") is True
        ),
        "product_ready": packet.get("product_ready") is True,
        "fallback_used": packet.get("fallback_used") is True,
        "local_imitation_used": packet.get("local_imitation_used") is True,
        "raw_dom_exposed": packet.get("raw_dom_exposed") is True,
        "raw_prompt_recorded": packet.get("raw_prompt_recorded") is True,
        "text_value_captured": packet.get("text_value_captured") is True,
    }


def _matrix_machine_code(case_summaries: Sequence[dict[str, Any]]) -> str:
    if case_summaries and all(
        case.get("native_ui_observer_packet_proven") is True
        for case in case_summaries
    ):
        return "OK"
    if any(
        case.get("assistant_turn_machine_error_code")
        == "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN"
        for case in case_summaries
    ):
        return "CUSTOM_NATIVE_RESPONSE_MATRIX_COMPLETED_WITHOUT_EXACT_TOKEN"
    if any(
        case.get("assistant_turn_machine_error_code")
        == "CUSTOM_NATIVE_ASSISTANT_TURN_PROMPT_ECHO_ONLY"
        for case in case_summaries
    ):
        return "CUSTOM_NATIVE_RESPONSE_MATRIX_PROMPT_ECHO_ONLY"
    return "CUSTOM_NATIVE_RESPONSE_MATRIX_NO_EXACT_RESPONSE_SURFACE"


def run_native_response_matrix_command(
    *,
    paths: RuntimePaths,
    proof_dir: str | None = None,
    matrix_id: str | None = None,
    request_prefix: str = DEFAULT_NATIVE_RESPONSE_MATRIX_REQUEST_PREFIX,
    expected_prefix: str = DEFAULT_NATIVE_RESPONSE_MATRIX_EXPECTED_PREFIX,
    persistent_profile_id: str = DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    persistent_profile_base_dir: str | None = None,
    observer_timeout_seconds: float | None = None,
    variants: Sequence[NativeResponsePromptVariant] | None = None,
    active_project_root: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    proof_root = _proof_root(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    matrix_id = _safe_marker(
        matrix_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        default="matrix",
        limit=64,
    )
    request_prefix = _safe_marker(
        request_prefix,
        default=DEFAULT_NATIVE_RESPONSE_MATRIX_REQUEST_PREFIX,
        limit=48,
    )
    selected_variants = list(variants or default_native_response_prompt_variants())

    case_summaries: list[dict[str, Any]] = []
    for index, variant in enumerate(selected_variants, start=1):
        request_id = _safe_marker(
            f"{request_prefix}-{matrix_id}-{index}-{variant.name}",
            default=f"{request_prefix}-{matrix_id}-{index}",
            limit=120,
        )
        expected_text = _case_expected_text(
            expected_prefix=expected_prefix,
            request_id=request_id,
        )
        prompt_text = variant.template.format(expected_text=expected_text)
        case_dir = proof_root / "cases" / variant.name
        packet = run_native_ui_observer_proof_command(
            paths=paths,
            prompt_text=prompt_text,
            request_id=request_id,
            expected_text=expected_text,
            proof_dir=str(case_dir),
            persistent_profile_id=persistent_profile_id,
            persistent_profile_base_dir=persistent_profile_base_dir,
            observer_timeout_seconds=observer_timeout_seconds,
        )
        case_summaries.append(
            _case_summary(
                variant=variant,
                index=index,
                request_id=request_id,
                expected_text=expected_text,
                prompt_text=prompt_text,
                packet=packet,
            )
        )

    positive_case_count = sum(
        1 for case in case_summaries if case["native_ui_observer_packet_proven"]
    )
    all_cases_proven = bool(
        case_summaries and positive_case_count == len(case_summaries)
    )
    machine_code = _matrix_machine_code(case_summaries)
    active_root_fields = active_project_root_fields_from_mapping(active_project_root)
    packet = {
        "schema_version": 1,
        "packet_kind": "custom_codex_native_response_matrix",
        "matrix_id": matrix_id,
        "status": "ok" if all_cases_proven else "error",
        "machine_error_code": machine_code,
        **dispatch_mode_truth_fields(
            execution_mode=DISPATCH_MODE_CHATGPT_ONLY,
            truth_source="custom_codex_native_response_matrix",
            orchestrator=ORCHESTRATOR_CHATGPT,
            executor=EXECUTOR_CHATGPT,
            mode_proven=all_cases_proven,
            chatgpt_lane_selected=True,
            api_route_selected=False,
            chatgpt_lane_called=all_cases_proven,
            api_route_called=False,
            **active_root_fields,
        ),
        "native_response_matrix_proven": all_cases_proven,
        "all_cases_proven": all_cases_proven,
        "positive_case_count": positive_case_count,
        "case_count": len(case_summaries),
        "cases": case_summaries,
        "prompt_text_recorded": False,
        "expected_text_recorded": False,
        "raw_prompt_recorded": False,
        "raw_dom_exposed": False,
        "text_value_captured": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "fallback_used": any(case["fallback_used"] for case in case_summaries),
        "local_imitation_used": any(
            case["local_imitation_used"] for case in case_summaries
        ),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "packet_file_written": True,
        "packet_file_path_recorded": False,
        "exit_code": 0 if all_cases_proven else 1,
    }
    write_json_atomic(proof_root / NATIVE_RESPONSE_MATRIX_PACKET_FILE_NAME, packet)
    return packet
