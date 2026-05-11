"""Observed state, locks, and evidence helpers for external-models."""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors

LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 60.0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            f"State file is not valid JSON: {path}",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        ) from exc


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


@contextmanager
def serialized_lock(path: Path) -> Iterator[None]:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "created_at_utc": contracts.utc_now_iso(),
            "created_at_monotonic": time.monotonic(),
        }
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True)
            break
        except FileExistsError:
            existing = None
            try:
                existing = _read_json(path)
            except RuntimeErrorInfo:
                existing = None
            created_at = 0.0
            pid = -1
            if isinstance(existing, dict):
                created_at = float(existing.get("created_at_monotonic", 0.0))
                pid = int(existing.get("pid", -1))
            lock_is_stale = (pid > 0 and not _pid_alive(pid)) or (
                created_at > 0.0 and (time.monotonic() - created_at) > STALE_LOCK_SECONDS
            )
            if lock_is_stale:
                path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise RuntimeErrorInfo(
                    f"Timed out waiting for lock: {path}",
                    machine_error_code=errors.LOCK_TIMEOUT,
                    operator_action="retry",
                    exit_code=1,
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


@contextmanager
def dual_lock(first: Path, second: Path) -> Iterator[None]:
    with serialized_lock(first):
        with serialized_lock(second):
            yield


def load_state_file(state_file: Path) -> dict[str, Any]:
    if not state_file.exists():
        return contracts.default_state_payload()
    payload = _read_json(state_file)
    if not isinstance(payload, dict):
        raise RuntimeErrorInfo(
            "External-models state must be a JSON object.",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        )
    schema_version = payload.get("schema_version")
    if schema_version != contracts.STATE_SCHEMA_VERSION:
        raise RuntimeErrorInfo(
            "Unsupported external-models state schema version.",
            machine_error_code=errors.UNSUPPORTED_SCHEMA_VERSION,
            operator_action="stop",
        )
    return payload


def write_state_file(state_file: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(state_file, payload)


def ensure_secrets_permissions(secrets_file: Path) -> None:
    if not secrets_file.exists():
        return
    mode = secrets_file.stat().st_mode & 0o777
    if mode != 0o600:
        raise RuntimeErrorInfo(
            f"Unsafe permissions on secrets file: {secrets_file}",
            machine_error_code=errors.UNSAFE_SECRET_PERMISSIONS,
            operator_action="user_action",
        )


def capture_local_evidence(
    *,
    evidence_dir: Path,
    route: dict[str, Any],
    packet: dict[str, Any],
) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = contracts.utc_now_iso().replace(":", "").replace("-", "")
    payload = {
        "schema_version": contracts.EVIDENCE_SCHEMA_VERSION,
        "captured_at_utc": contracts.utc_now_iso(),
        "route_id": route["route_id"],
        "command_context": "external-models evidence capture",
        "network_dependent_evidence": False,
        "result": {
            "status": packet["status"],
            "machine_error_code": packet["machine_error_code"],
            "requested_model": route["route_id"],
            "effective_model": None,
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
            "cost_class": route["cost_class"],
            "latency_ms": None,
        },
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = evidence_dir / f"{route['route_id']}-{stamp}.json"
    atomic_write_json(path, payload)
    return path
