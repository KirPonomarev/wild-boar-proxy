# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.web_token import (
    WEB_TOKEN_FILENAME,
    create_web_token,
    delete_web_token,
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
            self.assertGreaterEqual(len(token), 40)
            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(verify_web_token(state, token))
            self.assertFalse(verify_web_token(state, ""))
            self.assertFalse(verify_web_token(state, None))
            self.assertFalse(verify_web_token(state, token + "x"))

    def test_create_web_token_rotates_and_old_token_stops_verifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            managed_dir = Path(tmpdir) / "managed"
            first = create_web_token(managed_dir)
            first_token = first.token

            second = create_web_token(managed_dir)

            self.assertNotEqual(first_token, second.token)
            self.assertEqual((managed_dir / WEB_TOKEN_FILENAME).read_text(encoding="utf-8"), second.token)
            self.assertFalse(verify_web_token(second, first_token))
            self.assertTrue(verify_web_token(second, second.token))

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


if __name__ == "__main__":
    unittest.main()
