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
    response_status = 200
    response_payload: object | None = None

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
            payload = (
                {"output_text": self.response_text}
                if self.response_payload is None
                else self.response_payload
            )
            if isinstance(payload, (dict, list)):
                body = json.dumps(payload).encode("utf-8")
                content_type = "application/json"
            else:
                body = str(payload).encode("utf-8")
                content_type = "text/plain"
            self.send_response(self.response_status)
            self.send_header("Content-Type", content_type)
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
        self.launcher_script = self.profile_dir / "codex-custom-launch.sh"
        self.launcher_script.write_text(
            "#!/bin/sh\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "printf 'stable\\n' > \"$WBP_RUNTIME_EFFECTIVE_MODE_FILE\"\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            "from pathlib import Path\n"
            "path = Path(os.environ['WBP_STATE_FILE'])\n"
            "data = json.loads(path.read_text())\n"
            "data['effective_mode'] = 'stable'\n"
            "data['status'] = 'healthy'\n"
            "data['last_error'] = ''\n"
            "path.write_text(json.dumps(data) + '\\n')\n"
            "PY\n"
            "python3 - <<'PY'\n"
            "import os\n"
            "from pathlib import Path\n"
            "stable_config = Path(os.environ['WBP_STABLE_CONFIG'])\n"
            "port = '8318'\n"
            "for raw_line in stable_config.read_text().splitlines():\n"
            "    line = raw_line.strip()\n"
            "    if line.startswith('port:'):\n"
            "        port = line.split(':', 1)[1].strip().strip('\"')\n"
            "        break\n"
            "path = Path(os.environ['WBP_CONFIG_TOML'])\n"
            "lines = path.read_text().splitlines()\n"
            "out = []\n"
            "for line in lines:\n"
            "    if line.strip().startswith('base_url = '):\n"
            "        out.append(f'base_url = \\\"http://127.0.0.1:{port}/v1\\\"')\n"
            "    else:\n"
            "        out.append(line)\n"
            "path.write_text('\\n'.join(out) + '\\n')\n"
            "PY\n",
            encoding="utf-8",
        )
        self.launcher_script.chmod(0o755)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_CONFIG_TOML"] = str(self.profile_dir / "config.toml")
        env["WBP_MANAGED_CONFIG_FILE"] = str(self.managed_dir / "managed-config.yaml")
        env["WBP_STATE_FILE"] = str(self.managed_dir / "supervisor-state.json")
        env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
            self.profile_dir / "runtime-effective-mode.txt"
        )
        env["WBP_LAUNCHER_SCRIPT"] = str(self.launcher_script)
        env["WBP_LAUNCH_STABILIZATION_SECONDS"] = "0"
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
        stable_port = free_port()
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(payload["liveness"], "down")
        self.assertEqual(payload["next_action"], "retry")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["endpoint"], f"http://127.0.0.1:{stable_port}/v1")

    def test_status_reloads_reconciled_state_after_healthcheck(self) -> None:
        stable_port = free_port()
        ProbeHandler.response_text = "OK"
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
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
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["endpoint"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertEqual(payload["pool_summary"]["selected_backend_ids"], [])

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
            ProbeHandler.response_status = 200
            ProbeHandler.response_payload = None
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "ATTESTATION_FAILED")
        self.assertFalse(payload["attestation"]["responses_ok"])

    def test_healthcheck_reports_reprobe_failure_for_proxy_path_failure(self) -> None:
        port = free_port()
        ProbeHandler.response_status = 500
        ProbeHandler.response_payload = {
            "error": {
                "message": (
                    'Post "https://chatgpt.com/backend-api/codex/responses": '
                    "proxyconnect tcp: dial tcp 127.0.0.1:10808: connect: connection refused"
                )
            }
        }
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
            ProbeHandler.response_status = 200
            ProbeHandler.response_payload = None
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "PROXY_REPROBE_FAILED")
        self.assertEqual(payload["liveness"], "degraded")
        self.assertFalse(payload["proxy_reprobe"]["found_candidate"])
        self.assertIn("http://127.0.0.1:10808", payload["proxy_reprobe"]["candidates"])
        self.assertIn("proxyconnect tcp", payload["last_error"])

    def test_healthcheck_reports_working_reprobe_candidate_without_greenwash(self) -> None:
        port = free_port()
        candidate_port = free_port()
        ProbeHandler.response_status = 500
        ProbeHandler.response_payload = {
            "error": {
                "message": (
                    'Post "https://chatgpt.com/backend-api/codex/responses": '
                    "proxyconnect tcp: dial tcp 127.0.0.1:10808: connect: connection refused"
                )
            }
        }
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
        candidate_socket = socket.socket()
        candidate_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        candidate_socket.bind(("127.0.0.1", candidate_port))
        candidate_socket.listen(1)
        server_thread_started = False
        try:
            thread.start()
            server_thread_started = True
            env = self.env()
            env["WBP_PROXY_REPROBE_CANDIDATES"] = (
                f"http://127.0.0.1:{candidate_port},http://127.0.0.1:10808"
            )
            result = subprocess.run(
                ["python3", "-m", "wild_boar_proxy", "healthcheck", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            candidate_socket.close()
            server.shutdown()
            if server_thread_started:
                thread.join()
            server.server_close()
            ProbeHandler.response_status = 200
            ProbeHandler.response_payload = None
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "PROXY_PATH_BROKEN")
        self.assertEqual(payload["liveness"], "degraded")
        self.assertTrue(payload["proxy_reprobe"]["found_candidate"])
        self.assertEqual(
            payload["proxy_reprobe"]["working_candidate"],
            f"http://127.0.0.1:{candidate_port}",
        )
        self.assertFalse(payload["attestation"]["responses_ok"])

    def test_healthcheck_reconciles_effective_mode_mismatch_to_stable(self) -> None:
        stable_port = free_port()
        ProbeHandler.response_text = "OK"
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{stable_port}/v1"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "managed"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
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
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertTrue(payload["attestation"]["effective_mode_match"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["effective_mode"], "stable")
        self.assertEqual(state["selected_backend_ids"], [])

    def test_healthcheck_reconciles_managed_listener_loss_for_reporting(self) -> None:
        stable_port = free_port()
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        result = self.run_cli("healthcheck", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["endpoint"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertTrue(payload["attestation"]["effective_mode_match"])
        self.assertTrue(payload["attestation"]["base_url_match"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["effective_mode"], "stable")
        self.assertEqual(state["selected_backend_ids"], [])
        self.assertEqual(
            (self.profile_dir / "runtime-effective-mode.txt").read_text(encoding="utf-8").strip(),
            "stable",
        )

    def test_healthcheck_auto_reconciles_to_healthy_stable_when_listener_is_live(self) -> None:
        stable_port = free_port()
        ProbeHandler.response_text = "OK"
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        (self.managed_dir / "managed-proxy.pid").write_text("999999\n", encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
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
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["endpoint"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertTrue(payload["attestation"]["listener_ok"])
        self.assertTrue(payload["attestation"]["base_url_match"])
        self.assertTrue(payload["attestation"]["effective_mode_match"])
        self.assertIn("reconciled to", payload["last_error"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["effective_mode"], "stable")
        self.assertEqual(state["selected_backend_ids"], [])
        self.assertFalse((self.managed_dir / "managed-proxy.pid").exists())
        effective_mode_text = (
            self.profile_dir / "runtime-effective-mode.txt"
        ).read_text(encoding="utf-8").strip()
        self.assertEqual(
            effective_mode_text,
            "stable",
        )
        self.assertEqual(
            (self.profile_dir / "config.toml").read_text(encoding="utf-8").split('base_url = "', 1)[1].split('"', 1)[0],
            f"http://127.0.0.1:{stable_port}/v1",
        )

    def test_healthcheck_reconciles_stable_artifact_with_stale_managed_state(self) -> None:
        stable_port = free_port()
        ProbeHandler.response_text = "OK"
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{stable_port}/v1"\n',
            encoding="utf-8",
        )
        (self.managed_dir / "managed-proxy.pid").write_text("999999\n", encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
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
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["endpoint"], f"http://127.0.0.1:{stable_port}/v1")
        self.assertTrue(payload["attestation"]["effective_mode_match"])
        self.assertTrue(payload["attestation"]["base_url_match"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["effective_mode"], "stable")
        self.assertEqual(state["selected_backend_ids"], [])
        self.assertFalse((self.managed_dir / "managed-proxy.pid").exists())

    def test_healthcheck_requires_effective_mode_artifact(self) -> None:
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
        (self.profile_dir / "runtime-effective-mode.txt").unlink()
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
        self.assertIn("runtime-effective-mode", payload["last_error"])

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
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["endpoint"], "http://127.0.0.1:8318/v1")
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        self.assertEqual(result.stderr.strip(), "sync-ran")

    def test_sync_reports_config_toml_change_when_external_sync_promotes_base_url(self) -> None:
        port = free_port()
        sync_script = self.profile_dir / "sync-promotes-base-url.sh"
        sync_script.write_text(
            "#!/bin/sh\n"
            "python3 - <<'PY' >/dev/null 2>&1 &\n"
            "import os\n"
            "import socket\n"
            "import time\n"
            "port = int(os.environ['WBP_TEST_MANAGED_PORT'])\n"
            "sock = socket.socket()\n"
            "sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
            "sock.bind(('127.0.0.1', port))\n"
            "sock.listen(1)\n"
            "time.sleep(10)\n"
            "sock.close()\n"
            "PY\n"
            "sleep 0.1\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            "from pathlib import Path\n"
            "port = os.environ['WBP_TEST_MANAGED_PORT']\n"
            "state_path = Path(os.environ['WBP_STATE_FILE'])\n"
            "state = json.loads(state_path.read_text())\n"
            "state['effective_mode'] = 'managed'\n"
            "state['status'] = 'healthy'\n"
            "state['last_error'] = ''\n"
            "state['managed_port'] = int(port)\n"
            "state_path.write_text(json.dumps(state) + '\\n')\n"
            "Path(os.environ['WBP_RUNTIME_EFFECTIVE_MODE_FILE']).write_text('managed\\n')\n"
            "Path(os.environ['WBP_MANAGED_CONFIG_FILE']).write_text(f'host: 127.0.0.1\\nport: {port}\\n')\n"
            "config_path = Path(os.environ['WBP_CONFIG_TOML'])\n"
            "lines = config_path.read_text().splitlines()\n"
            "out = []\n"
            "for line in lines:\n"
            "    if line.strip().startswith('base_url = '):\n"
            "        out.append(f'base_url = \\\"http://127.0.0.1:{port}/v1\\\"')\n"
            "    else:\n"
            "        out.append(line)\n"
            "config_path.write_text('\\n'.join(out) + '\\n')\n"
            "PY\n"
            "echo sync-promoted >&2\n",
            encoding="utf-8",
        )
        sync_script.chmod(0o755)
        env = self.env()
        env["WBP_SYNC_SCRIPT"] = str(sync_script)
        env["WBP_TEST_MANAGED_PORT"] = str(port)
        result = subprocess.run(
            ["python3", "-m", "wild_boar_proxy", "sync", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["endpoint"], f"http://127.0.0.1:{port}/v1")
        self.assertIn(str(self.profile_dir / "config.toml"), payload["changed_files"])
        self.assertEqual(result.stderr.strip(), "sync-promoted")

    def test_mode_get_reports_stable_when_managed_listener_is_absent(self) -> None:
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "managed"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        result = self.run_cli("mode", "get", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["desired_mode"], "stable")
        self.assertEqual(payload["effective_mode"], "stable")

    def test_mode_set_respects_serialized_lock(self) -> None:
        lock_file = self.managed_dir / "wild-boar-proxy.lock"
        lock_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
        result = self.run_cli("mode", "set", "stable", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["machine_error_code"], "LOCK_HELD")
        self.assertEqual(payload["next_action"], "retry")

    def test_launch_smoke_wraps_external_launcher_and_reports_fallback(self) -> None:
        stable_port = free_port()
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli("launch", "smoke", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["launch_mode"], "smoke")
        self.assertEqual(payload["desired_mode"], "managed")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["launcher_exit_code"], 0)
        self.assertIn(str(self.profile_dir / "config.toml"), payload["changed_files"])
        self.assertIn(
            str(self.profile_dir / "runtime-effective-mode.txt"), payload["changed_files"]
        )

    def test_launch_smoke_reports_missing_launcher(self) -> None:
        self.launcher_script.unlink()
        result = self.run_cli("launch", "smoke", "--json")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "MISSING_LAUNCHER_SCRIPT")

    def test_launch_smoke_reports_nonzero_launcher_even_if_runtime_is_healthy(self) -> None:
        stable_port = free_port()
        nonzero_launcher = self.profile_dir / "codex-custom-launch-nonzero.sh"
        nonzero_launcher.write_text(
            "#!/bin/sh\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "printf 'stable\\n' > \"$WBP_RUNTIME_EFFECTIVE_MODE_FILE\"\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            "from pathlib import Path\n"
            "state_path = Path(os.environ['WBP_STATE_FILE'])\n"
            "state = json.loads(state_path.read_text())\n"
            "state['effective_mode'] = 'stable'\n"
            "state['status'] = 'healthy'\n"
            "state['last_error'] = ''\n"
            "state_path.write_text(json.dumps(state) + '\\n')\n"
            "config_path = Path(os.environ['WBP_CONFIG_TOML'])\n"
            "lines = config_path.read_text().splitlines()\n"
            "out = []\n"
            "for line in lines:\n"
            "    if line.strip().startswith('base_url = '):\n"
            "        out.append(f'base_url = \\\"http://127.0.0.1:{os.environ[\\'WBP_TEST_STABLE_PORT\\']}/v1\\\"')\n"
            "    else:\n"
            "        out.append(line)\n"
            "config_path.write_text('\\n'.join(out) + '\\n')\n"
            "PY\n"
            "exit 9\n",
            encoding="utf-8",
        )
        nonzero_launcher.chmod(0o755)
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = self.env()
            env["WBP_LAUNCHER_SCRIPT"] = str(nonzero_launcher)
            env["WBP_TEST_STABLE_PORT"] = str(stable_port)
            result = subprocess.run(
                ["python3", "-m", "wild_boar_proxy", "launch", "smoke", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 9, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LAUNCHER_EXIT_NONZERO")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(payload["launcher_exit_code"], 9)

    def test_launch_smoke_requires_managed_stability_window(self) -> None:
        port = free_port()
        stable_port = free_port()
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        one_shot_launcher = self.profile_dir / "codex-custom-launch-one-shot.sh"
        one_shot_launcher.write_text(
            "#!/bin/sh\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "PORT=\"$WBP_TEST_MANAGED_PORT\"\n"
            "python3 - <<'PY' >/dev/null 2>&1 &\n"
            "import json\n"
            "import os\n"
            "import threading\n"
            "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
            "port = int(os.environ['WBP_TEST_MANAGED_PORT'])\n"
            "class Handler(BaseHTTPRequestHandler):\n"
            "    count = 0\n"
            "    def do_GET(self):\n"
            "        if self.path == '/v1/models':\n"
            "            body = json.dumps({'data': [{'id': 'gpt-5.4'}]}).encode('utf-8')\n"
            "            self.send_response(200)\n"
            "            self.send_header('Content-Type', 'application/json')\n"
            "            self.send_header('Content-Length', str(len(body)))\n"
            "            self.end_headers()\n"
            "            self.wfile.write(body)\n"
            "            Handler.count += 1\n"
            "            if Handler.count >= 2:\n"
            "                threading.Thread(target=self.server.shutdown, daemon=True).start()\n"
            "            return\n"
            "        self.send_error(404)\n"
            "    def do_POST(self):\n"
            "        if self.path == '/v1/responses':\n"
            "            length = int(self.headers.get('Content-Length', '0'))\n"
            "            _ = self.rfile.read(length)\n"
            "            body = json.dumps({'output_text': 'OK'}).encode('utf-8')\n"
            "            self.send_response(200)\n"
            "            self.send_header('Content-Type', 'application/json')\n"
            "            self.send_header('Content-Length', str(len(body)))\n"
            "            self.end_headers()\n"
            "            self.wfile.write(body)\n"
            "            Handler.count += 1\n"
            "            if Handler.count >= 2:\n"
            "                threading.Thread(target=self.server.shutdown, daemon=True).start()\n"
            "            return\n"
            "        self.send_error(404)\n"
            "    def log_message(self, fmt, *args):\n"
            "        return\n"
            "server = ThreadingHTTPServer(('127.0.0.1', port), Handler)\n"
            "server.serve_forever()\n"
            "server.server_close()\n"
            "PY\n"
            "sleep 0.1\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            "from pathlib import Path\n"
            "port = os.environ['WBP_TEST_MANAGED_PORT']\n"
            "state_path = Path(os.environ['WBP_STATE_FILE'])\n"
            "state = json.loads(state_path.read_text())\n"
            "state['effective_mode'] = 'managed'\n"
            "state['managed_port'] = int(port)\n"
            "state['status'] = 'healthy'\n"
            "state['last_error'] = ''\n"
            "state_path.write_text(json.dumps(state) + '\\n')\n"
            "Path(os.environ['WBP_RUNTIME_EFFECTIVE_MODE_FILE']).write_text('managed\\n')\n"
            "Path(os.environ['WBP_MANAGED_CONFIG_FILE']).write_text(f'host: 127.0.0.1\\nport: {port}\\n')\n"
            "config_path = Path(os.environ['WBP_CONFIG_TOML'])\n"
            "lines = config_path.read_text().splitlines()\n"
            "out = []\n"
            "for line in lines:\n"
            "    if line.strip().startswith('base_url = '):\n"
            "        out.append(f'base_url = \\\"http://127.0.0.1:{port}/v1\\\"')\n"
            "    else:\n"
            "        out.append(line)\n"
            "config_path.write_text('\\n'.join(out) + '\\n')\n"
            "PY\n",
            encoding="utf-8",
        )
        one_shot_launcher.chmod(0o755)
        env = self.env()
        env["WBP_LAUNCHER_SCRIPT"] = str(one_shot_launcher)
        env["WBP_LAUNCH_STABILIZATION_SECONDS"] = "0.2"
        env["WBP_TEST_MANAGED_PORT"] = str(port)
        result = subprocess.run(
            ["python3", "-m", "wild_boar_proxy", "launch", "smoke", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "PROXY_REPROBE_FAILED")
        self.assertEqual(payload["effective_mode"], "managed")
        self.assertIn("Connection refused", payload["last_error"])


if __name__ == "__main__":
    unittest.main()
