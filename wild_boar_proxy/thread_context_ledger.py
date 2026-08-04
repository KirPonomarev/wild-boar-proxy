# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Thread Context Ledger V2 (B04).

The shared visible-context source for external actors. Stores only permitted
visible user messages, visible native answers, proven external actor outputs,
binding/assignment revisions, redacted summaries, and context digests.

Never stores: hidden reasoning, chain-of-thought, credentials, auth/session
payloads, raw Keychain values, cookies, or unrestricted runtime-context dumps.

Properties:

- transactional appends under a real flock
- monotonic revision and generation identifier
- event idempotency and duplicate rejection
- crash recovery and atomic compaction
- per-thread isolation
- TTL and size limits
- file mode 0600
- redaction before persistence
- every dispatch bound to an exact context digest
- explicit degraded/failure status when required hook fields are unavailable
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LEDGER_SCHEMA_VERSION = 2
LEDGER_KIND = "thread_context_ledger_v2"
LEDGER_FILE = "ledger.json"
LEDGER_JSONL = "ledger.jsonl"

ENTRY_USER_VISIBLE = "user_message_visible"
ENTRY_NATIVE_ANSWER = "native_answer_visible"
ENTRY_EXTERNAL_OUTPUT = "external_actor_output"
ENTRY_BINDING_REVISION = "binding_revision"
ENTRY_ASSIGNMENT_REVISION = "assignment_revision"
ENTRY_REDACTED_SUMMARY = "redacted_summary"
ENTRY_CONTEXT_DIGEST = "context_digest"
ENTRY_KINDS = (
    ENTRY_USER_VISIBLE,
    ENTRY_NATIVE_ANSWER,
    ENTRY_EXTERNAL_OUTPUT,
    ENTRY_BINDING_REVISION,
    ENTRY_ASSIGNMENT_REVISION,
    ENTRY_REDACTED_SUMMARY,
    ENTRY_CONTEXT_DIGEST,
)

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_FAILED = "failed"

DEFAULT_MAX_ENTRIES = 500
DEFAULT_MAX_ENTRY_BYTES = 4096
DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

