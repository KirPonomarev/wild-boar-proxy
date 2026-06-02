# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Bounded subprocess execution helpers for owner paths."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence

PROCESS_NOT_FOUND = "PROCESS_NOT_FOUND"
PROCESS_TIMEOUT = "PROCESS_TIMEOUT"
PROCESS_FAILED = "PROCESS_FAILED"
PROCESS_OK = "OK"

DEFAULT_PROCESS_TIMEOUT_SECONDS = 120.0
DEFAULT_OUTPUT_CAP_BYTES = 64 * 1024


@dataclass(frozen=True)
class BoundedProcessResult:
    status: str
    machine_error_code: str
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "machine_error_code": self.machine_error_code,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "timed_out": self.timed_out,
            "duration_seconds": self.duration_seconds,
        }


def _read_capped(handle, cap_bytes: int) -> tuple[str, bool]:
    handle.flush()
    handle.seek(0)
    data = handle.read(cap_bytes + 1)
    truncated = len(data) > cap_bytes
    if truncated:
        data = data[:cap_bytes]
    return data.decode("utf-8", errors="replace"), truncated


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


class BoundedProcessRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_PROCESS_TIMEOUT_SECONDS,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if output_cap_bytes < 0:
            raise ValueError("output_cap_bytes must be non-negative")
        self.timeout_seconds = timeout_seconds
        self.output_cap_bytes = output_cap_bytes

    def run(
        self,
        command: Sequence[str | Path],
        *,
        env: Mapping[str, str],
        cwd: Path | str | None = None,
        stdin_text: str | None = None,
        shell: bool = False,
    ) -> BoundedProcessResult:
        if shell:
            raise ValueError("shell=True is forbidden for bounded process execution")
        argv = [str(item) for item in command]
        if not argv:
            raise ValueError("command must not be empty")

        started = time.monotonic()
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            stdin_file = None
            try:
                stdin = subprocess.DEVNULL
                if stdin_text is not None:
                    stdin_file = tempfile.TemporaryFile()
                    stdin_file.write(stdin_text.encode("utf-8"))
                    stdin_file.seek(0)
                    stdin = stdin_file
                process = subprocess.Popen(
                    argv,
                    stdin=stdin,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=dict(env),
                    cwd=str(cwd) if cwd is not None else None,
                    start_new_session=True,
                    text=False,
                    shell=False,
                )
                if stdin_file is not None:
                    stdin_file.close()
                    stdin_file = None
            except FileNotFoundError as exc:
                return BoundedProcessResult(
                    status="error",
                    machine_error_code=PROCESS_NOT_FOUND,
                    exit_code=None,
                    stdout="",
                    stderr=str(exc),
                    stdout_truncated=False,
                    stderr_truncated=False,
                    timed_out=False,
                    duration_seconds=round(time.monotonic() - started, 3),
                )
            except OSError as exc:
                return BoundedProcessResult(
                    status="error",
                    machine_error_code=PROCESS_FAILED,
                    exit_code=None,
                    stdout="",
                    stderr=str(exc),
                    stdout_truncated=False,
                    stderr_truncated=False,
                    timed_out=False,
                    duration_seconds=round(time.monotonic() - started, 3),
                )
            finally:
                if stdin_file is not None:
                    stdin_file.close()

            timed_out = False
            try:
                process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_process_group(process.pid)
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    pass

            stdout, stdout_truncated = _read_capped(
                stdout_file, self.output_cap_bytes
            )
            stderr, stderr_truncated = _read_capped(
                stderr_file, self.output_cap_bytes
            )
            exit_code = process.returncode
            machine_error_code = (
                PROCESS_TIMEOUT
                if timed_out
                else PROCESS_OK
                if exit_code == 0
                else PROCESS_FAILED
            )
            return BoundedProcessResult(
                status="ok" if machine_error_code == PROCESS_OK else "error",
                machine_error_code=machine_error_code,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                timed_out=timed_out,
                duration_seconds=round(time.monotonic() - started, 3),
            )


def run_bounded_process(
    command: Sequence[str | Path],
    *,
    env: Mapping[str, str],
    cwd: Path | str | None = None,
    stdin_text: str | None = None,
    timeout_seconds: float = DEFAULT_PROCESS_TIMEOUT_SECONDS,
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
) -> BoundedProcessResult:
    return BoundedProcessRunner(
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
    ).run(command, env=env, cwd=cwd, stdin_text=stdin_text)
