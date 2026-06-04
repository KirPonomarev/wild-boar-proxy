# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import desktop_web_shell
from wild_boar_proxy.web_design_live_server import LIVE_READONLY_ACTION_PHASE
from wild_boar_proxy.web_token import WEB_TOKEN_FILENAME


class DesktopWebShellTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.profile_dir / "managed"
        self.env_patch = mock.patch.dict(
            os.environ,
            {
                "WBP_PROFILE_DIR": str(self.profile_dir),
                "WBP_MANAGED_DIR": str(self.managed_dir),
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_smoke_proves_local_web_shell_and_web_guards(self) -> None:
        packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke()

        self.assertEqual(exit_code, 0, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["desktop_shell"]["strategy"],
            desktop_web_shell.DESKTOP_WEB_SHELL_STRATEGY,
        )
        self.assertEqual(
            packet["desktop_shell"]["entrypoint"],
            desktop_web_shell.DESKTOP_WEB_SHELL_ENTRYPOINT,
        )
        self.assertTrue(packet["server"]["local_only_bind"])
        self.assertFalse(packet["server"]["public_bind_allowed"])
        self.assertEqual(packet["server"]["action_phase"], LIVE_READONLY_ACTION_PHASE)
        self.assertTrue(packet["first_screen"]["data_source_live"])
        self.assertTrue(packet["first_screen"]["custom_launch_action_present"])
        self.assertTrue(packet["first_screen"]["agent_alias_packet_present"])
        self.assertTrue(packet["web_security"]["web_token_bootstrap_meta_present"])
        self.assertTrue(packet["web_security"]["csrf_bootstrap_meta_present"])
        self.assertTrue(
            packet["web_security"]["web_bootstrap_tokens_delivered_to_browser"]
        )
        self.assertTrue(packet["web_security"]["unauthorized_post_rejected"])
        self.assertFalse(packet["packet_contents"]["includes_web_token_value"])
        self.assertFalse(packet["packet_contents"]["includes_csrf_token_value"])
        self.assertFalse(packet["package_boundary"]["evaluated_by_shell_smoke"])
        self.assertTrue(packet["package_boundary"]["requires_package_launchable_verify"])
        self.assertFalse((self.managed_dir / WEB_TOKEN_FILENAME).exists())

    def test_smoke_rejects_public_bind(self) -> None:
        packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke(
            host="0.0.0.0"
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            desktop_web_shell.DESKTOP_WEB_SHELL_PUBLIC_BIND_ERROR,
        )

    def test_validate_desktop_bind_host_rejects_non_loopback_host(self) -> None:
        with self.assertRaises(desktop_web_shell.DesktopWebShellError) as raised:
            desktop_web_shell.validate_desktop_bind_host("192.168.1.10")

        self.assertEqual(
            raised.exception.machine_error_code,
            desktop_web_shell.DESKTOP_WEB_SHELL_PUBLIC_BIND_ERROR,
        )


if __name__ == "__main__":
    unittest.main()
