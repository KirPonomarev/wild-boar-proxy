# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Web service lifecycle owner surface.

Turns the module-level live web server into a stable local release entrypoint
with exact PID/port ownership ledger, machine-readable startup/status/shutdown
packets, and stale-pid handling.

This module owns only the WBP web control-surface lifecycle (start/status/stop/
open). It does not own runtime health, account lifecycle, or provider truth;
those remain on their canonical owner paths. The web server itself is spawned
as a background child running the existing ``web_design_live_server`` entrypoint
in ``live_readonly`` action phase, bound to loopback only.

All commands emit a single strict-JSON packet on stdout when ``--json`` is
passed. Evidence is identity-bound (PID, port, host, started_at, token
presence) and never exposes the raw token value.
"""

from __future__ import annotations

import dataclasses
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

DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8788
# Conservative startup probe window: the live server boots a large route table,
# so allow up to this many seconds for the listener to accept connections.
STARTUP_PROBE_TIMEOUT_SECONDS = 15.0
STARTUP_PROBE_INTERVAL_SECONDS = 0.25
SHUTDOWN_GRACE_SECONDS = 5.0

WEB_PID_FILENAME = "web_server.pid"
WEB_STARTUP_RECEIPT_FILENAME = "web_server_startup_receipt.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def web_pid_ledger_path(managed_dir: Path) -> Path:
    return Path(managed_dir).expanduser().resolve(strict=False) / WEB_PID_FILENAME


def web_startup_receipt_path(managed_dir: Path) -> Path:
    return Path(managed_dir).expanduser().resolve(strict=False) / WEB_STARTUP_RECEIPT_FILENAME


@dataclasses.dataclass(frozen=True)
class WebLifecyclePaths:
    managed_dir: Path
    pid_ledger: Path
    startup_receipt: Path

    @classmethod
    def from_managed_dir(cls, managed_dir: Path | str) -> "WebLifecyclePaths":
        root = Path(managed_dir).expanduser().resolve(strict=False)
        return cls(
            managed_dir=root,
            pid_ledger=web_pid_ledger_path(root),
            startup_receipt=web_startup_receipt_path(root),
        )


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


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _process_alive(pid: int) -> bool:
    """Best-effort check that a PID belongs to a live process."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user; treat as not-ours.
        return False
    except OSError:
        return False
    return True


def _process_owner(pid: int) -> int | None:
    try:
        return os.stat(f"/proc/{pid}").st_uid if Path(f"/proc/{pid}").exists() else None
    except OSError:
        # On macOS there is no /proc; fall back to best-effort ps parsing.
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


def _process_command_digest(pid: int) -> str:
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


