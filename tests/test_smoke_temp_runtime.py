# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from tools.smoke_temp_runtime import _build_summary


class SmokeTempRuntimeSummaryTests(unittest.TestCase):
    def test_summary_rejects_hidden_healthcheck_listener_down(self) -> None:
        summary = _build_summary(
            {
                "status": {
                    "status": "ok",
                    "exit_code": 0,
                    "effect": "read",
                    "machine_error_code": "OK",
                },
                "healthcheck": {
                    "status": "error",
                    "exit_code": 1,
                    "effect": "probe",
                    "machine_error_code": "LISTENER_DOWN",
                },
            }
        )

        self.assertEqual(summary["status"], "error")
        self.assertEqual(summary["exit_code"], 1)
        self.assertEqual(summary["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(
            summary["failed_commands"],
            [
                {
                    "command": "healthcheck",
                    "status": "error",
                    "exit_code": 1,
                    "machine_error_code": "LISTENER_DOWN",
                }
            ],
        )

    def test_summary_stays_green_when_all_command_packets_are_green(self) -> None:
        summary = _build_summary(
            {
                "status": {
                    "status": "ok",
                    "exit_code": 0,
                    "effect": "read",
                    "machine_error_code": "OK",
                },
                "healthcheck": {
                    "status": "ok",
                    "exit_code": 0,
                    "effect": "probe",
                    "machine_error_code": "OK",
                },
            }
        )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["exit_code"], 0)
        self.assertEqual(summary["machine_error_code"], "OK")
        self.assertEqual(summary["failed_commands"], [])


if __name__ == "__main__":
    unittest.main()
