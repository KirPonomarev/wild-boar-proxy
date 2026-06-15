# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.voice_draft import (
    VOICE_DRAFT_ENDPOINT,
    VOICE_DRAFT_MACHINE_ERROR_CODE,
    VOICE_DRAFT_PACKET_KIND,
    build_voice_draft_contract_packet,
)


class VoiceDraftContractTests(unittest.TestCase):
    def test_voice_draft_contract_is_fail_closed_and_wbp_scoped(self) -> None:
        packet = build_voice_draft_contract_packet()

        self.assertEqual(packet["schema_version"], 1)
        self.assertEqual(packet["packet_kind"], VOICE_DRAFT_PACKET_KIND)
        self.assertEqual(packet["endpoint"], VOICE_DRAFT_ENDPOINT)
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], VOICE_DRAFT_MACHINE_ERROR_CODE)
        self.assertEqual(packet["voice_capture_scope"], "wbp_browser_local_draft")
        self.assertTrue(packet["voice_input_ui_present"])
        self.assertTrue(packet["transcription_adapter_fail_closed"])
        self.assertTrue(packet["clipboard_handoff_available"])
        self.assertFalse(packet["clipboard_handoff_attempted"])
        self.assertFalse(packet["clipboard_handoff_ok"])
        self.assertFalse(packet["clipboard_contains_transcript"])
        self.assertTrue(packet["empty_transcript_copy_blocked"])
        self.assertTrue(packet["custom_paste_bridge_available"])
        self.assertEqual(
            packet["custom_paste_bridge_preflight_endpoint"],
            "/api/wbp/custom-paste-bridge/preflight",
        )
        self.assertEqual(
            packet["custom_paste_bridge_live_endpoint"],
            "/api/wbp/custom-paste-bridge/live-paste",
        )
        self.assertTrue(packet["custom_paste_bridge_preflight_required"])
        self.assertTrue(packet["custom_paste_bridge_live_requires_owner_authorization"])

    def test_voice_draft_contract_does_not_mutate_custom_or_persist_audio(self) -> None:
        packet = build_voice_draft_contract_packet()

        self.assertFalse(packet["server_audio_ingress_enabled"])
        self.assertFalse(packet["raw_audio_recorded_by_server"])
        self.assertFalse(packet["raw_audio_persisted_by_default"])
        self.assertFalse(packet["transcript_persisted_by_server"])
        self.assertTrue(packet["custom_codex_not_mutated"])
        self.assertFalse(packet["custom_window_mutation_attempted"])
        self.assertTrue(packet["prompt_not_submitted"])
        self.assertFalse(packet["paste_attempted"])
        self.assertFalse(packet["paste_ok"])
        self.assertEqual(packet["custom_mutation_scope"], "none")
        self.assertFalse(packet["submit_action_planned"])
        self.assertFalse(packet["enter_key_pressed"])
        self.assertFalse(packet["send_button_pressed"])
        self.assertFalse(packet["api_called"])
        self.assertFalse(packet["model_endpoint_called"])
        self.assertFalse(packet["operator_run_called"])
        self.assertFalse(packet["session_prompt_endpoint_called"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertEqual(packet["changed_files"], [])


if __name__ == "__main__":
    unittest.main()
