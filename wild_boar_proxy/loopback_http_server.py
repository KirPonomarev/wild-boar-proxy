# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Loopback HTTP server class without the reverse-DNS stall on bind.

``http.server.HTTPServer.server_bind()`` calls ``socket.getfqdn(host)``,
which issues a blocking reverse-DNS (PTR) lookup. On hosts whose resolver
drops or slow-paths PTR queries — shared CI runners, VPN or offline
workstations — this stalls server startup for tens of seconds: measured
35s per fresh process on GitHub macos runners during SD-R57 diagnosis
(faulthandler stack: ``socket.getfqdn`` <- ``http/server.py server_bind``
<- ``socketserver.__init__``). WBP's own web lifecycle readiness probe is
bounded at 15-30s, so a control-plane child then fails
WEB_LISTENER_NOT_READY even though the listener itself would have come up
instantly.

WBP control-plane servers always bind explicit numeric loopback addresses
and never need an FQDN ``server_name``, so this class binds directly and
records the numeric host instead. Everything else is stock
``ThreadingHTTPServer`` behavior.
"""

from __future__ import annotations

import socketserver
from http.server import ThreadingHTTPServer


class LoopbackThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer whose bind never performs reverse DNS."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port
