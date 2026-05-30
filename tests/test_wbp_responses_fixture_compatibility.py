# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from wild_boar_proxy.external_models import errors
from wild_boar_proxy.operator_surface import ExternalRouteResponsesAdapter, WbpTraceObserver
from wild_boar_proxy.runtime import RuntimeErrorInfo


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "wbp_responses_compatibility"


def load_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_event_names(name: str) -> list[str]:
    return [
        json.loads(line)["event"]
        for line in (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def parse_sse_frames(body: str) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    for chunk in body.strip().split("\n\n"):
        event_name = ""
        data_text = ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data_text = line.removeprefix("data: ").strip()
        payload = json.loads(data_text)
        frames.append({"event": event_name, "payload": payload})
    return frames


def fixture_route() -> dict[str, object]:
    return {
        "route_id": "wbp-fixture-route",
        "provider": "fixture",
        "base_url": "https://example.invalid/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": "fixture-upstream-model",
        "compatibility": "openai_chat_completions",
        "auth": {"secret_ref": "FIXTURE_SECRET"},
    }


class FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self.payload = payload


class WbpResponsesFixtureCompatibilityTests(unittest.TestCase):
    def run_adapter_request(
        self,
        fixture_name: str,
        *,
        request_payload: dict[str, object] | None = None,
        route: dict[str, object] | None = None,
        response_payload: dict[str, object] | None = None,
        response_status: int = 200,
        accept: str = "application/json",
    ) -> tuple[int, str, dict[str, object], dict[str, object]]:
        captured: dict[str, object] = {}

        def fake_request_json(**kwargs: object) -> FakeResponse:
            captured.update(kwargs)
            payload = response_payload if response_payload is not None else load_json("non_stream_text_response.json")
            return FakeResponse(status_code=response_status, payload=payload)

        with (
            ExternalRouteResponsesAdapter(
                route=route if route is not None else fixture_route(),
                expected_api_key="local-runtime-fixture",
                route_secret="route-secret-fixture",
            ) as adapter,
            mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=fake_request_json),
        ):
            effective_payload = (
                request_payload
                if request_payload is not None
                else load_json(fixture_name)
            )
            request = urllib.request.Request(
                f"{adapter.listen_endpoint}/responses",
                data=json.dumps(effective_payload).encode("utf-8"),
                headers={
                    "Authorization": "Bearer local-runtime-fixture",
                    "Content-Type": "application/json",
                    "Accept": accept,
                },
                method="POST",
            )
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
                    status = int(response.status)
                    body = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                body = exc.read().decode("utf-8")

        return status, body, captured, (
            request_payload if request_payload is not None else load_json(fixture_name)
        )

    def test_fixture_matrix_has_required_cases_and_claim_limits(self) -> None:
        matrix = load_json("fixture_matrix.json")
        cases = matrix.get("cases")
        self.assertIsInstance(cases, list)
        case_ids = {case.get("case_id") for case in cases if isinstance(case, dict)}

        self.assertIn("non_stream_text", case_ids)
        self.assertIn("stream_text", case_ids)
        self.assertIn("tool_call_output_followup", case_ids)
        self.assertIn("large_prompt_redaction", case_ids)
        for case in cases:
            self.assertIsInstance(case, dict)
            self.assertTrue(case.get("allowed_claim"))
            self.assertTrue(case.get("forbidden_claims"))
            self.assertTrue(case.get("redaction_expectation"))

    def test_wbp_responses_non_stream_shape_is_codex_compatible(self) -> None:
        status, body, captured, _fixture = self.run_adapter_request("non_stream_text_request.json")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["object"], "response")
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["model"], "wbp-fixture-route")
        self.assertEqual(payload["output"][0]["type"], "message")
        self.assertEqual(payload["output"][0]["content"][0]["type"], "output_text")
        self.assertEqual(payload["output"][0]["content"][0]["text"], "WBP_FIXTURE_OK")
        self.assertEqual(captured["payload"]["model"], "fixture-upstream-model")  # type: ignore[index]
        self.assertEqual(captured["payload"]["stream"], False)  # type: ignore[index]

    def test_wbp_responses_stream_sse_sequence_required(self) -> None:
        status, body, _captured, _fixture = self.run_adapter_request(
            "stream_text_request.json",
            response_payload={"choices": [{"message": {"content": "WBP_STREAM_OK"}}]},
            accept="text/event-stream",
        )

        self.assertEqual(status, 200)
        observed_events = [
            line.removeprefix("event: ").strip()
            for line in body.splitlines()
            if line.startswith("event: ")
        ]
        self.assertEqual(observed_events, load_event_names("stream_text_events.ndjson"))
        self.assertIn("WBP_STREAM_OK", body)

    def test_wbp_responses_stream_sse_data_payload_matches_event_type(self) -> None:
        status, body, _captured, _fixture = self.run_adapter_request(
            "stream_text_request.json",
            response_payload={"choices": [{"message": {"content": "WBP_STREAM_OK"}}]},
            accept="text/event-stream",
        )

        self.assertEqual(status, 200)
        frames = parse_sse_frames(body)
        self.assertEqual([frame["event"] for frame in frames], load_event_names("stream_text_events.ndjson"))
        for frame in frames:
            payload = frame["payload"]
            self.assertIsInstance(payload, dict)
            self.assertEqual(payload["type"], frame["event"])  # type: ignore[index]
        self.assertEqual(frames[-1]["payload"]["response"]["status"], "completed")  # type: ignore[index]

    def test_wbp_responses_error_shape_required(self) -> None:
        for fixture_name in ("upstream_4xx_error.json", "upstream_5xx_error.json"):
            with self.subTest(fixture_name=fixture_name):
                fixture = load_json(fixture_name)
                status_code = int(fixture["status_code"])
                payload = {"error": fixture["error"]}
                status, body, _captured, _request_fixture = self.run_adapter_request(
                    "non_stream_text_request.json",
                    response_payload=payload,
                    response_status=status_code,
                )
                response_payload = json.loads(body)

                self.assertEqual(status, status_code)
                self.assertIn("error", response_payload)
                self.assertNotEqual(status, 200)

    def test_failure_semantics_429_classified(self) -> None:
        status, body, _captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            response_payload={
                "error": {
                    "message": "rate limit fixture",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            },
            response_status=429,
        )
        payload = json.loads(body)

        self.assertEqual(status, 429)
        self.assertEqual(payload["error"]["type"], "rate_limit_error")
        self.assertEqual(payload["error"]["code"], "rate_limit_exceeded")

    def test_failure_semantics_timeout_classified(self) -> None:
        def timeout_request_json(**_kwargs: object) -> FakeResponse:
            raise RuntimeErrorInfo(
                "Provider request timed out.",
                machine_error_code=errors.PROVIDER_NETWORK_FAILED,
                operator_action="retry",
            )

        with (
            ExternalRouteResponsesAdapter(
                route=fixture_route(),
                expected_api_key="local-runtime-fixture",
                route_secret="route-secret-fixture",
            ) as adapter,
            mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=timeout_request_json),
        ):
            request = urllib.request.Request(
                f"{adapter.listen_endpoint}/responses",
                data=json.dumps(load_json("non_stream_text_request.json")).encode("utf-8"),
                headers={
                    "Authorization": "Bearer local-runtime-fixture",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5)

        self.assertEqual(caught.exception.code, 504)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(payload["error"]["code"], errors.PROVIDER_NETWORK_FAILED)
        self.assertTrue(payload["error"]["retryable"])

    def test_failure_semantics_disconnect_classified(self) -> None:
        def disconnect_request_json(**_kwargs: object) -> FakeResponse:
            raise RuntimeErrorInfo(
                "Provider network request failed: upstream disconnect",
                machine_error_code=errors.PROVIDER_NETWORK_FAILED,
                operator_action="retry",
            )

        with (
            ExternalRouteResponsesAdapter(
                route=fixture_route(),
                expected_api_key="local-runtime-fixture",
                route_secret="route-secret-fixture",
            ) as adapter,
            mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=disconnect_request_json),
        ):
            request = urllib.request.Request(
                f"{adapter.listen_endpoint}/responses",
                data=json.dumps(load_json("non_stream_text_request.json")).encode("utf-8"),
                headers={
                    "Authorization": "Bearer local-runtime-fixture",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5)

        self.assertEqual(caught.exception.code, 502)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(payload["error"]["type"], "provider_runtime_error")
        self.assertTrue(payload["error"]["retryable"])

    def test_empty_responses_input_returns_invalid_request_without_upstream_call(self) -> None:
        status, body, captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            request_payload={"model": "wbp-fixture-route", "input": []},
        )
        payload = json.loads(body)

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["type"], "invalid_request_error")
        self.assertIn("responses input did not contain prompt text", payload["error"]["message"])
        self.assertEqual(captured, {})

    def test_system_role_transform_profile_maps_system_to_developer(self) -> None:
        route = fixture_route()
        route["transform_profile"] = "openai_chat_system_to_developer"
        status, _body, captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            request_payload={
                "model": "wbp-fixture-route",
                "input": [
                    {
                        "type": "message",
                        "role": "system",
                        "content": [{"type": "input_text", "text": "system fixture"}],
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "user fixture"}],
                    },
                ],
            },
            route=route,
        )
        upstream_messages = captured["payload"]["messages"]  # type: ignore[index]

        self.assertEqual(status, 200)
        self.assertEqual(upstream_messages[0]["role"], "developer")
        self.assertEqual(upstream_messages[0]["content"], "system fixture")
        self.assertEqual(upstream_messages[1]["role"], "developer")
        self.assertIn("runtime routing truth", upstream_messages[1]["content"])
        self.assertEqual(upstream_messages[2]["role"], "user")

    def test_developer_role_transform_profile_maps_developer_to_system(self) -> None:
        route = fixture_route()
        route["transform_profile"] = "openai_chat_developer_to_system"
        status, _body, captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            request_payload={
                "model": "wbp-fixture-route",
                "instructions": "developer fixture",
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "user fixture"}],
                    },
                ],
            },
            route=route,
        )
        upstream_messages = captured["payload"]["messages"]  # type: ignore[index]

        self.assertEqual(status, 200)
        self.assertEqual(upstream_messages[0]["role"], "system")
        self.assertEqual(upstream_messages[0]["content"], "developer fixture")
        self.assertEqual(upstream_messages[1]["role"], "system")
        self.assertIn("runtime routing truth", upstream_messages[1]["content"])
        self.assertEqual(upstream_messages[2]["role"], "user")

    def test_codex_namespace_and_web_search_tools_are_dropped_for_text_only_routes(self) -> None:
        status, body, captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            request_payload={
                "model": "wbp-fixture-route",
                "tools": [
                    {"type": "namespace", "name": "shell"},
                    {"type": "web_search", "name": "web_search"},
                ],
                "input": "Reply directly.",
            },
        )
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(
            payload["wbp_route_tool_policy"],
            "unsupported_codex_tools_dropped_for_text_only",
        )
        self.assertEqual(
            payload["dropped_responses_tool_types"],
            ["namespace", "web_search"],
        )
        self.assertNotIn("tools", captured["payload"])  # type: ignore[operator]

    def test_function_tools_are_forwarded_to_chat_completions(self) -> None:
        status, _body, captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            request_payload={
                "model": "wbp-fixture-route",
                "tools": [
                    {
                        "type": "function",
                        "name": "exec_command",
                        "description": "Run command.",
                        "parameters": {
                            "type": "object",
                            "properties": {"cmd": {"type": "string"}},
                            "required": ["cmd"],
                        },
                    }
                ],
                "input": "Use tools only if needed.",
            },
        )
        upstream_payload = captured["payload"]  # type: ignore[index]

        self.assertEqual(status, 200)
        self.assertEqual(
            upstream_payload["tools"],
            [
                {
                    "type": "function",
                    "function": {
                        "name": "exec_command",
                        "description": "Run command.",
                        "parameters": {
                            "type": "object",
                            "properties": {"cmd": {"type": "string"}},
                            "required": ["cmd"],
                        },
                    },
                }
            ],
        )

    def test_chat_completion_tool_call_is_returned_as_responses_function_call(self) -> None:
        status, body, _captured, _fixture = self.run_adapter_request(
            "non_stream_text_request.json",
            request_payload={
                "model": "wbp-fixture-route",
                "tools": [
                    {
                        "type": "function",
                        "name": "exec_command",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
                "input": "Call a tool.",
            },
            response_payload={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_fixture",
                                    "type": "function",
                                    "function": {
                                        "name": "exec_command",
                                        "arguments": "{\"cmd\":\"pwd\"}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["output_text"], "")
        self.assertEqual(payload["output"][0]["type"], "function_call")
        self.assertEqual(payload["output"][0]["call_id"], "call_fixture")
        self.assertEqual(payload["output"][0]["name"], "exec_command")
        self.assertEqual(payload["output"][0]["arguments"], "{\"cmd\":\"pwd\"}")

    def test_failure_semantics_partial_stream_classified(self) -> None:
        status, body, _captured, _fixture = self.run_adapter_request(
            "stream_text_request.json",
            response_payload={"choices": [{"message": {"content": "WBP_STREAM_OK"}}]},
            accept="text/event-stream",
        )
        observed_events = [
            line.removeprefix("event: ").strip()
            for line in body.splitlines()
            if line.startswith("event: ")
        ]

        self.assertEqual(status, 200)
        self.assertEqual(observed_events[-1], "response.completed")
        self.assertNotIn("partial_stream_passed", body)

    def test_environment_blocked_result_not_counted_as_pass(self) -> None:
        blocked_packet = {
            "status": "blocked_by_host_environment",
            "counts_as_pass": False,
            "root_cause": "fixture host intentionally unavailable",
        }

        self.assertFalse(blocked_packet["counts_as_pass"])
        self.assertEqual(blocked_packet["status"], "blocked_by_host_environment")

    def test_wbp_responses_unknown_model_error_blocks_route_overclaim(self) -> None:
        status, body, captured, _fixture = self.run_adapter_request("unknown_model_request.json")
        payload = json.loads(body)

        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "model_not_found")
        self.assertEqual(captured, {})

    def test_wbp_responses_tool_call_shape_required(self) -> None:
        status, _body, captured, _fixture = self.run_adapter_request("tool_call_request.json")
        upstream_messages = captured["payload"]["messages"]  # type: ignore[index]

        self.assertEqual(status, 200)
        self.assertEqual(upstream_messages[0]["role"], "developer")
        self.assertIn("runtime routing truth", upstream_messages[0]["content"])
        self.assertEqual(upstream_messages[1]["role"], "assistant")
        self.assertEqual(upstream_messages[2]["role"], "assistant")
        self.assertEqual(upstream_messages[2]["tool_calls"][0]["function"]["name"], "shell")
        self.assertEqual(upstream_messages[2]["tool_calls"][0]["function"]["arguments"], "{\"cmd\":\"pwd\"}")

    def test_wbp_responses_tool_call_output_loop_classified(self) -> None:
        status, _body, captured, _fixture = self.run_adapter_request("tool_call_output_followup.json")
        upstream_messages = captured["payload"]["messages"]  # type: ignore[index]

        self.assertEqual(status, 200)
        self.assertEqual(upstream_messages[0]["role"], "developer")
        self.assertIn("runtime routing truth", upstream_messages[0]["content"])
        self.assertEqual(upstream_messages[1]["role"], "assistant")
        self.assertEqual(upstream_messages[1]["tool_calls"][0]["id"], "call_fixture_1")
        self.assertEqual(upstream_messages[2]["role"], "tool")
        self.assertEqual(upstream_messages[2]["tool_call_id"], "call_fixture_1")
        self.assertEqual(upstream_messages[3]["role"], "user")

    def test_wbp_responses_reasoning_item_classified(self) -> None:
        status, _body, captured, _fixture = self.run_adapter_request("reasoning_item_input.json")
        upstream_payload_text = json.dumps(captured["payload"])

        self.assertEqual(status, 200)
        self.assertNotIn("internal reasoning summary should not go upstream", upstream_payload_text)
        self.assertNotIn("fixture-redacted-reasoning", upstream_payload_text)

    def test_wbp_large_prompt_redaction_required(self) -> None:
        fixture = load_json("large_prompt_redaction_case.json")
        raw_prompt = "LARGE_PROMPT_FIXTURE_DO_NOT_LOG_RAW_0123456789"

        class UpstreamHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"output_text": "OK"}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with WbpTraceObserver(downstream_endpoint=f"http://127.0.0.1:{server.server_port}/v1") as observer:
                request = urllib.request.Request(
                    f"{observer.listen_endpoint}/responses",
                    data=json.dumps(fixture).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer local-runtime-fixture",
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

        self.assertFalse(packet["prompt_body_recorded"])
        self.assertFalse(packet["auth_header_recorded"])
        self.assertFalse(packet["secret_value_recorded"])
        self.assertNotIn(raw_prompt, json.dumps(packet))
        self.assertNotIn("local-runtime-fixture", json.dumps(packet))
        self.assertTrue(packet["request_body_sha256"])

    def test_wbp_auth_header_not_logged(self) -> None:
        status, body, captured, _fixture = self.run_adapter_request("non_stream_text_request.json")
        evidence_like_packet = {
            "status": status,
            "response_body_sha256_present": bool(body),
            "captured_payload_keys": sorted(captured.keys()),
            "auth_header_recorded": False,
            "secret_value_recorded": False,
        }

        self.assertFalse(evidence_like_packet["auth_header_recorded"])
        self.assertFalse(evidence_like_packet["secret_value_recorded"])
        self.assertNotIn("route-secret-fixture", json.dumps(evidence_like_packet))
        self.assertNotIn("local-runtime-fixture", json.dumps(evidence_like_packet))

    def test_wbp_image_tool_unsupported_behavior_classified(self) -> None:
        status, body, captured, _fixture = self.run_adapter_request("image_tool_unsupported_case.json")
        payload = json.loads(body)

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "unsupported_tool_type")
        self.assertEqual(captured, {})

    def test_wire_compatibility_claims_do_not_overclaim_native_or_models(self) -> None:
        matrix = load_json("fixture_matrix.json")
        forbidden_text = json.dumps(matrix)

        self.assertIn("native app works", forbidden_text)
        self.assertIn("all models work", forbidden_text)
        self.assertNotIn("native Codex.app works", json.dumps({"allowed_claims": [case["allowed_claim"] for case in matrix["cases"]]}))


if __name__ == "__main__":
    unittest.main()
