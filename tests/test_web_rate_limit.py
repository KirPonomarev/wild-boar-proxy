# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.web_rate_limit import WebPostRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class WebPostRateLimiterTests(unittest.TestCase):
    def test_default_limit_blocks_eleventh_request_in_one_second(self) -> None:
        clock = FakeClock()
        limiter = WebPostRateLimiter(clock=clock)

        for _ in range(10):
            self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/action"))

        self.assertFalse(limiter.admit(client_ip="127.0.0.1", path="/api/action"))

    def test_window_resets_after_one_second(self) -> None:
        clock = FakeClock()
        limiter = WebPostRateLimiter(limit_per_second=2, clock=clock)

        self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/action"))
        self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/action"))
        self.assertFalse(limiter.admit(client_ip="127.0.0.1", path="/api/action"))

        clock.advance(1.0)

        self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/action"))

    def test_different_paths_do_not_share_quota(self) -> None:
        clock = FakeClock()
        limiter = WebPostRateLimiter(limit_per_second=1, clock=clock)

        self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/action"))
        self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/review-command"))
        self.assertFalse(limiter.admit(client_ip="127.0.0.1", path="/api/action"))

    def test_different_client_ips_do_not_share_quota(self) -> None:
        clock = FakeClock()
        limiter = WebPostRateLimiter(limit_per_second=1, clock=clock)

        self.assertTrue(limiter.admit(client_ip="127.0.0.1", path="/api/action"))
        self.assertTrue(limiter.admit(client_ip="127.0.0.2", path="/api/action"))
        self.assertFalse(limiter.admit(client_ip="127.0.0.1", path="/api/action"))

    def test_limit_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            WebPostRateLimiter(limit_per_second=0)


if __name__ == "__main__":
    unittest.main()
