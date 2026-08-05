# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic server-owned one-shot CLI runtime (B09, R5 separation).

Architecture after the R5 production/test separation:

- `OneShotRuntime` is the engine. Every instance carries its own sealed
  configuration (homes root, manifest). There is no module-level mutable
  state, no environment-variable hook, no test-injection API, and no
  runtime admission/grant mechanism anywhere in this package.
- `ProductionOneShotFacade` is the only production entry surface. It is
  built from server-owned constants and is fail-closed: every operational
  method returns `CLI_DISABLED_PENDING_SECURITY_ADMISSION` before any
  filesystem probe, binary resolution, digest, or subprocess. Production
  CLI stays disabled for the whole R5 contour and beyond; enabling it is
  a separate future contour with its own admission evidence.
- Tests construct their own `OneShotRuntime` from `tests/fakes.py` and
  never touch the production facade. Production code never imports tests.

Sandbox truth: every child process spawned by `OneShotRuntime` runs under
a macOS seatbelt profile built by the single production builder
`build_server_owned_sandbox_profile` (`deny default`). If `sandbox-exec`
is unavailable the runtime fails closed with `CLI_UNAVAILABLE_UNSAFE`;
there is no unsandboxed fallback. Secret values never appear in packets.
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

ONE_SHOT_RUNTIME_SCHEMA_VERSION = 2

# Production server-owned homes root. FIXED constant, not overridable by
# environment, config, prompt, or caller.
DEFAULT_HOMES_ROOT = (
    Path.home() / "Library" / "Application Support" / "WildBoarProxy" / "one-shot-homes"
)

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
ONE_SHOT_PATH_VIOLATION = "ONE_SHOT_PATH_VIOLATION"
CLI_DISABLED_PENDING_SECURITY_ADMISSION = "CLI_DISABLED_PENDING_SECURITY_ADMISSION"
CLI_UNAVAILABLE_UNSAFE = "CLI_UNAVAILABLE_UNSAFE"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
KEY_VALUE_LINE_RE = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")


@dataclass(frozen=True)
class OneShotToolManifestEntry:
    """Server-owned description of an invocable CLI tool.

    `binary_name` is a bare executable name resolved through the sterile
    PATH for server-owned entries. Absolute paths are admitted only for
    fake-adapter entries (`server_owned=False`) that tests place into
    their own runtime instances.
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
    """Declared sandbox posture reported in packets.

    Enforcement is honest: `os_enforcement` reflects what the OS actually
    provides (probed), never a simulated claim. Repo write is denied;
    there is no caller-selectable posture in R5.
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


# Server-owned tool manifest. Real provider CLIs are registered only by a
# future admitted contour. An empty server-owned set is the honest state.
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


# Strict allowlist: only these ambient variables may cross into a one-shot
# child (PATH and HOME are always overridden by the runtime).
STERILE_ENV_ALLOWLIST = frozenset({
    "PATH", "HOME", "TMPDIR", "TMP", "TEMP",
    "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES",
    "TERM", "SHELL",
    "SystemRoot", "WINDIR",  # Windows compat (harmless on macOS)
})

# Provider-specific home/runtime variables. They never enter from the
# ambient environment; they cross only as an explicit `provider_env`
# mapping validated by `OneShotRuntime`.
PROVIDER_HOME_ENV_VARS = frozenset({
    "QWEN_HOME", "QWEN_RUNTIME_DIR",
    "KIMI_CODE_HOME",
    "QWEN_PROJECT_ROOT", "KIMI_SNAPSHOT_ROOT",
})


def build_sterile_environment(
    *,
    provider_home: Path | str | None = None,
    provider_env: Mapping[str, str] | None = None,
    keep: Sequence[str] = (),
) -> dict[str, str]:
    """Strict allowlist environment for one-shot children.

    Only explicitly-allowed ambient variables cross the boundary, PATH is
    pinned to the sterile entries, and HOME is NEVER inherited from the
    ambient environment: it is set only from the sealed provider home (the
    runtime substitutes the per-run sandbox cwd when no provider home is
    given). Provider variables come only from the validated `provider_env`
    mapping — never from the ambient environment.
    """
    allow = STERILE_ENV_ALLOWLIST | frozenset(keep)
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in allow and key not in ("PATH", "HOME"):
            env[key] = value
    env["PATH"] = os.pathsep.join(STERILE_PATH_ENTRIES)
    if provider_home is not None:
        env["HOME"] = str(Path(provider_home).resolve())
    for key, value in (provider_env or {}).items():
        env[str(key)] = str(value)
    return env


