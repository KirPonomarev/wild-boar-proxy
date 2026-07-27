# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tools.smoke_temp_runtime import _build_summary


ROOT = Path(__file__).resolve().parents[1]


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

    def test_smoke_temp_runtime_positive_path_is_green(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/smoke_temp_runtime.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["failed_commands"], [])
        self.assertEqual(payload["commands"]["healthcheck"]["status"], "ok")
        self.assertEqual(payload["commands"]["healthcheck"]["exit_code"], 0)
        self.assertEqual(
            payload["commands"]["healthcheck"]["machine_error_code"], "OK"
        )


if __name__ == "__main__":
    unittest.main()
