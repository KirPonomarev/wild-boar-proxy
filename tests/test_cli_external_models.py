# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from wild_boar_proxy.core import packets


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


def sample_direct_deepseek_route(
    route_id: str = "wbp-deepseek-v3",
    *,
    base_url: str = "https://api.deepseek.com/v1",
    upstream_model: str = "deepseek-chat",
    cost_class: str = "paid_or_free_limited",
) -> dict[str, object]:
    return sample_route(
        route_id=route_id,
        base_url=base_url,
        upstream_model=upstream_model,
        cost_class=cost_class,
    ) | {
        "display_name": "DeepSeek direct",
        "provider": "deepseek",
        "auth": {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"},
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
    smoke_payload: dict[str, object] | None = None,
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
            raw_length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(raw_length) if raw_length else b""
            if raw_body:
                self.server.last_request_payload = json.loads(raw_body.decode("utf-8"))  # type: ignore[attr-defined]
            self._send_json(
                200,
                smoke_payload
                or {
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
    server.last_request_payload = None  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f"http://127.0.0.1:{port}/v1", server)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@contextmanager
def mocked_runtime_bridge(*, response_text: str) -> tuple[str, ThreadingHTTPServer]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            raw_length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(raw_length) if raw_length else b"{}"
            try:
                self.server.last_request_payload = json.loads(raw_body.decode("utf-8"))  # type: ignore[attr-defined]
            except json.JSONDecodeError:
                self.server.last_request_payload = {}  # type: ignore[attr-defined]
            self.server.request_count += 1  # type: ignore[attr-defined]
            raw = json.dumps({"output_text": response_text}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.request_count = 0  # type: ignore[attr-defined]
    server.last_request_payload = {}  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f"http://127.0.0.1:{port}", server)
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
        self.external_dir = self.managed_dir / "external-models"
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
            "effect",
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
        self.assertEqual(add_payload["effect"], "mutate")

        list_result = self.run_cli("external-models", "routes", "list", "--json")
        list_payload = self.parse_payload(list_result)
        self.assertEqual(list_payload["effect"], "read")
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
        self.assertEqual(disable_payload["effect"], "mutate")
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
        self.assertEqual(remove_payload["effect"], "mutate")
        routes_payload = json.loads((self.external_dir / "routes.json").read_text())
        self.assertEqual(routes_payload["routes"], [])

    def test_credentials_admit_and_status_owner_env_without_secret_leak(self) -> None:
        with mocked_provider(expected_token="admit-owner-env-key") as (base_url, _server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_route(base_url=base_url)),
            )
            admit_result = self.run_cli(
                "external-models",
                "credentials",
                "admit",
                "--provider",
                "openrouter",
                "--source",
                "owner-env",
                "--json",
                extra_env={"OPENROUTER_API_KEY": "admit-owner-env-key"},
            )
            admit_payload = self.parse_payload(admit_result)
            self.assertEqual(admit_payload["status"], "ok")
            self.assertEqual(admit_payload["machine_error_code"], "OK")
            self.assertEqual(admit_payload["next_action"], "api_route_connect")
            credential_result = admit_payload["data"]["credential_result"]
            self.assertEqual(credential_result["status"], "admitted")
            self.assertEqual(credential_result["provider"], "openrouter")
            self.assertEqual(credential_result["source"], "owner-env")
            self.assertEqual(credential_result["credential_ref"], "OPENROUTER_API_KEY")
            self.assertTrue(credential_result["credential_present"])
            self.assertFalse(credential_result["secret_value_exposed"])
            self.assertFalse(credential_result["browser_secret_intake"])
            self.assertFalse(credential_result["browser_path_intake"])
            self.assertEqual(credential_result["scope"], "sandbox")
            self.assertNotIn("admit-owner-env-key", admit_result.stdout)
            self.assertFalse(
                packets.command_packet_has_secret_leak(
                    admit_payload,
                    secret_values=["admit-owner-env-key"],
                )
            )
            self.assertEqual(
                stat.S_IMODE((self.external_dir / "secrets.env").stat().st_mode),
                0o600,
            )
            secrets_text = (self.external_dir / "secrets.env").read_text(encoding="utf-8")
            self.assertIn("OPENROUTER_API_KEY=admit-owner-env-key", secrets_text)

            status_result = self.run_cli(
                "external-models",
                "credentials",
                "status",
                "--provider",
                "openrouter",
                "--json",
            )
            status_payload = self.parse_payload(status_result)
            self.assertEqual(status_payload["status"], "ok")
            self.assertEqual(status_payload["next_action"], "none")
            status_credential = status_payload["data"]["credential_result"]
            self.assertEqual(status_credential["status"], "present")
            self.assertTrue(status_credential["credential_present"])
            self.assertEqual(status_credential["credential_ref"], "OPENROUTER_API_KEY")
            self.assertFalse(status_credential["secret_value_exposed"])
            self.assertNotIn("admit-owner-env-key", status_result.stdout)
            self.assertFalse(
                packets.command_packet_has_secret_leak(
                    status_payload,
                    secret_values=["admit-owner-env-key"],
                )
            )

            lifecycle_status = self.run_cli("external-models", "status", "--json")
            lifecycle_payload = self.parse_payload(lifecycle_status)
            self.assertEqual(lifecycle_payload["status"], "ok")
            self.assertTrue(lifecycle_payload["data"]["local_auth"]["token_present"])
            self.assertNotIn("admit-owner-env-key", lifecycle_status.stdout)

            validate_result = self.run_cli(
                "external-models",
                "routes",
                "validate",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
            validate_payload = self.parse_payload(validate_result)
            self.assertEqual(validate_payload["status"], "ok")
            self.assertEqual(validate_payload["machine_error_code"], "OK")

    def test_deepseek_credentials_admit_and_status_use_direct_provider_refs(self) -> None:
        admit_result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "deepseek",
            "--source",
            "owner-env",
            "--json",
            extra_env={"DEEPSEEK_API_KEY": "deepseek-owner-key"},
        )
        admit_payload = self.parse_payload(admit_result)
        self.assertEqual(admit_payload["status"], "ok")
        credential_result = admit_payload["data"]["credential_result"]
        self.assertEqual(credential_result["status"], "admitted")
        self.assertEqual(credential_result["provider"], "deepseek")
        self.assertEqual(credential_result["credential_ref"], "DEEPSEEK_API_KEY")
        self.assertEqual(
            credential_result["expected_refs"],
            [
                "DEEPSEEK_API_KEY",
                "WBP_DEEPSEEK_API_KEY",
                "WBP_PROVIDER_DEEPSEEK_API_KEY",
            ],
        )
        self.assertEqual(
            credential_result["provider_dashboard_url"],
            "https://platform.deepseek.com/api_keys",
        )
        self.assertFalse(credential_result["secret_value_exposed"])
        self.assertNotIn("deepseek-owner-key", admit_result.stdout)

        status_result = self.run_cli(
            "external-models",
            "credentials",
            "status",
            "--provider",
            "deepseek",
            "--json",
        )
        status_payload = self.parse_payload(status_result)
        self.assertEqual(status_payload["status"], "ok")
        self.assertEqual(status_payload["effect"], "read")
        self.assertEqual(status_payload["changed_files"], [])
        status_credential = status_payload["data"]["credential_result"]
        self.assertEqual(status_credential["status"], "present")
        self.assertEqual(status_credential["provider"], "deepseek")
        self.assertEqual(status_credential["credential_ref"], "DEEPSEEK_API_KEY")
        self.assertNotIn("deepseek-owner-key", status_result.stdout)

    def test_direct_deepseek_route_validate_check_and_live_format_prove_no_fallback(
        self,
    ) -> None:
        secret_value = "deepseek-owner-key"
        with mocked_provider(
            expected_token=secret_value,
            models=["deepseek-chat"],
            smoke_payload={
                "id": "chatcmpl-direct-deepseek-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "API_ONLY_DEEPSEEK_READY",
                        },
                    }
                ],
            },
        ) as (base_url, server):
            admit_result = self.run_cli(
                "external-models",
                "credentials",
                "admit",
                "--provider",
                "deepseek",
                "--source",
                "owner-env",
                "--json",
                extra_env={"DEEPSEEK_API_KEY": secret_value},
            )
            admit_payload = self.parse_payload(admit_result)
            self.assertEqual(admit_payload["status"], "ok")
            credential_result = admit_payload["data"]["credential_result"]
            self.assertEqual(credential_result["provider"], "deepseek")
            self.assertEqual(credential_result["credential_ref"], "DEEPSEEK_API_KEY")
            self.assertFalse(credential_result["secret_value_exposed"])
            self.assertNotIn(secret_value, admit_result.stdout)
            self.assertFalse(
                packets.command_packet_has_secret_leak(
                    admit_payload,
                    secret_values=[secret_value],
                )
            )

            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_direct_deepseek_route(base_url=base_url)),
            )

            validate_result = self.run_cli(
                "external-models",
                "routes",
                "validate",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
            validate_payload = self.parse_payload(validate_result)
            self.assertEqual(validate_payload["status"], "ok")
            self.assertEqual(validate_payload["data"]["provider"], "deepseek")
            self.assertEqual(validate_payload["data"]["effective_model"], "deepseek-chat")
            self.assertEqual(validate_payload["data"]["verification_scope"], "route_provider_only")
            self.assertFalse(validate_payload["data"]["listener_proven"])
            self.assertTrue(validate_payload["data"]["runtime_claim_blocked"])
            self.assertNotIn(secret_value, validate_result.stdout)
            self.assertFalse(
                packets.command_packet_has_secret_leak(
                    validate_payload,
                    secret_values=[secret_value],
                )
            )
            validate_evidence = json.loads(
                Path(validate_payload["data"]["evidence_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(validate_evidence["result"]["provider"], "deepseek")
            self.assertFalse(validate_evidence["result"]["fallback_used"])
            self.assertEqual(validate_evidence["result"]["fallback_chain"], ["wbp-deepseek-v3"])

            check_result = self.run_cli(
                "external-models",
                "check",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
            check_payload = self.parse_payload(check_result)
            check_request_payload = server.last_request_payload  # type: ignore[attr-defined]
            self.assertEqual(check_payload["status"], "ok")
            self.assertEqual(check_payload["data"]["provider"], "deepseek")
            self.assertEqual(check_payload["data"]["effective_model"], "deepseek-chat")
            self.assertFalse(check_payload["data"]["fallback_used"])
            self.assertEqual(check_payload["data"]["fallback_chain"], ["wbp-deepseek-v3"])
            self.assertEqual(check_payload["data"]["request_count"], 1)
            self.assertEqual(check_request_payload["model"], "deepseek-chat")
            self.assertNotIn(secret_value, check_result.stdout)
            self.assertFalse(
                packets.command_packet_has_secret_leak(
                    check_payload,
                    secret_values=[secret_value],
                )
            )

            request_count_before_live = server.request_count  # type: ignore[attr-defined]
            live_result = self.run_cli(
                "external-models",
                "live-format-check",
                "--json",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Return exactly: API_ONLY_DEEPSEEK_READY",
                "--expected-text",
                "API_ONLY_DEEPSEEK_READY",
            )
            live_request_payload = server.last_request_payload  # type: ignore[attr-defined]
            request_count_after_live = server.request_count  # type: ignore[attr-defined]

        live_payload = self.parse_payload(live_result)
        self.assertEqual(live_payload["status"], "ok")
        self.assertEqual(live_payload["effect"], "probe")
        self.assertEqual(live_payload["changed_files"], [])
        self.assertEqual(live_payload["data"]["provider"], "deepseek")
        self.assertEqual(live_payload["data"]["effective_model"], "deepseek-chat")
        self.assertFalse(live_payload["data"]["fallback_used"])
        self.assertEqual(live_payload["data"]["fallback_chain"], ["wbp-deepseek-v3"])
        self.assertTrue(live_payload["data"]["expected_text_observed"])
        self.assertEqual(live_payload["data"]["response_shape"], "choices_message")
        self.assertFalse(live_payload["data"]["state_written"])
        self.assertFalse(live_payload["data"]["evidence_written"])
        self.assertFalse(live_payload["data"]["file_mutation_attempted"])
        self.assertEqual(request_count_after_live, request_count_before_live + 1)
        self.assertEqual(live_request_payload["model"], "deepseek-chat")
        self.assertNotIn(secret_value, live_result.stdout)
        self.assertFalse(
            packets.command_packet_has_secret_leak(
                live_payload,
                secret_values=[secret_value],
            )
        )

    def test_mistral_credentials_admit_and_status_use_generic_provider_spec(self) -> None:
        admit_result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "mistral",
            "--source",
            "owner-env",
            "--json",
            extra_env={"MISTRAL_API_KEY": "mistral-owner-key"},
        )
        admit_payload = self.parse_payload(admit_result)
        self.assertEqual(admit_payload["status"], "ok")
        credential_result = admit_payload["data"]["credential_result"]
        self.assertEqual(credential_result["status"], "admitted")
        self.assertEqual(credential_result["provider"], "mistral")
        self.assertEqual(credential_result["provider_family"], "direct_provider")
        self.assertEqual(credential_result["auth_type"], "bearer")
        self.assertEqual(
            credential_result["credential_ref"],
            "MISTRAL_API_KEY",
        )
        self.assertEqual(
            credential_result["expected_refs"],
            [
                "MISTRAL_API_KEY",
                "WBP_MISTRAL_API_KEY",
                "WBP_PROVIDER_MISTRAL_API_KEY",
            ],
        )
        self.assertEqual(
            credential_result["provider_dashboard_url"],
            "https://docs.mistral.ai/admin/security-access/api-keys",
        )
        self.assertTrue(credential_result["schema_admitted"])
        self.assertEqual(
            credential_result["classification_scope"],
            "credential_admission_only",
        )
        self.assertFalse(credential_result["provider_runtime_compatibility_claimed"])
        self.assertFalse(credential_result["model_runtime_compatibility_claimed"])
        self.assertFalse(credential_result["generic_route_transform_support_claimed"])
        self.assertFalse(credential_result["generic_response_compatibility_claimed"])
        self.assertFalse(credential_result["provider_family_compatibility_claimed"])
        self.assertFalse(credential_result["secret_value_exposed"])
        self.assertNotIn("mistral-owner-key", admit_result.stdout)

        status_result = self.run_cli(
            "external-models",
            "credentials",
            "status",
            "--provider",
            "mistral",
            "--json",
        )
        status_payload = self.parse_payload(status_result)
        self.assertEqual(status_payload["status"], "ok")
        status_credential = status_payload["data"]["credential_result"]
        self.assertEqual(status_credential["status"], "present")
        self.assertEqual(status_credential["provider"], "mistral")
        self.assertEqual(status_credential["credential_ref"], "MISTRAL_API_KEY")
        self.assertFalse(status_credential["provider_runtime_compatibility_claimed"])
        self.assertNotIn("mistral-owner-key", status_result.stdout)

    def test_credentials_admit_rejects_unsupported_provider(self) -> None:
        result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "unknown-provider",
            "--source",
            "owner-env",
            "--json",
            extra_env={"OPENROUTER_API_KEY": "owner-key"},
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"], "EXTERNAL_MODELS_PROVIDER_UNSUPPORTED"
        )

    def test_credentials_status_rejects_unsupported_provider(self) -> None:
        result = self.run_cli(
            "external-models",
            "credentials",
            "status",
            "--provider",
            "unknown-provider",
            "--json",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(
            payload["machine_error_code"], "EXTERNAL_MODELS_PROVIDER_UNSUPPORTED"
        )

    def test_credentials_admit_rejects_unsupported_source(self) -> None:
        result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "openrouter",
            "--source",
            "browser-input",
            "--json",
            extra_env={"OPENROUTER_API_KEY": "owner-key"},
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            "EXTERNAL_MODELS_CREDENTIAL_SOURCE_UNSUPPORTED",
        )

    def test_credentials_admit_rejects_missing_owner_env(self) -> None:
        result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "openrouter",
            "--source",
            "owner-env",
            "--json",
            extra_env={
                "OPENROUTER_API_KEY": "",
                "WBP_OPENROUTER_API_KEY": "",
                "WBP_PROVIDER_OPENROUTER_API_KEY": "",
            },
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING",
        )
        self.assertEqual(payload["next_action"], "owner_action")
        credential_result = payload["data"]["credential_result"]
        self.assertEqual(credential_result["status"], "missing")
        self.assertEqual(credential_result["provider"], "openrouter")
        self.assertEqual(credential_result["source"], "owner-env")
        self.assertEqual(credential_result["credential_ref"], "OPENROUTER_API_KEY")
        self.assertFalse(credential_result["credential_present"])
        self.assertEqual(credential_result["supported_sources"], ["owner-env"])
        self.assertEqual(
            credential_result["expected_refs"],
            [
                "OPENROUTER_API_KEY",
                "WBP_OPENROUTER_API_KEY",
                "WBP_PROVIDER_OPENROUTER_API_KEY",
            ],
        )
        self.assertEqual(
            credential_result["provider_dashboard_url"],
            "https://openrouter.ai/settings/keys",
        )
        self.assertFalse(credential_result["secret_value_exposed"])
        self.assertFalse(credential_result["browser_secret_intake"])
        self.assertFalse(credential_result["browser_path_intake"])

    def test_credentials_status_reports_missing_without_secret_exposure(self) -> None:
        (self.external_dir / "secrets.env").write_text("", encoding="utf-8")
        os.chmod(self.external_dir / "secrets.env", 0o600)
        result = self.run_cli(
            "external-models",
            "credentials",
            "status",
            "--provider",
            "openrouter",
            "--json",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        credential_result = payload["data"]["credential_result"]
        self.assertEqual(credential_result["status"], "missing")
        self.assertFalse(credential_result["credential_present"])
        self.assertEqual(credential_result["credential_ref"], "OPENROUTER_API_KEY")
        self.assertEqual(credential_result["supported_sources"], ["owner-env"])
        self.assertEqual(
            credential_result["expected_refs"],
            [
                "OPENROUTER_API_KEY",
                "WBP_OPENROUTER_API_KEY",
                "WBP_PROVIDER_OPENROUTER_API_KEY",
            ],
        )
        self.assertEqual(
            credential_result["provider_dashboard_url"],
            "https://openrouter.ai/settings/keys",
        )
        self.assertFalse(credential_result["secret_value_exposed"])

    def test_credentials_admit_blocks_unproven_sandbox_target(self) -> None:
        outside_external = self.root / "outside-external-models"
        outside_external.mkdir(parents=True, exist_ok=True)
        (outside_external / "secrets.env").write_text("", encoding="utf-8")
        os.chmod(outside_external / "secrets.env", 0o600)
        result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "openrouter",
            "--source",
            "owner-env",
            "--json",
            extra_env={
                "OPENROUTER_API_KEY": "owner-key",
                "WBP_EXTERNAL_MODELS_DIR": str(outside_external),
            },
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            "EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN",
        )

    def test_credentials_admit_requires_json_flag(self) -> None:
        result = self.run_cli(
            "external-models",
            "credentials",
            "admit",
            "--provider",
            "openrouter",
            "--source",
            "owner-env",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--json", result.stderr)

    def test_credentials_status_requires_json_flag(self) -> None:
        result = self.run_cli(
            "external-models",
            "credentials",
            "status",
            "--provider",
            "openrouter",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--json", result.stderr)

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
        self.assertEqual(payload["effect"], "read")
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
        self.assertEqual(payload["effect"], "mutate")
        evidence_path = Path(payload["data"]["evidence_path"])
        self.assertTrue(evidence_path.exists())
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertFalse(evidence_payload["network_dependent_evidence"])

    def test_status_uses_isolated_external_model_paths(self) -> None:
        result = self.run_cli("external-models", "status", "--json")
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
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
        self.assertEqual(start_payload["effect"], "mutate")
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
        self.assertEqual(second_payload["effect"], "mutate")

        status_result = self.run_cli("external-models", "status", "--json")
        status_payload = self.parse_payload(status_result)
        self.assertEqual(status_payload["effect"], "read")
        self.assertEqual(status_payload["data"]["adapter_state"], "started")
        self.assertFalse(status_payload["data"]["listener_proven"])
        self.assertTrue(status_payload["data"]["runtime_claim_blocked"])
        self.assertIn("base_url", status_payload["data"]["adapter"])

        models_result = self.run_cli("external-models", "models", "--json")
        models_payload = self.parse_payload(models_result)
        self.assertEqual(models_payload["effect"], "read")
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
        self.assertEqual(profile_payload["effect"], "read")
        self.assertFalse(profile_payload["data"]["profile_ready"])
        self.assertFalse(profile_payload["data"]["listener_proven"])
        self.assertTrue(profile_payload["data"]["runtime_claim_blocked"])
        self.assertIsNotNone(profile_payload["data"]["base_url"])

        stop_result = self.run_cli("external-models", "stop", "--json")
        stop_payload = self.parse_payload(stop_result)
        self.assertEqual(stop_payload["status"], "ok")
        self.assertEqual(stop_payload["effect"], "mutate")
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
        self.assertEqual(payload["effect"], "mutate")
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
            request_payload = server.last_request_payload  # type: ignore[attr-defined]
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "mutate")
        self.assertEqual(payload["data"]["check_kind"], "provider_route_smoke")
        self.assertEqual(payload["data"]["verification_scope"], "route_provider_only")
        self.assertEqual(payload["data"]["route_state"], "verified")
        self.assertEqual(payload["data"]["request_count"], 1)
        self.assertEqual(request_count, 1)
        self.assertEqual(request_payload["max_tokens"], 96)
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

    def test_check_provider_network_failure_reports_runtime_bridge_without_provider_proof(
        self,
    ) -> None:
        expected_text = "pong"
        route_id = "wbp-deepseek-v3"
        with mocked_runtime_bridge(response_text=expected_text) as (bridge_base_url, bridge):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(
                    sample_route(
                        route_id=route_id,
                        base_url=f"http://127.0.0.1:{_free_port()}/v1",
                    )
                ),
            )
            (self.profile_dir / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "allowed_api_route_ids": [route_id],
                        "agent_id_to_route": {"dip": route_id},
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "bridge_kind": "local_wbp_responses_bridge",
                            "model": route_id,
                            "method": "POST",
                            "url_candidates": [f"{bridge_base_url}/responses"],
                            "request_json_template": {
                                "model": route_id,
                                "input": "Answer exactly one line: <expected_text>",
                                "request_id": "<unique-id>",
                                "stream": False,
                            },
                            "response_text_field": "output_text",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = self.run_cli(
                "external-models",
                "check",
                "--json",
                "--route",
                route_id,
            )

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "provider_network_failed")
        self.assertEqual(
            payload["data"]["route_state"],
            "provider_network_failed_bridge_observed",
        )
        self.assertTrue(payload["data"]["runtime_context_bridge_used"])
        self.assertFalse(payload["data"]["runtime_context_file_bridge_used"])
        self.assertTrue(payload["data"]["bridge_or_file_bridge_used"])
        self.assertTrue(payload["data"]["bridge_live_response_observed"])
        self.assertTrue(payload["data"]["bridge_expected_text_observed"])
        self.assertEqual(payload["data"]["bridge_response_preview_bounded"], expected_text)
        self.assertFalse(payload["data"]["direct_provider_auth_proven"])
        self.assertFalse(payload["data"]["direct_provider_response_observed"])
        self.assertFalse(payload["data"]["provider_auth_ok"])
        self.assertFalse(payload["data"]["positive_provider_proof_gate_satisfied"])
        self.assertFalse(payload["data"]["bridge_green_counts_as_provider_proof"])
        self.assertEqual(bridge.request_count, 1)  # type: ignore[attr-defined]
        state_payload = json.loads((self.external_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            state_payload["routes"][route_id]["availability_state"],
            "provider_network_failed_bridge_observed",
        )
        self.assertTrue(
            state_payload["routes"][route_id]["bridge_live_response_observed"]
        )

    def test_check_auth_failure_does_not_fallback_to_runtime_bridge(self) -> None:
        expected_text = "pong"
        route_id = "wbp-deepseek-v3"
        with mocked_runtime_bridge(response_text=expected_text) as (bridge_base_url, bridge):
            with mocked_provider(expected_token="expected-token") as (base_url, _server):
                self.run_cli(
                    "external-models",
                    "routes",
                    "add",
                    "--json",
                    "--stdin",
                    stdin_text=json.dumps(sample_route(route_id=route_id, base_url=base_url)),
                )
                (self.profile_dir / "wbp-agent-runtime-context.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "allowed_api_route_ids": [route_id],
                            "agent_id_to_route": {"dip": route_id},
                            "deepseek_live_format_check_bridge": {
                                "enabled": True,
                                "bridge_kind": "local_wbp_responses_bridge",
                                "model": route_id,
                                "method": "POST",
                                "url_candidates": [f"{bridge_base_url}/responses"],
                                "request_json_template": {
                                    "model": route_id,
                                    "input": "Answer exactly one line: <expected_text>",
                                    "request_id": "<unique-id>",
                                    "stream": False,
                                },
                                "response_text_field": "output_text",
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                result = self.run_cli(
                    "external-models",
                    "check",
                    "--json",
                    "--route",
                    route_id,
                )

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "provider_auth_failed")
        self.assertEqual(payload["data"]["route_state"], "provider_auth_failed")
        self.assertFalse(payload["data"]["runtime_context_bridge_used"])
        self.assertFalse(payload["data"]["runtime_context_file_bridge_used"])
        self.assertFalse(payload["data"]["bridge_or_file_bridge_used"])
        self.assertFalse(payload["data"]["direct_provider_auth_proven"])
        self.assertFalse(payload["data"]["direct_provider_response_observed"])
        self.assertEqual(bridge.request_count, 0)  # type: ignore[attr-defined]

    def test_live_format_check_calls_provider_once_without_state_or_evidence_writes(self) -> None:
        with mocked_provider(
            smoke_payload={
                "id": "chatcmpl-live-format-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "API_ONLY_DEEPSEEK_READY",
                        },
                    }
                ],
            },
        ) as (base_url, server):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(sample_route(base_url=base_url)),
            )
            state_before = (
                (self.external_dir / "state.json").read_text(encoding="utf-8")
                if (self.external_dir / "state.json").exists()
                else ""
            )
            evidence_before = sorted((self.external_dir / "evidence").glob("*"))
            result = self.run_cli(
                "external-models",
                "live-format-check",
                "--json",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Return exactly this single line, with no quotes and no extra text: API_ONLY_DEEPSEEK_READY",
                "--expected-text",
                "API_ONLY_DEEPSEEK_READY",
            )
            request_count = server.request_count  # type: ignore[attr-defined]
            request_payload = server.last_request_payload  # type: ignore[attr-defined]
            state_after = (
                (self.external_dir / "state.json").read_text(encoding="utf-8")
                if (self.external_dir / "state.json").exists()
                else ""
            )
            evidence_after = sorted((self.external_dir / "evidence").glob("*"))

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["data"]["check_kind"], "api_only_live_route_format")
        self.assertEqual(payload["data"]["verification_scope"], "route_provider_only_no_write")
        self.assertEqual(payload["data"]["request_count"], 1)
        self.assertEqual(payload["data"]["retry_count"], 0)
        self.assertFalse(payload["data"]["parallel_fanout_attempted"])
        self.assertTrue(payload["data"]["expected_text_observed"])
        self.assertEqual(payload["data"]["response_shape"], "choices_message")
        self.assertFalse(payload["data"]["state_written"])
        self.assertFalse(payload["data"]["evidence_written"])
        self.assertFalse(payload["data"]["file_mutation_attempted"])
        self.assertFalse(payload["data"]["commands_started_by_provider"])
        self.assertFalse(payload["data"]["codex_history_sent"])
        self.assertFalse(payload["data"]["repo_context_sent"])
        self.assertFalse(payload["data"]["runtime_context_bridge_used"])
        self.assertFalse(payload["data"]["runtime_context_file_bridge_used"])
        self.assertFalse(payload["data"]["bridge_or_file_bridge_used"])
        self.assertTrue(payload["data"]["direct_provider_auth_proven"])
        self.assertTrue(payload["data"]["direct_provider_response_observed"])
        self.assertTrue(payload["data"]["provider_auth_ok"])
        self.assertTrue(payload["data"]["positive_provider_proof_gate_satisfied"])
        self.assertEqual(request_count, 1)
        self.assertEqual(request_payload["max_tokens"], 96)
        self.assertEqual(state_after, state_before)
        self.assertEqual(evidence_after, evidence_before)

    def test_live_format_check_provider_auth_failure_marks_direct_gate_false(
        self,
    ) -> None:
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
                "live-format-check",
                "--json",
                "--route",
                "wbp-deepseek-v3",
                "--prompt",
                "Return the marker.",
                "--expected-text",
                "AUTH_SHOULD_FAIL",
            )

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "provider_auth_failed")
        self.assertEqual(payload["data"]["route_state"], "provider_auth_failed")
        self.assertFalse(payload["data"]["runtime_context_bridge_used"])
        self.assertFalse(payload["data"]["runtime_context_file_bridge_used"])
        self.assertFalse(payload["data"]["bridge_or_file_bridge_used"])
        self.assertFalse(payload["data"]["direct_provider_auth_proven"])
        self.assertFalse(payload["data"]["direct_provider_response_observed"])
        self.assertFalse(payload["data"]["provider_auth_ok"])
        self.assertFalse(payload["data"]["positive_provider_proof_gate_satisfied"])

    def test_live_format_check_uses_runtime_context_loopback_bridge_before_direct_provider(
        self,
    ) -> None:
        expected_text = "API_ONLY_DEEPSEEK_READY"
        route_id = "wbp-deepseek-v3"
        with mocked_runtime_bridge(response_text=expected_text) as (bridge_base_url, bridge):
            self.run_cli(
                "external-models",
                "routes",
                "add",
                "--json",
                "--stdin",
                stdin_text=json.dumps(
                    sample_route(
                        route_id=route_id,
                        base_url=f"http://127.0.0.1:{_free_port()}/v1",
                    )
                ),
            )
            (self.profile_dir / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "allowed_api_route_ids": [route_id],
                        "agent_id_to_route": {"dip": route_id},
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "bridge_kind": "local_wbp_responses_bridge",
                            "model": route_id,
                            "method": "POST",
                            "url_candidates": [f"{bridge_base_url}/responses"],
                            "request_json_template": {
                                "model": route_id,
                                "input": "Answer exactly one line: <expected_text>",
                                "request_id": "<unique-id>",
                                "stream": False,
                            },
                            "response_text_field": "output_text",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_before = (
                (self.external_dir / "state.json").read_text(encoding="utf-8")
                if (self.external_dir / "state.json").exists()
                else ""
            )
            result = self.run_cli(
                "external-models",
                "live-format-check",
                "--json",
                "--route",
                route_id,
                "--prompt",
                "Return the marker.",
                "--expected-text",
                expected_text,
            )
            state_after = (
                (self.external_dir / "state.json").read_text(encoding="utf-8")
                if (self.external_dir / "state.json").exists()
                else ""
            )

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["data"]["check_kind"], "api_only_live_route_format")
        self.assertTrue(payload["data"]["expected_text_observed"])
        self.assertEqual(payload["data"]["response_shape"], "output_text")
        self.assertTrue(payload["data"]["runtime_context_bridge_used"])
        self.assertFalse(payload["data"]["runtime_context_file_bridge_used"])
        self.assertTrue(payload["data"]["bridge_or_file_bridge_used"])
        self.assertFalse(payload["data"]["direct_provider_auth_proven"])
        self.assertFalse(payload["data"]["direct_provider_response_observed"])
        self.assertFalse(payload["data"]["provider_auth_ok"])
        self.assertFalse(payload["data"]["positive_provider_proof_gate_satisfied"])
        self.assertFalse(payload["data"]["bridge_green_counts_as_provider_proof"])
        self.assertEqual(payload["data"]["bridge_kind"], "local_wbp_responses_bridge")
        self.assertFalse(payload["data"]["fallback_used"])
        self.assertFalse(payload["data"]["state_written"])
        self.assertFalse(payload["data"]["evidence_written"])
        self.assertFalse(payload["data"]["file_mutation_attempted"])
        self.assertEqual(bridge.request_count, 1)  # type: ignore[attr-defined]
        self.assertEqual(state_after, state_before)

    def test_live_format_check_uses_runtime_context_file_bridge_without_socket(
        self,
    ) -> None:
        expected_text = "API_ONLY_FILE_BRIDGE_READY"
        route_id = "wbp-deepseek-v3"
        request_dir = self.root / "file-bridge" / "requests"
        response_dir = self.root / "file-bridge" / "responses"
        request_dir.mkdir(parents=True)
        response_dir.mkdir(parents=True)
        observed_request_ids: list[str] = []

        def responder() -> None:
            deadline = time.monotonic() + 5
            while time.monotonic() <= deadline:
                requests = sorted(request_dir.glob("*.json"))
                if requests:
                    request_payload = json.loads(requests[0].read_text(encoding="utf-8"))
                    observed_request_ids.append(str(request_payload["request_id"]))
                    response_path = response_dir / f"{request_payload['request_id']}.json"
                    response_path.write_text(
                        json.dumps(
                            {
                                "packet_kind": "custom_native_file_bridge_response",
                                "status": "completed",
                                "output_text": expected_text,
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    return
                time.sleep(0.02)

        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(
                sample_route(
                    route_id=route_id,
                    base_url=f"http://127.0.0.1:{_free_port()}/v1",
                )
            ),
        )
        (self.profile_dir / "wbp-agent-runtime-context.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "allowed_api_route_ids": [route_id],
                    "agent_id_to_route": {"dip": route_id},
                    "deepseek_live_format_check_file_bridge": {
                        "enabled": True,
                        "bridge_kind": "server_owned_file_bridge",
                        "model": route_id,
                        "request_dir": str(request_dir),
                        "response_dir": str(response_dir),
                        "request_extension": ".json",
                        "response_extension": ".json",
                        "request_json_template": {
                            "schema_version": 1,
                            "request_id": "<unique-id>",
                            "model": route_id,
                            "input": "Answer exactly one line: <expected_text>",
                            "stream": False,
                        },
                        "response_text_field": "output_text",
                        "poll_interval_seconds": 0.02,
                        "timeout_seconds": 5,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        thread = threading.Thread(target=responder, daemon=True)
        thread.start()
        result = self.run_cli(
            "external-models",
            "live-format-check",
            "--json",
            "--route",
            route_id,
            "--prompt",
            "Return the marker.",
            "--expected-text",
            expected_text,
        )
        thread.join(timeout=2)

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertTrue(payload["data"]["expected_text_observed"])
        self.assertFalse(payload["data"]["runtime_context_bridge_used"])
        self.assertTrue(payload["data"]["runtime_context_file_bridge_used"])
        self.assertTrue(payload["data"]["bridge_or_file_bridge_used"])
        self.assertFalse(payload["data"]["direct_provider_auth_proven"])
        self.assertFalse(payload["data"]["direct_provider_response_observed"])
        self.assertFalse(payload["data"]["provider_auth_ok"])
        self.assertFalse(payload["data"]["positive_provider_proof_gate_satisfied"])
        self.assertFalse(payload["data"]["bridge_green_counts_as_provider_proof"])
        self.assertEqual(payload["data"]["bridge_kind"], "server_owned_file_bridge")
        self.assertEqual(len(observed_request_ids), 1)
        self.assertEqual(
            payload["data"]["file_bridge_response_request_id_sha256"],
            hashlib.sha256(observed_request_ids[0].encode("utf-8")).hexdigest(),
        )
        self.assertNotIn("file_bridge_response_request_id", payload["data"])
        self.assertFalse(payload["data"]["fallback_used"])
        self.assertFalse(payload["data"]["state_written"])
        self.assertFalse(payload["data"]["evidence_written"])
        self.assertFalse(payload["data"]["file_mutation_attempted"])

    def test_live_format_check_does_not_use_runtime_bridge_without_allowlist(
        self,
    ) -> None:
        expected_text = "API_ONLY_BRIDGE_MUST_NOT_BE_USED"
        route_id = "wbp-deepseek-v3"
        with mocked_runtime_bridge(response_text=expected_text) as (bridge_base_url, bridge):
            with mocked_provider(
                smoke_payload={"choices": [{"message": {"content": expected_text}}]},
            ) as (provider_base_url, _provider):
                self.run_cli(
                    "external-models",
                    "routes",
                    "add",
                    "--json",
                    "--stdin",
                    stdin_text=json.dumps(
                        sample_route(
                            route_id=route_id,
                            base_url=provider_base_url,
                        )
                    ),
                )
                (self.profile_dir / "wbp-agent-runtime-context.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "allowed_api_route_ids": [],
                            "agent_id_to_route": {"dip": route_id},
                            "deepseek_live_format_check_bridge": {
                                "enabled": True,
                                "bridge_kind": "local_wbp_responses_bridge",
                                "model": route_id,
                                "method": "POST",
                                "url_candidates": [f"{bridge_base_url}/responses"],
                                "request_json_template": {
                                    "model": route_id,
                                    "input": "Answer exactly one line: <expected_text>",
                                    "request_id": "<unique-id>",
                                    "stream": False,
                                },
                                "response_text_field": "output_text",
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                result = self.run_cli(
                    "external-models",
                    "live-format-check",
                    "--json",
                    "--route",
                    route_id,
                    "--prompt",
                    "Return the marker.",
                    "--expected-text",
                    expected_text,
                )

        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["data"]["expected_text_observed"])
        self.assertEqual(payload["data"]["request_shape"], "openai_chat_messages")
        self.assertFalse(payload["data"]["bridge_or_file_bridge_used"])
        self.assertTrue(payload["data"]["direct_provider_auth_proven"])
        self.assertTrue(payload["data"]["direct_provider_response_observed"])
        self.assertTrue(payload["data"]["positive_provider_proof_gate_satisfied"])
        self.assertEqual(bridge.request_count, 0)  # type: ignore[attr-defined]

    def test_check_transform_profile_records_request_and_response_metadata(self) -> None:
        route = sample_route(base_url="https://placeholder.invalid") | {
            "transform_profile": "openai_chat_input_text",
            "response_profile": "top_level_output_text",
        }
        with mocked_provider(
            smoke_payload={"output_text": "pong"},
        ) as (base_url, server):
            route["base_url"] = base_url
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
            request_payload = server.last_request_payload  # type: ignore[attr-defined]
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["transform_profile"], "openai_chat_input_text")
        self.assertEqual(payload["data"]["response_profile"], "top_level_output_text")
        self.assertEqual(payload["data"]["request_shape"], "input_text")
        self.assertEqual(payload["data"]["response_shape"], "output_text")
        self.assertIsInstance(request_payload, dict)
        self.assertEqual(request_payload["max_output_tokens"], 96)
        self.assertIn("input_text", request_payload)
        self.assertNotIn("messages", request_payload)
        evidence_payload = json.loads(
            Path(payload["data"]["evidence_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence_payload["result"]["transform_profile"], "openai_chat_input_text"
        )
        self.assertEqual(evidence_payload["result"]["response_shape"], "output_text")

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

    def test_check_disabled_route_is_blocked_without_provider_call(self) -> None:
        with mocked_provider() as (base_url, server):
            route = sample_route(base_url=base_url) | {"enabled": False}
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
            request_count = server.request_count  # type: ignore[attr-defined]
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "route_disabled")
        self.assertEqual(payload["data"]["route_state"], "blocked")
        self.assertEqual(request_count, 0)

    def test_validate_disabled_route_is_blocked_without_provider_call(self) -> None:
        with mocked_provider() as (base_url, server):
            route = sample_route(base_url=base_url) | {"enabled": False}
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
                "routes",
                "validate",
                "--json",
                "--route",
                "wbp-deepseek-v3",
            )
            request_count = server.request_count  # type: ignore[attr-defined]
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "route_disabled")
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
        self.assertGreaterEqual(suite.countTestCases(), 11)
