# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTED_RE = re.compile(r"(\d+) tests collected")


def _run_collect(*command: str) -> int:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise AssertionError(
            f"collect command failed with code {result.returncode}:\n{output}"
        )
    matches = COLLECTED_RE.findall(output)
    if not matches:
        raise AssertionError(f"collect count missing from output:\n{output}")
    return int(matches[-1])


class MakefileTestFastContractTests(unittest.TestCase):
    def test_test_fast_includes_release_acceptance_gate_regressions(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("test-fast: test-core", makefile)
        self.assertIn("tests/test_gpt_api_dip_acceptance_gate.py", makefile)
        self.assertIn("tests/test_gpt_api_dip_product_ready_gate.py", makefile)
        self.assertIn("tests/test_e2e_mode_matrix.py", makefile)

    def test_make_test_fast_collects_real_material_subset_of_full_suite(self) -> None:
        fast_count = _run_collect(
            "make",
            "test-fast",
            f"PYTEST={sys.executable} -m pytest --collect-only",
        )
        full_count = _run_collect(
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
        )

        self.assertGreater(fast_count, 0)
        self.assertLess(fast_count, full_count)
        self.assertLess(fast_count * 2, full_count)


if __name__ == "__main__":
    unittest.main()
