# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R64: registry-bound web workflow control tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wild_boar_proxy import actor_registry
from wild_boar_proxy import api_transport_adapter
from wild_boar_proxy import web_workflow_control as wwc
from wild_boar_proxy import workflow_api_dispatch as wad
from wild_boar_proxy.core import packets as command_packets
from wild_boar_proxy.deepseek_route_profile import build_deepseek_route_definition
from wild_boar_proxy.external_models import routes as external_routes
from wild_boar_proxy.kimi_glm_provider_slices import build_kimi_route_definition
from wild_boar_proxy.web_rate_limit import WebPostRateLimiter
from wild_boar_proxy.web_token import WebTokenState, create_in_memory_web_token

GATE_FACTS = {
    "status": "ok",
    "machine_error_code": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
    "exit_code": 0,
    "design_gate_earned": True,
    "design_gate_marker": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
}

RUN_PAYLOAD = {
    "execution_mode": "controlled",
    "steps": [
        {
            "step_request_id": "w1",
            "alias": "DIP",
            "prompt": "first",
            "context_policy": "fresh",
        },
        {
            "step_request_id": "w2",
            "alias": "Kimi",
            "prompt": "second",
            "context_policy": "continue",
        },
    ],
}


def _fixtures(root: Path):
    deepseek = build_deepseek_route_definition()
    kimi = build_kimi_route_definition()
    for route in (deepseek, kimi):
        route["auth"] = {"type": "none"}
        route["enabled"] = True
    root.mkdir(parents=True, exist_ok=True)
    external_routes.write_routes_file(
        root / "routes.json",
        {"schema_version": 1, "routes": [deepseek, kimi]},
    )
    registry = actor_registry.build_actor_registry_document(
        [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex"],
                "lane": "primary_chatgpt",
                "model_id": "gpt-5.5",
                "enabled": True,
                "allowed_actions": [],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "researcher",
                "aliases": ["DIP"],
                "lane": "api_route",
                "route_id": deepseek["route_id"],
                "enabled": True,
                "allowed_actions": [],
            },
            {
                "agent_id": "kimi",
                "display_name": "Kimi",
                "role": "reviewer",
                "aliases": ["Kimi"],
                "lane": "api_route",
                "route_id": kimi["route_id"],
                "enabled": True,
                "allowed_actions": [],
            },
        ],
        route_records=[deepseek, kimi],
    )
    adapter = api_transport_adapter.ApiTransportAdapter(
        routes_file=root / "routes.json",
        external_models_dir=root,
        managed_dir=root / "managed",
    )
    return registry, adapter


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
        self.registry, self.adapter = _fixtures(self.managed / "external-models")
        self.token_state = create_in_memory_web_token()
        self.rate_limiter = WebPostRateLimiter(limit_per_second=100)
        self.state = wwc.WorkflowControlState(
            registry_document=self.registry,
            adapter=self.adapter,
            lease_root=self.managed / "leases",
            gate_facts=GATE_FACTS,
        )

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
        self.assertEqual(command_packets.inspect_command_packet_semantics(packet), [])

    def test_gate_and_status_expose_public_server_truth(self) -> None:
        gate = self._handle("GET", "/api/workflow/gate")
        self.assertTrue(gate["design_gate_earned"])
        self._assert_strict_packet(gate)

        status = self._handle("GET", "/api/workflow/status")
        self.assertEqual(status["registry"]["api_slot_count"], 2)
        self.assertEqual([item["primary_alias"] for item in status["actor_slots"]], ["DIP", "Kimi"])
        self.assertEqual(status["dispatch_modes_admitted"], ["controlled"])
        self.assertFalse(status["browser_can_supply_identity_authority"])
        self.assertFalse(status["browser_can_authorize_live_dispatch"])
        self.assertFalse(status["writer"]["fencing_token_exposed"])
        self.assertNotIn("fencing_token", status["writer"])
        self._assert_strict_packet(status)

    def test_controlled_run_uses_registry_adapter_and_records_receipts(self) -> None:
        calls = []
        original = self.adapter.dispatch

        def record(request, plan, **kwargs):
            calls.append((request, plan, kwargs))
            return original(request, plan, **kwargs)

        with patch.object(self.adapter, "dispatch", side_effect=record):
            packet = self._handle(
                "POST", "/api/workflow/run", body=RUN_PAYLOAD,
                headers=_csrf_headers(self.token_state),
            )
        self.assertEqual(packet["status"], "ok", packet)
        self.assertTrue(packet["all_steps_delivered"])
        self.assertEqual(packet["dispatched_steps"], 2)
        self.assertEqual(packet["execution_mode"], "controlled")
        self.assertEqual(len(packet["receipts"]), 2)
        self.assertTrue(all(call[2]["controlled"] for call in calls))
        self.assertIn(packet["receipts"][0]["output_text"], calls[1][0].text)
        self._assert_strict_packet(packet)

        history = self._handle("GET", "/api/workflow/history")
        self.assertEqual(len(history["history"]), 1)
        self.assertEqual(history["history"][0]["actor_aliases"], ["DIP", "Kimi"])
        self.assertEqual(len(history["history"][0]["receipts"]), 2)
        self._assert_strict_packet(history)

    def test_browser_identity_authority_is_rejected(self) -> None:
        for field, value in (("provider", "deepseek"), ("slot_id", "slot-forged"), ("binding_revision", 99)):
            payload = json.loads(json.dumps(RUN_PAYLOAD))
            payload["steps"][0][field] = value
            packet = self._handle(
                "POST", "/api/workflow/run", body=payload,
                headers=_csrf_headers(self.token_state),
            )
            self.assertEqual(packet["machine_error_code"], wwc.WC_BROWSER_AUTHORITY_FORBIDDEN)

    def test_primary_chatgpt_alias_is_not_dispatched_on_api_lane(self) -> None:
        payload = {
            "execution_mode": "controlled",
            "steps": [{"alias": "Codex", "prompt": "stay native"}],
        }
        with patch.object(self.adapter, "dispatch", side_effect=AssertionError("must not dispatch")):
            packet = self._handle(
                "POST", "/api/workflow/run", body=payload,
                headers=_csrf_headers(self.token_state),
            )
        self.assertEqual(packet["machine_error_code"], wwc.WC_ACTOR_LANE_UNSUPPORTED)

    def test_live_mode_fails_before_credential_probe_without_authorization(self) -> None:
        payload = json.loads(json.dumps(RUN_PAYLOAD))
        payload["execution_mode"] = "live"
        with patch.object(
            self.adapter, "_credential_presence",
            side_effect=AssertionError("credential presence must not be probed"),
        ), patch.object(
            self.adapter, "dispatch",
            side_effect=AssertionError("dispatch must not be attempted"),
        ):
            packet = self._handle(
                "POST", "/api/workflow/run", body=payload,
                headers=_csrf_headers(self.token_state),
            )
        self.assertEqual(packet["machine_error_code"], wad.WAD_LIVE_NOT_AUTHORIZED)
        self.assertFalse(packet["live_provider_proven"])
        self.assertEqual(len(self.state.history.list()), 1)

    def test_authorized_live_mode_preserves_proof(self) -> None:
        state = wwc.WorkflowControlState(
            registry_document=self.registry,
            adapter=self.adapter,
            lease_root=self.managed / "live-leases",
            live_dispatch_authorized=True,
            gate_facts=GATE_FACTS,
        )
        payload = {
            "execution_mode": "live",
            "steps": [{"alias": "DIP", "prompt": "live task"}],
        }

        def live_double(request, plan, **kwargs):
            return {
                "status": "ok",
                "machine_error_code": "DISPATCH_COMPLETE",
                "provider_id": plan["provider_id"],
                "response_text": "live output",
                "dispatch_proven": True,
                "dispatch_attempted": True,
                "response_observed": True,
                "controlled": False,
                "live_provider_called": True,
                "live_provider_proven": True,
                "result": "ok",
            }

        with patch.object(self.adapter, "dispatch", side_effect=live_double):
            packet = wwc.handle_admitted_workflow_request(
                state=state, method="POST", path="/api/workflow/run", payload=payload,
            )
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["live_provider_proven"])
        self.assertFalse(packet["controlled"])

    def test_run_ingress_requires_token_csrf_origin_and_loopback(self) -> None:
        packet = self._handle("POST", "/api/workflow/run", body=RUN_PAYLOAD, headers={})
        self.assertEqual(packet["machine_error_code"], wwc.WC_UNAUTHORIZED)
        no_csrf = {
            "x-wbp-token": self.token_state.token,
            "origin": "http://127.0.0.1:8080",
            "host": "127.0.0.1:8080",
        }
        packet = self._handle("POST", "/api/workflow/run", body=RUN_PAYLOAD, headers=no_csrf)
        self.assertEqual(packet["machine_error_code"], wwc.WC_CSRF_INVALID)
        bad_origin = _csrf_headers(self.token_state)
        bad_origin["origin"] = "https://evil.example"
        packet = self._handle("POST", "/api/workflow/run", body=RUN_PAYLOAD, headers=bad_origin)
        self.assertEqual(packet["machine_error_code"], wwc.WC_ORIGIN_DENIED)
        packet = self._handle(
            "POST", "/api/workflow/run", body=RUN_PAYLOAD,
            headers=_csrf_headers(self.token_state), client_ip="192.168.1.10",
        )
        self.assertEqual(packet["machine_error_code"], wwc.WC_LOOPBACK_DENIED)

    def test_rate_limit_applies_to_posts(self) -> None:
        limiter = WebPostRateLimiter(limit_per_second=1)
        packets = [
            wwc.handle_workflow_control_request(
                state=self.state,
                token_state=self.token_state,
                rate_limiter=limiter,
                method="POST",
                path="/api/workflow/run",
                headers=_csrf_headers(self.token_state),
                body=json.dumps(RUN_PAYLOAD).encode("utf-8"),
                server_port=8080,
            )
            for _ in range(2)
        ]
        self.assertEqual(packets[0]["status"], "ok")
        self.assertEqual(packets[1]["machine_error_code"], wwc.WC_RATE_LIMITED)

    def test_secret_values_never_echoed(self) -> None:
        payload = {
            "execution_mode": "controlled",
            "steps": [{
                "alias": "DIP",
                "prompt": "handle sk-ant-secret-abc123 and DASHSCOPE_API_KEY=xyz",
            }],
        }
        packet = self._handle(
            "POST", "/api/workflow/run", body=payload,
            headers=_csrf_headers(self.token_state),
        )
        rendered = json.dumps(packet)
        self.assertNotIn("sk-ant-secret-abc123", rendered)
        self.assertNotIn("xyz", rendered)

    def test_history_is_bounded_and_unknown_paths_fail_closed(self) -> None:
        history = wwc.WorkflowRunHistory(max_entries=2)
        for index in range(5):
            history.append({"workflow_run_id": f"run-{index}"})
        self.assertEqual(
            [item["workflow_run_id"] for item in history.list()],
            ["run-3", "run-4"],
        )
        packet = self._handle("GET", "/api/workflow/nope")
        self.assertEqual(packet["machine_error_code"], wwc.WC_UNKNOWN_PATH)

    def test_writer_lock_is_single_writer_and_hides_token_publicly(self) -> None:
        lock = wwc.WorkflowWriterLock()
        first = lock.acquire("a")
        second = lock.acquire("b")
        self.assertEqual(second, {"status": "blocked", "holder": "a", "fencing_token": None})
        public = lock.public_status()
        self.assertTrue(public["fencing_token_present"])
        self.assertNotIn("fencing_token", public)
        self.assertEqual(lock.release(fencing_token="wrong")["status"], "blocked")
        self.assertTrue(lock.release(fencing_token=first["fencing_token"])["released"])


if __name__ == "__main__":
    unittest.main()
