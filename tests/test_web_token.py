# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.web_token import (
    WEB_AUTH_HEADER,
    WEB_CSRF_HEADER,
    WEB_FORM_CSRF_FIELD,
    WEB_FORM_TOKEN_FIELD,
    WEB_TOKEN_FILENAME,
    create_in_memory_web_token,
    create_web_token,
    delete_web_token,
    web_form_csrf_valid,
    web_form_token_valid,
    web_post_csrf_valid,
    web_post_token_valid,
    verify_web_csrf,
    verify_web_token,
)


class WebTokenTests(unittest.TestCase):
    def test_create_web_token_writes_0600_token_under_managed_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            managed_dir = Path(tmpdir) / "managed"

            state = create_web_token(managed_dir)

            token_path = managed_dir / WEB_TOKEN_FILENAME
            token = token_path.read_text(encoding="utf-8")
            self.assertEqual(state.token_path, token_path.resolve(strict=False))
            self.assertEqual(token, state.token)
            self.assertNotEqual(state.csrf_token, state.token)
            self.assertGreaterEqual(len(token), 40)
            self.assertGreaterEqual(len(state.csrf_token), 40)
            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(verify_web_token(state, token))
            self.assertTrue(verify_web_csrf(state, state.csrf_token))
            self.assertFalse(verify_web_token(state, ""))
            self.assertFalse(verify_web_token(state, None))
            self.assertFalse(verify_web_token(state, token + "x"))
            self.assertFalse(verify_web_csrf(state, state.csrf_token + "x"))

    def test_create_web_token_rotates_and_old_token_stops_verifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            managed_dir = Path(tmpdir) / "managed"
            first = create_web_token(managed_dir)
            first_token = first.token

            second = create_web_token(managed_dir)

            self.assertNotEqual(first_token, second.token)
            self.assertNotEqual(first.csrf_token, second.csrf_token)
            self.assertEqual((managed_dir / WEB_TOKEN_FILENAME).read_text(encoding="utf-8"), second.token)
            self.assertFalse(verify_web_token(second, first_token))
            self.assertTrue(verify_web_token(second, second.token))
            self.assertFalse(verify_web_csrf(second, first.csrf_token))
            self.assertTrue(verify_web_csrf(second, second.csrf_token))

    def test_delete_web_token_is_best_effort_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            managed_dir = Path(tmpdir) / "managed"
            state = create_web_token(managed_dir)

            delete_web_token(state)
            delete_web_token(state)
            delete_web_token(None)

            self.assertFalse((managed_dir / WEB_TOKEN_FILENAME).exists())

    def test_delete_web_token_does_not_remove_newer_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            managed_dir = Path(tmpdir) / "managed"
            first = create_web_token(managed_dir)
            second = create_web_token(managed_dir)

            delete_web_token(first)

            token_path = managed_dir / WEB_TOKEN_FILENAME
            self.assertTrue(token_path.exists())
            self.assertEqual(token_path.read_text(encoding="utf-8"), second.token)

    def test_in_memory_web_token_does_not_write_or_delete_files(self) -> None:
        state = create_in_memory_web_token()

        delete_web_token(state)

        self.assertIsNone(state.token_path)
        self.assertTrue(verify_web_token(state, state.token))
        self.assertTrue(verify_web_csrf(state, state.csrf_token))

    def test_web_post_and_form_token_validation_helpers(self) -> None:
        state = create_in_memory_web_token()
        headers = {
            WEB_AUTH_HEADER: f"Bearer {state.token}",
            WEB_CSRF_HEADER: state.csrf_token,
        }
        fields = {
            WEB_FORM_TOKEN_FIELD: state.token,
            WEB_FORM_CSRF_FIELD: state.csrf_token,
        }

        self.assertTrue(web_post_token_valid(state, headers))
        self.assertTrue(web_post_csrf_valid(state, headers))
        self.assertTrue(web_form_token_valid(state, fields))
        self.assertTrue(web_form_csrf_valid(state, fields))

        self.assertFalse(web_post_token_valid(state, {WEB_AUTH_HEADER: state.token}))
        self.assertFalse(web_post_token_valid(state, {WEB_AUTH_HEADER: "Bearer wrong"}))
        self.assertFalse(web_post_csrf_valid(state, {WEB_CSRF_HEADER: "wrong"}))
        self.assertFalse(web_form_token_valid(state, {WEB_FORM_TOKEN_FIELD: "wrong"}))
        self.assertFalse(web_form_csrf_valid(state, {WEB_FORM_CSRF_FIELD: "wrong"}))


if __name__ == "__main__":
    unittest.main()
