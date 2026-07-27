# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest
from unittest import mock

import wild_boar_proxy.native_window_probe as native_probe


class NativeCustomPasteBridgeTests(unittest.TestCase):
    def test_native_prompt_submit_verifier_escapes_contenteditable_newline_normalizer(self) -> None:
        prompt = "line one\nline two"
        cdp_messages: list[dict[str, object]] = []

        def fake_cdp(_ws_url: str, message: dict[str, object], **_kwargs: object) -> dict[str, object]:
            cdp_messages.append(message)
            method = message["method"]
            if method == "Runtime.evaluate":
                expression = str(message["params"]["expression"])  # type: ignore[index]
                message_id = int(message["id"])
                if message_id == 3001:
                    return {
                        "id": message["id"],
                        "result": {
                            "result": {
                                "value": {
                                    "url": "app://-/index.html",
                                    "focused": True,
                                    "textValueCaptured": False,
                                }
                            }
                        },
                    }
                if message_id == 3201:
                    self.assertIn('replace(/\\r\\n/g, "\\n")', expression)
                    self.assertIn('replace(/\\n\\n/g, "\\n")', expression)
                    return {
                        "id": message["id"],
                        "result": {
                            "result": {
                                "value": {
                                    "insertedLengthMatches": True,
                                    "insertedTextPresent": True,
                                    "textValueCaptured": False,
                                }
                            }
                        },
                    }
                if message_id == 3301:
                    return {
                        "id": message["id"],
                        "result": {
                            "result": {
                                "value": {
                                    "submitted": True,
                                    "submitButtonObserved": False,
                                    "submitMechanism": "cdp_keyboard_event_enter",
                                    "textValueCaptured": False,
                                }
                            }
                        },
                    }
                if message_id == 3650:
                    return {
                        "id": message["id"],
                        "result": {
                            "result": {
                                "value": {
                                    "promptAcceptanceScanPerformed": True,
                                    "promptAccepted": True,
                                    "promptStillInInput": False,
                                    "inputCandidateCount": 1,
                                    "inputContainingPromptCandidateCount": 0,
                                    "maxVisibleInputLength": 0,
                                    "disabledSubmitLikeButtonCount": 0,
                                    "submitLikeButtonCount": 1,
                                    "textValueCaptured": False,
                                    "rawDomExposed": False,
                                    "rawPromptRecorded": False,
                                }
                            }
                        },
                    }
            if method == "Input.insertText":
                return {"id": message["id"], "result": {}}
            raise AssertionError(f"unexpected CDP message {message}")

        with (
            mock.patch.object(native_probe, "_devtools_port_owned_by_pid", return_value=(True, "111")),
            mock.patch.object(
                native_probe,
                "_cdp_app_page_targets",
                return_value=([
                    {
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
                        "url": "app://-/index.html",
                        "type": "page",
                    }
                ], ""),
            ),
            mock.patch.object(native_probe, "_cdp_command", side_effect=fake_cdp),
            mock.patch.object(native_probe, "_read_macos_clipboard_text") as read_clipboard,
        ):
            packet = native_probe._cdp_submit_prompt_to_app_page(
                111,
                prompt,
                request_id="submit-newline-normalizer-test",
                allowed_owner_pids=[111],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["input_text_insert_method"], "cdp_insert_text")
        self.assertTrue(packet["prompt_submitted"])
        read_clipboard.assert_not_called()
        self.assertEqual(
            [message["method"] for message in cdp_messages],
            [
                "Runtime.evaluate",
                "Input.insertText",
                "Runtime.evaluate",
                "Runtime.evaluate",
                "Runtime.evaluate",
            ],
        )

    def test_cdp_clipboard_paste_only_never_dispatches_enter_or_submit(self) -> None:
        draft = "WBP paste bridge draft"
        cdp_messages: list[dict[str, object]] = []
        clipboard_writes: list[str] = []

        def fake_cdp(_ws_url: str, message: dict[str, object], **_kwargs: object) -> dict[str, object]:
            cdp_messages.append(message)
            method = message["method"]
            if method == "Runtime.evaluate":
                if int(message["id"]) < 3900:
                    value = {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "targetInputUnique": True,
                        "targetInputFocused": True,
                        "targetInputLength": 0,
                        "textValueCaptured": False,
                    }
                else:
                    value = {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "visibleInputCandidateCount": 1,
                        "targetInputUnique": True,
                        "targetInputFocused": True,
                        "afterLength": len(draft),
                        "expectedAfterLength": len(draft),
                        "draftTextPresent": True,
                        "pasteLengthDeltaMatches": True,
                        "pasteReplaceLengthMatches": True,
                        "textValueCaptured": False,
                    }
                return {"id": message["id"], "result": {"result": {"value": value}}}
            if method == "Input.dispatchKeyEvent":
                return {"id": message["id"], "result": {}}
            raise AssertionError(f"unexpected CDP method {method}")

        def fake_write_clipboard(value: str) -> tuple[bool, str]:
            clipboard_writes.append(value)
            return True, ""

        with (
            mock.patch.object(native_probe, "_devtools_port_owned_by_pid", return_value=(True, "111")),
            mock.patch.object(
                native_probe,
                "_cdp_app_page_targets",
                return_value=([
                    {
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
                        "url": "app://-/index.html",
                        "type": "page",
                    }
                ], ""),
            ),
            mock.patch.object(native_probe, "_cdp_command", side_effect=fake_cdp),
            mock.patch.object(native_probe, "_read_macos_clipboard_text", return_value=(True, "old-clipboard", "")),
            mock.patch.object(native_probe, "_write_macos_clipboard_text", side_effect=fake_write_clipboard),
        ):
            packet = native_probe._cdp_paste_clipboard_into_custom_target(
                111,
                draft,
                request_id="paste-test",
                allowed_owner_pids=[111],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["paste_ok"])
        self.assertEqual(packet["custom_mutation_scope"], "paste_only")
        self.assertTrue(packet["clipboard_backup_captured"])
        self.assertTrue(packet["clipboard_write_attempted"])
        self.assertTrue(packet["clipboard_restored"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertFalse(packet["submit_action_planned"])
        self.assertFalse(packet["enter_key_planned"])
        self.assertFalse(packet["enter_key_pressed"])
        self.assertFalse(packet["send_button_planned"])
        self.assertFalse(packet["send_button_pressed"])
        self.assertFalse(packet["api_called"])
        self.assertFalse(packet["model_endpoint_called"])
        self.assertEqual(clipboard_writes, [draft, "old-clipboard"])
        key_events = [message for message in cdp_messages if message["method"] == "Input.dispatchKeyEvent"]
        self.assertEqual(len(key_events), 2)
        self.assertEqual(key_events[0]["params"]["code"], "KeyV")
        self.assertEqual(key_events[0]["params"]["commands"], ["Paste"])
        self.assertNotEqual(key_events[0]["params"].get("key"), "Enter")
        self.assertTrue(all(event["params"].get("code") != "Enter" for event in key_events))
        serialized = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn(draft, serialized)
        self.assertNotIn("old-clipboard", serialized)

    def test_clipboard_restore_failure_is_not_false_green(self) -> None:
        draft = "restore failure draft"
        write_count = 0

        def fake_cdp(_ws_url: str, message: dict[str, object], **_kwargs: object) -> dict[str, object]:
            if message["method"] == "Runtime.evaluate":
                value = {
                    "readyState": "complete",
                    "url": "app://-/index.html",
                    "inputCandidateCount": 1,
                    "visibleInputCandidateCount": 1,
                    "targetInputUnique": True,
                    "targetInputFocused": True,
                    "targetInputLength": 0,
                    "afterLength": len(draft),
                    "expectedAppendLength": len(draft),
                    "expectedReplaceLength": len(draft),
                    "draftTextPresent": True,
                    "pasteLengthDeltaMatches": True,
                    "pasteReplaceLengthMatches": True,
                    "textValueCaptured": False,
                }
                return {"id": message["id"], "result": {"result": {"value": value}}}
            return {"id": message["id"], "result": {}}

        def fake_write_clipboard(_value: str) -> tuple[bool, str]:
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                return False, "restore failed"
            return True, ""

        with (
            mock.patch.object(native_probe, "_devtools_port_owned_by_pid", return_value=(True, "111")),
            mock.patch.object(
                native_probe,
                "_cdp_app_page_targets",
                return_value=([
                    {
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
                        "url": "app://-/index.html",
                        "type": "page",
                    }
                ], ""),
            ),
            mock.patch.object(native_probe, "_cdp_command", side_effect=fake_cdp),
            mock.patch.object(native_probe, "_read_macos_clipboard_text", return_value=(True, "old", "")),
            mock.patch.object(native_probe, "_write_macos_clipboard_text", side_effect=fake_write_clipboard),
        ):
            packet = native_probe._cdp_paste_clipboard_into_custom_target(
                111,
                draft,
                request_id="restore-test",
                allowed_owner_pids=[111],
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CLIPBOARD_RESTORE_FAILED")
        self.assertTrue(packet["paste_ok"])
        self.assertTrue(packet["input_text_insert_succeeded"])
        self.assertFalse(packet["clipboard_restored"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertNotIn(draft, json.dumps(packet, ensure_ascii=False))

    def test_cdp_clipboard_paste_accepts_replace_selection_without_raw_text(self) -> None:
        draft = "replace selected placeholder"

        def fake_cdp(_ws_url: str, message: dict[str, object], **_kwargs: object) -> dict[str, object]:
            if message["method"] == "Runtime.evaluate":
                if int(message["id"]) < 3900:
                    value = {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "targetInputUnique": True,
                        "targetInputFocused": True,
                        "targetInputLength": 1,
                        "textValueCaptured": False,
                    }
                else:
                    value = {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "visibleInputCandidateCount": 1,
                        "targetInputUnique": True,
                        "targetInputFocused": True,
                        "afterLength": len(draft),
                        "expectedAppendLength": len(draft) + 1,
                        "expectedReplaceLength": len(draft),
                        "draftTextPresent": True,
                        "pasteLengthDeltaMatches": False,
                        "pasteReplaceLengthMatches": True,
                        "textValueCaptured": False,
                    }
                return {"id": message["id"], "result": {"result": {"value": value}}}
            if message["method"] == "Input.dispatchKeyEvent":
                return {"id": message["id"], "result": {}}
            raise AssertionError(f"unexpected CDP method {message['method']}")

        with (
            mock.patch.object(native_probe, "_devtools_port_owned_by_pid", return_value=(True, "111")),
            mock.patch.object(
                native_probe,
                "_cdp_app_page_targets",
                return_value=([
                    {
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
                        "url": "app://-/index.html",
                        "type": "page",
                    }
                ], ""),
            ),
            mock.patch.object(native_probe, "_cdp_command", side_effect=fake_cdp),
            mock.patch.object(native_probe, "_read_macos_clipboard_text", return_value=(True, "old", "")),
            mock.patch.object(native_probe, "_write_macos_clipboard_text", return_value=(True, "")),
        ):
            packet = native_probe._cdp_paste_clipboard_into_custom_target(
                111,
                draft,
                request_id="replace-test",
                allowed_owner_pids=[111],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["paste_ok"])
        self.assertTrue(packet["input_text_insert_succeeded"])
        self.assertTrue(packet["draft_text_present_after_paste"])
        self.assertFalse(packet["paste_length_delta_matches"])
        self.assertTrue(packet["paste_replace_length_matches"])
        self.assertEqual(packet["target_input_before_length"], 1)
        self.assertEqual(packet["target_input_after_length"], len(draft))
        self.assertFalse(packet["prompt_submitted"])
        self.assertNotIn(draft, json.dumps(packet, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
