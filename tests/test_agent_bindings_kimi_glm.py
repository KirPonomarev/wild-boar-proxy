# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import unittest
from wild_boar_proxy.custom_agent_bindings import (
    default_agent_bindings, kimi_glm_additional_routes,
)


class DefaultBindingsTests(unittest.TestCase):
    def test_primary_and_dip(self):
        b = default_agent_bindings(primary_model_id="gpt-5", api_route_id="deepseek")
        self.assertEqual(len(b), 2)
        self.assertEqual(b[0]["display_name"], "Codex")
        self.assertEqual(b[1]["display_name"], "DIP")

    def test_no_api_route(self):
        b = default_agent_bindings(primary_model_id="gpt-5", api_route_id="")
        self.assertEqual(len(b), 1)

    def test_additional_kimi_glm(self):
        extra = kimi_glm_additional_routes()
        b = default_agent_bindings(
            primary_model_id="gpt-5",
            api_route_id="deepseek",
            additional_api_routes=extra,
        )
        self.assertEqual(len(b), 4)  # Codex + DIP + Kimi + GLM
        names = [a["display_name"] for a in b]
        self.assertIn("Kimi", names)
        self.assertIn("GLM", names)
        kimi = [a for a in b if a["display_name"] == "Kimi"][0]
        self.assertEqual(kimi["route_id"], "wbp-kimi-primary")
        self.assertIn("Kimi", kimi["aliases"])

    def test_additional_custom_route(self):
        b = default_agent_bindings(
            primary_model_id="gpt-5",
            api_route_id="deepseek",
            additional_api_routes=[{
                "route_id": "custom-route",
                "display_name": "Custom",
                "aliases": ["Custom", "Agent 3"],
            }],
        )
        self.assertEqual(len(b), 3)
        custom = [a for a in b if a["display_name"] == "Custom"][0]
        self.assertEqual(custom["agent_id"], "agent_3")

    def test_additional_empty_route_skipped(self):
        b = default_agent_bindings(
            primary_model_id="gpt-5",
            api_route_id="deepseek",
            additional_api_routes=[{"route_id": "", "display_name": "Empty"}],
        )
        self.assertEqual(len(b), 2)  # only Codex + DIP

    def test_backward_compatible_no_additional(self):
        """Existing callers without additional_api_routes still work."""
        b = default_agent_bindings(primary_model_id="gpt-5", api_route_id="deepseek")
        self.assertEqual(len(b), 2)


if __name__ == "__main__":
    unittest.main()
