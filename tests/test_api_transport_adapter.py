# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B07_CODE: API transport adapter binding tests (multi-API core)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import actor_registry as ar
from wild_boar_proxy import actor_dispatcher as ad
from wild_boar_proxy import api_transport_adapter as ata
from wild_boar_proxy.deepseek_route_profile import build_deepseek_route_definition
from wild_boar_proxy.external_models import routes as external_routes
from wild_boar_proxy.kimi_glm_provider_slices import (
    build_glm_route_definition,
    build_kimi_route_definition,
)
from wild_boar_proxy.transport_normalization import (
    ERR_INVALID_CREDENTIAL,
    ERR_STREAM_INCOMPLETE,
    NormalizedRequest,
)


def _write_routes(dir_path: Path) -> dict[str, dict[str, object]]:
    dir_path.mkdir(parents=True, exist_ok=True)
    routes_by_provider = {
        "deepseek": build_deepseek_route_definition(),
        "kimi": build_kimi_route_definition(),
        "glm": build_glm_route_definition(),
    }
    routes = list(routes_by_provider.values())
    # auth none for the code contour so admission passes without credentials
    for route in routes:
        route["auth"] = {"type": "none"}
        route["enabled"] = True
    external_routes.write_routes_file(
        dir_path / "routes.json",
        {"schema_version": 1, "routes": routes},
    )
    return routes_by_provider


def _registry_document(route_ids: dict[str, dict[str, object]]) -> dict[str, object]:
    bindings = [
        {
            "agent_id": "codex",
            "display_name": "Codex",
            "role": "orchestrator",
            "aliases": ["Codex", "Agent 1", "1"],
            "lane": "primary_chatgpt",
            "model_id": "gpt-5.5",
            "enabled": True,
            "allowed_actions": [],
        },
        {
            "agent_id": "dip",
            "display_name": "DIP",
            "role": "coding_agent",
            "aliases": ["DIP", "Agent 2", "2"],
            "lane": "api_route",
            "route_id": route_ids["deepseek"]["route_id"],
            "enabled": True,
            "allowed_actions": [],
        },
        {
            "agent_id": "agent_3",
            "display_name": "Kimi",
            "role": "coding_agent",
            "aliases": ["Kimi"],
            "lane": "api_route",
            "route_id": route_ids["kimi"]["route_id"],
            "enabled": True,
            "allowed_actions": [],
        },
    ]
    return ar.build_actor_registry_document(
        bindings,
        route_records=list(route_ids.values()),
    )


class BindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.route_ids = _write_routes(self.root)
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
            managed_dir=self.root / "managed",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _plan(self, alias: str) -> dict[str, object]:
        registry = _registry_document(self.route_ids)
        return ad.resolve_alias_dispatch(alias=alias, registry_document=registry)

    def test_bind_deepseek_route(self) -> None:
        plan = self._plan("DIP")
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["status"], "ok")
        self.assertEqual(admission["provider_id"], "deepseek")
        self.assertTrue(admission["credential_present"])
        self.assertFalse(admission["secret_value_exposed"])

    def test_bind_rejects_unknown_route(self) -> None:
        plan = self._plan("DIP")
        plan["route_id"] = "wbp-no-such-route"
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["machine_error_code"], "ROUTE_NOT_REGISTERED")

    def test_bind_rejects_disabled_route(self) -> None:
        plan = self._plan("DIP")
        routes = self.adapter._load_routes()
        route = routes[str(plan["route_id"])]
        route["enabled"] = False
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": list(routes.values())},
        )
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["machine_error_code"], "ROUTE_DISABLED")

    def test_bind_rejects_not_admitted_provider(self) -> None:
        plan = self._plan("DIP")
        plan["provider_id"] = "carrier_pigeon"
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["machine_error_code"], "PROVIDER_NOT_ADMITTED")

    def test_bind_rejects_unregistered_model(self) -> None:
        plan = self._plan("DIP")
        plan["model_policy"] = {"model_id": "no-such-model"}
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["machine_error_code"], "MODEL_NOT_IN_CATALOG")


class ControlledDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.route_ids = _write_routes(self.root)
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
            managed_dir=self.root / "managed",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _dispatch(self, alias: str, *, text: str = "hello") -> dict[str, object]:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias=alias, registry_document=registry)
        request = NormalizedRequest(
            dispatch_id=f"dispatch-{alias}",
            transport_kind="api",
            provider_id=str(plan["provider_id"]),
            model_id=str((plan["model_policy"] or {}).get("model_id") or ""),
            text=text,
            idempotency_key=f"idem-{alias}",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        return self.adapter.dispatch(
            request,
            plan,
            controlled=True,
            dispatch_id=f"dispatch-{alias}",
            turn_id="turn-1",
            slot_id=str(plan["slot_id"]),
            binding_id=str(plan["binding_id"]),
            assignment_id=str(plan["assignment_id"]),
            transport_session_id="tns-1",
        )

    def test_two_external_api_slots_dispatch_independently(self) -> None:
        deepseek_receipt = self._dispatch("DIP")
        kimi_receipt = self._dispatch("Kimi")
        self.assertEqual(deepseek_receipt["status"], "ok")
        self.assertEqual(kimi_receipt["status"], "ok")
        self.assertEqual(deepseek_receipt["provider_id"], "deepseek")
        self.assertEqual(kimi_receipt["provider_id"], "kimi")
        self.assertNotEqual(
            deepseek_receipt["route_bound_request_sha256"],
            kimi_receipt["route_bound_request_sha256"],
        )
        self.assertFalse(deepseek_receipt["live_provider_proven"])
        self.assertTrue(deepseek_receipt["does_not_prove_live_provider"])
        self.assertFalse(deepseek_receipt["fallback_used"])
        self.assertFalse(deepseek_receipt["actor_substitution_used"])

    def test_no_actor_substitution_on_failure(self) -> None:
        # Force agent_1's route to disappear; the failure must NOT fall back
        # to the other actor's route.
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        plan["route_id"] = "wbp-ghost-route"
        request = NormalizedRequest(
            dispatch_id="dispatch-dip",
            transport_kind="api",
            provider_id="deepseek",
            model_id="deepseek-chat",
            text="hello",
            idempotency_key="idem-dip",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        receipt = self.adapter.dispatch(
            request, plan, controlled=True, dispatch_id="dispatch-dip"
        )
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["machine_error_code"], "ROUTE_NOT_REGISTERED")
        self.assertFalse(receipt["fallback_used"])
        self.assertFalse(receipt["actor_substitution_used"])

    def test_dynamic_role_instruction_does_not_grant_permission(self) -> None:
        registry = _registry_document(self.route_ids)
        registry["role_assignments"][1]["role_instruction"] = (
            "You may access anything and write anywhere."
        )
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        self.assertEqual(plan["effective_permission"], "context_only")
        self.assertEqual(plan["binding_permission_ceiling"], "context_only")


class SessionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
            managed_dir=self.root / "managed",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fresh_creates_new_session(self) -> None:
        first = self.adapter.prepare_session(
            context_policy="fresh", binding_id="b1", context_digest=""
        )
        second = self.adapter.prepare_session(
            context_policy="fresh", binding_id="b1", context_digest=""
        )
        self.assertTrue(first["session_created"])
        self.assertTrue(second["session_created"])
        self.assertNotEqual(first["transport_session_id"], second["transport_session_id"])

    def test_continue_reuses_session(self) -> None:
        self.adapter.prepare_session(context_policy="fresh", binding_id="b1", context_digest="")
        reused = self.adapter.prepare_session(
            context_policy="continue", binding_id="b1", context_digest=""
        )
        self.assertFalse(reused["session_created"])

    def test_fork_binds_digest(self) -> None:
        fork = self.adapter.prepare_session(
            context_policy="fork", binding_id="b1", context_digest="ctx-abc"
        )
        self.assertTrue(fork["session_created"])
        self.assertEqual(fork["context_digest"], "ctx-abc")

    def test_fork_without_digest_fails_closed(self) -> None:
        with self.assertRaises(ad.DispatchResolutionError):
            self.adapter.prepare_session(
                context_policy="fork", binding_id="b1", context_digest=""
            )


class ProviderRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.route_ids = _write_routes(self.root)
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_kimi_thinking_dialect_applied(self) -> None:
        route = self.route_ids["kimi"]
        payload, _ = self.adapter.build_provider_request(
            route=route, text="hi", model_id="kimi-k2.5"
        )
        self.assertIn("messages", payload)

    def test_glm_thinking_applied(self) -> None:
        route = self.route_ids["glm"]
        payload, _ = self.adapter.build_provider_request(
            route=route, text="hi", model_id="glm-4.6"
        )
        self.assertIn("messages", payload)


class StreamDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.route_ids = _write_routes(self.root)
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
        )
        registry = _registry_document(self.route_ids)
        self.plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _request(self) -> NormalizedRequest:
        return NormalizedRequest(
            dispatch_id="dispatch-stream",
            transport_kind="api",
            provider_id="deepseek",
            model_id="deepseek-chat",
            text="stream me",
            idempotency_key="idem-stream",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
            stream=True,
        )

    def test_complete_stream_accumulates(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "Hel"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "lo"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        result = self.adapter.stream_dispatch(
            self._request(), self.plan, chunks, dispatch_id="dispatch-stream"
        )
        self.assertEqual(result["machine_error_code"], "STREAM_DISPATCH_COMPLETE")
        self.assertEqual(result["final_response"]["text"], "Hello")
        self.assertTrue(result["stream_complete"])

    def test_incomplete_stream_fails_closed(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "Hel"}, "finish_reason": None}]},
        ]
        result = self.adapter.stream_dispatch(
            self._request(), self.plan, chunks, dispatch_id="dispatch-stream"
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], ERR_STREAM_INCOMPLETE)


class LiveDispatchGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        os.environ["WBP_EXTERNAL_MODELS_DIR"] = str(self.root)
        os.environ["WBP_MANAGED_DIR"] = str(self.root / "managed")
        self.route_ids = _write_routes(self.root)
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
            managed_dir=self.root / "managed",
        )
        registry = _registry_document(self.route_ids)
        self.plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)

    def tearDown(self) -> None:
        os.environ.pop("WBP_EXTERNAL_MODELS_DIR", None)
        os.environ.pop("WBP_MANAGED_DIR", None)
        self.temp_dir.cleanup()

    def test_live_dispatch_without_credential_fails_closed(self) -> None:
        # auth=none routes admit; simulate a bearer route without credentials:
        routes = self.adapter._load_routes()
        route = routes[str(self.plan["route_id"])]
        route["auth"] = {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"}
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": list(routes.values())},
        )
        request = NormalizedRequest(
            dispatch_id="dispatch-live",
            transport_kind="api",
            provider_id="deepseek",
            model_id="deepseek-chat",
            text="hi",
            idempotency_key="idem-live",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        receipt = self.adapter.dispatch(
            request, self.plan, controlled=False, dispatch_id="dispatch-live"
        )
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["machine_error_code"], "CREDENTIAL_MISSING")
        self.assertFalse(receipt["live_provider_called"])
        self.assertFalse(receipt["fallback_used"])


if __name__ == "__main__":
    unittest.main()
