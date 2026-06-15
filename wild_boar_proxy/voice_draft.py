# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fail-closed contract for the WBP-side voice draft surface."""

from __future__ import annotations

from typing import Any

from wild_boar_proxy.custom_paste_bridge import (
    CUSTOM_PASTE_BRIDGE_LIVE_ENDPOINT,
    CUSTOM_PASTE_BRIDGE_PREFLIGHT_ENDPOINT,
)


VOICE_DRAFT_ENDPOINT = "/api/wbp/voice-draft"
VOICE_DRAFT_PACKET_KIND = "wbp_voice_draft_contract"
VOICE_DRAFT_MACHINE_ERROR_CODE = "TRANSCRIPTION_ENGINE_NOT_CONFIGURED"


def build_voice_draft_contract_packet() -> dict[str, Any]:
    """Return the server-owned contract for browser-local voice drafts."""

    return {
        "schema_version": 1,
        "packet_kind": VOICE_DRAFT_PACKET_KIND,
        "endpoint": VOICE_DRAFT_ENDPOINT,
        "status": "blocked",
        "machine_error_code": VOICE_DRAFT_MACHINE_ERROR_CODE,
        "human_message": "WBP voice draft UI is present, but no server transcription engine is configured.",
        "voice_input_ui_present": True,
        "voice_capture_scope": "wbp_browser_local_draft",
        "transcription_adapter_scope": "browser_speech_recognition_if_available",
        "transcription_adapter_fail_closed": True,
        "audio_recording_requires_explicit_user_action": True,
        "transcript_preview_required": True,
        "server_audio_ingress_enabled": False,
        "raw_audio_recorded_by_server": False,
        "raw_audio_persisted_by_default": False,
        "transcript_persisted_by_server": False,
        "custom_codex_not_mutated": True,
        "custom_window_mutation_attempted": False,
        "prompt_not_submitted": True,
        "clipboard_handoff_available": True,
        "clipboard_handoff_attempted": False,
        "clipboard_handoff_ok": False,
        "clipboard_contains_transcript": False,
        "empty_transcript_copy_blocked": True,
        "clipboard_copy_only": True,
        "custom_paste_bridge_available": True,
        "custom_paste_bridge_preflight_endpoint": CUSTOM_PASTE_BRIDGE_PREFLIGHT_ENDPOINT,
        "custom_paste_bridge_live_endpoint": CUSTOM_PASTE_BRIDGE_LIVE_ENDPOINT,
        "custom_paste_bridge_preflight_required": True,
        "custom_paste_bridge_live_requires_owner_authorization": True,
        "clipboard_restore_required": True,
        "clipboard_restored": False,
        "live_paste_attempted": False,
        "paste_attempted": False,
        "paste_ok": False,
        "custom_mutation_scope": "none",
        "submit_action_planned": False,
        "enter_key_planned": False,
        "enter_key_pressed": False,
        "send_button_planned": False,
        "send_button_pressed": False,
        "api_called": False,
        "model_endpoint_called": False,
        "operator_run_called": False,
        "session_prompt_endpoint_called": False,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
        "no_secret_exposed": True,
        "changed_files": [],
        "next_action": "use_browser_voice_adapter_or_copy_manual_draft",
    }
