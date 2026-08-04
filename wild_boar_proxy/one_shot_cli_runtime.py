# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic server-owned one-shot CLI runtime (B09).

The runtime that provider CLIs (Qwen B10, Kimi B11, GLM B12) build on:
server-owned tool manifest, sterile probes (realpath/version/digest),
scrubbed environments, isolated provider homes, bounded process groups,
sandbox seams, output parsers, cancellation, and presence-only auth
sessions. One-shot sessions are stateless: resume is never supported.

The manifest is server-owned: tool definitions are repo-resident constants,
never operator input. Tests register a fake adapter through the
test-only `WBP_ONE_SHOT_FAKE_MANIFEST` env hook so the full runtime is
exercised against a fake CLI without touching real provider binaries.
Secret values never appear in any packet.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import packets as command_packets
from .runtime import build_command_payload
from .runtime_errors import RuntimeErrorInfo

ONE_SHOT_RUNTIME_SCHEMA_VERSION = 1

# Server-owned one-shot homes root (override only for tests).
HOMES_ROOT_ENV = "WBP_ONE_SHOT_HOMES_ROOT"
DEFAULT_HOMES_ROOT = (
    Path.home() / "Library" / "Application Support" / "WildBoarProxy" / "one-shot-homes"
)

# Test-only fake-adapter manifest hook. Never read in production paths
# unless explicitly set; resolves to a JSON file describing fake tools.
FAKE_MANIFEST_ENV = "WBP_ONE_SHOT_FAKE_MANIFEST"

DEFAULT_PROBE_TIMEOUT_SECONDS = 20.0
DEFAULT_RUN_TIMEOUT_SECONDS = 300.0
DEFAULT_OUTPUT_CAP_BYTES = 64 * 1024
DEFAULT_DIGEST_SIZE_LIMIT = 5_000_000
CANCEL_GRACE_SECONDS = 5.0

# Sterile PATH: system bins only; brew/user bins are not inherited so
# first-launch config from user tooling cannot leak in.
STERILE_PATH_ENTRIES = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")

# Environment keys that must never cross into a one-shot child.
SECRET_ENV_SUFFIXES = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY", "AUTH",
)

ONE_SHOT_NO_RESUME_REASON = "one_shot_sessions_are_stateless"

# Machine error codes.
ONE_SHOT_OK = "OK"
ONE_SHOT_TOOL_UNKNOWN = "ONE_SHOT_TOOL_UNKNOWN"
TOOL_BINARY_NOT_FOUND = "TOOL_BINARY_NOT_FOUND"
ONE_SHOT_PROBE_FAILED = "ONE_SHOT_PROBE_FAILED"
ONE_SHOT_RUN_TIMEOUT = "ONE_SHOT_RUN_TIMEOUT"
ONE_SHOT_RUN_FAILED = "ONE_SHOT_RUN_FAILED"
ONE_SHOT_CANCELLED = "ONE_SHOT_CANCELLED"
ONE_SHOT_ENV_VIOLATION = "ONE_SHOT_ENV_VIOLATION"
ONE_SHOT_SCHEMA_INVALID = "ONE_SHOT_SCHEMA_INVALID"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
KEY_VALUE_LINE_RE = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")


@dataclass(frozen=True)
class OneShotToolManifestEntry:
    """Server-owned description of an invocable CLI tool.

    `binary_name` is a bare executable name resolved through the sterile
    PATH for server-owned entries. Absolute paths are admitted only for
    fake-adapter entries coming from the test manifest hook.
    """

    tool_id: str
    binary_name: str
    display_name: str
    version_args: tuple[str, ...] = ("--version",)
    output_profiles: tuple[str, ...] = ("text",)
    server_owned: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "binary_name": self.binary_name,
            "display_name": self.display_name,
            "version_args": list(self.version_args),
            "output_profiles": list(self.output_profiles),
            "server_owned": self.server_owned,
        }


@dataclass(frozen=True)
class SandboxProfile:
    """Declared sandbox posture for a one-shot run.

    Enforcement is honest: `os_enforcement` reflects what the OS actually
    provides (probed), never a simulated claim. Repo write is denied by
    default; repo read defaults to none (provider stages choose an admitted
    read mode such as an immutable snapshot).
    """

    repo_write: str = "denied"
    repo_read: str = "none"
    home_isolation: str = "isolated_home"
    os_enforcement: str = "declared_not_available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_write": self.repo_write,
            "repo_read": self.repo_read,
            "home_isolation": self.home_isolation,
            "os_enforcement": self.os_enforcement,
        }


