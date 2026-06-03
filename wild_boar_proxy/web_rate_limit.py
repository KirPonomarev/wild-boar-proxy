# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Local web POST ingress rate limiting helpers."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import Lock
import time


DEFAULT_WEB_POST_RATE_LIMIT_PER_SECOND = 10
WEB_RATE_LIMIT_MACHINE_ERROR_CODE = "WEB_INGRESS_RATE_LIMITED"


class WebPostRateLimiter:
    def __init__(
        self,
        *,
        limit_per_second: int = DEFAULT_WEB_POST_RATE_LIMIT_PER_SECOND,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if limit_per_second <= 0:
            raise ValueError("limit_per_second must be positive")
        self._limit_per_second = int(limit_per_second)
        self._clock = clock or time.monotonic
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    @property
    def limit_per_second(self) -> int:
        return self._limit_per_second

    def admit(self, *, client_ip: str, path: str) -> bool:
        key = (str(client_ip or ""), str(path or ""))
        now = float(self._clock())
        oldest_allowed = now - 1.0
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= oldest_allowed:
                events.popleft()
            if len(events) >= self._limit_per_second:
                return False
            events.append(now)
            return True
