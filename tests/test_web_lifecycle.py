# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hardened contract tests for the WBP web service lifecycle owner surface.

Covers (W05-R1):
- shared core packet semantics (inspect_command_packet_semantics == []) for
  every result path;
- exact PID identity: PID + UID + canonical module + listener-owned, with
  argv-digest/start-time drift as recorded soft signals;
- PID-reuse-by-same-user-with-similar-but-different-argv does not get a
  signal when the canonical module marker is absent or the recorded loopback
  port is not owned;
- failed-start orphan cleanup: a child that exits during the readiness window
  is stopped, exit proven, and all owner artifacts cleaned;
- stop-incomplete ledger preservation: when SIGTERM does not fully stop the
  process, the pid ledger is preserved as diagnostic ownership evidence;
- effect/changed_files truth for read/mutate/repair paths.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import web_lifecycle
from wild_boar_proxy.core import packets


def _free_loopback_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _assert_packet_semantics(testcase: unittest.TestCase, packet: dict) -> None:
    """Assert the packet conforms to the shared core packet contract."""
    missing = packets.missing_required_fields(
        packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS)
    )
    testcase.assertEqual(
        missing, [], f"packet missing required fields: {missing}\n{json.dumps(packet, indent=2)[:1000]}"
    )
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(
        violations, [], f"packet has semantic violations: {violations}\n{json.dumps(packet, indent=2)[:1000]}"
    )
    # status/exit_code must agree.
    if packet["status"] == "ok":
        testcase.assertEqual(packet["exit_code"], packets.COMMAND_EXIT_OK)
    else:
        testcase.assertEqual(packet["status"], "error")
        testcase.assertEqual(packet["exit_code"], packets.COMMAND_EXIT_ERROR)


class WebLifecyclePathsTests(unittest.TestCase):
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
            "argv_digest": fields.get("argv_digest", "x" * 64),
            "argv": ["python3", "-m", "wild_boar_proxy.web_design_live_server"],
            "started_at": "2026-07-27T00:00:00Z",
            "owner_uid": os.getuid(),
            "process_start_time": fields.get("process_start_time", "Thu Jan  1 00:00:00 1970"),
            "token_present": True,
        }
        ledger.update(fields)
        web_lifecycle._write_json_atomic(self.paths.pid_ledger, ledger, mode=0o600)


class WebStatusContractTests(WebLifecyclePathsTests):
    def test_status_no_ledger_is_ok_read_with_empty_changed_files(self) -> None:
        packet = web_lifecycle.web_status(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "WEB_NOT_STARTED")
        self.assertEqual(packet["effect"], "read")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packet["liveness"], "down")

    def test_status_running_reports_healthy_with_base_url(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_process_start_time", return_value="Thu Jan  1 00:00:00 1970"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_status(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["liveness"], "healthy")
        self.assertEqual(packet["base_url"], f"http://127.0.0.1:{port}")

    def test_status_stale_missing_process_is_error_read(self) -> None:
        self._write_ledger(pid=999999)
        with mock.patch.object(web_lifecycle, "_process_alive", return_value=False):
            packet = web_lifecycle.web_status(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "STALE_WEB_PID_LEDGER")
        self.assertEqual(packet["effect"], "read")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packet["liveness"], "degraded")

    def test_status_foreign_owner_is_error_read(self) -> None:
        self._write_ledger(pid=os.getpid())
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(
                web_lifecycle, "_process_owner_uid", return_value=os.getuid() + 1000
            ),
        ):
            packet = web_lifecycle.web_status(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], "WEB_PID_FOREIGN_OWNER")

    def test_status_identity_mismatch_when_canonical_module_absent(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="/usr/bin/something_else --foo",
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_status(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], "WEB_PROCESS_IDENTITY_MISMATCH")

    def test_status_port_closed_when_listener_gone(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=False),
        ):
            packet = web_lifecycle.web_status(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], "WEB_LISTENER_CLOSED")


class WebStartContractTests(WebLifecyclePathsTests):
    def test_start_rejects_public_bind(self) -> None:
        packet = web_lifecycle.web_start(self.paths, host="0.0.0.0")
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_PUBLIC_BIND_REJECTED")
        self.assertEqual(packet["effect"], "mutate")
        self.assertEqual(packet["changed_files"], [])
        self.assertFalse(packet["loopback_bind_enforced"])

    def test_start_rejects_double_start_same_port(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_start(self.paths, port=port)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], "WEB_ALREADY_RUNNING")

    def test_start_blocks_when_loopback_port_occupied_by_foreign_listener(self) -> None:
        port = _free_loopback_port()
        with mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True):
            packet = web_lifecycle.web_start(self.paths, port=port)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_PORT_OCCUPIED")