# Redaction: secret-shaped content is never persisted.
REDACTION_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}\b", re.IGNORECASE),
    re.compile(r"\bAuthorization\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\s*[:=]\s*[^\s,;]{8,}", re.IGNORECASE),
    re.compile(r"\bpassword\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\btoken\s*[:=]\s*[^\s,;]{8,}", re.IGNORECASE),
    re.compile(r"\bsecret\s*[:=]\s*[^\s,;]{8,}", re.IGNORECASE),
    re.compile(r"\bkeychain\b", re.IGNORECASE),
    re.compile(r"\bcookie\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact_text(text: str) -> str:
    """Redact secret-shaped content before persistence."""
    redacted = str(text)
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def context_digest(entries: Iterable["LedgerEntry"]) -> str:
    """Order-sensitive digest of the canonical visible content of entries.

    R03: the digest now includes the entry sequence (revision) and preserves
    insertion order — reversing the message order produces a different digest.
    Timestamps and generation are excluded for cross-replica reproducibility,
    but the relative order (revision) is part of the content identity.
    """
    payload = [
        {
            "seq": entry.revision,
            "kind": entry.kind,
            "content": entry.content,
            "actor_id": entry.actor_id,
            "binding_revision": entry.binding_revision,
            "assignment_revision": entry.assignment_revision,
            "context_digest": entry.context_digest,
            "source": entry.source,
        }
        for entry in entries  # preserve caller's list order; do NOT sort
    ]
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


@dataclasses.dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    thread_id: str
    kind: str
    content: str
    context_digest: str
    revision: int
    generation: int
    source: str  # native | external_actor_id | hook | system
    observed_at_utc: str
    status: str = STATUS_OK
    actor_id: str = ""
    binding_revision: int | None = None
    assignment_revision: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class ThreadContextLedger:
    def __init__(
        self,
        root: Path,
        *,
        thread_id: str,
        generation: int = 1,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_entry_bytes: int = DEFAULT_MAX_ENTRY_BYTES,
        ttl_seconds: int | None = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.root = Path(root)
        self.thread_id = thread_id
        self.generation = generation
        self.max_entries = max_entries
        self.max_entry_bytes = max_entry_bytes
        self.ttl_seconds = ttl_seconds
        self.ledger_root = (self.root / self.thread_id).resolve()
        self._ensure_owned_root()
        self.ledger_path = self.ledger_root / LEDGER_FILE
        self.jsonl_path = self.ledger_root / LEDGER_JSONL
        self._entries: list[LedgerEntry] = []
        self._revision = 0
        self._status = STATUS_OK
        self._last_error = ""
        self._recovered = False
        self._load()

    def _ensure_owned_root(self) -> None:
        # Per-thread isolation: the thread root must stay under the approved
        # ledger root. Use Path.resolve().relative_to() — not str.startswith()
        # — because "../approved-escape" defeats startswith.
        resolved_root = Path(self.root).resolve()
        try:
            self.ledger_root.relative_to(resolved_root)
        except ValueError:
            raise ValueError("ledger thread root escapes approved root")
        self.ledger_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.ledger_root, 0o700)

    # -- persistence ------------------------------------------------------

    def _acquire_lock(self):
        lock_path = self.ledger_root / "ledger.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def _load(self) -> None:
        if not self.ledger_path.is_file():
            return
        try:
            raw = self.ledger_path.read_text(encoding="utf-8")
            document = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            self._status = STATUS_FAILED
            self._last_error = "ledger_file_unreadable"
            return
        if not isinstance(document, dict):
            self._status = STATUS_FAILED
            self._last_error = "ledger_document_not_object"
            return
        entries_raw = document.get("entries")
        if not isinstance(entries_raw, list):
            self._status = STATUS_FAILED
            self._last_error = "ledger_entries_not_list"
            return
        loaded: list[LedgerEntry] = []
        recovered = False
        for raw_entry in entries_raw:
            if not isinstance(raw_entry, dict):
                self._status = STATUS_DEGRADED
                self._last_error = "ledger_entry_invalid"
                continue
            try:
                loaded.append(LedgerEntry(**raw_entry))
            except TypeError:
                # Crash recovery: skip malformed entries instead of failing
                # the whole ledger; the status is degraded until compaction.
                self._status = STATUS_DEGRADED
                self._last_error = "ledger_entry_invalid"
                recovered = True
                continue
        # Recovery: enforce monotonic revision ordering; drop non-monotonic
        # tail. Malformed or out-of-order entries mark the ledger degraded
        # until the atomic compaction rewrites the file.
        ordered: list[LedgerEntry] = []
        for entry in loaded:
            if entry.revision == len(ordered) + 1:
                ordered.append(entry)
            else:
                recovered = True
        self._entries = ordered
        self._revision = len(ordered)
        self._recovered = recovered
        if self._status == STATUS_OK and recovered:
            self._status = STATUS_DEGRADED
            self._last_error = "ledger_revision_gap_recovered"
        if recovered or self._status == STATUS_DEGRADED:
            self._compact_locked()

    def _write_locked(self) -> None:
        document = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "kind": LEDGER_KIND,
            "thread_id": self.thread_id,
            "generation": self.generation,
            "revision": self._revision,
            "entries": [entry.as_dict() for entry in self._entries],
            "updated_at_utc": utc_now(),
        }
        tmp = self.ledger_root / ".ledger.tmp"
        with open(tmp, "wb") as f:
            f.write(canonical_bytes(document))
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.ledger_path)
        dir_fd = os.open(self.ledger_root, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _compact_locked(self) -> None:
        self._write_locked()

    def _prune_expired_locked(self) -> int:
        if self.ttl_seconds is None:
            return 0
        now = datetime.now(timezone.utc)
        keep: list[LedgerEntry] = []
        pruned = 0
        for entry in self._entries:
            try:
                observed = datetime.fromisoformat(
                    entry.observed_at_utc.replace("Z", "+00:00")
                )
            except ValueError:
                pruned += 1
                continue
            if (now - observed).total_seconds() > self.ttl_seconds:
                pruned += 1
            else:
                keep.append(entry)
        if pruned:
            # TTL prune keeps revision continuity: the digest changes, so the
            # generation advances (documented degradation path).
            self._entries = keep
            self.generation += 1
            self._write_locked()
        return pruned

    # -- public surface ---------------------------------------------------

    @property
    def status(self) -> str:
        return self._status

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def recovered(self) -> bool:
        return self._recovered

    def append(
        self,
        *,
        entry_id: str,
        kind: str,
        content: str,
        source: str,
        context_digest: str,
        actor_id: str = "",
        binding_revision: int | None = None,
        assignment_revision: int | None = None,
    ) -> dict[str, Any]:
        """Append one entry transactionally. Idempotent on entry_id."""
        if kind not in ENTRY_KINDS:
            return self._packet(STATUS_FAILED, "ledger_entry_kind_unknown")
        if not isinstance(entry_id, str) or not entry_id:
            return self._packet(STATUS_FAILED, "ledger_entry_id_missing")
        if not isinstance(context_digest, str) or not context_digest:
            return self._packet(STATUS_DEGRADED, "ledger_context_digest_missing")
        redacted = redact_text(content)
        if len(redacted.encode("utf-8")) > self.max_entry_bytes:
            return self._packet(STATUS_DEGRADED, "ledger_entry_too_large")
        fd = self._acquire_lock()
        try:
            # R03: reread disk state under lock to prevent lost updates
            # when two instances share the same root.
            self._load()
            if any(entry.entry_id == entry_id for entry in self._entries):
                return self._packet(STATUS_OK, "ledger_entry_duplicate_rejected", duplicate=True)
            entry = LedgerEntry(
                entry_id=entry_id,
                thread_id=self.thread_id,
                kind=kind,
                content=redacted,
                context_digest=context_digest,
                revision=self._revision + 1,
                generation=self.generation,
                source=source,
                observed_at_utc=utc_now(),
                actor_id=actor_id,
                binding_revision=binding_revision,
                assignment_revision=assignment_revision,
            )
            self._entries.append(entry)
            self._revision += 1
            if len(self._entries) > self.max_entries:
                # Size limit: keep the newest entries, advance generation.
                self._entries = self._entries[-self.max_entries:]
                self.generation += 1
            self._write_locked()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        return self._packet(STATUS_OK, "ledger_entry_appended")

    def snapshot(self) -> dict[str, Any]:
        """Read-only ledger snapshot with bounded entry projections."""
        if self._status == STATUS_FAILED:
            return self._packet(STATUS_FAILED, self._last_error)
        pruned = self._prune_expired_locked() if self._entries else 0
        visible = [entry.as_dict() for entry in self._entries]
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "kind": LEDGER_KIND,
            "thread_id": self.thread_id,
            "generation": self.generation,
            "revision": self._revision,
            "status": self._status,
            "entry_count": len(visible),
            "entries": visible,
            "context_digest": context_digest(self._entries),
            "pruned_expired": pruned,
            "recovered": self._recovered,
            "last_error": self._last_error,
            "permissions": "0600",
        }

    def _packet(self, status: str, machine_error_code: str, *, duplicate: bool = False) -> dict[str, Any]:
        return {
            "status": status,
            "machine_error_code": machine_error_code,
            "thread_id": self.thread_id,
            "revision": self._revision,
            "generation": self.generation,
            "entry_count": len(self._entries),
            "duplicate_rejected": duplicate,
        }


def default_ledger_root() -> Path:
    return Path(tempfile.gettempdir()) / "wbp-thread-context-ledgers"


__all__ = [
    "LEDGER_SCHEMA_VERSION",
    "LEDGER_KIND",
    "ENTRY_USER_VISIBLE",
    "ENTRY_NATIVE_ANSWER",
    "ENTRY_EXTERNAL_OUTPUT",
    "ENTRY_BINDING_REVISION",
    "ENTRY_ASSIGNMENT_REVISION",
    "ENTRY_REDACTED_SUMMARY",
    "ENTRY_CONTEXT_DIGEST",
    "ENTRY_KINDS",
    "STATUS_OK",
    "STATUS_DEGRADED",
    "STATUS_FAILED",
    "LedgerEntry",
    "ThreadContextLedger",
    "redact_text",
    "context_digest",
    "default_ledger_root",
]
