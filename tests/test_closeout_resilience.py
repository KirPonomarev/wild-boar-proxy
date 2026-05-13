# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "tools" / "check_closeout_resilience.py"


spec = importlib.util.spec_from_file_location("check_closeout_resilience", CHECKER_PATH)
assert spec is not None
checker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(checker)


class CloseoutResilienceTests(unittest.TestCase):
    def test_template_contains_required_resilience_fields(self) -> None:
        text = (ROOT / "templates" / "CLOSEOUT_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        for phrase in checker.REQUIRED_PHRASES:
            self.assertIn(phrase, text)

    def test_valid_closeout_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit_results" / "sample_closeout.md"
            path.parent.mkdir()
            path.write_text(
                "\n".join(
                    (
                        "# Sample Closeout",
                        "## Contour Capsule",
                        "- goal: prove the checker",
                        "- branch: codex/sample",
                        "- head: abc123",
                        "- touched files: tools/check_closeout_resilience.py",
                        "- tests run: python -m unittest tests.test_closeout_resilience",
                        "- blocked risks: none",
                        "- next exact command: CLOSED",
                        "## Notes",
                        "- resume from here: CLOSED",
                    )
                ),
                encoding="utf-8",
            )

            self.assertEqual(checker.validate_closeout(path), [])

    def test_missing_capsule_fields_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit_results" / "sample_closeout.md"
            path.parent.mkdir()
            path.write_text(
                "\n".join(
                    (
                        "# Sample Closeout",
                        "## Notes",
                        "- resume from here: CLOSED",
                    )
                ),
                encoding="utf-8",
            )

            errors = checker.validate_closeout(path)

        self.assertTrue(errors)
        self.assertTrue(
            any("## Contour Capsule" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
