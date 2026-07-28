# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for Kimi + GLM provider slices (P05+P06)."""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import kimi_glm_provider_slices as kg
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class KimiRouteDefinitionTests(unittest.TestCase):
    def test_kimi_route(self) -> None:
        r = kg.build_kimi_route_definition()
        self.assertEqual(r["provider"], kg.KIMI_PROVIDER_ID)
        self.assertEqual(r["base_url"], kg.KIMI_DEFAULT_BASE_URL)
        self.assertFalse(r["enabled"])

    def test_kimi_no_secret(self) -> None:
        r = kg.build_kimi_route_definition()
        self.assertNotIn("sk-", json.dumps(r))

    def test_kimi_stable_aliases(self) -> None:
        r1 = kg.build_kimi_route_definition(route_id="wbp-kimi-primary")
        r2 = kg.build_kimi_route_definition(route_id="wbp-kimi-code-fast")
        self.assertEqual(r1["route_id"], "wbp-kimi-primary")
        self.assertEqual(r2["route_id"], "wbp-kimi-code-fast")


class GLMRouteDefinitionTests(unittest.TestCase):
    def test_glm_route(self) -> None:
        r = kg.build_glm_route_definition()
        self.assertEqual(r["provider"], kg.GLM_PROVIDER_ID)
        self.assertEqual(r["base_url"], kg.GLM_DEFAULT_BASE_URL)
        self.assertFalse(r["enabled"])

    def test_glm_no_secret(self) -> None:
        r = kg.build_glm_route_definition()
        self.assertNotIn("sk-", json.dumps(r))


class IntelligenceMappingTests(unittest.TestCase):
    def test_kimi_k3_fast_maps_to_low(self) -> None:
        r = kg.build_intelligence_mapping_receipt(provider="kimi", model=kg.KIMI_MODEL_K3)
        _assert_semantics(self, r)
        levels = {l["catalog_level"]: l for l in r["levels"]}
        self.assertEqual(levels["fast"]["provider_parameter"], "low")
        self.assertEqual(levels["max"]["provider_parameter"], "max")

    def test_kimi_k27_high_unavailable(self) -> None:
        r = kg.build_intelligence_mapping_receipt(provider="kimi", model=kg.KIMI_MODEL_K27_CODE)
        levels = {l["catalog_level"]: l for l in r["levels"]}
        self.assertFalse(levels["high"]["available"])
        self.assertFalse(levels["max"]["available"])

    def test_kimi_k26_fast_disabled(self) -> None:
        r = kg.build_intelligence_mapping_receipt(provider="kimi", model=kg.KIMI_MODEL_K26)
        levels = {l["catalog_level"]: l for l in r["levels"]}
        self.assertEqual(levels["fast"]["provider_parameter"], "disabled")
        self.assertEqual(levels["high"]["provider_parameter"], "enabled")

    def test_glm_high_maps_to_enabled(self) -> None:
        r = kg.build_intelligence_mapping_receipt(provider="glm", model=kg.GLM_MODEL_FLAGSHIP)
        _assert_semantics(self, r)
        levels = {l["catalog_level"]: l for l in r["levels"]}
        self.assertEqual(levels["high"]["provider_parameter"], "enabled")

    def test_no_cross_provider_equivalence(self) -> None:
        for prov, model in [("kimi", kg.KIMI_MODEL_K3), ("glm", kg.GLM_MODEL_FLAGSHIP)]:
            r = kg.build_intelligence_mapping_receipt(provider=prov, model=model)
            for l in r["levels"]:
                self.assertFalse(l["cross_provider_equivalence_claimed"])

    def test_unknown_provider_rejected(self) -> None:
        r = kg.build_intelligence_mapping_receipt(provider="unknown", model="x")
        self.assertEqual(r["status"], "error")


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = kg.run_kimi_glm_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["checks"]["kimi_k3_fast_maps_to_low"])
        self.assertTrue(s["checks"]["kimi_k27_high_unavailable"])
        self.assertTrue(s["checks"]["glm_high_maps_to_enabled"])
        self.assertTrue(s["checks"]["no_equivalence_claimed"])

    def test_no_secret_leak(self) -> None:
        s = kg.run_kimi_glm_synthetic_proof()
        self.assertNotIn("sk-", json.dumps(s))


if __name__ == "__main__":
    unittest.main()
