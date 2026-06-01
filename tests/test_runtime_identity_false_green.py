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
SENTINEL_SECRET = "sk-d0a-false-green-sentinel-secret"


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


class _FalseGreenProbeHandler(BaseHTTPRequestHandler):
    mode = "no_openai_surfaces"
    last_authorization = ""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models" and self.mode in {
            "models_only",
            "responses_auth_unavailable",
            "responses_status_ok_wrong_shape",
            "responses_not_ok",
        }:
            body = json.dumps({"data": [{"id": "gpt-5.4"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)
        self.__class__.last_authorization = self.headers.get("Authorization", "")
        if self.mode == "responses_auth_unavailable":
            payload: dict[str, Any] = {
                "error": {
                    "message": "auth_unavailable: no auth available for model gpt-5.4"
                }
            }
            status_code = 503
        elif self.mode == "responses_status_ok_wrong_shape":
            payload = {"status": "OK"}
            status_code = 200
        elif self.mode == "responses_not_ok":
            payload = {"output_text": "NOT OK"}
            status_code = 200
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        return


class RuntimeIdentityFalseGreenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.auth_dir = self.root / "auth"
        self.bin_dir = self.managed_dir / "bin"
        for path in (
            self.profile_dir,
            self.managed_dir,
            self.stable_dir,
            self.auth_dir,
            self.bin_dir,
        ):
            path.mkdir(parents=True)
        _FalseGreenProbeHandler.mode = "no_openai_surfaces"
        _FalseGreenProbeHandler.last_authorization = ""

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_runtime_fixture(
        self, port: int, *, auth_pool_unusable: bool = False
    ) -> None:
        endpoint = f"http://127.0.0.1:{port}/v1"
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
        (self.profile_dir / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": SENTINEL_SECRET}) + "\n",
            encoding="utf-8",
        )
        backend_auth = self.auth_dir / "backend-a.json"
        backend_auth.write_text("{}\n", encoding="utf-8")
        backend = {
            "id": "backend-a",
            "label": "Backend A",
            "pool": "active",
            "status": "healthy",
            "manual_hold": False,
            "auth_ref": str(backend_auth),
            "fail_count": 0,
            "success_count": 1,
        }
        if auth_pool_unusable:
            backend.update(
                {
                    "status": "down",
                    "last_error_class": "auth",
                    "last_error": "HTTP 401: auth_unavailable",
                }
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
                    "backends": [backend],
                },
                ensure_ascii=True,
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
                    "selected_backend_ids": ["backend-a"],
                    "managed_port": port,
                    "last_error": "",
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 9\n",
            encoding="utf-8",
        )
        launcher_script = self.managed_dir / "stable-runtime-launcher.sh"
        launcher_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        launcher_script.chmod(0o755)

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
        env["WBP_LAUNCHER_SCRIPT"] = str(
            self.managed_dir / "stable-runtime-launcher.sh"
        )
        env["WBP_LOCK_FILE"] = str(self.managed_dir / "wild-boar-proxy.lock")
        env["WBP_LAUNCHER_LOCK_FILE"] = str(
            self.managed_dir / "stable-runtime-launch.lock"
        )
        env["WBP_PROXY_REPROBE_DISABLE_LEGACY_CANDIDATES"] = "1"
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    def truth_snapshot(self) -> dict[str, dict[str, Any]]:
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
            }
        )

    def run_healthcheck(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", "healthcheck", "--json"],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_honest_probe_failure(
        self,
        payload: dict[str, Any],
        *,
        attestation: dict[str, bool],
        machine_error_code: str = "ATTESTATION_FAILED",
        auth_pool_status: str = "launch_capable_available",
        blocking_reason: str,
    ) -> None:
        for field in (
            "status",
            "exit_code",
            "human_message",
            "machine_error_code",
            "changed_files",
            "next_action",
            "liveness",
            "severity",
            "operator_action",
        ):
            self.assertIn(field, payload)
        self.assertEqual(payload["status"], "error")
        self.assertNotEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["machine_error_code"], machine_error_code)
        self.assertNotEqual(payload["liveness"], "healthy")
        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertNotEqual(payload["operator_action"], "none")

        observed_attestation = payload["attestation"]
        self.assertEqual(
            observed_attestation["attestation_source"], "healthcheck --json"
        )
        for field in (
            "listener_ok",
            "models_ok",
            "responses_ok",
            "effective_mode_match",
            "base_url_match",
        ):
            self.assertIsInstance(observed_attestation[field], bool)
        self.assertIsInstance(observed_attestation["observed_at_utc"], str)
        for field, expected in attestation.items():
            self.assertEqual(observed_attestation[field], expected)

        launch_readiness = payload["launch_readiness"]
        self.assertFalse(launch_readiness["gate_passed"])
        self.assertEqual(launch_readiness["status"], "blocked")
        self.assertEqual(launch_readiness["blocking_reason"], blocking_reason)
        self.assertEqual(
            launch_readiness["owner_command_surface"], "healthcheck --json"
        )

        self.assertEqual(payload["auth_pool_hygiene"]["status"], auth_pool_status)
        self.assertEqual(
            payload["runtime_guardrails"]["owner_command_surface"],
            "healthcheck --json",
        )

    def assert_case(
        self,
        *,
        handler_mode: str,
        expected_attestation: dict[str, bool],
        expected_blocking_reason: str,
        expected_machine_error_code: str = "ATTESTATION_FAILED",
        auth_pool_unusable: bool = False,
        expected_auth_pool_status: str = "launch_capable_available",
    ) -> None:
        port = _free_port()
        self.write_runtime_fixture(port, auth_pool_unusable=auth_pool_unusable)
        _FalseGreenProbeHandler.mode = handler_mode
        server = ThreadingHTTPServer(("127.0.0.1", port), _FalseGreenProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            before = self.truth_snapshot()
            result = self.run_healthcheck()
            after = self.truth_snapshot()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

        self.assertEqual(result.stderr, "")
        self.assertNotIn(SENTINEL_SECRET, result.stdout)
        self.assertNotIn("sk-d0a-", result.stdout)
        payload = _strict_json_object(result.stdout)
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(result.returncode, 1)
        self.assert_honest_probe_failure(
            payload,
            attestation=expected_attestation,
            machine_error_code=expected_machine_error_code,
            auth_pool_status=expected_auth_pool_status,
            blocking_reason=expected_blocking_reason,
        )
        assert_no_truth_mutation(before, after)

    def test_listener_without_openai_surfaces_is_not_runtime_green(self) -> None:
        self.assert_case(
            handler_mode="no_openai_surfaces",
            expected_attestation={
                "listener_ok": True,
                "models_ok": False,
                "responses_ok": False,
                "effective_mode_match": True,
                "base_url_match": True,
            },
            expected_blocking_reason="models_surface_unavailable_or_invalid",
        )

    def test_models_only_surface_is_not_runtime_green(self) -> None:
        self.assert_case(
            handler_mode="models_only",
            expected_attestation={
                "listener_ok": True,
                "models_ok": True,
                "responses_ok": False,
                "effective_mode_match": True,
                "base_url_match": True,
            },
            expected_blocking_reason="responses_probe_failed",
        )

    def test_broken_responses_proof_is_not_runtime_green(self) -> None:
        self.assert_case(
            handler_mode="responses_not_ok",
            expected_attestation={
                "listener_ok": True,
                "models_ok": True,
                "responses_ok": False,
                "effective_mode_match": True,
                "base_url_match": True,
            },
            expected_blocking_reason="responses_probe_failed",
        )

    def test_status_ok_without_response_text_is_not_runtime_green(self) -> None:
        self.assert_case(
            handler_mode="responses_status_ok_wrong_shape",
            expected_attestation={
                "listener_ok": True,
                "models_ok": True,
                "responses_ok": False,
                "effective_mode_match": True,
                "base_url_match": True,
            },
            expected_blocking_reason="responses_probe_failed",
        )

    def test_unusable_auth_pool_is_not_runtime_green(self) -> None:
        self.assert_case(
            handler_mode="responses_auth_unavailable",
            expected_attestation={
                "listener_ok": True,
                "models_ok": True,
                "responses_ok": False,
                "effective_mode_match": True,
                "base_url_match": True,
            },
            expected_blocking_reason="usable_auth_pool_empty",
            expected_machine_error_code="AUTH_UNAVAILABLE",
            auth_pool_unusable=True,
            expected_auth_pool_status="launch_capable_empty",
        )


if __name__ == "__main__":
    unittest.main()
