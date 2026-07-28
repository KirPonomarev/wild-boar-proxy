# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import unittest
from wild_boar_proxy.external_models.capability_registry import (
    CATALOG, get_catalog, get_entry, get_intelligence_mapping,
    resolve_intelligence_level,
)


class CatalogTests(unittest.TestCase):
    def test_has_deepseek_kimi_glm(self):
        providers = {e.provider for e in CATALOG}
        self.assertIn("deepseek", providers)
        self.assertIn("kimi", providers)
        self.assertIn("glm", providers)

    def test_all_entries_have_docs_source(self):
        for e in CATALOG:
            self.assertTrue(e.docs_source.startswith("http"))

    def test_get_entry_by_model(self):
        e = get_entry("kimi-k2.5")
        self.assertIsNotNone(e)
        self.assertEqual(e.provider, "kimi")

    def test_get_entry_not_found(self):
        self.assertIsNone(get_entry("nonexistent"))


class IntelligenceMappingTests(unittest.TestCase):
    def test_kimi_k25_fast_maps_to_low(self):
        param, source = resolve_intelligence_level("kimi-k2.5", "fast")
        self.assertEqual(param, "low")
        self.assertEqual(source, "provider_declared")

    def test_kimi_k25_max_maps_to_max(self):
        param, _ = resolve_intelligence_level("kimi-k2.5", "max")
        self.assertEqual(param, "max")

    def test_glm_high_maps_to_enabled(self):
        param, _ = resolve_intelligence_level("glm-4.6", "high")
        self.assertEqual(param, "enabled")

    def test_kimi_k26_no_max(self):
        mapping = get_intelligence_mapping("kimi-k2.6")
        self.assertNotIn("max", mapping)

    def test_default_returns_none(self):
        param, source = resolve_intelligence_level("glm-4.6", "default")
        self.assertIsNone(param)
        self.assertEqual(source, "provider_default")

    def test_unavailable_level(self):
        param, source = resolve_intelligence_level("kimi-k2.6", "max")
        self.assertIsNone(param)
        self.assertEqual(source, "unavailable")


if __name__ == "__main__":
    unittest.main()
