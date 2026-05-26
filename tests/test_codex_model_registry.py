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
        self.assertEqual(packet["configured_model"], "gpt-5.3-codex")
        self.assertTrue(packet["configured_model_visible"])
        self.assertEqual(packet["model_count"], 3)
        self.assertTrue(packet["server_issued"])
        self.assertTrue(packet["openai_compatible_shape_declared"])
        self.assertTrue(packet["models_endpoint_shape_declared"])
        self.assertTrue(packet["responses_shape_declared"])
        self.assertTrue(packet["chat_completions_shape_declared"])
        self.assertTrue(packet["codex_config_compatible"])
        self.assertFalse(packet["live_api_checked"])
        self.assertFalse(packet["network_calls_made"])
        self.assertEqual(packet["model_provider"], "cliproxy")
        self.assertEqual(packet["wire_api"], "responses")
        self.assertIn("gpt-5.3-codex", packet["canonical_internal_model_ids_visible"])
        self.assertFalse(packet["route_or_backend_exposed"])
        self.assertFalse(packet["models_endpoint_called"])
        self.assertFalse(packet["inference_called"])
        self.assertFalse(packet["provider_called"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["negative_claim_basis"],
            "shape_declaration_no_live_api_or_inference_call",
        )
        self.assertFalse(packet["independent_runtime_meter_attached"])
        self.assertNotIn("backend_id", json.dumps(packet["available_models"]))
        self.assertNotIn("route_id", json.dumps(packet["available_models"]))
        self.assertIn("backend_id", packet["forbidden_browser_fields"])
        self.assertIn("route_id", packet["forbidden_browser_fields"])
        first_model = packet["available_models"][0]
        self.assertEqual(first_model["label"], first_model["model_id"])
        self.assertIn("provider_class", first_model)
        self.assertTrue(first_model["codex_compatible"])
        self.assertTrue(first_model["responses_supported"])
        self.assertEqual(first_model["responses_supported_claim_scope"], "shape_declared_not_live_proven")
        self.assertFalse(first_model["responses_live_acceptance_proven"])
        self.assertTrue(first_model["chat_completions_supported"])
        self.assertEqual(
            first_model["chat_completions_supported_claim_scope"],
            "shape_declared_not_live_proven",
        )
        self.assertFalse(first_model["chat_completions_live_acceptance_proven"])
        self.assertEqual(first_model["availability_claim_level"], "listed_not_live_proven")
        self.assertFalse(first_model["live_availability_proven"])
        self.assertFalse(first_model["account_health_proven"])
        self.assertFalse(first_model["native_proven_by_registry"])
        self.assertFalse(first_model["direct_egress_proven_by_registry"])
        self.assertFalse(packet["claim_limits"]["model_listed_means_usable"])
        self.assertFalse(packet["claim_limits"]["registry_proves_live_availability"])

    def test_api_compat_only_declares_openai_shape_without_live_calls(self) -> None:
        packet = build_custom_api_compat_packet(operator_status(claim_gate="passed"))

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["openai_compatible_shape_declared"])
        self.assertTrue(packet["models_endpoint_shape_declared"])
        self.assertTrue(packet["responses_shape_declared"])
        self.assertTrue(packet["chat_completions_shape_declared"])
        self.assertEqual(packet["configured_wire_api"], "responses")
        self.assertTrue(packet["codex_config_compatible"])
        self.assertFalse(packet["live_api_checked"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertFalse(packet["compat_surfaces"]["/v1/models"]["called"])
        self.assertFalse(packet["compat_surfaces"]["/v1/models"]["fresh_truth"])
        self.assertEqual(packet["compat_surfaces"]["/v1/models"]["status"], "shape_declared")
        self.assertFalse(packet["compat_surfaces"]["/v1/responses"]["called"])
        self.assertEqual(
            packet["compat_surfaces"]["/v1/responses"]["status"],
            "shape_declared_not_called",
        )
        self.assertFalse(packet["compat_surfaces"]["/v1/chat/completions"]["called"])
        self.assertFalse(packet["network_call_summary"]["network_calls_made"])
        self.assertEqual(packet["network_call_summary"]["allowed_calls_made"], [])
        self.assertEqual(packet["network_call_summary"]["forbidden_calls_made"], [])
        self.assertFalse(packet["network_call_summary"]["inference_called"])
        self.assertEqual(packet["network_call_summary"]["token_burn"], 0)
        self.assertEqual(
            packet["network_call_summary"]["negative_claim_basis"],
            "shape_declaration_no_live_api_or_inference_call",
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
        self.assertTrue(packet["selected_model_server_issued"])
        self.assertTrue(packet["codex_config_compatible"])
        self.assertEqual(packet["model_provider"], "cliproxy")
        self.assertEqual(packet["wire_api"], "responses")
        self.assertFalse(packet["network_call_summary"]["network_calls_made"])
        self.assertEqual(packet["network_call_summary"]["allowed_calls_made"], [])
        self.assertFalse(packet["route_or_backend_exposed"])
        self.assertFalse(packet["inference_called"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["responses_called"])
        self.assertFalse(packet["chat_completions_called"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["negative_claim_basis"],
            "shape_declaration_no_live_api_or_inference_call",
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
                "openai_base_url": "http://127.0.0.1:9999/v1",
                "wire_api": "chat_completions",
                "provider": "openai",
                "CODEX_HOME": "/tmp/home",
                "nested": {"auth": "secret"},
            },
            operator_status(claim_gate="passed"),
        )

        self.assertEqual(free_form["status"], "rejected")
        self.assertEqual(free_form["machine_error_code"], "MODEL_NOT_SERVER_ISSUED")
        self.assertFalse(free_form["inference_called"])
        self.assertFalse(free_form["network_call_summary"]["network_calls_made"])
        self.assertEqual(free_form["token_burn"], 0)
        self.assertEqual(forged["status"], "rejected")
        self.assertEqual(forged["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            forged["forbidden_fields"],
            [
                "route_id",
                "backend_id",
                "openai_base_url",
                "wire_api",
                "provider",
                "CODEX_HOME",
                "nested",
                "nested.auth",
            ],
        )
        self.assertFalse(forged["network_call_summary"]["network_calls_made"])

    def test_forbidden_custom_model_fields_allows_only_top_level_model_id(self) -> None:
        self.assertEqual(forbidden_custom_model_fields({"model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_custom_model_fields({"dry_run": True}), ["dry_run"])
        self.assertEqual(
            forbidden_custom_model_fields({"model_id": "gpt-5.3-codex", "items": [{"path": "/x"}]}),
            ["items", "items[0].path"],
        )


if __name__ == "__main__":
    unittest.main()
