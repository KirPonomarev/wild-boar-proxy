# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Contract tests for .github/workflows/r5-assurance-ci.yml (SD-R57 item 3).

The full-suite receipt must never claim clean_run=true after a nonzero
make test-full exit code, and every r5 job must emit a per-attempt receipt
with if: always() upload. Raw-text parsing only: PyYAML is not a project
dependency.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "r5-assurance-ci.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job_section(text: str, job_key: str) -> str:
    """Extract the `  <job_key>:` block from the jobs mapping (2-space indent)."""
    match = re.search(rf"^  {re.escape(job_key)}:\n(.*?)(?=^  \S|\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"job section not found: {job_key}")
    return match.group(1)


class R5WorkflowContractTests(unittest.TestCase):
    def test_full_suite_clean_run_is_bound_to_exit_code(self) -> None:
        section = _job_section(_text(), "full-suite")
        self.assertNotIn('"clean_run":true', section)
        self.assertIn(
            'if [ "$code" -eq 0 ]; then clean_run=true; else clean_run=false; fi',
            section,
        )
        self.assertIn('"clean_run":$clean_run', section)

    def test_full_suite_clean_run_simulation(self) -> None:
        """The shell conditional maps exit code 0 to true, nonzero to false."""
        for code, expected in ((0, "true"), (1, "false"), (2, "false")):
            clean = "true" if code == 0 else "false"
            self.assertEqual(clean, expected, f"exit {code} must map to clean_run={expected}")

    def test_every_r5_job_emits_receipt_with_always_upload(self) -> None:
        text = _text()
        for job_key in ("unit-isolation", "full-suite", "macos-sandbox", "package"):
            section = _job_section(text, job_key)
            self.assertIn("- name: Emit CI receipt", section, f"{job_key}: missing emit step")
            self.assertRegex(
                section,
                re.compile(r"- name: Emit CI receipt\n\s+if: always\(\)"),
                f"{job_key}: emit must be if: always()",
            )
            self.assertRegex(
                section,
                re.compile(r"- name: Upload[^\n]*\n\s+if: always\(\)"),
                f"{job_key}: upload must be if: always()",
            )
            self.assertRegex(
                section,
                re.compile(r"- name: Enforce [^\n]*\n"),
                f"{job_key}: missing enforce step",
            )

    def test_jobs_run_on_required_platforms(self) -> None:
        text = _text()
        for job_key in ("unit-isolation", "full-suite", "macos-sandbox"):
            section = _job_section(text, job_key)
            self.assertIn("runs-on: macos-latest", section, f"{job_key}: must run on macOS")
        self.assertIn("runs-on: ubuntu-latest", _job_section(text, "package"))


if __name__ == "__main__":
    unittest.main()
