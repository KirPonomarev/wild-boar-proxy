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

    def run_cli_with_env(
        self, env_overrides: dict[str, str], *args: str
    ) -> subprocess.CompletedProcess[str]:
        env = self.env()
        env.update(env_overrides)
        return subprocess.run(
            ["python3", "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def state_snapshot(self) -> dict[str, str]:
        repair_target_dir = self.managed_dir / "stable-repair-target"
        paths = [
            self.stable_dir / "config.yaml",
            self.managed_dir / "backend-registry.json",
            self.managed_dir / "supervisor-state.json",
            self.managed_dir / "approved-repair-target.json",
            self.managed_dir / "target-switch-transaction.json",
            self.profile_dir / "config.toml",
            self.profile_dir / "runtime-mode.txt",
            self.profile_dir / "runtime-effective-mode.txt",
        ]
        snapshot = {
            str(path): path.read_text(encoding="utf-8")
            for path in paths
            if path.exists()
        }
        snapshot[f"DIR:{repair_target_dir}"] = (
            json.dumps(sorted(path.name for path in repair_target_dir.iterdir()))
            if repair_target_dir.is_dir()
            else "__MISSING__"
        )
        for path in sorted(self.stable_dir.glob("codex-*.json")):
            snapshot[str(path)] = path.read_text(encoding="utf-8")
        for path in sorted(repair_target_dir.glob("codex-*.json")):
            snapshot[str(path)] = path.read_text(encoding="utf-8")
        return snapshot

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
        self.assertNotIn("policy_drift", payload)
        self.assertNotIn("registry_identity", payload)
        self.assertNotIn("claim_gate", payload)
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
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        self.assertEqual(payload["policy_drift"]["status"], "clear")
        self.assertEqual(payload["policy_drift"]["machine_error_code"], "OK")
        self.assertEqual(payload["policy_drift"]["missing_auths"], [])
        self.assertEqual(
            payload["policy_drift"]["stable_auth_inventory_source"]["source"],
            "stable_config_parent",
        )
        self.assertEqual(
            payload["policy_drift"]["stable_auth_inventory_source"]["path_resolution"],
            "fallback",
        )
        self.assertTrue(payload["policy_drift"]["stable_auth_inventory_source"]["exists"])
        self.assertEqual(payload["registry_identity_summary"]["status"], "clear")
        self.assertEqual(payload["registry_identity_summary"]["machine_error_code"], "OK")
        self.assertEqual(payload["claim_gate"]["status"], "clear")
        self.assertEqual(payload["claim_gate"]["machine_error_code"], "OK")
        self.assertEqual(payload["claim_gate"]["blocked_claims"], [])
        self.assertEqual(payload["claim_gate"]["sources"], [])
        self.assertEqual(payload["claim_gate"]["next_action"], "none")

    def test_status_reports_stable_policy_drift_without_greenwash(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        stable_auth = self.stable_dir / "codex-reserve.json"
        stable_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                "id": "reserve-backend",
                "label": "Reserve Backend",
                "pool": "reserve",
                "status": "healthy",
                "manual_hold": True,
                "auth_ref": str(stable_auth),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            }
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["liveness"], "healthy")
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "detected")
        self.assertEqual(drift["machine_error_code"], "STABLE_POLICY_DRIFT")
        self.assertEqual(drift["stable_auth_inventory_count"], 1)
        self.assertEqual(drift["allowed_stable_auth_count"], 0)
        self.assertEqual(drift["stable_auth_inventory_source"]["source"], "stable_config_parent")
        self.assertEqual(drift["stable_auth_inventory_source"]["path_resolution"], "fallback")
        self.assertTrue(drift["stable_auth_inventory_source"]["exists"])
        self.assertEqual(
            drift["disallowed_configured_auths"][0]["backend_id"],
            "reserve-backend",
        )
        self.assertEqual(
            drift["disallowed_configured_auths"][0]["auth_basename"],
            "codex-reserve.json",
        )
        self.assertEqual(drift["missing_auths"], [])
        self.assertIn("stable-15-proved", drift["claim_blockers"])
        self.assertEqual(payload["claim_gate"]["status"], "blocked")
        self.assertEqual(payload["claim_gate"]["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertIn("stable-15-proved", payload["claim_gate"]["blocked_claims"])
        self.assertEqual(payload["claim_gate"]["sources"], ["policy_drift"])

    def test_status_reports_missing_allowed_stable_auth_drift(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        missing_auth = self.stable_dir / "codex-missing.json"
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(missing_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        self.assertEqual(payload["machine_error_code"], "OK")
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "detected")
        self.assertEqual(drift["machine_error_code"], "STABLE_POLICY_DRIFT")
        self.assertEqual(drift["missing_auths"][0]["backend_id"], "backend-a")
        self.assertEqual(
            drift["missing_auths"][0]["auth_basename"],
            "codex-missing.json",
        )
        self.assertEqual(
            drift["missing_auths"][0]["reason"],
            "auth_ref_not_in_stable_inventory",
        )
        self.assertEqual(payload["claim_gate"]["status"], "blocked")
        self.assertEqual(payload["claim_gate"]["sources"], ["policy_drift"])

    def test_status_uses_stable_auth_dir_for_policy_drift_inventory(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        auth_dir = self.temp_dir.name and Path(self.temp_dir.name) / "stable-auth-dir"
        auth_dir.mkdir()
        active_auth = auth_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{auth_dir}"\n',
            encoding="utf-8",
        )
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "clear")
        self.assertEqual(drift["stable_auth_inventory_count"], 1)
        self.assertEqual(drift["stable_auth_inventory_source"]["source"], "auth-dir")
        self.assertEqual(drift["stable_auth_inventory_source"]["path"], str(auth_dir))
        self.assertEqual(drift["stable_auth_inventory_source"]["path_resolution"], "absolute")
        self.assertTrue(drift["stable_auth_inventory_source"]["exists"])

    def test_status_reports_drift_from_stable_auth_dir_inventory(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        auth_dir = Path(self.temp_dir.name) / "stable-auth-dir"
        auth_dir.mkdir()
        stable_auth = auth_dir / "codex-reserve.json"
        stable_auth.write_text("{}", encoding="utf-8")
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{auth_dir}"\n',
            encoding="utf-8",
        )
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                "id": "reserve-backend",
                "label": "Reserve Backend",
                "pool": "reserve",
                "status": "healthy",
                "manual_hold": True,
                "auth_ref": str(stable_auth),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            }
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "detected")
        self.assertEqual(drift["stable_auth_inventory_source"]["source"], "auth-dir")
        self.assertEqual(
            drift["disallowed_configured_auths"][0]["auth_basename"],
            "codex-reserve.json",
        )

    def test_status_resolves_relative_stable_auth_dir_from_config_parent(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        auth_dir = self.stable_dir / "auth"
        auth_dir.mkdir()
        active_auth = auth_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 8318\nauth-dir: \"auth\"\n",
            encoding="utf-8",
        )
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        source = payload["policy_drift"]["stable_auth_inventory_source"]
        self.assertEqual(source["source"], "auth-dir")
        self.assertEqual(source["path"], "auth")
        self.assertEqual(source["path_resolution"], "stable_config_parent")
        self.assertTrue(source["exists"])

    def test_status_reports_unknown_when_stable_auth_dir_is_missing(self) -> None:
        missing_dir = self.stable_dir / "missing-auth"
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{missing_dir}"\n',
            encoding="utf-8",
        )
        result = self.run_cli("status", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "unknown")
        self.assertEqual(drift["machine_error_code"], "STABLE_POLICY_DRIFT_UNKNOWN")
        self.assertEqual(drift["stable_auth_inventory_source"]["source"], "auth-dir")
        self.assertFalse(drift["stable_auth_inventory_source"]["exists"])

    def test_stable_repair_dry_run_reports_not_needed_without_mutation(self) -> None:
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_NOT_NEEDED")
        self.assertFalse(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        plan = payload["transaction_plan"]
        self.assertEqual(plan["mode"], "dry_run")
        self.assertTrue(plan["snapshot_required"])
        self.assertTrue(plan["lock_required"])
        self.assertEqual(plan["lock_preflight"]["status"], "available")
        self.assertEqual(plan["would_add"], [])
        self.assertEqual(plan["would_remove"], [])
        self.assertEqual(plan["would_keep"][0]["auth_basename"], "codex-active.json")

    def test_stable_repair_dry_run_reports_disallowed_auth_plan(self) -> None:
        stable_auth = self.stable_dir / "codex-reserve.json"
        stable_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                "id": "reserve-backend",
                "label": "Reserve Backend",
                "pool": "reserve",
                "status": "healthy",
                "manual_hold": True,
                "auth_ref": str(stable_auth),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            }
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertTrue(payload["would_change"])
        self.assertEqual(payload["next_action"], "review_transaction_plan")
        self.assertEqual(payload["changed_files"], [])
        plan = payload["transaction_plan"]
        self.assertEqual(plan["disallowed_auths"][0]["auth_basename"], "codex-reserve.json")
        self.assertEqual(plan["would_remove"][0]["auth_basename"], "codex-reserve.json")
        self.assertEqual(plan["would_add"], [])

    def test_stable_repair_dry_run_reports_missing_allowed_auth_plan(self) -> None:
        missing_auth = self.stable_dir / "codex-missing.json"
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(missing_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertTrue(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        plan = payload["transaction_plan"]
        self.assertEqual(plan["missing_auths"][0]["auth_basename"], "codex-missing.json")
        self.assertEqual(plan["would_add"][0]["auth_basename"], "codex-missing.json")
        self.assertEqual(plan["would_remove"], [])

    def test_stable_repair_dry_run_blocks_ambiguous_registry(self) -> None:
        auth_a = self.stable_dir / "codex-a.json"
        auth_b = self.stable_dir / "codex-b.json"
        auth_a.write_text("{}", encoding="utf-8")
        auth_b.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                **registry["backends"][0],
                "id": "duplicate-backend",
                "auth_ref": str(auth_a),
            },
            {
                **registry["backends"][0],
                "id": "duplicate-backend",
                "auth_ref": str(auth_b),
            },
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "REGISTRY_IDENTITY_AMBIGUOUS")
        self.assertFalse(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["next_action"], "inspect_registry_identity")
        self.assertEqual(
            payload["transaction_plan"]["blocked_reasons"][0]["machine_error_code"],
            "REGISTRY_IDENTITY_AMBIGUOUS",
        )

    def test_stable_repair_dry_run_blocks_missing_stable_auth_dir(self) -> None:
        missing_dir = self.stable_dir / "missing-auth"
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{missing_dir}"\n',
            encoding="utf-8",
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "STABLE_AUTH_DIR_MISSING")
        self.assertFalse(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse(
            payload["transaction_plan"]["stable_auth_inventory_source"]["exists"]
        )

    def test_stable_repair_dry_run_blocks_held_lock_without_mutation(self) -> None:
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        (self.managed_dir / "wild-boar-proxy.lock").write_text(
            f"{os.getpid()}\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "LOCK_HELD")
        self.assertFalse(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["transaction_plan"]["lock_preflight"]["status"], "held")

    def test_stable_repair_dry_run_blocks_stale_lock_without_mutation(self) -> None:
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        (self.managed_dir / "wild-boar-proxy.lock").write_text(
            "not-a-pid\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_DRY_RUN_BLOCKED")
        self.assertFalse(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["next_action"], "inspect_stale_lock")
        self.assertEqual(payload["transaction_plan"]["lock_preflight"]["status"], "stale")

    def test_stable_target_switch_dry_run_returns_contract_without_mutation(self) -> None:
        before = self.state_snapshot()
        result = self.run_cli("stable", "target", "switch", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "TARGET_SWITCH_CONTRACT_READY")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["command_mode"], "dry_run")
        self.assertEqual(payload["operator_action"], "user_action")
        self.assertEqual(payload["next_action"], "review_target_switch_contract")
        self.assertTrue(payload["write_surface_declared"])
        self.assertEqual(payload["target_surface"]["status"], "declared_review_only")
        self.assertEqual(
            payload["target_surface"]["observed_stable_inventory_source"]["source"],
            "stable_config_parent",
        )
        approved_target = payload["target_surface"]["approved_repair_target_reference"]
        self.assertEqual(
            approved_target["target_identity"], "companion_managed_stable_auth_inventory"
        )
        self.assertEqual(approved_target["target_kind"], "control_owned_inventory_path")
        self.assertEqual(
            approved_target["inventory_dir"],
            str(self.managed_dir / "stable-repair-target"),
        )
        self.assertEqual(
            approved_target["reference_file"],
            str(self.managed_dir / "approved-repair-target.json"),
        )
        self.assertEqual(approved_target["ownership"], "control_layer")
        self.assertFalse(approved_target["reference_file_exists"])
        self.assertFalse(approved_target["inventory_dir_exists"])
        transaction_surface = payload["target_surface"][
            "target_switch_transaction_metadata_surface"
        ]
        self.assertEqual(
            transaction_surface["transaction_file"],
            str(self.managed_dir / "target-switch-transaction.json"),
        )
        self.assertEqual(transaction_surface["status"], "reserved_not_materialized")
        self.assertEqual(transaction_surface["ownership"], "control_layer")
        self.assertFalse(transaction_surface["transaction_file_exists"])
        self.assertEqual(
            payload["declared_write_surfaces"],
            [
                "approved_control_target_reference_surface",
                "target_switch_transaction_metadata",
            ],
        )
        self.assertIn("~/.cli-proxy-api", payload["forbidden_surfaces"])
        self.assertEqual(
            payload["transaction_phases"],
            ["snapshot", "stage", "verify", "switch", "rollback"],
        )
        self.assertEqual(
            payload["verify_scope"],
            [
                "target_reference_correctness",
                "switch_completion_only",
                "transaction_completeness",
            ],
        )
        self.assertFalse(payload["target_surface"]["mode_set_is_target_switch"])

    def test_stable_target_switch_apply_returns_blocker_without_mutation(self) -> None:
        before = self.state_snapshot()
        result = self.run_cli("stable", "target", "switch", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "TARGET_SWITCH_NOT_IMPLEMENTED")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["command_mode"], "apply")
        self.assertEqual(payload["operator_action"], "user_action")
        self.assertTrue(payload["write_surface_declared"])
        approved_target = payload["target_surface"]["approved_repair_target_reference"]
        self.assertEqual(
            approved_target["reference_file"],
            str(self.managed_dir / "approved-repair-target.json"),
        )
        self.assertIn("~/.cli-proxy-api", payload["forbidden_surfaces"])
        self.assertEqual(payload["next_action"], "inspect_target_switch_contract")

    def test_stable_target_switch_contract_ignores_override_alias_attempts(self) -> None:
        result = self.run_cli_with_env(
            {
                "WBP_REPAIR_TARGET_INVENTORY_DIR": str(self.stable_dir),
                "WBP_REPAIR_TARGET_REFERENCE_FILE": str(
                    self.managed_dir / "backend-registry.json"
                ),
                "WBP_TARGET_SWITCH_TRANSACTION_FILE": str(
                    self.managed_dir / "supervisor-state.json"
                ),
            },
            "stable",
            "target",
            "switch",
            "--dry-run",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        approved_target = payload["target_surface"]["approved_repair_target_reference"]
        self.assertEqual(
            approved_target["inventory_dir"],
            str(self.managed_dir / "stable-repair-target"),
        )
        self.assertEqual(
            approved_target["reference_file"],
            str(self.managed_dir / "approved-repair-target.json"),
        )
        transaction_surface = payload["target_surface"][
            "target_switch_transaction_metadata_surface"
        ]
        self.assertEqual(
            transaction_surface["transaction_file"],
            str(self.managed_dir / "target-switch-transaction.json"),
        )

    def test_stable_repair_dry_run_reports_approved_target_separately(self) -> None:
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        plan = payload["transaction_plan"]
        self.assertEqual(plan["stable_auth_inventory_source"]["source"], "stable_config_parent")
        approved_target = plan["approved_repair_target_reference"]
        self.assertEqual(
            approved_target["target_identity"], "companion_managed_stable_auth_inventory"
        )
        self.assertEqual(
            approved_target["inventory_dir"],
            str(self.managed_dir / "stable-repair-target"),
        )
        self.assertEqual(
            approved_target["reference_file"],
            str(self.managed_dir / "approved-repair-target.json"),
        )
        transaction_surface = plan["target_switch_transaction_metadata_surface"]
        self.assertEqual(
            transaction_surface["transaction_file"],
            str(self.managed_dir / "target-switch-transaction.json"),
        )
        self.assertNotEqual(
            plan["stable_auth_inventory_source"]["path"],
            approved_target["inventory_dir"],
        )

    def test_stable_repair_dry_run_does_not_leak_to_other_json_surfaces(self) -> None:
        for args in (
            ("status", "--json"),
            ("healthcheck", "--json"),
            ("accounts", "list", "--json"),
        ):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                payload = json.loads(result.stdout)
                self.assertNotIn("transaction_plan", payload)
                self.assertNotIn("would_change", payload)

    def test_stable_target_switch_does_not_leak_to_other_json_surfaces(self) -> None:
        for args in (
            ("status", "--json"),
            ("healthcheck", "--json"),
            ("accounts", "list", "--json"),
            ("stable", "repair", "--dry-run", "--json"),
        ):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                payload = json.loads(result.stdout)
                self.assertNotIn("target_surface", payload)
                self.assertNotIn("write_surface_declared", payload)
                self.assertNotIn("declared_write_surfaces", payload)
                self.assertNotIn("forbidden_surfaces", payload)
                self.assertNotIn("verify_scope", payload)

    def test_status_reports_disabled_retired_down_stable_auth_drift(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        stable_auths = {
            "disabled-backend": self.stable_dir / "codex-disabled.json",
            "retired-backend": self.stable_dir / "codex-retired.json",
            "down-backend": self.stable_dir / "codex-down.json",
        }
        for stable_auth in stable_auths.values():
            stable_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                "id": "disabled-backend",
                "label": "Disabled Backend",
                "pool": "active",
                "status": "healthy",
                "enabled": False,
                "manual_hold": False,
                "auth_ref": str(stable_auths["disabled-backend"]),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
            {
                "id": "retired-backend",
                "label": "Retired Backend",
                "pool": "retired",
                "status": "retired",
                "manual_hold": False,
                "auth_ref": str(stable_auths["retired-backend"]),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
            {
                "id": "down-backend",
                "label": "Down Backend",
                "pool": "active",
                "status": "down",
                "manual_hold": False,
                "auth_ref": str(stable_auths["down-backend"]),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "detected")
        self.assertEqual(drift["missing_auths"], [])
        reasons_by_backend = {
            item["backend_id"]: item["reason"]
            for item in drift["disallowed_configured_auths"]
        }
        self.assertIn("disabled", reasons_by_backend["disabled-backend"])
        self.assertIn("pool_not_active", reasons_by_backend["retired-backend"])
        self.assertIn("status_not_allowed", reasons_by_backend["down-backend"])

    def test_status_reports_unknown_stable_auth_as_policy_drift(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        (self.stable_dir / "codex-unknown.json").write_text("{}", encoding="utf-8")
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
        drift = payload["policy_drift"]
        self.assertEqual(drift["status"], "detected")
        self.assertEqual(drift["unknown_auths"], ["codex-unknown.json"])
        self.assertEqual(drift["machine_error_code"], "STABLE_POLICY_DRIFT")

    def test_status_claim_gate_blocks_registry_identity_ambiguity_without_full_dump(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        duplicate = dict(registry["backends"][0])
        duplicate["id"] = "backend-b"
        duplicate["auth_ref"] = "/tmp/other/codex-active.json"
        registry["backends"].append(duplicate)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["policy_drift"]["status"], "clear")
        self.assertEqual(payload["registry_identity_summary"]["status"], "ambiguous")
        self.assertEqual(
            payload["registry_identity_summary"]["machine_error_code"],
            "REGISTRY_IDENTITY_AMBIGUOUS",
        )
        self.assertEqual(payload["claim_gate"]["status"], "blocked")
        self.assertEqual(payload["claim_gate"]["sources"], ["registry_identity"])
        self.assertNotIn("duplicate_backend_ids", payload["registry_identity_summary"])
        self.assertNotIn("duplicate_auth_basenames", payload["registry_identity_summary"])

    def test_status_claim_gate_reports_both_blocking_sources(self) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        stable_auth = self.stable_dir / "codex-reserve.json"
        stable_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                "id": "reserve-backend",
                "label": "Reserve Backend",
                "pool": "reserve",
                "status": "healthy",
                "manual_hold": True,
                "auth_ref": str(stable_auth),
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
            {
                "id": "active-backend-a",
                "label": "Active Backend A",
                "pool": "active",
                "status": "healthy",
                "manual_hold": False,
                "auth_ref": "/tmp/one/codex-duplicate.json",
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
            {
                "id": "active-backend-b",
                "label": "Active Backend B",
                "pool": "active",
                "status": "healthy",
                "manual_hold": False,
                "auth_ref": "/tmp/two/codex-duplicate.json",
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
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
        self.assertEqual(payload["policy_drift"]["status"], "detected")
        self.assertEqual(payload["registry_identity_summary"]["status"], "ambiguous")
        self.assertEqual(payload["claim_gate"]["status"], "blocked")
        self.assertEqual(
            payload["claim_gate"]["sources"],
            ["policy_drift", "registry_identity"],
        )

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
        self.assertIn("claim_gate", payload)
        self.assertNotEqual(payload["machine_error_code"], payload["claim_gate"]["machine_error_code"])

    def test_accounts_list_returns_registry_snapshot(self) -> None:
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["accounts"][0]["id"], "backend-a")
        self.assertEqual(payload["registry_identity"]["status"], "clear")
        self.assertEqual(payload["registry_identity"]["machine_error_code"], "OK")
        self.assertEqual(payload["registry_identity"]["next_action"], "none")
        self.assertNotIn("claim_gate", payload)

    def test_accounts_list_reports_duplicate_backend_id_identity_ambiguity(self) -> None:
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        duplicate = dict(registry["backends"][0])
        duplicate["auth_ref"] = "/tmp/b.json"
        registry["backends"].append(duplicate)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        identity = payload["registry_identity"]
        self.assertEqual(identity["status"], "ambiguous")
        self.assertEqual(identity["machine_error_code"], "REGISTRY_IDENTITY_AMBIGUOUS")
        self.assertEqual(identity["duplicate_backend_ids"], ["backend-a"])
        self.assertIn("stable-15-proved", identity["claim_blockers"])

    def test_accounts_list_reports_duplicate_auth_basename_identity_ambiguity(self) -> None:
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = "/tmp/one/codex-duplicate.json"
        duplicate = dict(registry["backends"][0])
        duplicate["id"] = "backend-b"
        duplicate["auth_ref"] = "/tmp/two/codex-duplicate.json"
        registry["backends"].append(duplicate)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        identity = payload["registry_identity"]
        self.assertEqual(identity["status"], "ambiguous")
        self.assertEqual(identity["duplicate_auth_basenames"], ["codex-duplicate.json"])

    def test_accounts_list_reports_missing_auth_ref_identity_ambiguity(self) -> None:
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        del registry["backends"][0]["auth_ref"]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        identity = payload["registry_identity"]
        self.assertEqual(identity["status"], "ambiguous")
        self.assertEqual(identity["missing_auth_refs"], ["backend-a"])

    def test_accounts_list_reports_empty_auth_ref_identity_ambiguity(self) -> None:
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = "   "
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        identity = payload["registry_identity"]
        self.assertEqual(identity["status"], "ambiguous")
        self.assertEqual(identity["empty_auth_ref_backends"], ["backend-a"])

    def test_accounts_list_reports_invalid_auth_basename_identity_ambiguity(self) -> None:
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = "/"
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        result = self.run_cli("accounts", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        identity = payload["registry_identity"]
        self.assertEqual(identity["status"], "ambiguous")
        self.assertEqual(identity["invalid_auth_basenames"], ["backend-a"])

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
