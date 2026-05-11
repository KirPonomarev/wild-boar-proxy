# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sample_route(
    route_id: str = "wbp-deepseek-v3",
    *,
    base_url: str = "https://openrouter.ai/api/v1",
    upstream_model: str = "deepseek/deepseek-chat",
    cost_class: str = "paid_or_free_limited",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "route_id": route_id,
        "display_name": "DeepSeek V3",
        "provider": "openrouter",
        "base_url": base_url,
        "endpoint_path": "/chat/completions",
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
        "cost_class": cost_class,
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": True,
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


@contextmanager
def mocked_provider(
    *,
    expected_token: str = "test-key",
    models: list[str] | None = None,
    malformed_models: bool = False,
    malformed_smoke: bool = False,
) -> tuple[str, ThreadingHTTPServer]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorized(self) -> bool:
            return self.headers.get("Authorization") == f"Bearer {expected_token}"

        def do_GET(self) -> None:  # noqa: N802
            self.server.request_count += 1
            if self.path != "/v1/models":
                self._send_json(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._send_json(401, {"error": "auth_failed"})
                return
            if malformed_models:
                self._send_json(200, {"unexpected": True})
                return
            self._send_json(
                200,
                {"data": [{"id": model_id} for model_id in (models or ["deepseek/deepseek-chat"])]},
            )

        def do_POST(self) -> None:  # noqa: N802
            self.server.request_count += 1
            if self.path != "/v1/chat/completions":
                self._send_json(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._send_json(401, {"error": "auth_failed"})
                return
            if malformed_smoke:
                self._send_json(200, {"unexpected": True})
                return
            self._send_json(
                200,
                {
                    "id": "chatcmpl-test",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "pong"}}
                    ],
                },
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.request_count = 0  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f"http://127.0.0.1:{port}/v1", server)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class ExternalModelsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.external_dir = self.root / "external-models"
        self.profile_dir.mkdir(parents=True)
        self.managed_dir.mkdir(parents=True)
        self.stable_dir.mkdir(parents=True)
        self.external_dir.mkdir(parents=True)
        (self.profile_dir / "config.toml").write_text("", encoding="utf-8")
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps({"schema_version": 2, "backends": []}) + "\n", encoding="utf-8"
        )
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps({"schema_version": 2}) + "\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 8318\n", encoding="utf-8"
        )
        (self.external_dir / "secrets.env").write_text(
            "OPENROUTER_API_KEY=test-key\n", encoding="utf-8"
        )
        os.chmod(self.external_dir / "secrets.env", 0o600)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_CONFIG_TOML"] = str(self.profile_dir / "config.toml")
        env["WBP_RUNTIME_MODE_FILE"] = str(self.profile_dir / "runtime-mode.txt")
        env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
            self.profile_dir / "runtime-effective-mode.txt"
        )
        env["WBP_REGISTRY_FILE"] = str(self.managed_dir / "backend-registry.json")
        env["WBP_STATE_FILE"] = str(self.managed_dir / "supervisor-state.json")
        env["WBP_MANAGED_CONFIG_FILE"] = str(self.managed_dir / "managed-config.yaml")
        env["WBP_EXTERNAL_MODELS_DIR"] = str(self.external_dir)
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    def run_cli(
        self, *args: str, stdin_text: str | None = None, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = self.env()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=env,
            input=stdin_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def parse_payload(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
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
            "data",
            "timestamp_utc",
        ):
            self.assertIn(field, payload)
        return payload

    def test_routes_add_list_disable_remove_round_trip(self) -> None:
        route_file = self.root / "route.json"
        route_file.write_text(json.dumps(sample_route()) + "\n", encoding="utf-8")

        add_result = self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--file",
            str(route_file),
        )
        add_payload = self.parse_payload(add_result)
        self.assertEqual(add_payload["status"], "ok")
        self.assertEqual(add_payload["machine_error_code"], "OK")

        list_result = self.run_cli("external-models", "routes", "list", "--json")
        list_payload = self.parse_payload(list_result)
        self.assertEqual(list_payload["data"]["count"], 1)
        self.assertEqual(list_payload["data"]["routes"][0]["route_id"], "wbp-deepseek-v3")

        disable_result = self.run_cli(
            "external-models",
            "routes",
            "disable",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        disable_payload = self.parse_payload(disable_result)
        self.assertTrue(disable_payload["data"]["enabled"] is False)

        remove_result = self.run_cli(
            "external-models",
            "routes",
            "remove",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        remove_payload = self.parse_payload(remove_result)
        self.assertEqual(remove_payload["status"], "ok")
        routes_payload = json.loads((self.external_dir / "routes.json").read_text())
        self.assertEqual(routes_payload["routes"], [])

    def test_routes_add_from_stdin_and_models_projection(self) -> None:
        add_result = self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route("wbp-qwen-coder")),
        )
        self.assertEqual(self.parse_payload(add_result)["status"], "ok")
        models_result = self.run_cli("external-models", "models", "--json")
        models_payload = self.parse_payload(models_result)
        self.assertEqual(models_payload["data"]["count"], 1)
        model = models_payload["data"]["models"][0]
        self.assertEqual(model["route_id"], "wbp-qwen-coder")
        self.assertNotIn("auth", model)

    def test_duplicate_route_is_rejected(self) -> None:
        route_file = self.root / "route.json"
        route_file.write_text(json.dumps(sample_route()) + "\n", encoding="utf-8")
        first = self.run_cli(
            "external-models", "routes", "add", "--json", "--file", str(route_file)
        )
        self.assertEqual(self.parse_payload(first)["status"], "ok")
        second = self.run_cli(
            "external-models", "routes", "add", "--json", "--file", str(route_file)
        )
        payload = self.parse_payload(second)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "duplicate_route")

    def test_profile_packet_is_non_mutating_and_local_only(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )
        profile_result = self.run_cli(
            "external-models",
            "profile",
            "codex-desktop",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(profile_result)
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["data"]["writes_external_config"])
        self.assertFalse(payload["data"]["profile_ready"])
        self.assertIsNone(payload["data"]["base_url"])
        self.assertEqual(payload["data"]["prerequisite"], "live_listener_contour_required")

    def test_evidence_capture_writes_local_artifact(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )
        result = self.run_cli(
            "external-models",
            "evidence",
            "capture",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        evidence_path = Path(payload["data"]["evidence_path"])
        self.assertTrue(evidence_path.exists())
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertFalse(evidence_payload["network_dependent_evidence"])

    def test_status_uses_isolated_external_model_paths(self) -> None:
        result = self.run_cli("external-models", "status", "--json")
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["foundation_phase"], "C3")
        self.assertEqual(payload["data"]["adapter_state"], "stopped")
        self.assertFalse(payload["data"]["listener_proven"])
        self.assertTrue(payload["data"]["runtime_claim_blocked"])
        self.assertEqual(
            Path(payload["data"]["paths"]["routes_file"]).resolve(),
            (self.external_dir / "routes.json").resolve(),
        )

    def test_start_status_models_profile_stop_synthetic_lifecycle(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )

        start_result = self.run_cli("external-models", "start", "--json")
        start_payload = self.parse_payload(start_result)
        self.assertEqual(start_payload["status"], "ok")
        self.assertEqual(start_payload["machine_error_code"], "OK")
        self.assertFalse(start_payload["data"]["listener_proven"])
        self.assertTrue(start_payload["data"]["runtime_claim_blocked"])
        self.assertNotIn("test-key", start_result.stdout)
        secrets_text = (self.external_dir / "secrets.env").read_text(encoding="utf-8")
        self.assertIn("WBP_EXTERNAL_MODELS_LOCAL_TOKEN=", secrets_text)
        local_token = [
            line.split("=", 1)[1]
            for line in secrets_text.splitlines()
            if line.startswith("WBP_EXTERNAL_MODELS_LOCAL_TOKEN=")
        ][0]
        self.assertNotIn(local_token, start_result.stdout)
        state_payload = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state_payload["adapter"]["state"], "started")
        self.assertNotIn(state_payload["adapter"]["port"], (8318, 8320))
        self.assertTrue(state_payload["local_auth"]["token_present"])

        second_start = self.run_cli("external-models", "start", "--json")
        second_payload = self.parse_payload(second_start)
        self.assertEqual(second_payload["machine_error_code"], "already_running")

        status_result = self.run_cli("external-models", "status", "--json")
        status_payload = self.parse_payload(status_result)
        self.assertEqual(status_payload["data"]["adapter_state"], "started")
        self.assertFalse(status_payload["data"]["listener_proven"])
        self.assertTrue(status_payload["data"]["runtime_claim_blocked"])
        self.assertIn("base_url", status_payload["data"]["adapter"])

        models_result = self.run_cli("external-models", "models", "--json")
        models_payload = self.parse_payload(models_result)
        self.assertEqual(models_payload["data"]["models"][0]["synthetic_adapter_state"], "started")
        self.assertFalse(models_payload["data"]["models"][0]["profile_ready"])

        profile_result = self.run_cli(
            "external-models",
            "profile",
            "codex-desktop",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        profile_payload = self.parse_payload(profile_result)
        self.assertFalse(profile_payload["data"]["profile_ready"])
        self.assertFalse(profile_payload["data"]["listener_proven"])
        self.assertTrue(profile_payload["data"]["runtime_claim_blocked"])
        self.assertIsNotNone(profile_payload["data"]["base_url"])

        stop_result = self.run_cli("external-models", "stop", "--json")
        stop_payload = self.parse_payload(stop_result)
        self.assertEqual(stop_payload["status"], "ok")
        self.assertFalse(stop_payload["data"]["listener_proven"])
        stopped_state = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(stopped_state["adapter"]["state"], "stopped")
        self.assertIsNone(stopped_state["adapter"]["base_url"])
        self.assertTrue(stopped_state["local_auth"]["token_present"])

    def test_v1_state_is_migrated_by_status(self) -> None:
        (self.external_dir / "state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "policy": {
                        "paid_routes_enabled": False,
                        "paid_route_allowlist": [],
                        "paid_route_default": "blocked",
                    },
                    "routes": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        result = self.run_cli("external-models", "status", "--json")
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["adapter"]["state"], "stopped")

    def test_secrets_permissions_are_enforced(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )
        os.chmod(self.external_dir / "secrets.env", 0o644)
        result = self.run_cli(
            "external-models",
            "profile",
            "codex-desktop",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "unsafe_secret_permissions")
        self.assertEqual(
            stat.S_IMODE((self.external_dir / "secrets.env").stat().st_mode), 0o644
        )

    def test_route_validate_success_writes_network_evidence_and_state(self) -> None:
        with mocked_provider() as (base_url, _server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_route(base_url=base_url)),
            )
            result = self.run_cli(
                "external-models",
                "routes",
                "validate",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["validation_kind"], "provider_route_validate")
        self.assertEqual(payload["data"]["verification_scope"], "route_provider_only")
        self.assertEqual(payload["data"]["route_state"], "model_visible")
        self.assertFalse(payload["data"]["listener_proven"])
        self.assertTrue(payload["data"]["runtime_claim_blocked"])
        self.assertFalse(payload["data"]["profile_ready"])
        self.assertNotIn("test-key", result.stdout)
        state_payload = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            state_payload["routes"]["wbp-deepseek-v3"]["availability_state"],
            "model_visible",
        )
        evidence_path = Path(payload["data"]["evidence_path"])
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertTrue(evidence_payload["network_dependent_evidence"])
        self.assertEqual(evidence_payload["verification_scope"], "route_provider_only")

    def test_route_validate_auth_failure_updates_route_state(self) -> None:
        with mocked_provider(expected_token="expected-token") as (base_url, _server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_route(base_url=base_url)),
            )
            result = self.run_cli(
                "external-models",
                "routes",
                "validate",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "provider_auth_failed")
        self.assertEqual(payload["data"]["verification_scope"], "route_provider_only")
        self.assertEqual(payload["data"]["route_state"], "provider_auth_failed")
        self.assertEqual(
            [str(Path(item).resolve()) for item in payload["changed_files"]],
            [str((self.external_dir / "state.json").resolve())],
        )
        state_payload = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            state_payload["routes"]["wbp-deepseek-v3"]["availability_state"],
            "provider_auth_failed",
        )

    def test_route_validate_model_unavailable_updates_route_state(self) -> None:
        with mocked_provider(models=["other/model"]) as (base_url, _server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_route(base_url=base_url)),
            )
            result = self.run_cli(
                "external-models",
                "routes",
                "validate",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "model_not_available")
        self.assertEqual(payload["data"]["route_state"], "model_not_available")

    def test_check_success_writes_verified_state_and_evidence(self) -> None:
        with mocked_provider() as (base_url, server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_route(base_url=base_url)),
            )
            result = self.run_cli(
                "external-models",
                "check",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
            request_count = server.request_count  # type: ignore[attr-defined]
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["check_kind"], "provider_route_smoke")
        self.assertEqual(payload["data"]["verification_scope"], "route_provider_only")
        self.assertEqual(payload["data"]["route_state"], "verified")
        self.assertEqual(payload["data"]["request_count"], 1)
        self.assertEqual(request_count, 1)
        self.assertFalse(payload["data"]["listener_proven"])
        state_payload = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            state_payload["routes"]["wbp-deepseek-v3"]["availability_state"], "verified"
        )
        self.assertEqual(
            state_payload["routes"]["wbp-deepseek-v3"]["effective_model"],
            "deepseek/deepseek-chat",
        )
        evidence_payload = json.loads(
            Path(payload["data"]["evidence_path"]).read_text(encoding="utf-8")
        )
        self.assertTrue(evidence_payload["network_dependent_evidence"])
        self.assertEqual(
            evidence_payload["result"]["effective_model"], "deepseek/deepseek-chat"
        )

    def test_check_paid_route_is_blocked_without_provider_call(self) -> None:
        with mocked_provider() as (base_url, server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(
                    sample_route(base_url=base_url, route_id="wbp-paid", cost_class="paid_direct")
                ),
            )
            result = self.run_cli(
                "external-models",
                "check",
                "--json",
                "--route",
                "wbp-paid",
            )
            request_count = server.request_count  # type: ignore[attr-defined]
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "paid_route_blocked")
        self.assertEqual(payload["data"]["route_state"], "blocked")
        self.assertEqual(request_count, 0)

    def test_check_network_failure_is_route_local_only(self) -> None:
        route = sample_route(base_url=f"http://127.0.0.1:{_free_port()}/v1")
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(route),
        )
        result = self.run_cli(
            "external-models",
            "check",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "provider_network_failed")
        self.assertEqual(payload["data"]["verification_scope"], "route_provider_only")
        state_payload = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            state_payload["routes"]["wbp-deepseek-v3"]["availability_state"],
            "provider_network_failed",
        )
        status_payload = self.parse_payload(self.run_cli("external-models", "status", "--json"))
        self.assertEqual(status_payload["data"]["adapter_state"], "stopped")
        self.assertFalse(status_payload["data"]["listener_proven"])


class ZeroTestSelectionGuardTests(unittest.TestCase):
    def test_module_contains_real_tests(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExternalModelsCliTests)
        self.assertGreaterEqual(suite.countTestCases(), 10)
