# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
import subprocess
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from wild_boar_proxy.operator_surface import (
    OperatorSurfaceConfig,
    OperatorSurfaceSession,
    WbpTraceObserver,
    build_codex_config,
    forbidden_browser_fields,
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
        session.status_payload = lambda: {  # type: ignore[method-assign]
            "status": {"status": "ok", "machine_error_code": "OK"},
            "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
        }
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            self.assertEqual(command[-1], "-")
            self.assertEqual(kwargs.get("input"), "Reply with exactly MAIN_WEB_OK.")
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            self.assertEqual(env.get("OPENAI_API_KEY"), "sk-test-secret-value")  # type: ignore[union-attr]
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("MAIN_WEB_OK\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"type": "done"}), stderr="")

        with mock.patch("wild_boar_proxy.operator_surface.subprocess.run", side_effect=fake_run):
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
        self.assertNotIn("sk-test-secret-value", json.dumps(result))

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
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
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
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"type": "done"}), stderr="")

        try:
            with mock.patch("wild_boar_proxy.operator_surface.subprocess.run", side_effect=fake_run):
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


if __name__ == "__main__":
    unittest.main()
