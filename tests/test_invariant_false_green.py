# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tools.truth_tree_harness import assert_no_truth_mutation, snapshot_truth_tree


ROOT = Path(__file__).resolve().parents[1]
SENTINEL_SECRET = "sentinel-secret-d1a-invariant-false-green"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _strict_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, index = decoder.raw_decode(raw)
    if raw[index:].strip():
        raise AssertionError("stdout must contain exactly one JSON object")
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


class _InvariantFalseGreenHandler(BaseHTTPRequestHandler):
    mode = "socket_only"

    def do_GET(self) -> None:  # noqa: N802
        if self.mode == "foreign_openai" and self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "gpt-5.4"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.mode == "foreign_openai" and self.path == "/v1/responses":
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length)
            body = json.dumps({"output_text": "OK"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        return


class InvariantFalseGreenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.profile_dir / "managed"
        self.stable_dir = self.root / "stable"
        for path in (self.profile_dir, self.managed_dir, self.stable_dir):
            path.mkdir(parents=True)
        _InvariantFalseGreenHandler.mode = "socket_only"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_runtime_fixture(self, port: int) -> None:
        endpoint = f"http://127.0.0.1:{port}/v1"
        (self.profile_dir / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": SENTINEL_SECRET}) + "\n",
            encoding="utf-8",
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "{endpoint}"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n",
            encoding="utf-8",
        )
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "updated_at": "2026-06-01T00:00:00+00:00",
                    "stable_default_backend_id": "default-backend",
                    "pool_policy": {
                        "active_min": 1,
                        "active_target": 2,
                        "reserve_target": 0,
                    },
                    "backends": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "status": "healthy",
                            "manual_hold": False,
                            "auth_ref": str(self.profile_dir / "auth.json"),
                            "fail_count": 0,
                            "success_count": 1,
                            "last_success": None,
                            "last_error": "",
                            "cooldown_until": None,
                            "notes": "",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "status": "healthy",
                    "effective_mode": "managed",
                    "last_sync_at": "2026-06-01T00:00:00+00:00",
                    "last_error": "",
                    "selected_backend_ids": ["backend-a"],
                    "managed_port": port,
                    "current_proxy_url": "http://127.0.0.1:10808",
                    "stable_default_backend_id": "default-backend",
                    "active_count": 1,
                    "reserve_count": 0,
                    "retired_count": 0,
                    "healthy_count": 1,
                    "degraded_count": 0,
                    "down_count": 0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 9\n",
            encoding="utf-8",
        )

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_AUTH_FILE"] = str(self.profile_dir / "auth.json")
        env["WBP_CONFIG_TOML"] = str(self.profile_dir / "config.toml")
        env["WBP_RUNTIME_MODE_FILE"] = str(self.profile_dir / "runtime-mode.txt")
        env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
            self.profile_dir / "runtime-effective-mode.txt"
        )
        env["WBP_REGISTRY_FILE"] = str(self.managed_dir / "backend-registry.json")
        env["WBP_STATE_FILE"] = str(self.managed_dir / "supervisor-state.json")
        env["WBP_MANAGED_CONFIG_FILE"] = str(self.managed_dir / "managed-config.yaml")
        env["WBP_LOCK_FILE"] = str(self.managed_dir / "wild-boar-proxy.lock")
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    def truth_snapshot(self) -> dict[str, dict[str, object]]:
        return snapshot_truth_tree(
            {
                "backend-registry.json": self.managed_dir / "backend-registry.json",
                "supervisor-state.json": self.managed_dir / "supervisor-state.json",
                "managed-config.yaml": self.managed_dir / "managed-config.yaml",
                "runtime-mode.txt": self.profile_dir / "runtime-mode.txt",
                "runtime-effective-mode.txt": (
                    self.profile_dir / "runtime-effective-mode.txt"
                ),
                "config.toml": self.profile_dir / "config.toml",
                "auth.json": self.profile_dir / "auth.json",
            },
            secret_labels={"auth.json"},
        )

    def run_invariant_check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", "invariant-check", "--json"],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_not_green_without_truth(self, result: subprocess.CompletedProcess[str]) -> None:
        payload = _strict_json_object(result.stdout)
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertNotEqual(payload["status"], "ok")
        self.assertNotEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["machine_error_code"], "RUNTIME_INVARIANT_FAILED")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["invariant_result"]["status"], "failed")
        failed_checks = [
            check
            for check in payload["invariant_result"]["checks"]
            if check["status"] == "fail"
        ]
        self.assertTrue(failed_checks)
        identity_check = next(
            check
            for check in failed_checks
            if check["id"] == "runtime_identity_truth"
        )
        self.assertEqual(identity_check["machine_error_code"], "RUNTIME_IDENTITY_UNPROVEN")
        self.assertNotIn(SENTINEL_SECRET, result.stdout)

    def test_invariant_check_rejects_socket_only_listener_without_runtime_truth(
        self,
    ) -> None:
        port = _free_port()
        self.write_runtime_fixture(port)
        _InvariantFalseGreenHandler.mode = "socket_only"
        server = ThreadingHTTPServer(("127.0.0.1", port), _InvariantFalseGreenHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            before = self.truth_snapshot()
            result = self.run_invariant_check()
            after = self.truth_snapshot()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assert_not_green_without_truth(result)
        assert_no_truth_mutation(before, after)

    def test_invariant_check_rejects_foreign_openai_compatible_listener_without_identity(
        self,
    ) -> None:
        port = _free_port()
        self.write_runtime_fixture(port)
        _InvariantFalseGreenHandler.mode = "foreign_openai"
        server = ThreadingHTTPServer(("127.0.0.1", port), _InvariantFalseGreenHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            before = self.truth_snapshot()
            result = self.run_invariant_check()
            after = self.truth_snapshot()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assert_not_green_without_truth(result)
        assert_no_truth_mutation(before, after)


if __name__ == "__main__":
    unittest.main()
