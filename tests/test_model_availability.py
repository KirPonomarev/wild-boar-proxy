# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.model_availability import (
    build_candidate_model_list,
    build_model_availability_matrix,
    build_model_direct_preflight_packet,
    build_runtime_readiness_packet,
    classify_failure_cause,
    forbidden_model_browser_fields,
    validate_model_availability_matrix,
)


def catalog_packet() -> dict[str, object]:
    return {
        "models": [
            {"model_id": "gpt-5.4-mini", "server_issued": True},
            {"model_id": "gpt-5.4", "server_issued": True},
            {"model_id": "gpt-5.5", "server_issued": True},
            {"model_id": "browser-forged", "server_issued": False},
        ]
    }


def routes_packet() -> dict[str, object]:
    return {
        "data": {
            "routes": [
                {
                    "route_id": "wbp-web-primary-openrouter",
                    "enabled": True,
                    "auth": {"secret_ref": "OPENROUTER_API_KEY"},
                }
            ]
        }
    }


def runtime_packet() -> dict[str, object]:
    return {
        "endpoint": "http://127.0.0.1:8318/v1",
        "liveness": "healthy",
        "launch_readiness": {
            "gate_passed": True,
            "listener_reachable": True,
            "models_surface_reachable": True,
            "responses_proof_passed": True,
            "truth_alignment_passed": True,
        },
    }


class ModelAvailabilityTests(unittest.TestCase):
    def test_runtime_readiness_requires_responses_models_and_listener(self) -> None:
        ready = build_runtime_readiness_packet({"endpoint": "x"}, runtime_packet())

        self.assertEqual(ready["status"], "ok")
        self.assertTrue(ready["runtime_ready"])

        blocked = build_runtime_readiness_packet({}, {"launch_readiness": {}})
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("endpoint_missing", blocked["failed_checks"])

    def test_sampling_limit_blocks_all_model_sweep(self) -> None:
        packet = build_candidate_model_list(
            configured_model="gpt-5.5",
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )

        self.assertLessEqual(packet["candidate_count"], packet["sampling_limit"])
        self.assertFalse(packet["all_model_sweep_attempted"])
        self.assertEqual(
            packet["candidate_model_ids"],
            ["gpt-5.5", "gpt-5.4-mini", "gpt-5.4", "wbp-web-primary-openrouter"],
        )

    def test_model_availability_requires_route_and_response(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertEqual(validate_model_availability_matrix(matrix), [])
        self.assertEqual(model["direct_preflight_status"], "passed")

    def test_model_listed_does_not_imply_usable(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.5",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            request_sent_to_wbp=False,
        )

        self.assertEqual(model["direct_preflight_status"], "blocked_or_unknown")
        self.assertEqual(model["allowed_claim"], "MODEL_gpt-5.5_LISTED_ONLY")

    def test_model_selectable_does_not_imply_upstream_accepts(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=404,
            error_payload={"error": {"type": "model_not_found"}},
            request_sent_to_wbp=True,
        )

        self.assertEqual(model["failure_cause"], "upstream_model_rejected")
        self.assertNotEqual(model["direct_preflight_status"], "passed")

    def test_model_direct_preflight_does_not_claim_native(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
        )

        self.assertFalse(model["native_tested"])
        self.assertFalse(model["owner_ui_tested"])

    def test_model_direct_preflight_does_not_claim_cli_runner(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
        )

        self.assertFalse(model["codex_cli_tested"])

    def test_model_direct_preflight_does_not_claim_egress_absence(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
        )

        self.assertFalse(model["direct_egress_tested"])

    def test_model_availability_redacts_prompt_and_auth(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="secret prompt",
            request_sent_to_wbp=True,
        )

        serialized = json.dumps(model)
        self.assertNotIn("secret prompt", serialized)
        self.assertFalse(model["prompt_body_recorded"])
        self.assertFalse(model["auth_header_recorded"])
        self.assertTrue(model["prompt_hash"])

    def test_gpt_5_5_requires_own_packet_before_claim(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertEqual(matrix["gpt_5_5_claim"], "absent_or_not_sampled")

    def test_model_availability_matrix_forbids_all_models_work(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertIn("all_models_work", matrix["forbidden_claims"])
        self.assertFalse(matrix["all_model_sweep_attempted"])

    def test_model_availability_error_shape_classified(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=500,
            error_payload={"error": {"type": "server_error"}},
            request_sent_to_wbp=True,
        )

        self.assertTrue(model["error_shape_classified"])
        self.assertEqual(model["failure_cause"], "provider_error")

    def test_model_availability_failure_cause_required(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=False,
        )

        self.assertEqual(model["failure_cause"], "wbp_runtime_unavailable")

    def test_401_403_429_503_not_model_absence_by_default(self) -> None:
        self.assertEqual(classify_failure_cause(http_status=401), "account_auth_failed")
        self.assertEqual(classify_failure_cause(http_status=403), "account_auth_failed")
        self.assertEqual(classify_failure_cause(http_status=429), "quota_or_rate_limit")
        self.assertEqual(classify_failure_cause(http_status=503), "provider_error")

    def test_validation_freshness_required_for_interpretation(self) -> None:
        ready = build_runtime_readiness_packet({"claim_gate": {"status": "blocked"}}, runtime_packet())

        self.assertTrue(ready["claim_gate_blocks_account_pool_claim"])
        self.assertFalse(ready["account_pool_health_proven"])

    def test_browser_authority_is_forbidden(self) -> None:
        findings = forbidden_model_browser_fields(
            {"model": "gpt-5.5", "route_id": "forged", "token": "fixture-token"}
        )

        self.assertIn("route_id", findings)
        self.assertIn("token", findings)


if __name__ == "__main__":
    unittest.main()
