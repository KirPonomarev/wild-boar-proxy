# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fail-closed packets for WBP-to-Custom Codex paste-only handoff."""

from __future__ import annotations

from typing import Any, Callable


CUSTOM_PASTE_BRIDGE_PREFLIGHT_ENDPOINT = "/api/wbp/custom-paste-bridge/preflight"
CUSTOM_PASTE_BRIDGE_LIVE_ENDPOINT = "/api/wbp/custom-paste-bridge/live-paste"
CUSTOM_PASTE_BRIDGE_PREFLIGHT_ALLOWED_FIELDS = frozenset(
    {"draft_length", "draft_sha256", "request_id"}
)
CUSTOM_PASTE_BRIDGE_LIVE_ALLOWED_FIELDS = frozenset(
    {"draft_text", "draft_length", "draft_sha256", "request_id"}
)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _draft_length_from_payload(payload: dict[str, Any], *, allow_text: bool) -> int:
    if allow_text:
        return len(_text(payload.get("draft_text")))
    value = payload.get("draft_length")
    try:
        length = int(value)
    except (TypeError, ValueError):
        return 0
    return max(length, 0)


def _draft_sha256_from_payload(payload: dict[str, Any]) -> str:
    value = _text(payload.get("draft_sha256")).strip().lower()
    if len(value) == 64 and all(char in "0123456789abcdef" for char in value):
        return value
    return ""


def _base_packet(
    *,
    endpoint: str,
    phase: str,
    payload: dict[str, Any],
    allow_text: bool,
    owner_authorized_for_live: bool = False,
) -> dict[str, Any]:
    draft_length = _draft_length_from_payload(payload, allow_text=allow_text)
    return {
        "schema_version": 1,
        "packet_kind": "wbp_custom_paste_bridge",
        "endpoint": endpoint,
        "phase": phase,
        "status": "blocked",
        "machine_error_code": "PENDING",
        "human_message": "",
        "request_id": _text(payload.get("request_id")),
        "draft_present": draft_length > 0,
        "draft_length": draft_length,
        "draft_sha256": _draft_sha256_from_payload(payload),
        "draft_sha256_present": bool(_draft_sha256_from_payload(payload)),
        "draft_text_in_packet": False,
        "custom_window_found": False,
        "custom_window_identity": "unknown",
        "custom_window_identity_proven": False,
        "target_input_candidate": "unknown",
        "target_input_unique": False,
        "paste_action_plan": "clipboard_paste_only",
        "clipboard_restore_required": True,
        "clipboard_backup_captured": False,
        "clipboard_handoff_attempted": False,
        "clipboard_write_attempted": False,
        "clipboard_restore_attempted": False,
        "clipboard_restored": False,
        "live_paste_attempted": False,
        "paste_attempted": False,
        "paste_ok": False,
        "custom_mutation_scope": "none",
        "custom_window_mutation_attempted": False,
        "input_text_insert_attempted": False,
        "input_text_insert_succeeded": False,
        "prompt_submitted": False,
        "submit_action_planned": False,
        "enter_key_planned": False,
        "enter_key_pressed": False,
        "send_button_planned": False,
        "send_button_pressed": False,
        "api_called": False,
        "model_endpoint_called": False,
        "operator_run_called": False,
        "session_prompt_endpoint_called": False,
        "owner_authorized_for_live": owner_authorized_for_live,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
        "no_secret_exposed": True,
        "next_action": "stop_and_diagnose_custom_paste_bridge",
        "blocking_reasons": [],
    }


def _forbidden_fields(payload: dict[str, Any], allowed_fields: frozenset[str]) -> list[str]:
    return sorted(str(key) for key in payload if str(key) not in allowed_fields)


def _block(
    packet: dict[str, Any],
    *,
    machine_error_code: str,
    human_message: str,
    blocking_reasons: list[str] | None = None,
    next_action: str = "stop_and_diagnose_custom_paste_bridge",
) -> dict[str, Any]:
    packet.update(
        {
            "status": "blocked",
            "machine_error_code": machine_error_code,
            "human_message": human_message,
            "blocking_reasons": blocking_reasons or [machine_error_code],
            "next_action": next_action,
        }
    )
    return packet


