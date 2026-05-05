from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from wild_boar_proxy import runtime as runtime_mod


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
        ProbeHandler.response_text = "OK"
        ProbeHandler.response_status = 200
        ProbeHandler.response_payload = None
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
        self.default_launcher_script = (
            self.profile_dir / runtime_mod.DEFAULT_LAUNCHER_SCRIPT_NAME
        )
        self.launcher_script = self.profile_dir / "codex-custom-launch-override.sh"
        self.write_recording_stable_launcher(self.launcher_script)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self, *, include_launcher_override: bool = True) -> dict[str, str]:
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
        if include_launcher_override:
            env["WBP_LAUNCHER_SCRIPT"] = str(self.launcher_script)
        else:
            env.pop("WBP_LAUNCHER_SCRIPT", None)
        env["WBP_LAUNCH_STABILIZATION_SECONDS"] = "0"
        env["WBP_SYNC_SCRIPT"] = str(self.sync_script)
        return env

    def run_cli(
        self, *args: str, include_launcher_override: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(include_launcher_override=include_launcher_override),
            text=True,
            capture_output=True,
            check=False,
        )

    def run_cli_with_env(
        self,
        env_overrides: dict[str, str],
        *args: str,
        include_launcher_override: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = self.env(include_launcher_override=include_launcher_override)
        env.update(env_overrides)
        return subprocess.run(
            ["python3", "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_sanitized_env_removes_ambient_proxy_variables(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://example.invalid:1",
                "HTTPS_PROXY": "http://example.invalid:2",
                "ALL_PROXY": "http://example.invalid:3",
                "http_proxy": "http://example.invalid:4",
                "https_proxy": "http://example.invalid:5",
                "all_proxy": "http://example.invalid:6",
                "WBP_CURRENT_PROXY_URL": "http://example.invalid:7",
            },
            clear=True,
        ):
            env = runtime_mod.sanitized_env()
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "WBP_CURRENT_PROXY_URL",
        ):
            self.assertNotIn(key, env)
        self.assertEqual(env["NO_PROXY"], "127.0.0.1,localhost,::1")
        self.assertEqual(env["no_proxy"], env["NO_PROXY"])

    def state_snapshot(self) -> dict[str, str]:
        repair_target_dir = self.managed_dir / "stable-repair-target"
        paths = [
            self.stable_dir / "config.yaml",
            self.managed_dir / "backend-registry.json",
            self.managed_dir / "supervisor-state.json",
            self.managed_dir / "approved-repair-target.json",
            self.managed_dir / "target-switch-transaction.json",
            self.managed_dir / "stable-runtime-config.generated.yaml",
            self.profile_dir / "config.toml",
            self.profile_dir / "runtime-mode.txt",
            self.profile_dir / "runtime-effective-mode.txt",
        ]
        snapshot = {}
        for path in paths:
            if not path.exists():
                continue
            if path.is_dir():
                snapshot[str(path)] = json.dumps(
                    {
                        "kind": "dir",
                        "entries": sorted(entry.name for entry in path.iterdir()),
                    }
                )
                continue
            snapshot[str(path)] = path.read_text(encoding="utf-8")
        snapshot[f"DIR:{repair_target_dir}"] = (
            json.dumps(sorted(path.name for path in repair_target_dir.iterdir()))
            if repair_target_dir.is_dir()
            else "__MISSING__"
        )
        snapshot[f"DIR_GLOB:{self.managed_dir}/.stable-repair-*"] = json.dumps(
            sorted(path.name for path in self.managed_dir.glob(".stable-repair-*"))
        )
        for path in sorted(self.stable_dir.glob("codex-*.json")):
            snapshot[str(path)] = path.read_text(encoding="utf-8")
        for path in sorted(repair_target_dir.glob("codex-*.json")):
            snapshot[str(path)] = path.read_text(encoding="utf-8")
        return snapshot

    def write_recording_stable_launcher(
        self, path: Path, *, exit_code: int = 0, start_server: bool = False
    ) -> Path:
        server_block = ""
        if start_server:
            server_block = (
                "python3 - <<'PY' >/dev/null 2>&1 &\n"
                "import json\n"
                "import os\n"
                "import threading\n"
                "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
                "from pathlib import Path\n"
                "stable_config = Path(os.environ['WBP_STABLE_CONFIG'])\n"
                "port = 8318\n"
                "for raw_line in stable_config.read_text().splitlines():\n"
                "    line = raw_line.strip()\n"
                "    if line.startswith('port:'):\n"
                "        port = int(line.split(':', 1)[1].strip().strip('\"'))\n"
                "        break\n"
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
            )
        path.write_text(
            (
                "#!/bin/sh\n"
                "mode=\"$1\"\n"
                "[ \"$mode\" = smoke ] || exit 7\n"
                "printf 'stable\\n' > \"$WBP_RUNTIME_EFFECTIVE_MODE_FILE\"\n"
                + server_block
                + "python3 - <<'PY'\n"
                "import json\n"
                "import os\n"
                "from pathlib import Path\n"
                "state_path = Path(os.environ['WBP_STATE_FILE'])\n"
                "state = json.loads(state_path.read_text())\n"
                "stable_config = Path(os.environ['WBP_STABLE_CONFIG'])\n"
                "port = '8318'\n"
                "auth_dir = ''\n"
                "for raw_line in stable_config.read_text().splitlines():\n"
                "    line = raw_line.strip()\n"
                "    if line.startswith('port:'):\n"
                "        port = line.split(':', 1)[1].strip().strip('\"')\n"
                "    if line.startswith('auth-dir:'):\n"
                "        auth_dir = line.split(':', 1)[1].strip().strip('\"')\n"
                "state['effective_mode'] = 'stable'\n"
                "state['status'] = 'healthy'\n"
                "state['last_error'] = ''\n"
                "state['launcher_stable_config'] = str(stable_config)\n"
                "state['launcher_auth_dir'] = auth_dir\n"
                "state_path.write_text(json.dumps(state) + '\\n')\n"
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
                f"exit {exit_code}\n"
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

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
        recovery = payload["stable_runtime_consumer"][
            "deterministic_stable_recovery_result"
        ]
        self.assertEqual(recovery["entry_lane"], "managed_preflight_failure")
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
        self.assertEqual(payload["machine_error_code"], "STABLE_SERVICE_DISABLED")
        self.assertEqual(payload["liveness"], "down")
        recovery = payload["stable_runtime_consumer"][
            "deterministic_stable_recovery_result"
        ]
        self.assertEqual(recovery["entry_lane"], "stable_service_disabled")

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
        recovery_contract = payload["deterministic_stable_recovery_contract"]
        self.assertEqual(recovery_contract["owner_command_surface"], "healthcheck --json")
        self.assertEqual(
            recovery_contract["entry_lane_surface"]["status"],
            "owner_path_emitted",
        )
        self.assertEqual(
            recovery_contract["entry_lane_surface"]["field"],
            "deterministic_stable_recovery_result.entry_lane",
        )
        self.assertIn(
            "stable_service_disabled",
            recovery_contract["entry_lane_surface"]["allowed_values"],
        )
        self.assertEqual(
            recovery_contract["stable_service_disabled_classification"]["status"],
            "owner_path_emitted",
        )
        self.assertTrue(
            recovery_contract["stable_service_disabled_classification"][
                "positive_evidence_required"
            ]
        )
        self.assertEqual(
            recovery_contract["stable_service_disabled_classification"][
                "generic_listener_down_fallback"
            ],
            "LISTENER_DOWN",
        )
        self.assertEqual(
            recovery_contract["top_level_machine_error_code_rules"]["status"],
            "owner_path_emitted",
        )
        self.assertEqual(
            recovery_contract["top_level_machine_error_code_rules"][
                "stable_service_disabled_final_code"
            ],
            "STABLE_SERVICE_DISABLED",
        )
        self.assertFalse(recovery_contract["last_known_good_proxy_persistence_in_scope"])
        self.assertEqual(payload["current_proxy_url"], "http://127.0.0.1:10808")
        current_proxy_adoption_contract = payload["current_proxy_adoption_contract"]
        self.assertEqual(
            current_proxy_adoption_contract["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertTrue(current_proxy_adoption_contract["status_delegates_to_owner"])
        self.assertEqual(
            current_proxy_adoption_contract["current_proxy_truth_surface"]["field"],
            "current_proxy_url",
        )
        self.assertEqual(
            current_proxy_adoption_contract["working_candidate_surface"]["field"],
            "proxy_reprobe.working_candidate",
        )
        self.assertTrue(
            current_proxy_adoption_contract["working_candidate_surface"][
                "nested_evidence_only"
            ]
        )
        self.assertEqual(
            current_proxy_adoption_contract["current_proxy_url_write_path_status"],
            "contract_fixed_not_implemented",
        )
        self.assertEqual(
            current_proxy_adoption_contract["activation_surface_status"],
            "contract_fixed_not_implemented",
        )
        self.assertEqual(
            current_proxy_adoption_contract["activation_surface_kind"],
            "repo_owned_handoff_env_var",
        )
        self.assertEqual(
            current_proxy_adoption_contract["handoff_env_var"],
            "WBP_CURRENT_PROXY_URL",
        )
        handoff_carrier = current_proxy_adoption_contract["handoff_carrier_contract"]
        self.assertEqual(handoff_carrier["status"], "contract_ready")
        self.assertEqual(handoff_carrier["env_var"], "WBP_CURRENT_PROXY_URL")
        self.assertEqual(
            handoff_carrier["surface_kind"],
            "launcher_scoped_process_local_carrier",
        )
        self.assertEqual(
            handoff_carrier["current_proxy_truth_surface_field"],
            "current_proxy_url",
        )
        self.assertTrue(handoff_carrier["ambient_authoritative_forbidden"])
        self.assertTrue(handoff_carrier["top_level_runtime_truth_by_presence_forbidden"])
        self.assertEqual(
            current_proxy_adoption_contract["owner_activation_lane"],
            "serialized_healthcheck_owner_path",
        )
        self.assertEqual(
            current_proxy_adoption_contract["effectful_runtime_wiring_status"],
            "contract_fixed_not_implemented",
        )
        launcher_consumer = current_proxy_adoption_contract["launcher_consumer_contract"]
        self.assertEqual(
            launcher_consumer["status"],
            "repo_owned_default_consumer_provisioning_available",
        )
        self.assertEqual(
            launcher_consumer["launcher_protocol_scope"],
            "bounded_launcher_smoke_seam",
        )
        self.assertEqual(
            launcher_consumer["external_launcher_readiness_status"],
            "external_script_path_present_consumer_capability_unverified",
        )
        self.assertFalse(launcher_consumer["repo_owned_default_consumer_provisioned"])
        self.assertTrue(launcher_consumer["path_presence_not_capability_proof"])
        self.assertTrue(launcher_consumer["repo_managed_marker_required_for_refresh"])
        self.assertFalse(launcher_consumer["repo_managed_marker_present"])
        self.assertFalse(launcher_consumer["repo_managed_marker_valid"])
        self.assertFalse(launcher_consumer["repo_managed_marker_recognized"])
        self.assertTrue(launcher_consumer["default_path_non_clobber_required"])
        external_launcher = current_proxy_adoption_contract["external_launcher_path_surface"]
        self.assertEqual(external_launcher["status"], "path_present")
        self.assertEqual(external_launcher["env_var"], "WBP_LAUNCHER_SCRIPT")
        self.assertTrue(external_launcher["exists"])
        self.assertEqual(
            external_launcher["role"],
            "launcher_executable_path_surface",
        )
        self.assertEqual(
            external_launcher["path_kind"],
            "explicit_external_override",
        )
        self.assertFalse(external_launcher["repo_managed_marker_present"])
        self.assertFalse(external_launcher["repo_managed_marker_valid"])
        self.assertFalse(external_launcher["repo_managed_marker_recognized"])
        self.assertTrue(
            external_launcher["consumer_capability_by_path_presence_forbidden"]
        )
        engine_local_routing = current_proxy_adoption_contract[
            "engine_local_proxy_routing_contract"
        ]
        self.assertEqual(engine_local_routing["status"], "contract_ready")
        self.assertTrue(engine_local_routing["allowed"])
        self.assertEqual(
            engine_local_routing["routing_scope"],
            "managed_runtime_child_process_only",
        )
        self.assertTrue(engine_local_routing["derived_from_handoff_carrier_only"])
        self.assertFalse(engine_local_routing["current_engine_consumption_claimed"])
        self.assertEqual(
            current_proxy_adoption_contract["launcher_consumer_status"],
            "repo_owned_default_consumer_provisioning_available",
        )
        self.assertEqual(
            current_proxy_adoption_contract["external_launcher_readiness_status"],
            "external_script_path_present_consumer_capability_unverified",
        )
        self.assertTrue(
            current_proxy_adoption_contract["engine_local_proxy_routing_allowed"]
        )
        self.assertTrue(
            current_proxy_adoption_contract[
                "ambient_proxy_env_authoritative_forbidden"
            ]
        )
        self.assertTrue(current_proxy_adoption_contract["control_plane_proxyless"])
        self.assertTrue(
            current_proxy_adoption_contract[
                "base_url_proxy_selection_surface_forbidden"
            ]
        )
        self.assertTrue(
            current_proxy_adoption_contract["candidate_existence_alone_not_ok"]
        )
        self.assertTrue(
            current_proxy_adoption_contract["top_level_ok_requires_live_runtime_reproof"]
        )
        self.assertEqual(
            current_proxy_adoption_contract["nested_adoption_result_surface"]["field"],
            "proxy_reprobe_adoption_result",
        )
        last_known_good_contract = payload["last_known_good_proxy_contract"]
        self.assertEqual(last_known_good_contract["status"], "contract_ready")
        self.assertEqual(last_known_good_contract["owner_command_surface"], "healthcheck --json")
        self.assertEqual(last_known_good_contract["write_path_status"], "owner_path_emitted")
        self.assertEqual(
            last_known_good_contract["candidate_input_priority"],
            [
                "WBP_PROXY_REPROBE_CANDIDATES",
                "last_known_good_proxy_url",
                "current_proxy_url",
            ],
        )
        self.assertTrue(last_known_good_contract["current_proxy_url_reuse_forbidden"])
        self.assertFalse(last_known_good_contract["historical_truth_promotes_live_truth"])
        self.assertEqual(
            last_known_good_contract["state_fields"],
            ["last_known_good_proxy_url", "last_known_good_proxy_observed_at"],
        )
        last_known_good = payload["last_known_good_proxy"]
        self.assertEqual(last_known_good["status"], "materialized")
        self.assertEqual(last_known_good["proxy_url"], "http://127.0.0.1:10808")
        self.assertTrue(last_known_good["observed_at_utc"])
        self.assertTrue(last_known_good["matches_current_proxy_url"])
        self.assertTrue(last_known_good["eligible_for_bounded_reprobe"])
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["last_known_good_proxy_url"], "http://127.0.0.1:10808")
        self.assertTrue(state["last_known_good_proxy_observed_at"])
        recovery_result = payload["deterministic_stable_recovery_result"]
        self.assertEqual(recovery_result["status"], "not_invoked")
        self.assertEqual(recovery_result["entry_lane"], "not_invoked")
        self.assertEqual(recovery_result["re_enable_method"], "")

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
        candidate_port = free_port()
        ProbeHandler.response_status = 500
        ProbeHandler.response_payload = {
            "error": {
                "message": (
                    'Post "https://chatgpt.com/backend-api/codex/responses": '
                    f"proxyconnect tcp: dial tcp 127.0.0.1:{candidate_port}: connect: connection refused"
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
        state["current_proxy_url"] = f"http://127.0.0.1:{candidate_port}"
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
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse(payload["proxy_reprobe"]["found_candidate"])
        self.assertIn(
            f"http://127.0.0.1:{candidate_port}", payload["proxy_reprobe"]["candidates"]
        )
        self.assertEqual(payload["last_known_good_proxy"]["status"], "declared_not_materialized")
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertNotIn("last_known_good_proxy_url", state)
        self.assertNotIn("last_known_good_proxy_observed_at", state)
        self.assertIn("proxyconnect tcp", payload["last_error"])

    def test_healthcheck_preserves_materialized_last_known_good_proxy_on_proxy_reprobe_failure(
        self,
    ) -> None:
        port = free_port()
        candidate_port = free_port()
        ProbeHandler.response_status = 500
        ProbeHandler.response_payload = {
            "error": {
                "message": (
                    'Post "https://chatgpt.com/backend-api/codex/responses": '
                    f"proxyconnect tcp: dial tcp 127.0.0.1:{candidate_port}: connect: connection refused"
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
        state["current_proxy_url"] = f"http://127.0.0.1:{candidate_port}"
        state["last_known_good_proxy_url"] = "http://127.0.0.1:10809"
        state["last_known_good_proxy_observed_at"] = "2026-05-05T00:00:00+00:00"
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
        self.assertEqual(payload["machine_error_code"], "PROXY_PATH_BROKEN")
        self.assertEqual(payload["changed_files"], [])
        last_known_good = payload["last_known_good_proxy"]
        self.assertEqual(last_known_good["status"], "materialized")
        self.assertEqual(last_known_good["proxy_url"], "http://127.0.0.1:10809")
        self.assertFalse(last_known_good["matches_current_proxy_url"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["last_known_good_proxy_url"], "http://127.0.0.1:10809")
        self.assertEqual(
            state["last_known_good_proxy_observed_at"], "2026-05-05T00:00:00+00:00"
        )

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
        self.assertNotIn("proxy_reprobe_adoption_result", payload)
        self.assertEqual(payload["current_proxy_url"], "http://127.0.0.1:10808")
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
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertTrue(recovery["attempted"])
        self.assertEqual(recovery["entry_lane"], "managed_preflight_failure")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
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
        self.assertIn(
            str(self.managed_dir / "managed-proxy.pid"),
            payload["changed_files"],
        )
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

    def test_healthcheck_owner_path_recovers_approved_target_and_reports_changed_files(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        stable_port = free_port()
        baseline_text = (
            f'host: 127.0.0.1\nport: {stable_port}\nlabel: stable\nauth-dir: "{self.stable_dir}"\n'
        )
        (self.stable_dir / "config.yaml").write_text(baseline_text, encoding="utf-8")
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-healthcheck-recover.sh",
            start_server=True,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "healthcheck", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertTrue(payload["attestation"]["listener_ok"])
        self.assertTrue(recovery["attempted"])
        self.assertEqual(recovery["status"], "completed")
        self.assertEqual(recovery["owner_command_surface"], "healthcheck --json")
        self.assertFalse(recovery["delegated_from_status"])
        self.assertEqual(recovery["entry_lane"], "managed_preflight_failure")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
        self.assertEqual(recovery["outcome"], "approved_target_recovered")
        self.assertEqual(recovery["selected_source_kind"], "approved_repair_target")
        self.assertEqual(
            recovery["selected_source_path"],
            str(self.managed_dir / "stable-repair-target"),
        )
        self.assertTrue(recovery["generated_config_regenerated"])
        self.assertTrue(recovery["snapshot_refreshed"])
        self.assertTrue(recovery["live_runtime_observation_confirmed"])
        self.assertIn(
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
            payload["changed_files"],
        )
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        self.assertIn(str(self.profile_dir / "config.toml"), payload["changed_files"])
        self.assertIn(
            str(self.profile_dir / "runtime-effective-mode.txt"),
            payload["changed_files"],
        )
        self.assertEqual(
            (self.stable_dir / "config.yaml").read_text(encoding="utf-8"), baseline_text
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(
            state["launcher_stable_config"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertEqual(state["healthy_count"], 1)
        self.assertEqual(state["down_count"], 0)
        self.assertEqual(
            state["stable_runtime_consumer_snapshot"]["activation_outcome"],
            "approved_target_activated",
        )

    def test_healthcheck_owner_path_reports_observed_source_fallback_recovery(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        stable_port = free_port()
        baseline_text = (
            f'host: 127.0.0.1\nport: {stable_port}\nauth-dir: "{self.stable_dir}"\n'
        )
        (self.stable_dir / "config.yaml").write_text(baseline_text, encoding="utf-8")
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-healthcheck-fallback.sh",
            exit_code=9,
            start_server=True,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "healthcheck", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(recovery["status"], "completed")
        self.assertTrue(recovery["attempted"])
        self.assertEqual(recovery["entry_lane"], "managed_preflight_failure")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
        self.assertEqual(recovery["outcome"], "observed_source_fallback_recovered")
        self.assertEqual(
            recovery["selected_source_kind"], "observed_stable_inventory_source"
        )
        self.assertEqual(recovery["fallback_reason"], "launcher_exit_nonzero")
        self.assertTrue(recovery["generated_config_regenerated"])
        self.assertTrue(recovery["snapshot_refreshed"])
        self.assertTrue(recovery["live_runtime_observation_confirmed"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["healthy_count"], 1)
        self.assertEqual(state["down_count"], 0)
        self.assertEqual(
            state["stable_runtime_consumer_snapshot"]["activation_outcome"],
            "observed_source_fallback",
        )
        self.assertEqual(
            (self.stable_dir / "config.yaml").read_text(encoding="utf-8"), baseline_text
        )

    def test_healthcheck_owner_path_reports_failed_recovery_without_greenwashing_state(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        stable_port = free_port()
        baseline_text = (
            f'host: 127.0.0.1\nport: {stable_port}\nauth-dir: "{self.stable_dir}"\n'
        )
        (self.stable_dir / "config.yaml").write_text(baseline_text, encoding="utf-8")
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-healthcheck-failed.sh",
            exit_code=9,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "healthcheck", "--json"
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(recovery["status"], "failed")
        self.assertTrue(recovery["attempted"])
        self.assertEqual(recovery["entry_lane"], "managed_preflight_failure")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
        self.assertEqual(recovery["outcome"], "recovery_failed_before_stable_healthy")
        self.assertEqual(recovery["fallback_reason"], "launcher_exit_nonzero")
        self.assertTrue(recovery["generated_config_regenerated"])
        self.assertFalse(recovery["snapshot_refreshed"])
        self.assertFalse(recovery["live_runtime_observation_confirmed"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["effective_mode"], "stable")
        self.assertEqual(state["status"], "failed")
        self.assertNotIn("stable_runtime_consumer_snapshot", state)
        self.assertEqual(
            (self.stable_dir / "config.yaml").read_text(encoding="utf-8"), baseline_text
        )

    def test_healthcheck_owner_path_emits_stable_service_disabled_on_failed_stable_reenable(
        self,
    ) -> None:
        stable_port = free_port()
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "stable"
        state["selected_backend_ids"] = []
        state["status"] = "failed"
        state["last_error"] = ""
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{stable_port}/v1"\n',
            encoding="utf-8",
        )
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-healthcheck-stable-disabled-failed.sh",
            exit_code=9,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "healthcheck", "--json"
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "STABLE_SERVICE_DISABLED")
        self.assertEqual(recovery["entry_lane"], "stable_service_disabled")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
        self.assertEqual(recovery["status"], "failed")
        self.assertTrue(recovery["attempted"])
        self.assertFalse(recovery["live_runtime_observation_confirmed"])

    def test_healthcheck_owner_path_emits_stable_service_disabled_lane_on_successful_stable_reenable(
        self,
    ) -> None:
        stable_port = free_port()
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "stable"
        state["selected_backend_ids"] = []
        state["status"] = "failed"
        state["last_error"] = ""
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{stable_port}/v1"\n',
            encoding="utf-8",
        )
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-healthcheck-stable-disabled-success.sh",
            start_server=True,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "healthcheck", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(recovery["entry_lane"], "stable_service_disabled")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
        self.assertEqual(recovery["status"], "completed")
        self.assertTrue(recovery["attempted"])
        self.assertTrue(recovery["live_runtime_observation_confirmed"])

    def test_healthcheck_stable_service_disabled_lane_does_not_clobber_attestation_failure(
        self,
    ) -> None:
        stable_port = free_port()
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "stable"
        state["selected_backend_ids"] = []
        state["status"] = "failed"
        state["last_error"] = ""
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{stable_port}/v1"\n',
            encoding="utf-8",
        )
        launcher = self.profile_dir / "codex-custom-healthcheck-stable-disabled-attestation-failed.sh"
        launcher.write_text(
            "#!/bin/sh\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "printf 'stable\\n' > \"$WBP_RUNTIME_EFFECTIVE_MODE_FILE\"\n"
            "python3 - <<'PY' >/dev/null 2>&1 &\n"
            "import json\n"
            "import os\n"
            "import threading\n"
            "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
            "from pathlib import Path\n"
            "stable_config = Path(os.environ['WBP_STABLE_CONFIG'])\n"
            "port = 8318\n"
            "for raw_line in stable_config.read_text().splitlines():\n"
            "    line = raw_line.strip()\n"
            "    if line.startswith('port:'):\n"
            "        port = int(line.split(':', 1)[1].strip().strip('\"'))\n"
            "        break\n"
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
            "            body = json.dumps({'output_text': 'NOT OK'}).encode('utf-8')\n"
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
            "state_path = Path(os.environ['WBP_STATE_FILE'])\n"
            "state = json.loads(state_path.read_text())\n"
            "stable_config = Path(os.environ['WBP_STABLE_CONFIG'])\n"
            "port = '8318'\n"
            "for raw_line in stable_config.read_text().splitlines():\n"
            "    line = raw_line.strip()\n"
            "    if line.startswith('port:'):\n"
            "        port = line.split(':', 1)[1].strip().strip('\"')\n"
            "state['effective_mode'] = 'stable'\n"
            "state['status'] = 'healthy'\n"
            "state['last_error'] = ''\n"
            "state_path.write_text(json.dumps(state) + '\\n')\n"
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
            "exit 0\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "healthcheck", "--json"
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertEqual(payload["machine_error_code"], "ATTESTATION_FAILED")
        self.assertEqual(recovery["entry_lane"], "stable_service_disabled")
        self.assertFalse(recovery["live_runtime_observation_confirmed"])

    def test_healthcheck_reports_materialized_last_known_good_proxy_separately_from_current_proxy_url(
        self,
    ) -> None:
        port = free_port()
        ProbeHandler.response_text = "OK"
        (self.stable_dir / "config.yaml").write_text(
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
        state["effective_mode"] = "stable"
        state["selected_backend_ids"] = []
        state["last_known_good_proxy_url"] = "http://127.0.0.1:10809"
        state["last_known_good_proxy_observed_at"] = "2026-05-05T00:00:00+00:00"
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
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["current_proxy_url"], "http://127.0.0.1:10808")
        last_known_good = payload["last_known_good_proxy"]
        self.assertEqual(last_known_good["status"], "materialized")
        self.assertEqual(last_known_good["proxy_url"], "http://127.0.0.1:10809")
        self.assertEqual(
            last_known_good["observed_at_utc"], "2026-05-05T00:00:00+00:00"
        )
        self.assertFalse(last_known_good["matches_current_proxy_url"])
        self.assertTrue(last_known_good["eligible_for_bounded_reprobe"])
        self.assertNotIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])

    def test_healthcheck_refreshes_last_known_good_proxy_timestamp_on_new_positive_proof(
        self,
    ) -> None:
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
        state["last_known_good_proxy_url"] = "http://127.0.0.1:10808"
        state["last_known_good_proxy_observed_at"] = "2026-05-05T00:00:00+00:00"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.dict(os.environ, self.env(), clear=False):
                paths = runtime_mod.RuntimePaths.from_env()
                with mock.patch(
                    "wild_boar_proxy.runtime.now_iso",
                    side_effect=[
                        "2026-05-05T00:00:01+00:00",
                        "2026-05-05T00:00:02+00:00",
                    ],
                ):
                    payload = runtime_mod.run_healthcheck(paths)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(
            payload["last_known_good_proxy"]["observed_at_utc"],
            "2026-05-05T00:00:01+00:00",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(
            state["last_known_good_proxy_observed_at"],
            "2026-05-05T00:00:01+00:00",
        )
        self.assertEqual(
            payload["attestation"]["observed_at_utc"], "2026-05-05T00:00:02+00:00"
        )
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])

    def test_healthcheck_proxy_reprobe_uses_last_known_good_before_current_proxy(
        self,
    ) -> None:
        port = free_port()
        env_candidate_port = free_port()
        lkg_candidate_port = free_port()
        current_candidate_port = free_port()
        ProbeHandler.response_status = 500
        ProbeHandler.response_payload = {
            "error": {
                "message": (
                    'Post "https://chatgpt.com/backend-api/codex/responses": '
                    f"proxyconnect tcp: dial tcp 127.0.0.1:{current_candidate_port}: connect: connection refused"
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
        state["current_proxy_url"] = f"http://127.0.0.1:{current_candidate_port}"
        state["last_known_good_proxy_url"] = f"http://127.0.0.1:{lkg_candidate_port}"
        state["last_known_good_proxy_observed_at"] = "2026-05-05T00:00:00+00:00"
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        lkg_socket = socket.socket()
        lkg_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lkg_socket.bind(("127.0.0.1", lkg_candidate_port))
        lkg_socket.listen(1)
        try:
            thread.start()
            result = self.run_cli_with_env(
                {
                    "WBP_PROXY_REPROBE_CANDIDATES": (
                        f"http://127.0.0.1:{env_candidate_port}"
                    )
                },
                "healthcheck",
                "--json",
            )
        finally:
            lkg_socket.close()
            server.shutdown()
            thread.join()
            server.server_close()
            ProbeHandler.response_status = 200
            ProbeHandler.response_payload = None
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "PROXY_PATH_BROKEN")
        self.assertEqual(
            payload["proxy_reprobe"]["candidates"],
            [
                f"http://127.0.0.1:{env_candidate_port}",
                f"http://127.0.0.1:{lkg_candidate_port}",
                f"http://127.0.0.1:{current_candidate_port}",
            ],
        )
        self.assertEqual(
            payload["proxy_reprobe"]["working_candidate"],
            f"http://127.0.0.1:{lkg_candidate_port}",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(
            state["last_known_good_proxy_url"], f"http://127.0.0.1:{lkg_candidate_port}"
        )

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

    def test_stable_repair_dry_run_reports_not_needed_when_target_matches_eligible_registry_auths(
        self,
    ) -> None:
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        (self.managed_dir / "stable-repair-target" / "codex-active.json").write_text(
            "{}",
            encoding="utf-8",
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
        self.assertEqual(
            plan["repair_observation"]["observed_source_matching_allowed_auths"][0][
                "auth_basename"
            ],
            "codex-active.json",
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_add"],
            [],
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_prune"],
            [],
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_keep"][0]["auth_basename"],
            "codex-active.json",
        )
        self.assertEqual(
            plan["repair_apply_authority"]["target_mutation_authority"]["exactness"],
            "exact_approved_set",
        )

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
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_NOT_NEEDED")
        self.assertFalse(payload["would_change"])
        self.assertEqual(payload["next_action"], "none")
        self.assertEqual(payload["changed_files"], [])
        plan = payload["transaction_plan"]
        self.assertEqual(
            plan["repair_observation"]["observed_source_disallowed_auths"][0][
                "auth_basename"
            ],
            "codex-reserve.json",
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_add"],
            [],
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_prune"],
            [],
        )

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
        self.assertEqual(
            plan["repair_observation"]["observed_source_missing_allowed_auths"][0][
                "auth_basename"
            ],
            "codex-missing.json",
        )
        self.assertEqual(
            plan["registry_source_inputs"]["source_copy_missing_auth_refs"][0][
                "auth_basename"
            ],
            "codex-missing.json",
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_add"][0]["auth_basename"],
            "codex-missing.json",
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_add"][0]["source_exists"],
            False,
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_prune"],
            [],
        )

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

    def test_stable_repair_dry_run_reports_observed_source_missing_dir_without_blocking(
        self,
    ) -> None:
        missing_dir = self.stable_dir / "missing-auth"
        active_auth = self.stable_dir / "codex-active.json"
        active_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{missing_dir}"\n',
            encoding="utf-8",
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertTrue(payload["would_change"])
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(
            payload["transaction_plan"]["repair_observation"]["status"], "unknown"
        )
        self.assertFalse(
            payload["transaction_plan"]["repair_observation"][
                "stable_auth_inventory_source"
            ]["exists"]
        )
        self.assertEqual(
            payload["transaction_plan"]["target_reconciliation_plan"]["target_would_add"][
                0
            ]["auth_basename"],
            "codex-active.json",
        )

    def test_stable_repair_dry_run_keeps_unknown_source_auths_out_of_target_prune_lane(
        self,
    ) -> None:
        active_auth = self.stable_dir / "codex-active.json"
        unknown_auth = self.stable_dir / "codex-unknown.json"
        active_auth.write_text("{}", encoding="utf-8")
        unknown_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(active_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{self.stable_dir}"\n',
            encoding="utf-8",
        )
        result = self.run_cli("stable", "repair", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        plan = payload["transaction_plan"]
        self.assertEqual(
            plan["repair_observation"]["observed_source_unknown_auths"][0][
                "auth_basename"
            ],
            "codex-unknown.json",
        )
        self.assertEqual(
            plan["target_reconciliation_plan"]["target_would_prune"],
            [],
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

    def test_stable_target_switch_apply_materializes_only_approved_surfaces(self) -> None:
        before = self.state_snapshot()
        result = self.run_cli("stable", "target", "switch", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertNotEqual(before, after)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "TARGET_SWITCH_APPLIED")
        self.assertEqual(
            sorted(payload["changed_files"]),
            sorted(
                [
                    str(self.managed_dir / "approved-repair-target.json"),
                    str(self.managed_dir / "stable-repair-target"),
                    str(self.managed_dir / "target-switch-transaction.json"),
                ]
            ),
        )
        self.assertEqual(payload["command_mode"], "apply")
        self.assertEqual(payload["operator_action"], "none")
        self.assertTrue(payload["write_surface_declared"])
        approved_target = payload["target_surface"]["approved_repair_target_reference"]
        self.assertEqual(approved_target["status"], "materialized_aligned")
        self.assertEqual(
            approved_target["reference_file"],
            str(self.managed_dir / "approved-repair-target.json"),
        )
        self.assertTrue((self.managed_dir / "stable-repair-target").is_dir())
        self.assertEqual(
            sorted((self.managed_dir / "stable-repair-target").glob("codex-*.json")),
            [],
        )
        reference_payload = json.loads(
            (self.managed_dir / "approved-repair-target.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            reference_payload,
            {
                "schema_version": 1,
                "target_identity": "companion_managed_stable_auth_inventory",
                "target_kind": "control_owned_inventory_path",
                "inventory_dir": str(self.managed_dir / "stable-repair-target"),
                "ownership": "control_layer",
                "location_scope": "companion_managed_data",
            },
        )
        transaction_payload = json.loads(
            (self.managed_dir / "target-switch-transaction.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            transaction_payload,
            {
                "schema_version": 1,
                "transaction_status": "applied",
                "target_identity": "companion_managed_stable_auth_inventory",
                "target_kind": "control_owned_inventory_path",
                "inventory_dir": str(self.managed_dir / "stable-repair-target"),
                "reference_file": str(self.managed_dir / "approved-repair-target.json"),
                "ownership": "control_layer",
                "location_scope": "companion_managed_data",
            },
        )
        self.assertIn("~/.cli-proxy-api", payload["forbidden_surfaces"])
        self.assertEqual(payload["next_action"], "none")

    def test_stable_target_switch_apply_is_idempotent_when_already_aligned(self) -> None:
        first = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.state_snapshot()
        result = self.run_cli("stable", "target", "switch", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "TARGET_SWITCH_ALREADY_ACTIVE")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["next_action"], "none")

    def test_stable_target_switch_apply_rolls_back_on_transaction_write_failure(self) -> None:
        (self.managed_dir / "target-switch-transaction.json").mkdir()
        before = self.state_snapshot()
        result = self.run_cli("stable", "target", "switch", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "TARGET_SWITCH_APPLY_FAILED")
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse((self.managed_dir / "approved-repair-target.json").exists())
        self.assertFalse((self.managed_dir / "stable-repair-target").exists())
        self.assertTrue((self.managed_dir / "target-switch-transaction.json").is_dir())
        self.assertEqual(before, after)

    def test_stable_target_switch_apply_blocks_nonempty_target_inventory_dir(self) -> None:
        target_dir = self.managed_dir / "stable-repair-target"
        target_dir.mkdir()
        (target_dir / "codex-manual.json").write_text("{}", encoding="utf-8")
        before = self.state_snapshot()
        result = self.run_cli("stable", "target", "switch", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(payload["machine_error_code"], "TARGET_SWITCH_DIR_NOT_EMPTY")
        self.assertFalse((self.managed_dir / "approved-repair-target.json").exists())
        self.assertFalse((self.managed_dir / "target-switch-transaction.json").exists())

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
        self.assertEqual(
            plan["repair_observation"]["stable_auth_inventory_source"]["source"],
            "stable_config_parent",
        )
        approved_target = plan["repair_target_contract_surface"][
            "approved_repair_target_reference"
        ]
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
        self.assertEqual(approved_target["status"], "fixed_not_materialized")
        transaction_surface = plan["repair_target_contract_surface"][
            "target_switch_transaction_metadata_surface"
        ]
        self.assertEqual(
            transaction_surface["transaction_file"],
            str(self.managed_dir / "target-switch-transaction.json"),
        )
        authority = plan["repair_apply_authority"]
        self.assertNotEqual(
            plan["repair_observation"]["stable_auth_inventory_source"]["path"],
            approved_target["inventory_dir"],
        )
        self.assertFalse(
            authority["source_of_copy_authority"]["observed_source_delete_authority"]
        )
        self.assertFalse(
            authority["source_of_copy_authority"]["engine_owned_delete_authority"]
        )
        self.assertEqual(
            authority["target_mutation_authority"]["write_scope"],
            "approved_target_inventory_only",
        )

    def test_stable_repair_dry_run_reports_materialized_approved_target_after_apply(self) -> None:
        result = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        repair = self.run_cli("stable", "repair", "--dry-run", "--json")
        self.assertEqual(repair.returncode, 0, repair.stderr)
        payload = json.loads(repair.stdout)
        plan = payload["transaction_plan"]
        self.assertEqual(
            plan["repair_target_contract_surface"]["approved_repair_target_reference"][
                "status"
            ],
            "materialized_aligned",
        )
        self.assertEqual(
            plan["repair_target_contract_surface"][
                "target_switch_transaction_metadata_surface"
            ]["status"],
            "materialized_aligned",
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

    def test_stable_repair_apply_copies_eligible_sources_into_target_inventory_only(
        self,
    ) -> None:
        source_a = self.profile_dir / "sources" / "codex-a.json"
        source_b = self.profile_dir / "sources" / "codex-b.json"
        source_a.parent.mkdir(parents=True, exist_ok=True)
        source_a.write_text('{"token":"a"}', encoding="utf-8")
        source_b.write_text('{"token":"b"}', encoding="utf-8")
        observed_unknown = self.stable_dir / "codex-observed.json"
        observed_unknown.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                **registry["backends"][0],
                "id": "backend-a",
                "auth_ref": str(source_a),
            },
            {
                **registry["backends"][0],
                "id": "backend-b",
                "auth_ref": str(source_b),
            },
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        guard_paths = [
            self.managed_dir / "backend-registry.json",
            self.managed_dir / "supervisor-state.json",
            self.managed_dir / "approved-repair-target.json",
            self.managed_dir / "target-switch-transaction.json",
            self.profile_dir / "config.toml",
            self.profile_dir / "runtime-mode.txt",
            self.profile_dir / "runtime-effective-mode.txt",
            self.stable_dir / "config.yaml",
        ]
        guard_before = {
            str(path): path.read_text(encoding="utf-8")
            for path in guard_paths
        }
        result = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_APPLIED")
        self.assertEqual(payload["command_mode"], "apply")
        self.assertFalse(payload["would_change"])
        self.assertEqual(
            sorted(payload["changed_files"]),
            sorted(
                [
                    str(self.managed_dir / "stable-repair-target" / "codex-a.json"),
                    str(self.managed_dir / "stable-repair-target" / "codex-b.json"),
                ]
            ),
        )
        self.assertEqual(
            (self.managed_dir / "stable-repair-target" / "codex-a.json").read_text(
                encoding="utf-8"
            ),
            '{"token":"a"}',
        )
        self.assertEqual(
            (self.managed_dir / "stable-repair-target" / "codex-b.json").read_text(
                encoding="utf-8"
            ),
            '{"token":"b"}',
        )
        self.assertEqual(source_a.read_text(encoding="utf-8"), '{"token":"a"}')
        self.assertEqual(source_b.read_text(encoding="utf-8"), '{"token":"b"}')
        self.assertTrue(observed_unknown.exists())
        self.assertEqual(
            sorted(path.name for path in self.managed_dir.glob(".stable-repair-*")),
            [],
        )
        guard_after = {
            str(path): path.read_text(encoding="utf-8")
            for path in guard_paths
        }
        self.assertEqual(guard_before, guard_after)

    def test_stable_repair_apply_prunes_unauthorized_target_entries_only(self) -> None:
        source_auth = self.profile_dir / "sources" / "codex-active.json"
        source_auth.parent.mkdir(parents=True, exist_ok=True)
        source_auth.write_text('{"token":"fresh"}', encoding="utf-8")
        observed_unknown = self.stable_dir / "codex-observed.json"
        observed_unknown.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        target_dir = self.managed_dir / "stable-repair-target"
        (target_dir / "codex-active.json").write_text('{"token":"stale"}', encoding="utf-8")
        (target_dir / "codex-extra.json").write_text('{"token":"extra"}', encoding="utf-8")
        result = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_APPLIED")
        self.assertEqual(
            sorted(payload["changed_files"]),
            sorted(
                [
                    str(target_dir / "codex-active.json"),
                    str(target_dir / "codex-extra.json"),
                ]
            ),
        )
        self.assertEqual(
            (target_dir / "codex-active.json").read_text(encoding="utf-8"),
            '{"token":"fresh"}',
        )
        self.assertFalse((target_dir / "codex-extra.json").exists())
        self.assertTrue(observed_unknown.exists())
        self.assertEqual(
            sorted(path.name for path in self.managed_dir.glob(".stable-repair-*")),
            [],
        )

    def test_stable_repair_apply_blocks_missing_source_without_mutation(self) -> None:
        missing_auth = self.profile_dir / "sources" / "codex-missing.json"
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(missing_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "REPAIR_SOURCE_AUTH_REF_MISSING")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(before, after)

    def test_stable_repair_dry_run_and_apply_report_basename_collision(self) -> None:
        source_a = self.profile_dir / "sources-a" / "codex-shared.json"
        source_b = self.profile_dir / "sources-b" / "codex-shared.json"
        source_a.parent.mkdir(parents=True, exist_ok=True)
        source_b.parent.mkdir(parents=True, exist_ok=True)
        source_a.write_text('{"token":"a"}', encoding="utf-8")
        source_b.write_text('{"token":"b"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"] = [
            {
                **registry["backends"][0],
                "id": "backend-a",
                "auth_ref": str(source_a),
            },
            {
                **registry["backends"][0],
                "id": "backend-b",
                "auth_ref": str(source_b),
            },
        ]
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        dry_run = self.run_cli("stable", "repair", "--dry-run", "--json")
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        dry_payload = json.loads(dry_run.stdout)
        self.assertEqual(
            dry_payload["transaction_plan"]["registry_source_inputs"][
                "source_copy_basename_collisions"
            ],
            [
                {
                    "auth_basename": "codex-shared.json",
                    "backend_ids": ["backend-a", "backend-b"],
                    "auth_refs": [str(source_a), str(source_b)],
                    "reason": "eligible_registry_auth_ref_basename_collision",
                }
            ],
        )
        self.assertIn(
            {
                "machine_error_code": "REPAIR_SOURCE_BASENAME_COLLISION",
                "auth_basename": "codex-shared.json",
                "reason": "eligible_registry_auth_ref_basename_collision",
            },
            dry_payload["transaction_plan"]["blocked_reasons"],
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "REPAIR_SOURCE_BASENAME_COLLISION")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(before, after)

    def test_stable_repair_apply_blocks_held_lock_without_mutation(self) -> None:
        source_auth = self.profile_dir / "sources" / "codex-active.json"
        source_auth.parent.mkdir(parents=True, exist_ok=True)
        source_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        (self.managed_dir / "wild-boar-proxy.lock").write_text(
            f"{os.getpid()}\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "LOCK_HELD")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(before, after)
        self.assertEqual(payload["transaction_plan"]["mode"], "apply")

    def test_stable_repair_apply_blocks_stale_lock_without_mutation(self) -> None:
        source_auth = self.profile_dir / "sources" / "codex-active.json"
        source_auth.parent.mkdir(parents=True, exist_ok=True)
        source_auth.write_text("{}", encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        (self.managed_dir / "wild-boar-proxy.lock").write_text(
            "not-a-pid\n", encoding="utf-8"
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_APPLY_BLOCKED")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(before, after)
        self.assertEqual(payload["transaction_plan"]["mode"], "apply")

    def test_stable_repair_apply_reports_already_aligned_without_mutation(self) -> None:
        source_auth = self.profile_dir / "sources" / "codex-active.json"
        source_auth.parent.mkdir(parents=True, exist_ok=True)
        source_auth.write_text('{"token":"steady"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        (self.managed_dir / "stable-repair-target" / "codex-active.json").write_text(
            '{"token":"steady"}',
            encoding="utf-8",
        )
        before = self.state_snapshot()
        result = self.run_cli("stable", "repair", "--apply", "--json")
        after = self.state_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_ALREADY_ALIGNED")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(before, after)

    def test_stable_repair_apply_rolls_back_on_verification_failure(self) -> None:
        source_auth = self.profile_dir / "sources" / "codex-active.json"
        source_auth.parent.mkdir(parents=True, exist_ok=True)
        source_auth.write_text('{"token":"repair"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        before = self.state_snapshot()
        with mock.patch.dict(os.environ, self.env(), clear=False):
            paths = runtime_mod.RuntimePaths.from_env()
            with mock.patch(
                "wild_boar_proxy.runtime.verify_stable_repair_apply_result",
                side_effect=runtime_mod.RuntimeErrorInfo(
                    "forced verify failure",
                    machine_error_code="STABLE_REPAIR_VERIFICATION_FAILED",
                    severity="recoverable",
                    operator_action="user_action",
                ),
            ):
                payload = runtime_mod.run_stable_repair_apply(paths)
        after = self.state_snapshot()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "STABLE_REPAIR_VERIFICATION_FAILED")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(before, after)
        self.assertEqual(
            sorted(path.name for path in self.managed_dir.glob(".stable-repair-*")),
            [],
        )

    def test_status_reports_stable_runtime_consumer_contract_when_approved_target_not_ready(
        self,
    ) -> None:
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        consumer = payload["stable_runtime_consumer"]
        self.assertEqual(consumer["status"], "contract_ready")
        self.assertEqual(
            consumer["observed_stable_inventory_source"]["source"],
            "stable_config_parent",
        )
        self.assertEqual(
            consumer["approved_repair_target_reference"]["status"],
            "fixed_not_materialized",
        )
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["status"],
            "observed_source_selected",
        )
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "observed_stable_inventory_source",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["status"],
            "observed_source_active",
        )
        self.assertTrue(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"]
        )
        derived_surface = consumer["derived_stable_runtime_config_surface"]
        self.assertEqual(derived_surface["status"], "declared_not_materialized")
        self.assertEqual(
            derived_surface["config_file"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertFalse(derived_surface["truth_surface"])
        self.assertFalse(derived_surface["exists"])
        launcher_handoff = consumer["launcher_handoff_contract"]
        self.assertEqual(launcher_handoff["status"], "contract_ready")
        self.assertEqual(launcher_handoff["handoff_method"], "process_local_env_override")
        self.assertEqual(launcher_handoff["env_var"], "WBP_STABLE_CONFIG")
        self.assertEqual(
            launcher_handoff["generated_config_file"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertTrue(launcher_handoff["baseline_config_rewrite_forbidden"])
        self.assertTrue(launcher_handoff["generic_config_routing_forbidden"])
        activation_evidence = consumer["activation_evidence_surface"]
        self.assertEqual(activation_evidence["status"], "declared_not_materialized")
        self.assertEqual(
            activation_evidence["snapshot_file"],
            str(self.managed_dir / "supervisor-state.json"),
        )
        self.assertEqual(
            activation_evidence["snapshot_topic"], "stable_runtime_consumer_snapshot"
        )
        self.assertFalse(activation_evidence["snapshot_present"])
        self.assertFalse(activation_evidence["snapshot_shape_valid"])
        effective_truth = consumer["effective_truth_contract"]
        self.assertEqual(effective_truth["status"], "contract_ready")
        self.assertTrue(effective_truth["live_runtime_observation_required"])
        self.assertFalse(effective_truth["desired_source_alone_sufficient"])
        self.assertFalse(effective_truth["generated_config_existence_alone_sufficient"])
        self.assertFalse(
            effective_truth["activation_evidence_snapshot_alone_sufficient"]
        )
        recovery_contract = consumer["deterministic_stable_recovery_contract"]
        self.assertEqual(recovery_contract["status"], "contract_ready")
        self.assertEqual(
            recovery_contract["entry_owner"], "healthcheck_live_attestation_path"
        )
        self.assertEqual(
            recovery_contract["owner_command_surface"], "healthcheck --json"
        )
        self.assertTrue(recovery_contract["status_delegates_to_owner"])
        self.assertTrue(recovery_contract["sync_hidden_owner_forbidden"])
        self.assertFalse(recovery_contract["new_generic_cli_default"])
        self.assertEqual(
            recovery_contract["shared_activation_mechanics"]["status"],
            "contract_fixed_not_implemented",
        )
        self.assertEqual(
            recovery_contract["generated_config_regeneration_status"],
            "contract_fixed_not_implemented",
        )
        self.assertEqual(
            recovery_contract["generated_config_regeneration_policy"],
            "regenerate_each_recovery_attempt",
        )
        self.assertFalse(recovery_contract["stale_generated_config_authoritative"])
        self.assertEqual(
            recovery_contract["entry_lane_surface"]["status"],
            "owner_path_emitted",
        )
        self.assertEqual(
            recovery_contract["entry_lane_surface"]["field"],
            "deterministic_stable_recovery_result.entry_lane",
        )
        self.assertIn(
            "stable_service_disabled",
            recovery_contract["entry_lane_surface"]["allowed_values"],
        )
        self.assertEqual(
            recovery_contract["snapshot_refresh_status"],
            "contract_fixed_not_implemented",
        )
        self.assertTrue(recovery_contract["snapshot_refresh_after_stable_live_outcome"])
        self.assertFalse(recovery_contract["snapshot_schema_widening_required"])
        self.assertFalse(
            recovery_contract["new_persisted_recovery_metadata_required"]
        )
        self.assertEqual(
            recovery_contract["stable_service_disabled_classification"]["status"],
            "owner_path_emitted",
        )
        self.assertTrue(
            recovery_contract["stable_service_disabled_classification"][
                "control_layer_classification"
            ]
        )
        self.assertTrue(
            recovery_contract["stable_service_disabled_classification"][
                "positive_evidence_required"
            ]
        )
        self.assertFalse(
            recovery_contract["stable_service_disabled_classification"][
                "desired_mode_alone_sufficient"
            ]
        )
        self.assertEqual(
            recovery_contract["stable_service_disabled_classification"][
                "generic_listener_down_fallback"
            ],
            "LISTENER_DOWN",
        )
        self.assertEqual(
            recovery_contract["re_enable_method_contract"]["status"],
            "owner_path_emitted",
        )
        self.assertTrue(
            recovery_contract["re_enable_method_contract"][
                "launchd_integration_forbidden"
            ]
        )
        self.assertTrue(
            recovery_contract["re_enable_method_contract"][
                "os_service_manager_integration_forbidden"
            ]
        )
        self.assertEqual(
            recovery_contract["top_level_truth_boundaries"]["status"],
            "contract_ready",
        )
        self.assertTrue(
            recovery_contract["top_level_truth_boundaries"][
                "final_live_truth_separate"
            ]
        )
        self.assertTrue(
            recovery_contract["top_level_truth_boundaries"][
                "launch_smoke_owner_lane_fields_forbidden"
            ]
        )
        self.assertEqual(
            recovery_contract["top_level_machine_error_code_rules"]["status"],
            "owner_path_emitted",
        )
        self.assertEqual(
            recovery_contract["top_level_machine_error_code_rules"][
                "stable_service_disabled_final_code"
            ],
            "STABLE_SERVICE_DISABLED",
        )
        self.assertEqual(
            recovery_contract["top_level_machine_error_code_rules"][
                "generic_listener_down_fallback"
            ],
            "LISTENER_DOWN",
        )
        self.assertFalse(recovery_contract["last_known_good_proxy_persistence_in_scope"])
        self.assertEqual(payload["current_proxy_url"], "http://127.0.0.1:10808")
        last_known_good_contract = payload["last_known_good_proxy_contract"]
        self.assertEqual(last_known_good_contract["status"], "contract_ready")
        self.assertEqual(
            last_known_good_contract["state_fields"],
            ["last_known_good_proxy_url", "last_known_good_proxy_observed_at"],
        )
        self.assertEqual(
            last_known_good_contract["candidate_input_priority"],
            [
                "WBP_PROXY_REPROBE_CANDIDATES",
                "last_known_good_proxy_url",
                "current_proxy_url",
            ],
        )
        self.assertEqual(last_known_good_contract["write_path_status"], "owner_path_emitted")
        self.assertFalse(last_known_good_contract["historical_truth_promotes_live_truth"])
        current_proxy_adoption_contract = payload["current_proxy_adoption_contract"]
        self.assertEqual(
            current_proxy_adoption_contract["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertTrue(current_proxy_adoption_contract["status_delegates_to_owner"])
        self.assertEqual(
            current_proxy_adoption_contract["current_proxy_truth_surface"]["field"],
            "current_proxy_url",
        )
        self.assertTrue(
            current_proxy_adoption_contract["working_candidate_surface"][
                "nested_evidence_only"
            ]
        )
        self.assertEqual(
            current_proxy_adoption_contract["activation_surface_status"],
            "contract_fixed_not_implemented",
        )
        self.assertEqual(
            current_proxy_adoption_contract["activation_surface_kind"],
            "repo_owned_handoff_env_var",
        )
        self.assertEqual(
            current_proxy_adoption_contract["handoff_env_var"],
            "WBP_CURRENT_PROXY_URL",
        )
        self.assertEqual(
            current_proxy_adoption_contract["launcher_consumer_status"],
            "repo_owned_default_consumer_provisioning_available",
        )
        self.assertEqual(
            current_proxy_adoption_contract["launcher_protocol_scope"],
            "bounded_launcher_smoke_seam",
        )
        self.assertEqual(
            current_proxy_adoption_contract["external_launcher_readiness_status"],
            "external_script_path_present_consumer_capability_unverified",
        )
        self.assertFalse(
            current_proxy_adoption_contract["repo_owned_default_consumer_provisioned"]
        )
        self.assertEqual(
            current_proxy_adoption_contract["external_launcher_path_surface"]["env_var"],
            "WBP_LAUNCHER_SCRIPT",
        )
        self.assertEqual(
            current_proxy_adoption_contract["external_launcher_path_surface"][
                "path_kind"
            ],
            "explicit_external_override",
        )
        self.assertTrue(
            current_proxy_adoption_contract["external_launcher_path_surface"][
                "consumer_capability_by_path_presence_forbidden"
            ]
        )
        self.assertFalse(
            current_proxy_adoption_contract["external_launcher_path_surface"][
                "repo_managed_marker_valid"
            ]
        )
        self.assertFalse(
            current_proxy_adoption_contract["external_launcher_path_surface"][
                "repo_managed_marker_recognized"
            ]
        )
        self.assertTrue(
            current_proxy_adoption_contract["engine_local_proxy_routing_allowed"]
        )
        self.assertEqual(
            current_proxy_adoption_contract["engine_local_proxy_routing_scope"],
            "managed_runtime_child_process_only",
        )
        self.assertFalse(
            current_proxy_adoption_contract["engine_local_proxy_routing_contract"][
                "current_engine_consumption_claimed"
            ]
        )
        self.assertTrue(
            current_proxy_adoption_contract[
                "ambient_proxy_env_authoritative_forbidden"
            ]
        )
        self.assertTrue(current_proxy_adoption_contract["control_plane_proxyless"])
        self.assertEqual(
            current_proxy_adoption_contract["current_proxy_url_write_path_status"],
            "contract_fixed_not_implemented",
        )
        last_known_good = payload["last_known_good_proxy"]
        self.assertEqual(last_known_good["status"], "declared_not_materialized")
        self.assertEqual(last_known_good["proxy_url"], "")
        self.assertFalse(last_known_good["eligible_for_bounded_reprobe"])
        self.assertEqual(
            recovery_contract["approved_target_recovery_outcome"], "separate"
        )
        self.assertEqual(
            recovery_contract["observed_source_fallback_recovery_outcome"], "separate"
        )
        self.assertEqual(recovery_contract["recovery_failure_outcome"], "separate")
        self.assertEqual(
            consumer["baseline_stable_config_surface"]["config_file"],
            str(self.stable_dir / "config.yaml"),
        )
        self.assertEqual(
            consumer["consumer_activation_readiness"]["machine_error_code"], "OK"
        )

    def test_status_reports_desired_approved_target_before_effective_activation(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        consumer = payload["stable_runtime_consumer"]
        self.assertEqual(
            consumer["approved_repair_target_reference"]["status"],
            "materialized_aligned",
        )
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["resolved_path"],
            str(self.managed_dir / "stable-repair-target"),
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["source_kind"],
            "observed_stable_inventory_source",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["resolved_path"],
            str(self.stable_dir),
        )
        self.assertFalse(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"]
        )
        self.assertEqual(
            consumer["consumer_activation_readiness"]["machine_error_code"],
            "STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING",
        )
        self.assertTrue(consumer["fallback_contract"]["fallback_allowed"])
        self.assertTrue(consumer["fallback_contract"]["silent_fallback_forbidden"])
        self.assertEqual(
            consumer["activation_evidence_surface"]["status"], "declared_not_materialized"
        )

    def test_status_reports_effective_approved_target_only_when_observation_matches_target(
        self,
    ) -> None:
        source_auth = self.profile_dir / "sources" / "codex-active.json"
        source_auth.parent.mkdir(parents=True, exist_ok=True)
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\n"
            "port: 8318\n"
            f'auth-dir: "{self.managed_dir / "stable-repair-target"}"\n',
            encoding="utf-8",
        )
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        consumer = payload["stable_runtime_consumer"]
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertTrue(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"]
        )
        self.assertEqual(
            consumer["consumer_activation_readiness"]["machine_error_code"], "OK"
        )

    def test_status_does_not_promote_activation_snapshot_to_effective_truth(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["stable_runtime_consumer_snapshot"] = {
            "schema_version": 1,
            "activation_method": "process_local_env_override",
            "selected_config_file": str(
                self.managed_dir / "stable-runtime-config.generated.yaml"
            ),
            "selected_source_kind": "approved_repair_target",
            "selected_source_path": str(self.managed_dir / "stable-repair-target"),
            "activation_outcome": "approved_target_activated",
            "fallback_reason": "",
            "observed_at_utc": "2026-05-04T00:00:00+00:00",
        }
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        result = self.run_cli("status", "--json")
        payload = json.loads(result.stdout)
        consumer = payload["stable_runtime_consumer"]
        evidence = consumer["activation_evidence_surface"]
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertEqual(evidence["status"], "snapshot_present")
        self.assertTrue(evidence["snapshot_present"])
        self.assertTrue(evidence["snapshot_shape_valid"])
        self.assertEqual(
            evidence["current_snapshot"]["selected_source_kind"], "approved_repair_target"
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["source_kind"],
            "observed_stable_inventory_source",
        )
        self.assertFalse(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"]
        )
        self.assertFalse(
            consumer["effective_truth_contract"][
                "activation_evidence_snapshot_alone_sufficient"
            ]
        )
        self.assertEqual(
            consumer["consumer_activation_readiness"]["machine_error_code"],
            "STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING",
        )

    def test_status_delegates_deterministic_stable_recovery_result_and_changed_files(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        stable_port = free_port()
        baseline_text = (
            f'host: 127.0.0.1\nport: {stable_port}\nauth-dir: "{self.stable_dir}"\n'
        )
        (self.stable_dir / "config.yaml").write_text(baseline_text, encoding="utf-8")
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-status-recovery.sh",
            start_server=True,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "status", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertNotIn("deterministic_stable_recovery_result", payload)
        recovery = payload["stable_runtime_consumer"][
            "deterministic_stable_recovery_result"
        ]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertEqual(recovery["status"], "completed")
        self.assertTrue(recovery["delegated_from_status"])
        self.assertTrue(recovery["attempted"])
        self.assertEqual(recovery["entry_lane"], "managed_preflight_failure")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")
        self.assertEqual(recovery["outcome"], "approved_target_recovered")
        self.assertEqual(recovery["selected_source_kind"], "approved_repair_target")
        self.assertIn(
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
            payload["changed_files"],
        )
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        self.assertIn(str(self.profile_dir / "config.toml"), payload["changed_files"])
        self.assertIn(
            str(self.profile_dir / "runtime-effective-mode.txt"),
            payload["changed_files"],
        )
        self.assertEqual(
            payload["stable_runtime_consumer"]["effective_stable_runtime_consumer_source"][
                "source_kind"
            ],
            "approved_repair_target",
        )
        self.assertEqual(
            (self.stable_dir / "config.yaml").read_text(encoding="utf-8"), baseline_text
        )

    def test_launch_smoke_reports_stable_runtime_consumer_contract(self) -> None:
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
        consumer = payload["stable_runtime_consumer"]
        self.assertEqual(consumer["status"], "contract_ready")
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "observed_stable_inventory_source",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["source_kind"],
            "observed_stable_inventory_source",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"], True
        )
        self.assertEqual(
            consumer["launcher_handoff_contract"]["env_var"], "WBP_STABLE_CONFIG"
        )
        self.assertEqual(
            consumer["activation_evidence_surface"]["status"], "snapshot_present"
        )
        self.assertEqual(
            consumer["activation_evidence_surface"]["current_snapshot"][
                "activation_outcome"
            ],
            "observed_source_selected",
        )
        self.assertEqual(
            consumer["activation_evidence_surface"]["current_snapshot"][
                "selected_source_kind"
            ],
            "observed_stable_inventory_source",
        )
        self.assertEqual(
            consumer["deterministic_stable_recovery_contract"][
                "owner_command_surface"
            ],
            "healthcheck --json",
        )
        self.assertTrue(
            consumer["deterministic_stable_recovery_contract"][
                "status_delegates_to_owner"
            ]
        )
        self.assertEqual(
            consumer["deterministic_stable_recovery_contract"]["entry_lane_surface"][
                "status"
            ],
            "owner_path_emitted",
        )
        self.assertTrue(
            consumer["deterministic_stable_recovery_contract"][
                "top_level_truth_boundaries"
            ]["launch_smoke_owner_lane_fields_forbidden"]
        )
        self.assertEqual(payload["current_proxy_url"], "http://127.0.0.1:10808")
        self.assertNotIn("last_known_good_proxy", payload)
        self.assertNotIn("last_known_good_proxy_contract", payload)
        self.assertNotIn("current_proxy_adoption_contract", payload)
        self.assertNotIn("deterministic_stable_recovery_result", consumer)

    def test_launch_smoke_does_not_forward_current_proxy_handoff_env(self) -> None:
        stable_port = free_port()
        marker = self.profile_dir / "launch-smoke-current-proxy-env.txt"
        baseline_launcher = self.profile_dir / "baseline-launcher.sh"
        baseline_launcher.write_text(self.launcher_script.read_text(encoding="utf-8"), encoding="utf-8")
        baseline_launcher.chmod(0o755)
        self.launcher_script.write_text(
            "#!/bin/sh\n"
            f"printf '%s' \"${{{runtime_mod.CURRENT_PROXY_URL_HANDOFF_ENV}:-}}\" > '{marker}'\n"
            f"exec '{baseline_launcher}' \"$@\"\n",
            encoding="utf-8",
        )
        self.launcher_script.chmod(0o755)
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli_with_env(
                {runtime_mod.CURRENT_PROXY_URL_HANDOFF_ENV: "http://127.0.0.1:65535"},
                "launch",
                "smoke",
                "--json",
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(marker.exists())
        self.assertEqual(marker.read_text(encoding="utf-8"), "")
        self.assertNotIn("current_proxy_adoption_contract", payload)

    def test_launch_smoke_does_not_write_last_known_good_proxy_when_it_is_not_the_owner(
        self,
    ) -> None:
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
        state.pop("last_known_good_proxy_url", None)
        state.pop("last_known_good_proxy_observed_at", None)
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        launcher = self.profile_dir / "codex-custom-managed-launch-noop.sh"
        launcher.write_text(
            "#!/bin/sh\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "exit 0\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli_with_env(
                {
                    "WBP_LAUNCHER_SCRIPT": str(launcher),
                    "WBP_LAUNCH_STABILIZATION_SECONDS": "0",
                },
                "launch",
                "smoke",
                "--json",
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effective_mode"], "managed")
        self.assertEqual(payload["changed_files"], [])
        self.assertNotIn("last_known_good_proxy", payload)
        self.assertNotIn("last_known_good_proxy_contract", payload)
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertNotIn("last_known_good_proxy_url", state)
        self.assertNotIn("last_known_good_proxy_observed_at", state)

    def test_launch_smoke_nonzero_managed_path_does_not_write_last_known_good_proxy(
        self,
    ) -> None:
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
        state.pop("last_known_good_proxy_url", None)
        state.pop("last_known_good_proxy_observed_at", None)
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        launcher = self.profile_dir / "codex-custom-managed-launch-fail.sh"
        launcher.write_text(
            "#!/bin/sh\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "exit 9\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        server = ThreadingHTTPServer(("127.0.0.1", port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli_with_env(
                {
                    "WBP_LAUNCHER_SCRIPT": str(launcher),
                    "WBP_LAUNCH_STABILIZATION_SECONDS": "0",
                },
                "launch",
                "smoke",
                "--json",
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 9, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "LAUNCHER_EXIT_NONZERO")
        self.assertEqual(payload["changed_files"], [])
        self.assertNotIn("last_known_good_proxy", payload)
        self.assertNotIn("last_known_good_proxy_contract", payload)
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertNotIn("last_known_good_proxy_url", state)
        self.assertNotIn("last_known_good_proxy_observed_at", state)

    def test_status_delegates_stable_service_disabled_lane_without_becoming_owner(
        self,
    ) -> None:
        stable_port = free_port()
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        state["effective_mode"] = "stable"
        state["selected_backend_ids"] = []
        state["status"] = "failed"
        state["last_error"] = ""
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{stable_port}/v1"\n',
            encoding="utf-8",
        )
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-status-stable-disabled-failed.sh",
            exit_code=9,
        )
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "status", "--json"
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "STABLE_SERVICE_DISABLED")
        self.assertNotIn("deterministic_stable_recovery_result", payload)
        recovery = payload["stable_runtime_consumer"][
            "deterministic_stable_recovery_result"
        ]
        self.assertTrue(recovery["delegated_from_status"])
        self.assertEqual(recovery["entry_lane"], "stable_service_disabled")
        self.assertEqual(recovery["re_enable_method"], "bounded_healthcheck_owner_retry")

    def test_status_reports_materialized_last_known_good_proxy_without_owner_transfer(
        self,
    ) -> None:
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
            "managed\n", encoding="utf-8"
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
            result = self.run_cli("status", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["current_proxy_url"], "http://127.0.0.1:10808")
        current_proxy_adoption_contract = payload["current_proxy_adoption_contract"]
        self.assertEqual(
            current_proxy_adoption_contract["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertEqual(
            current_proxy_adoption_contract["current_proxy_truth_surface"]["field"],
            "current_proxy_url",
        )
        self.assertEqual(
            current_proxy_adoption_contract["current_proxy_url_write_path_status"],
            "contract_fixed_not_implemented",
        )
        last_known_good = payload["last_known_good_proxy"]
        self.assertEqual(last_known_good["status"], "materialized")
        self.assertEqual(last_known_good["proxy_url"], "http://127.0.0.1:10808")
        self.assertTrue(last_known_good["matches_current_proxy_url"])
        self.assertTrue(last_known_good["eligible_for_bounded_reprobe"])
        self.assertEqual(
            payload["last_known_good_proxy_contract"]["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(state["last_known_good_proxy_url"], "http://127.0.0.1:10808")
        self.assertTrue(state["last_known_good_proxy_observed_at"])

    def test_launch_smoke_activates_approved_target_via_generated_config_and_status_reports_effective_target(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        stable_port = free_port()
        baseline_text = (
            f'host: 127.0.0.1\nport: {stable_port}\nlabel: stable\nauth-dir: "{self.stable_dir}"\n'
        )
        (self.stable_dir / "config.yaml").write_text(baseline_text, encoding="utf-8")
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-launch-activation.sh"
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli_with_env(
                {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "launch", "smoke", "--json"
            )
            status_result = self.run_cli("status", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        payload = json.loads(result.stdout)
        consumer = payload["stable_runtime_consumer"]
        evidence = consumer["activation_evidence_surface"]
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertTrue(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"]
        )
        self.assertEqual(
            consumer["consumer_activation_readiness"]["machine_error_code"], "OK"
        )
        self.assertEqual(evidence["status"], "snapshot_present")
        self.assertEqual(
            evidence["current_snapshot"]["activation_outcome"],
            "approved_target_activated",
        )
        self.assertEqual(
            evidence["current_snapshot"]["selected_config_file"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertEqual(
            evidence["current_snapshot"]["selected_source_kind"],
            "approved_repair_target",
        )
        self.assertEqual(
            evidence["current_snapshot"]["selected_source_path"],
            str(self.managed_dir / "stable-repair-target"),
        )
        generated_text = (
            self.managed_dir / "stable-runtime-config.generated.yaml"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            (self.stable_dir / "config.yaml").read_text(encoding="utf-8"), baseline_text
        )
        self.assertIn(f"port: {stable_port}", generated_text)
        self.assertIn("label: stable", generated_text)
        self.assertIn(
            f'auth-dir: "{self.managed_dir / "stable-repair-target"}"',
            generated_text,
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(
            state["launcher_stable_config"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertEqual(
            state["launcher_auth_dir"], str(self.managed_dir / "stable-repair-target")
        )
        self.assertIn(
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
            payload["changed_files"],
        )
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        self.assertIn(str(self.profile_dir / "config.toml"), payload["changed_files"])
        self.assertIn(
            str(self.profile_dir / "runtime-effective-mode.txt"),
            payload["changed_files"],
        )
        status_payload = json.loads(status_result.stdout)
        self.assertEqual(
            status_payload["stable_runtime_consumer"][
                "effective_stable_runtime_consumer_source"
            ]["source_kind"],
            "approved_repair_target",
        )

    def test_launch_smoke_records_conservative_observed_source_fallback_when_launcher_exits_nonzero_during_approved_target_attempt(
        self,
    ) -> None:
        source_auth = self.stable_dir / "codex-active.json"
        source_auth.write_text('{"token":"active"}', encoding="utf-8")
        registry = json.loads((self.managed_dir / "backend-registry.json").read_text())
        registry["backends"][0]["auth_ref"] = str(source_auth)
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(registry) + "\n", encoding="utf-8"
        )
        switched = self.run_cli("stable", "target", "switch", "--apply", "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        repaired = self.run_cli("stable", "repair", "--apply", "--json")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        stable_port = free_port()
        baseline_text = (
            f'host: 127.0.0.1\nport: {stable_port}\nauth-dir: "{self.stable_dir}"\n'
        )
        (self.stable_dir / "config.yaml").write_text(baseline_text, encoding="utf-8")
        launcher = self.write_recording_stable_launcher(
            self.profile_dir / "codex-custom-launch-fallback.sh",
            exit_code=9,
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli_with_env(
                {"WBP_LAUNCHER_SCRIPT": str(launcher)}, "launch", "smoke", "--json"
            )
            status_result = self.run_cli("status", "--json")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        payload = json.loads(result.stdout)
        consumer = payload["stable_runtime_consumer"]
        evidence = consumer["activation_evidence_surface"]
        self.assertEqual(payload["machine_error_code"], "LAUNCHER_EXIT_NONZERO")
        self.assertEqual(
            consumer["desired_stable_runtime_consumer_source"]["source_kind"],
            "approved_repair_target",
        )
        self.assertEqual(
            consumer["effective_stable_runtime_consumer_source"]["source_kind"],
            "observed_stable_inventory_source",
        )
        self.assertFalse(
            consumer["effective_stable_runtime_consumer_source"]["matches_desired"]
        )
        self.assertEqual(
            consumer["consumer_activation_readiness"]["machine_error_code"],
            "STABLE_RUNTIME_CONSUMER_FALLBACK_ACTIVE",
        )
        self.assertEqual(evidence["status"], "snapshot_present")
        self.assertEqual(
            evidence["current_snapshot"]["activation_outcome"],
            "observed_source_fallback",
        )
        self.assertEqual(
            evidence["current_snapshot"]["fallback_reason"], "launcher_exit_nonzero"
        )
        self.assertEqual(
            evidence["current_snapshot"]["selected_config_file"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertEqual(
            evidence["current_snapshot"]["selected_source_kind"],
            "observed_stable_inventory_source",
        )
        state = json.loads((self.managed_dir / "supervisor-state.json").read_text())
        self.assertEqual(
            state["launcher_stable_config"],
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
        )
        self.assertEqual(
            (self.stable_dir / "config.yaml").read_text(encoding="utf-8"), baseline_text
        )
        self.assertIn(
            str(self.managed_dir / "stable-runtime-config.generated.yaml"),
            payload["changed_files"],
        )
        self.assertIn(str(self.managed_dir / "supervisor-state.json"), payload["changed_files"])
        self.assertIn(str(self.profile_dir / "config.toml"), payload["changed_files"])
        self.assertIn(
            str(self.profile_dir / "runtime-effective-mode.txt"),
            payload["changed_files"],
        )
        status_payload = json.loads(status_result.stdout)
        self.assertEqual(
            status_payload["stable_runtime_consumer"][
                "effective_stable_runtime_consumer_source"
            ]["source_kind"],
            "observed_stable_inventory_source",
        )

    def test_stable_runtime_consumer_contract_does_not_leak_to_unrelated_json_surfaces(
        self,
    ) -> None:
        for args in (
            ("healthcheck", "--json"),
            ("accounts", "list", "--json"),
            ("stable", "repair", "--dry-run", "--json"),
            ("sync", "--json"),
        ):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                payload = json.loads(result.stdout)
                self.assertNotIn("stable_runtime_consumer", payload)

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

    def test_sync_does_not_expose_deterministic_stable_recovery_result(self) -> None:
        result = self.run_cli("sync", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertNotIn("deterministic_stable_recovery_result", payload)
        self.assertNotIn("last_known_good_proxy", payload)
        self.assertNotIn("last_known_good_proxy_contract", payload)
        self.assertNotIn("current_proxy_adoption_contract", payload)

    def test_sync_reports_managed_pid_deletion_in_changed_files(self) -> None:
        pid_path = self.managed_dir / "managed-proxy.pid"
        pid_path.write_text("999999\n", encoding="utf-8")
        sync_script = self.profile_dir / "sync-deletes-managed-pid.sh"
        sync_script.write_text(
            "#!/bin/sh\n"
            f"rm -f '{pid_path}'\n"
            "echo sync-removed-pid >&2\n",
            encoding="utf-8",
        )
        sync_script.chmod(0o755)
        result = self.run_cli_with_env({"WBP_SYNC_SCRIPT": str(sync_script)}, "sync", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn(str(pid_path), payload["changed_files"])
        self.assertEqual(result.stderr.strip(), "sync-removed-pid")

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

    def test_status_reports_default_launcher_provisioning_available_before_materialization(
        self,
    ) -> None:
        result = self.run_cli("status", "--json", include_launcher_override=False)
        payload = json.loads(result.stdout)
        contract = payload["current_proxy_adoption_contract"]
        self.assertEqual(
            contract["launcher_consumer_status"],
            "repo_owned_default_consumer_provisioning_available",
        )
        self.assertEqual(
            contract["external_launcher_readiness_status"],
            "default_path_missing_repo_consumer_unprovisioned",
        )
        self.assertFalse(contract["repo_owned_default_consumer_provisioned"])
        self.assertEqual(
            contract["external_launcher_path_surface"]["path_kind"],
            "default_owned_provisioning_target",
        )
        self.assertFalse(
            contract["external_launcher_path_surface"]["repo_managed_marker_present"]
        )
        self.assertFalse(
            contract["external_launcher_path_surface"]["repo_managed_marker_valid"]
        )
        self.assertFalse(
            contract["external_launcher_path_surface"][
                "repo_managed_marker_recognized"
            ]
        )

    def test_launch_smoke_materializes_repo_owned_default_launcher_when_default_path_is_absent(
        self,
    ) -> None:
        stable_port = free_port()
        self.assertFalse(self.default_launcher_script.exists())
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli(
                "launch",
                "smoke",
                "--json",
                include_launcher_override=False,
            )
            status_result = self.run_cli(
                "status",
                "--json",
                include_launcher_override=False,
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(self.default_launcher_script.exists())
        self.assertIn(
            runtime_mod.REPO_MANAGED_DEFAULT_LAUNCHER_MARKER,
            self.default_launcher_script.read_text(encoding="utf-8"),
        )
        self.assertIn(str(self.default_launcher_script), payload["changed_files"])
        self.assertNotIn("current_proxy_adoption_contract", payload)
        status_payload = json.loads(status_result.stdout)
        contract = status_payload["current_proxy_adoption_contract"]
        self.assertTrue(contract["repo_owned_default_consumer_provisioned"])
        self.assertEqual(
            contract["external_launcher_readiness_status"],
            "default_path_provisioned_repo_managed",
        )
        self.assertTrue(
            contract["external_launcher_path_surface"]["repo_managed_marker_present"]
        )
        self.assertTrue(
            contract["external_launcher_path_surface"]["repo_managed_marker_valid"]
        )
        self.assertTrue(
            contract["external_launcher_path_surface"][
                "repo_managed_marker_recognized"
            ]
        )

    def test_launch_smoke_does_not_overwrite_unmarked_default_launcher_file(self) -> None:
        original_text = "#!/bin/sh\nmode=\"$1\"\n[ \"$mode\" = smoke ] || exit 7\nexit 9\n"
        self.default_launcher_script.write_text(original_text, encoding="utf-8")
        self.default_launcher_script.chmod(0o755)
        result = self.run_cli(
            "launch",
            "smoke",
            "--json",
            include_launcher_override=False,
        )
        self.assertEqual(result.returncode, 9, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "LAUNCHER_EXIT_NONZERO")
        self.assertEqual(
            self.default_launcher_script.read_text(encoding="utf-8"),
            original_text,
        )
        self.assertNotIn(str(self.default_launcher_script), payload["changed_files"])

    def test_status_does_not_treat_invalid_marked_default_launcher_as_provisioned(
        self,
    ) -> None:
        invalid_marked_text = (
            "#!/bin/sh\n"
            f"{runtime_mod.REPO_MANAGED_DEFAULT_LAUNCHER_MARKER}\n"
            f"{runtime_mod.REPO_MANAGED_DEFAULT_LAUNCHER_DIGEST_PREFIX}invalid\n"
            "exit 0\n"
        )
        self.default_launcher_script.write_text(invalid_marked_text, encoding="utf-8")
        self.default_launcher_script.chmod(0o755)
        result = self.run_cli("status", "--json", include_launcher_override=False)
        payload = json.loads(result.stdout)
        contract = payload["current_proxy_adoption_contract"]
        self.assertFalse(contract["repo_owned_default_consumer_provisioned"])
        self.assertEqual(
            contract["external_launcher_readiness_status"],
            "default_path_present_repo_marker_invalid",
        )
        self.assertTrue(
            contract["external_launcher_path_surface"]["repo_managed_marker_present"]
        )
        self.assertFalse(
            contract["external_launcher_path_surface"]["repo_managed_marker_valid"]
        )
        self.assertFalse(
            contract["external_launcher_path_surface"][
                "repo_managed_marker_recognized"
            ]
        )

    def test_launch_smoke_does_not_overwrite_self_signed_unrecognized_default_launcher_file(
        self,
    ) -> None:
        custom_payload = (
            "set -eu\n"
            "mode=\"$1\"\n"
            "[ \"$mode\" = smoke ] || exit 7\n"
            "exit 9\n"
        )
        custom_text = runtime_mod.render_repo_owned_default_launcher_script_text(
            custom_payload
        )
        self.default_launcher_script.write_text(custom_text + "\n", encoding="utf-8")
        self.default_launcher_script.chmod(0o755)
        result = self.run_cli(
            "launch",
            "smoke",
            "--json",
            include_launcher_override=False,
        )
        self.assertEqual(result.returncode, 9, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "LAUNCHER_EXIT_NONZERO")
        self.assertEqual(
            self.default_launcher_script.read_text(encoding="utf-8").rstrip("\n"),
            custom_text.rstrip("\n"),
        )
        self.assertNotIn(str(self.default_launcher_script), payload["changed_files"])

    def test_launch_smoke_repairs_exec_bit_for_recognized_default_launcher_file(
        self,
    ) -> None:
        self.default_launcher_script.write_text(
            runtime_mod.build_repo_owned_default_launcher_script_text() + "\n",
            encoding="utf-8",
        )
        self.default_launcher_script.chmod(0o644)
        stable_port = free_port()
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {stable_port}\n",
            encoding="utf-8",
        )
        server = ThreadingHTTPServer(("127.0.0.1", stable_port), ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_cli(
                "launch",
                "smoke",
                "--json",
                include_launcher_override=False,
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(os.access(self.default_launcher_script, os.X_OK))
        self.assertIn(str(self.default_launcher_script), payload["changed_files"])

    def test_launch_smoke_does_not_materialize_default_launcher_for_nondefault_override(
        self,
    ) -> None:
        missing_override = self.profile_dir / "missing-custom-launch.sh"
        self.assertFalse(self.default_launcher_script.exists())
        result = self.run_cli_with_env(
            {"WBP_LAUNCHER_SCRIPT": str(missing_override)},
            "launch",
            "smoke",
            "--json",
            include_launcher_override=False,
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["machine_error_code"], "MISSING_LAUNCHER_SCRIPT")
        self.assertFalse(self.default_launcher_script.exists())
        self.assertFalse(missing_override.exists())

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
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertEqual(payload["effective_mode"], "stable")
        self.assertIn("Listener is not reachable", payload["last_error"])


if __name__ == "__main__":
    unittest.main()