def env_digest(mapping: Mapping[str, str]) -> str:
    """Content-only digest of the prepared child environment."""
    canonical = json.dumps(
        dict(sorted(mapping.items())), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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


def default_sandbox_profile() -> SandboxProfile:
    """The runtime default: denied repo write, probed OS enforcement."""
    return SandboxProfile(os_enforcement=probe_os_sandbox()["os_enforcement"])


# Seatbelt system read surface required for process startup on macOS.
# Empirically localized in R52: process startup aborts unless the root
# directory itself is readable (`literal "/"`); every allow path embedded
# in a profile must be realpath-resolved because seatbelt matches the
# kernel-resolved path string.
_SANDBOX_SYSTEM_READ_SUBPATHS = (
    "/usr",
    "/bin",
    "/sbin",
    "/System",
    "/Library",
    "/dev",
    "/private/var/db",
    "/private/etc",
    "/etc",
)


def build_server_owned_sandbox_profile(
    *,
    home_dir: Path | str,
    sandbox_cwd: Path | str,
    binary_path: Path | str | None = None,
    read_only_roots: Sequence[Path | str] = (),
) -> str:
    """THE single production seatbelt profile builder (R52).

    Primary defense is `(deny default)` — never a private-path deny list.
    Allow surface:

    - process operations (required for startup on this OS version);
    - read of `/` itself (required by dyld path resolution);
    - read/exec of the immutable system runtime surface;
    - read+exec of the exact resolved binary being launched;
    - read-only access to explicitly admitted read roots (for example an
      immutable snapshot root or a policy-admitted project root);
    - read+write of exactly the sealed provider home and the sandbox cwd
      (all paths realpath-resolved before embedding);
    - `/dev/null` and `/dev/dtracehelper` writes, posix shm.

    No network operations are allowed: the profile is offline by
    construction. A future admitted contour that needs a networked
    provider must extend THIS builder with explicit evidence.
    """
    home_r = Path(home_dir).resolve()
    cwd_r = Path(sandbox_cwd).resolve()
    read_subpaths = " ".join(f'(subpath "{p}")' for p in _SANDBOX_SYSTEM_READ_SUBPATHS)
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow process*)",
        '(allow file-read* (literal "/"))',
        f"(allow file-read* file-map-executable {read_subpaths})",
    ]
    if binary_path is not None:
        binary_r = Path(binary_path).resolve()
        lines.append(
            f'(allow file-read-data file-map-executable (literal "{binary_r}"))'
        )
    for root in read_only_roots:
        root_r = Path(root).resolve()
        lines.append(f'(allow file-read* (subpath "{root_r}"))')
    lines.extend(
        [
            f'(allow file-read* file-write* (subpath "{home_r}") (subpath "{cwd_r}"))',
            '(allow file-write* (literal "/dev/null") (literal "/dev/dtracehelper"))',
            "(allow ipc-posix-shm)",
        ]
    )
    return "\n".join(lines) + "\n"


# Provider env keys whose values double as admitted read-only roots in the
# sandbox profile. The policy layer (per-path admission) stays finer; the
# OS layer only widens read, never write.
_READ_ONLY_PROVIDER_ENV_KEYS = ("QWEN_PROJECT_ROOT", "KIMI_SNAPSHOT_ROOT")


def _resolve_binary(entry: OneShotToolManifestEntry, env: Mapping[str, str]) -> str | None:
    binary = str(entry.binary_name).strip()
    if not binary:
        return None
    if os.path.sep in binary:
        # Absolute paths are admitted only for fake-adapter entries that
        # tests place into their own runtime instances.
        if not entry.server_owned:
            resolved = Path(binary).resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
        return None
    found = shutil.which(binary, path=env.get("PATH", os.pathsep.join(STERILE_PATH_ENTRIES)))
    if not found:
        return None
    return str(Path(found).resolve())