def _loopback_listener_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Probe whether a loopback TCP listener is accepting connections."""
    if not _is_loopback_host(host):
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def _classify_running_ledger(
    paths: WebLifecyclePaths,
) -> tuple[dict[str, Any] | None, str]:
    """Return (ledger, classification) where classification is one of:
    no_ledger, stale_missing_process, stale_port_closed,
    foreign_owner, running.
    """
    ledger = _read_pid_ledger(paths)
    if ledger is None:
        return None, "no_ledger"
    pid = _as_int(ledger.get("pid"))
    host = str(ledger.get("host") or DEFAULT_WEB_HOST)
    port = _as_int(ledger.get("port")) or 0
    expected_argv_digest = str(ledger.get("argv_digest") or "")
    if pid is None or port == 0:
        return ledger, "stale_missing_process"
    if not _process_alive(pid):
        return ledger, "stale_missing_process"
    # Ownership guard: the running process must be owned by the current user
    # and its command line must carry the WBP web-server marker.
    owner = _process_owner(pid)
    if owner is not None and owner != os.getuid():
        return ledger, "foreign_owner"
    command = _process_command_digest(pid)
    if "web_design_live_server" not in command and expected_argv_digest not in command:
        # PID was reused by a non-WBP process.
        return ledger, "stale_missing_process"
    if not _loopback_listener_open(host, port):
        return ledger, "stale_port_closed"
    return ledger, "running"


def _clear_ledger(paths: WebLifecyclePaths) -> None:
    for path in (paths.pid_ledger, paths.startup_receipt):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _base_packet(paths: WebLifecyclePaths, kind: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": kind,
        "captured_at_utc": _utc_now(),
        "managed_dir": str(paths.managed_dir),
        "exit_code": 0,
    }


def _mark_failed(packet: dict[str, Any]) -> dict[str, Any]:
    """Set exit_code to 1 for any non-OK / rejected / blocked / failed packet."""
    status = str(packet.get("status") or "").lower()
    if status in {"rejected", "blocked", "failed"}:
        packet["exit_code"] = 1
    return packet


def _argv_digest(argv: list[str]) -> str:
    import hashlib

    return hashlib.sha256("\x00".join(argv).encode("utf-8")).hexdigest()


def web_status(paths: WebLifecyclePaths) -> dict[str, Any]:
    """Read-only status packet for the WBP web control surface."""
    ledger, classification = _classify_running_ledger(paths)
    packet = _base_packet(paths, "wbp_web_lifecycle_status")
    packet.update(
        {
            "ledger_present": ledger is not None,
            "classification": classification,
            "listener_ok": classification == "running",
        }
    )
    if ledger is not None:
        packet["pid"] = ledger.get("pid")
        packet["port"] = ledger.get("port")
        packet["host"] = ledger.get("host")
        packet["started_at"] = ledger.get("started_at")
        packet["action_phase"] = ledger.get("action_phase")
        packet["token_present"] = bool(ledger.get("token_present"))
        if classification == "running":
            base_url = f"http://{ledger.get('host') or DEFAULT_WEB_HOST}:{ledger.get('port')}"
            packet["base_url"] = base_url
    if classification in {
        "stale_missing_process",
        "stale_port_closed",
        "foreign_owner",
    }:
        packet["machine_error_code"] = "STALE_WEB_PID_LEDGER"
        packet["human_message"] = (
            "Recorded web PID no longer matches a running WBP web server."
        )
        packet["next_action"] = "run_web_start_or_stop_to_clear_ledger"
    elif classification == "running":
        packet["machine_error_code"] = "OK"
        packet["human_message"] = "WBP web control surface is running on loopback."
        packet["next_action"] = "none"
    else:
        packet["machine_error_code"] = "WEB_NOT_STARTED"
        packet["human_message"] = "WBP web control surface is not running."
        packet["next_action"] = "run_web_start"
    return packet


def _probe_live_readonly(host: str, port: int, timeout: float) -> dict[str, Any]:
    """Hit /api/live-readonly on the live server to prove readiness.

    The live-readonly endpoint returns a command snapshot (not a status:ok
    packet), so readiness is proven by a successful HTTP 200 with a JSON body
    that carries a ``commands`` snapshot. The listener-accepts-connections
    check already proves the socket is bound; this probe proves the HTTP
    route table is wired and answering.
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
    """Start the WBP web control surface as a background child process.

    Fails closed if the ledger already records a running server on the same
    port, if the requested host is not loopback, or if the listener never
    becomes ready within the probe window.
    """
    packet = _base_packet(paths, "wbp_web_lifecycle_start")
    packet.update(
        {
            "host": host,
            "port": port,
            "action_phase": action_phase,
            "loopback_bind_enforced": _is_loopback_host(host),
        }
    )
    if not _is_loopback_host(host):
        packet.update(
            {
                "status": "rejected",
                "machine_error_code": "WEB_PUBLIC_BIND_REJECTED",
                "human_message": (
                    "WBP web control surface binds to loopback only in the "
                    "release-supported flow."
                ),
                "next_action": "use_loopback_host",
            }
        )
        return packet

    # Refuse to clobber a genuinely running server.
    existing_ledger, classification = _classify_running_ledger(paths)
    if classification == "running" and existing_ledger is not None:
        existing_port = _as_int(existing_ledger.get("port")) or 0
        if existing_port == port:
            packet.update(
                {
                    "status": "rejected",
                    "machine_error_code": "WEB_ALREADY_RUNNING",
                    "human_message": (
                        "WBP web control surface is already running on the "
                        "requested loopback port."
                    ),
                    "existing_pid": existing_ledger.get("pid"),
                    "existing_port": existing_port,
                    "next_action": "run_web_status_or_stop_first",
                }
            )
            return packet
    # Clear any stale ledger before starting fresh.
    if classification in {"stale_missing_process", "stale_port_closed"}:
        _clear_ledger(paths)

    # Refuse to grab a port already owned by a foreign listener.
    if _loopback_listener_open(host, port):
        packet.update(
            {
                "status": "blocked",
                "machine_error_code": "WEB_PORT_OCCUPIED",
                "human_message": (
                    "Requested loopback port is already accepting connections "
                    "from another process."
                ),
                "next_action": "choose_another_loopback_port",
            }
        )
        return packet

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

    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ),
        )
    except OSError as exc:
        packet.update(
            {
                "status": "failed",
                "machine_error_code": "WEB_SPAWN_FAILED",
                "human_message": f"Failed to spawn WBP web server: {type(exc).__name__}.",
                "error_class": type(exc).__name__,
                "next_action": "diagnose_python_environment",
            }
        )
        return packet

    argv_digest = _argv_digest(argv)
    ledger = {
        "schema_version": 1,
        "pid": process.pid,
        "ppid": os.getpid(),
        "host": host,
        "port": port,
        "action_phase": action_phase,
        "argv_digest": argv_digest,
        "started_at": _utc_now(),
        "owner_uid": os.getuid(),
        "token_present": True,
    }
    _write_json_atomic(paths.pid_ledger, ledger)

    # Probe readiness in a bounded loop without retry storms.
    deadline = time.monotonic() + max(0.0, startup_probe_timeout)
    readiness: dict[str, Any] = {"readiness_probed": False, "readiness_ok": False}
    while time.monotonic() < deadline:
        if process.poll() is not None:
            # Child exited during startup; capture stderr.
            stderr_tail = ""
            try:
                if process.stderr is not None:
                    stderr_tail = (process.stderr.read() or "")[-2000:]
            except OSError:
                pass
            _clear_ledger(paths)
            packet.update(
                {
                    "status": "failed",
                    "machine_error_code": "WEB_SERVER_EXITED_DURING_STARTUP",
                    "human_message": (
                        "WBP web server exited before the listener became ready."
                    ),
                    "exit_code": process.returncode,
                    "stderr_tail_digest": _argv_digest([stderr_tail]),
                    "next_action": "diagnose_web_server_startup",
                }
            )
            return packet
        if _loopback_listener_open(host, port, timeout=0.5):
            readiness = _probe_live_readonly(host, port, timeout=2.0)
            if readiness.get("readiness_ok"):
                break
        time.sleep(STARTUP_PROBE_INTERVAL_SECONDS)

    startup_receipt = {
        **ledger,
        "readiness": readiness,
        "listener_ok": _loopback_listener_open(host, port, timeout=0.5),
        "captured_at_utc": _utc_now(),
    }
    _write_json_atomic(paths.startup_receipt, startup_receipt)

    listener_ok = bool(startup_receipt["listener_ok"])
    readiness_ok = bool(readiness.get("readiness_ok"))
    running = listener_ok and readiness_ok
    packet.update(
        {
            "status": "ok" if running else "blocked",
            "machine_error_code": "OK" if running else "WEB_LISTENER_NOT_READY",
            "pid": process.pid,
            "port": port,
            "host": host,
            "started_at": ledger["started_at"],
            "listener_ok": listener_ok,
            "readiness_ok": readiness_ok,
            "readiness": readiness,
            "base_url": f"http://{host}:{port}" if running else None,
            "next_action": "none" if running else "run_web_status_or_stop",
        }
    )
    return packet


