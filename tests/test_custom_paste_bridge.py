# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.custom_paste_bridge import (
    build_custom_paste_bridge_live_packet,
    build_custom_paste_bridge_preflight_packet,
    custom_paste_bridge_live_payload_ready,
    custom_paste_bridge_preflight_payload_ready,
)


class CustomPasteBridgePacketTests(unittest.TestCase):
    def test_preflight_rejects_raw_text_and_forbidden_authority(self) -> None:
        payload = {
            "draft_length": 10,
            "draft_sha256": "a" * 64,
            "draft_text": "raw secret draft",
            "route_id": "browser-route",
        }

        packet = build_custom_paste_bridge_preflight_packet(payload)

        self.assertFalse(custom_paste_bridge_preflight_payload_ready(payload))
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "BROWSER_PAYLOAD_FORBIDDEN_FIELDS")
        self.assertIn("draft_text", packet["blocking_reasons"])
        self.assertIn("route_id", packet["blocking_reasons"])
        self.assertFalse(packet["draft_text_in_packet"])
        self.assertFalse(packet["live_paste_attempted"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertFalse(packet["api_called"])
        self.assertNotIn("raw secret draft", json.dumps(packet, ensure_ascii=False))

    def test_preflight_ok_requires_unique_custom_target(self) -> None:
        payload = {"draft_length": 7, "draft_sha256": "b" * 64, "request_id": "r1"}
        native_target = {
            "status": "ok",
            "machine_error_code": "OK",
            "custom_window_found": True,
            "custom_window_identity": "custom_codex",
            "custom_window_identity_proven": True,
            "target_input_candidate": "single",
            "target_input_unique": True,
            "custom_window_mutation_attempted": False,
        }

        packet = build_custom_paste_bridge_preflight_packet(
            payload,
            native_target_packet=native_target,
        )

        self.assertTrue(custom_paste_bridge_preflight_payload_ready(payload))
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["target_input_unique"])
        self.assertFalse(packet["live_paste_attempted"])
        self.assertFalse(packet["paste_attempted"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertFalse(packet["enter_key_pressed"])
        self.assertFalse(packet["send_button_pressed"])

    def test_live_blocks_without_owner_auth_before_executor(self) -> None:
        called = False

        def executor(_draft_text: str, _request_id: str) -> dict[str, object]:
            nonlocal called
            called = True
            return {"status": "ok"}

        payload = {"draft_text": "paste me", "draft_length": 8, "draft_sha256": "c" * 64}

        packet = build_custom_paste_bridge_live_packet(
            payload,
            owner_authorized=False,
            paste_executor=executor,
        )

        self.assertFalse(custom_paste_bridge_live_payload_ready(payload, owner_authorized=False))
        self.assertFalse(called)
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "OWNER_AUTH_REQUIRED")
        self.assertFalse(packet["live_paste_attempted"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertNotIn("paste me", json.dumps(packet, ensure_ascii=False))

    def test_live_ok_is_paste_only_and_redacted(self) -> None:
        payload = {"draft_text": "paste me", "draft_length": 8, "draft_sha256": "d" * 64}

        def executor(draft_text: str, request_id: str) -> dict[str, object]:
            self.assertEqual(draft_text, "paste me")
            self.assertEqual(request_id, "")
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "custom_window_found": True,
                "custom_window_identity": "custom_codex",
                "custom_window_identity_proven": True,
                "target_input_candidate": "single",
                "target_input_unique": True,
                "clipboard_backup_captured": True,
                "clipboard_handoff_attempted": True,
                "clipboard_write_attempted": True,
                "clipboard_restore_attempted": True,
                "clipboard_restored": True,
                "paste_attempted": True,
                "paste_ok": True,
                "custom_mutation_scope": "paste_only",
                "custom_window_mutation_attempted": True,
                "input_text_insert_attempted": True,
                "input_text_insert_succeeded": True,
            }

        packet = build_custom_paste_bridge_live_packet(
            payload,
            owner_authorized=True,
            paste_executor=executor,
        )

        self.assertTrue(custom_paste_bridge_live_payload_ready(payload, owner_authorized=True))
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["paste_attempted"])
        self.assertTrue(packet["paste_ok"])
        self.assertEqual(packet["custom_mutation_scope"], "paste_only")
        self.assertTrue(packet["clipboard_restored"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertFalse(packet["submit_action_planned"])
        self.assertFalse(packet["enter_key_pressed"])
        self.assertFalse(packet["send_button_pressed"])
        self.assertFalse(packet["api_called"])
        self.assertFalse(packet["model_endpoint_called"])
        self.assertFalse(packet["operator_run_called"])
        self.assertFalse(packet["session_prompt_endpoint_called"])
        self.assertFalse(packet["draft_text_in_packet"])
        self.assertNotIn("paste me", json.dumps(packet, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