def _read_capped(fh: Any, cap_bytes: int) -> tuple[str, bool]:
    fh.seek(0)
    data = fh.read(cap_bytes + 1)
    truncated = len(data) > cap_bytes
    return data[:cap_bytes].decode("utf-8", errors="replace"), truncated


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


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


class OneShotRuntime:
    """Configured one-shot engine.

    Every instance carries its own sealed configuration. There is no
    module-level mutable state: no globals are read or written, no
    environment hooks exist, and nothing about an instance can be changed
    after construction. Tests build instances from `tests/fakes.py`;
    production surfaces use `ProductionOneShotFacade` instead.
    """

    def __init__(
        self,
        *,
        homes_root: Path | str,
        manifest: Sequence[OneShotToolManifestEntry] = (),
    ) -> None:
        root = Path(homes_root)
        self._homes_root = root
        self._manifest = tuple(manifest)

    @property
    def homes_root(self) -> Path:
        return self._homes_root

    @property
    def manifest(self) -> tuple[OneShotToolManifestEntry, ...]:
        return self._manifest

    def resolve_manifest_entry(self, tool_id: str) -> OneShotToolManifestEntry | None:
        """Resolve a tool id against this instance's manifest.

        Unknown ids fail closed (None)."""
        if not tool_id or not str(tool_id).strip():
            return None
        tool_id = str(tool_id).strip()
        for entry in self._manifest:
            if entry.tool_id == tool_id:
                return entry
        return None

    def _validate_provider_home(self, provider_home: Path | str | None) -> Path | None:
        """A provider home must resolve inside this instance's homes root."""
        if provider_home is None:
            return None
        resolved = Path(provider_home).resolve()
        try:
            resolved.relative_to(self._homes_root.resolve())
        except ValueError:
            raise RuntimeErrorInfo(
                "provider home must resolve inside the sealed homes root.",
                machine_error_code=ONE_SHOT_PATH_VIOLATION,
                operator_action="user_action",
            )
        return resolved

    def _validate_provider_env(
        self, provider_env: Mapping[str, str] | None
    ) -> dict[str, str]:
        """Provider env keys are allowlisted; values must be absolute paths.

        The sandbox profile — not the variable wording — enforces what the
        child may actually touch.
        """
        validated: dict[str, str] = {}
        for key, value in (provider_env or {}).items():
            key = str(key)
            if key not in PROVIDER_HOME_ENV_VARS:
                raise RuntimeErrorInfo(
                    f"provider env key '{key}' is not allowlisted.",
                    machine_error_code=ONE_SHOT_ENV_VIOLATION,
                    operator_action="user_action",
                )
            value = str(value)
            if not value.startswith(os.path.sep):
                raise RuntimeErrorInfo(
                    f"provider env value for '{key}' must be an absolute path.",
                    machine_error_code=ONE_SHOT_ENV_VIOLATION,
                    operator_action="user_action",
                )
            # Canonicalize: seatbelt matches the kernel-resolved path, so
            # symlinked prefixes (/var -> /private/var) must be resolved
            # before the value reaches the child or the sandbox profile.
            validated[key] = os.path.realpath(value)
        return validated

    def _prepare_child_env(
        self,
        *,
        provider_home: Path | str | None,
        provider_env: Mapping[str, str] | None,
    ) -> dict[str, str]:
        home = self._validate_provider_home(provider_home)
        extra = self._validate_provider_env(provider_env)
        return build_sterile_environment(provider_home=home, provider_env=extra)

    def create_provider_home(self, provider_id: str) -> dict[str, Any]:
        """Create an isolated provider home (0700) with a distinct runtime dir.

        The homes root is instance-sealed; there is no per-call override.
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
        root = self._homes_root
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

    def run_sterile_probe(
        self,
        tool_id: str,
        *,
        provider_home: Path | str | None = None,
        timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
    ) -> dict[str, Any]:
        """Version/help probe of a declared tool in a sterile environment.

        The probe child runs under the same deny-default sandbox profile as
        a full run. Returns realpath, bounded digest, version text, and the
        env digest.
        """
        entry = self.resolve_manifest_entry(tool_id)
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
        env = self._prepare_child_env(provider_home=provider_home, provider_env=None)
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
        handle = self.one_shot_cli_handle(
            tool_id,
            args=tuple(entry.version_args),
            provider_home=provider_home,
            output_cap_bytes=output_cap_bytes,
        )
        if isinstance(handle, dict):
            return handle
        probe = handle.wait(timeout_seconds=timeout_seconds)
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
                "env_digest": handle.env_digest,
                "sterile_path": list(STERILE_PATH_ENTRIES),
                "timeout_seconds": timeout_seconds,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def one_shot_cli_handle(
        self,
        tool_id: str,
        *,
        args: Sequence[str] = (),
        stdin_text: str | None = None,
        provider_home: Path | str | None = None,
        provider_env: Mapping[str, str] | None = None,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
    ) -> OneShotCliRunHandle | dict[str, Any]:
        """Spawn a declared tool as a one-shot process group.

        The child environment and sandbox are built from instance-sealed
        configuration only: no caller-provided environment, no
        caller-provided sandbox posture, no caller-provided homes root.
        Every child runs under the deny-default seatbelt profile; without
        `sandbox-exec` the runtime fails closed (`CLI_UNAVAILABLE_UNSAFE`).
        """
        entry = self.resolve_manifest_entry(tool_id)
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
        prepared_env = self._prepare_child_env(
            provider_home=provider_home, provider_env=provider_env
        )
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
        sandbox_exec = shutil.which("sandbox-exec")
        sandbox_cwd = Path(tempfile.mkdtemp(prefix="wbp-sandbox-ro-")).resolve()
        if not sandbox_exec:
            # No sandbox-exec: fail closed. There is no unsandboxed lane.
            shutil.rmtree(sandbox_cwd, ignore_errors=True)
            stdout_file.close()
            stderr_file.close()
            return build_command_payload(
                ok=False,
                human_message=(
                    f"one-shot CLI '{tool_id}' is unsafe: sandbox-exec is "
                    f"required and is not available."
                ),
                machine_error_code=CLI_UNAVAILABLE_UNSAFE,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "tool_id": tool_id,
                    "sandbox": default_sandbox_profile().to_dict(),
                    "reason": "sandbox_exec_absent",
                },
            )
        # HOME is exactly the sealed provider home, or the per-run sandbox
        # cwd when no provider home was given. The ambient user HOME must
        # never become the writable root of a one-shot child.
        if provider_home is not None:
            child_home = Path(prepared_env["HOME"]).resolve()
        else:
            child_home = sandbox_cwd
            prepared_env["HOME"] = str(sandbox_cwd)
        read_only_roots = [
            prepared_env[key]
            for key in _READ_ONLY_PROVIDER_ENV_KEYS
            if key in prepared_env
        ]
        profile_text = build_server_owned_sandbox_profile(
            home_dir=child_home,
            sandbox_cwd=sandbox_cwd,
            binary_path=realpath,
            read_only_roots=read_only_roots,
        )
        sandbox_profile_path = sandbox_cwd / "sandbox.sb"
        sandbox_profile_path.write_text(profile_text, encoding="utf-8")
        run_argv = [
            str(Path(sandbox_exec).resolve()),
            "-f", str(sandbox_profile_path),
            *argv,
        ]
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
                cwd=str(sandbox_cwd),
                start_new_session=True,
                text=False,
                shell=False,
            )
        except OSError as exc:
            stdout_file.close()
            stderr_file.close()
            if stdin_file is not None:
                stdin_file.close()
            shutil.rmtree(sandbox_cwd, ignore_errors=True)
            return build_command_payload(
                ok=False,
                human_message=f"one-shot spawn failed for '{tool_id}': {exc}",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "sandbox": default_sandbox_profile().to_dict()},
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
        self,
        tool_id: str,
        *,
        args: Sequence[str] = (),
        stdin_text: str | None = None,
        provider_home: Path | str | None = None,
        provider_env: Mapping[str, str] | None = None,
        timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
        cancel_after_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Bounded one-shot run built from instance-sealed configuration."""
        handle = self.one_shot_cli_handle(
            tool_id,
            args=args,
            stdin_text=stdin_text,
            provider_home=provider_home,
            provider_env=provider_env,
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
        profile = default_sandbox_profile().to_dict()
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

    def one_shot_auth_session(
        self,
        provider_id: str,
        provider_home: Path | str,
    ) -> dict[str, Any]:
        """Begin a presence-only auth session inside the provider home.

        The provider home must resolve inside this instance's homes root.
        The packet carries session presence and paths, never secret values.
        """
        provider_id = str(provider_id or "").strip()
        home = self._validate_provider_home(provider_home)
        assert home is not None
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

    def one_shot_auth_status(self, provider_home: Path | str) -> dict[str, Any]:
        """Presence-only auth status for a provider home."""
        home = self._validate_provider_home(provider_home)
        assert home is not None
        session_file = home / "auth" / "session.json"
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

    def end_one_shot_auth_session(self, provider_home: Path | str) -> dict[str, Any]:
        """End the auth session by removing its presence marker."""
        home = self._validate_provider_home(provider_home)
        assert home is not None
        session_file = home / "auth" / "session.json"
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


class ProductionOneShotFacade:
    """Sealed production facade for one-shot CLI surfaces.

    R5: production CLI is disabled. There is no runtime grant, no
    admission boolean, no environment hook, and no caller-controlled
    configuration on any operational method. Every method returns
    `CLI_DISABLED_PENDING_SECURITY_ADMISSION` before any provider home
    creation, auth/session creation, filesystem probe, binary resolution,
    digest, version/help execution, subprocess, or snapshot creation.
    """

    def __init__(
        self,
        *,
        homes_root: Path | str = DEFAULT_HOMES_ROOT,
        manifest: Sequence[OneShotToolManifestEntry] = SERVER_OWNED_TOOL_MANIFEST,
    ) -> None:
        # Sealed at construction; never mutated afterwards. Tests may
        # point a throwaway facade at a synthetic root to prove that no
        # filesystem or process side effect ever happens while disabled.
        self._homes_root = Path(homes_root)
        self._manifest = tuple(manifest)

    @property
    def homes_root(self) -> Path:
        return self._homes_root

    def _disabled_packet(self, surface: str, **extra: Any) -> dict[str, Any]:
        payload_extra = {
            "surface": surface,
            "cli_disabled": True,
            "disabled_reason": "pending_security_admission",
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        }
        payload_extra.update(extra)
        return build_command_payload(
            ok=False,
            human_message=(
                f"one-shot CLI surface '{surface}' is disabled pending "
                f"security admission."
            ),
            machine_error_code=CLI_DISABLED_PENDING_SECURITY_ADMISSION,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra=payload_extra,
        )

    def create_home(self, provider_id: str) -> dict[str, Any]:
        return self._disabled_packet("create_home", provider_id=str(provider_id))

    def session(self, provider_id: str) -> dict[str, Any]:
        return self._disabled_packet("session", provider_id=str(provider_id))

    def auth_session(self, provider_id: str) -> dict[str, Any]:
        return self._disabled_packet("auth_session", provider_id=str(provider_id))

    def probe(self, tool_id: str) -> dict[str, Any]:
        return self._disabled_packet("probe", tool_id=str(tool_id))

    def run(self, tool_id: str) -> dict[str, Any]:
        return self._disabled_packet("run", tool_id=str(tool_id))

    def receipt(self) -> dict[str, Any]:
        """Honest read-only facade receipt: no filesystem or process touch."""
        sandbox = probe_os_sandbox()
        return build_command_payload(
            ok=True,
            human_message=(
                "Production one-shot CLI facade is disabled pending security "
                "admission; receipt is declared, not live."
            ),
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "schema_version": ONE_SHOT_RUNTIME_SCHEMA_VERSION,
                "cli_disabled": True,
                "disabled_reason": "pending_security_admission",
                "declared_not_live_verified": True,
                "server_owned_tools": [entry.to_dict() for entry in self._manifest],
                "homes_root": str(self._homes_root),
                "sterile_path": list(STERILE_PATH_ENTRIES),
                "sandbox": sandbox,
                "runtime_grant_available": False,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )


_PRODUCTION_FACADE: ProductionOneShotFacade | None = None
_PRODUCTION_FACADE_LOCK = threading.Lock()


def default_production_facade() -> ProductionOneShotFacade:
    """The singleton production facade (sealed server-owned config)."""
    global _PRODUCTION_FACADE
    with _PRODUCTION_FACADE_LOCK:
        if _PRODUCTION_FACADE is None:
            _PRODUCTION_FACADE = ProductionOneShotFacade()
        return _PRODUCTION_FACADE


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
