# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.codex_model_registry import (
    build_model_catalog_fidelity_packets,
    build_custom_api_compat_packet,
    build_custom_model_dry_run_packet,
    build_custom_model_registry_packet,
    forbidden_custom_model_fields,
    validate_wbp_model_catalog_contract,
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
        self.assertEqual(first_model["lane"], "codex_native")
        self.assertEqual(first_model["source_class"], "current_build_catalog_visible")
        self.assertFalse(first_model["physical_provider_proven"])
        self.assertEqual(first_model["display_name"], first_model["model_id"])
        self.assertIn("source", first_model["intelligence_tier"])
        self.assertIn("proof_level", first_model["speed_tier"])
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

    def test_model_catalog_preserves_codex_native_and_wbp_api_lanes(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))

        native_lane = packets["codex_native_model_lane_packet.json"]
        wbp_lane = packets["wbp_api_model_lane_packet.json"]
        separation = packets["model_lane_separation_packet.json"]

        self.assertEqual(native_lane["status"], "ok")
        self.assertEqual(wbp_lane["status"], "ok")
        self.assertEqual(separation["status"], "ok")
        self.assertTrue(native_lane["models"])
        self.assertTrue(wbp_lane["models"])
        self.assertTrue(all(model["lane"] == "codex_native" for model in native_lane["models"]))
        self.assertTrue(all(model["lane"] == "wbp_api" for model in wbp_lane["models"]))
        self.assertFalse(separation["lanes_mixed"])

    def test_model_display_metadata_not_runtime_truth(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        display = packets["model_display_metadata_packet.json"]
        runtime = packets["runtime_binding_truth_packet.json"]

        self.assertEqual(display["status"], "ok")
        self.assertFalse(display["display_metadata_is_runtime_truth"])
        self.assertEqual(runtime["status"], "ok")
        self.assertFalse(runtime["display_metadata_becomes_runtime_binding_truth"])
        self.assertFalse(runtime["route_selected_proven"])
        self.assertFalse(runtime["upstream_accepts_proven"])
        self.assertFalse(runtime["response_accepted_by_codex_proven"])

    def test_catalog_registry_truth_not_runtime_binding_truth(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        registry = packets["catalog_registry_truth_packet.json"]
        runtime = packets["runtime_binding_truth_packet.json"]

        self.assertEqual(registry["status"], "ok")
        self.assertFalse(registry["display_metadata_is_catalog_registry_truth"])
        self.assertFalse(registry["catalog_registry_truth_is_runtime_binding_truth"])
        self.assertEqual(runtime["status"], "ok")
        self.assertFalse(runtime["catalog_registry_truth_becomes_runtime_binding_truth"])
        for row in runtime["rows"]:
            self.assertFalse(row["catalog_registry_truth_becomes_runtime_binding_truth"])

    def test_runtime_binding_truth_not_capability_proof(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        capability = packets["capability_claims_packet.json"]

        self.assertEqual(capability["status"], "ok")
        self.assertFalse(capability["catalog_registry_truth_is_capability_proof"])
        self.assertFalse(capability["runtime_binding_truth_is_capability_proof"])
        self.assertFalse(capability["runtime_truth_boundary_is_capability_proof"])
        for model in capability["models"]:
            self.assertFalse(model["catalog_registry_counts_as_capability_proof"])
            self.assertFalse(model["runtime_binding_counts_as_capability_proof"])
            self.assertFalse(model["runtime_truth_counts_as_capability_proof"])
            self.assertIn("proof_level", model["capabilities"]["tools"])

    def test_intelligence_and_speed_tier_source_and_proof_level_required(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        display = packets["model_display_metadata_packet.json"]

        for model in display["models"]:
            self.assertIn("source", model["intelligence_tier"])
            self.assertIn("proof_level", model["intelligence_tier"])
            self.assertIn("source", model["speed_tier"])
            self.assertIn("proof_level", model["speed_tier"])

    def test_measured_source_requires_measurement_packet(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        catalog = packets["codex_native_model_lane_packet.json"]
        mutated = {
            "schema_version": 1,
            "contract_scope": "provider_catalog_only",
            "server_owned_source": True,
            "default_model_explicit": True,
            "default_model": "gpt-5.3-codex",
            "browser_authority": {
                "catalog_path": False,
                "model_provider": False,
                "base_url": False,
                "wire_api": False,
                "route_id": False,
                "backend_id": False,
                "auth_path": False,
                "token": False,
            },
            "live_api_checked": False,
            "network_calls_made": False,
            "inference_called": False,
            "provider_called": False,
            "account_health_proven": False,
            "native_codex_proven": False,
            "cli_runner_proven": False,
            "direct_egress_absence_proven": False,
            "final_e2e_proven": False,
            "current_codex_auth_json_dependency": False,
            "keychain_dependency": False,
            "original_codex_mutation": False,
            "raw_upstream_secret_exposed": False,
            "models": [dict(catalog["models"][0])],
        }
        mutated["models"][0]["speed_tier"] = {
            "label": "x1.5",
            "source": "measured",
            "proof_level": "declared",
        }

        self.assertIn(
            "models[0].speed_tier.measured_without_packet",
            validate_wbp_model_catalog_contract(mutated),
        )

    def test_wbp_api_external_models_are_prefixed_or_non_impersonating(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        wbp_lane = packets["wbp_api_model_lane_packet.json"]
        non_impersonation = packets["non_impersonation_packet.json"]

        for model in wbp_lane["models"]:
            self.assertTrue(model["display_name"].lower().startswith("wbp "))
        self.assertEqual(non_impersonation["status"], "ok")
        self.assertTrue(non_impersonation["exception_requires_wbp_prefixed_display_name"])
        self.assertFalse(non_impersonation["native_parity_claimed"])

    def test_codex_native_provider_identity_not_assumed(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        native_lane = packets["codex_native_model_lane_packet.json"]

        self.assertFalse(native_lane["physical_provider_identity_assumed"])
        self.assertTrue(native_lane["provider_class_or_source_class_only"])
        for model in native_lane["models"]:
            self.assertFalse(model["physical_provider_proven"])
            self.assertEqual(model["physical_provider"], "")

    def test_browser_remote_catalog_authority_blocked(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        authority = packets["model_catalog_authority_boundary_packet.json"]

        self.assertEqual(authority["status"], "ok")
        self.assertFalse(authority["browser_can_supply_catalog_path"])
        self.assertFalse(authority["browser_can_supply_provider"])
        self.assertFalse(authority["browser_can_supply_model_authority"])
        self.assertFalse(authority["remote_can_supply_catalog_path"])
        self.assertFalse(authority["remote_can_supply_provider"])
        self.assertFalse(authority["remote_can_supply_model_authority"])

    def test_gpt_5_5_visibility_not_availability(self) -> None:
        packets = build_model_catalog_fidelity_packets(
            operator_status(claim_gate="passed")
            | {"models": {"ok": True, "model_ids": ["gpt-5.5"], "server_issued": True}}
        )
        false_green = packets["model_catalog_fidelity_false_green_audit.json"]
        matrix = packets["model_catalog_fidelity_matrix.json"]

        self.assertEqual(matrix["status"], "ok")
        self.assertFalse(matrix["model_availability_proven"])
        self.assertFalse(false_green["gpt_5_5_visibility_claimed_as_availability"])

    def test_catalog_does_not_claim_route_or_upstream_acceptance(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        matrix = packets["model_catalog_fidelity_matrix.json"]

        self.assertFalse(matrix["route_selected_proven"])
        self.assertFalse(matrix["upstream_accepts_proven"])
        self.assertFalse(matrix["response_accepted_by_codex_proven"])


if __name__ == "__main__":
    unittest.main()
