# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "emit_r5_ci_receipt.py"

sys.path.insert(0, str(ROOT / "tools"))
import emit_r5_ci_receipt as emit  # noqa: E402

FAKE_SHA = "a" * 40


def _ci_env(**overrides: str) -> dict[str, str]:
    env = {
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": FAKE_SHA,
    }
    env.update(overrides)
    return env


class BuildReceiptTests(unittest.TestCase):
    def test_happy_path_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.txt"
            summary.write_bytes(b"23 passed in 3.60s\n")
            artifact = Path(tmp) / "pkg.whl"
            artifact.write_bytes(b"wheel-bytes")
            receipt = emit.build_receipt(
                env=_ci_env(),
                job_name="r5-full-suite",
                command="make test-full",
                exit_code=0,
                summary_file=summary,
                artifact_file=artifact,
                details={"tests_passed": 23},
                observed_at="2026-08-06T00:00:00Z",
            )
        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(receipt["conclusion"], "success")
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(
            receipt["test_summary_sha256"],
            hashlib.sha256(b"23 passed in 3.60s\n").hexdigest(),
        )
        self.assertEqual(
            receipt["artifact_sha256"], hashlib.sha256(b"wheel-bytes").hexdigest()
        )
        self.assertEqual(receipt["commit_sha"], FAKE_SHA)
        self.assertEqual(receipt["workflow_run_attempt"], "1")
        self.assertEqual(receipt["details"], {"tests_passed": 23})

    def test_nonzero_exit_code_is_failure_conclusion(self) -> None:
        receipt = emit.build_receipt(
            env=_ci_env(),
            job_name="r5-unit-isolation",
            command="pytest -q tests/",
            exit_code=1,
            summary_file=None,
            artifact_file=None,
            details=None,
            observed_at="2026-08-06T00:00:00Z",
        )
        self.assertEqual(receipt["conclusion"], "failure")
        self.assertEqual(receipt["exit_code"], 1)
        self.assertIsNone(receipt["test_summary_sha256"])
        self.assertIsNone(receipt["artifact_sha256"])
        self.assertNotIn("details", receipt)

    def test_missing_env_fails_closed(self) -> None:
        for missing in emit.REQUIRED_ENV:
            env = _ci_env()
            del env[missing]
            with self.assertRaises(SystemExit):
                emit.build_receipt(
                    env=env,
                    job_name="j",
                    command="c",
                    exit_code=0,
                    summary_file=None,
                    artifact_file=None,
                    details=None,
                )

    def test_bad_commit_sha_fails_closed(self) -> None:
        with self.assertRaises(SystemExit):
            emit.build_receipt(
                env=_ci_env(GITHUB_SHA="not-a-sha"),
                job_name="j",
                command="c",
                exit_code=0,
                summary_file=None,
                artifact_file=None,
                details=None,
            )

    def test_canonical_bytes_sorted_lf_terminated(self) -> None:
        payload = emit.canonical_receipt_bytes({"b": 1, "a": 2})
        self.assertEqual(payload, b'{"a":2,"b":1}\n')


class CliTests(unittest.TestCase):
    def _run(self, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        full_env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
        full_env.update(env)
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            capture_output=True,
            text=True,
            env=full_env,
            timeout=30,
        )

    def test_cli_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "s.txt"
            summary.write_text("ok\n", encoding="utf-8")
            details = Path(tmp) / "d.json"
            details.write_text('{"runner":"ci"}', encoding="utf-8")
            out = Path(tmp) / "receipt.json"
            result = self._run(
                [
                    "--job-name",
                    "r5-package",
                    "--command",
                    "python3 -m build",
                    "--exit-code",
                    "0",
                    "--summary-file",
                    str(summary),
                    "--details-json",
                    str(details),
                    "--out",
                    str(out),
                ],
                _ci_env(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["job_name"], "r5-package")
            self.assertEqual(receipt["details"], {"runner": "ci"})

    def test_cli_fails_without_ci_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "receipt.json"
            result = self._run(
                [
                    "--job-name",
                    "j",
                    "--command",
                    "c",
                    "--exit-code",
                    "0",
                    "--out",
                    str(out),
                ],
                {},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_cli_fails_on_missing_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "receipt.json"
            result = self._run(
                [
                    "--job-name",
                    "j",
                    "--command",
                    "c",
                    "--exit-code",
                    "0",
                    "--summary-file",
                    str(Path(tmp) / "absent.txt"),
                    "--out",
                    str(out),
                ],
                _ci_env(),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
