# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B08: Qwen provider slice tests (credential, route, dialects, catalog)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import api_transport_adapter as ata
from wild_boar_proxy import qwen_provider_slice as qps
from wild_boar_proxy.external_models import routes as external_routes
from wild_boar_proxy.external_models.capability_registry import CATALOG, get_entry


class QwenRouteTests(unittest.TestCase):
    def test_default_route_passes_schema(self) -> None:
        route = qps.build_qwen_route_definition()
        self.assertEqual(route["route_id"], "wbp-qwen-primary")
        self.assertEqual(route["provider"], "qwen")
        self.assertIs(external_routes.validate_route_schema(route), route)

    def test_route_never_embeds_credential_value(self) -> None:
        route = qps.build_qwen_route_definition()
        self.assertNotIn("sk-", json.dumps(route))
        self.assertEqual(route["auth"]["secret_ref"], "DASHSCOPE_API_KEY")

    def test_route_disabled_by_default(self) -> None:
        route = qps.build_qwen_route_definition()
        self.assertFalse(route["enabled"])


class QwenThinkingTests(unittest.TestCase):
    def test_qwen3_thinking_param_applied(self) -> None:
        payload = {"model": "qwen3-max", "messages": []}
        result = qps.apply_qwen_thinking(payload, model="qwen3-max", thinking_enabled=True)
        self.assertTrue(result["enable_thinking"])

    def test_qwen3_thinking_disabled(self) -> None:
        payload = {"model": "qwen3-max", "messages": []}
        result = qps.apply_qwen_thinking(payload, model="qwen3-max", thinking_enabled=False)
        self.assertFalse(result["enable_thinking"])

    def test_non_qwen3_model_untouched(self) -> None:
        payload = {"model": "qwen-plus", "messages": []}
        result = qps.apply_qwen_thinking(payload, model="qwen-plus", thinking_enabled=True)
        self.assertNotIn("enable_thinking", result)

    def test_thinking_never_inferred_from_unknown_model(self) -> None:
        payload = {"model": "some-other-model", "messages": []}
        result = qps.apply_qwen_thinking(payload, model="some-other-model", thinking_enabled=True)
        self.assertNotIn("enable_thinking", result)


class QwenCatalogTests(unittest.TestCase):
    def test_catalog_entries_present(self) -> None:
        qwen_models = [entry.upstream_model for entry in CATALOG if entry.provider == "qwen"]
        self.assertEqual(set(qwen_models), set(qps.QWEN_MODEL_IDS))

    def test_qwen3_max_mapped(self) -> None:
        entry = get_entry("qwen3-max")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.thinking_dialect, "qwen_thinking")


class QwenProfilePacketTests(unittest.TestCase):
    def test_profile_packet_synthetic_proven(self) -> None:
        packet = qps.build_qwen_profile_packet()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "SYNTHETIC_PROVEN")
        self.assertTrue(packet["declared_not_live_verified"])
        self.assertEqual(packet["provider_id"], "qwen")


class QwenAdapterBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.root.mkdir(parents=True, exist_ok=True)
        route = qps.build_qwen_route_definition(enabled=True)
        route["auth"] = {"type": "none"}
        external_routes.write_routes_file(
            self.root / "routes.json",
            {"schema_version": 1, "routes": [route]},
        )
        self.adapter = ata.ApiTransportAdapter(
            routes_file=self.root / "routes.json",
            external_models_dir=self.root,
        )
        self.route = route

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_qwen_route_admitted(self) -> None:
        plan = {
            "status": "ok",
            "provider_id": "qwen",
            "route_id": "wbp-qwen-primary",
            "model_policy": {"model_id": "qwen-plus"},
            "transport_adapter_id": "api",
        }
        admission = self.adapter.bind(plan)
        self.assertEqual(admission["status"], "ok")
        self.assertTrue(admission["credential_present"])
        self.assertFalse(admission["secret_value_exposed"])

    def test_qwen_thinking_via_adapter(self) -> None:
        route = dict(self.route)
        route["thinking"] = {"type": "enabled", "reasoning_effort": "max"}
        payload, _ = self.adapter.build_provider_request(
            route=route, text="hi", model_id="qwen3-max"
        )
        self.assertTrue(payload["enable_thinking"])

    def test_qwen_thinking_disabled_by_default_route(self) -> None:
        payload, _ = self.adapter.build_provider_request(
            route=self.route, text="hi", model_id="qwen3-max"
        )
        self.assertFalse(payload["enable_thinking"])


if __name__ == "__main__":
    unittest.main()
