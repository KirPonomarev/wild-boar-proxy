# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
import subprocess
import threading
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from wild_boar_proxy.operator_surface import (
    ExternalRouteResponsesAdapter,
    OwnerSideProcessNetworkObserver,
    OperatorSurfaceConfig,
    OperatorSurfaceSession,
    WbpTraceObserver,
    _run_command_with_observation,
    build_codex_config,
    forbidden_browser_fields,
    run_process_isolation_proof,
    select_server_issued_model,
)


class OperatorSurfaceTests(unittest.TestCase):
    def test_build_codex_config_targets_cliproxy_responses_wire(self) -> None:
        config = build_codex_config(
            endpoint="http://127.0.0.1:8318/v1",
            model_id="gpt-5.3-codex",
        )

        self.assertIn('model = "gpt-5.3-codex"', config)
        self.assertIn('model_provider = "cliproxy"', config)
        self.assertIn('base_url = "http://127.0.0.1:8318/v1"', config)
        self.assertIn('wire_api = "responses"', config)
        self.assertNotIn("api_key", config)
        self.assertNotIn("secret", config)

    def test_forbidden_browser_fields_detect_nested_secret_path_and_ids(self) -> None:
        findings = forbidden_browser_fields(
            {
                "prompt": "ok",
                "model_id": "gpt-5.3-codex",
                "nested": {"api_key": "sk-hidden", "route_id": "route"},
                "items": [{"backend_id": "backend"}, {"path": "/tmp/secret"}],
                "trace_wbp": True,
            }
        )

        self.assertEqual(findings, ["nested.api_key", "nested.route_id", "items[0].backend_id", "items[1].path", "trace_wbp"])

    def test_select_server_issued_model_rejects_free_form_model(self) -> None:
        with self.assertRaises(ValueError):
            select_server_issued_model("gpt-free-form", ["gpt-5.3-codex"])

    def test_trace_observer_forwards_without_recording_body_or_auth(self) -> None:
        captured_headers: dict[str, str] = {}

        class UpstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                captured_headers.update({key: value for key, value in self.headers.items()})
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"output_text": "WBP_TRACE_OK"}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            downstream = f"http://127.0.0.1:{server.server_port}/v1"
            with WbpTraceObserver(downstream_endpoint=downstream) as observer:
                request = urllib.request.Request(
                    f"{observer.listen_endpoint}/responses",
                    data=b'{"input":"SECRET PROMPT"}',
                    headers={
                        "Authorization": "Bearer sk-test-secret-value",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "OpenAI-Beta": "responses=v1",
                        "User-Agent": "Codex-Test/1.0",
                        "Proxy-Authorization": "Bearer sk-proxy-secret",
                        "Cookie": "session=secret",
                        "Connection": "close",
                    },
                    method="POST",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                packet = observer.packet()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertTrue(packet["request_observed"])
        self.assertTrue(packet["response_observed"])
        self.assertTrue(packet["forwarded_to_wbp"])
        self.assertEqual(packet["forwarded_endpoint"], downstream)
        self.assertEqual(packet["path"], "/v1/responses")
        self.assertEqual(packet["upstream_status"], 200)
        self.assertFalse(packet["prompt_body_recorded"])
        self.assertFalse(packet["auth_header_recorded"])
        self.assertFalse(packet["secret_value_recorded"])
        self.assertNotIn("SECRET PROMPT", json.dumps(packet))
        self.assertNotIn("sk-test-secret-value", json.dumps(packet))
        self.assertEqual(captured_headers.get("Authorization"), "Bearer sk-test-secret-value")
        self.assertEqual(captured_headers.get("Accept"), "application/json")
        self.assertEqual(captured_headers.get("Openai-Beta"), "responses=v1")
        self.assertEqual(captured_headers.get("User-Agent"), "Codex-Test/1.0")
        self.assertNotIn("Proxy-Authorization", captured_headers)
        self.assertNotIn("Cookie", captured_headers)

    def test_trace_observer_allows_models_query_string(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"data": []}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            downstream = f"http://127.0.0.1:{server.server_port}/v1"
            with WbpTraceObserver(downstream_endpoint=downstream) as observer:
                request = urllib.request.Request(
                    f"{observer.listen_endpoint}/models?client_version=0.133.0",
                    method="GET",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    self.assertEqual(response.status, 200)
                packet = observer.packet()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertTrue(packet["request_observed"])
        self.assertTrue(packet["response_observed"])
        self.assertEqual(packet["upstream_status"], 200)

    def test_trace_observer_classifies_upstream_4xx_without_green_code(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            status_code = 401

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(self.status_code)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"error": {"message": "auth failed"}}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        for status_code in (401, 403, 429):
            with self.subTest(status_code=status_code):
                UpstreamHandler.status_code = status_code
                server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    downstream = f"http://127.0.0.1:{server.server_port}/v1"
                    with WbpTraceObserver(downstream_endpoint=downstream) as observer:
                        request = urllib.request.Request(
                            f"{observer.listen_endpoint}/responses",
                            data=b'{"input":"SECRET PROMPT"}',
                            headers={
                                "Authorization": "Bearer sk-test-secret-value",
                                "Content-Type": "application/json",
                            },
                            method="POST",
                        )
                        with self.assertRaises(urllib.error.HTTPError) as raised:
                            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                                request,
                                timeout=5,
                            )
                        self.assertEqual(raised.exception.code, status_code)
                        packet = observer.packet()
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()

                self.assertTrue(packet["request_observed"])
                self.assertTrue(packet["response_observed"])
                self.assertTrue(packet["forwarded_to_wbp"])
                self.assertEqual(packet["upstream_status"], status_code)
                self.assertEqual(
                    packet["machine_error_code"],
                    f"TRACE_UPSTREAM_HTTP_{status_code}",
                )
                self.assertFalse(packet["prompt_body_recorded"])
                self.assertFalse(packet["auth_header_recorded"])
                self.assertFalse(packet["secret_value_recorded"])
                self.assertNotIn("SECRET PROMPT", json.dumps(packet))
                self.assertNotIn("sk-test-secret-value", json.dumps(packet))

    def test_run_prompt_uses_stdin_dash_and_redacted_transcript(self) -> None:
        session = OperatorSurfaceSession(
            OperatorSurfaceConfig(
                codex_bin=Path("/bin/echo"),
                runtime_config=Path("/tmp/nonexistent-runtime-config.yaml"),
                timeout_seconds=5,
            )
        )
        session.probe_models = lambda: {  # type: ignore[method-assign]
            "ok": True,
            "model_ids": ["gpt-5.3-codex"],
            "server_issued": True,
        }
        session.run_wbp = lambda args: {"json": {"data": {"routes": []}}}  # type: ignore[method-assign]
        session.status_payload = lambda: {  # type: ignore[method-assign]
            "status": {"status": "ok", "machine_error_code": "OK"},
            "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
        }
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        def fake_observed_run(command: list[str], **kwargs: object) -> dict[str, object]:
            self.assertEqual(command[-1], "-")
            self.assertEqual(kwargs.get("prompt"), "Reply with exactly MAIN_WEB_OK.")
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            self.assertEqual(env.get("OPENAI_API_KEY"), "sk-test-secret-value")  # type: ignore[union-attr]
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("MAIN_WEB_OK\n", encoding="utf-8")
            return {
                "exit_code": 0,
                "stderr": "",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "process_tree_observed": True,
                    "sample_count": 2,
                    "observed_process_count_max": 1,
                    "allowed_local_endpoints": ["127.0.0.1:8318"],
                    "allowed_local_endpoint_observed": True,
                    "peer_endpoints": [{"endpoint": "127.0.0.1:8318", "host_class": "local"}],
                    "non_local_peer_endpoints_present": False,
                    "classification": "wbp_forward_only_proven",
                    "direct_non_wbp_model_egress_absent_proven": True,
                    "raw_pid_exposed": False,
                    "pid_not_exposed_to_browser": True,
                    "secret_value_recorded": False,
                },
            }

        with mock.patch(
            "wild_boar_proxy.operator_surface._run_command_with_observation",
            side_effect=fake_observed_run,
        ):
            result = session.run_prompt(
                {
                    "prompt": "Reply with exactly MAIN_WEB_OK.",
                    "model_id": "gpt-5.3-codex",
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["final_message"], "MAIN_WEB_OK")
        self.assertEqual(result["configured_base_url"], "http://127.0.0.1:8318/v1")
        self.assertEqual(result["configured_provider"], "cliproxy")
        self.assertEqual(result["configured_wire_api"], "responses")
        self.assertTrue(result["wbp_endpoint_configured"])
        self.assertTrue(result["config_endpoint_matches"])
        self.assertTrue(result["config_provider_matches"])
        self.assertTrue(result["config_wire_api_matches"])
        self.assertTrue(result["command_uses_stdin_dash"])
        self.assertTrue(result["command_json_mode"])
        self.assertTrue(result["command_output_file_is_temp"])
        self.assertTrue(result["env_codex_home_is_temp"])
        self.assertTrue(result["env_home_is_temp"])
        self.assertTrue(result["workdir_is_temp"])
        self.assertTrue(result["command_workdir_is_temp"])
        self.assertFalse(result["current_codex_home_used"])
        self.assertTrue(result["stdin_prompt_used"])
        self.assertTrue(result["temp_root_removed"])
        self.assertTrue(result["direct_non_wbp_model_egress_absent_proven"])
        self.assertNotIn("sk-test-secret-value", json.dumps(result))

    def test_run_prompt_route_backed_external_model_uses_route_upstream_model_and_secret(self) -> None:
        session = OperatorSurfaceSession(
            OperatorSurfaceConfig(
                codex_bin=Path("/bin/echo"),
                runtime_config=Path("/tmp/nonexistent-runtime-config.yaml"),
                timeout_seconds=5,
            )
        )
        session.probe_models = lambda: {  # type: ignore[method-assign]
            "ok": True,
            "model_ids": ["wbp-web-primary-openrouter"],
            "server_issued": True,
        }
        session.status_payload = lambda: {  # type: ignore[method-assign]
            "status": {"status": "ok", "machine_error_code": "OK"},
            "models": {"model_ids": ["wbp-web-primary-openrouter"], "server_issued": True},
        }
        session.run_wbp = lambda args: {  # type: ignore[method-assign]
            "json": {
                "data": {
                    "routes": [
                        {
                            "route_id": "wbp-web-primary-openrouter",
                            "enabled": True,
                            "provider": "openrouter",
                            "base_url": "https://openrouter.ai/api/v1",
                            "endpoint_path": "/chat/completions",
                            "upstream_model": "openai/gpt-5",
                            "compatibility": "openai_chat_completions",
                            "auth": {"secret_ref": "OPENROUTER_API_KEY"},
                        }
                    ]
                }
            }
        }

        def fake_observed_run(command: list[str], **kwargs: object) -> dict[str, object]:
            self.assertEqual(command[-1], "-")
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            self.assertEqual(env.get("OPENAI_API_KEY"), "sk-local-runtime")  # type: ignore[union-attr]
            last_message = Path(command[command.index("-o") + 1])
            config = (Path(str(env["CODEX_HOME"])) / "config.toml").read_text(encoding="utf-8")  # type: ignore[index]
            self.assertIn('model = "wbp-web-primary-openrouter"', config)
            self.assertIn('model_provider = "external_route"', config)
            self.assertIn('base_url = "http://127.0.0.1:', config)
            self.assertIn('/v1"', config)
            self.assertIn('wire_api = "responses"', config)
            last_message.write_text("WBP_CUSTOM_EXTERNAL_API_OK\n", encoding="utf-8")
            return {
                "exit_code": 0,
                "stderr": "",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "process_tree_observed": True,
                    "sample_count": 2,
                    "observed_process_count_max": 1,
                    "allowed_local_endpoints": ["127.0.0.1:8318"],
                    "allowed_local_endpoint_observed": True,
                    "peer_endpoints": [{"endpoint": "127.0.0.1:8318", "host_class": "local"}],
                    "non_local_peer_endpoints_present": False,
                    "classification": "wbp_forward_only_proven",
                    "direct_non_wbp_model_egress_absent_proven": True,
                    "raw_pid_exposed": False,
                    "pid_not_exposed_to_browser": True,
                    "secret_value_recorded": False,
                },
            }

        with (
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-route-secret",
            ),
            mock.patch.object(session, "local_api_key", return_value="sk-local-runtime"),
            mock.patch(
                "wild_boar_proxy.operator_surface._run_command_with_observation",
                side_effect=fake_observed_run,
            ),
        ):
            result = session.run_prompt(
                {
                    "prompt": "Reply with exactly WBP_CUSTOM_EXTERNAL_API_OK.",
                    "model_id": "wbp-web-primary-openrouter",
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["runtime_model"], "wbp-web-primary-openrouter")
        self.assertEqual(result["configured_provider"], "external_route")
        self.assertEqual(result["configured_wire_api"], "responses")
        self.assertTrue(result["route_adapter_used"])
        self.assertTrue(str(result["downstream_wbp_endpoint"]).startswith("http://127.0.0.1:"))
        self.assertTrue(str(result["downstream_wbp_endpoint"]).endswith("/v1"))
        self.assertEqual(result["route_provider_endpoint"], "https://openrouter.ai/api/v1")
        self.assertNotIn("sk-route-secret", json.dumps(result))
        self.assertNotIn("sk-local-runtime", json.dumps(result))

    def test_external_route_responses_adapter_translates_responses_to_chat_completions(self) -> None:
        route = {
            "route_id": "wbp-web-primary-openrouter",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "endpoint_path": "/chat/completions",
            "upstream_model": "openai/gpt-5",
            "compatibility": "openai_chat_completions",
            "auth": {"secret_ref": "OPENROUTER_API_KEY"},
        }
        captured: dict[str, object] = {}

        def fake_request_json(**kwargs: object):
            captured.update(kwargs)

            class FakeResponse:
                status_code = 200
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": "WBP_CUSTOM_EXTERNAL_API_OK",
                            }
                        }
                    ],
                    "usage": {"total_tokens": 12},
                }

            return FakeResponse()

        with (
            ExternalRouteResponsesAdapter(
                route=route,
                expected_api_key="sk-local-runtime",
                route_secret="sk-route-secret",
            ) as adapter,
            mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=fake_request_json),
        ):
            request = urllib.request.Request(
                f"{adapter.listen_endpoint}/responses",
                data=json.dumps(
                    {
                        "input": [
                            {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "Reply exactly OK"}],
                            }
                        ],
                        "max_output_tokens": 32,
                    }
                ).encode("utf-8"),
                headers={
                    "Authorization": "Bearer sk-local-runtime",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["model"], "wbp-web-primary-openrouter")
        self.assertEqual(payload["output_text"], "WBP_CUSTOM_EXTERNAL_API_OK")
        self.assertEqual(captured["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"], {"Authorization": "Bearer sk-route-secret", "Accept": "application/json"})
        self.assertEqual(
            captured["payload"],
            {
                "model": "openai/gpt-5",
                "messages": [{"role": "user", "content": "Reply exactly OK"}],
                "stream": False,
                "max_tokens": 32,
            },
        )

    def test_external_route_responses_adapter_streams_response_completed_for_streaming_clients(self) -> None:
        route = {
            "route_id": "wbp-web-primary-openrouter",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "endpoint_path": "/chat/completions",
            "upstream_model": "openai/gpt-5",
            "compatibility": "openai_chat_completions",
            "auth": {"secret_ref": "OPENROUTER_API_KEY"},
        }

        def fake_request_json(**kwargs: object):
            class FakeResponse:
                status_code = 200
                payload = {
                    "choices": [{"message": {"content": "WBP_CUSTOM_EXTERNAL_API_OK"}}],
                    "usage": {"total_tokens": 12},
                }

            return FakeResponse()

        with (
            ExternalRouteResponsesAdapter(
                route=route,
                expected_api_key="sk-local-runtime",
                route_secret="sk-route-secret",
            ) as adapter,
            mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=fake_request_json),
        ):
            request = urllib.request.Request(
                f"{adapter.listen_endpoint}/responses",
                data=json.dumps(
                    {
                        "stream": True,
                        "input": [
                            {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "Reply exactly OK"}],
                            }
                        ],
                    }
                ).encode("utf-8"),
                headers={
                    "Authorization": "Bearer sk-local-runtime",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                method="POST",
            )
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
                body = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")

        self.assertEqual(content_type, "text/event-stream")
        self.assertIn("event: response.output_text.delta", body)
        self.assertIn("event: response.completed", body)
        self.assertIn("WBP_CUSTOM_EXTERNAL_API_OK", body)

    def test_run_prompt_rejects_browser_supplied_route_id(self) -> None:
        session = OperatorSurfaceSession()
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]

        result = session.run_prompt(
            {
                "prompt": "Reply OK.",
                "model_id": "gpt-5.3-codex",
                "route_id": "browser-forged",
            }
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(result["forbidden_fields"], ["route_id"])

    def test_probe_models_merges_enabled_server_owned_external_route_ids(self) -> None:
        class FakeResponse:
            status = 200

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps({"data": [{"id": "gpt-5.3-codex"}]}).encode("utf-8")

        class FakeOpener:
            def open(self, request, timeout=20):  # noqa: ANN001
                return FakeResponse()

        session = OperatorSurfaceSession()
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]
        session.run_wbp = lambda args: {  # type: ignore[method-assign]
            "json": {
                "data": {
                    "routes": [
                        {
                            "route_id": "wbp-web-primary-openrouter",
                            "enabled": True,
                            "auth": {"secret_ref": "OPENROUTER_API_KEY"},
                        }
                    ]
                }
            }
        }
        with mock.patch("wild_boar_proxy.operator_surface.urllib.request.build_opener", return_value=FakeOpener()):
            result = session.probe_models()

        self.assertTrue(result["ok"])
        self.assertIn("gpt-5.3-codex", result["model_ids"])
        self.assertIn("wbp-web-primary-openrouter", result["model_ids"])

    def test_run_prompt_trace_mode_marks_path_proven_only_after_observer_request(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"output_text": "WBP_TRACE_OK"}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = OperatorSurfaceSession(
            OperatorSurfaceConfig(
                endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                codex_bin=Path("/bin/echo"),
                runtime_config=Path("/tmp/nonexistent-runtime-config.yaml"),
                timeout_seconds=5,
            )
        )
        session.probe_models = lambda: {  # type: ignore[method-assign]
            "ok": True,
            "model_ids": ["gpt-5.3-codex"],
            "server_issued": True,
        }
        session.run_wbp = lambda args: {"json": {"data": {"routes": []}}}  # type: ignore[method-assign]
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        def fake_observed_run(command: list[str], **kwargs: object) -> dict[str, object]:
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            config_path = Path(str(env["CODEX_HOME"])) / "config.toml"  # type: ignore[index]
            config = config_path.read_text(encoding="utf-8")
            match = re.search(r'base_url = "([^"]+)"', config)
            self.assertIsNotNone(match)
            request = urllib.request.Request(
                f"{match.group(1)}/responses",  # type: ignore[union-attr]
                data=b'{"input":"Reply with exactly WBP_TRACE_OK."}',
                headers={
                    "Authorization": "Bearer sk-test-secret-value",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("WBP_TRACE_OK\n", encoding="utf-8")
            return {
                "exit_code": 0,
                "stderr": "",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "process_tree_observed": True,
                    "sample_count": 3,
                    "observed_process_count_max": 1,
                    "allowed_local_endpoints": [],
                    "allowed_local_endpoint_observed": False,
                    "peer_endpoints": [{"endpoint": "127.0.0.1:9999", "host_class": "local"}],
                    "non_local_peer_endpoints_present": False,
                    "classification": "wbp_forward_only_proven",
                    "direct_non_wbp_model_egress_absent_proven": True,
                    "raw_pid_exposed": False,
                    "pid_not_exposed_to_browser": True,
                    "secret_value_recorded": False,
                },
            }

        try:
            with mock.patch(
                "wild_boar_proxy.operator_surface._run_command_with_observation",
                side_effect=fake_observed_run,
            ):
                result = session.run_prompt(
                    {
                        "prompt": "Reply with exactly WBP_TRACE_OK.",
                        "model_id": "gpt-5.3-codex",
                    },
                    trace_wbp=True,
                )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["trace_observer_enabled"])
        self.assertTrue(result["independent_wbp_trace_observed"])
        self.assertEqual(result["downstream_wbp_endpoint"], f"http://127.0.0.1:{server.server_port}/v1")
        self.assertNotEqual(result["configured_base_url"], result["downstream_wbp_endpoint"])
        trace = result["trace_observer_packet"]
        self.assertTrue(trace["request_observed"])
        self.assertTrue(trace["response_observed"])
        self.assertTrue(trace["forwarded_to_wbp"])
        self.assertEqual(trace["path"], "/v1/responses")
        self.assertFalse(trace["prompt_body_recorded"])
        self.assertFalse(trace["auth_header_recorded"])
        self.assertNotIn("Reply with exactly WBP_TRACE_OK.", json.dumps(trace))
        self.assertNotIn("sk-test-secret-value", json.dumps(result))

    def test_run_prompt_trace_mode_bubbles_upstream_401_code(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"error": {"message": "auth failed"}}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = OperatorSurfaceSession(
            OperatorSurfaceConfig(
                endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                codex_bin=Path("/bin/echo"),
                runtime_config=Path("/tmp/nonexistent-runtime-config.yaml"),
                timeout_seconds=5,
            )
        )
        session.probe_models = lambda: {  # type: ignore[method-assign]
            "ok": True,
            "model_ids": ["gpt-5.3-codex"],
            "server_issued": True,
        }
        session.run_wbp = lambda args: {"json": {"data": {"routes": []}}}  # type: ignore[method-assign]
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        def fake_observed_run(command: list[str], **kwargs: object) -> dict[str, object]:
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            config_path = Path(str(env["CODEX_HOME"])) / "config.toml"  # type: ignore[index]
            config = config_path.read_text(encoding="utf-8")
            match = re.search(r'base_url = "([^"]+)"', config)
            self.assertIsNotNone(match)
            request = urllib.request.Request(
                f"{match.group(1)}/responses",  # type: ignore[union-attr]
                data=b'{"input":"Reply with exactly WBP_TRACE_OK."}',
                headers={
                    "Authorization": "Bearer sk-test-secret-value",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5)
            self.assertEqual(raised.exception.code, 401)
            return {
                "exit_code": 1,
                "stderr": "upstream failed",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "process_tree_observed": True,
                    "sample_count": 1,
                    "observed_process_count_max": 1,
                    "allowed_local_endpoints": [],
                    "allowed_local_endpoint_observed": False,
                    "peer_endpoints": [{"endpoint": "127.0.0.1:9999", "host_class": "local"}],
                    "non_local_peer_endpoints_present": False,
                    "classification": "wbp_forward_only_proven",
                    "direct_non_wbp_model_egress_absent_proven": True,
                    "raw_pid_exposed": False,
                    "pid_not_exposed_to_browser": True,
                    "secret_value_recorded": False,
                },
            }

        try:
            with mock.patch(
                "wild_boar_proxy.operator_surface._run_command_with_observation",
                side_effect=fake_observed_run,
            ):
                result = session.run_prompt(
                    {
                        "prompt": "Reply with exactly WBP_TRACE_OK.",
                        "model_id": "gpt-5.3-codex",
                    },
                    trace_wbp=True,
                )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["machine_error_code"], "TRACE_UPSTREAM_HTTP_401")
        trace = result["trace_observer_packet"]
        self.assertTrue(trace["request_observed"])
        self.assertTrue(trace["response_observed"])
        self.assertEqual(trace["path"], "/v1/responses")
        self.assertEqual(trace["upstream_status"], 401)
        self.assertEqual(trace["machine_error_code"], "TRACE_UPSTREAM_HTTP_401")
        self.assertFalse(result["independent_wbp_trace_observed"])
        self.assertNotIn("Reply with exactly WBP_TRACE_OK.", json.dumps(result))
        self.assertNotIn("sk-test-secret-value", json.dumps(result))

    def test_process_network_observer_classifies_missing_samples_as_insufficient(self) -> None:
        observer = OwnerSideProcessNetworkObserver(
            root_pid=123,
            allowed_local_endpoints={"127.0.0.1:8318"},
        )

        packet = observer.packet(warning_classes=[])

        self.assertEqual(packet["classification"], "insufficient_observation")
        self.assertFalse(packet["direct_non_wbp_model_egress_absent_proven"])

    def test_process_network_observer_classifies_local_only_as_wbp_forward_only(self) -> None:
        observer = OwnerSideProcessNetworkObserver(
            root_pid=123,
            allowed_local_endpoints={"127.0.0.1:8318"},
        )
        observer._samples = [  # type: ignore[attr-defined]
            {
                "process_tree_seen": True,
                "process_count": 1,
                "process_tree": [{"pid_digest": "abc", "is_root": True, "command_basename": "codex"}],
                "peer_endpoints": [{"endpoint": "127.0.0.1:8318", "host_class": "local", "command_basename": "codex"}],
            }
        ]

        packet = observer.packet(warning_classes=[])

        self.assertEqual(packet["classification"], "wbp_forward_only_proven")
        self.assertTrue(packet["direct_non_wbp_model_egress_absent_proven"])

    def test_process_network_observer_classifies_remote_plugin_sync_as_ancillary(self) -> None:
        observer = OwnerSideProcessNetworkObserver(
            root_pid=123,
            allowed_local_endpoints={"127.0.0.1:8318"},
        )
        observer._samples = [  # type: ignore[attr-defined]
            {
                "process_tree_seen": True,
                "process_count": 1,
                "process_tree": [{"pid_digest": "abc", "is_root": False, "command_basename": "git"}],
                "peer_endpoints": [
                    {"endpoint": "127.0.0.1:8318", "host_class": "local", "command_basename": "codex"},
                    {"endpoint": "34.120.0.1:443", "host_class": "non_local", "command_basename": "git"},
                ],
            }
        ]

        packet = observer.packet(warning_classes=["remote_plugin_sync_401"])

        self.assertEqual(packet["classification"], "ancillary_non_model_egress_observed")
        self.assertTrue(packet["direct_non_wbp_model_egress_absent_proven"])

    def test_process_isolation_proof_reports_protected_surfaces_unchanged(self) -> None:
        snapshot = {
            "codex_config": {
                "path_label": "~/.codex/config.toml",
                "exists": True,
                "is_dir": False,
                "size": 12,
                "mtime_ns": 100,
                "sha256": "a" * 64,
            },
            "default_cache_codex": {
                "path_label": "~/Library/Caches/com.openai.codex",
                "exists": True,
                "is_dir": True,
                "size": 64,
                "mtime_ns": 200,
            },
        }

        with (
            mock.patch(
                "wild_boar_proxy.operator_surface.protected_snapshot",
                side_effect=[snapshot, json.loads(json.dumps(snapshot))],
            ),
            mock.patch.object(
                OperatorSurfaceSession,
                "run_prompt",
                return_value={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "temp_root_removed": True,
                    "secret_value_recorded": False,
                },
            ),
        ):
            proof = run_process_isolation_proof("Reply OK.")

        self.assertTrue(proof["protected_surfaces_unchanged"])
        self.assertTrue(proof["tmp_root_removed"])
        self.assertEqual(proof["comparisons"]["codex_config"]["exists_unchanged"], True)
        self.assertEqual(proof["comparisons"]["codex_config"]["mtime_ns_unchanged"], True)
        self.assertEqual(proof["comparisons"]["codex_config"]["sha256_unchanged"], True)


if __name__ == "__main__":
    unittest.main()
