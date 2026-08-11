# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B07_CODE: API transport adapter binding tests (multi-API core)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wild_boar_proxy import actor_registry as ar
from wild_boar_proxy import actor_dispatcher as ad
from wild_boar_proxy import api_transport_adapter as ata
from wild_boar_proxy.deepseek_route_profile import build_deepseek_route_definition
from wild_boar_proxy.external_models import routes as external_routes
from wild_boar_proxy.external_models.http_client import HttpJsonResponse
from wild_boar_proxy.kimi_glm_provider_slices import (
    build_glm_route_definition,
    build_kimi_route_definition,
)
from wild_boar_proxy.transport_normalization import (
    ERR_AMBIGUOUS_DELIVERY,
    ERR_IDENTITY_DRIFT,
    ERR_INVALID_CREDENTIAL,
    ERR_INVALID_UPSTREAM_RESPONSE,
    ERR_MODEL_NOT_AVAILABLE,
    ERR_NETWORK_FAILED,
    ERR_QUOTA_EXHAUSTED,
    ERR_SECRET_INPUT_BLOCKED,
    ERR_STREAM_INCOMPLETE,
    ERR_TIMEOUT,
    NormalizedRequest,
)
from wild_boar_proxy.runtime_errors import RuntimeErrorInfo


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
        self.assertEqual(len(admission["route_record_sha256"]), 64)
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

    def test_controlled_admission_does_not_probe_credentials(self) -> None:
        plan = self._plan("DIP")
        with patch.object(
            self.adapter,
            "_credential_presence",
            side_effect=AssertionError("credential probe must not run"),
        ):
            admission = self.adapter.bind(plan, require_credential=False)
        self.assertEqual(admission["status"], "ok")
        self.assertFalse(admission["credential_required"])
        self.assertFalse(admission["credential_present"])
        self.assertEqual(admission["credential_source"], "not_probed")

    def test_bind_rejects_route_provider_identity_drift(self) -> None:
        plan = self._plan("DIP")
        routes = self.adapter._load_routes()
        route = routes[str(plan["route_id"])]
        route["provider"] = "kimi"
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": list(routes.values())},
        )
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["machine_error_code"], "ROUTE_PROVIDER_MISMATCH")

    def test_credential_broker_exceptions_fail_closed(self) -> None:
        plan = self._plan("DIP")
        routes = self.adapter._load_routes()
        routes[str(plan["route_id"])]["auth"] = {
            "type": "bearer",
            "secret_ref": "DEEPSEEK_API_KEY",
        }
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": list(routes.values())},
        )
        with patch.object(
            ata.external_credentials,
            "credential_status",
            return_value={"credential_present": False},
        ), patch.object(
            ata,
            "lookup_keychain_credential",
            side_effect=RuntimeError("keychain unavailable"),
        ):
            admission = self.adapter.bind(plan)
        self.assertEqual(admission["status"], "blocked")
        self.assertEqual(admission["machine_error_code"], "CREDENTIAL_MISSING")


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
        self.assertEqual(deepseek_receipt["evidence_level"], "SYNTHETIC_PROVEN")
        self.assertEqual(deepseek_receipt["binding_revision"], 1)
        self.assertEqual(deepseek_receipt["assignment_revision"], 1)
        self.assertEqual(deepseek_receipt["context_digest"], "ctx-1")
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
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
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

    def test_controlled_bearer_dispatch_is_credential_free(self) -> None:
        routes = self.adapter._load_routes()
        deepseek = routes[str(self.route_ids["deepseek"]["route_id"])]
        deepseek["auth"] = {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"}
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": list(routes.values())},
        )
        with patch.object(
            self.adapter,
            "_credential_presence",
            side_effect=AssertionError("credential probe must not run"),
        ):
            receipt = self._dispatch("DIP")
        self.assertEqual(receipt["status"], "ok")
        self.assertTrue(receipt["controlled"])
        self.assertFalse(receipt["live_provider_called"])
        self.assertEqual(receipt["evidence_level"], "SYNTHETIC_PROVEN")

    def test_request_identity_drift_blocks_before_dispatch(self) -> None:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = NormalizedRequest(
            dispatch_id="dispatch-drift",
            transport_kind="api",
            provider_id="qwen",
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
            text="hello",
            idempotency_key="idem-drift",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        receipt = self.adapter.dispatch(
            request,
            plan,
            controlled=True,
            dispatch_id="dispatch-drift",
        )
        self.assertEqual(receipt["machine_error_code"], ERR_IDENTITY_DRIFT)
        self.assertFalse(receipt["dispatch_attempted"])

    def test_secret_shaped_prompt_blocks_before_dispatch(self) -> None:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = NormalizedRequest(
            dispatch_id="dispatch-secret",
            transport_kind="api",
            provider_id=str(plan["provider_id"]),
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
            text="api_key=abcdefgh12345678",
            idempotency_key="idem-secret",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        receipt = self.adapter.dispatch(
            request,
            plan,
            controlled=True,
            dispatch_id="dispatch-secret",
        )
        self.assertEqual(receipt["machine_error_code"], ERR_SECRET_INPUT_BLOCKED)
        self.assertFalse(receipt["dispatch_attempted"])
        self.assertNotIn("abcdefgh", json.dumps(receipt))

    def test_caller_route_override_drift_is_rejected(self) -> None:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = NormalizedRequest(
            dispatch_id="dispatch-route-drift",
            transport_kind="api",
            provider_id=str(plan["provider_id"]),
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
            text="hello",
            idempotency_key="idem-route-drift",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        drifted_route = dict(self.route_ids["deepseek"])
        drifted_route["base_url"] = "https://unregistered.invalid"
        receipt = self.adapter.dispatch(
            request,
            plan,
            controlled=True,
            dispatch_id="dispatch-route-drift",
            route=drifted_route,
        )
        self.assertEqual(receipt["machine_error_code"], "ROUTE_RECORD_DRIFT")
        self.assertFalse(receipt["dispatch_attempted"])

    def test_route_mutation_between_admission_and_dispatch_is_rejected(self) -> None:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = NormalizedRequest(
            dispatch_id="dispatch-route-race",
            transport_kind="api",
            provider_id=str(plan["provider_id"]),
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
            text="hello",
            idempotency_key="idem-route-race",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        admitted_routes = self.adapter._load_routes()
        mutated_routes = json.loads(json.dumps(admitted_routes))
        mutated_routes[str(plan["route_id"])]["base_url"] = (
            "https://mutated.invalid"
        )
        with patch.object(
            self.adapter,
            "_load_routes",
            side_effect=[admitted_routes, mutated_routes],
        ):
            receipt = self.adapter.dispatch(
                request,
                plan,
                controlled=True,
                dispatch_id="dispatch-route-race",
            )
        self.assertEqual(receipt["machine_error_code"], "ROUTE_RECORD_DRIFT")
        self.assertFalse(receipt["dispatch_attempted"])

    def test_receipt_fills_identity_from_resolved_plan(self) -> None:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = NormalizedRequest(
            dispatch_id="dispatch-plan-identity",
            transport_kind="api",
            provider_id=str(plan["provider_id"]),
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
            text="hello",
            idempotency_key="idem-plan-identity",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        receipt = self.adapter.dispatch(
            request,
            plan,
            controlled=True,
            dispatch_id="dispatch-plan-identity",
        )
        self.assertEqual(receipt["slot_id"], plan["slot_id"])
        self.assertEqual(receipt["binding_id"], plan["binding_id"])
        self.assertEqual(receipt["assignment_id"], plan["assignment_id"])

    def test_non_serializable_provider_payload_fails_before_dispatch(self) -> None:
        registry = _registry_document(self.route_ids)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = NormalizedRequest(
            dispatch_id="dispatch-invalid-payload",
            transport_kind="api",
            provider_id=str(plan["provider_id"]),
            model_id=str((plan.get("model_policy") or {}).get("model_id") or ""),
            text="hello",
            idempotency_key="idem-invalid-payload",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )
        with patch.object(
            self.adapter,
            "build_provider_request",
            return_value=({"model": request.model_id, "bad": object()}, {}),
        ):
            receipt = self.adapter.dispatch(
                request,
                plan,
                controlled=True,
                dispatch_id="dispatch-invalid-payload",
            )
        self.assertEqual(receipt["machine_error_code"], ERR_INVALID_UPSTREAM_RESPONSE)
        self.assertFalse(receipt["dispatch_attempted"])


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
            model_id=str((self.plan.get("model_policy") or {}).get("model_id") or ""),
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

    def test_secret_split_across_stream_chunks_redacts_all_deltas(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "token=abcd"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "efgh1234"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        result = self.adapter.stream_dispatch(
            self._request(), self.plan, chunks, dispatch_id="dispatch-stream"
        )
        serialized = json.dumps(result)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["response_redacted"])
        self.assertEqual(result["final_response"]["text"], "[redacted]")
        self.assertNotIn("token=abcd", serialized)
        self.assertNotIn("efgh1234", serialized)


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

    def _request(self, *, text: str = "hi") -> NormalizedRequest:
        return NormalizedRequest(
            dispatch_id="dispatch-live",
            transport_kind="api",
            provider_id=str(self.plan["provider_id"]),
            model_id=str((self.plan.get("model_policy") or {}).get("model_id") or ""),
            text=text,
            idempotency_key="idem-live",
            context_digest="ctx-1",
            requested_permission="context_only",
            effective_permission="context_only",
        )

    def _set_auth(self, auth: dict[str, str]) -> None:
        routes = self.adapter._load_routes()
        routes[str(self.plan["route_id"])]["auth"] = auth
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": list(routes.values())},
        )

    def test_live_dispatch_without_credential_fails_closed(self) -> None:
        # auth=none routes admit; simulate a bearer route without credentials:
        self._set_auth({"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"})
        receipt = self.adapter.dispatch(
            self._request(), self.plan, controlled=False, dispatch_id="dispatch-live"
        )
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["machine_error_code"], "CREDENTIAL_MISSING")
        self.assertFalse(receipt["live_provider_called"])
        self.assertFalse(receipt["dispatch_attempted"])
        self.assertFalse(receipt["fallback_used"])

    def test_http_error_statuses_never_false_green(self) -> None:
        expected = {
            401: ERR_INVALID_CREDENTIAL,
            403: ERR_INVALID_CREDENTIAL,
            404: ERR_MODEL_NOT_AVAILABLE,
            408: ERR_TIMEOUT,
            429: ERR_QUOTA_EXHAUSTED,
            500: ERR_NETWORK_FAILED,
            503: ERR_NETWORK_FAILED,
        }
        payload = {"choices": [{"message": {"content": "must not be accepted"}}]}
        for status_code, error_code in expected.items():
            with self.subTest(status_code=status_code):
                response = HttpJsonResponse(
                    status_code=status_code,
                    payload=payload,
                    latency_ms=1,
                )
                with patch(
                    "wild_boar_proxy.external_models.http_client.request_json",
                    return_value=response,
                ):
                    receipt = self.adapter.dispatch(
                        self._request(),
                        self.plan,
                        controlled=False,
                        dispatch_id="dispatch-live",
                    )
                self.assertEqual(receipt["status"], "error")
                self.assertEqual(receipt["machine_error_code"], error_code)
                self.assertEqual(receipt["result"], "error")
                self.assertTrue(receipt["dispatch_attempted"])
                self.assertTrue(receipt["response_observed"])
                self.assertTrue(receipt["live_provider_called"])
                self.assertFalse(receipt["live_provider_proven"])
                self.assertFalse(receipt["retry_permitted"])

    def test_post_request_exception_is_ambiguous_and_never_retryable(self) -> None:
        failure = RuntimeErrorInfo(
            "Provider network failed with Bearer sk-sensitive-value",
            machine_error_code="provider_network_failed",
            operator_action="retry",
        )
        with patch(
            "wild_boar_proxy.external_models.http_client.request_json",
            side_effect=failure,
        ):
            receipt = self.adapter.dispatch(
                self._request(),
                self.plan,
                controlled=False,
                dispatch_id="dispatch-live",
            )
        self.assertEqual(receipt["machine_error_code"], ERR_AMBIGUOUS_DELIVERY)
        self.assertEqual(receipt["upstream_error_code"], ERR_NETWORK_FAILED)
        self.assertEqual(receipt["result"], "ambiguous")
        self.assertTrue(receipt["dispatch_attempted"])
        self.assertFalse(receipt["response_observed"])
        self.assertTrue(receipt["live_provider_called"])
        self.assertFalse(receipt["live_provider_proven"])
        self.assertFalse(receipt["retry_permitted"])
        self.assertNotIn("sensitive", json.dumps(receipt))
        self.assertNotIn("Bearer", json.dumps(receipt))

    def test_invalid_success_payload_is_observed_error_without_raw_body(self) -> None:
        response = HttpJsonResponse(
            status_code=200,
            payload={"error": "token=abcdefgh12345678"},
            latency_ms=1,
        )
        with patch(
            "wild_boar_proxy.external_models.http_client.request_json",
            return_value=response,
        ):
            receipt = self.adapter.dispatch(
                self._request(),
                self.plan,
                controlled=False,
                dispatch_id="dispatch-live",
            )
        self.assertEqual(receipt["machine_error_code"], ERR_INVALID_UPSTREAM_RESPONSE)
        self.assertEqual(receipt["result"], "error")
        self.assertTrue(receipt["dispatch_attempted"])
        self.assertTrue(receipt["response_observed"])
        self.assertFalse(receipt["live_provider_proven"])
        self.assertNotIn("abcdefgh", json.dumps(receipt))

    def test_malformed_http_response_status_is_observed_error(self) -> None:
        with patch(
            "wild_boar_proxy.external_models.http_client.request_json",
            return_value=object(),
        ):
            receipt = self.adapter.dispatch(
                self._request(),
                self.plan,
                controlled=False,
                dispatch_id="dispatch-live",
            )
        self.assertEqual(receipt["machine_error_code"], ERR_INVALID_UPSTREAM_RESPONSE)
        self.assertEqual(receipt["result"], "error")
        self.assertTrue(receipt["dispatch_attempted"])
        self.assertTrue(receipt["response_observed"])
        self.assertTrue(receipt["live_provider_called"])
        self.assertIsNone(receipt["provider_http_status"])

    def test_route_mutation_at_live_rebind_blocks_before_provider(self) -> None:
        admitted_routes = self.adapter._load_routes()
        dispatch_routes = json.loads(json.dumps(admitted_routes))
        mutated_routes = json.loads(json.dumps(admitted_routes))
        mutated_routes[str(self.plan["route_id"])]["base_url"] = (
            "https://mutated.invalid"
        )
        with patch.object(
            self.adapter,
            "_load_routes",
            side_effect=[admitted_routes, dispatch_routes, mutated_routes],
        ), patch(
            "wild_boar_proxy.external_models.http_client.request_json"
        ) as request_mock:
            receipt = self.adapter.dispatch(
                self._request(),
                self.plan,
                controlled=False,
                dispatch_id="dispatch-live",
            )
        request_mock.assert_not_called()
        self.assertEqual(receipt["machine_error_code"], "ROUTE_RECORD_DRIFT")
        self.assertFalse(receipt["dispatch_attempted"])
        self.assertFalse(receipt["live_provider_called"])

    def test_successful_provider_output_is_redacted_and_digest_bound(self) -> None:
        response = HttpJsonResponse(
            status_code=200,
            payload={
                "choices": [
                    {"message": {"content": "result token=abcdefgh12345678"}}
                ]
            },
            latency_ms=1,
        )
        with patch(
            "wild_boar_proxy.external_models.http_client.request_json",
            return_value=response,
        ):
            receipt = self.adapter.dispatch(
                self._request(),
                self.plan,
                controlled=False,
                dispatch_id="dispatch-live",
            )
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["evidence_level"], "LIVE_PROVEN")
        self.assertTrue(receipt["live_provider_proven"])
        self.assertTrue(receipt["response_redacted"])
        self.assertEqual(receipt["response_text"], "result [redacted]")
        self.assertEqual(
            receipt["response_text_sha256"],
            hashlib.sha256(b"result [redacted]").hexdigest(),
        )
        self.assertNotIn("abcdefgh", json.dumps(receipt))

    def test_pre_dispatch_header_failure_is_not_marked_attempted(self) -> None:
        failure = RuntimeErrorInfo(
            "missing secret value that must not escape",
            machine_error_code="missing_secret",
            operator_action="user_action",
        )
        with patch(
            "wild_boar_proxy.external_models.validate._provider_headers",
            side_effect=failure,
        ), patch(
            "wild_boar_proxy.external_models.http_client.request_json"
        ) as request_mock:
            receipt = self.adapter.dispatch(
                self._request(),
                self.plan,
                controlled=False,
                dispatch_id="dispatch-live",
            )
        request_mock.assert_not_called()
        self.assertEqual(receipt["machine_error_code"], ERR_INVALID_CREDENTIAL)
        self.assertFalse(receipt["dispatch_attempted"])
        self.assertFalse(receipt["live_provider_called"])
        self.assertNotIn("secret value", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
