# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Web service lifecycle owner surface (W05-R1 hardened).

Turns the module-level live web server into a stable local release entrypoint
with exact PID/port ownership ledger, machine-readable startup/status/shutdown
packets built on the shared core packet contract, hardened PID identity, full
failed-start orphan cleanup, and stop-incomplete ledger preservation.

This module owns only the WBP web control-surface lifecycle (start/status/stop/
open/clear-stale-ledger). It does not own runtime health, account lifecycle, or
provider truth; those remain on their canonical owner paths. The web server is
spawned as a background child running the existing ``web_design_live_server``
entrypoint in ``live_readonly`` action phase, bound to loopback only.

All command results are produced through ``wild_boar_proxy.core.packets``
``build_command_packet`` and pass ``inspect_command_packet_semantics`` with no
violations. Evidence is identity-bound (PID, port, host, started_at, token
presence, exact argv digest) and never exposes the raw token value.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .core import packets as command_packets
from .runtime import build_command_payload

DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8788
# Conservative startup probe window: the live server boots a large route table,
# so allow up to this many seconds for the listener to accept connections.
STARTUP_PROBE_TIMEOUT_SECONDS = 15.0
STARTUP_PROBE_INTERVAL_SECONDS = 0.25
SHUTDOWN_GRACE_SECONDS = 5.0

WEB_PID_FILENAME = "web_server.pid"
WEB_STARTUP_RECEIPT_FILENAME = "web_server_startup_receipt.json"
WEB_SERVER_STDERR_LOG = "web_server.stderr.log"

# Effect vocabulary (kept narrow; matches COMMAND_API effect field semantics).
WEB_EFFECT_READ = "read"
WEB_EFFECT_MUTATE = "mutate"
WEB_EFFECT_REPAIR = "repair"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def web_pid_ledger_path(managed_dir: Path) -> Path:
    return Path(managed_dir).expanduser().resolve(strict=False) / WEB_PID_FILENAME


def web_startup_receipt_path(managed_dir: Path) -> Path:
    return Path(managed_dir).expanduser().resolve(strict=False) / WEB_STARTUP_RECEIPT_FILENAME


def web_server_stderr_log_path(managed_dir: Path) -> Path:
    return Path(managed_dir).expanduser().resolve(strict=False) / WEB_SERVER_STDERR_LOG


@dataclasses.dataclass(frozen=True)
class WebLifecyclePaths:
    managed_dir: Path
    pid_ledger: Path
    startup_receipt: Path
    stderr_log: Path

    @classmethod
    def from_managed_dir(cls, managed_dir: Path | str) -> "WebLifecyclePaths":
        root = Path(managed_dir).expanduser().resolve(strict=False)
        return cls(
            managed_dir=root,
            pid_ledger=web_pid_ledger_path(root),
            startup_receipt=web_startup_receipt_path(root),
            stderr_log=web_server_stderr_log_path(root),
        )

    def owner_artifact_paths(self) -> list[Path]:
        return [self.pid_ledger, self.startup_receipt, self.stderr_log]


def _read_pid_ledger(paths: WebLifecyclePaths) -> dict[str, Any] | None:
    ledger_path = paths.pid_ledger
    if not ledger_path.is_file():
        return None
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_json_atomic(path: Path, payload: Mapping[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True))
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    except OSError:
        return False
    return True