@dataclass(frozen=True)
class OneShotCliRunResult:
    status: str
    machine_error_code: str
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    cancelled: bool
    duration_seconds: float
    pid: int | None
    resume_supported: bool = False
    resume_reason: str = ONE_SHOT_NO_RESUME_REASON

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
            "cancelled": self.cancelled,
            "duration_seconds": self.duration_seconds,
            "pid": self.pid,
            "resume_supported": self.resume_supported,
            "resume_reason": self.resume_reason,
        }


# Server-owned tool manifest. Real provider CLIs are registered by the
# provider stages (B10 Qwen, B11 Kimi, B12 GLM). This stage owns the
# mechanism and the fail-closed policy; an empty server-owned set is the
# honest state before provider bindings land.
SERVER_OWNED_TOOL_MANIFEST: tuple[OneShotToolManifestEntry, ...] = ()


# Environment keys that must NEVER cross into a one-shot child. These are
# host/Codex/proxy surfaces unrelated to the sterile probe.
FORBIDDEN_ENV_KEYS = frozenset({
    "CODEX_HOME",
    "WBP_PROFILE_DIR",
    "SSH_AUTH_SOCK",
    "SSH_AGENT_PID",
    "ALL_PROXY", "all_proxy",
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "NO_PROXY", "no_proxy",
    "GNOME_KEYRING_CONTROL",
    "KEYCHAIN",
    "BROWSER",
    "VISUAL", "EDITOR",
})


def is_sensitive_env_key(name: str) -> bool:
    upper = name.upper()
    return any(upper.endswith(suffix) for suffix in SECRET_ENV_SUFFIXES)


def is_forbidden_env_key(name: str) -> bool:
    """Host/Codex/proxy keys that must be scrubbed even if not secret-pattern."""
    return name in FORBIDDEN_ENV_KEYS or name.upper() in FORBIDDEN_ENV_KEYS


def provider_homes_root(*, override: str | None = None) -> Path:
    if override is not None:
        return Path(override).expanduser()
    env_value = os.environ.get(HOMES_ROOT_ENV)
    if env_value:
        return Path(env_value).expanduser()
    return DEFAULT_HOMES_ROOT


def _load_fake_manifest() -> tuple[OneShotToolManifestEntry, ...]:
    """Load the test-only fake-adapter manifest (absent -> empty)."""
    raw_path = os.environ.get(FAKE_MANIFEST_ENV)
    if not raw_path:
        return ()
    path = Path(raw_path).expanduser()
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    entries = []
    for item in payload.get("tools", []):
        try:
            entries.append(
                OneShotToolManifestEntry(
                    tool_id=str(item["tool_id"]),
                    binary_name=str(item["binary_name"]),
                    display_name=str(item.get("display_name", item["tool_id"])),
                    version_args=tuple(str(a) for a in item.get("version_args", ("--version",))),
                    output_profiles=tuple(str(p) for p in item.get("output_profiles", ("text",))),
                    server_owned=False,
                )
            )
        except (KeyError, TypeError):
            continue
    return tuple(entries)


def resolve_manifest_entry(tool_id: str) -> OneShotToolManifestEntry | None:
    """Resolve a tool id against the server-owned manifest, then the
    test-only fake hook. Unknown ids fail closed (None)."""
    if not tool_id or not str(tool_id).strip():
        return None
    tool_id = str(tool_id).strip()
    for entry in SERVER_OWNED_TOOL_MANIFEST:
        if entry.tool_id == tool_id:
            return entry
    for entry in _load_fake_manifest():
        if entry.tool_id == tool_id:
            return entry
    return None


# Strict allowlist: only these env vars cross into a one-shot child.
# Everything else from the ambient environment is dropped.
STERILE_ENV_ALLOWLIST = frozenset({
    "PATH", "HOME", "TMPDIR", "TMP", "TEMP",
    "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES",
    "TERM", "SHELL",
    "SystemRoot", "WINDIR",  # Windows compat (harmless on macOS)
})

