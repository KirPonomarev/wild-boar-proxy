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
import threading
import time
from typing import Any, Mapping, Sequence, TextIO

PROCESS_NOT_FOUND = "PROCESS_NOT_FOUND"
PROCESS_TIMEOUT = "PROCESS_TIMEOUT"
PROCESS_FAILED = "PROCESS_FAILED"
PROCESS_OK = "OK"

DEFAULT_PROCESS_TIMEOUT_SECONDS = 120.0
DEFAULT_OUTPUT_CAP_BYTES = 64 * 1024
PIPE_DRAIN_TIMEOUT_SECONDS = 1.0


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


@dataclass(frozen=True)
class DetachedProcessStartResult:
    status: str
    machine_error_code: str
    pid: int | None
    launch_observed: bool
    error: str
    duration_seconds: float
    process_observed_running: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "machine_error_code": self.machine_error_code,
            "pid": self.pid,
            "launch_observed": self.launch_observed,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "process_observed_running": self.process_observed_running,
        }


@dataclass(frozen=True)
class DetachedProcessHandle:
    _process: Any

    @property
    def pid(self) -> int:
        return int(getattr(self._process, "pid", 0) or 0)

    def poll(self) -> int | None:
        return self._process.poll()


@dataclass(frozen=True)
class ObservableDetachedProcessStartResult:
    status: str
    machine_error_code: str
    handle: DetachedProcessHandle | None
    error: str
    duration_seconds: float

    @property
    def pid(self) -> int | None:
        if self.handle is None:
            return None
        return self.handle.pid

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "machine_error_code": self.machine_error_code,
            "pid": self.pid,
            "launch_observed": self.handle is not None,
            "error": self.error,
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


def _read_pipe_capped(
    handle,
    cap_bytes: int,
    passthrough: TextIO | None,
) -> tuple[str, bool]:
    captured = bytearray()
    truncated = False
    read_chunk = getattr(handle, "read1", handle.read)
    while True:
        # read1() preserves already-available output even when a descendant keeps
        # the pipe open; read() can block waiting for EOF or a full buffer.
        chunk = read_chunk(8192)
        if not chunk:
            break
        remaining = max(0, cap_bytes - len(captured))
        if remaining:
            visible = chunk[:remaining]
            captured.extend(visible)
            if passthrough is not None:
                passthrough.write(visible.decode("utf-8", errors="replace"))
                passthrough.flush()
        if len(chunk) > remaining:
            truncated = True
    return captured.decode("utf-8", errors="replace"), truncated


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def start_detached_process(
    command: Sequence[str | Path],
    *,
    env: Mapping[str, str],
    cwd: Path | str | None = None,
    stdout: Any = subprocess.DEVNULL,
    stderr: Any = subprocess.DEVNULL,
    text: bool = False,
    shell: bool = False,
    observe_after_seconds: float | None = None,
) -> DetachedProcessStartResult:
    if shell:
        raise ValueError("shell=True is forbidden for detached process execution")
    if observe_after_seconds is not None and observe_after_seconds < 0:
        raise ValueError("observe_after_seconds must be non-negative")
    argv = [str(item) for item in command]
    if not argv:
        raise ValueError("command must not be empty")

    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env=dict(env),
            cwd=str(cwd) if cwd is not None else None,
            start_new_session=True,
            text=text,
            shell=False,
        )
    except FileNotFoundError as exc:
        return DetachedProcessStartResult(
            status="error",
            machine_error_code=PROCESS_NOT_FOUND,
            pid=None,
            launch_observed=False,
            error=str(exc),
            duration_seconds=round(time.monotonic() - started, 3),
        )
    except OSError as exc:
        return DetachedProcessStartResult(
            status="error",
            machine_error_code=PROCESS_FAILED,
            pid=None,
            launch_observed=False,
            error=str(exc),
            duration_seconds=round(time.monotonic() - started, 3),
        )

    pid = int(getattr(process, "pid", 0) or 0)
    if pid <= 0:
        return DetachedProcessStartResult(
            status="error",
            machine_error_code=PROCESS_FAILED,
            pid=None,
            launch_observed=False,
            error="detached process started without a valid pid",
            duration_seconds=round(time.monotonic() - started, 3),
        )
    process_observed_running: bool | None = None
    if observe_after_seconds is not None:
        if observe_after_seconds:
            time.sleep(observe_after_seconds)
        process_observed_running = process.poll() is None
    return DetachedProcessStartResult(
        status="ok",
        machine_error_code=PROCESS_OK,
        pid=pid,
        launch_observed=True,
        error="",
        duration_seconds=round(time.monotonic() - started, 3),
        process_observed_running=process_observed_running,
    )


