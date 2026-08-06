# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Integration test: real web start/status/open/stop on a free loopback port.

This is an INTEGRATION_PROVEN test (not synthetic): it spawns a real web server,
proves the listener, hits /api/live-readonly, and stops the exact PID.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import web_lifecycle
from wild_boar_proxy.core import packets

# Bounded readiness window for the spawned server child. The production
# default (15s) is calibrated for an interactive workstation; a loaded
# shared CI runner can need longer for a fresh interpreter to import the
# server module and bind. 30s is still a hard bound: on expiry web_start
# fails honestly with WEB_LISTENER_NOT_READY plus full packet diagnostics
# (listener_ok/readiness/pid/orphan_cleanup).
STARTUP_PROBE_TIMEOUT_SECONDS = 30.0


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class WebLifecycleIntegrationTests(unittest.TestCase):
    """Real start/status/open/stop with a spawned loopback server."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.managed_dir = Path(self._tmp.name) / "managed"
        self.managed_dir.mkdir(parents=True, exist_ok=True)
        self.paths = web_lifecycle.WebLifecyclePaths.from_managed_dir(self.managed_dir)
        self.port = _free_port()

    def tearDown(self) -> None:
        # Ensure cleanup even on failure
        web_lifecycle.web_stop(self.paths, shutdown_grace=3.0)
        self._tmp.cleanup()

    def test_start_status_open_stop_full_lifecycle(self) -> None:
        # Start
        start_packet = web_lifecycle.web_start(
            self.paths,
            host="127.0.0.1",
            port=self.port,
            active_project_root=str(self.managed_dir),
            startup_probe_timeout=STARTUP_PROBE_TIMEOUT_SECONDS,
        )
        _assert_semantics(self, start_packet)
        self.assertEqual(start_packet["status"], "ok", f"start failed: {start_packet}")
        self.assertTrue(start_packet["listener_ok"])
        self.assertTrue(start_packet["readiness_ok"])
        self.assertIsNotNone(start_packet["base_url"])

        # Status (should see running)
        status_packet = web_lifecycle.web_status(self.paths)
        _assert_semantics(self, status_packet)
        self.assertEqual(status_packet["classification"], "running")

        # Open (should report URL)
        open_packet = web_lifecycle.web_open(self.paths)
        _assert_semantics(self, open_packet)
        self.assertEqual(open_packet["status"], "ok")
        self.assertIn(str(self.port), open_packet["base_url"])

        # Stop (use a generous grace for CI reliability)
        stop_packet = web_lifecycle.web_stop(self.paths, shutdown_grace=10.0)
        _assert_semantics(self, stop_packet)
        self.assertEqual(stop_packet["status"], "ok")
        # Process should have exited or at minimum listener should be closed
        self.assertTrue(stop_packet["listener_closed"])

        # Status after stop (should see no_ledger)
        after = web_lifecycle.web_status(self.paths)
        self.assertEqual(after["classification"], "no_ledger")

    def test_double_start_rejected(self) -> None:
        web_lifecycle.web_start(
            self.paths, host="127.0.0.1", port=self.port,
            active_project_root=str(self.managed_dir),
            startup_probe_timeout=STARTUP_PROBE_TIMEOUT_SECONDS,
        )
        second = web_lifecycle.web_start(
            self.paths, host="127.0.0.1", port=self.port,
            active_project_root=str(self.managed_dir),
        )
        self.assertEqual(second["status"], "error")
        self.assertEqual(second["machine_error_code"], "WEB_ALREADY_RUNNING")

    def test_public_bind_rejected(self) -> None:
        packet = web_lifecycle.web_start(self.paths, host="0.0.0.0", port=self.port)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_PUBLIC_BIND_REJECTED")

    def test_orphan_cleanup_on_failed_start(self) -> None:
        """If start fails (port occupied), no orphan process or artifacts remain."""
        # Occupy the port first
        occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupier.bind(("127.0.0.1", self.port))
        occupier.listen(1)
        try:
            packet = web_lifecycle.web_start(
                self.paths, host="127.0.0.1", port=self.port,
                active_project_root=str(self.managed_dir),
            )
            # Should be blocked by occupied port
            self.assertEqual(packet["machine_error_code"], "WEB_PORT_OCCUPIED")
            # No artifacts left behind
            self.assertFalse(self.paths.pid_ledger.exists())
        finally:
            occupier.close()


if __name__ == "__main__":
    unittest.main()
