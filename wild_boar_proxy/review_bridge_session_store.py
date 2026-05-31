# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Main-side review session store for the review bridge contours."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from wild_boar_proxy.review_bridge_apply_admission import (
    ReviewApplyContext,
    build_review_apply_preflight_packet,
)
from wild_boar_proxy.review_bridge_exact_text_apply import (
    ReviewExactTextApplyResult,
    apply_exact_text_change,
)


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
        self._lock = RLock()

    def has_active_session(self) -> bool:
        with self._lock:
            return self._record is not None

    def active_record(self) -> ReviewSessionRecord | None:
        with self._lock:
            return self._record

    def query_surface(self) -> dict[str, Any]:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            had_active = self._record is not None
            self._record = None
            return had_active

    def _replace_active_review_surface(self, review_surface: dict[str, Any]) -> ReviewSessionRecord:
        with self._lock:
            return self._replace_active_review_surface_unlocked(review_surface)

    def _run_exact_text_apply(
        self,
        *,
        context: ReviewApplyContext | None,
    ) -> tuple[ReviewExactTextApplyResult, ReviewSessionRecord | None]:
        with self._lock:
            result = apply_exact_text_change(self._record, context=context)
            if result.updated_review_surface is None:
                return result, None
            updated = self._replace_active_review_surface_unlocked(result.updated_review_surface)
            return result, updated

    def _replace_active_review_surface_unlocked(
        self,
        review_surface: dict[str, Any],
    ) -> ReviewSessionRecord:
        record = self._record
        if record is None:
            raise RuntimeError("No active review session to update.")
        updated = ReviewSessionRecord(
            project_id=record.project_id,
            session_id=record.session_id,
            baseline_hash=record.baseline_hash,
            review_surface=review_surface,
            revision_session=record.revision_session,
            source_packet_hash=record.source_packet_hash,
            created_at=record.created_at,
        )
        self._record = updated
        return updated


class ReviewQueryBridge:
    """Read-only query bridge for review session surfaces."""

    def __init__(
        self,
        store: ReviewSessionStore,
        *,
        review_apply_context: ReviewApplyContext | None = None,
    ) -> None:
        self._store = store
        self._review_apply_context = review_apply_context

    def get_review_surface(
        self,
        browser_payload: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        payload = self._store.query_surface()
        if self._review_apply_context is None:
            return payload
        payload["apply_preflight"] = build_review_apply_preflight_packet(
            self._store.active_record(),
            context=self._review_apply_context,
            browser_payload=browser_payload,
        )
        return payload
