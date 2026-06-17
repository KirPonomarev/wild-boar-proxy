# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE
from .core import packets
from .real_custom_codex_hook_proof import (
    REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
    run_real_custom_codex_hook_proof_command,
)
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths, write_json_atomic


NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_PACKET_KIND = (
    "wbp_native_free_chat_router_dispatch_admission"
)
NATIVE_FREE_CHAT_ROUTER_DISPATCH_HANDOFF_PACKET_KIND = (
    "wbp_native_free_chat_router_dispatch_handoff"
)

DISPATCH_ADMISSION_OK = "OK"
DISPATCH_ADMISSION_SOURCE_INVALID = (
    "WBP_NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_SOURCE_INVALID"
)
DISPATCH_ADMISSION_SOURCE_UNSAFE = (
    "WBP_NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_SOURCE_UNSAFE"
)
DISPATCH_ADMISSION_HANDOFF_UNSAFE = (
    "WBP_NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_HANDOFF_UNSAFE"
)
DISPATCH_ADMISSION_HANDOFF_WRITE_FAILED = (
    "WBP_NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_HANDOFF_WRITE_FAILED"
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(
            dict(value),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _default_handoff_file(paths: RuntimePaths) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        paths.managed_dir
        / "router-hook"
        / "native-free-chat-router-dispatch-admission"
        / stamp
        / "dispatch-handoff.json"
    )


def _path_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _runtime_secret_values(runtime_context: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    allowed = runtime_context.get("allowed_api_route_ids")
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        values.extend(route for route in allowed if isinstance(route, str) and route)
    routes = runtime_context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        values.extend(route for route in routes.values() if isinstance(route, str) and route)
    return sorted(set(values))


def _source_required_failures(source: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if source.get("packet_kind") != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND:
        failures.append("source_packet_kind_invalid")
    if source.get("status") != "ok":
        failures.append("source_packet_not_ok")
    if source.get("machine_error_code") != "OK":
        failures.append("source_machine_error_not_ok")
    for field, reason in (
        ("hook_producer_ledger_proven", "hook_producer_ledger_not_proven"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_api_route_ids_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("api_response_received", "api_response_not_received"),
        ("response_bound_to_proof", "response_not_bound_to_proof"),
        ("dispatch_proven", "dispatch_not_proven"),
        ("route_bound_dispatch_proven", "route_bound_dispatch_not_proven"),
        ("provider_response_proven", "provider_response_not_proven"),
        (
            "controlled_provider_response_proven",
            "controlled_provider_response_not_proven",
        ),
        ("approved_handoff_ready", "approved_handoff_not_ready"),
        ("approved_handoff_payload_sanitized", "approved_handoff_payload_not_sanitized"),
        ("handoff_delivered", "source_handoff_not_delivered"),
        ("delivery_observed", "source_delivery_not_observed"),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    if source.get("dispatch_status") != "proven":
        failures.append("dispatch_status_not_proven")
    for field, reason in (
        ("prompt_digest", "prompt_digest_missing"),
        ("runtime_context_digest", "runtime_context_digest_missing"),
        ("hook_event_digest", "hook_event_digest_missing"),
        ("route_bound_request_sha256", "route_bound_request_digest_missing"),
        ("provider_response_digest", "provider_response_digest_missing"),
        (
            "controlled_provider_response_sha256",
            "controlled_provider_response_digest_missing",
        ),
        ("selected_api_route_id_sha256", "selected_api_route_digest_missing"),
        ("machine_response_envelope_sha256", "machine_response_envelope_digest_missing"),
        ("handoff_payload_digest", "handoff_payload_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    if not _safe_text(source.get("selected_alias"), limit=80):
        failures.append("selected_alias_missing")
    if not _safe_text(source.get("selected_slot"), limit=64):
        failures.append("selected_slot_missing")
    return sorted(set(failures))


def _source_false_claim_failures(source: Mapping[str, Any]) -> list[str]:
    checks = {
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
        "custom_codex_ui_visibility_proven": (
            "custom_codex_ui_visibility_must_not_be_claimed"
        ),
        "codex_working_flow_delivery_proven": (
            "codex_working_flow_delivery_must_not_be_claimed"
        ),
        "delivery_counts_as_custom_codex_ui": (
            "delivery_counts_as_custom_codex_ui_must_not_be_claimed"
        ),
        "native_free_chat_router_proven": (
            "native_free_chat_router_must_not_be_claimed"
        ),
        "product_ready": "product_ready_must_not_be_claimed",
    }
    return sorted(
        {reason for field, reason in checks.items() if source.get(field) is True}
    )


def _dispatch_result_digest(source: Mapping[str, Any]) -> str:
    return _canonical_digest(
        {
            "prompt_digest": _hex_sha256(source.get("prompt_digest")),
            "runtime_context_digest": _hex_sha256(
                source.get("runtime_context_digest")
            ),
            "route_bound_request_sha256": _hex_sha256(
                source.get("route_bound_request_sha256")
            ),
            "provider_response_digest": _hex_sha256(
                source.get("provider_response_digest")
            ),
            "controlled_provider_response_sha256": _hex_sha256(
                source.get("controlled_provider_response_sha256")
            ),
            "selected_api_route_id_sha256": _hex_sha256(
                source.get("selected_api_route_id_sha256")
            ),
            "selected_alias": _safe_text(source.get("selected_alias"), limit=80),
            "selected_slot": _safe_text(source.get("selected_slot"), limit=64),
        }
    )


def _handoff_evidence_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    dispatch_result_digest = _dispatch_result_digest(source)
    payload = {
        "schema_version": 1,
        "packet_kind": NATIVE_FREE_CHAT_ROUTER_DISPATCH_HANDOFF_PACKET_KIND,
        "source_packet_kind": _safe_text(source.get("packet_kind"), limit=80),
        "source_packet_status": _safe_text(source.get("status"), limit=32),
        "prompt_digest": _hex_sha256(source.get("prompt_digest")),
        "runtime_context_digest": _hex_sha256(source.get("runtime_context_digest")),
        "hook_event_digest": _hex_sha256(source.get("hook_event_digest")),
        "hook_thread_digest": _hex_sha256(source.get("hook_thread_digest")),
        "hook_turn_digest": _hex_sha256(source.get("hook_turn_digest")),
        "hook_prompt_digest_bound": source.get("hook_prompt_digest_bound") is True,
        "hook_runtime_context_digest_bound": (
            source.get("hook_runtime_context_digest_bound") is True
        ),
        "alias_context_read": source.get("alias_context_read") is True,
        "allowed_api_route_ids_enforced": (
            source.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": source.get("route_id_allowed") is True,
        "selected_alias": _safe_text(source.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            source.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(source.get("selected_slot"), limit=64),
        "selected_api_route_id_present": (
            source.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            source.get("selected_api_route_id_sha256")
        ),
        "api_lane_called": source.get("api_lane_called") is True,
        "dispatch_status": _safe_text(source.get("dispatch_status"), limit=32),
        "dispatch_proven": source.get("dispatch_proven") is True,
        "dispatch_result_digest": dispatch_result_digest,
        "dispatch_result_digest_bound": bool(dispatch_result_digest),
        "api_response_received": source.get("api_response_received") is True,
        "response_bound_to_proof": source.get("response_bound_to_proof") is True,
        "route_bound_dispatch_proven": (
            source.get("route_bound_dispatch_proven") is True
        ),
        "route_bound_request_sha256": _hex_sha256(
            source.get("route_bound_request_sha256")
        ),
        "provider_response_digest": _hex_sha256(source.get("provider_response_digest")),
        "controlled_provider_response_sha256": _hex_sha256(
            source.get("controlled_provider_response_sha256")
        ),
        "handoff_payload_digest": _hex_sha256(source.get("handoff_payload_digest")),
        "machine_response_envelope_sha256": _hex_sha256(
            source.get("machine_response_envelope_sha256")
        ),
        "custom_codex_ui_visibility_proven": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "delivery_counts_as_custom_codex_ui_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
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
    }
    payload["handoff_evidence_digest"] = _canonical_digest(payload)
    return payload


def _admission_handoff_secret_leak(
    payload: Mapping[str, Any],
    *,
    secret_values: Sequence[str],
) -> bool:
    return packets.command_packet_has_secret_leak(
        dict(payload),
        secret_values=list(secret_values),
    )


def build_native_free_chat_router_dispatch_admission_packet(
    *,
    source_packet: Mapping[str, Any],
    handoff_file: Path,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    secret_list = list(secret_values or [])
    source_required_failures = _source_required_failures(source_packet)
    source_false_claim_failures = _source_false_claim_failures(source_packet)
    source_unsafe = packets.command_packet_has_secret_leak(
        dict(source_packet),
        secret_values=secret_list,
    )
    blocking_reasons: list[str] = []
    blocking_reasons.extend(source_required_failures)
    blocking_reasons.extend(source_false_claim_failures)
    if source_unsafe:
        blocking_reasons.append("source_packet_secret_leak")

    handoff_payload: dict[str, Any] = {}
    handoff_unsafe = False
    handoff_written = False
    write_error_code = ""
    handoff_file_sha256 = ""
    changed_files: list[str] = []
    if not blocking_reasons:
        handoff_payload = _handoff_evidence_payload(source_packet)
        handoff_unsafe = _admission_handoff_secret_leak(
            handoff_payload,
            secret_values=secret_list,
        )
        if handoff_unsafe:
            blocking_reasons.append("handoff_payload_secret_leak")
        else:
            try:
                write_json_atomic(handoff_file, handoff_payload)
            except OSError:
                write_error_code = "handoff_write_os_error"
                blocking_reasons.append(write_error_code)
            else:
                handoff_written = True
                handoff_file_sha256 = _path_sha256(handoff_file)
                changed_files = [str(handoff_file)]

    blocking_reasons = sorted(set(blocking_reasons))
    ok = not blocking_reasons and handoff_written
    if ok:
        machine_error_code = DISPATCH_ADMISSION_OK
    elif source_unsafe or source_false_claim_failures:
        machine_error_code = DISPATCH_ADMISSION_SOURCE_UNSAFE
    elif handoff_unsafe:
        machine_error_code = DISPATCH_ADMISSION_HANDOFF_UNSAFE
    elif write_error_code:
        machine_error_code = DISPATCH_ADMISSION_HANDOFF_WRITE_FAILED
    else:
        machine_error_code = DISPATCH_ADMISSION_SOURCE_INVALID

    extra = {
        "schema_version": 1,
        "packet_kind": NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_PACKET_KIND,
        "source_packet_kind": _safe_text(source_packet.get("packet_kind"), limit=80),
        "source_packet_status": _safe_text(source_packet.get("status"), limit=32),
        "source_packet_machine_error_code": _safe_text(
            source_packet.get("machine_error_code"),
            limit=96,
        ),
        "source_packet_digest": _canonical_digest(dict(source_packet)),
        "source_required_failures": source_required_failures,
        "source_false_claim_failures": source_false_claim_failures,
        "source_packet_secret_leak": source_unsafe,
        "native_free_chat_router_dispatch_admission_proven": ok,
        "dispatch_admission_scope": "user_prompt_submit_hook_to_wbp_api_lane_handoff_file",
        "user_prompt_submit_hook_ran": (
            source_packet.get("user_prompt_submit_hook_ran") is True and ok
        ),
        "hook_producer_ledger_proven": (
            source_packet.get("hook_producer_ledger_proven") is True and ok
        ),
        "hook_prompt_digest_bound": (
            source_packet.get("hook_prompt_digest_bound") is True and ok
        ),
        "hook_runtime_context_digest_bound": (
            source_packet.get("hook_runtime_context_digest_bound") is True and ok
        ),
        "thread_or_turn_digest_bound": (
            source_packet.get("thread_or_turn_digest_bound") is True and ok
        ),
        "alias_context_read": source_packet.get("alias_context_read") is True and ok,
        "allowed_api_route_ids_enforced": (
            source_packet.get("allowed_api_route_ids_enforced") is True and ok
        ),
        "route_id_allowed": source_packet.get("route_id_allowed") is True and ok,
        "api_lane_called": source_packet.get("api_lane_called") is True and ok,
        "api_response_received": (
            source_packet.get("api_response_received") is True and ok
        ),
        "response_bound_to_proof": (
            source_packet.get("response_bound_to_proof") is True and ok
        ),
        "dispatch_proven": source_packet.get("dispatch_proven") is True and ok,
        "dispatch_status": "proven" if ok else "blocked",
        "route_bound_dispatch_proven": (
            source_packet.get("route_bound_dispatch_proven") is True and ok
        ),
        "provider_response_proven": (
            source_packet.get("provider_response_proven") is True and ok
        ),
        "controlled_provider_response_proven": (
            source_packet.get("controlled_provider_response_proven") is True and ok
        ),
        "approved_handoff_ready": (
            source_packet.get("approved_handoff_ready") is True and ok
        ),
        "approved_handoff_payload_sanitized": (
            source_packet.get("approved_handoff_payload_sanitized") is True and ok
        ),
        "source_handoff_delivered": source_packet.get("handoff_delivered") is True and ok,
        "source_delivery_observed": source_packet.get("delivery_observed") is True and ok,
        "handoff_file_write_attempted": not bool(source_required_failures),
        "handoff_file_written": handoff_written,
        "handoff_file_path_recorded": False,
        "handoff_file_sha256": handoff_file_sha256,
        "handoff_payload_digest": _hex_sha256(
            handoff_payload.get("handoff_payload_digest")
        ),
        "handoff_evidence_digest": _hex_sha256(
            handoff_payload.get("handoff_evidence_digest")
        ),
        "handoff_evidence_digest_bound": bool(
            ok and _hex_sha256(handoff_payload.get("handoff_evidence_digest"))
        ),
        "dispatch_result_digest": _hex_sha256(
            handoff_payload.get("dispatch_result_digest")
        ),
        "dispatch_result_digest_bound": bool(
            ok and _hex_sha256(handoff_payload.get("dispatch_result_digest"))
        ),
        "selected_alias": _safe_text(source_packet.get("selected_alias"), limit=80),
        "selected_alias_lane": _safe_text(
            source_packet.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(source_packet.get("selected_slot"), limit=64),
        "selected_api_route_id_present": (
            source_packet.get("selected_api_route_id_present") is True and ok
        ),
        "selected_api_route_id_sha256": _hex_sha256(
            source_packet.get("selected_api_route_id_sha256")
        ),
        "route_bound_request_sha256": _hex_sha256(
            source_packet.get("route_bound_request_sha256")
        ),
        "provider_response_digest": _hex_sha256(
            source_packet.get("provider_response_digest")
        ),
        "controlled_provider_response_sha256": _hex_sha256(
            source_packet.get("controlled_provider_response_sha256")
        ),
        "machine_response_envelope_sha256": _hex_sha256(
            source_packet.get("machine_response_envelope_sha256")
        ),
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router_product_ready": True,
        "does_not_prove_native_free_chat_router_delivery": True,
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
        "evidence_written": handoff_written,
        "file_mutation_attempted": handoff_written,
        "blocking_reasons": blocking_reasons,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved native free-chat router dispatch admission and wrote a proof-backed handoff file."
            if ok
            else "WBP blocked native free-chat router dispatch admission before handoff proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=secret_list,
        extra=extra,
    )


def run_native_free_chat_router_dispatch_admission_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    hook_ledger_file: str,
    runtime_context_file: str | None = None,
    handoff_file: str | None = None,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, _metadata = load_runtime_context_packet(context_path)
    prompt = str(prompt_text or "")
    secret_values = [prompt, *_runtime_secret_values(runtime_context)]
    source_packet = run_real_custom_codex_hook_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        hook_ledger_file=hook_ledger_file,
        runtime_context_file=runtime_context_file,
    )
    output_path = Path(handoff_file).expanduser() if handoff_file else _default_handoff_file(paths)
    return build_native_free_chat_router_dispatch_admission_packet(
        source_packet=source_packet,
        handoff_file=output_path,
        secret_values=secret_values,
    )