def web_stop(
    paths: WebLifecyclePaths,
    *,
    shutdown_grace: float = SHUTDOWN_GRACE_SECONDS,
) -> dict[str, Any]:
    """Stop the exact PID recorded in the ledger, then read back."""
    packet = _base_packet(paths, "wbp_web_lifecycle_stop")
    ledger, classification = _classify_running_ledger(paths)
    if ledger is None or classification in {
        "no_ledger",
        "stale_missing_process",
        "stale_port_closed",
    }:
        _clear_ledger(paths)
        packet.update(
            {
                "status": "ok",
                "machine_error_code": "WEB_NOT_RUNNING",
                "human_message": "No running WBP web server was found; ledger cleared.",
                "ledger_present_before": ledger is not None,
                "next_action": "none",
            }
        )
        return packet
    if classification == "foreign_owner":
        packet.update(
            {
                "status": "rejected",
                "machine_error_code": "WEB_PID_FOREIGN_OWNER",
                "human_message": (
                    "Recorded PID is owned by another user; refusing to signal it."
                ),
                "next_action": "diagnose_web_pid_owner",
            }
        )
        return packet

    pid = _as_int(ledger.get("pid"))
    if pid is None:
        _clear_ledger(paths)
        packet.update(
            {
                "status": "ok",
                "machine_error_code": "WEB_NOT_RUNNING",
                "human_message": "Ledger had no usable PID; cleared.",
                "next_action": "none",
            }
        )
        return packet

    host = str(ledger.get("host") or DEFAULT_WEB_HOST)
    port = _as_int(ledger.get("port")) or 0

    # Pre-signal identity readback for the ledger.
    pre_command = _process_command_digest(pid)
    signalled = False
    try:
        os.kill(pid, signal.SIGTERM)
        signalled = True
    except ProcessLookupError:
        signalled = False
    except PermissionError:
        packet.update(
            {
                "status": "rejected",
                "machine_error_code": "WEB_SIGNAL_PERMISSION_DENIED",
                "human_message": "Not allowed to signal the recorded PID.",
                "next_action": "diagnose_web_pid_owner",
            }
        )
        return packet

    deadline = time.monotonic() + max(0.0, shutdown_grace)
    exited = False
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            exited = True
            break
        time.sleep(0.1)
    if not exited and _process_alive(pid):
        # Final SIGKILL within the bounded grace window.
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        # Best-effort reap.
        try:
            os.waitpid(pid, os.WNOHANG)
        except (OSError, ChildProcessError):
            pass

    listener_closed = not _loopback_listener_open(host, port) if port else True
    _clear_ledger(paths)
    packet.update(
        {
            "status": "ok" if exited or listener_closed else "blocked",
            "machine_error_code": "OK" if exited or listener_closed else "WEB_STOP_INCOMPLETE",
            "pid": pid,
            "signalled": signalled,
            "exited_within_grace": exited,
            "listener_closed": listener_closed,
            "pre_signal_command_digest": _argv_digest([pre_command]),
            "next_action": "none" if exited or listener_closed else "diagnose_web_stop",
        }
    )
    return packet


