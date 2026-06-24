# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy.wbp_dip_tool import _run_tests


TARGET_MODULE = "test_wbp_dip_tool_command_args_target"


class TestWbpDipToolCommandArgs(unittest.TestCase):
    def test_run_tests_accepts_single_string_args_list_item(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            target_path = repo / f"{TARGET_MODULE}.py"
            target_path.write_text(
                "import unittest\n"
                "class TargetTests(unittest.TestCase):\n"
                "    def test_passes(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            call = {"args": [f"python3 -m unittest {TARGET_MODULE}"]}
            result = _run_tests(repo, call)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["command_exit_code"], 0)
