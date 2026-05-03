from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProbeHandler(BaseHTTPRequestHandler):
    response_text = "OK"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "gpt-5.4"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/responses":
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length)
            body = json.dumps({"output_text": self.response_text}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.profile_dir = root / "profile"
        self.managed_dir = self.profile_dir / "managed"
        self.stable_dir = root / "stable"
        self.profile_dir.mkdir(parents=True)
        self.managed_dir.mkdir(parents=True)
        self.stable_dir.mkdir(parents=True)
        (self.profile_dir / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": "test-key"}) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:9999/v1"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text("managed\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "updated_at": "2026-05-03T00:00:00+00:00",
                    "stable_default_backend_id": "default-backend",
                    "pool_policy": {
                        "active_min": 1,
                        "active_target": 2,
                        "reserve_target": 1,
                    },
                    "backends": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "status": "healthy",
                            "manual_hold": False,
                            "auth_ref": "/tmp/a.json",
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
                    "last_sync_at": "2026-05-03T00:00:00+00:00",
                    "last_error": "",
                    "selected_backend_ids": ["backend-a"],
                    "managed_port": 9999,
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
        (self.managed_dir / "managed-config.yaml").write_text(
            "host: 127.0.0.1\nport: 9999\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 8318\n",
            encoding="utf-8",
        )
        self.sync_script = self.managed_dir / "supervisor-sync.sh"
        self.sync_script.write_text(
            "#!/bin/sh\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "from pathlib import Path\n"
            "path = Path(r'" + str(self.managed_dir / "supervisor-state.json") + "')\n"
            "data = json.loads(path.read_text())\n"
            "data['last_error'] = ''\n"
            "path.write_text(json.dumps(data) + '\\n')\n"
            "PY\n"
            "echo sync-ran >&2\n",
            encoding="utf-8",
        )
        self.sync_script.chmod(0o755)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_SYNC_SCRIPT"] = str(self.sync_script)
        return env

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_mode_set_updates_desired_mode(self) -> None:
        result = self.run_cli("mode", "set", "stable", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["desired_mode"], "stable")
        self.assertEqual(
            (self.profile_dir / "runtime-mode.txt").read_text(encoding="utf-8").strip(),
            "stable",
        )

    def test_status_reports_listener_down_when_managed_port_is_absent(self) -> None:
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(payload["liveness"], "down")
        self.assertEqual(payload["next_action"], "retry")

    def test_status_reports_listener_down_when_stable_port_is_absent(self) -> None:
        stable_port = free_port()
        (self.profile_dir / "runtime-effective-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "stable"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(payload["liveness"], "down")

    def test_healthcheck_returns_attestation(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{port}/v1"\n',
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["managed_port"] = port
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli("healthcheck", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["liveness"], "healthy")
        self.assertIn("attestation", payload)
        self.assertTrue(payload["attestation"]["listener_ok"])
        self.assertTrue(payload["attestation"]["models_ok"])
        self.assertTrue(payload["attestation"]["responses_ok"])
        self.assertTrue(payload["attestation"]["base_url_match"])
        self.assertTrue(payload["attestation"]["effective_mode_match"])

    def test_healthcheck_rejects_not_ok_probe(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "NOT OK"
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{port}/v1"\n',
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["managed_port"] = port
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli("healthcheck", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            ProbeHandler.response_text = "OK"
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "ATTESTATION_FAILED")
        self.assertFalse(payload["attestation"]["responses_ok"])

    def test_healthcheck_detects_effective_mode_mismatch(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{port}/v1"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["managed_port"] = port
        state["effective_mode"] = "managed"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli("healthcheck", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertFalse(payload["attestation"]["effective_mode_match"])

    def test_status_uses_live_attestation_for_green_state(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{port}/v1"\n',
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["managed_port"] = port
        state["effective_mode"] = "managed"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli("status", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["liveness"], "healthy")
        self.assertEqual(payload["attestation_summary"]["status"], "ok")

    def test_status_does_not_greenwash_failed_attestation(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "NOT OK"
        (self.managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{port}/v1"\n',
            encoding="utf-8"
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["managed_port"] = port
        state["effective_mode"] = "managed"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli("status", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            ProbeHandler.response_text = "OK"
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "ATTESTATION_FAILED")
        self.assertEqual(payload["liveness"], "degraded")
        self.assertEqual(payload["attestation_summary"]["status"], "error")

    def test_accounts_list_returns_registry_snapshot(self) -> None:
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["accounts"][0]["id"], "backend-a")

    def test_diagnostics_export_creates_bundle(self) -> None:
        result = self.run_cli("diagnostics", "export", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        bundle_path = Path(payload["bundle_path"])
        self.assertTrue(bundle_path.exists())
        registry = json.loads((bundle_path / "backend-registry.json").read_text())
        self.assertEqual(registry["backends"][0]["auth_ref"], "a.json")

    def test_sync_returns_single_json_object(self) -> None:
        result = self.run_cli("sync", "--json")
        self.assertEqual(result.returncode, 1, "managed listener should remain absent")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "SYNC_HEALTHCHECK_FAILED")
        self.assertEqual(payload["liveness"], "down")
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        self.assertEqual(result.stderr.strip(), "sync-ran")

    def test_mode_set_respects_serialized_lock(self) -> None:
        lock_file = self.managed_dir / "wild-boar-proxy.lock"
        lock_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
        result = self.run_cli("mode", "set", "stable", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["machine_error_code"], "LOCK_HELD")
        self.assertEqual(payload["next_action"], "retry")


if __name__ == "__main__":
    unittest.main()
