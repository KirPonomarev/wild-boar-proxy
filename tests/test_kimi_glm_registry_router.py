# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import unittest
from wild_boar_proxy import kimi_glm_registry_router as rr
from wild_boar_proxy.core import packets

def _assert(t, p):
    m = packets.missing_required_fields(p, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    t.assertEqual(m, [], f"missing: {m}")
    v = packets.inspect_command_packet_semantics(p)
    t.assertEqual(v, [], f"violations: {v}")

class RegistryTests(unittest.TestCase):
    def test_has_all_providers(self):
        providers = {e.provider for e in rr.REGISTRY}
        self.assertIn("deepseek", providers)
        self.assertIn("kimi", providers)
        self.assertIn("glm", providers)

    def test_kimi_has_3_models(self):
        kimi_models = [e for e in rr.REGISTRY if e.provider == "kimi"]
        self.assertGreaterEqual(len(kimi_models), 3)

    def test_registry_receipt(self):
        r = rr.build_registry_receipt()
        _assert(self, r)
        self.assertGreater(r["entry_count"], 4)

class AliasRouterTests(unittest.TestCase):
    def test_kimi_routes_to_kimi(self):
        lane, code = rr.resolve_alias("Kimi")
        self.assertEqual(lane, "kimi")
        self.assertEqual(code, "OK")

    def test_glm_routes_to_glm(self):
        lane, code = rr.resolve_alias("GLM")
        self.assertEqual(lane, "glm")

    def test_unknown_fails_closed(self):
        lane, code = rr.resolve_alias("Ghost")
        self.assertEqual(lane, "unknown")
        self.assertNotEqual(code, "OK")

    def test_kimi_never_falls_to_deepseek(self):
        lane, _ = rr.resolve_alias("Kimi")
        self.assertNotEqual(lane, "deepseek")

    def test_matrix_receipt(self):
        r = rr.build_alias_routing_matrix_receipt()
        _assert(self, r)
        self.assertTrue(r["no_silent_fallback"])

class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self):
        s = rr.run_registry_router_synthetic_proof()
        _assert(self, s)
        self.assertEqual(s["status"], "ok")

if __name__ == "__main__":
    unittest.main()