def custom_paste_bridge_preflight_payload_ready(payload: dict[str, Any]) -> bool:
    if _forbidden_fields(payload, CUSTOM_PASTE_BRIDGE_PREFLIGHT_ALLOWED_FIELDS):
        return False
    return _draft_length_from_payload(payload, allow_text=False) > 0


def custom_paste_bridge_live_payload_ready(payload: dict[str, Any], *, owner_authorized: bool) -> bool:
    if _forbidden_fields(payload, CUSTOM_PASTE_BRIDGE_LIVE_ALLOWED_FIELDS):
        return False
    if not owner_authorized:
        return False
    return _draft_length_from_payload(payload, allow_text=True) > 0


def _apply_native_target_packet(packet: dict[str, Any], native_target_packet: dict[str, Any]) -> None:
    packet["native_target_packet"] = native_target_packet
    packet["custom_window_found"] = native_target_packet.get("custom_window_found") is True
    packet["custom_window_identity"] = str(
        native_target_packet.get("custom_window_identity") or "unknown"
    )
    packet["custom_window_identity_proven"] = (
        native_target_packet.get("custom_window_identity_proven") is True
    )
    packet["target_input_unique"] = native_target_packet.get("target_input_unique") is True
    packet["target_input_candidate"] = str(
        native_target_packet.get("target_input_candidate") or "unknown"
    )
    packet["custom_window_mutation_attempted"] = (
        native_target_packet.get("custom_window_mutation_attempted") is True
    )


