# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.codex_model_registry import (
    build_custom_api_compat_packet,
    build_custom_model_dry_run_packet,
    build_custom_model_registry_packet,
    forbidden_custom_model_fields,
)


def operator_status(*, claim_gate: str = "blocked") -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.3-codex",
        },
        "claim_gate": {"status": claim_gate},
        "models": {
            "ok": True,
            "model_ids": ["gpt-5.3-codex", "gpt-5.4", "direct-mistral-devstral-2512"],
            "server_issued": True,
        },
    }


class CodexModelRegistryTests(unittest.TestCase):
    def test_model_registry_is_degraded_when_claim_gate_blocked_without_false_green(self) -> None:
        packet = build_custom_model_registry_packet(operator_status(claim_gate="blocked"))

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertEqual(packet["reported_configured_model"], "gpt-5.3-codex")
        self.assertTrue(packet["configured_model_visible"])
        self.assertEqual(packet["model_count"], 3)
        self.assertTrue(packet["server_issued"])
        self.assertFalse(packet["route_or_backend_exposed"])
        self.assertTrue(packet["models_endpoint_called"])
        self.assertFalse(packet["inference_called"])
        self.assertFalse(packet["provider_called"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["negative_claim_basis"],
            "dry_run_static_code_path_no_inference_adapter",
        )
        self.assertFalse(packet["independent_runtime_meter_attached"])
        self.assertNotIn("backend_id", json.dumps(packet["available_models"]))
        self.assertNotIn("route_id", json.dumps(packet["available_models"]))
        self.assertIn("backend_id", packet["forbidden_browser_fields"])
        self.assertIn("route_id", packet["forbidden_browser_fields"])

    def test_api_compat_only_claims_models_surface_called(self) -> None:
        packet = build_custom_api_compat_packet(operator_status(claim_gate="passed"))

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["compat_surfaces"]["/v1/models"]["called"])
        self.assertTrue(packet["compat_surfaces"]["/v1/models"]["fresh_truth"])
        self.assertFalse(packet["compat_surfaces"]["/v1/responses"]["called"])
        self.assertEqual(
            packet["compat_surfaces"]["/v1/responses"]["status"],
            "not_called_in_this_contour",
        )
        self.assertFalse(packet["compat_surfaces"]["/v1/chat/completions"]["called"])
        self.assertEqual(packet["network_call_summary"]["forbidden_calls_made"], [])
        self.assertFalse(packet["network_call_summary"]["inference_called"])
        self.assertEqual(packet["network_call_summary"]["token_burn"], 0)
        self.assertEqual(
            packet["network_call_summary"]["negative_claim_basis"],
            "dry_run_static_code_path_no_inference_adapter",
        )
        self.assertFalse(packet["network_call_summary"]["independent_runtime_meter_attached"])

    def test_model_dry_run_accepts_only_server_issued_model_without_inference(self) -> None:
        packet = build_custom_model_dry_run_packet(
            {"model_id": "gpt-5.3-codex"},
            operator_status(claim_gate="blocked"),
        )

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertTrue(packet["dry_run"])
        self.assertEqual(packet["selected_model"], "gpt-5.3-codex")
        self.assertTrue(packet["model_server_issued"])
        self.assertTrue(packet["codex_config_compatible"])
        self.assertFalse(packet["route_or_backend_exposed"])
        self.assertFalse(packet["inference_called"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["responses_called"])
        self.assertFalse(packet["chat_completions_called"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["negative_claim_basis"],
            "dry_run_static_code_path_no_inference_adapter",
        )
        self.assertFalse(packet["independent_runtime_meter_attached"])
        self.assertEqual(packet["claim_gate_status"], "blocked")

    def test_model_dry_run_rejects_free_form_model_and_browser_routes(self) -> None:
        free_form = build_custom_model_dry_run_packet(
            {"model_id": "invented-model"},
            operator_status(claim_gate="passed"),
        )
        forged = build_custom_model_dry_run_packet(
            {
                "model_id": "gpt-5.3-codex",
                "route_id": "browser-route",
                "backend_id": "browser-backend",
                "provider": "openai",
                "CODEX_HOME": "/tmp/home",
                "nested": {"auth": "secret"},
            },
            operator_status(claim_gate="passed"),
        )

        self.assertEqual(free_form["status"], "rejected")
        self.assertEqual(free_form["machine_error_code"], "MODEL_NOT_SERVER_ISSUED")
        self.assertFalse(free_form["inference_called"])
        self.assertEqual(free_form["token_burn"], 0)
        self.assertEqual(forged["status"], "rejected")
        self.assertEqual(forged["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            forged["forbidden_fields"],
            ["route_id", "backend_id", "provider", "CODEX_HOME", "nested", "nested.auth"],
        )

    def test_forbidden_custom_model_fields_allows_only_top_level_model_id(self) -> None:
        self.assertEqual(forbidden_custom_model_fields({"model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_custom_model_fields({"dry_run": True}), ["dry_run"])
        self.assertEqual(
            forbidden_custom_model_fields({"model_id": "gpt-5.3-codex", "items": [{"path": "/x"}]}),
            ["items", "items[0].path"],
        )


if __name__ == "__main__":
    unittest.main()
