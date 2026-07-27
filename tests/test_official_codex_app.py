# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import official_codex_app


class OfficialCodexAppTests(unittest.TestCase):
    def _app(self, root: Path, *, bundle_id: str = "com.openai.codex") -> Path:
        app = root / "ChatGPT.app"
        (app / "Contents/MacOS").mkdir(parents=True)
        (app / "Contents/Resources").mkdir(parents=True)
        with (app / "Contents/Info.plist").open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleIdentifier": bundle_id,
                    "CFBundleExecutable": "ChatGPT",
                    "CFBundleShortVersionString": "1.2.3",
                    "CFBundleVersion": "123",
                },
                handle,
            )
        for path in (
            app / "Contents/MacOS/ChatGPT",
            app / "Contents/Resources/codex",
        ):
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        return app

    def test_attestation_requires_bundle_team_signature_and_executables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(Path(tmp))
            with (
                mock.patch.object(
                    official_codex_app,
                    "_codesign_team_id",
                    return_value=(official_codex_app.OFFICIAL_CODEX_TEAM_ID, ""),
                ),
                mock.patch.object(
                    official_codex_app,
                    "_codesign_valid",
                    return_value=(True, ""),
                ),
            ):
                packet = official_codex_app.attest_official_codex_app(app)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["bundle_id_proven"])
        self.assertTrue(packet["team_id_proven"])
        self.assertTrue(packet["codesign_valid"])
        self.assertTrue(packet["cli_executable"])

    def test_bundle_id_collision_fails_before_signature_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(Path(tmp), bundle_id="com.example.lookalike")
            packet = official_codex_app.attest_official_codex_app(app)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "OFFICIAL_CODEX_APP_BUNDLE_ID_MISMATCH",
        )
        self.assertFalse(packet["team_id_proven"])
        self.assertFalse(packet["codesign_valid"])

    def test_wrong_team_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(Path(tmp))
            with mock.patch.object(
                official_codex_app,
                "_codesign_team_id",
                return_value=("WRONGTEAM", ""),
            ):
                packet = official_codex_app.attest_official_codex_app(app)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "OFFICIAL_CODEX_APP_TEAM_ID_MISMATCH",
        )
        self.assertFalse(packet["team_id_proven"])

    def test_explicit_binary_outside_app_fails_closed(self) -> None:
        packet = official_codex_app.resolve_official_codex_app(
            {"WBP_CODEX_BIN": "/tmp/untrusted-codex"}
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "OFFICIAL_CODEX_APP_PATH_INVALID",
        )
        self.assertEqual(packet["candidate_count"], 0)

    def test_explicit_app_does_not_fallback_after_failed_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(Path(tmp), bundle_id="com.example.lookalike")
            packet = official_codex_app.resolve_official_codex_app(
                {"WBP_CODEX_APP_PATH": str(app)}
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["candidate_count"], 1)
        self.assertEqual(packet["attempted_paths"], [str(app.resolve())])


if __name__ == "__main__":
    unittest.main()
