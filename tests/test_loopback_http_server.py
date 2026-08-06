# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression tests for LoopbackThreadingHTTPServer (SD-R57).

Root cause proven on CI runners: ``http.server.HTTPServer.server_bind``
calls ``socket.getfqdn``, a blocking reverse-DNS lookup that stalled ~35s
per fresh process on runners whose resolver drops PTR queries. Seven
full-suite tests failed on that stall (test_cli fake stable runtime, web
lifecycle integration, web design UI static preview). Patching
``socket.getfqdn`` to raise proves the bind path stays hermetic.
"""

from __future__ import annotations

import http.server
import inspect
import json
import threading
import unittest
import urllib.request
from unittest import mock

from wild_boar_proxy.loopback_http_server import LoopbackThreadingHTTPServer


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        return


class LoopbackThreadingHTTPServerTests(unittest.TestCase):
    def test_stdlib_server_bind_still_calls_getfqdn(self) -> None:
        # Meta-guard: if stdlib ever drops getfqdn from server_bind, revisit
        # whether this class is still needed instead of silently drifting.
        source = inspect.getsource(http.server.HTTPServer.server_bind)
        self.assertIn("getfqdn", source)

    def test_server_bind_never_calls_getfqdn(self) -> None:
        with mock.patch(
            "socket.getfqdn",
            side_effect=AssertionError("reverse DNS lookup on bind"),
        ):
            server = LoopbackThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        try:
            self.assertEqual(server.server_name, "127.0.0.1")
            self.assertGreater(server.server_port, 0)
        finally:
            server.server_close()

    def test_serves_real_request_on_loopback(self) -> None:
        server = LoopbackThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(
                f"http://127.0.0.1:{server.server_port}/", timeout=10
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload, {"ok": True})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