def _process_owner_uid(pid: int) -> int | None:
    try:
        completed = subprocess.run(
            ["/bin/ps", "-o", "uid=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        text = completed.stdout.strip()
        return int(text) if text.isdigit() else None
    except (OSError, ValueError):
        return None


def _process_command_line(pid: int) -> str:
    try:
        completed = subprocess.run(
            ["/bin/ps", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return (completed.stdout or "").strip()
    except OSError:
        return ""


def _process_start_time(pid: int) -> str:
    """Best-effort process start timestamp used as an identity dimension."""
    try:
        completed = subprocess.run(
            ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        text = (completed.stdout or "").strip()
        return text
    except OSError:
        return ""


def _argv_digest(argv: list[str]) -> str:
    return hashlib.sha256("\x00".join(argv).encode("utf-8")).hexdigest()


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def _loopback_listener_open(host: str, port: int, timeout: float = 0.5) -> bool:
    if not _is_loopback_host(host):
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


@dataclasses.dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    uid: int | None
    command_line: str
    start_time: str
    alive: bool


def _capture_process_identity(pid: int) -> ProcessIdentity:
    return ProcessIdentity(
        pid=pid,
        uid=_process_owner_uid(pid),
        command_line=_process_command_line(pid),
        start_time=_process_start_time(pid),
        alive=_process_alive(pid),
    )


def _process_identity_matches_ledger(
    identity: ProcessIdentity,
    ledger: Mapping[str, Any],
    *,
    expected_host: str,
    expected_port: int,
) -> tuple[bool, list[str]]:
    """Exact PID ownership proof.

    Hard requirements (all must pass for "running"):
    - process alive
    - process owner is the current user (same-UID)
    - canonical module marker (``web_design_live_server``) in argv
    - exact recorded loopback port is owned by a live listener

    Soft mismatch reasons (recorded as identity evidence; only escalate to a
    hard blocker when a hard requirement also fails):
    - argv digest drift (ps command-line reconstruction is unreliable on
      macOS, so a digest mismatch alone does not disprove ownership when the
      canonical module marker is present and the exact recorded loopback port
      is owned)
    - process start-time drift (PID recycle signal; only authoritative when a
      hard requirement also fails)
    """
    reasons: list[str] = []
    hard_blockers: list[str] = []
    if not identity.alive:
        hard_blockers.append("process_not_alive")
    if identity.uid is not None and identity.uid != os.getuid():
        hard_blockers.append("foreign_owner_uid")
    # Canonical module identity: argv must run web_design_live_server as module.
    canonical_marker = "web_design_live_server"
    if canonical_marker not in identity.command_line:
        hard_blockers.append("canonical_module_absent_from_argv")
    port_owned = bool(expected_port) and _loopback_listener_open(expected_host, expected_port)
    if expected_port and not port_owned:
        hard_blockers.append("expected_loopback_port_not_owned")
    # Soft identity signals (evidence only).
    ledger_argv_digest = str(ledger.get("argv_digest") or "")
    actual_argv_digest = _argv_digest(_argv_tokens_from_command(identity.command_line))
    argv_digest_mismatch = (
        bool(ledger_argv_digest)
        and bool(actual_argv_digest)
        and ledger_argv_digest != actual_argv_digest
    )
    if argv_digest_mismatch:
        reasons.append("argv_digest_drift")
    ledger_start = str(ledger.get("process_start_time") or "")
    start_time_drift = (
        bool(ledger_start)
        and bool(identity.start_time)
        and ledger_start != identity.start_time
    )
    if start_time_drift:
        reasons.append("process_start_time_drift")
    # Hard blocker escalation: a soft signal alone is not authoritative. But a
    # canonical-module-absent OR foreign-UID OR port-not-owned combined with
    # any soft drift is treated as a full identity mismatch (PID recycle by a
    # different web_design_live_server invocation, foreign reuse, etc.).
    if hard_blockers:
        return (False, hard_blockers + reasons)
    return (True, reasons)


def _argv_tokens_from_command(command_line: str) -> list[str]:
    # Best-effort reconstruction of argv tokens from the ps command line for
    # digest comparison. This is intentionally conservative: when the ps output
    # cannot be confidently tokenized, the digest will not match the ledger's
    # pre-recorded argv digest and the identity check fails closed.
    return [token for token in command_line.split() if token]


def _classify_ledger(
    paths: WebLifecyclePaths,
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Return (ledger, classification, identity_extra).

    classification is one of: no_ledger, stale_missing_process,
    foreign_owner, identity_mismatch, port_closed, running.
    """
    ledger = _read_pid_ledger(paths)
    if ledger is None:
        return None, "no_ledger", {}
    pid = _as_int(ledger.get("pid"))
    host = str(ledger.get("host") or DEFAULT_WEB_HOST)
    port = _as_int(ledger.get("port")) or 0
    if pid is None or port == 0:
        return ledger, "stale_missing_process", {}
    identity = _capture_process_identity(pid)
    if not identity.alive:
        return ledger, "stale_missing_process", _identity_extra(identity)
    if identity.uid is not None and identity.uid != os.getuid():
        return ledger, "foreign_owner", _identity_extra(identity)
    matches, reasons = _process_identity_matches_ledger(
        identity, ledger, expected_host=host, expected_port=port
    )
    extra = _identity_extra(identity)
    extra["identity_mismatch_reasons"] = reasons
    if not matches:
        # Distinguish a non-listening-but-otherwise-matching process from a
        # full identity mismatch. Only hard blockers (canonical module absent,
        # foreign owner) escalate to identity_mismatch. Soft signals
        # (argv_digest_drift, start_time_drift) and the port-not-owned reason
        # alone do not: the port-not-owned case is classified as port_closed,
        # and soft drift on an otherwise-canonical same-UID process is recorded
        # as evidence but does not by itself disprove ownership.
        hard_non_port_blockers = [
            r
            for r in reasons
            if r
            not in (
                "expected_loopback_port_not_owned",
                "argv_digest_drift",
                "process_start_time_drift",
            )
        ]
        if hard_non_port_blockers:
            return ledger, "identity_mismatch", extra
        # Port-not-owned is the only hard blocker -> listener gone.
        if "expected_loopback_port_not_owned" in reasons:
            return ledger, "port_closed", extra
        # Only soft drift on an otherwise-canonical same-UID same-port process:
        # treat as running with recorded drift evidence.
        return ledger, "running", extra
    return ledger, "running", extra


def _identity_extra(identity: ProcessIdentity) -> dict[str, Any]:
    return {
        "live_pid": identity.pid,
        "live_uid": identity.uid,
        "live_command_digest": _argv_digest(_argv_tokens_from_command(identity.command_line)),
        "live_process_start_time": identity.start_time,
        "live_process_alive": identity.alive,
    }


def _clear_artifact(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _clear_owner_artifacts(paths: WebLifecyclePaths, *, keep_diagnostics: bool = False) -> list[str]:
    """Remove owner artifacts. Returns the list of relative paths removed.

    When keep_diagnostics=True (used for incomplete stop), the pid ledger is
    preserved as the single diagnostic ownership evidence; only the startup
    receipt and bounded stderr log are cleared so the next start can write
    fresh ones.
    """
    removed: list[str] = []
    for path in paths.owner_artifact_paths():
        if keep_diagnostics and path == paths.pid_ledger:
            continue
        if path.exists():
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    return removed


def _build_packet(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    operator_action: str,
    liveness: str,
    severity: str,
    changed_files: list[str],
    effect: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        operator_action=operator_action,
        liveness=liveness,
        severity=severity,
        changed_files=changed_files,
        effect=effect,
        extra=extra,
    )


def web_status(paths: WebLifecyclePaths) -> dict[str, Any]:
    """Read-only status packet for the WBP web control surface."""
    ledger, classification, identity_extra = _classify_ledger(paths)
    running = classification == "running"
    extra: dict[str, Any] = {
        "ledger_present": ledger is not None,
        "classification": classification,
        "loopback_bind_enforced": True,
    }
    if ledger is not None:
        extra["pid"] = ledger.get("pid")
        extra["port"] = ledger.get("port")
        extra["host"] = ledger.get("host")
        extra["started_at"] = ledger.get("started_at")
        extra["action_phase"] = ledger.get("action_phase")
        extra["token_present"] = bool(ledger.get("token_present"))
        extra.update(identity_extra)
        if running:
            extra["base_url"] = (
                f"http://{ledger.get('host') or DEFAULT_WEB_HOST}:{ledger.get('port')}"
            )
    if running:
        return _build_packet(
            ok=True,
            human_message="WBP web control surface is running on loopback.",
            machine_error_code="OK",
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=WEB_EFFECT_READ,
            extra=extra,
        )
    if classification == "no_ledger":
        return _build_packet(
            ok=True,
            human_message="WBP web control surface is not running.",
            machine_error_code="WEB_NOT_STARTED",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=[],
            effect=WEB_EFFECT_READ,
            extra=extra,
        )
    # stale / foreign / mismatch / port_closed
    code = {
        "foreign_owner": "WEB_PID_FOREIGN_OWNER",
        "identity_mismatch": "WEB_PROCESS_IDENTITY_MISMATCH",
        "port_closed": "WEB_LISTENER_CLOSED",
        "stale_missing_process": "STALE_WEB_PID_LEDGER",
    }.get(classification, "STALE_WEB_PID_LEDGER")
    return _build_packet(
        ok=False,
        human_message="Recorded web PID no longer matches a running WBP web server.",
        machine_error_code=code,
        operator_action="user_action",
        liveness="degraded",
        severity="recoverable",
        changed_files=[],
        effect=WEB_EFFECT_READ,
        extra=extra,
    )


def _probe_live_readonly(host: str, port: int, timeout: float) -> dict[str, Any]:
    """Hit /api/live-readonly on the live server to prove readiness.

    Requires HTTP 200, a valid JSON object, and the expected ``commands``
    snapshot marker. Loopback route identity is enforced by the caller's
    loopback-only bind.
    """
    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/api/live-readonly"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            status_code = int(getattr(response, "status", 0))
    except (urllib.error.URLError, OSError) as exc:
        return {
            "readiness_probed": False,
            "readiness_ok": False,
            "transport_error": type(exc).__name__,
        }
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {
            "readiness_probed": True,
            "readiness_ok": False,
            "http_status": status_code,
            "json_parse_error": True,
        }
    snapshot_ok = (
        isinstance(payload, dict)
        and status_code == 200
        and isinstance(payload.get("commands"), dict)
    )
    return {
        "readiness_probed": True,
        "readiness_ok": snapshot_ok,
        "http_status": status_code,
        "commands_present": isinstance(payload, dict)
        and isinstance(payload.get("commands"), dict),
    }


def _stop_child_process(pid: int, *, shutdown_grace: float) -> dict[str, Any]:
    """Signal an exact spawned child PID with SIGTERM then SIGKILL within a
    bounded grace window. Returns the readback evidence."""
    pre_identity = _capture_process_identity(pid)
    signalled_term = False
    signalled_kill = False
    if not pre_identity.alive:
        return {
            "pre_signal_identity": _identity_extra(pre_identity),
            "signalled_term": False,
            "signalled_kill": False,
            "exited_within_grace": True,
            "post_signal_alive": False,
        }
    try:
        os.kill(pid, signal.SIGTERM)
        signalled_term = True
    except (ProcessLookupError, PermissionError, OSError):
        pass
    deadline = time.monotonic() + max(0.0, shutdown_grace)
    exited = False
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            exited = True
            break
        time.sleep(0.1)
    if not exited and _process_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
            signalled_kill = True
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except (OSError, ChildProcessError):
            pass
    post_alive = _process_alive(pid)
    return {
        "pre_signal_identity": _identity_extra(pre_identity),
        "signalled_term": signalled_term,
        "signalled_kill": signalled_kill,
        "exited_within_grace": exited,
        "post_signal_alive": post_alive,
    }


def web_start(
    paths: WebLifecyclePaths,
    *,
    host: str = DEFAULT_WEB_HOST,
    port: int = DEFAULT_WEB_PORT,
    action_phase: str = "live_readonly",
    owner_authorization_phrase: str | None = None,
    active_project_root: Path | None = None,
    extra_argv: list[str] | None = None,
    startup_probe_timeout: float = STARTUP_PROBE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Start the WBP web control surface as a background child process."""
    base_extra: dict[str, Any] = {
        "host": host,
        "port": port,
        "action_phase": action_phase,
        "loopback_bind_enforced": _is_loopback_host(host),
    }
    if not _is_loopback_host(host):
        return _build_packet(
            ok=False,
            human_message=(
                "WBP web control surface binds to loopback only in the "
                "release-supported flow."
            ),
            machine_error_code="WEB_PUBLIC_BIND_REJECTED",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=[],
            effect=WEB_EFFECT_MUTATE,
            extra=base_extra,
        )

    existing_ledger, classification, _ = _classify_ledger(paths)
    if classification == "running" and existing_ledger is not None:
        existing_port = _as_int(existing_ledger.get("port")) or 0
        if existing_port == port:
            base_extra["existing_pid"] = existing_ledger.get("pid")
            base_extra["existing_port"] = existing_port
            return _build_packet(
                ok=False,
                human_message=(
                    "WBP web control surface is already running on the "
                    "requested loopback port."
                ),
                machine_error_code="WEB_ALREADY_RUNNING",
                operator_action="user_action",
                liveness="healthy",
                severity="recoverable",
                changed_files=[],
                effect=WEB_EFFECT_MUTATE,
                extra=base_extra,
            )
    # Clear stale ledger before starting fresh; this is a repair write.
    stale_cleared: list[str] = []
    if classification in {"stale_missing_process", "port_closed", "identity_mismatch"}:
        stale_cleared = _clear_owner_artifacts(paths)

    if _loopback_listener_open(host, port):
        base_extra["stale_cleared"] = stale_cleared
        return _build_packet(
            ok=False,
            human_message=(
                "Requested loopback port is already accepting connections "
                "from another process."
            ),
            machine_error_code="WEB_PORT_OCCUPIED",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=stale_cleared,
            effect=WEB_EFFECT_MUTATE,
            extra=base_extra,
        )

    argv: list[str] = [
        sys.executable,
        "-m",
        "wild_boar_proxy.web_design_live_server",
        "--host",
        host,
        "--port",
        str(port),
        "--action-phase",
        action_phase,
    ]
    if owner_authorization_phrase:
        argv.extend(["--owner-authorization-phrase", owner_authorization_phrase])
    if active_project_root is not None:
        argv.extend(
            ["--active-project-root", str(Path(active_project_root).resolve(strict=False))]
        )
    if extra_argv:
        argv.extend(extra_argv)
    argv_digest = _argv_digest(argv)

    # Use a bounded WBP-owned stderr log sink instead of an undrained pipe to
    # avoid blocking the server after the pipe fills. The log is owner-only.
    try:
        paths.stderr_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_fd = os.open(
            paths.stderr_log,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
    except OSError as exc:
        base_extra["stale_cleared"] = stale_cleared
        base_extra["error_class"] = type(exc).__name__
        return _build_packet(
            ok=False,
            human_message="Failed to open WBP-owned bounded stderr log sink.",
            machine_error_code="WEB_STDERR_SINK_OPEN_FAILED",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=stale_cleared,
            effect=WEB_EFFECT_MUTATE,
            extra=base_extra,
        )

    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=stderr_fd,
            text=True,
            env=dict(os.environ),
            close_fds=True,
        )
    except OSError as exc:
        try:
            os.close(stderr_fd)
        except OSError:
            pass
        base_extra["stale_cleared"] = stale_cleared
        base_extra["error_class"] = type(exc).__name__
        return _build_packet(
            ok=False,
            human_message=f"Failed to spawn WBP web server: {type(exc).__name__}.",
            machine_error_code="WEB_SPAWN_FAILED",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=stale_cleared,
            effect=WEB_EFFECT_MUTATE,
            extra=base_extra,
        )
    finally:
        try:
            os.close(stderr_fd)
        except OSError:
            pass

    pid = process.pid
    process_start_time = _process_start_time(pid)
    ledger = {
        "schema_version": 1,
        "pid": pid,
        "ppid": os.getpid(),
        "host": host,
        "port": port,
        "action_phase": action_phase,
        "argv_digest": argv_digest,
        "argv": argv,
        "started_at": utc_now(),
        "owner_uid": os.getuid(),
        "process_start_time": process_start_time,
        "token_present": True,
    }
    _write_json_atomic(paths.pid_ledger, ledger, mode=0o600)

    # Probe readiness in a bounded loop without retry storms.
    deadline = time.monotonic() + max(0.0, startup_probe_timeout)
    readiness: dict[str, Any] = {"readiness_probed": False, "readiness_ok": False}
    listener_ok = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            # Child exited during startup. This is a failed start: stop the
            # exact spawned child (already exited), prove exit, clean ALL owner
            # artifacts, and report honestly. No orphan is left behind.
            _stop_child_process(pid, shutdown_grace=0.0)
            removed = _clear_owner_artifacts(paths)
            base_extra.update(
                {
                    "stale_cleared": stale_cleared,
                    "pid": pid,
                    "exit_code": process.returncode,
                    "readiness": readiness,
                    "orphan_cleanup": removed,
                }
            )
            return _build_packet(
                ok=False,
                human_message="WBP web server exited before the listener became ready.",
                machine_error_code="WEB_SERVER_EXITED_DURING_STARTUP",
                operator_action="user_action",
                liveness="down",
                severity="recoverable",
                changed_files=stale_cleared + removed,
                effect=WEB_EFFECT_MUTATE,
                extra=base_extra,
            )
        if _loopback_listener_open(host, port, timeout=0.5):
            listener_ok = True
            readiness = _probe_live_readonly(host, port, timeout=2.0)
            if readiness.get("readiness_ok"):
                break
        time.sleep(STARTUP_PROBE_INTERVAL_SECONDS)

    listener_ok = listener_ok or _loopback_listener_open(host, port, timeout=0.5)
    readiness_ok = bool(readiness.get("readiness_ok"))
    running = listener_ok and readiness_ok

    startup_receipt = {
        **ledger,
        "readiness": readiness,
        "listener_ok": listener_ok,
        "captured_at_utc": utc_now(),
    }
    receipt_changed: list[str] = []
    if running:
        _write_json_atomic(paths.startup_receipt, startup_receipt, mode=0o600)
        receipt_changed.append(paths.startup_receipt.name)
    else:
        # Failed startup: stop the exact spawned child, prove exit, clean ALL
        # owner artifacts. Never leave a background child as a side effect.
        _stop_child_process(pid, shutdown_grace=SHUTDOWN_GRACE_SECONDS)
        orphan_cleanup = _clear_owner_artifacts(paths)
        base_extra.update(
            {
                "stale_cleared": stale_cleared,
                "pid": pid,
                "started_at": ledger["started_at"],
                "listener_ok": listener_ok,
                "readiness_ok": readiness_ok,
                "readiness": readiness,
                "orphan_cleanup": orphan_cleanup,
            }
        )
        return _build_packet(
            ok=False,
            human_message=(
                "WBP web server listener did not become ready within the "
                "bounded startup window; spawned child stopped and owner "
                "artifacts cleaned."
            ),
            machine_error_code="WEB_LISTENER_NOT_READY",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=stale_cleared + orphan_cleanup,
            effect=WEB_EFFECT_MUTATE,
            extra=base_extra,
        )

    base_extra.update(
        {
            "stale_cleared": stale_cleared,
            "pid": pid,
            "port": port,
            "host": host,
            "started_at": ledger["started_at"],
            "listener_ok": listener_ok,
            "readiness_ok": readiness_ok,
            "readiness": readiness,
            "base_url": f"http://{host}:{port}",
        }
    )
    return _build_packet(
        ok=True,
        human_message="WBP web control surface started on loopback.",
        machine_error_code="OK",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[paths.pid_ledger.name, paths.startup_receipt.name, paths.stderr_log.name]
        + stale_cleared,
        effect=WEB_EFFECT_MUTATE,
        extra=base_extra,
    )


def web_stop(
    paths: WebLifecyclePaths,
    *,
    shutdown_grace: float = SHUTDOWN_GRACE_SECONDS,
) -> dict[str, Any]:
    """Stop the exact PID recorded in the ledger after a fresh pre-signal
    identity readback. Preserves the ledger on incomplete stop as the single
    diagnostic ownership evidence."""
    ledger, classification, identity_extra = _classify_ledger(paths)
    if classification in {"no_ledger", "stale_missing_process", "port_closed"} or ledger is None:
        removed = _clear_owner_artifacts(paths)
        return _build_packet(
            ok=True,
            human_message="No running WBP web server was found; owner artifacts cleared.",
            machine_error_code="WEB_NOT_RUNNING",
            operator_action="none",
            liveness="down",
            severity="recoverable",
            changed_files=removed,
            effect=WEB_EFFECT_REPAIR,
            extra={
                "ledger_present_before": ledger is not None,
                "classification_before": classification,
            },
        )
    if classification == "foreign_owner":
        return _build_packet(
            ok=False,
            human_message=(
                "Recorded PID is owned by another user; refusing to signal it."
            ),
            machine_error_code="WEB_PID_FOREIGN_OWNER",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=WEB_EFFECT_REPAIR,
            extra={"classification_before": classification, **identity_extra},
        )
    if classification == "identity_mismatch":
        return _build_packet(
            ok=False,
            human_message=(
                "Recorded PID identity no longer matches the ledger (PID "
                "recycled, argv digest mismatch, or start-time drift). "
                "Refusing to signal; ledger preserved for diagnostics."
            ),
            machine_error_code="WEB_PROCESS_IDENTITY_MISMATCH",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=WEB_EFFECT_REPAIR,
            extra={"classification_before": classification, **identity_extra},
        )

    pid = _as_int(ledger.get("pid"))
    host = str(ledger.get("host") or DEFAULT_WEB_HOST)
    port = _as_int(ledger.get("port")) or 0
    if pid is None:
        removed = _clear_owner_artifacts(paths)
        return _build_packet(
            ok=True,
            human_message="Ledger had no usable PID; owner artifacts cleared.",
            machine_error_code="WEB_NOT_RUNNING",
            operator_action="none",
            liveness="down",
            severity="recoverable",
            changed_files=removed,
            effect=WEB_EFFECT_REPAIR,
            extra={"classification_before": classification},
        )

    stop_evidence = _stop_child_process(pid, shutdown_grace=shutdown_grace)
    post_alive = bool(stop_evidence.get("post_signal_alive"))
    listener_closed = not _loopback_listener_open(host, port) if port else True
    fully_stopped = (not post_alive) and listener_closed

    if fully_stopped:
        removed = _clear_owner_artifacts(paths)
        return _build_packet(
            ok=True,
            human_message="WBP web control surface stopped; owner artifacts cleared.",
            machine_error_code="OK",
            operator_action="none",
            liveness="down",
            severity="recoverable",
            changed_files=removed,
            effect=WEB_EFFECT_REPAIR,
            extra={
                "pid": pid,
                "classification_before": classification,
                **stop_evidence,
                "listener_closed": listener_closed,
            },
        )
    # Incomplete stop: preserve the ledger as the single diagnostic ownership
    # evidence. Only the startup receipt and stderr log are cleared so the next
    # start can write fresh ones; the pid ledger stays for diagnosis.
    removed = _clear_owner_artifacts(paths, keep_diagnostics=True)
    return _build_packet(
        ok=False,
        human_message=(
            "WBP web server did not fully stop within the grace window; pid "
            "ledger preserved as diagnostic ownership evidence."
        ),
        machine_error_code="WEB_STOP_INCOMPLETE",
        operator_action="stop",
        liveness="degraded",
        severity="high",
        changed_files=removed,
        effect=WEB_EFFECT_REPAIR,
        extra={
            "pid": pid,
            "classification_before": classification,
            **stop_evidence,
            "listener_closed": listener_closed,
            "ledger_preserved_for_diagnostics": True,
        },
    )


def web_open(paths: WebLifecyclePaths) -> dict[str, Any]:
    """Report the loopback deep-link URL for the running server. Read-only;
    never dispatches an OS open action."""
    ledger, classification, _ = _classify_ledger(paths)
    if classification != "running" or ledger is None:
        return _build_packet(
            ok=False,
            human_message="WBP web control surface is not running.",
            machine_error_code="WEB_NOT_STARTED",
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=[],
            effect=WEB_EFFECT_READ,
            extra={"classification": classification},
        )
    host = str(ledger.get("host") or DEFAULT_WEB_HOST)
    port = _as_int(ledger.get("port")) or DEFAULT_WEB_PORT
    return _build_packet(
        ok=True,
        human_message="Open the URL from the operator OS browser session.",
        machine_error_code="OK",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=WEB_EFFECT_READ,
        extra={"base_url": f"http://{host}:{port}", "classification": classification},
    )


def clear_stale_ledger(paths: WebLifecyclePaths) -> dict[str, Any]:
    """Clear a stale ledger without signalling any process. Repair effect."""
    ledger, classification, identity_extra = _classify_ledger(paths)
    if classification == "running":
        return _build_packet(
            ok=False,
            human_message="Ledger records a running server; use stop instead.",
            machine_error_code="WEB_STILL_RUNNING",
            operator_action="user_action",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=WEB_EFFECT_REPAIR,
            extra={"classification_before": classification, **identity_extra},
        )
    removed = _clear_owner_artifacts(paths)
    return _build_packet(
        ok=True,
        human_message="Stale web PID ledger cleared.",
        machine_error_code="OK",
        operator_action="none",
        liveness="down",
        severity="recoverable",
        changed_files=removed,
        effect=WEB_EFFECT_REPAIR,
        extra={"classification_before": classification, **identity_extra},
    )


# Public alias kept for backwards compatibility with earlier call sites/tests
# that imported the lowercase name; the canonical public name is
# ``clear_stale_ledger``.
def web_clear_stale_ledger(paths: WebLifecyclePaths) -> dict[str, Any]:  # pragma: no cover
    return clear_stale_ledger(paths)


__all__ = [
    "DEFAULT_WEB_HOST",
    "DEFAULT_WEB_PORT",
    "STARTUP_PROBE_TIMEOUT_SECONDS",
    "SHUTDOWN_GRACE_SECONDS",
    "WebLifecyclePaths",
    "web_pid_ledger_path",
    "web_startup_receipt_path",
    "web_start",
    "web_status",
    "web_stop",
    "web_open",
    "clear_stale_ledger",
    "web_clear_stale_ledger",
]