# Provider-specific home/runtime variables that are explicitly injected
# by the runtime (not inherited from ambient).
_PROVIDER_HOME_VARS = frozenset({
    "QWEN_HOME", "QWEN_RUNTIME_DIR",
    "KIMI_CODE_HOME",
    "QWEN_PROJECT_ROOT", "KIMI_SNAPSHOT_ROOT",
})


def build_sterile_environment(
    *,
    provider_home: Path | str | None = None,
    keep: Sequence[str] = (),
) -> dict[str, str]:
    """Strict allowlist environment for one-shot children.

    Only explicitly-allowed variables cross the boundary. All ambient
    host/Codex/proxy/cloud variables are dropped by default.
    """
    allow = STERILE_ENV_ALLOWLIST | _PROVIDER_HOME_VARS | frozenset(keep)
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in allow:
            env[key] = value
    env["PATH"] = os.pathsep.join(STERILE_PATH_ENTRIES)
    if provider_home is not None:
        env["HOME"] = str(Path(provider_home))
    return env


def env_digest(env: Mapping[str, str]) -> str:
    """Content-only digest of the prepared child environment."""
    canonical = json.dumps(
        dict(sorted(env.items())), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def create_provider_home(
    provider_id: str,
    *,
    homes_root: Path | str | None = None,
) -> dict[str, Any]:
    """Create an isolated provider home (0700) with a distinct runtime dir.

    Packet never contains secret values.
    """
    provider_id = str(provider_id or "").strip()
    if not provider_id or re.search(r"[^A-Za-z0-9_-]", provider_id):
        return build_command_payload(
            ok=False,
            human_message="provider id is invalid for one-shot home creation.",
            machine_error_code=ONE_SHOT_SCHEMA_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={
                "provider_id": provider_id,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )
    root = provider_homes_root(override=homes_root if homes_root is not None else None)
    if homes_root is not None:
        root = Path(homes_root).expanduser()
    home = root / provider_id
    runtime_dir = home / "runtime"
    created = False
    changed: list[str] = []
    try:
        if not home.exists():
            home.mkdir(parents=True, exist_ok=True)
            created = True
            changed.append(str(home))
        os.chmod(home, 0o700)
        if not runtime_dir.exists():
            runtime_dir.mkdir(parents=True, exist_ok=True)
            changed.append(str(runtime_dir))
        os.chmod(runtime_dir, 0o700)
    except OSError as exc:
        return build_command_payload(
            ok=False,
            human_message=f"provider home creation failed: {exc}",
            machine_error_code=ONE_SHOT_RUN_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=changed,
            exit_code=1,
            extra={
                "provider_id": provider_id,
                "created": created,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )
    return build_command_payload(
        ok=True,
        human_message=f"provider home ready for {provider_id}.",
        machine_error_code=ONE_SHOT_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=changed,
        exit_code=0,
        extra={
            "provider_id": provider_id,
            "home_path": str(home),
            "runtime_dir": str(runtime_dir),
            "mode": "0700",
            "created": created,
            "homes_root": str(root),
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )


def _resolve_binary(entry: OneShotToolManifestEntry, env: Mapping[str, str]) -> str | None:
    binary = str(entry.binary_name).strip()
    if not binary:
        return None
    if os.path.sep in binary:
        # Absolute/adjusted paths admitted only for fake-adapter entries.
        if not entry.server_owned:
            resolved = Path(binary).resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
        return None
    found = shutil.which(binary, path=env.get("PATH", os.pathsep.join(STERILE_PATH_ENTRIES)))
    if not found:
        return None
    return str(Path(found).resolve())


def compute_tool_digest(path: str, *, size_limit: int = DEFAULT_DIGEST_SIZE_LIMIT) -> str:
    """Bounded sha256 of the tool binary."""
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        remaining = size_limit
        while remaining > 0:
            chunk = fh.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            hasher.update(chunk)
            remaining -= len(chunk)
    return hasher.hexdigest()


def probe_os_sandbox() -> dict[str, Any]:
    """Honest OS-level sandbox availability probe (never simulated)."""
    available = shutil.which("sandbox-exec") is not None
    return {
        "os_sandbox_available": available,
        "os_enforcement": "os_sandbox_available" if available else "declared_not_available",
    }


def run_sterile_probe(
    tool_id: str,
    *,
    provider_home: Path | str | None = None,
    timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
) -> dict[str, Any]:
    """Version/help probe of a declared tool in a sterile environment.

    Returns realpath, bounded digest, version text, and the env digest.
    """
    entry = resolve_manifest_entry(tool_id)
    if entry is None:
        return build_command_payload(
            ok=False,
            human_message=f"unknown one-shot tool id '{tool_id}'.",
            machine_error_code=ONE_SHOT_TOOL_UNKNOWN,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": tool_id, "server_owned": True},
        )
    env = build_sterile_environment(provider_home=provider_home)
    realpath = _resolve_binary(entry, env)
    if realpath is None:
        return build_command_payload(
            ok=False,
            human_message=f"tool binary not found for '{tool_id}' in sterile PATH.",
            machine_error_code=TOOL_BINARY_NOT_FOUND,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": tool_id, "binary_name": entry.binary_name},
        )
    try:
        digest = compute_tool_digest(realpath)
    except OSError as exc:
        digest = ""
        return build_command_payload(
            ok=False,
            human_message=f"tool digest failed for '{tool_id}': {exc}",
            machine_error_code=ONE_SHOT_PROBE_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": tool_id, "realpath": realpath},
        )
    probe = _run_bounded(
        [realpath, *entry.version_args],
        env=env,
        stdin_text=None,
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
    )
    ok = probe.machine_error_code == ONE_SHOT_OK and not probe.timed_out
    version_text = probe.stdout.strip().splitlines()[0] if probe.stdout.strip() else ""
    return build_command_payload(
        ok=ok,
        human_message=(
            f"probe ok for '{tool_id}'." if ok else f"probe failed for '{tool_id}'."
        ),
        machine_error_code=probe.machine_error_code,
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        exit_code=probe.exit_code,
        extra={
            "tool_id": tool_id,
            "server_owned": entry.server_owned,
            "realpath": realpath,
            "binary_sha256": digest,
            "version_text": version_text,
            "env_digest": env_digest(env),
            "sterile_path": list(STERILE_PATH_ENTRIES),
            "timeout_seconds": timeout_seconds,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )


def _read_capped(fh: Any, cap_bytes: int) -> tuple[str, bool]:
    fh.seek(0)
    data = fh.read(cap_bytes + 1)
    truncated = len(data) > cap_bytes
    return data[:cap_bytes].decode("utf-8", errors="replace"), truncated


def _run_bounded(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    stdin_text: str | None,
    timeout_seconds: float,
    output_cap_bytes: int,
    cwd: Path | str | None = None,
) -> OneShotCliRunResult:
    """Bounded process-group run (timeout + cap; group kill on timeout)."""
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
                [str(item) for item in argv],
                stdin=stdin,
                stdout=stdout_file,
                stderr=stderr_file,
                env=dict(env),
                cwd=str(cwd) if cwd is not None else None,
                start_new_session=True,
                text=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            return OneShotCliRunResult(
                status="error",
                machine_error_code=TOOL_BINARY_NOT_FOUND,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=False,
                cancelled=False,
                duration_seconds=round(time.monotonic() - started, 3),
                pid=None,
            )
        except OSError as exc:
            return OneShotCliRunResult(
                status="error",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=False,
                cancelled=False,
                duration_seconds=round(time.monotonic() - started, 3),
                pid=None,
            )
        finally:
            if stdin_file is not None:
                stdin_file.close()

        timed_out = False
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_group(process.pid)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

        stdout, stdout_truncated = _read_capped(stdout_file, output_cap_bytes)
        stderr, stderr_truncated = _read_capped(stderr_file, output_cap_bytes)
        exit_code = process.returncode
        machine_error_code = (
            ONE_SHOT_RUN_TIMEOUT
            if timed_out
            else ONE_SHOT_OK
            if exit_code == 0
            else ONE_SHOT_RUN_FAILED
        )
        return OneShotCliRunResult(
            status="ok" if machine_error_code == ONE_SHOT_OK else "error",
            machine_error_code=machine_error_code,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timed_out=timed_out,
            cancelled=False,
            duration_seconds=round(time.monotonic() - started, 3),
            pid=process.pid,
        )


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


class OneShotCliRunHandle:
    """Interactive handle for a running one-shot CLI.

    `cancel()` terminates the whole process group (SIGTERM, grace, SIGKILL);
    `wait()` collects the bounded result. One-shot runs never resume.
    """

    def __init__(
        self,
        process: subprocess.Popen,
        stdout_file: Any,
        stderr_file: Any,
        *,
        started: float,
        output_cap_bytes: int,
        env_digest_value: str,
        tool_id: str,
        sandbox_cwd: Path | None = None,
    ) -> None:
        self._process = process
        self._sandbox_cwd = sandbox_cwd
        self._stdout_file = stdout_file
        self._stderr_file = stderr_file
        self._started = started
        self._output_cap_bytes = output_cap_bytes
        self._env_digest = env_digest_value
        self.tool_id = tool_id
        self.pid = process.pid
        self.cancelled = False
        self._lock = threading.Lock()
        self._result: OneShotCliRunResult | None = None

    @property
    def env_digest(self) -> str:
        return self._env_digest

    def cancel(self, *, grace_seconds: float = CANCEL_GRACE_SECONDS) -> dict[str, Any]:
        """Terminate the whole process group; never just the leader."""
        if self._process.poll() is not None:
            return {"cancelled": False, "reason": "process_already_exited"}
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            return {"cancelled": False, "reason": "process_group_gone"}
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                break
            time.sleep(0.05)
        if self._process.poll() is None:
            _kill_process_group(self.pid)
        with self._lock:
            self.cancelled = True
        return {
            "cancelled": True,
            "pid": self.pid,
            "grace_seconds": grace_seconds,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        }

    def wait(self, timeout_seconds: float | None = None) -> OneShotCliRunResult:
        with self._lock:
            if self._result is not None:
                return self._result
        try:
            self._process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            pass
        stdout, stdout_truncated = _read_capped(self._stdout_file, self._output_cap_bytes)
        stderr, stderr_truncated = _read_capped(self._stderr_file, self._output_cap_bytes)
        exit_code = self._process.returncode
        timed_out = exit_code is None
        machine_error_code = (
            ONE_SHOT_CANCELLED
            if self.cancelled
            else ONE_SHOT_RUN_TIMEOUT
            if timed_out
            else ONE_SHOT_OK
            if exit_code == 0
            else ONE_SHOT_RUN_FAILED
        )
        result = OneShotCliRunResult(
            status="ok" if machine_error_code == ONE_SHOT_OK else "error",
            machine_error_code=machine_error_code,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timed_out=timed_out,
            cancelled=self.cancelled,
            duration_seconds=round(time.monotonic() - self._started, 3),
            pid=self.pid,
        )
        with self._lock:
            self._result = result
            self._stdout_file.close()
            self._stderr_file.close()
            if self._sandbox_cwd is not None:
                try:
                    os.chmod(self._sandbox_cwd, 0o755)
                    shutil.rmtree(self._sandbox_cwd, ignore_errors=True)
                except OSError:
                    pass
        return result


def default_sandbox_profile() -> SandboxProfile:
    """The runtime default: denied repo write, probed OS enforcement."""
    return SandboxProfile(os_enforcement=probe_os_sandbox()["os_enforcement"])


def one_shot_cli_handle(
    tool_id: str,
    *,
    args: Sequence[str] = (),
    stdin_text: str | None = None,
    provider_home: Path | str | None = None,
    sandbox: SandboxProfile | None = None,
    env: Mapping[str, str] | None = None,
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
) -> OneShotCliRunHandle | dict[str, Any]:
    """Spawn a declared tool as a one-shot process group.

    Returns an `OneShotCliRunHandle` on success or an error packet on
    resolution failures (unknown tool / missing binary).
    """
    sandbox = sandbox or default_sandbox_profile()
    entry = resolve_manifest_entry(tool_id)
    if entry is None:
        return build_command_payload(
            ok=False,
            human_message=f"unknown one-shot tool id '{tool_id}'.",
            machine_error_code=ONE_SHOT_TOOL_UNKNOWN,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": tool_id, "server_owned": True},
        )
    if env is not None:
        prepared_env = dict(env)
    else:
        prepared_env = build_sterile_environment(provider_home=provider_home)
    realpath = _resolve_binary(entry, prepared_env)
    if realpath is None:
        return build_command_payload(
            ok=False,
            human_message=f"tool binary not found for '{tool_id}'.",
            machine_error_code=TOOL_BINARY_NOT_FOUND,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": tool_id, "binary_name": entry.binary_name},
        )
    argv = [realpath, *(str(item) for item in args)]
    stdout_file = tempfile.TemporaryFile()
    stderr_file = tempfile.TemporaryFile()
    stdin_file = None
    # P0-1 Sandbox: macOS sandbox-exec profile that DENIES read AND write
    # outside an explicit allowlist. No read-only-cwd fallback — if
    # sandbox-exec is unavailable, CLI is CLI_UNAVAILABLE_UNSAFE.
    sandbox_cwd: Path | None = None
    sandbox_profile_path: Path | None = None
    use_sandbox_exec = False
    if sandbox.repo_write == "denied":
        sandbox_cwd = Path(tempfile.mkdtemp(prefix="wbp-sandbox-ro-"))
        sandbox_exec = shutil.which("sandbox-exec") if entry.server_owned else None
        if not sandbox_exec and entry.server_owned:
            # No sandbox-exec on a server-owned entry: CLI is unsafe.
            sandbox_cwd.rmdir()
            return build_command_payload(
                ok=False,
                human_message=(
                    f"one-shot CLI '{tool_id}' is unsafe: sandbox-exec is "
                    f"required for server-owned entries and is not available."
                ),
                machine_error_code="CLI_UNAVAILABLE_UNSAFE",
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "tool_id": tool_id,
                    "sandbox": sandbox.to_dict(),
                    "reason": "sandbox_exec_absent_for_server_owned_entry",
                },
            )
        if sandbox_exec:
            home_dir = str(Path(prepared_env.get("HOME", sandbox_cwd)))
            codex_home = str(Path.home() / ".codex")
            repo_root = "/Volumes/Work/wild-boar-proxy"
            profiles_root = str(Path.home() / "Library" / "Application Support" / "WildBoarProxy" / "CodexProfiles")
            profile_lines = [
                "(version 1)",
                "(deny default)",
                # Process lifecycle
                "(allow process-exec process-fork process-info* signal)",
                "(allow sysctl-read)",
                # Explicit DENY of protected surfaces (read + write)
                '(deny file-read* (subpath "' + codex_home + '"))',
                '(deny file-write* (subpath "' + codex_home + '"))',
                '(deny file-read* (subpath "' + repo_root + '"))',
                '(deny file-write* (subpath "' + repo_root + '"))',
                '(deny file-read* (subpath "' + profiles_root + '"))',
                '(deny file-write* (subpath "' + profiles_root + '"))',
                # Allowlist: system runtime files needed by /bin/sh
                '(allow file-read* (subpath "/usr/lib"))',
                '(allow file-read* (subpath "/usr/share"))',
                '(allow file-read* (subpath "/lib"))',
                '(allow file-read* (subpath "/bin"))',
                '(allow file-read* (subpath "/sbin"))',
                '(allow file-read* (subpath "/usr/bin"))',
                '(allow file-read* (subpath "/usr/sbin"))',
                '(allow file-read* (subpath "/etc"))',
                '(allow file-read* (subpath "/private/etc"))',
                '(allow file-read* (subpath "/dev"))',
                '(allow file-read* (subpath "' + str(sandbox_cwd) + '"))',
                '(allow file-read* (subpath "' + home_dir + '"))',
                # Write: only sandbox cwd + provider home
                '(allow file-write* (subpath "' + str(sandbox_cwd) + '"))',
                '(allow file-write* (subpath "' + home_dir + '"))',
                # IPC / mach for shell
                "(allow ipc-posix-shm)",
                '(allow mach-lookup (global-name "com.apple.system.logger"))',
                '(allow mach-lookup (global-name "com.apple.cfprefsd.daemon"))',
            ]
            sandbox_profile_path = sandbox_cwd / "sandbox.sb"
            sandbox_profile_path.write_text(
                "\n".join(profile_lines) + "\n", encoding="utf-8"
            )
            use_sandbox_exec = True
        # Fake-adapter entries: no sandbox, no fallback claim
    # Build final argv
    if use_sandbox_exec and sandbox_profile_path is not None:
        run_argv = [
            shutil.which("sandbox-exec") or "/usr/bin/sandbox-exec",
            "-f", str(sandbox_profile_path),
            *argv,
        ]
    else:
        run_argv = argv
    try:
        stdin = subprocess.DEVNULL
        if stdin_text is not None:
            stdin_file = tempfile.TemporaryFile()
            stdin_file.write(stdin_text.encode("utf-8"))
            stdin_file.seek(0)
            stdin = stdin_file
        process = subprocess.Popen(
            run_argv,
            stdin=stdin,
            stdout=stdout_file,
            stderr=stderr_file,
            env=dict(prepared_env),
            cwd=str(sandbox_cwd) if sandbox_cwd is not None else None,
            start_new_session=True,
            text=False,
            shell=False,
        )
    except OSError as exc:
        stdout_file.close()
        stderr_file.close()
        if stdin_file is not None:
            stdin_file.close()
        return build_command_payload(
            ok=False,
            human_message=f"one-shot spawn failed for '{tool_id}': {exc}",
            machine_error_code=ONE_SHOT_RUN_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": tool_id, "sandbox": sandbox.to_dict()},
        )
    finally:
        if stdin_file is not None:
            stdin_file.close()
    return OneShotCliRunHandle(
        process,
        stdout_file,
        stderr_file,
        started=time.monotonic(),
        output_cap_bytes=output_cap_bytes,
        env_digest_value=env_digest(prepared_env),
        tool_id=tool_id,
        sandbox_cwd=sandbox_cwd,
    )


def one_shot_cli_run(
    tool_id: str,
    *,
    args: Sequence[str] = (),
    stdin_text: str | None = None,
    provider_home: Path | str | None = None,
    sandbox: SandboxProfile | None = None,
    timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS,
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
    cancel_after_seconds: float | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Bounded one-shot run with optional deterministic cancellation."""
    handle = one_shot_cli_handle(
        tool_id,
        args=args,
        stdin_text=stdin_text,
        provider_home=provider_home,
        sandbox=sandbox,
        env=env,
        output_cap_bytes=output_cap_bytes,
    )
    if isinstance(handle, dict):
        return handle
    if cancel_after_seconds is not None:
        deadline = time.monotonic() + cancel_after_seconds
        while time.monotonic() < deadline:
            if handle._process.poll() is not None:
                break
            time.sleep(0.05)
        if handle._process.poll() is None:
            handle.cancel()
    result = handle.wait(timeout_seconds=timeout_seconds)
    profile = (sandbox or default_sandbox_profile()).to_dict()
    return build_command_payload(
        ok=result.status == "ok",
        human_message=(
            f"one-shot run '{tool_id}' finished." if result.status == "ok"
            else f"one-shot run '{tool_id}' failed."
        ),
        machine_error_code=result.machine_error_code,
        liveness="healthy",
        severity="info" if result.status == "ok" else "error",
        operator_action="none" if result.status == "ok" else "user_action",
        changed_files=[],
        exit_code=result.exit_code,
        extra={
            "tool_id": tool_id,
            "run": result.to_dict(),
            "sandbox": profile,
            "env_digest": handle.env_digest,
            "timeout_seconds": timeout_seconds,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )


def parse_cli_output(
    text: str,
    *,
    profile: str = "auto",
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
) -> dict[str, Any]:
    """Normalize CLI output without fabricating structure.

    - `text`: ANSI-stripped lines, capped
    - `key_value`: `name=value` lines only; unmatched lines counted honestly
    - `json_lines`: JSON objects per line; mixed content is reported
    - `auto`: detect json-lines, then key-value, else text; the detected
      format is always reported
    """
    profile = str(profile or "auto").strip()
    if profile not in {"auto", "text", "key_value", "json_lines"}:
        raise RuntimeErrorInfo(
            "unknown CLI output profile.",
            machine_error_code="schema_invalid",
            operator_action="user_action",
        )
    cleaned = ANSI_ESCAPE_RE.sub("", text or "")
    capped = cleaned[:output_cap_bytes]
    truncated = len(cleaned) > output_cap_bytes
    lines = [line.rstrip("\r") for line in capped.splitlines()]

    if profile in {"auto", "json_lines"}:
        records: list[dict[str, Any]] = []
        malformed = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except ValueError:
                malformed += 1
        if records or profile == "json_lines":
            detected = "json_lines"
            return {
                "profile": profile,
                "detected_format": detected,
                "records": records,
                "malformed_lines": malformed,
                "line_count": len(lines),
                "truncated": truncated,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            }

    if profile in {"auto", "key_value"}:
        pairs: dict[str, str] = {}
        unmatched = 0
        for line in lines:
            match = KEY_VALUE_LINE_RE.match(line.strip())
            if match:
                pairs[match.group(1)] = match.group(2)
            else:
                unmatched += 1
        if pairs or profile == "key_value":
            detected = "key_value"
            return {
                "profile": profile,
                "detected_format": detected,
                "pairs": pairs,
                "unmatched_lines": unmatched,
                "line_count": len(lines),
                "truncated": truncated,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            }

    return {
        "profile": profile,
        "detected_format": "text",
        "text": "\n".join(lines),
        "line_count": len(lines),
        "truncated": truncated,
        "resume_supported": False,
        "resume_reason": ONE_SHOT_NO_RESUME_REASON,
    }


def one_shot_auth_session(
    provider_id: str,
    provider_home: Path | str,
    *,
    homes_root: Path | str | None = None,
) -> dict[str, Any]:
    """Begin a presence-only auth session inside the provider home.

    The packet carries session presence and paths, never secret values.
    """
    provider_id = str(provider_id or "").strip()
    home = Path(provider_home)
    auth_dir = home / "auth"
    session_id = uuid.uuid4().hex
    try:
        auth_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(auth_dir, 0o700)
        session_file = auth_dir / "session.json"
        payload = {
            "provider_id": provider_id,
            "session_id": session_id,
            "presence_only": True,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        session_file.write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8"
        )
        os.chmod(session_file, 0o600)
    except OSError as exc:
        return build_command_payload(
            ok=False,
            human_message=f"auth session start failed: {exc}",
            machine_error_code=ONE_SHOT_RUN_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"provider_id": provider_id, "session_id": session_id},
        )
    return build_command_payload(
        ok=True,
        human_message=f"auth session started for {provider_id} (presence-only).",
        machine_error_code=ONE_SHOT_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[str(auth_dir), str(session_file)],
        exit_code=0,
        extra={
            "provider_id": provider_id,
            "session_id": session_id,
            "auth_dir": str(auth_dir),
            "presence_only": True,
            "secret_values_exposed": False,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )


def one_shot_auth_status(
    provider_home: Path | str,
) -> dict[str, Any]:
    """Presence-only auth status for a provider home."""
    session_file = Path(provider_home) / "auth" / "session.json"
    present = session_file.is_file()
    return build_command_payload(
        ok=True,
        human_message="auth session present." if present else "no auth session.",
        machine_error_code=ONE_SHOT_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "auth_present": present,
            "auth_dir": str(session_file.parent),
            "presence_only": True,
            "secret_values_exposed": False,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )


def end_one_shot_auth_session(
    provider_home: Path | str,
) -> dict[str, Any]:
    """End the auth session by removing its presence marker."""
    session_file = Path(provider_home) / "auth" / "session.json"
    changed: list[str] = []
    removed = False
    try:
        if session_file.is_file():
            session_file.unlink()
            removed = True
            changed.append(str(session_file))
    except OSError as exc:
        return build_command_payload(
            ok=False,
            human_message=f"auth session end failed: {exc}",
            machine_error_code=ONE_SHOT_RUN_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=changed,
            exit_code=1,
            extra={"removed": removed},
        )
    return build_command_payload(
        ok=True,
        human_message="auth session ended." if removed else "no auth session to end.",
        machine_error_code=ONE_SHOT_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=changed,
        exit_code=0,
        extra={
            "removed": removed,
            "presence_only": True,
            "secret_values_exposed": False,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )


def build_one_shot_runtime_receipt() -> dict[str, Any]:
    """Declared synthetic receipt for the generic runtime.

    Fake-adapter proof is the honest evidence level for B09; real provider
    bindings and probes are B10/B11/B12 scope.
    """
    sandbox = probe_os_sandbox()
    return build_command_payload(
        ok=True,
        human_message="One-shot CLI runtime declared; fake-adapter proof only (B09).",
        machine_error_code="SYNTHETIC_PROVEN",
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "schema_version": ONE_SHOT_RUNTIME_SCHEMA_VERSION,
            "declared_not_live_verified": True,
            "server_owned_tools": [entry.to_dict() for entry in SERVER_OWNED_TOOL_MANIFEST],
            "homes_root": str(provider_homes_root()),
            "sterile_path": list(STERILE_PATH_ENTRIES),
            "sandbox": sandbox,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        },
    )
