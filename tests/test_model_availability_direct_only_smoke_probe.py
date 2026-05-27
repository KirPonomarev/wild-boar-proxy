# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from tools.model_availability_direct_only_smoke_probe import (
    _candidate_inputs_from_live_and_readiness,
)
from wild_boar_proxy.model_availability import build_candidate_model_list


class ModelAvailabilityDirectOnlySmokeProbeTests(unittest.TestCase):
    def test_candidate_inputs_merge_fresh_models_with_readiness_rows(self) -> None:
        catalog_packet, routes_packet, reference_packet = _candidate_inputs_from_live_and_readiness(
            model_ids=["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"],
            readiness_rows=[
                {
                    "model_id": "gpt-5.3-codex",
                    "candidate_selected": True,
                    "route_family": "codex_native_account_route",
                },
                {
                    "model_id": "direct-mistral-devstral-2512",
                    "candidate_selected": True,
                    "route_family": "wbp_api_external_route",
                    "provider_model_id": "direct-mistral-devstral-2512",
                },
            ],
        )

        self.assertEqual(reference_packet["status"], "ok")
        self.assertEqual(
            reference_packet["readiness_admitted_candidate_ids"],
            ["gpt-5.3-codex", "direct-mistral-devstral-2512"],
        )
        self.assertEqual(
            reference_packet["fresh_models_endpoint_visible_ids"],
            ["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"],
        )
        catalog_ids = {
            row["model_id"]
            for row in catalog_packet["models"]
            if isinstance(row, dict)
        }
        self.assertIn("gpt-5.3-codex", catalog_ids)
        self.assertIn("direct-mistral-devstral-2512", catalog_ids)
        routes = routes_packet["data"]["routes"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["route_id"], "direct-mistral-devstral-2512")
        self.assertEqual(routes[0]["auth"]["secret_ref"], "present_redacted")

    def test_candidate_inputs_allow_bounded_freeze_with_default_and_external_candidate(self) -> None:
        catalog_packet, routes_packet, _ = _candidate_inputs_from_live_and_readiness(
            model_ids=["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"],
            readiness_rows=[
                {
                    "model_id": "gpt-5.3-codex",
                    "candidate_selected": True,
                    "route_family": "codex_native_account_route",
                },
                {
                    "model_id": "direct-mistral-devstral-2512",
                    "candidate_selected": True,
                    "route_family": "wbp_api_external_route",
                    "provider_model_id": "direct-mistral-devstral-2512",
                },
            ],
        )

        candidate_packet = build_candidate_model_list(
            configured_model="gpt-5.3-codex",
            catalog_packet=catalog_packet,
            routes_packet=routes_packet,
        )

        self.assertEqual(candidate_packet["status"], "ok")
        self.assertEqual(
            candidate_packet["candidate_model_ids"],
            [
                "gpt-5.3-codex",
                "gpt-5.4-mini",
                "gpt-5.4",
                "gpt-5.5",
                "direct-mistral-devstral-2512",
            ],
        )
        self.assertEqual(candidate_packet["candidate_count"], 5)


if __name__ == "__main__":
    unittest.main()