def start_observable_detached_process(
    command: Sequence[str | Path],
    *,
    env: Mapping[str, str],
    cwd: Path | str | None = None,
    stdout: Any = subprocess.DEVNULL,
    stderr: Any = subprocess.DEVNULL,
    text: bool = False,
    shell: bool = False,
) -> ObservableDetachedProcessStartResult:
    if shell:
        raise ValueError("shell=True is forbidden for detached process execution")
    argv = [str(item) for item in command]
    if not argv:
        raise ValueError("command must not be empty")

    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env=dict(env),
            cwd=str(cwd) if cwd is not None else None,
            start_new_session=True,
            text=text,
            shell=False,
        )
    except FileNotFoundError as exc:
        return ObservableDetachedProcessStartResult(
            status="error",
            machine_error_code=PROCESS_NOT_FOUND,
            handle=None,
            error=str(exc),
            duration_seconds=round(time.monotonic() - started, 3),
        )
    except OSError as exc:
        return ObservableDetachedProcessStartResult(
            status="error",
            machine_error_code=PROCESS_FAILED,
            handle=None,
            error=str(exc),
            duration_seconds=round(time.monotonic() - started, 3),
        )

    handle = DetachedProcessHandle(process)
    if handle.pid <= 0:
        return ObservableDetachedProcessStartResult(
            status="error",
            machine_error_code=PROCESS_FAILED,
            handle=None,
            error="detached process started without a valid pid",
            duration_seconds=round(time.monotonic() - started, 3),
        )
    return ObservableDetachedProcessStartResult(
        status="ok",
        machine_error_code=PROCESS_OK,
        handle=handle,
        error="",
        duration_seconds=round(time.monotonic() - started, 3),
    )


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
        stdout_passthrough: TextIO | None = None,
        stderr_passthrough: TextIO | None = None,
        shell: bool = False,
    ) -> BoundedProcessResult:
        if shell:
            raise ValueError("shell=True is forbidden for bounded process execution")
        argv = [str(item) for item in command]
        if not argv:
            raise ValueError("command must not be empty")

        started = time.monotonic()
        if stdout_passthrough is not None or stderr_passthrough is not None:
            return self._run_with_pipe_passthrough(
                argv,
                env=env,
                cwd=cwd,
                stdin_text=stdin_text,
                stdout_passthrough=stdout_passthrough,
                stderr_passthrough=stderr_passthrough,
                started=started,
            )

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

    def _run_with_pipe_passthrough(
        self,
        argv: list[str],
        *,
        env: Mapping[str, str],
        cwd: Path | str | None,
        stdin_text: str | None,
        stdout_passthrough: TextIO | None,
        stderr_passthrough: TextIO | None,
        started: float,
    ) -> BoundedProcessResult:
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
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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

        stdout_result: dict[str, object] = {"text": "", "truncated": False}
        stderr_result: dict[str, object] = {"text": "", "truncated": False}

        def read_stdout() -> None:
            try:
                assert process.stdout is not None
                text, truncated = _read_pipe_capped(
                    process.stdout,
                    self.output_cap_bytes,
                    stdout_passthrough,
                )
                stdout_result["text"] = text
                stdout_result["truncated"] = truncated
            except (OSError, ValueError) as exc:
                stdout_result["text"] = str(stdout_result["text"])
                stdout_result["truncated"] = True
                stdout_result["error"] = str(exc)

        def read_stderr() -> None:
            try:
                assert process.stderr is not None
                text, truncated = _read_pipe_capped(
                    process.stderr,
                    self.output_cap_bytes,
                    stderr_passthrough,
                )
                stderr_result["text"] = text
                stderr_result["truncated"] = truncated
            except (OSError, ValueError) as exc:
                stderr_result["text"] = str(stderr_result["text"])
                stderr_result["truncated"] = True
                stderr_result["error"] = str(exc)

        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

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

        stdout_thread.join(timeout=PIPE_DRAIN_TIMEOUT_SECONDS)
        stderr_thread.join(timeout=PIPE_DRAIN_TIMEOUT_SECONDS)
        stream_incomplete = stdout_thread.is_alive() or stderr_thread.is_alive()
        if stream_incomplete:
            _kill_process_group(process.pid)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            stdout_thread.join(timeout=PIPE_DRAIN_TIMEOUT_SECONDS)
            stderr_thread.join(timeout=PIPE_DRAIN_TIMEOUT_SECONDS)
        exit_code = process.returncode
        machine_error_code = (
            PROCESS_TIMEOUT
            if timed_out
            else PROCESS_FAILED
            if stream_incomplete
            else PROCESS_OK
            if exit_code == 0
            else PROCESS_FAILED
        )
        stderr_text = str(stderr_result["text"])
        if stream_incomplete:
            if stderr_text and not stderr_text.endswith("\n"):
                stderr_text += "\n"
            stderr_text += "process output streams did not close before bounded drain completed"
        return BoundedProcessResult(
            status="ok" if machine_error_code == PROCESS_OK else "error",
            machine_error_code=machine_error_code,
            exit_code=exit_code,
            stdout=str(stdout_result["text"]),
            stderr=stderr_text,
            stdout_truncated=bool(stdout_result["truncated"]),
            stderr_truncated=bool(stderr_result["truncated"]),
            timed_out=timed_out,
            duration_seconds=round(time.monotonic() - started, 3),
        )


def run_bounded_process(
    command: Sequence[str | Path],
    *,
    env: Mapping[str, str],
    cwd: Path | str | None = None,
    stdin_text: str | None = None,
    stdout_passthrough: TextIO | None = None,
    stderr_passthrough: TextIO | None = None,
    timeout_seconds: float = DEFAULT_PROCESS_TIMEOUT_SECONDS,
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
) -> BoundedProcessResult:
    return BoundedProcessRunner(
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
    ).run(
        command,
        env=env,
        cwd=cwd,
        stdin_text=stdin_text,
        stdout_passthrough=stdout_passthrough,
        stderr_passthrough=stderr_passthrough,
    )
