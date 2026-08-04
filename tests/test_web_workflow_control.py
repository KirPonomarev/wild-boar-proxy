# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B14: web workflow control surface tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import web_workflow_control as wwc
from wild_boar_proxy.core import packets as command_packets
from wild_boar_proxy.web_rate_limit import WebPostRateLimiter
from wild_boar_proxy.web_token import WebTokenState, create_in_memory_web_token

GATE_FACTS = {
    "completed_stages": [
        "B00_BASELINE_ADMISSION_REPAIR",
        "B01_ACTOR_ADR_AND_SPIKES",
        "B02_ACTOR_SCHEMA_V2_AND_MIGRATION",
        "B03_TRANSPORT_AND_EVIDENCE_STATE_MACHINE",
        "B04_THREAD_CONTEXT_LEDGER_V2",
        "B05_DISPATCHER_ASSIGNMENTS_PERMISSIONS_DIAGNOSTICS",
        "B06_LEGACY_SURFACE_AND_EVIDENCE_MATRIX_REGRESSION",
        "B07_CODE_MULTI_API_CORE",
        "B08_CODE_QWEN_API",
        "B09_ONE_SHOT_CLI_RUNTIME",
        "B10_CODE_QWEN_ONE_SHOT_CLI",
        "B11_CODE_KIMI_ONE_SHOT_CLI",
        "B12_ADMISSION_GLM_CLI_API_ONLY",
        "B13_SEQUENTIAL_WORKFLOW_RUNNER",
        "B13G_EXECUTION_CORE_DESIGN_GATE",
    ],
    "evidence_index_references": 15,
    "full_suite_passed": 4867,
    "main_head": "f60ae261b4e82f9263a9b3fb5a6ac95ebf8b9aee",
}

RUN_PAYLOAD = {
    "dispatch_mode": "controlled_fake",
    "steps": [
        {
            "step_request_id": "w1",
            "provider": "deepseek",
            "prompt": "first",
            "context_policy": "fresh",
        },
        {
            "step_request_id": "w2",
            "provider": "qwen",
            "prompt": "second",
            "context_policy": "continue",
        },
    ],
}


def _csrf_headers(token_state: WebTokenState) -> dict[str, str]:
    return {
        "x-wbp-token": token_state.token,
        "X-WBP-CSRF": token_state.csrf_token,
        "origin": "http://127.0.0.1:8080",
        "host": "127.0.0.1:8080",
    }


class WebWorkflowControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.managed = Path(self.temp_dir.name)
        self.token_state = create_in_memory_web_token()
        self.rate_limiter = WebPostRateLimiter(limit_per_second=100)
        self.state = wwc.WorkflowControlState()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _handle(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
        client_ip: str = "127.0.0.1",
    ) -> dict:
        return wwc.handle_workflow_control_request(
            state=self.state,
            token_state=self.token_state,
            rate_limiter=self.rate_limiter,
            method=method,
            path=path,
            headers=headers or {},
            body=json.dumps(body).encode("utf-8") if body is not None else None,
            client_ip=client_ip,
            server_port=8080,
        )

    def _assert_strict_packet(self, packet: dict) -> None:
        violations = command_packets.inspect_command_packet_semantics(packet)
        self.assertEqual(violations, [])

    def test_gate_endpoint_returns_packet(self) -> None:
        """Gate endpoint returns a strict packet with the gate verdict
        (earned or not, depending on git state)."""
        packet = self._handle("GET", "/api/workflow/gate")
        self.assertIn(packet["status"], {"ok", "error"})
        self.assertIn("design_gate_earned", packet)
        self.assertIn("design_gate_marker", packet)
        self._assert_strict_packet(packet)

    def test_history_endpoint_is_bounded(self) -> None:
        for _ in range(3):
            packet = self._handle(
                "POST", "/api/workflow/run", body=RUN_PAYLOAD, headers=_csrf_headers(self.token_state)
            )
            self.assertEqual(packet["status"], "ok", packet)
        history = self._handle("GET", "/api/workflow/history")
        self.assertEqual(history["status"], "ok")
        self.assertEqual(len(history["history"]), 3)
        run_ids = {entry["workflow_run_id"] for entry in history["history"]}
        self.assertEqual(len(run_ids), 3)
        self._assert_strict_packet(history)

    def test_run_requires_token(self) -> None:
        packet = self._handle("POST", "/api/workflow/run", body=RUN_PAYLOAD, headers={})
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wwc.WC_UNAUTHORIZED)
        self._assert_strict_packet(packet)

    def test_run_requires_csrf(self) -> None:
        headers = {
            "x-wbp-token": self.token_state.token,
            "origin": "http://127.0.0.1:8080",
            "host": "127.0.0.1:8080",
        }
        packet = self._handle("POST", "/api/workflow/run", body=RUN_PAYLOAD, headers=headers)
        self.assertEqual(packet["machine_error_code"], wwc.WC_CSRF_INVALID)
        self._assert_strict_packet(packet)

    def test_run_rejects_non_loopback_client(self) -> None:
        packet = self._handle(
            "POST",
            "/api/workflow/run",
            body=RUN_PAYLOAD,
            headers=_csrf_headers(self.token_state),
            client_ip="192.168.1.10",
        )
        self.assertEqual(packet["machine_error_code"], wwc.WC_LOOPBACK_DENIED)
        self._assert_strict_packet(packet)

    def test_run_rejects_bad_origin(self) -> None:
        headers = {
            "x-wbp-token": self.token_state.token,
            "X-WBP-CSRF": self.token_state.csrf_token,
            "origin": "https://evil.example",
            "host": "127.0.0.1:8080",
        }
        packet = self._handle("POST", "/api/workflow/run", body=RUN_PAYLOAD, headers=headers)
        self.assertEqual(packet["machine_error_code"], wwc.WC_ORIGIN_DENIED)
        self._assert_strict_packet(packet)

    def test_run_rejects_live_dispatch(self) -> None:
        payload = dict(RUN_PAYLOAD, dispatch_mode="live")
        packet = self._handle(
            "POST", "/api/workflow/run", body=payload, headers=_csrf_headers(self.token_state)
        )
        self.assertEqual(
            packet["machine_error_code"], wwc.WC_LIVE_DISPATCH_NOT_IMPLEMENTED
        )
        self._assert_strict_packet(packet)

    def test_run_executes_steps_and_records_history(self) -> None:
        packet = self._handle(
            "POST", "/api/workflow/run", body=RUN_PAYLOAD, headers=_csrf_headers(self.token_state)
        )
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["all_steps_delivered"])
        self.assertEqual(packet["dispatched_steps"], 2)
        self.assertEqual(packet["dispatch_mode"], "controlled_fake")
        self.assertEqual(len(packet["receipts"]), 2)
        self._assert_strict_packet(packet)

        status = self._handle("GET", "/api/workflow/status")
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["writer"]["status"], "free")
        self.assertEqual(status["dispatch_modes_supported"], ["controlled_fake"])
        self._assert_strict_packet(status)

    def test_writer_lock_is_single_writer(self) -> None:
        lock = wwc.WorkflowWriterLock()
        first = lock.acquire("a")
        self.assertEqual(first["status"], "ok")
        second = lock.acquire("b")
        self.assertEqual(second["status"], "blocked")
        self.assertEqual(second["holder"], "a")
        status = lock.status()
        self.assertEqual(status["status"], "held")
        self.assertEqual(status["holder"], "a")
        # wrong fencing token cannot release
        denied = lock.release(fencing_token="wrong")
        self.assertEqual(denied["status"], "blocked")
        ok = lock.release(fencing_token=first["fencing_token"])
        self.assertTrue(ok["released"])
        self.assertEqual(lock.status()["status"], "free")

    def test_rate_limit_applies_to_posts(self) -> None:
        limiter = WebPostRateLimiter(limit_per_second=2)
        results = []
        for _ in range(3):
            results.append(
                wwc.handle_workflow_control_request(
                    state=self.state,
                    token_state=self.token_state,
                    rate_limiter=limiter,
                    method="POST",
                    path="/api/workflow/run",
                    headers=_csrf_headers(self.token_state),
                    body=json.dumps(RUN_PAYLOAD).encode("utf-8"),
                    client_ip="127.0.0.1",
                    server_port=0,
                )
            )
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[1]["status"], "ok")
        self.assertEqual(results[2]["machine_error_code"], wwc.WC_RATE_LIMITED)

    def test_unknown_path_fails_closed(self) -> None:
        packet = self._handle("GET", "/api/workflow/nope")
        self.assertEqual(packet["machine_error_code"], wwc.WC_UNKNOWN_PATH)
        self._assert_strict_packet(packet)

    def test_secret_values_never_echoed(self) -> None:
        payload = {
            "dispatch_mode": "controlled_fake",
            "steps": [
                {
                    "step_request_id": "s1",
                    "provider": "deepseek",
                    "prompt": "handle sk-ant-secret-abc123 and DASHSCOPE_API_KEY=xyz",
                }
            ],
        }
        packet = self._handle(
            "POST", "/api/workflow/run", body=payload, headers=_csrf_headers(self.token_state)
        )
        self.assertEqual(packet["status"], "ok")
        body_text = json.dumps(packet)
        self.assertNotIn("sk-ant-secret-abc123", body_text)
        self.assertNotIn("xyz", body_text)

    def test_history_bounded(self) -> None:
        state = wwc.WorkflowControlState(gate_facts=GATE_FACTS, )
        history = wwc.WorkflowRunHistory(max_entries=2)
        for index in range(5):
            history.append({"workflow_run_id": f"run-{index}"})
        entries = history.list()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["workflow_run_id"], "run-3")
        self.assertEqual(entries[1]["workflow_run_id"], "run-4")


if __name__ == "__main__":
    unittest.main()
