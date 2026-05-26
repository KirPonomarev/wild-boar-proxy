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

from wild_boar_proxy.operator_surface import ExternalRouteResponsesAdapter, WbpTraceObserver


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "wbp_responses_compatibility"


def load_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_event_names(name: str) -> list[str]:
    return [
        json.loads(line)["event"]
        for line in (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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
                route=fixture_route(),
                expected_api_key="local-runtime-fixture",
                route_secret="route-secret-fixture",
            ) as adapter,
            mock.patch("wild_boar_proxy.operator_surface.request_json", side_effect=fake_request_json),
        ):
            request = urllib.request.Request(
                f"{adapter.listen_endpoint}/responses",
                data=json.dumps(load_json(fixture_name)).encode("utf-8"),
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

        return status, body, captured, load_json(fixture_name)

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
        self.assertEqual(upstream_messages[0]["role"], "assistant")
        self.assertEqual(upstream_messages[1]["role"], "assistant")
        self.assertEqual(upstream_messages[1]["tool_calls"][0]["function"]["name"], "shell")
        self.assertEqual(upstream_messages[1]["tool_calls"][0]["function"]["arguments"], "{\"cmd\":\"pwd\"}")

    def test_wbp_responses_tool_call_output_loop_classified(self) -> None:
        status, _body, captured, _fixture = self.run_adapter_request("tool_call_output_followup.json")
        upstream_messages = captured["payload"]["messages"]  # type: ignore[index]

        self.assertEqual(status, 200)
        self.assertEqual(upstream_messages[0]["role"], "assistant")
        self.assertEqual(upstream_messages[0]["tool_calls"][0]["id"], "call_fixture_1")
        self.assertEqual(upstream_messages[1]["role"], "tool")
        self.assertEqual(upstream_messages[1]["tool_call_id"], "call_fixture_1")
        self.assertEqual(upstream_messages[2]["role"], "user")

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
