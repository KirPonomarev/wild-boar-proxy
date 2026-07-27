# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic unit tests for the WBP web service lifecycle owner surface.

These tests exercise the ledger/classification/clear logic without spawning
real web servers. The end-to-end start/status/stop flow that spawns a real
loopback server is covered by an integration probe that runs only when the
test environment can bind a loopback port.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import web_lifecycle


def _free_loopback_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class WebLifecycleLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.managed_dir = Path(self._tmp.name) / "managed"
        self.managed_dir.mkdir(parents=True, exist_ok=True)
        self.paths = web_lifecycle.WebLifecyclePaths.from_managed_dir(self.managed_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_ledger(self, **fields: object) -> None:
        ledger = {
            "schema_version": 1,
            "pid": fields.get("pid", os.getpid()),
            "ppid": os.getppid(),
            "host": fields.get("host", "127.0.0.1"),
            "port": fields.get("port", _free_loopback_port()),
            "action_phase": "live_readonly",
            "argv_digest": "x" * 64,
            "started_at": "2026-07-27T00:00:00Z",
            "owner_uid": os.getuid(),
            "token_present": True,
        }
        ledger.update(fields)
        web_lifecycle._write_json_atomic(self.paths.pid_ledger, ledger)

    def test_status_no_ledger_reports_not_started(self) -> None:
        packet = web_lifecycle.web_status(self.paths)
        self.assertEqual(packet["classification"], "no_ledger")
        self.assertFalse(packet["ledger_present"])
        self.assertEqual(packet["machine_error_code"], "WEB_NOT_STARTED")
        self.assertEqual(packet["exit_code"], 0)

    def test_status_stale_missing_process(self) -> None:
        # PID 2 is the kernel/scheduler on macOS; effectively never a WBP server.
        self._write_ledger(pid=999999)
        with mock.patch.object(web_lifecycle, "_process_alive", return_value=False):
            packet = web_lifecycle.web_status(self.paths)
        self.assertEqual(packet["classification"], "stale_missing_process")
        self.assertEqual(packet["machine_error_code"], "STALE_WEB_PID_LEDGER")
        self.assertFalse(packet["listener_ok"])

    def test_status_foreign_owner_rejected(self) -> None:
        self._write_ledger(pid=os.getpid())
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid() + 1000),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="web_design_live_server"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_status(self.paths)
        self.assertEqual(packet["classification"], "foreign_owner")
        self.assertEqual(packet["machine_error_code"], "STALE_WEB_PID_LEDGER")

    def test_status_running_reports_ok_and_base_url(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid()),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="python web_design_live_server"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_status(self.paths)
        self.assertEqual(packet["classification"], "running")
        self.assertTrue(packet["listener_ok"])
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["base_url"], f"http://127.0.0.1:{port}")

    def test_start_rejects_public_bind(self) -> None:
        packet = web_lifecycle.web_start(self.paths, host="0.0.0.0")
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "WEB_PUBLIC_BIND_REJECTED")
        self.assertFalse(packet["loopback_bind_enforced"])

    def test_start_rejects_double_start_same_port(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid()),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="python web_design_live_server"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_start(self.paths, port=port)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "WEB_ALREADY_RUNNING")

    def test_start_blocks_when_loopback_port_occupied_by_foreign_listener(self) -> None:
        port = _free_loopback_port()
        with mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True):
            packet = web_lifecycle.web_start(self.paths, port=port)
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "WEB_PORT_OCCUPIED")

    def test_stop_clears_stale_ledger_without_signal(self) -> None:
        self._write_ledger(pid=999999)
        with mock.patch.object(web_lifecycle, "_process_alive", return_value=False):
            packet = web_lifecycle.web_stop(self.paths)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "WEB_NOT_RUNNING")
        self.assertFalse(self.paths.pid_ledger.exists())

    def test_stop_signalls_recorded_pid_and_clears_ledger(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        # First _process_alive call (inside _classify_running_ledger) returns
        # True so stop reaches the signalling path. Subsequent calls in the
        # bounded wait loop return False so the loop observes the exit.
        call_count = {"n": 0}

        def _alive(pid: int) -> bool:
            call_count["n"] += 1
            return call_count["n"] == 1

        with (
            mock.patch.object(web_lifecycle, "_process_alive", side_effect=_alive),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid()),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="python web_design_live_server"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
            mock.patch.object(web_lifecycle.os, "kill") as mock_kill,
        ):
            packet = web_lifecycle.web_stop(self.paths)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["signalled"])
        self.assertTrue(packet["exited_within_grace"])
        mock_kill.assert_called()
        self.assertFalse(self.paths.pid_ledger.exists())

    def test_clear_stale_ledger_rejects_when_running(self) -> None:
        self._write_ledger(pid=os.getpid())
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid()),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="python web_design_live_server"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.clear_stale_ledger(self.paths)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "WEB_STILL_RUNNING")

    def test_clear_stale_ledger_clears_when_missing_process(self) -> None:
        self._write_ledger(pid=999999)
        with mock.patch.object(web_lifecycle, "_process_alive", return_value=False):
            packet = web_lifecycle.clear_stale_ledger(self.paths)
        self.assertEqual(packet["status"], "ok")
        self.assertFalse(self.paths.pid_ledger.exists())

    def test_open_rejects_when_not_running(self) -> None:
        packet = web_lifecycle.web_open(self.paths)
        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "WEB_NOT_RUNNING")

    def test_open_reports_url_when_running(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid()),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="python web_design_live_server"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_open(self.paths)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["base_url"], f"http://127.0.0.1:{port}")

    def test_ledger_is_json_and_writes_atomically(self) -> None:
        self._write_ledger(pid=4242, port=12345)
        raw = self.paths.pid_ledger.read_text(encoding="utf-8")
        self.assertEqual(json.loads(raw)["pid"], 4242)
        self.assertEqual(json.loads(raw)["port"], 12345)

    def test_pid_reuse_by_non_wbp_process_is_stale(self) -> None:
        # PID alive but command line lacks web_design_live_server marker.
        self._write_ledger(pid=os.getpid())
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner", return_value=os.getuid()),
            mock.patch.object(web_lifecycle, "_process_command_digest", return_value="/usr/bin/something_else --foo"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_status(self.paths)
        self.assertEqual(packet["classification"], "stale_missing_process")


class WebLifecycleStartProbeConfigTests(unittest.TestCase):
    def test_probe_loopback_listener_rejects_public_host(self) -> None:
        self.assertFalse(web_lifecycle._loopback_listener_open("0.0.0.0", 8788))

    def test_probe_live_readonly_handles_transport_error(self) -> None:
        result = web_lifecycle._probe_live_readonly("127.0.0.1", 1, timeout=0.2)
        self.assertFalse(result["readiness_ok"])
        self.assertIn(result.get("transport_error", ""), {"ConnectionRefusedError", "URLError", "OSError", "TimeoutError"})


if __name__ == "__main__":
    unittest.main()
