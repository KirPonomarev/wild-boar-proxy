# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R64 HTTP integration for the production workflow control routes."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from wild_boar_proxy import actor_registry
from wild_boar_proxy import api_transport_adapter
from wild_boar_proxy import web_design_live_server as live_server
from wild_boar_proxy import web_workflow_control as wwc
from wild_boar_proxy.deepseek_route_profile import build_deepseek_route_definition
from wild_boar_proxy.external_models import routes as external_routes
from wild_boar_proxy.kimi_glm_provider_slices import build_kimi_route_definition
from wild_boar_proxy.web_route_table import EFFECT_MUTATE, EFFECT_READ
from wild_boar_proxy.web_token import create_in_memory_web_token


def _state(root: Path) -> wwc.WorkflowControlState:
    deepseek = build_deepseek_route_definition()
    kimi = build_kimi_route_definition()
    for route in (deepseek, kimi):
        route["auth"] = {"type": "none"}
        route["enabled"] = True
    external_root = root / "external-models"
    external_root.mkdir(parents=True)
    external_routes.write_routes_file(
        external_root / "routes.json",
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
        routes_file=external_root / "routes.json",
        external_models_dir=external_root,
        managed_dir=root / "managed",
    )
    return wwc.WorkflowControlState(
        registry_document=registry,
        adapter=adapter,
        lease_root=root / "leases",
        gate_facts={
            "status": "ok",
            "machine_error_code": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
            "exit_code": 0,
            "design_gate_earned": True,
            "design_gate_marker": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
        },
    )


class WebWorkflowLiveServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.token = create_in_memory_web_token()
        handler = live_server.build_handler(
            web_token_state=self.token,
            workflow_control_state=_state(Path(self.temp.name)),
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def _request(self, method: str, path: str, payload: dict | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Host": f"127.0.0.1:{self.server.server_port}"}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers.update(
                {
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{self.server.server_port}",
                    "Authorization": f"Bearer {self.token.token}",
                    "X-WBP-CSRF": self.token.csrf_token,
                }
            )
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        packet = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, packet

    def test_routes_are_centrally_registered_with_declared_effects(self) -> None:
        for path in ("/api/workflow/gate", "/api/workflow/status", "/api/workflow/history"):
            route = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("GET", path)
            self.assertIsNotNone(route)
            self.assertEqual(route.effect, EFFECT_READ)
        route = live_server.WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("POST", "/api/workflow/run")
        self.assertIsNotNone(route)
        self.assertEqual(route.effect, EFFECT_MUTATE)
        self.assertTrue(route.auth_required)

    def test_status_run_and_history_use_one_server_owned_state(self) -> None:
        status_code, status = self._request("GET", "/api/workflow/status")
        self.assertEqual(status_code, 200)
        self.assertEqual(status["registry"]["api_slot_count"], 2)

        payload = {
            "execution_mode": "controlled",
            "steps": [
                {"step_request_id": "s1", "alias": "DIP", "prompt": "first"},
                {
                    "step_request_id": "s2",
                    "alias": "Kimi",
                    "prompt": "second",
                    "context_policy": "continue",
                },
            ],
        }
        run_code, run = self._request("POST", "/api/workflow/run", payload)
        self.assertEqual(run_code, 200)
        self.assertEqual(run["status"], "ok", run)
        self.assertEqual(run["dispatched_steps"], 2)

        _, history = self._request("GET", "/api/workflow/history")
        self.assertEqual(len(history["history"]), 1)
        self.assertEqual(history["history"][0]["workflow_run_id"], run["workflow_run_id"])

    def test_post_still_uses_central_token_and_csrf_ingress(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(
            "POST",
            "/api/workflow/run",
            body=json.dumps({"execution_mode": "controlled", "steps": []}),
            headers={
                "Host": f"127.0.0.1:{self.server.server_port}",
                "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.server.server_port}",
            },
        )
        response = connection.getresponse()
        packet = json.loads(response.read().decode("utf-8"))
        connection.close()
        self.assertEqual(response.status, 401)
        self.assertEqual(packet["machine_error_code"], "WEB_INGRESS_WEB_TOKEN_REJECTED")


if __name__ == "__main__":
    unittest.main()
