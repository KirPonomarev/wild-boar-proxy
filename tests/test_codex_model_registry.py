# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.codex_model_registry import (
    build_model_catalog_fidelity_packets,
    build_custom_api_compat_packet,
    build_custom_codex_execution_mode_selector_packet,
    build_custom_model_dry_run_packet,
    build_custom_model_registry_packet,
    forbidden_custom_model_fields,
    validate_wbp_model_catalog_contract,
)
from wild_boar_proxy.model_availability import (
    build_catalog_availability_lattice_packet,
    build_model_direct_preflight_packet,
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


def availability_lattice() -> dict[str, object]:
    catalog = {
        "models": [
            {"model_id": "gpt-5.3-codex", "lane": "codex_native"},
            {"model_id": "gpt-5.4", "lane": "codex_native"},
            {"model_id": "direct-mistral-devstral-2512", "lane": "wbp_api"},
        ]
    }
    current_packets = [
        build_model_direct_preflight_packet(
            model_id="gpt-5.3-codex",
            source="current_thread_anchor",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
            route_family="codex_native_account_route",
        )
    ]
    historical_packets = [
        build_model_direct_preflight_packet(
            model_id="direct-mistral-devstral-2512",
            source="historical_external_anchor",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
            route_family="wbp_api_external_route",
        )
    ]
    return build_catalog_availability_lattice_packet(
        catalog_packet=catalog,
        current_model_packets=current_packets,
        historical_model_packets=historical_packets,
    )


def api_snapshot_with_deepseek() -> dict[str, object]:
    return {
        "routes": [
            {
                "route_id": "wbp-deepseek-v3",
                "provider": "deepseek",
                "upstream_model": "deepseek-chat",
                "enabled": True,
                "secret_ref": "DEEPSEEK_API_KEY",
            }
        ]
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
        self.assertEqual(first_model["provider_label"], "Codex native")
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
        self.assertTrue(first_model["selection_enabled"])
        self.assertEqual(first_model["selection_state"], "selectable")
        self.assertEqual(first_model["selection_disabled_reason_code"], "")
        self.assertEqual(first_model["selection_disabled_reasons"], [])
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

    def test_model_dry_run_rejects_visible_but_disabled_catalog_entry(self) -> None:
        packet = build_custom_model_dry_run_packet(
            {"model_id": "wbp-disabled-openrouter"},
            operator_status(claim_gate="passed"),
            api_snapshot={
                "routes": [
                    {
                        "route_id": "wbp-disabled-openrouter",
                        "provider": "openrouter",
                        "upstream_model": "openai/gpt-5",
                        "enabled": False,
                        "secret_ref": "OPENROUTER_API_KEY",
                    }
                ]
            },
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "MODEL_NOT_SELECTABLE")
        self.assertTrue(packet["model_server_issued"])
        self.assertFalse(packet["selected_model_selectable"])
        self.assertEqual(packet["selection_state"], "disabled")
        self.assertEqual(packet["selection_disabled_reason_code"], "ROUTE_DISABLED")

    def test_custom_codex_execution_mode_packets_bind_slots_without_live_claims(self) -> None:
        chatgpt_only = build_custom_codex_execution_mode_selector_packet(
            {"execution_mode": "chatgpt_only"},
            operator_status(claim_gate="passed"),
            api_snapshot=api_snapshot_with_deepseek(),
        )
        chatgpt_api = build_custom_codex_execution_mode_selector_packet(
            {"execution_mode": "chatgpt_api", "api_model_id": "wbp-deepseek-v3"},
            operator_status(claim_gate="passed"),
            api_snapshot=api_snapshot_with_deepseek(),
        )
        api_only = build_custom_codex_execution_mode_selector_packet(
            {"execution_mode": "api_only", "api_model_id": "wbp-deepseek-v3"},
            operator_status(claim_gate="passed"),
            api_snapshot=api_snapshot_with_deepseek(),
        )

        self.assertEqual(chatgpt_only["status"], "ok")
        self.assertEqual(
            chatgpt_only["final_status"],
            "CUSTOM_CODEX_EXECUTION_MODE_SELECTOR_PACKET_PROVEN_NO_LIVE_EXECUTION",
        )
        self.assertEqual(chatgpt_only["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertEqual(chatgpt_only["api_model_id"], "")
        self.assertEqual(
            chatgpt_only["coding_agent_model_slot"]["status"],
            "not_bound_for_mode",
        )
        self.assertFalse(chatgpt_only["api_line_used_as_executor"])
        self.assertFalse(chatgpt_only["chatgpt_only_calls_api"])

        self.assertEqual(chatgpt_api["status"], "ok")
        self.assertEqual(chatgpt_api["primary_model_slot"]["lane"], "codex_account_lane")
        self.assertEqual(chatgpt_api["coding_agent_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(chatgpt_api["coding_agent_model_slot"]["model_id"], "wbp-deepseek-v3")
        self.assertTrue(chatgpt_api["dual_lane_slots_preserved"])

        self.assertEqual(api_only["status"], "ok")
        self.assertEqual(api_only["primary_model_slot"]["lane"], "api_route_lane")
        self.assertEqual(api_only["primary_model_slot"]["model_id"], "wbp-deepseek-v3")
        self.assertEqual(
            api_only["coding_agent_model_slot"]["reason"],
            "api_only_uses_primary_model_slot",
        )
        self.assertFalse(api_only["chatgpt_line_used_as_executor"])
        self.assertFalse(api_only["api_only_calls_chatgpt"])
        self.assertFalse(api_only["live_call_attempted"])
        self.assertFalse(api_only["provider_called"])
        self.assertFalse(api_only["original_codex_touched"])
        self.assertFalse(api_only["asar_touched"])
        self.assertFalse(api_only["wbp_patch_applier_used"])
        self.assertTrue(api_only["selector_packet_truth_only"])
        self.assertFalse(api_only["ui_text_counts_as_runtime_truth"])

    def test_custom_codex_execution_mode_rejects_raw_backend_fields_and_unknown_api(self) -> None:
        rejected = build_custom_codex_execution_mode_selector_packet(
            {
                "execution_mode": "api_only",
                "api_model_id": "wbp-deepseek-v3",
                "base_url": "https://browser.invalid/v1",
                "route_config": {"secret_ref": "BROWSER_SECRET_REF"},
                "CODEX_HOME": "/tmp/browser-codex-home",
                "api_key": "browser-key",
            },
            operator_status(claim_gate="passed"),
            api_snapshot=api_snapshot_with_deepseek(),
        )
        unknown = build_custom_codex_execution_mode_selector_packet(
            {"execution_mode": "api_only", "api_model_id": "browser-invented-model"},
            operator_status(claim_gate="passed"),
            api_snapshot=api_snapshot_with_deepseek(),
        )

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(
            rejected["machine_error_code"],
            "CUSTOM_CODEX_EXECUTION_MODE_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertIn("base_url", rejected["forbidden_fields"])
        self.assertIn("route_config", rejected["forbidden_fields"])
        self.assertIn("route_config.secret_ref", rejected["forbidden_fields"])
        self.assertIn("CODEX_HOME", rejected["forbidden_fields"])
        self.assertIn("api_key", rejected["forbidden_fields"])
        self.assertFalse(rejected["live_call_attempted"])
        self.assertTrue(rejected["browser_raw_backend_authority_widened"])

        self.assertEqual(unknown["status"], "rejected")
        self.assertEqual(
            unknown["machine_error_code"],
            "CUSTOM_CODEX_EXECUTION_MODE_API_MODEL_NOT_SERVER_ISSUED",
        )
        self.assertFalse(unknown["live_call_attempted"])

    def test_external_route_entries_can_be_visible_but_disabled(self) -> None:
        registry = build_custom_model_registry_packet(
            operator_status(claim_gate="passed"),
            api_snapshot={
                "routes": [
                    {
                        "route_id": "wbp-disabled-openrouter",
                        "provider": "openrouter",
                        "upstream_model": "openai/gpt-5",
                        "enabled": False,
                        "secret_ref": "OPENROUTER_API_KEY",
                    },
                    {
                        "route_id": "wbp-missing-secret",
                        "provider": "openrouter",
                        "upstream_model": "openai/gpt-5-mini",
                        "enabled": True,
                    },
                ]
            },
        )

        rows = {entry["model_id"]: entry for entry in registry["available_models"]}
        self.assertIn("wbp-disabled-openrouter", rows)
        self.assertIn("wbp-missing-secret", rows)
        self.assertEqual(registry["disabled_model_count"], 3)
        self.assertFalse(rows["direct-mistral-devstral-2512"]["selection_enabled"])
        self.assertEqual(
            rows["direct-mistral-devstral-2512"]["selection_disabled_reason_code"],
            "HEURISTIC_ONLY_NOT_EXECUTABLE",
        )
        self.assertFalse(rows["wbp-disabled-openrouter"]["selection_enabled"])
        self.assertEqual(rows["wbp-disabled-openrouter"]["selection_state"], "disabled")
        self.assertEqual(
            rows["wbp-disabled-openrouter"]["selection_disabled_reason_code"],
            "ROUTE_DISABLED",
        )
        self.assertEqual(
            rows["wbp-disabled-openrouter"]["selection_disabled_reasons"],
            ["route_disabled"],
        )
        self.assertFalse(rows["wbp-missing-secret"]["selection_enabled"])
        self.assertEqual(
            rows["wbp-missing-secret"]["selection_disabled_reason_code"],
            "SECRET_REF_MISSING",
        )
        self.assertEqual(
            rows["wbp-missing-secret"]["selection_disabled_reasons"],
            ["secret_ref_missing"],
        )
        self.assertEqual(rows["wbp-missing-secret"]["provider_label"], "openrouter via WBP")

    def test_current_live_native_failure_disables_selection_without_hiding_row(self) -> None:
        catalog = {"models": [{"model_id": "gpt-5.3-codex", "lane": "codex_native"}]}
        current_packets = [
            build_model_direct_preflight_packet(
                model_id="gpt-5.3-codex",
                source="current_live_native_probe",
                listed=True,
                selectable=True,
                route_selected=True,
                runtime_ready=True,
                http_status=503,
                error_payload={
                    "machine_error_code": "AUTH_UNAVAILABLE",
                    "error": {"type": "auth_error"},
                },
                prompt_text="Reply OK",
                request_sent_to_wbp=True,
                route_family="codex_native_account_route",
            )
        ]
        lattice = build_catalog_availability_lattice_packet(
            catalog_packet=catalog,
            current_model_packets=current_packets,
        )

        registry = build_custom_model_registry_packet(
            operator_status(claim_gate="passed"),
            availability_lattice_packet=lattice,
        )

        row = next(entry for entry in registry["available_models"] if entry["model_id"] == "gpt-5.3-codex")
        self.assertFalse(row["selection_enabled"])
        self.assertEqual(row["selection_state"], "disabled")
        self.assertEqual(row["selection_disabled_reason_code"], "ACCOUNT_AUTH_UNAVAILABLE")
        self.assertIn("account_auth_failed", row["selection_disabled_reasons"])
        self.assertEqual(row["availability_claim_level"], "listed_not_live_proven")
        self.assertTrue(registry["live_api_checked"])
        self.assertTrue(registry["network_calls_made"])
        self.assertTrue(registry["inference_called"])

    def test_codex_prefixed_model_is_classified_as_native_lane(self) -> None:
        registry = build_custom_model_registry_packet(
            {
                "status": {"configured_model": "codex-auto-review"},
                "claim_gate": {"status": "passed"},
                "models": {"ok": True, "model_ids": ["codex-auto-review"]},
            }
        )

        row = registry["available_models"][0]
        self.assertEqual(row["lane"], "codex_native")
        self.assertEqual(row["model_lane"], "codex_account_lane")
        self.assertTrue(row["model_lane_classified"])
        self.assertEqual(row["model_lane_classification_source"], "server_model_catalog")
        self.assertFalse(row["model_lane_fallback_used"])
        self.assertFalse(row["runtime_lane_proven"])
        self.assertEqual(row["provider_label"], "Codex native")

    def test_server_issued_non_gpt_model_can_be_native_lane_from_catalog_metadata(self) -> None:
        registry = build_custom_model_registry_packet(
            {
                "status": {"configured_model": "orion-native"},
                "claim_gate": {"status": "passed"},
                "models": {
                    "ok": True,
                    "server_issued": True,
                    "model_entries": [
                        {"model_id": "orion-native", "lane": "codex_native"},
                    ],
                },
            }
        )

        row = registry["available_models"][0]
        self.assertEqual(row["model_id"], "orion-native")
        self.assertEqual(row["lane"], "codex_native")
        self.assertEqual(row["model_lane"], "codex_account_lane")
        self.assertTrue(row["model_lane_classified"])
        self.assertEqual(row["model_lane_classification_source"], "server_model_catalog")
        self.assertFalse(row["model_lane_fallback_used"])
        self.assertFalse(row["heuristic_only_not_executable"])
        self.assertTrue(row["selection_enabled"])
        self.assertEqual(row["provider_label"], "Codex native")

    def test_gpt_prefixed_unknown_catalog_model_is_heuristic_only_not_executable(self) -> None:
        registry = build_custom_model_registry_packet(
            {
                "status": {"configured_model": "gpt-unknown-local"},
                "claim_gate": {"status": "passed"},
                "models": {
                    "ok": True,
                    "server_issued": True,
                    "model_ids": ["gpt-unknown-local"],
                },
            }
        )

        row = registry["available_models"][0]
        self.assertEqual(row["model_id"], "gpt-unknown-local")
        self.assertEqual(row["model_lane"], "unknown_lane")
        self.assertFalse(row["model_lane_classified"])
        self.assertEqual(row["model_lane_classification_source"], "fallback_name_heuristic")
        self.assertTrue(row["model_lane_fallback_used"])
        self.assertEqual(row["heuristic_model_lane"], "codex_account_lane")
        self.assertTrue(row["heuristic_only_not_executable"])
        self.assertEqual(row["model_lane_proof_level"], "heuristic_only_not_executable")
        self.assertFalse(row["selection_enabled"])
        self.assertEqual(row["selection_disabled_reason_code"], "HEURISTIC_ONLY_NOT_EXECUTABLE")

    def test_gpt_prefixed_external_route_uses_api_lane_from_server_snapshot(self) -> None:
        registry = build_custom_model_registry_packet(
            operator_status(claim_gate="passed"),
            api_snapshot={
                "routes": [
                    {
                        "route_id": "gpt-external-route",
                        "provider": "openrouter",
                        "upstream_model": "openrouter/gpt-upstream",
                        "enabled": True,
                        "secret_ref": "OPENROUTER_API_KEY",
                    }
                ]
            },
        )

        row = next(entry for entry in registry["available_models"] if entry["model_id"] == "gpt-external-route")
        self.assertEqual(row["lane"], "wbp_api")
        self.assertEqual(row["model_lane"], "api_route_lane")
        self.assertTrue(row["model_lane_classified"])
        self.assertEqual(row["model_lane_classification_source"], "server_api_route_snapshot")
        self.assertFalse(row["model_lane_fallback_used"])
        self.assertEqual(row["model_lane_proof_level"], "server_classified")
        self.assertFalse(row["runtime_lane_proven"])

    def test_api_route_snapshot_replaces_heuristic_catalog_duplicate(self) -> None:
        registry = build_custom_model_registry_packet(
            {
                "status": {"configured_model": "gpt-5.3-codex"},
                "claim_gate": {"status": "passed"},
                "models": {
                    "ok": True,
                    "model_ids": ["gpt-5.3-codex", "wbp-deepseek-v3"],
                    "server_issued": True,
                },
            },
            api_snapshot={
                "routes": [
                    {
                        "route_id": "wbp-deepseek-v3",
                        "provider": "openrouter",
                        "upstream_model": "deepseek/deepseek-chat",
                        "enabled": True,
                        "secret_ref": "OPENROUTER_API_KEY",
                    }
                ]
            },
        )

        rows = [
            entry
            for entry in registry["available_models"]
            if entry["model_id"] == "wbp-deepseek-v3"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "server_owned_external_route")
        self.assertEqual(rows[0]["model_lane"], "api_route_lane")
        self.assertTrue(rows[0]["model_lane_classified"])
        self.assertFalse(rows[0]["model_lane_fallback_used"])
        self.assertTrue(rows[0]["selection_enabled"])

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

    def test_current_catalog_tiers_remain_unknown_unproven_without_stronger_metadata(self) -> None:
        packets = build_model_catalog_fidelity_packets(operator_status(claim_gate="passed"))
        display = packets["model_display_metadata_packet.json"]

        for model in display["models"]:
            self.assertEqual(model["intelligence_tier"]["label"], "unavailable_unknown")
            self.assertEqual(model["intelligence_tier"]["source"], "unavailable_unknown")
            self.assertEqual(model["intelligence_tier"]["proof_level"], "unproven")
            self.assertEqual(model["speed_tier"]["label"], "unavailable_unknown")
            self.assertEqual(model["speed_tier"]["source"], "unavailable_unknown")
            self.assertEqual(model["speed_tier"]["proof_level"], "unproven")

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
        mutated["models"][0]["availability_evidence_scope"] = "current_operator_catalog_only"
        mutated["models"][0]["availability_levels"] = ["listed"]
        mutated["models"][0]["direct_wbp_non_stream_response_accepted"] = False
        mutated["models"][0]["request_reaches_wbp_proven"] = False
        mutated["models"][0]["upstream_accepts_proven"] = False
        mutated["models"][0]["current_stability_proven"] = False
        mutated["models"][0]["bounded_limitations"] = []

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

    def test_catalog_fidelity_can_import_availability_lattice_without_collapsing_lanes(self) -> None:
        packets = build_model_catalog_fidelity_packets(
            operator_status(claim_gate="passed"),
            availability_lattice_packet=availability_lattice(),
        )

        native_models = {
            model["model_id"]: model
            for model in packets["codex_native_model_lane_packet.json"]["models"]
        }
        wbp_models = {
            model["model_id"]: model
            for model in packets["wbp_api_model_lane_packet.json"]["models"]
        }

        self.assertEqual(
            native_models["gpt-5.3-codex"]["availability_claim_level"],
            "direct_wbp_non_stream_response_accepted",
        )
        self.assertTrue(native_models["gpt-5.3-codex"]["live_availability_proven"])
        self.assertEqual(
            wbp_models["direct-mistral-devstral-2512"]["availability_claim_level"],
            "historically_direct_wbp_non_stream_response_accepted",
        )
        self.assertFalse(wbp_models["direct-mistral-devstral-2512"]["live_availability_proven"])


if __name__ == "__main__":
    unittest.main()
