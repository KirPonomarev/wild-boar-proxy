# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exclusive repository lease (B05).

All repo-touching operations, including reads, are serialized in V1: at most
one actor may hold the repo lease at a time. The lease is a real OS-level
exclusive lock with holder metadata, a fencing identity, and stale-owner
recovery. ``repo_write`` requires a safe checkout or linked worktree AND this
exclusive lease.
"""

from __future__ import annotations

import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_LEASE_SCHEMA_VERSION = 1
REPO_LEASE_KIND = "repo_lease"
REPO_LEASE_FILENAME = "repo-lease.json"
REPO_LEASE_LOCK_FILENAME = "repo-lease.lock"
STALE_LEASE_TTL_SECONDS = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _lease_path(lease_root: Path) -> Path:
    return Path(lease_root) / REPO_LEASE_FILENAME


def _lock_path(lease_root: Path) -> Path:
    return Path(lease_root) / REPO_LEASE_LOCK_FILENAME


def _read_lease(lease_root: Path) -> dict[str, Any] | None:
    path = _lease_path(lease_root)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


class RepoLease:
    def __init__(self, lease_root: Path) -> None:
        self.lease_root = Path(lease_root)
        self.lease_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def acquire(
        self,
        *,
        holder: str,
        operation: str,
        worktree: str,
        ttl_seconds: int = STALE_LEASE_TTL_SECONDS,
    ) -> dict[str, Any]:
        """Acquire the exclusive repo lease (blocking until free)."""
        lock_fd = os.open(_lock_path(self.lease_root), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            existing = _read_lease(self.lease_root)
            if existing and not self._lease_stale(existing, ttl_seconds=ttl_seconds):
                return self._packet("blocked", "REPO_LEASE_HELD", existing=existing)
            lease = {
                "schema_version": REPO_LEASE_SCHEMA_VERSION,
                "kind": REPO_LEASE_KIND,
                "fencing_token": uuid.uuid4().hex,
                "holder": holder,
                "operation": operation,
                "worktree": worktree,
                "acquired_at_utc": utc_now(),
                "expires_at_utc": utc_now(),
            }
            lease["expires_at_utc"] = _expiry(ttl_seconds)
            self._write(lease)
            return self._packet("ok", "REPO_LEASE_ACQUIRED", lease=lease)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def release(self, *, fencing_token: str) -> dict[str, Any]:
        """Release the lease only when the fencing token matches."""
        lock_fd = os.open(_lock_path(self.lease_root), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            existing = _read_lease(self.lease_root)
            if not existing:
                return self._packet("ok", "REPO_LEASE_NOT_HELD")
            if str(existing.get("fencing_token") or "") != fencing_token:
                return self._packet("blocked", "REPO_LEASE_FENCING_MISMATCH", existing=existing)
            _lease_path(self.lease_root).unlink(missing_ok=True)
            return self._packet("ok", "REPO_LEASE_RELEASED")
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def status(self) -> dict[str, Any]:
        existing = _read_lease(self.lease_root)
        if not existing:
            return self._packet("ok", "REPO_LEASE_FREE")
        return self._packet("ok", "REPO_LEASE_HELD", existing=existing)

    @staticmethod
    def _lease_stale(lease: dict[str, Any], *, ttl_seconds: int) -> bool:
        try:
            expires = datetime.fromisoformat(
                str(lease.get("expires_at_utc") or "").replace("Z", "+00:00")
            )
        except ValueError:
            return True
        return datetime.now(timezone.utc) > expires

    def _write(self, lease: dict[str, Any]) -> None:
        tmp = self.lease_root / ".repo-lease.tmp"
        with open(tmp, "wb") as f:
            f.write(
                (
                    json.dumps(lease, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    + "\n"
                ).encode("utf-8")
            )
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, _lease_path(self.lease_root))

    @staticmethod
    def _packet(status: str, machine_error_code: str, *, existing=None, lease=None) -> dict[str, Any]:
        packet: dict[str, Any] = {
            "status": status,
            "machine_error_code": machine_error_code,
            "lease_held": machine_error_code == "REPO_LEASE_HELD",
        }
        if lease:
            # The fencing token is the holder-only release identity; it is
            # returned to the acquirer and never logged or recorded elsewhere.
            packet["fencing_token"] = lease["fencing_token"]
            packet["lease_held"] = True
        if existing:
            packet["lease_held"] = True
        return packet


def _expiry(ttl_seconds: int) -> str:
    from datetime import timedelta

    return (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    ).isoformat().replace("+00:00", "Z")


__all__ = [
    "REPO_LEASE_SCHEMA_VERSION",
    "REPO_LEASE_KIND",
    "STALE_LEASE_TTL_SECONDS",
    "RepoLease",
]