def web_open(paths: WebLifecyclePaths) -> dict[str, Any]:
    """Print the loopback deep-link URL for the running server.

    This command never dispatches an OS ``open`` action; it only reports the
    URL so the operator can open it deliberately.
    """
    packet = _base_packet(paths, "wbp_web_lifecycle_open")
    ledger, classification = _classify_running_ledger(paths)
    if classification != "running" or ledger is None:
        packet.update(
            {
                "status": "rejected",
                "machine_error_code": "WEB_NOT_RUNNING",
                "human_message": "WBP web control surface is not running.",
                "next_action": "run_web_start_first",
            }
        )
        return packet
    host = str(ledger.get("host") or DEFAULT_WEB_HOST)
    port = _as_int(ledger.get("port")) or DEFAULT_WEB_PORT
    packet.update(
        {
            "status": "ok",
            "machine_error_code": "OK",
            "base_url": f"http://{host}:{port}",
            "human_message": "Open the URL from the operator OS browser session.",
            "next_action": "none",
        }
    )
    return packet


def clear_stale_ledger(paths: WebLifecyclePaths) -> dict[str, Any]:
    """Clear a stale ledger without signalling any process. Read-only-safe."""
    packet = _base_packet(paths, "wbp_web_lifecycle_clear_stale")
    ledger, classification = _classify_running_ledger(paths)
    if classification == "running":
        packet.update(
            {
                "status": "rejected",
                "machine_error_code": "WEB_STILL_RUNNING",
                "human_message": "Ledger records a running server; use stop instead.",
                "next_action": "run_web_stop",
            }
        )
        return packet
    _clear_ledger(paths)
    packet.update(
        {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "Stale web PID ledger cleared.",
            "classification_before": classification,
            "next_action": "none",
        }
    )
    return packet