class WebStopContractTests(WebLifecyclePathsTests):
    def test_stop_clears_stale_ledger_without_signal(self) -> None:
        self._write_ledger(pid=999999)
        with mock.patch.object(web_lifecycle, "_process_alive", return_value=False):
            packet = web_lifecycle.web_stop(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "WEB_NOT_RUNNING")
        self.assertEqual(packet["effect"], "repair")
        self.assertIn(self.paths.pid_ledger.name, packet["changed_files"])
        self.assertFalse(self.paths.pid_ledger.exists())

    def test_stop_refuses_foreign_owner_and_preserves_ledger(self) -> None:
        self._write_ledger(pid=os.getpid())
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(
                web_lifecycle, "_process_owner_uid", return_value=os.getuid() + 1000
            ),
        ):
            packet = web_lifecycle.web_stop(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_PID_FOREIGN_OWNER")
        self.assertTrue(self.paths.pid_ledger.exists())

    def test_stop_preserves_ledger_on_incomplete_stop(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        alive_states = iter([True, True, True, True])

        def _alive(pid: int) -> bool:
            try:
                return next(alive_states)
            except StopIteration:
                return True

        with (
            mock.patch.object(web_lifecycle, "_process_alive", side_effect=_alive),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
            mock.patch.object(web_lifecycle.os, "kill"),
        ):
            packet = web_lifecycle.web_stop(self.paths, shutdown_grace=0.01)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_STOP_INCOMPLETE")
        self.assertTrue(packet["ledger_preserved_for_diagnostics"])
        self.assertTrue(self.paths.pid_ledger.exists())

    def test_stop_signalls_exact_running_pid_and_clears_ledger(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        # Track os.kill calls to flip listener/alive state right after SIGTERM
        # is dispatched, so the post-stop readback sees the listener closed.
        kill_calls = {"n": 0}
        state = {"stopped": False}

        def _alive(pid: int) -> bool:
            return not state["stopped"]

        def _listener(host: str, p: int, timeout: float = 0.5) -> bool:
            return not state["stopped"]

        def _kill(pid: int, sig: int = signal.SIGTERM) -> None:
            kill_calls["n"] += 1
            # First SIGTERM flips the stopped flag so subsequent alive/listener
            # probes return False (process exited, listener closed).
            if sig == signal.SIGTERM:
                state["stopped"] = True

        with (
            mock.patch.object(web_lifecycle, "_process_alive", side_effect=_alive),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", side_effect=_listener),
            mock.patch.object(web_lifecycle.os, "kill", side_effect=_kill) as mock_kill,
        ):
            packet = web_lifecycle.web_stop(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok", f"packet: {json.dumps(packet)[:400]}")
        self.assertTrue(packet["signalled_term"])
        self.assertTrue(packet["exited_within_grace"])
        mock_kill.assert_called()
        self.assertFalse(self.paths.pid_ledger.exists())


class WebOpenContractTests(WebLifecyclePathsTests):
    def test_open_rejects_when_not_running(self) -> None:
        packet = web_lifecycle.web_open(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_NOT_STARTED")
        self.assertEqual(packet["effect"], "read")

    def test_open_reports_url_when_running(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.web_open(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["base_url"], f"http://127.0.0.1:{port}")


class ClearStaleLedgerContractTests(WebLifecyclePathsTests):
    def test_clear_stale_rejects_when_running(self) -> None:
        port = _free_loopback_port()
        self._write_ledger(pid=os.getpid(), port=port)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=True),
        ):
            packet = web_lifecycle.clear_stale_ledger(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_STILL_RUNNING")
        self.assertEqual(packet["effect"], "repair")

    def test_clear_stale_clears_when_missing_process(self) -> None:
        self._write_ledger(pid=999999)
        with mock.patch.object(web_lifecycle, "_process_alive", return_value=False):
            packet = web_lifecycle.clear_stale_ledger(self.paths)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["effect"], "repair")
        self.assertFalse(self.paths.pid_ledger.exists())


class FailedStartOrphanCleanupTests(WebLifecyclePathsTests):
    def test_failed_start_stops_child_and_cleans_all_artifacts(self) -> None:
        port = _free_loopback_port()
        fake_process = mock.MagicMock()
        fake_process.pid = 999998
        fake_process.poll.return_value = 1
        fake_process.returncode = 1

        with (
            mock.patch.object(web_lifecycle.subprocess, "Popen", return_value=fake_process),
            mock.patch.object(web_lifecycle, "_process_start_time", return_value="Thu Jan  1 00:00:00 1970"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=False),
            mock.patch.object(
                web_lifecycle,
                "_stop_child_process",
                return_value={"post_signal_alive": False, "signalled_term": False, "signalled_kill": False, "exited_within_grace": True, "pre_signal_identity": {}},
            ) as mock_stop,
        ):
            packet = web_lifecycle.web_start(self.paths, port=port, startup_probe_timeout=0.5)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_SERVER_EXITED_DURING_STARTUP")
        mock_stop.assert_called()
        self.assertFalse(self.paths.pid_ledger.exists())
        self.assertFalse(self.paths.startup_receipt.exists())
        self.assertFalse(self.paths.stderr_log.exists())

    def test_failed_start_listener_timeout_stops_child_and_cleans_artifacts(self) -> None:
        port = _free_loopback_port()
        fake_process = mock.MagicMock()
        fake_process.pid = 999997
        fake_process.poll.return_value = None

        with (
            mock.patch.object(web_lifecycle.subprocess, "Popen", return_value=fake_process),
            mock.patch.object(web_lifecycle, "_process_start_time", return_value="Thu Jan  1 00:00:00 1970"),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=False),
            mock.patch.object(web_lifecycle, "_probe_live_readonly", return_value={"readiness_ok": False, "readiness_probed": False}),
            mock.patch.object(
                web_lifecycle,
                "_stop_child_process",
                return_value={"post_signal_alive": False, "signalled_term": True, "signalled_kill": False, "exited_within_grace": True, "pre_signal_identity": {}},
            ) as mock_stop,
        ):
            packet = web_lifecycle.web_start(self.paths, port=port, startup_probe_timeout=0.1)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WEB_LISTENER_NOT_READY")
        mock_stop.assert_called()
        self.assertFalse(self.paths.pid_ledger.exists())


class ProcessIdentityPidReuseTests(unittest.TestCase):
    def test_pid_reuse_with_similar_argv_no_signal_when_port_not_owned(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        managed = Path(tmp.name) / "managed"
        managed.mkdir(parents=True, exist_ok=True)
        paths = web_lifecycle.WebLifecyclePaths.from_managed_dir(managed)
        port = _free_loopback_port()
        ledger = {
            "schema_version": 1,
            "pid": os.getpid(),
            "host": "127.0.0.1",
            "port": port,
            "action_phase": "live_readonly",
            "argv_digest": "x" * 64,
            "argv": ["python", "-m", "wild_boar_proxy.web_design_live_server", "--port", str(port)],
            "started_at": "2026-07-27T00:00:00Z",
            "owner_uid": os.getuid(),
            "process_start_time": "Thu Jan  1 00:00:00 1970",
            "token_present": True,
        }
        web_lifecycle._write_json_atomic(paths.pid_ledger, ledger, mode=0o600)
        with (
            mock.patch.object(web_lifecycle, "_process_alive", return_value=True),
            mock.patch.object(web_lifecycle, "_process_owner_uid", return_value=os.getuid()),
            mock.patch.object(
                web_lifecycle,
                "_process_command_line",
                return_value="python -m wild_boar_proxy.web_design_live_server --port " + str(port),
            ),
            mock.patch.object(web_lifecycle, "_loopback_listener_open", return_value=False),
            mock.patch.object(web_lifecycle.os, "kill") as mock_kill,
        ):
            stop_packet = web_lifecycle.web_stop(paths)
        _assert_packet_semantics(self, stop_packet)
        self.assertEqual(stop_packet["machine_error_code"], "WEB_NOT_RUNNING")
        mock_kill.assert_not_called()


class ProbeLoopbackTests(unittest.TestCase):
    def test_probe_rejects_public_host(self) -> None:
        self.assertFalse(web_lifecycle._loopback_listener_open("0.0.0.0", 8788))

    def test_probe_handles_transport_error(self) -> None:
        result = web_lifecycle._probe_live_readonly("127.0.0.1", 1, timeout=0.2)
        self.assertFalse(result["readiness_ok"])


if __name__ == "__main__":
    unittest.main()
