# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import desktop_web_shell
from wild_boar_proxy.web_design_live_server import (
    FULL_ACTION_PHASE,
    LIVE_READONLY_ACTION_PHASE,
    SANDBOX_ACTION_PHASE,
    OWNER_STANDING_AUTHORIZATION_PHRASE,
)
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
        self.assertFalse(packet["server"]["full_action_phase_admitted_by_desktop_shell"])
        self.assertTrue(packet["first_screen"]["data_source_live"])
        self.assertTrue(packet["first_screen"]["custom_launch_action_present"])
        self.assertTrue(packet["first_screen"]["agent_alias_packet_present"])
        self.assertTrue(packet["first_screen"]["live_readonly_endpoint_ok"])
        self.assertTrue(packet["first_screen"]["status_truth_present"])
        self.assertTrue(packet["first_screen"]["accounts_readonly_endpoint_ok"])
        self.assertIn("accounts_machine_error_code", packet["first_screen"])
        self.assertTrue(packet["first_screen"]["api_connections_readonly_endpoint_ok"])
        self.assertIn("api_machine_error_code", packet["first_screen"])
        self.assertTrue(packet["web_security"]["web_token_bootstrap_meta_present"])
        self.assertTrue(packet["web_security"]["csrf_bootstrap_meta_present"])
        self.assertTrue(
            packet["web_security"]["web_bootstrap_tokens_delivered_to_browser"]
        )
        self.assertTrue(packet["web_security"]["unauthorized_post_rejected"])
        self.assertEqual(
            packet["action_metadata"]["action_phase"],
            LIVE_READONLY_ACTION_PHASE,
        )
        self.assertEqual(
            packet["action_metadata"]["r1_actions"]["api_route_connect"][
                "availability_state"
            ],
            "disabled_live_action",
        )
        self.assertFalse(packet["packet_contents"]["includes_live_readonly_payload"])
        self.assertFalse(packet["packet_contents"]["includes_accounts_payload"])
        self.assertFalse(packet["packet_contents"]["includes_api_connections_payload"])
        self.assertFalse(packet["packet_contents"]["includes_web_token_value"])
        self.assertFalse(packet["packet_contents"]["includes_csrf_token_value"])
        self.assertFalse(packet["package_boundary"]["evaluated_by_shell_smoke"])
        self.assertTrue(packet["package_boundary"]["requires_package_launchable_verify"])
        self.assertFalse((self.managed_dir / WEB_TOKEN_FILENAME).exists())

    def test_smoke_can_admit_explicit_desktop_sandbox_actions(self) -> None:
        packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke(
            action_phase=SANDBOX_ACTION_PHASE
        )

        self.assertEqual(exit_code, 0, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["server"]["action_phase"], SANDBOX_ACTION_PHASE)
        self.assertFalse(packet["server"]["full_action_phase_admitted_by_desktop_shell"])
        self.assertEqual(
            packet["action_metadata"]["action_phase"],
            SANDBOX_ACTION_PHASE,
        )
        self.assertEqual(
            packet["action_metadata"]["sandbox_preflight_status"],
            "admitted",
        )
        self.assertEqual(
            packet["action_metadata"]["sandbox_preflight_machine_error_code"],
            "OK",
        )
        for ui_action in (
            "onboard_account_dry_run",
            "onboard_account",
            "api_route_connect",
            "api_route_credential_check",
            "quick_start_check_all",
        ):
            self.assertTrue(
                packet["action_metadata"]["r1_actions"][ui_action]["available"],
                ui_action,
            )
            self.assertEqual(
                packet["action_metadata"]["r1_actions"][ui_action][
                    "disabled_reason_code"
                ],
                "",
            )
        self.assertFalse(
            packet["action_metadata"]["r1_actions"]["launch_custom_client_native"][
                "available"
            ]
        )
        self.assertEqual(
            packet["action_metadata"]["r1_actions"]["launch_custom_client_native"][
                "disabled_reason_code"
            ],
            "UI_ACTION_PHASE_NOT_ADMITTED",
        )
        self.assertFalse((self.managed_dir / WEB_TOKEN_FILENAME).exists())
        self.assertFalse(desktop_web_shell._desktop_sandbox_root().exists())

    def test_main_smoke_json_uses_ephemeral_port_by_default(self) -> None:
        with (
            mock.patch.object(
                desktop_web_shell,
                "run_desktop_web_shell_smoke",
                return_value=({"status": "ok"}, 0),
            ) as smoke,
            mock.patch("builtins.print"),
        ):
            exit_code = desktop_web_shell.main(["--smoke-json"])

        self.assertEqual(exit_code, 0)
        smoke.assert_called_once_with(
            host=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_HOST,
            port=0,
            action_phase=LIVE_READONLY_ACTION_PHASE,
            owner_authorization_phrase=None,
        )

    def test_smoke_can_admit_explicit_full_phase_with_owner_authorization(self) -> None:
        packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke(
            action_phase=FULL_ACTION_PHASE,
            owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
        )

        self.assertEqual(exit_code, 0, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["server"]["action_phase"], FULL_ACTION_PHASE)
        self.assertTrue(packet["server"]["full_action_phase_admitted_by_desktop_shell"])
        self.assertTrue(
            packet["action_metadata"]["r1_actions"]["launch_custom_client_native"][
                "available"
            ]
        )
        self.assertEqual(
            packet["action_metadata"]["r1_actions"]["launch_custom_client_native"][
                "disabled_reason_code"
            ],
            "",
        )

    def test_smoke_requests_share_one_remaining_total_budget(self) -> None:
        server = mock.MagicMock()
        server.server_port = 43123
        web_token_state = mock.MagicMock()

        with (
            mock.patch.object(
                desktop_web_shell,
                "build_desktop_web_shell_server",
                return_value=(server, web_token_state),
            ),
            mock.patch.object(
                desktop_web_shell.time,
                "monotonic",
                side_effect=[100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            ),
            mock.patch.object(
                desktop_web_shell,
                "_fetch_text",
                side_effect=["<html></html>", "{}"],
            ) as fetch_text,
            mock.patch.object(
                desktop_web_shell,
                "_fetch_json",
                side_effect=[{}, {}, {}],
            ) as fetch_json,
            mock.patch.object(
                desktop_web_shell,
                "_post_json_without_auth",
                return_value={},
            ) as post_json,
            mock.patch.object(
                desktop_web_shell,
                "build_desktop_web_shell_packet",
                return_value={"status": "ok"},
            ),
            mock.patch.object(desktop_web_shell, "delete_web_token"),
            mock.patch.object(
                desktop_web_shell,
                "_cleanup_desktop_sandbox_root_if_needed",
            ),
        ):
            packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke()

        self.assertEqual(exit_code, 0, packet)
        observed_timeouts = [
            fetch_text.call_args_list[0].kwargs["timeout_seconds"],
            fetch_json.call_args_list[0].kwargs["timeout_seconds"],
            fetch_json.call_args_list[1].kwargs["timeout_seconds"],
            fetch_json.call_args_list[2].kwargs["timeout_seconds"],
            fetch_text.call_args_list[1].kwargs["timeout_seconds"],
            post_json.call_args.kwargs["timeout_seconds"],
        ]
        self.assertEqual(observed_timeouts, [29.0, 28.0, 27.0, 26.0, 25.0, 24.0])
        server.shutdown.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_main_smoke_json_forwards_explicit_sandbox_action_phase(self) -> None:
        with (
            mock.patch.object(
                desktop_web_shell,
                "run_desktop_web_shell_smoke",
                return_value=({"status": "ok"}, 0),
            ) as smoke,
            mock.patch("builtins.print"),
        ):
            exit_code = desktop_web_shell.main(
                ["--smoke-json", "--action-phase", SANDBOX_ACTION_PHASE]
            )

        self.assertEqual(exit_code, 0)
        smoke.assert_called_once_with(
            host=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_HOST,
            port=0,
            action_phase=SANDBOX_ACTION_PHASE,
            owner_authorization_phrase=None,
        )

    def test_main_smoke_json_forwards_full_action_phase_owner_authorization(self) -> None:
        with (
            mock.patch.object(
                desktop_web_shell,
                "run_desktop_web_shell_smoke",
                return_value=({"status": "ok"}, 0),
            ) as smoke,
            mock.patch("builtins.print"),
        ):
            exit_code = desktop_web_shell.main(
                [
                    "--smoke-json",
                    "--action-phase",
                    FULL_ACTION_PHASE,
                    "--owner-authorization-phrase",
                    OWNER_STANDING_AUTHORIZATION_PHRASE,
                ]
            )

        self.assertEqual(exit_code, 0)
        smoke.assert_called_once_with(
            host=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_HOST,
            port=0,
            action_phase=FULL_ACTION_PHASE,
            owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
        )

    def test_main_interactive_shell_keeps_default_fixed_port(self) -> None:
        with mock.patch.object(
            desktop_web_shell,
            "run_desktop_web_shell",
            return_value=0,
        ) as run_shell:
            exit_code = desktop_web_shell.main(["--no-open-browser"])

        self.assertEqual(exit_code, 0)
        run_shell.assert_called_once_with(
            host=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_HOST,
            port=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_PORT,
            open_browser=False,
            action_phase=LIVE_READONLY_ACTION_PHASE,
            owner_authorization_phrase=None,
        )

    def test_main_interactive_shell_forwards_explicit_sandbox_action_phase(self) -> None:
        with mock.patch.object(
            desktop_web_shell,
            "run_desktop_web_shell",
            return_value=0,
        ) as run_shell:
            exit_code = desktop_web_shell.main(
                ["--no-open-browser", "--action-phase", SANDBOX_ACTION_PHASE]
            )

        self.assertEqual(exit_code, 0)
        run_shell.assert_called_once_with(
            host=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_HOST,
            port=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_PORT,
            open_browser=False,
            action_phase=SANDBOX_ACTION_PHASE,
            owner_authorization_phrase=None,
        )

    def test_main_interactive_shell_forwards_full_action_phase_owner_authorization(self) -> None:
        with mock.patch.object(
            desktop_web_shell,
            "run_desktop_web_shell",
            return_value=0,
        ) as run_shell:
            exit_code = desktop_web_shell.main(
                [
                    "--no-open-browser",
                    "--action-phase",
                    FULL_ACTION_PHASE,
                    "--owner-authorization-phrase",
                    OWNER_STANDING_AUTHORIZATION_PHRASE,
                ]
            )

        self.assertEqual(exit_code, 0)
        run_shell.assert_called_once_with(
            host=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_HOST,
            port=desktop_web_shell.DESKTOP_WEB_SHELL_DEFAULT_PORT,
            open_browser=False,
            action_phase=FULL_ACTION_PHASE,
            owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
        )

    def test_build_server_rejects_full_action_phase_without_owner_authorization(self) -> None:
        for phrase in (None, "", "   "):
            with self.subTest(phrase=phrase):
                with self.assertRaises(desktop_web_shell.DesktopWebShellError) as raised:
                    desktop_web_shell.build_desktop_web_shell_server(
                        action_phase="full",
                        owner_authorization_phrase=phrase,
                    )

                self.assertEqual(
                    raised.exception.machine_error_code,
                    "DESKTOP_WEB_SHELL_OWNER_AUTHORIZATION_REQUIRED",
                )

    def test_smoke_returns_packet_for_explicit_busy_port(self) -> None:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        try:
            port = int(sock.getsockname()[1])
            packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke(
                port=port
            )
        finally:
            sock.close()

        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            desktop_web_shell.DESKTOP_WEB_SHELL_BIND_ERROR,
        )
        self.assertFalse((self.managed_dir / WEB_TOKEN_FILENAME).exists())

    def test_smoke_returns_packet_for_fetch_failure(self) -> None:
        with mock.patch.object(
            desktop_web_shell,
            "_fetch_text",
            side_effect=OSError("connection closed"),
        ):
            packet, exit_code = desktop_web_shell.run_desktop_web_shell_smoke()

        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "DESKTOP_WEB_SHELL_SMOKE_FAILED")
        self.assertIn("connection closed", packet["human_message"])
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
