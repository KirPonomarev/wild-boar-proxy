# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.codex_model_registry import (
    build_wbp_model_catalog_contract_packet,
    validate_wbp_model_catalog_contract,
)
from wild_boar_proxy.model_availability import (
    build_catalog_availability_lattice_packet,
    build_model_direct_preflight_packet,
)


def operator_status(*, model_ids: list[str] | None = None, claim_gate: str = "passed") -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.3-codex",
        },
        "claim_gate": {"status": claim_gate},
        "models": {
            "ok": True,
            "model_ids": model_ids or ["gpt-5.4", "gpt-5.3-codex"],
            "server_issued": True,
        },
    }


def api_snapshot() -> dict[str, object]:
    return {
        "routes": [
            {
                "route_id": "wbp-web-primary-openrouter",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
                "upstream_model": "openrouter/upstream",
            },
            {
                "route_id": "wbp-disabled-route",
                "enabled": False,
                "secret_ref": "DISABLED_SECRET",
            },
            {
                "route_id": "wbp-missing-secret",
                "enabled": True,
            },
        ]
    }


def availability_lattice_for(*model_ids: str) -> dict[str, object]:
    catalog = build_wbp_model_catalog_contract_packet(
        operator_status(model_ids=list(model_ids)),
        api_snapshot=api_snapshot(),
    )
    current_packets = [
        build_model_direct_preflight_packet(
            model_id=model_id,
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
        for model_id in model_ids
        if model_id.startswith("gpt-")
    ]
    historical_packets = []
    if "wbp-web-primary-openrouter" in model_ids:
        historical_packets.append(
            build_model_direct_preflight_packet(
                model_id="wbp-web-primary-openrouter",
                source="pass2_selected_route",
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
        )
    return build_catalog_availability_lattice_packet(
        catalog_packet=catalog,
        current_model_packets=current_packets,
        historical_model_packets=historical_packets,
    )


class WbpModelCatalogContractTests(unittest.TestCase):
    def test_wbp_model_catalog_generated_by_server(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status(), api_snapshot=api_snapshot())

        self.assertEqual(packet["catalog_generated_by"], "wbp_server")
        self.assertEqual(
            packet["catalog_source"],
            "server_owned_operator_status_plus_external_route_registry",
        )
        self.assertTrue(packet["server_owned_source"])
        self.assertEqual(packet["contract_scope"], "provider_catalog_only")
        self.assertEqual(validate_wbp_model_catalog_contract(packet), [])

    def test_wbp_model_catalog_schema_required_fields(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status(), api_snapshot=api_snapshot())

        required_fields = {
            "schema_version",
            "status",
            "machine_error_code",
            "captured_at_utc",
            "model_provider",
            "base_url",
            "wire_api",
            "default_model",
            "default_model_explicit",
            "model_count",
            "models",
            "allowed_claims",
            "forbidden_claims",
            "claim_limits",
        }
        self.assertFalse(required_fields - packet.keys())
        for entry in packet["models"]:
            self.assertFalse(
                {
                    "model_id",
                    "label",
                    "source",
                    "provider_class",
                    "provider_label",
                    "server_issued",
                    "selection_enabled",
                    "selection_state",
                    "availability_claim_level",
                    "capabilities",
                }
                - entry.keys()
            )

    def test_wbp_model_catalog_no_browser_authority(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status())

        self.assertTrue(packet["browser_authority"])
        self.assertTrue(all(value is False for value in packet["browser_authority"].values()))
        self.assertEqual(packet["allowed_browser_fields"], ["model_id"])
        for forbidden in ("route_id", "backend_id", "auth_path", "model_provider", "base_url", "wire_api"):
            self.assertIn(forbidden, packet["forbidden_browser_fields"])

    def test_wbp_model_catalog_server_issued_model_ids(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status(), api_snapshot=api_snapshot())

        model_ids = [entry["model_id"] for entry in packet["models"]]
        self.assertEqual(model_ids, sorted(model_ids))
        self.assertIn("gpt-5.3-codex", model_ids)
        self.assertIn("wbp-web-primary-openrouter", model_ids)
        self.assertIn("wbp-disabled-route", model_ids)
        self.assertIn("wbp-missing-secret", model_ids)
        self.assertTrue(all(entry["server_issued"] is True for entry in packet["models"]))
        self.assertTrue(all(entry["model_id_authority"] == "server_issued" for entry in packet["models"]))

        rows = {entry["model_id"]: entry for entry in packet["models"]}
        self.assertFalse(rows["wbp-disabled-route"]["selection_enabled"])
        self.assertEqual(rows["wbp-disabled-route"]["selection_state"], "disabled")
        self.assertEqual(
            rows["wbp-disabled-route"]["selection_disabled_reason_code"],
            "ROUTE_DISABLED",
        )
        self.assertFalse(rows["wbp-missing-secret"]["selection_enabled"])
        self.assertEqual(
            rows["wbp-missing-secret"]["selection_disabled_reason_code"],
            "SECRET_REF_MISSING",
        )

    def test_wbp_model_catalog_default_model_explicit(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(
            operator_status(model_ids=["gpt-5.3-codex"]),
            recommended_default_model="gpt-5.3-codex",
        )

        self.assertEqual(packet["default_model"], "gpt-5.3-codex")
        self.assertTrue(packet["default_model_explicit"])
        self.assertTrue(packet["default_model_in_catalog"])

    def test_wbp_model_catalog_capability_claims_classified(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status())

        for entry in packet["models"]:
            capabilities = entry["capabilities"]
            self.assertEqual(capabilities["responses"]["status"], "shape_declared")
            self.assertFalse(capabilities["responses"]["live_acceptance_proven_by_catalog"])
            self.assertEqual(capabilities["chat_completions"]["status"], "shape_declared")
            self.assertFalse(capabilities["chat_completions"]["live_acceptance_proven_by_catalog"])
            self.assertEqual(capabilities["streaming"]["status"], "classified_elsewhere")
            self.assertEqual(capabilities["context_window"]["status"], "unclassified")

    def test_wbp_model_catalog_unsupported_capabilities_not_advertised(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status())

        for entry in packet["models"]:
            self.assertFalse(entry["unsupported_capabilities_advertised"])
            self.assertFalse(entry["capabilities"]["tools"]["advertised"])
            self.assertFalse(entry["capabilities"]["images"]["advertised"])
            self.assertFalse(entry["capabilities"]["reasoning"]["advertised"])

    def test_wbp_model_catalog_no_current_codex_auth_json_dependency(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status())

        self.assertFalse(packet["current_codex_auth_json_dependency"])
        self.assertFalse(packet["keychain_dependency"])
        self.assertFalse(packet["original_codex_mutation"])
        self.assertNotIn(".codex/auth.json", json.dumps(packet))
        self.assertNotIn("Library/Application Support/Codex", json.dumps(packet))

    def test_wbp_model_catalog_does_not_claim_live_availability(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status(model_ids=["gpt-5.5"]))

        self.assertFalse(packet["live_api_checked"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["inference_called"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["account_health_proven"])
        self.assertIn("gpt_5_5_works", packet["forbidden_claims"])
        self.assertTrue(all(entry["live_availability_proven"] is False for entry in packet["models"]))
        self.assertTrue(
            all(entry["availability_claim_level"] == "listed_not_live_proven" for entry in packet["models"])
        )

    def test_wbp_model_catalog_imports_current_native_availability_lattice(self) -> None:
        lattice = availability_lattice_for("gpt-5.4", "gpt-5.3-codex")
        packet = build_wbp_model_catalog_contract_packet(
            operator_status(model_ids=["gpt-5.4", "gpt-5.3-codex"]),
            api_snapshot=api_snapshot(),
            availability_lattice_packet=lattice,
        )

        rows = {entry["model_id"]: entry for entry in packet["models"]}
        self.assertTrue(packet["availability_lattice_imported"])
        self.assertEqual(packet["availability_lattice_status"], "ok")
        self.assertEqual(
            rows["gpt-5.4"]["availability_claim_level"],
            "direct_wbp_non_stream_response_accepted",
        )
        self.assertTrue(rows["gpt-5.4"]["live_availability_proven"])
        self.assertEqual(
            rows["gpt-5.4"]["availability_evidence_scope"],
            "current_thread_direct_wbp_non_stream",
        )

    def test_wbp_model_catalog_imports_historical_external_lane_boundedly(self) -> None:
        lattice = availability_lattice_for("gpt-5.4", "wbp-web-primary-openrouter")
        packet = build_wbp_model_catalog_contract_packet(
            operator_status(model_ids=["gpt-5.4"]),
            api_snapshot=api_snapshot(),
            availability_lattice_packet=lattice,
        )

        rows = {entry["model_id"]: entry for entry in packet["models"]}
        self.assertEqual(
            rows["wbp-web-primary-openrouter"]["availability_claim_level"],
            "historically_direct_wbp_non_stream_response_accepted",
        )
        self.assertFalse(rows["wbp-web-primary-openrouter"]["live_availability_proven"])
        self.assertEqual(
            rows["wbp-web-primary-openrouter"]["availability_evidence_scope"],
            "pass2_selected_external_route_closed_truth",
        )

    def test_wbp_model_catalog_does_not_claim_native_or_egress_proof(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status())

        self.assertFalse(packet["native_codex_proven"])
        self.assertFalse(packet["cli_runner_proven"])
        self.assertFalse(packet["direct_egress_absence_proven"])
        self.assertFalse(packet["final_e2e_proven"])
        self.assertFalse(packet["claim_limits"]["catalog_proves_native"])
        self.assertFalse(packet["claim_limits"]["catalog_proves_egress"])
        self.assertFalse(packet["claim_limits"]["catalog_proves_route"])


if __name__ == "__main__":
    unittest.main()
