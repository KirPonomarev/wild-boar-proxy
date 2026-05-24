# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Main-side review session store for the review bridge contours."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ReviewSessionRecord:
    project_id: str
    session_id: str
    baseline_hash: str
    review_surface: dict[str, Any]
    revision_session: dict[str, Any]
    source_packet_hash: str
    created_at: str


class ReviewSessionStore:
    """In-memory main-process-owned store for a single active review session."""

    def __init__(self) -> None:
        self._record: ReviewSessionRecord | None = None

    def has_active_session(self) -> bool:
        return self._record is not None

    def active_record(self) -> ReviewSessionRecord | None:
        return self._record

    def query_surface(self) -> dict[str, Any]:
        record = self._record
        if record is None:
            return {
                "status": "empty",
                "machine_error_code": "REVIEW_SESSION_EMPTY",
                "session_present": False,
                "review_surface": None,
                "revision_session": None,
            }
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "session_present": True,
            **asdict(record),
        }

    def _store_imported_session(
        self,
        *,
        project_id: str,
        session_id: str,
        baseline_hash: str,
        review_surface: dict[str, Any],
        revision_session: dict[str, Any],
        source_packet_hash: str,
    ) -> ReviewSessionRecord:
        record = ReviewSessionRecord(
            project_id=project_id,
            session_id=session_id,
            baseline_hash=baseline_hash,
            review_surface=review_surface,
            revision_session=revision_session,
            source_packet_hash=source_packet_hash,
            created_at=_utc_now(),
        )
        self._record = record
        return record

    def _clear_active_session(self) -> bool:
        had_active = self._record is not None
        self._record = None
        return had_active


class ReviewQueryBridge:
    """Read-only query bridge for review session surfaces."""

    def __init__(self, store: ReviewSessionStore) -> None:
        self._store = store

    def get_review_surface(self) -> dict[str, Any]:
        return self._store.query_surface()