def build_custom_paste_bridge_preflight_packet(
    payload: dict[str, Any],
    *,
    native_target_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = _base_packet(
        endpoint=CUSTOM_PASTE_BRIDGE_PREFLIGHT_ENDPOINT,
        phase="preflight",
        payload=payload,
        allow_text=False,
    )
    forbidden = _forbidden_fields(payload, CUSTOM_PASTE_BRIDGE_PREFLIGHT_ALLOWED_FIELDS)
    if forbidden:
        return _block(
            packet,
            machine_error_code="BROWSER_PAYLOAD_FORBIDDEN_FIELDS",
            human_message="Paste preflight accepts only redacted draft metadata.",
            blocking_reasons=forbidden,
            next_action="remove_forbidden_browser_fields",
        )
    if not packet["draft_present"]:
        return _block(
            packet,
            machine_error_code="EMPTY_DRAFT",
            human_message="Paste preflight requires a non-empty WBP draft.",
            blocking_reasons=["empty_draft"],
            next_action="dictate_or_type_draft",
        )
    if not isinstance(native_target_packet, dict):
        return _block(
            packet,
            machine_error_code="PASTE_PREFLIGHT_NATIVE_TARGET_NOT_CHECKED",
            human_message="Paste preflight has not checked the Custom Codex target window yet.",
            blocking_reasons=["native_target_not_checked"],
            next_action="check_custom_window_target",
        )
    _apply_native_target_packet(packet, native_target_packet)
    if native_target_packet.get("status") != "ok":
        return _block(
            packet,
            machine_error_code=str(
                native_target_packet.get("machine_error_code") or "PASTE_PREFLIGHT_BLOCKED"
            ),
            human_message="Paste preflight could not prove a safe Custom Codex target.",
            blocking_reasons=list(native_target_packet.get("blocking_reasons") or []),
            next_action=str(native_target_packet.get("next_action") or "stop_and_diagnose_custom_window"),
        )
    packet.update(
        {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Custom Codex paste preflight passed without inserting text.",
            "blocking_reasons": [],
            "next_action": "live_paste_requires_owner_authorization",
        }
    )
    return packet


def build_custom_paste_bridge_live_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    paste_executor: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    packet = _base_packet(
        endpoint=CUSTOM_PASTE_BRIDGE_LIVE_ENDPOINT,
        phase="live_paste",
        payload=payload,
        allow_text=True,
        owner_authorized_for_live=owner_authorized,
    )
    forbidden = _forbidden_fields(payload, CUSTOM_PASTE_BRIDGE_LIVE_ALLOWED_FIELDS)
    if forbidden:
        return _block(
            packet,
            machine_error_code="BROWSER_PAYLOAD_FORBIDDEN_FIELDS",
            human_message="Live paste accepts only draft text plus redacted metadata.",
            blocking_reasons=forbidden,
            next_action="remove_forbidden_browser_fields",
        )
    draft_text = _text(payload.get("draft_text"))
    if not draft_text:
        return _block(
            packet,
            machine_error_code="EMPTY_DRAFT",
            human_message="Live paste requires a non-empty WBP draft.",
            blocking_reasons=["empty_draft"],
            next_action="dictate_or_type_draft",
        )
    if not owner_authorized:
        return _block(
            packet,
            machine_error_code="OWNER_AUTH_REQUIRED",
            human_message="Live paste requires exact owner authorization for Custom Codex window mutation.",
            blocking_reasons=["owner_authorization_required"],
            next_action="provide_exact_owner_authorization_phrase",
        )
    if paste_executor is None:
        return _block(
            packet,
            machine_error_code="PASTE_EXECUTOR_NOT_CONFIGURED",
            human_message="Live paste executor is not configured.",
            blocking_reasons=["paste_executor_not_configured"],
        )
    paste_packet = paste_executor(draft_text, packet["request_id"])
    packet["native_paste_packet"] = paste_packet
    packet["custom_window_found"] = paste_packet.get("custom_window_found") is True
    packet["custom_window_identity"] = str(
        paste_packet.get("custom_window_identity") or "unknown"
    )
    packet["custom_window_identity_proven"] = (
        paste_packet.get("custom_window_identity_proven") is True
    )
    packet["target_input_candidate"] = str(paste_packet.get("target_input_candidate") or "unknown")
    packet["target_input_unique"] = paste_packet.get("target_input_unique") is True
    packet["clipboard_backup_captured"] = paste_packet.get("clipboard_backup_captured") is True
    packet["clipboard_handoff_attempted"] = paste_packet.get("clipboard_handoff_attempted") is True
    packet["clipboard_write_attempted"] = paste_packet.get("clipboard_write_attempted") is True
    packet["clipboard_restore_attempted"] = paste_packet.get("clipboard_restore_attempted") is True
    packet["clipboard_restored"] = paste_packet.get("clipboard_restored") is True
    packet["live_paste_attempted"] = paste_packet.get("paste_attempted") is True
    packet["paste_attempted"] = paste_packet.get("paste_attempted") is True
    packet["paste_ok"] = paste_packet.get("paste_ok") is True
    packet["custom_mutation_scope"] = str(paste_packet.get("custom_mutation_scope") or "none")
    packet["custom_window_mutation_attempted"] = (
        paste_packet.get("custom_window_mutation_attempted") is True
    )
    packet["input_text_insert_attempted"] = paste_packet.get("input_text_insert_attempted") is True
    packet["input_text_insert_succeeded"] = (
        paste_packet.get("input_text_insert_succeeded") is True
    )
    if paste_packet.get("status") != "ok":
        return _block(
            packet,
            machine_error_code=str(paste_packet.get("machine_error_code") or "PASTE_FAILED"),
            human_message="Custom Codex live paste did not complete cleanly.",
            blocking_reasons=list(paste_packet.get("blocking_reasons") or []),
            next_action=str(paste_packet.get("next_action") or "stop_and_diagnose_custom_paste"),
        )
    packet.update(
        {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "WBP draft pasted into Custom Codex input without submitting.",
            "blocking_reasons": [],
            "next_action": "inspect_custom_input_then_submit_manually_if_desired",
        }
    )
    return packet
