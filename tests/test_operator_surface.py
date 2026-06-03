# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from wild_boar_proxy.operator_surface import (
    ExternalRouteResponsesAdapter,
    HybridOpenAICompatAdapter,
    OPERATOR_OBSERVATION_CWD,
    OPERATOR_OBSERVATION_OUTPUT_CAP_BYTES,
    OPERATOR_OBSERVATION_RUNTIME_PATH,
    OPERATOR_OBSERVATION_TIMEOUT_SECONDS,
    OPERATOR_WBP_OUTPUT_CAP_BYTES,
    OPERATOR_WBP_TIMEOUT_SECONDS,
    OwnerSideProcessNetworkObserver,
    OperatorSurfaceConfig,
    OperatorSurfaceSession,
    WbpTraceObserver,
    _network_sample_for_pid,
    _process_tree_snapshot,
    _prompt_trace_hash_and_smoke_match,
    _run_operator_observation_command,
    _run_command_with_observation,
    build_bridge_failure_recovery_truth_packet,
    build_codex_config,
    build_stable_bridge_preflight_packet,
    forbidden_browser_fields,
    run_process_isolation_proof,
    select_server_issued_model,
)
from wild_boar_proxy.process_runner import BoundedProcessResult


def bounded_completed(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> BoundedProcessResult:
    return BoundedProcessResult(
        status="ok" if returncode == 0 else "error",
        machine_error_code="OK" if returncode == 0 else "PROCESS_FAILED",
        exit_code=returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=False,
        duration_seconds=0.01,
    )


def bounded_timeout(*, stderr: str = "timed out") -> BoundedProcessResult:
    return BoundedProcessResult(
        status="error",
        machine_error_code="PROCESS_TIMEOUT",
        exit_code=None,
        stdout="",
        stderr=stderr,
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=True,
        duration_seconds=OPERATOR_OBSERVATION_TIMEOUT_SECONDS,
    )


class OperatorSurfaceTests(unittest.TestCase):
    def test_operator_observation_command_uses_bounded_runner_with_deterministic_env(self) -> None:
        observed_calls: list[dict[str, object]] = []

        def fake_run_bounded_process(
            command: list[str],
            *,
            env: dict[str, str],
            cwd: Path,
            timeout_seconds: float,
            output_cap_bytes: int,
        ) -> BoundedProcessResult:
            observed_calls.append(
                {
                    "command": command,
                    "env": dict(env),
                    "cwd": cwd,
                    "timeout_seconds": timeout_seconds,
                    "output_cap_bytes": output_cap_bytes,
                }
            )
            return bounded_completed(stdout="ok\n")

        with (
            mock.patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": "http://example.invalid:1",
                    "HTTPS_PROXY": "http://example.invalid:2",
                    "ALL_PROXY": "http://example.invalid:3",
                    "http_proxy": "http://example.invalid:4",
                    "https_proxy": "http://example.invalid:5",
                    "all_proxy": "http://example.invalid:6",
                    "WBP_CURRENT_PROXY_URL": "http://example.invalid:7",
                    "CODEX_HOME": "/tmp/ambient-codex-home",
                    "OPENAI_API_KEY": "ambient-secret",
                    "PATH": "/definitely/missing",
                    "HOME": "/tmp/ambient-home",
                },
                clear=True,
            ),
            mock.patch(
                "wild_boar_proxy.operator_surface.run_bounded_process",
                side_effect=fake_run_bounded_process,
            ),
        ):
            result = _run_operator_observation_command(["ps", "-Ao", "pid=,ppid=,command="])

        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(len(observed_calls), 1)
        call = observed_calls[0]
        self.assertEqual(call["command"], ["ps", "-Ao", "pid=,ppid=,command="])
        self.assertEqual(call["cwd"], OPERATOR_OBSERVATION_CWD)
        self.assertEqual(call["timeout_seconds"], OPERATOR_OBSERVATION_TIMEOUT_SECONDS)
        self.assertEqual(call["output_cap_bytes"], OPERATOR_OBSERVATION_OUTPUT_CAP_BYTES)
        env = call["env"]
        self.assertEqual(env["PATH"], OPERATOR_OBSERVATION_RUNTIME_PATH)
        self.assertEqual(env["NO_PROXY"], "127.0.0.1,localhost,::1")
        self.assertEqual(env["no_proxy"], "127.0.0.1,localhost,::1")
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "WBP_CURRENT_PROXY_URL",
            "CODEX_HOME",
            "OPENAI_API_KEY",
            "HOME",
        ):
            self.assertNotIn(key, env)

    def test_run_wbp_uses_bounded_runner_with_expected_command_cwd_env_timeout_cap(
        self,
    ) -> None:
        observed_calls: list[dict[str, object]] = []

        def fake_run_bounded_process(
            command: list[str],
            *,
            env: dict[str, str],
            cwd: str,
            timeout_seconds: float,
            output_cap_bytes: int,
        ) -> BoundedProcessResult:
            observed_calls.append(
                {
                    "command": command,
                    "env": dict(env),
                    "cwd": cwd,
                    "timeout_seconds": timeout_seconds,
                    "output_cap_bytes": output_cap_bytes,
                }
            )
            return bounded_completed(stdout='{"status":"ok"}\n', stderr="diagnostic")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            session = OperatorSurfaceSession(
                OperatorSurfaceConfig(repo_root=repo_root),
            )
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "HTTP_PROXY": "http://example.invalid:1",
                        "HTTPS_PROXY": "http://example.invalid:2",
                        "ALL_PROXY": "http://example.invalid:3",
                        "http_proxy": "http://example.invalid:4",
                        "https_proxy": "http://example.invalid:5",
                        "all_proxy": "http://example.invalid:6",
                        "PATH": "/usr/bin:/bin",
                    },
                    clear=True,
                ),
                mock.patch(
                    "wild_boar_proxy.operator_surface.run_bounded_process",
                    side_effect=fake_run_bounded_process,
                ),
            ):
                result = session.run_wbp(["status", "--json"])

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["json"], {"status": "ok"})
        self.assertEqual(len(observed_calls), 1)
        call = observed_calls[0]
        self.assertEqual(
            call["command"],
            ["python3", "-m", "wild_boar_proxy", "status", "--json"],
        )
        self.assertEqual(call["cwd"], str(repo_root))
        self.assertEqual(call["timeout_seconds"], OPERATOR_WBP_TIMEOUT_SECONDS)
        self.assertEqual(call["output_cap_bytes"], OPERATOR_WBP_OUTPUT_CAP_BYTES)
        env = call["env"]
        self.assertEqual(env["NO_PROXY"], "127.0.0.1,localhost")
        self.assertEqual(env["no_proxy"], "127.0.0.1,localhost")
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            self.assertNotIn(key, env)

    def test_run_wbp_reports_redacted_lengths_without_raw_output(self) -> None:
        session = OperatorSurfaceSession()
        with mock.patch(
            "wild_boar_proxy.operator_surface.run_bounded_process",
            return_value=bounded_completed(
                stdout='{"answer":true}',
                stderr="secret-ish stderr",
            ),
        ):
            result = session.run_wbp(["status", "--json"])

        self.assertEqual(result["json"], {"answer": True})
        self.assertEqual(result["stdout_redacted_len"], len('{"answer":true}'))
        self.assertEqual(result["stderr_redacted_len"], len("secret-ish stderr"))
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)

    def test_run_wbp_returns_none_json_for_empty_or_malformed_stdout(self) -> None:
        session = OperatorSurfaceSession()
        for stdout in ("", "not-json"):
            with self.subTest(stdout=stdout):
                with mock.patch(
                    "wild_boar_proxy.operator_surface.run_bounded_process",
                    return_value=bounded_completed(stdout=stdout),
                ):
                    result = session.run_wbp(["status", "--json"])

                self.assertEqual(result["exit_code"], 0)
                self.assertIsNone(result["json"])

    def test_run_wbp_preserves_nonzero_exit_code_without_false_green(self) -> None:
        session = OperatorSurfaceSession()
        with mock.patch(
            "wild_boar_proxy.operator_surface.run_bounded_process",
            return_value=bounded_completed(
                returncode=42,
                stdout='{"status":"error","machine_error_code":"BROKEN"}',
            ),
        ):
            result = session.run_wbp(["healthcheck", "--json"])

        self.assertEqual(result["exit_code"], 42)
        self.assertEqual(
            result["json"],
            {"status": "error", "machine_error_code": "BROKEN"},
        )

    def test_run_wbp_timeout_without_exit_code_uses_conservative_nonzero(self) -> None:
        session = OperatorSurfaceSession()
        with mock.patch(
            "wild_boar_proxy.operator_surface.run_bounded_process",
            return_value=bounded_timeout(),
        ):
            result = session.run_wbp(["healthcheck", "--json"])

        self.assertEqual(result["exit_code"], 127)
        self.assertIsNone(result["json"])

    def test_process_tree_snapshot_uses_bounded_ps_and_fails_closed(self) -> None:
        ps_stdout = "\n".join(
            [
                " 100 1 /Applications/Codex.app/Contents/MacOS/Codex",
                " 101 100 /usr/bin/git fetch",
                " 102 101 /bin/sh -c echo ok",
            ]
        )
        with mock.patch(
            "wild_boar_proxy.operator_surface._run_operator_observation_command",
            return_value=bounded_completed(stdout=ps_stdout),
        ) as run:
            packet = _process_tree_snapshot(100)

        run.assert_called_once_with(["ps", "-Ao", "pid=,ppid=,command="])
        self.assertEqual(packet["raw_pids"], [100, 101, 102])
        self.assertEqual(len(packet["public_entries"]), 3)
        self.assertTrue(packet["public_entries"][0]["is_root"])
        self.assertEqual(packet["public_entries"][1]["command_basename"], "git")
        self.assertEqual(packet["public_entries"][2]["command_basename"], "sh")

        for result in (
            bounded_completed(returncode=1, stderr="ps failed"),
            bounded_timeout(stderr="ps timed out"),
        ):
            with mock.patch(
                "wild_boar_proxy.operator_surface._run_operator_observation_command",
                return_value=result,
            ):
                self.assertEqual(_process_tree_snapshot(100), {"public_entries": [], "raw_pids": []})

    def test_network_sample_for_pid_uses_bounded_lsof_and_fails_closed(self) -> None:
        lsof_stdout = "\n".join(
            [
                "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME",
                "Codex 100 user 10u IPv4 0x1 0t0 TCP 127.0.0.1:55000->127.0.0.1:8318 (ESTABLISHED)",
                "Codex 100 user 11u IPv4 0x2 0t0 TCP 127.0.0.1:55001->api.example.invalid:443 (ESTABLISHED)",
            ]
        )
        with mock.patch(
            "wild_boar_proxy.operator_surface._run_operator_observation_command",
            return_value=bounded_completed(stdout=lsof_stdout),
        ) as run:
            packet = _network_sample_for_pid(100)

        run.assert_called_once_with(["lsof", "-n", "-P", "-a", "-i", "-p", "100"])
        self.assertEqual(packet["peer_endpoint_count"], 2)
        self.assertFalse(packet["local_only"])
        self.assertEqual(packet["peer_endpoints"][0]["host_class"], "local")
        self.assertEqual(packet["peer_endpoints"][1]["host_class"], "non_local")

        for result in (
            bounded_completed(returncode=1, stderr="lsof failed"),
            bounded_timeout(stderr="lsof timed out"),
        ):
            with mock.patch(
                "wild_boar_proxy.operator_surface._run_operator_observation_command",
                return_value=result,
            ):
                self.assertEqual(
                    _network_sample_for_pid(100),
                    {"peer_endpoints": [], "peer_endpoint_count": 0, "local_only": True},
                )

    def test_hybrid_openai_compat_adapter_honors_explicit_listen_port(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])

        adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:8318/v1",
            expected_api_key="sk-local-runtime",
            routes=[],
            listen_port=port,
        )
        try:
            adapter.__enter__()
            self.assertEqual(adapter.listen_endpoint, f"http://127.0.0.1:{port}/v1")
        finally:
            adapter.__exit__(None, None, None)

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

    def test_external_route_injects_runtime_truth_before_user_prompt(self) -> None:
        captured_payload: dict[str, object] = {}
        route = {
            "route_id": "wbp-deepseek-v4-pro-max",
            "provider": "deepseek",
            "enabled": True,
            "base_url": "https://api.deepseek.com/v1",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-v4-pro",
            "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
            "transform_profile": "openai_chat_developer_to_system",
            "thinking": {"type": "enabled", "reasoning_effort": "max"},
        }

        def fake_request_json(**kwargs: object):  # noqa: ANN001
            captured_payload.update(kwargs["payload"])  # type: ignore[index]

            class FakeResponse:
                status_code = 200
                payload = {"choices": [{"message": {"content": "Я DeepSeek."}}]}

            return FakeResponse()

        adapter = ExternalRouteResponsesAdapter(
            route=route,
            expected_api_key="sk-local-test",
            route_secret="sk-route-secret",
        )
        with mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=fake_request_json):
            status, _, body = adapter.handle(
                method="POST",
                path="/v1/responses",
                headers={
                    "Authorization": "Bearer sk-local-test",
                    "Content-Type": "application/json",
                },
                body=json.dumps(
                    {
                        "model": "wbp-deepseek-v4-pro-max",
                        "instructions": "You are Codex CLI from OpenAI.",
                        "input": "какая ты модель?",
                    }
                ).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        response_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(response_payload["requested_model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(response_payload["upstream_model"], "deepseek-v4-pro")
        self.assertEqual(response_payload["thinking"], {"type": "enabled", "reasoning_effort": "max"})
        self.assertTrue(response_payload["api_parameter_sent"])
        self.assertEqual(response_payload["max_tokens_sent"], 2048)
        self.assertFalse(response_payload["intelligence_measured"])
        self.assertEqual(
            captured_payload["thinking"],
            {"type": "enabled", "reasoning_effort": "max"},
        )
        self.assertEqual(captured_payload["max_tokens"], 2048)
        messages = captured_payload["messages"]
        self.assertIsInstance(messages, list)
        runtime_truth = [message for message in messages if "runtime routing truth" in str(message.get("content"))]
        self.assertEqual(len(runtime_truth), 1)
        self.assertEqual(runtime_truth[0]["role"], "system")
        self.assertIn("provider 'deepseek'", str(runtime_truth[0]["content"]))
        self.assertIn("upstream model 'deepseek-v4-pro'", str(runtime_truth[0]["content"]))
        self.assertIn("thinking enabled with reasoning_effort 'max'", str(runtime_truth[0]["content"]))
        self.assertIn("Do not say 'I am Codex CLI from OpenAI'", str(runtime_truth[0]["content"]))
        self.assertLess(messages.index(runtime_truth[0]), len(messages) - 1)

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
        self.assertEqual(packet["request_count"], 1)
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

    def test_trace_observer_records_bounded_error_metadata_without_raw_body(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                body = json.dumps(
                    {
                        "error": {
                            "message": "bad role for developer role",
                            "type": "invalid_request_error",
                            "code": "invalid_request_error",
                        }
                    }
                ).encode("utf-8")
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
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                        request,
                        timeout=5,
                    )
                packet = observer.packet()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(packet["upstream_status"], 400)
        self.assertEqual(packet["response_error_type"], "invalid_request_error")
        self.assertEqual(packet["response_error_code"], "invalid_request_error")
        self.assertIn("bad role", packet["response_error_message_bounded"])
        self.assertNotIn("raw_body", packet)
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

    def test_run_prompt_admits_workspace_write_only_with_temp_add_dir(self) -> None:
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
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        captured_command: list[str] = []

        def fake_observed_run(command: list[str], **_kwargs: object) -> dict[str, object]:
            captured_command[:] = command
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("WORKSPACE_WRITE_OK\n", encoding="utf-8")
            return {
                "exit_code": 0,
                "stderr": "",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "process_tree_observed": True,
                    "sample_count": 1,
                    "observed_process_count_max": 1,
                    "allowed_local_endpoint_observed": True,
                    "non_local_peer_endpoints_present": False,
                    "classification": "wbp_forward_only_proven",
                    "direct_non_wbp_model_egress_absent_proven": True,
                    "raw_pid_exposed": False,
                    "pid_not_exposed_to_browser": True,
                    "secret_value_recorded": False,
                },
            }

        with tempfile.TemporaryDirectory(prefix="wbp-operator-add-dir-test-") as temp_dir:
            writable_dir = Path(temp_dir)
            with mock.patch(
                "wild_boar_proxy.operator_surface._run_command_with_observation",
                side_effect=fake_observed_run,
            ):
                result = session.run_prompt(
                    {
                        "prompt": "Reply with exactly WORKSPACE_WRITE_OK.",
                        "model_id": "gpt-5.3-codex",
                    },
                    sandbox_mode_override="workspace-write",
                    writable_additional_dir=writable_dir,
                )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sandbox_mode"], "workspace-write")
        self.assertTrue(result["workspace_write_admitted"])
        self.assertTrue(result["additional_writable_dir_admitted"])
        self.assertEqual(result["additional_writable_dir_scope"], "temp_only")
        self.assertFalse(result["danger_full_access_admitted"])
        self.assertIn("--add-dir", captured_command)
        self.assertEqual(captured_command[captured_command.index("--add-dir") + 1], str(writable_dir.resolve()))
        self.assertIn("--add-dir", result["command_surface"]["args_shape"])
        self.assertNotIn(str(writable_dir.resolve()), json.dumps(result))

    def test_run_prompt_admits_declared_repo_tmp_add_dir_only_with_explicit_flag(self) -> None:
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
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        captured_command: list[str] = []

        def fake_observed_run(command: list[str], **_kwargs: object) -> dict[str, object]:
            captured_command[:] = command
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("REPO_TMP_WRITE_OK\n", encoding="utf-8")
            return {
                "exit_code": 0,
                "stderr": "",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "process_tree_observed": True,
                    "sample_count": 1,
                    "observed_process_count_max": 1,
                    "allowed_local_endpoint_observed": True,
                    "non_local_peer_endpoints_present": False,
                    "classification": "wbp_forward_only_proven",
                    "direct_non_wbp_model_egress_absent_proven": True,
                    "raw_pid_exposed": False,
                    "pid_not_exposed_to_browser": True,
                    "secret_value_recorded": False,
                },
            }

        repo_tmp = Path.cwd().resolve() / ".tmp"
        repo_tmp.mkdir(exist_ok=True)
        with mock.patch(
            "wild_boar_proxy.operator_surface._run_command_with_observation",
            side_effect=fake_observed_run,
        ):
            rejected = session.run_prompt(
                {
                    "prompt": "Reply with exactly REPO_TMP_WRITE_OK.",
                    "model_id": "gpt-5.3-codex",
                },
                sandbox_mode_override="workspace-write",
                writable_additional_dir=repo_tmp,
            )
            result = session.run_prompt(
                {
                    "prompt": "Reply with exactly REPO_TMP_WRITE_OK.",
                    "model_id": "gpt-5.3-codex",
                },
                sandbox_mode_override="workspace-write",
                writable_additional_dir=repo_tmp,
                declared_repo_tmp_dir=repo_tmp,
            )

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["machine_error_code"], "ADDITIONAL_WRITABLE_DIR_NOT_ADMITTED")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["additional_writable_dir_admitted"])
        self.assertEqual(result["additional_writable_dir_scope"], "declared_repo_tmp_only")
        self.assertIn("--add-dir", captured_command)
        self.assertEqual(captured_command[captured_command.index("--add-dir") + 1], str(repo_tmp.resolve()))

    def test_run_prompt_rejects_danger_full_access_sandbox_override(self) -> None:
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
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        with mock.patch("wild_boar_proxy.operator_surface._run_command_with_observation") as observed_run:
            result = session.run_prompt(
                {
                    "prompt": "Reply OK.",
                    "model_id": "gpt-5.3-codex",
                },
                sandbox_mode_override="danger-full-access",
            )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["machine_error_code"], "SANDBOX_MODE_NOT_ADMITTED")
        self.assertFalse(result["danger_full_access_admitted"])
        observed_run.assert_not_called()

    def test_run_prompt_preserves_normalized_primary_slot_as_non_explicit(self) -> None:
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
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("MAIN_WEB_OK\n", encoding="utf-8")
            return {
                "exit_code": 0,
                "stderr": "",
                "timed_out": False,
                "process_network_observation_packet": {
                    "status": "ok",
                    "machine_error_code": "OK",
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
                    "slot_id": "primary_model_slot",
                    "slot_id_explicit": False,
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["requested_slot_id"], "primary_model_slot")
        self.assertFalse(result["requested_slot_explicit"])

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
        self.assertEqual(captured["payload"]["model"], "openai/gpt-5")
        self.assertEqual(captured["payload"]["stream"], False)
        self.assertEqual(captured["payload"]["max_tokens"], 32)
        messages = captured["payload"]["messages"]
        self.assertEqual(messages[-1], {"role": "user", "content": "Reply exactly OK"})
        runtime_truth = [
            message for message in messages if "runtime routing truth" in str(message.get("content"))
        ]
        self.assertEqual(len(runtime_truth), 1)
        self.assertLess(messages.index(runtime_truth[0]), len(messages) - 1)

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

    def test_hybrid_openai_compat_adapter_merges_route_ids_into_models(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:
                if self.path != "/v1/models":
                    self.send_error(404)
                    return
                if self.headers.get("Authorization") != "Bearer sk-local-test":
                    self.send_error(401)
                    return
                body = json.dumps({"data": [{"id": "gpt-5.3-codex"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            route = {
                "route_id": "wbp-web-primary-openrouter",
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "endpoint_path": "/chat/completions",
                "upstream_model": "openai/gpt-5",
                "auth": {"secret_ref": "OPENROUTER_API_KEY"},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                    return_value="sk-route-secret",
                ),
                HybridOpenAICompatAdapter(
                    downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                    expected_api_key="sk-local-test",
                    routes=[route],
                ) as adapter,
            ):
                request = urllib.request.Request(
                    f"{adapter.listen_endpoint}/models",
                    headers={"Authorization": "Bearer sk-local-test"},
                    method="GET",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(
            [item["id"] for item in payload["data"]],
            ["gpt-5.3-codex", "wbp-web-primary-openrouter"],
        )

    def test_hybrid_openai_compat_adapter_hides_blocked_native_models_from_models_surface(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:
                if self.path != "/v1/models":
                    self.send_error(404)
                    return
                body = json.dumps(
                    {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.4-mini"}]}
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with HybridOpenAICompatAdapter(
                downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                expected_api_key="sk-local-test",
                routes=[],
                hidden_downstream_model_ids=["gpt-5.5"],
            ) as adapter:
                request = urllib.request.Request(
                    f"{adapter.listen_endpoint}/models",
                    headers={"Authorization": "Bearer sk-local-test"},
                    method="GET",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual([item["id"] for item in payload["data"]], ["gpt-5.4-mini"])

    def test_hybrid_openai_compat_adapter_can_admit_missing_auth_only_from_loopback_when_enabled(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:
                if self.path != "/v1/models":
                    self.send_error(404)
                    return
                body = json.dumps({"data": [{"id": "gpt-5.3-codex"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with HybridOpenAICompatAdapter(
                downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                expected_api_key="sk-local-test",
                routes=[],
                allow_missing_auth_from_loopback=True,
            ) as adapter:
                request = urllib.request.Request(f"{adapter.listen_endpoint}/models", method="GET")
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual([item["id"] for item in payload["data"]], ["gpt-5.3-codex"])

        strict_adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:1/v1",
            expected_api_key="sk-local-test",
            routes=[],
        )
        status, _, body = strict_adapter.handle(
            method="GET",
            path="/v1/models",
            headers={},
            body=b"",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 401)
        auth_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(auth_payload["error"]["type"], "local_bridge_auth_error")
        self.assertEqual(auth_payload["error"]["code"], "LOCAL_BRIDGE_AUTH_ERROR")
        self.assertEqual(auth_payload["error"]["bridge_code"], "BRIDGE_AUTH_MISSING")
        self.assertEqual(auth_payload["bridge_machine_error_code"], "BRIDGE_AUTH_MISSING")
        self.assertTrue(auth_payload["auth_header_expected"])
        self.assertFalse(auth_payload["auth_header_seen"])
        self.assertFalse(auth_payload["auth_ok"])
        self.assertNotIn("sk-local-test", json.dumps(auth_payload))
        auth_trace = strict_adapter.trace_snapshot()
        self.assertEqual(auth_trace["bridge_machine_error_code"], "BRIDGE_AUTH_MISSING")
        self.assertEqual(auth_trace["bridge_health_packet"]["machine_error_code"], "BRIDGE_AUTH_MISSING")
        self.assertEqual(
            auth_trace["bridge_request_trace_packet"]["machine_error_code"],
            "BRIDGE_AUTH_MISSING",
        )
        self.assertFalse(auth_trace["bridge_request_trace_packet"]["fallback_used"])

        status, _, body = strict_adapter.handle(
            method="GET",
            path="/v1/models",
            headers={"Authorization": "Bearer wrong-local-token"},
            body=b"",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 401)
        rejected_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(rejected_payload["bridge_machine_error_code"], "BRIDGE_AUTH_REJECTED")
        rejected_trace = strict_adapter.trace_snapshot()
        self.assertEqual(rejected_trace["bridge_machine_error_code"], "BRIDGE_AUTH_REJECTED")
        self.assertFalse(rejected_trace["bridge_health_packet"]["secret_value_recorded"])

        route = {
            "route_id": "wbp-web-primary-openrouter",
            "enabled": True,
            "base_url": "https://openrouter.ai/api/v1",
            "endpoint_path": "/chat/completions",
            "upstream_model": "openai/gpt-5",
            "auth": {"secret_ref": "OPENROUTER_API_KEY"},
        }
        with (
            mock.patch(
                "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                return_value="sk-route-secret",
            ),
            mock.patch.object(
                ExternalRouteResponsesAdapter,
                "handle",
                return_value=(
                    200,
                    {"Content-Type": "application/json"},
                    json.dumps({"output_text": "API_OK"}).encode("utf-8"),
                ),
            ) as route_handle,
        ):
            adapter = HybridOpenAICompatAdapter(
                downstream_endpoint="http://127.0.0.1:1/v1",
                expected_api_key="sk-local-test",
                routes=[route],
                allow_missing_auth_from_loopback=True,
            )
            status, _, body = adapter.handle(
                method="POST",
                path="/v1/responses",
                headers={},
                body=json.dumps({"model": "wbp-web-primary-openrouter", "input": "hello"}).encode("utf-8"),
                client_host="127.0.0.1",
            )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["output_text"], "API_OK")
        self.assertEqual(
            route_handle.call_args.kwargs["headers"].get("Authorization"),
            "Bearer sk-local-test",
        )

    def test_hybrid_openai_compat_adapter_dispatches_route_model_to_external_route(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            downstream_called = False

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                type(self).downstream_called = True
                self.send_error(500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            route = {
                "route_id": "wbp-web-primary-openrouter",
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "endpoint_path": "/chat/completions",
                "upstream_model": "openai/gpt-5",
                "auth": {"secret_ref": "OPENROUTER_API_KEY"},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                    return_value="sk-route-secret",
                ),
                mock.patch.object(
                    ExternalRouteResponsesAdapter,
                    "handle",
                    return_value=(
                        200,
                        {"Content-Type": "application/json"},
                        json.dumps({"output_text": "API_OK"}).encode("utf-8"),
                    ),
                ) as route_handle,
                HybridOpenAICompatAdapter(
                    downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                    expected_api_key="sk-local-test",
                    routes=[route],
                ) as adapter,
            ):
                request = urllib.request.Request(
                    f"{adapter.listen_endpoint}/responses",
                    data=json.dumps(
                        {"model": "wbp-web-primary-openrouter", "input": "hello"}
                    ).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer sk-local-test",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(payload["output_text"], "API_OK")
        self.assertFalse(DownstreamHandler.downstream_called)
        route_handle.assert_called_once()

    def test_hybrid_openai_compat_adapter_forces_native_model_request_to_selected_route(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            downstream_called = False

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                type(self).downstream_called = True
                self.send_error(500)

        route = {
            "route_id": "wbp-deepseek-v4-pro-max",
            "provider": "deepseek",
            "enabled": True,
            "base_url": "https://api.deepseek.com/v1",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-v4-pro",
            "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
            "thinking": {"type": "enabled", "reasoning_effort": "max"},
        }
        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with (
                mock.patch(
                    "wild_boar_proxy.operator_surface._resolve_external_route_secret_value",
                    return_value="sk-route-secret",
                ),
                mock.patch.object(
                    ExternalRouteResponsesAdapter,
                    "handle",
                    return_value=(
                        200,
                        {"Content-Type": "application/json"},
                        json.dumps({"requested_model": "wbp-deepseek-v4-pro-max"}).encode("utf-8"),
                    ),
                ) as route_handle,
                HybridOpenAICompatAdapter(
                    downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                    expected_api_key="sk-local-test",
                    routes=[route],
                    forced_route_model_id="wbp-deepseek-v4-pro-max",
                ) as adapter,
            ):
                adapter.set_trace_context(
                    {
                        "launch_id": "launch-test",
                        "trace_id": "trace-test",
                        "selected_model": "wbp-deepseek-v4-pro-max",
                        "api_reasoning_option_id": "provider_declared_max",
                        "launch_route_digest": "bad-digest",
                    }
                )
                request = urllib.request.Request(
                    f"{adapter.listen_endpoint}/responses",
                    data=json.dumps(
                        {
                            "model": "gpt-5.5",
                            "input": "Ответь одной строкой: WBP_DEEPSEEK_WINDOW_SMOKE_OK",
                        }
                    ).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer sk-local-test",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                trace = adapter.trace_snapshot()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(payload["requested_model"], "wbp-deepseek-v4-pro-max")
        self.assertFalse(DownstreamHandler.downstream_called)
        captured = json.loads(route_handle.call_args.kwargs["body"].decode("utf-8"))
        self.assertEqual(captured["model"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(trace["request_count"], 1)
        self.assertEqual(trace["trace_id"], "trace-test")
        self.assertEqual(trace["launch_packet_id"], "launch-test")
        self.assertTrue(trace["bridge_alive"])
        self.assertTrue(trace["responses_endpoint_alive"])
        self.assertTrue(trace["auth_header_expected"])
        self.assertTrue(trace["auth_header_seen"])
        self.assertTrue(trace["auth_ok"])
        self.assertEqual(trace["selected_route"], "wbp-deepseek-v4-pro-max")
        self.assertEqual(trace["provider_id"], "deepseek")
        self.assertEqual(trace["model_id"], "deepseek-v4-pro")
        self.assertFalse(trace["fallback_used"])
        self.assertFalse(trace["restart_required"])
        self.assertFalse(trace["stale_port_detected"])
        last_record = trace["last_record"]
        self.assertEqual(last_record["launch_id"], "launch-test")
        self.assertEqual(last_record["trace_id"], "trace-test")
        self.assertEqual(last_record["launch_packet_id"], "launch-test")
        self.assertEqual(last_record["requested_model"], "gpt-5.5")
        self.assertEqual(last_record["effective_route_model"], "wbp-deepseek-v4-pro-max")
        self.assertTrue(last_record["forced_route_used"])
        self.assertTrue(last_record["provider_called"])
        self.assertEqual(last_record["provider_id"], "deepseek")
        self.assertEqual(last_record["upstream_model"], "deepseek-v4-pro")
        self.assertEqual(last_record["api_reasoning_option_id"], "provider_declared_max")
        self.assertTrue(last_record["known_smoke_phrase_matched"])
        self.assertTrue(last_record["response_seen"])
        self.assertFalse(last_record["route_digest_matches_launch"])
        self.assertFalse(last_record["raw_prompt_recorded"])
        self.assertFalse(last_record["auth_header_recorded"])
        self.assertFalse(last_record["secret_value_recorded"])
        self.assertFalse(last_record["response_text_counts_as_model_truth"])

    def test_hybrid_openai_compat_adapter_classifies_stale_responses_port(self) -> None:
        adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:1/v1",
            expected_api_key="sk-local-test",
            routes=[],
        )
        adapter.set_trace_context(
            {
                "launch_id": "launch-stale",
                "trace_id": "trace-stale",
                "selected_model": "gpt-5.4",
            }
        )

        status, _, body = adapter.handle(
            method="POST",
            path="/v1/responses",
            headers={
                "Authorization": "Bearer sk-local-test",
                "Content-Type": "application/json",
            },
            body=json.dumps({"model": "gpt-5.4", "input": "hello"}).encode("utf-8"),
        )
        payload = json.loads(body.decode("utf-8"))
        trace = adapter.trace_snapshot()

        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["type"], "local_bridge_error")
        self.assertEqual(payload["error"]["code"], "STALE_RESPONSES_PORT")
        self.assertEqual(payload["error"]["bridge_code"], "BRIDGE_PORT_STALE")
        self.assertEqual(payload["bridge_machine_error_code"], "BRIDGE_PORT_STALE")
        self.assertTrue(payload["restart_required"])
        self.assertTrue(payload["stale_port_detected"])
        self.assertEqual(trace["request_count"], 1)
        self.assertEqual(trace["trace_id"], "trace-stale")
        self.assertEqual(trace["last_error_type"], "STALE_RESPONSES_PORT")
        self.assertEqual(trace["bridge_machine_error_code"], "BRIDGE_PORT_STALE")
        self.assertTrue(trace["restart_required"])
        self.assertTrue(trace["recoverable"])
        self.assertTrue(trace["stale_port_detected"])
        self.assertFalse(trace["fallback_used"])
        self.assertEqual(trace["bridge_health_packet"]["machine_error_code"], "BRIDGE_PORT_STALE")
        self.assertFalse(trace["bridge_health_packet"]["responses_endpoint_ready"])
        self.assertEqual(
            trace["bridge_request_trace_packet"]["machine_error_code"],
            "BRIDGE_PORT_STALE",
        )
        self.assertFalse(trace["bridge_request_trace_packet"]["fallback_used"])
        self.assertTrue(trace["bridge_request_trace_packet"]["retry_allowed"])
        self.assertNotIn("sk-local-test", json.dumps(payload))

    def test_hybrid_openai_compat_adapter_reports_unstarted_responses_endpoint_unready(self) -> None:
        adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:8329/v1",
            expected_api_key="sk-local-test",
            routes=[],
        )
        adapter.set_trace_context(
            {
                "launch_id": "launch-unready",
                "trace_id": "trace-unready",
                "selected_model": "gpt-5.4",
            }
        )

        trace = adapter.trace_snapshot()

        self.assertFalse(trace["bridge_alive"])
        self.assertFalse(trace["responses_endpoint_alive"])
        self.assertEqual(
            trace["bridge_machine_error_code"],
            "BRIDGE_RESPONSES_ENDPOINT_UNREADY",
        )
        self.assertEqual(
            trace["bridge_health_packet"]["machine_error_code"],
            "BRIDGE_RESPONSES_ENDPOINT_UNREADY",
        )
        self.assertFalse(trace["bridge_health_packet"]["responses_endpoint_ready"])
        self.assertFalse(trace["bridge_request_trace_packet"]["request_started"])
        self.assertFalse(trace["bridge_request_trace_packet"]["fallback_used"])

    def test_hybrid_openai_compat_adapter_classifies_stream_disconnect(self) -> None:
        adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:8329/v1",
            expected_api_key="sk-local-test",
            routes=[],
        )
        adapter.set_trace_context(
            {
                "launch_id": "launch-stream",
                "trace_id": "trace-stream",
                "selected_model": "gpt-5.4",
            }
        )

        with mock.patch.object(urllib.request.OpenerDirector, "open", side_effect=TimeoutError):
            status, _, body = adapter.handle(
                method="POST",
                path="/v1/responses",
                headers={
                    "Authorization": "Bearer sk-local-test",
                    "Content-Type": "application/json",
                },
                body=json.dumps({"model": "gpt-5.4", "input": "hello"}).encode("utf-8"),
            )
        payload = json.loads(body.decode("utf-8"))
        trace = adapter.trace_snapshot()

        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "LOCAL_BRIDGE_STREAM_TIMEOUT")
        self.assertEqual(payload["error"]["bridge_code"], "BRIDGE_STREAM_TIMEOUT")
        self.assertEqual(payload["bridge_machine_error_code"], "BRIDGE_STREAM_TIMEOUT")
        self.assertTrue(payload["restart_required"])
        self.assertEqual(trace["last_error_type"], "LOCAL_BRIDGE_STREAM_TIMEOUT")
        self.assertEqual(trace["bridge_machine_error_code"], "BRIDGE_STREAM_TIMEOUT")
        self.assertTrue(trace["restart_required"])
        self.assertFalse(trace["fallback_used"])
        self.assertFalse(trace["stale_launch_packet"])
        self.assertEqual(
            trace["bridge_request_trace_packet"]["machine_error_code"],
            "BRIDGE_STREAM_TIMEOUT",
        )

    def test_hybrid_openai_compat_adapter_classifies_stream_reset_disconnect(self) -> None:
        adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:8329/v1",
            expected_api_key="sk-local-test",
            routes=[],
        )
        adapter.set_trace_context(
            {
                "launch_id": "launch-reset",
                "trace_id": "trace-reset",
                "selected_model": "gpt-5.4",
            }
        )

        with mock.patch.object(
            urllib.request.OpenerDirector,
            "open",
            side_effect=ConnectionResetError,
        ):
            status, _, body = adapter.handle(
                method="POST",
                path="/v1/responses",
                headers={
                    "Authorization": "Bearer sk-local-test",
                    "Content-Type": "application/json",
                },
                body=json.dumps(
                    {"model": "gpt-5.4", "input": "hello", "stream": True}
                ).encode("utf-8"),
            )
        payload = json.loads(body.decode("utf-8"))
        trace = adapter.trace_snapshot()

        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "LOCAL_BRIDGE_STREAM_DISCONNECTED")
        self.assertEqual(payload["error"]["bridge_code"], "BRIDGE_STREAM_DISCONNECTED")
        self.assertEqual(trace["bridge_machine_error_code"], "BRIDGE_STREAM_DISCONNECTED")
        self.assertTrue(trace["bridge_request_trace_packet"]["stream_requested"])
        self.assertFalse(trace["bridge_request_trace_packet"]["stream_completed"])
        self.assertFalse(trace["bridge_request_trace_packet"]["fallback_used"])

    def test_hybrid_openai_compat_adapter_classifies_dead_bridge(self) -> None:
        adapter = HybridOpenAICompatAdapter(
            downstream_endpoint="http://127.0.0.1:8329/v1",
            expected_api_key="sk-local-test",
            routes=[],
        )
        adapter.set_trace_context(
            {
                "launch_id": "launch-dead",
                "trace_id": "trace-dead",
                "selected_model": "gpt-5.4",
            }
        )

        with mock.patch.object(urllib.request.OpenerDirector, "open", side_effect=OSError):
            status, _, body = adapter.handle(
                method="POST",
                path="/v1/responses",
                headers={
                    "Authorization": "Bearer sk-local-test",
                    "Content-Type": "application/json",
                },
                body=json.dumps({"model": "gpt-5.4", "input": "hello"}).encode("utf-8"),
            )
        payload = json.loads(body.decode("utf-8"))
        trace = adapter.trace_snapshot()

        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "LOCAL_BRIDGE_DEAD")
        self.assertEqual(payload["error"]["bridge_code"], "BRIDGE_PROCESS_DEAD")
        self.assertEqual(payload["bridge_machine_error_code"], "BRIDGE_PROCESS_DEAD")
        self.assertTrue(payload["restart_required"])
        self.assertEqual(trace["last_error_type"], "LOCAL_BRIDGE_DEAD")
        self.assertEqual(trace["bridge_machine_error_code"], "BRIDGE_PROCESS_DEAD")
        self.assertTrue(trace["restart_required"])
        self.assertFalse(trace["fallback_used"])
        self.assertFalse(trace["stale_launch_packet"])

    def test_hybrid_openai_compat_adapter_marks_stale_launch_packet_restart_required(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"output_text": "OLD_LAUNCH_OK"}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with HybridOpenAICompatAdapter(
                downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                expected_api_key="sk-local-test",
                routes=[],
            ) as adapter:
                adapter.set_trace_context(
                    {
                        "launch_packet_id": "launch-old",
                        "trace_id": "trace-old",
                        "selected_model": "gpt-5.4",
                    }
                )
                request = urllib.request.Request(
                    f"{adapter.listen_endpoint}/responses",
                    data=json.dumps({"model": "gpt-5.4", "input": "hello"}).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer sk-local-test",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    self.assertEqual(response.status, 200)
                adapter.set_trace_context(
                    {
                        "launch_packet_id": "launch-new",
                        "trace_id": "trace-new",
                        "selected_model": "gpt-5.4",
                    }
                )
                trace = adapter.trace_snapshot()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(trace["launch_packet_id"], "launch-new")
        self.assertEqual(trace["last_record_launch_packet_id"], "launch-old")
        self.assertTrue(trace["stale_launch_packet"])
        self.assertEqual(trace["last_error_type"], "STALE_LAUNCH_PACKET")
        self.assertEqual(trace["bridge_machine_error_code"], "BRIDGE_PORT_NOT_OWNED")
        self.assertEqual(
            trace["bridge_health_packet"]["machine_error_code"],
            "BRIDGE_PORT_NOT_OWNED",
        )
        self.assertTrue(trace["restart_required"])
        self.assertFalse(trace["fallback_used"])

    def _bridge_failure_recovery_truth_fixture(
        self,
        *,
        bridge_machine_error_code: str = "OK",
        upstream_status: int = 200,
        bridge_alive: bool = True,
        responses_endpoint_ready: bool = True,
        route_unchanged: bool = True,
        fallback_used: bool = False,
        stale_launch_packet: bool = False,
        response_seen: bool = True,
        stream_requested: bool = False,
        stream_completed: bool = True,
        selected_route: str = "wbp-deepseek-v4-pro-max",
        effective_route: str = "wbp-deepseek-v4-pro-max",
    ) -> tuple[dict[str, object], dict[str, object]]:
        launch: dict[str, object] = {
            "status": "ok",
            "launch_id": "launch-bridge",
            "trace_id": "trace-bridge",
            "selected_model": selected_route,
            "original_codex_touched": False,
            "asar_touched": False,
        }
        trace: dict[str, object] = {
            "bridge_alive": bridge_alive,
            "responses_endpoint_alive": responses_endpoint_ready,
            "bridge_machine_error_code": bridge_machine_error_code,
            "fallback_used": fallback_used,
            "stale_launch_packet": stale_launch_packet,
            "route_unchanged": route_unchanged,
            "selected_route": effective_route,
            "bridge_health_packet": {
                "packet_kind": "hybrid_openai_compat_bridge_health",
                "machine_error_code": bridge_machine_error_code,
                "responses_endpoint_ready": responses_endpoint_ready,
                "bridge_alive": bridge_alive,
                "fallback_used": fallback_used,
                "secret_value_recorded": False,
            },
            "bridge_request_trace_packet": {
                "packet_kind": "hybrid_openai_compat_bridge_request_trace",
                "machine_error_code": bridge_machine_error_code,
                "request_started": True,
                "route_unchanged": route_unchanged,
                "fallback_used": fallback_used,
                "retry_attempted": False,
                "stream_requested": stream_requested,
                "stream_completed": stream_completed,
            },
            "last_record": {
                "request_seen_after_launch": True,
                "response_seen": response_seen,
                "selected_model": selected_route,
                "effective_route_model": effective_route,
                "forced_route_used": effective_route == selected_route,
                "upstream_status": upstream_status,
                "fallback_used": fallback_used,
                "raw_prompt_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            },
        }
        return launch, trace

    def test_bridge_failure_recovery_truth_reports_ready_bridge_without_restart(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture()

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["last_error_kind"], "none")
        self.assertTrue(packet["bridge_ready"])
        self.assertTrue(packet["last_request_seen"])
        self.assertTrue(packet["last_response_completed"])
        self.assertTrue(packet["selected_route_preserved"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["restart_admissible"])
        self.assertFalse(packet["restart_attempted"])
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_BRIDGE_FAILURE_AND_RECOVERY_TRUTH_PROVEN_WITH_LIMITS",
        )
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])

    def test_bridge_failure_recovery_truth_classifies_stream_disconnect_as_retryable(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture(
            bridge_machine_error_code="BRIDGE_STREAM_DISCONNECTED",
            response_seen=False,
            stream_requested=True,
            stream_completed=False,
        )

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["last_error_kind"], "stream_disconnected")
        self.assertTrue(packet["safe_to_retry"])
        self.assertFalse(packet["requires_owner_action"])
        self.assertTrue(packet["restart_admissible"])
        self.assertFalse(packet["restart_attempted"])
        self.assertTrue(packet["owner_action_required_for_live_restart"])
        self.assertFalse(packet["fallback_used"])
        self.assertTrue(packet["selected_route_preserved"])
        self.assertEqual(
            packet["final_status"],
            "CUSTOM_CODEX_BRIDGE_FAILURE_AND_RECOVERY_TRUTH_PROVEN_WITH_LIMITS",
        )

    def test_bridge_failure_recovery_truth_classifies_unauthorized_as_owner_action(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture(
            upstream_status=401,
            response_seen=False,
        )

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["bridge_ready"])
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["last_error_kind"], "unauthorized")
        self.assertFalse(packet["safe_to_retry"])
        self.assertTrue(packet["requires_owner_action"])
        self.assertFalse(packet["restart_admissible"])
        self.assertFalse(packet["fallback_used"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_CUSTOM_CODEX_BRIDGE_STABILITY_NOT_PROVEN",
        )

    def test_bridge_failure_recovery_truth_classifies_dead_bridge_without_live_restart(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture(
            bridge_machine_error_code="BRIDGE_PROCESS_DEAD",
            bridge_alive=False,
            responses_endpoint_ready=False,
            response_seen=False,
        )

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["last_error_kind"], "bridge_process_dead")
        self.assertTrue(packet["safe_to_retry"])
        self.assertTrue(packet["restart_admissible"])
        self.assertFalse(packet["restart_attempted"])
        self.assertFalse(packet["profile_mutation_attempted"])
        self.assertFalse(packet["history_deletion_attempted"])

    def test_bridge_failure_recovery_truth_blocks_stale_port_as_not_ready(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture(
            bridge_machine_error_code="BRIDGE_PORT_STALE",
            responses_endpoint_ready=False,
            response_seen=False,
        )
        trace["stale_port_detected"] = True

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["last_error_kind"], "stale_port")
        self.assertTrue(packet["stale_port_detected"])
        self.assertTrue(packet["safe_to_retry"])
        self.assertTrue(packet["restart_admissible"])
        self.assertFalse(packet["restart_attempted"])

    def test_bridge_failure_recovery_truth_blocks_route_mismatch(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture(
            route_unchanged=False,
            effective_route="gpt-5.4",
        )

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["last_error_kind"], "route_mismatch")
        self.assertFalse(packet["selected_route_preserved"])
        self.assertFalse(packet["restart_admissible"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_CUSTOM_CODEX_BRIDGE_STABILITY_NOT_PROVEN",
        )
        self.assertFalse(packet["route_swap_attempted"])

    def test_bridge_failure_recovery_truth_blocks_fallback_attempt(self) -> None:
        launch, trace = self._bridge_failure_recovery_truth_fixture(fallback_used=True)

        packet = build_bridge_failure_recovery_truth_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["last_error_kind"], "fallback_attempt")
        self.assertTrue(packet["fallback_used"])
        self.assertTrue(packet["fallback_attempted"])
        self.assertFalse(packet["selected_route_preserved"])
        self.assertFalse(packet["restart_admissible"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_CUSTOM_CODEX_BRIDGE_STABILITY_NOT_PROVEN",
        )

    def _stable_bridge_preflight_fixture(
        self,
        **overrides: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        launch, trace = self._bridge_failure_recovery_truth_fixture(**overrides)
        health = trace["bridge_health_packet"]
        request_trace = trace["bridge_request_trace_packet"]
        record = trace["last_record"]
        self.assertIsInstance(health, dict)
        self.assertIsInstance(request_trace, dict)
        self.assertIsInstance(record, dict)
        health.update(
            {
                "bridge_port": 53621,
                "port_owned_by_bridge": True,
                "auth_header_expected": True,
                "auth_header_present": True,
                "auth_ok": True,
            }
        )
        request_trace.update({"auth_header_seen": True, "auth_ok": True})
        record.update({"auth_header_seen": True, "auth_ok": True})
        trace.update(
            {
                "bridge_port": 53621,
                "auth_header_expected": True,
                "auth_header_seen": True,
                "auth_ok": True,
            }
        )
        return launch, trace

    def test_stable_bridge_preflight_allows_only_explicit_healthy_bridge(self) -> None:
        launch, trace = self._stable_bridge_preflight_fixture()

        packet = build_stable_bridge_preflight_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["launch_allowed"])
        self.assertTrue(packet["bridge_process_seen"])
        self.assertTrue(packet["bridge_health_ok"])
        self.assertTrue(packet["bridge_owner_known"])
        self.assertTrue(packet["auth_matches"])
        self.assertTrue(packet["stream_state_known"])
        self.assertTrue(packet["stream_not_known_broken"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["fallback_attempted"])
        self.assertEqual(packet["final_status"], "STABLE_BRIDGE_PREFLIGHT_PROVEN_WITH_LIMITS")
        self.assertEqual(packet["next_action"], "none")

    def test_stable_bridge_preflight_blocks_missing_health_as_unknown(self) -> None:
        launch, trace = self._stable_bridge_preflight_fixture()
        trace.pop("bridge_health_packet")

        packet = build_stable_bridge_preflight_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["launch_allowed"])
        self.assertIn("bridge_health_packet", packet["unknown_critical_fields"])
        self.assertIn("unknown_not_admitted", packet["blocking_reasons"])
        self.assertEqual(
            packet["final_status"],
            "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN",
        )

    def test_stable_bridge_preflight_blocks_unknown_stream_state(self) -> None:
        launch, trace = self._stable_bridge_preflight_fixture()
        request_trace = trace["bridge_request_trace_packet"]
        self.assertIsInstance(request_trace, dict)
        request_trace.pop("stream_requested")
        request_trace.pop("stream_completed")

        packet = build_stable_bridge_preflight_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["launch_allowed"])
        self.assertFalse(packet["stream_state_known"])
        self.assertIn("stream_state", packet["unknown_critical_fields"])
        self.assertIn("stream_state_unknown", packet["blocking_reasons"])

    def test_stable_bridge_preflight_blocks_auth_and_401(self) -> None:
        launch, trace = self._stable_bridge_preflight_fixture(upstream_status=401)
        health = trace["bridge_health_packet"]
        request_trace = trace["bridge_request_trace_packet"]
        record = trace["last_record"]
        self.assertIsInstance(health, dict)
        self.assertIsInstance(request_trace, dict)
        self.assertIsInstance(record, dict)
        health["auth_ok"] = False
        request_trace["auth_ok"] = False
        record["auth_ok"] = False
        trace["auth_ok"] = False

        packet = build_stable_bridge_preflight_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["launch_allowed"])
        self.assertEqual(packet["last_http_status"], 401)
        self.assertEqual(packet["last_error_class"], "unauthorized")
        self.assertIn("auth_mismatch", packet["blocking_reasons"])
        self.assertIn("http_401_unauthorized", packet["blocking_reasons"])

    def test_stable_bridge_preflight_blocks_stream_disconnect(self) -> None:
        launch, trace = self._stable_bridge_preflight_fixture(
            bridge_machine_error_code="BRIDGE_STREAM_DISCONNECTED",
            responses_endpoint_ready=False,
            response_seen=False,
            stream_requested=True,
            stream_completed=False,
        )

        packet = build_stable_bridge_preflight_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["launch_allowed"])
        self.assertEqual(packet["last_error_class"], "stream_disconnected")
        self.assertFalse(packet["stream_not_known_broken"])
        self.assertTrue(packet["last_stream_failure_classified"])

    def test_stable_bridge_preflight_blocks_fallback_attempt(self) -> None:
        launch, trace = self._stable_bridge_preflight_fixture(fallback_used=True)

        packet = build_stable_bridge_preflight_packet(
            last_launch_packet=launch,
            bridge_trace_packet=trace,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["launch_allowed"])
        self.assertTrue(packet["fallback_used"])
        self.assertTrue(packet["fallback_attempted"])
        self.assertIn("fallback_attempted", packet["blocking_reasons"])

    def test_hybrid_openai_compat_adapter_marks_stable_bridge_window_smoke_phrase(self) -> None:
        prompt_hash, smoke_match = _prompt_trace_hash_and_smoke_match(
            {
                "model": "wbp-deepseek-v4-pro-max",
                "input": "Ответь одной строкой: WBP_STABLE_BRIDGE_SMOKE_OK",
            }
        )

        self.assertTrue(prompt_hash)
        self.assertTrue(smoke_match)

    def test_hybrid_openai_compat_adapter_marks_window_trace_refresh_smoke_phrase(self) -> None:
        prompt_hash, smoke_match = _prompt_trace_hash_and_smoke_match(
            {
                "model": "wbp-deepseek-v4-pro-max",
                "input": "Ответь одной строкой: WBP_DEEPSEEK_WINDOW_TRACE_REFRESH_OK",
            }
        )

        self.assertTrue(prompt_hash)
        self.assertTrue(smoke_match)

    def test_hybrid_openai_compat_adapter_records_downstream_prompt_trace(self) -> None:
        class DownstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"output_text": "CHATGPT_OK"}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with HybridOpenAICompatAdapter(
                downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                expected_api_key="sk-local-test",
                routes=[],
            ) as adapter:
                adapter.set_trace_context(
                    {
                        "launch_id": "launch-test",
                        "trace_id": "trace-test",
                        "selected_model": "gpt-5.4",
                        "api_reasoning_option_id": "",
                        "launch_route_digest": "",
                    }
                )
                request = urllib.request.Request(
                    f"{adapter.listen_endpoint}/responses",
                    data=json.dumps(
                        {
                            "model": "gpt-5.4",
                            "input": "Попроси кодера ответить WBP_MIXED_DEEPSEEK_CODER_OK",
                        }
                    ).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer sk-local-test",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request,
                    timeout=5,
                ) as response:
                    self.assertEqual(response.status, 200)
                trace = adapter.trace_snapshot()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(trace["request_count"], 1)
        last_record = trace["last_record"]
        self.assertTrue(last_record["request_seen_after_launch"])
        self.assertTrue(last_record["downstream_called"])
        self.assertTrue(last_record["chatgpt_route_used"])
        self.assertFalse(last_record["provider_called"])
        self.assertEqual(last_record["requested_model"], "gpt-5.4")
        self.assertTrue(last_record["known_smoke_phrase_matched"])
        self.assertFalse(last_record["raw_prompt_recorded"])
        self.assertFalse(last_record["secret_value_recorded"])

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
