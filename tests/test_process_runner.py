from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from io import StringIO

from wild_boar_proxy.process_runner import (
    PROCESS_FAILED,
    PROCESS_NOT_FOUND,
    PROCESS_OK,
    PROCESS_TIMEOUT,
    BoundedProcessRunner,
)


class BoundedProcessRunnerTests(unittest.TestCase):
    def test_success_captures_stdout_stderr_env_and_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            result = BoundedProcessRunner(timeout_seconds=5).run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import os, pathlib, sys; "
                        "print(os.environ['WBP_TEST_VALUE']); "
                        "print(pathlib.Path.cwd()); "
                        "print('warn', file=sys.stderr)"
                    ),
                ],
                env={**os.environ, "WBP_TEST_VALUE": "runner-ok"},
                cwd=workdir,
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.machine_error_code, PROCESS_OK)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("runner-ok", result.stdout)
        self.assertIn(str(workdir), result.stdout)
        self.assertEqual(result.stderr.strip(), "warn")

    def test_nonzero_exit_is_structured_process_failure(self) -> None:
        result = BoundedProcessRunner(timeout_seconds=5).run(
            [
                sys.executable,
                "-c",
                "import sys; print('bad', file=sys.stderr); sys.exit(7)",
            ],
            env=os.environ,
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.machine_error_code, PROCESS_FAILED)
        self.assertEqual(result.exit_code, 7)
        self.assertEqual(result.stderr.strip(), "bad")

    def test_stdin_text_is_delivered_as_utf8_without_shell(self) -> None:
        result = BoundedProcessRunner(timeout_seconds=5).run(
            [
                sys.executable,
                "-c",
                "import sys; data = sys.stdin.read(); print(data.upper())",
            ],
            env=os.environ,
            stdin_text="hello stdin",
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.machine_error_code, PROCESS_OK)
        self.assertEqual(result.stdout.strip(), "HELLO STDIN")

    def test_missing_binary_returns_process_not_found(self) -> None:
        result = BoundedProcessRunner(timeout_seconds=5).run(
            ["/definitely/missing/wbp-process-runner-binary"],
            env=os.environ,
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.machine_error_code, PROCESS_NOT_FOUND)
        self.assertIsNone(result.exit_code)

    def test_timeout_kills_child_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            child_started = temp_root / "child-started.txt"
            child_survived = temp_root / "child-survived.txt"
            parent_script = (
                "import pathlib, subprocess, sys, time; "
                "started = pathlib.Path(sys.argv[1]); "
                "survived = pathlib.Path(sys.argv[2]); "
                "subprocess.Popen([sys.executable, '-c', "
                "\"import pathlib, sys, time; time.sleep(1.0); "
                "pathlib.Path(sys.argv[1]).write_text('alive')\", str(survived)]); "
                "started.write_text('yes'); "
                "time.sleep(10)"
            )

            result = BoundedProcessRunner(timeout_seconds=0.2).run(
                [sys.executable, "-c", parent_script, child_started, child_survived],
                env=os.environ,
            )
            time.sleep(1.2)

            self.assertTrue(child_started.exists())
            self.assertFalse(child_survived.exists())
            self.assertEqual(result.status, "error")
            self.assertEqual(result.machine_error_code, PROCESS_TIMEOUT)
            self.assertTrue(result.timed_out)

    def test_timeout_with_stdin_remains_structured_timeout(self) -> None:
        result = BoundedProcessRunner(timeout_seconds=0.2).run(
            [
                sys.executable,
                "-c",
                "import sys, time; sys.stdin.read(); time.sleep(10)",
            ],
            env=os.environ,
            stdin_text="prompt\n",
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.machine_error_code, PROCESS_TIMEOUT)
        self.assertTrue(result.timed_out)

    def test_large_stdout_and_stderr_are_capped(self) -> None:
        result = BoundedProcessRunner(
            timeout_seconds=5,
            output_cap_bytes=12,
        ).run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "sys.stdout.write('o' * 40); "
                    "sys.stderr.write('e' * 40)"
                ),
            ],
            env=os.environ,
        )

        self.assertEqual(result.machine_error_code, PROCESS_OK)
        self.assertEqual(result.stdout, "o" * 12)
        self.assertEqual(result.stderr, "e" * 12)
        self.assertTrue(result.stdout_truncated)
        self.assertTrue(result.stderr_truncated)

    def test_passthrough_stdout_and_stderr_are_capped(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        result = BoundedProcessRunner(
            timeout_seconds=5,
            output_cap_bytes=6,
        ).run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "sys.stdout.write('o' * 20); "
                    "sys.stderr.write('e' * 20)"
                ),
            ],
            env=os.environ,
            stdout_passthrough=stdout,
            stderr_passthrough=stderr,
        )

        self.assertEqual(result.machine_error_code, PROCESS_OK)
        self.assertEqual(result.stdout, "o" * 6)
        self.assertEqual(result.stderr, "e" * 6)
        self.assertEqual(stdout.getvalue(), "o" * 6)
        self.assertEqual(stderr.getvalue(), "e" * 6)
        self.assertTrue(result.stdout_truncated)
        self.assertTrue(result.stderr_truncated)

    def test_passthrough_open_grandchild_pipe_is_not_false_green(self) -> None:
        stdout = StringIO()
        script = (
            "import subprocess, sys, time; "
            "print('parent ready', flush=True); "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)']); "
            "sys.exit(0)"
        )

        result = BoundedProcessRunner(
            timeout_seconds=5,
            output_cap_bytes=64,
        ).run(
            [sys.executable, "-c", script],
            env=os.environ,
            stdout_passthrough=stdout,
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.machine_error_code, PROCESS_FAILED)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("parent ready", result.stdout)
        self.assertIn("parent ready", stdout.getvalue())
        self.assertIn("output streams did not close", result.stderr)

    def test_shell_true_is_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            BoundedProcessRunner(timeout_seconds=5).run(
                ["echo", "nope"],
                env=os.environ,
                shell=True,
            )


if __name__ == "__main__":
    unittest.main()
