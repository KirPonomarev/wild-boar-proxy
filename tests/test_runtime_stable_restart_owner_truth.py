# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from wild_boar_proxy import runtime as runtime_mod


class StableRuntimeRestartOwnerTruthTests(unittest.TestCase):
    def test_restart_rejects_listener_that_reappears_without_launched_config_owner(self) -> None:
        paths = SimpleNamespace(stable_config=Path("/owned/config.yaml"))
        launched_config = Path("/owned/generated.yaml")

        def command_contains_path(pid: str, path: Path) -> bool:
            return pid == "111" and path == paths.stable_config

        with (
            mock.patch.object(
                runtime_mod,
                "get_endpoint",
                return_value=("127.0.0.1", 8318, "http://127.0.0.1:8318/v1"),
            ),
            mock.patch.object(
                runtime_mod,
                "socket_is_listening",
                side_effect=[True, True],
            ),
            mock.patch.object(
                runtime_mod,
                "discover_stable_runtime_pids",
                side_effect=[[111], [333]],
            ),
            mock.patch.object(
                runtime_mod,
                "pid_command_line_contains_path",
                side_effect=command_contains_path,
            ),
            mock.patch.object(runtime_mod, "terminate_pid", return_value=True),
            mock.patch.object(
                runtime_mod,
                "launch_stable_runtime_process",
                return_value={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "pid": 222,
                    "config_path": str(launched_config),
                },
            ),
        ):
            packet = runtime_mod.restart_owned_stable_runtime_process(
                paths, config_path=launched_config
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "STABLE_RUNTIME_LAUNCHED_OWNER_UNPROVEN",
        )
        self.assertEqual(packet["terminated_pids"], [111])
        self.assertEqual(packet["active_pids"], [333])
        self.assertEqual(packet["active_owner_pids"], [])
        self.assertEqual(packet["launched_config_path"], str(launched_config))


if __name__ == "__main__":
    unittest.main()
