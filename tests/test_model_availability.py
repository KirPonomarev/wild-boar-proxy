# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.model_availability import (
    build_candidate_model_list,
    build_catalog_availability_lattice_packet,
    build_candidate_partition_packet,
    build_default_model_source_packet,
    build_external_route_admission_packet,
    build_layer_boundary_packet,
    build_model_availability_admission_packet,
    build_model_availability_matrix,
    build_model_direct_preflight_packet,
    build_model_availability_false_green_audit,
    build_model_id_normalization_packet,
    build_no_route_account_mutation_packet,
    build_route_family_classification_packet,
    build_runtime_readiness_packet,
    build_validation_freshness_packet,
    classify_failure_cause,
    forbidden_model_browser_fields,
    validate_model_availability_contour_packets,
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
                    "provider": {"id": "openrouter"},
                    "upstream_model": "openai/gpt-5.4-mini",
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
        self.assertEqual(
            model["claim_level"],
            "direct_wbp_non_stream_response_accepted",
        )
        self.assertTrue(model["response_accepted_by_direct_wbp_client"])

    def test_model_direct_preflight_does_not_claim_codex_acceptance(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
        )

        self.assertTrue(model["request_reaches_wbp"])
        self.assertTrue(model["upstream_accepts"])
        self.assertTrue(model["direct_only_contour"])
        self.assertEqual(model["proof_transport"], "direct_wbp_http_non_stream")
        self.assertFalse(model["response_accepted_by_codex"])
        self.assertEqual(model["codex_acceptance_status"], "not_tested")
        self.assertFalse(model["direct_wbp_200_counted_as_codex_acceptance"])

    def test_model_availability_matrix_rejects_codex_acceptance_overclaim(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
        )
        model["response_accepted_by_codex"] = True
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertIn("gpt-5.4-mini.response_accepted_by_codex", matrix["overclaim_findings"])
        self.assertIn(
            "models[0].response_accepted_by_codex",
            validate_model_availability_matrix(matrix),
        )

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
        self.assertFalse(model["raw_prompt_recorded"])
        self.assertFalse(model["auth_header_recorded"])
        self.assertFalse(model["raw_upstream_secret_recorded"])
        self.assertTrue(model["prompt_hash"])
        self.assertTrue(model["request_hash_recorded"])

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

    def test_validation_freshness_blocks_stale_current_truth(self) -> None:
        packet = build_validation_freshness_packet(
            observed_at_utc="2026-05-25T00:00:00Z",
            captured_at_utc="2026-05-26T12:00:00Z",
            validation_actor="fixture",
            validation_scope="gpt-5.4-mini",
            max_age_seconds=60,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["current_truth_allowed"])
        self.assertFalse(packet["stale_validation_used_as_current_truth"])

    def test_model_availability_requires_request_hash_for_attempted_request(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            request_sent_to_wbp=True,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertIn(
            "models[0].request_hash_recorded",
            validate_model_availability_matrix(matrix),
        )

    def test_model_availability_blocks_raw_prompt_or_auth_evidence(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
        )
        model["raw_prompt_recorded"] = True
        model["auth_header_recorded"] = True
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        findings = validate_model_availability_matrix(matrix)
        self.assertIn("models[0].raw_prompt_recorded", findings)
        self.assertIn("models[0].auth_header_recorded", findings)

    def test_validation_freshness_blocks_malformed_timestamp(self) -> None:
        packet = build_validation_freshness_packet(
            observed_at_utc="not-a-timestamp",
            captured_at_utc="2026-05-26T12:00:00Z",
            validation_actor="fixture",
            validation_scope="gpt-5.4-mini",
            max_age_seconds=60,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIsNone(packet["validation_age_seconds"])
        self.assertFalse(packet["current_truth_allowed"])

    def test_validation_freshness_allows_recent_truth(self) -> None:
        packet = build_validation_freshness_packet(
            observed_at_utc="2026-05-26T11:59:30Z",
            captured_at_utc="2026-05-26T12:00:00Z",
            validation_actor="fixture",
            validation_scope="gpt-5.4-mini",
            max_age_seconds=60,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["current_truth_allowed"])

    def test_model_id_normalization_separates_catalog_and_route_identity(self) -> None:
        candidates = build_candidate_model_list(
            configured_model="gpt-5.4-mini",
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        packet = build_model_id_normalization_packet(
            candidate_packet=candidates,
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )

        self.assertEqual(packet["status"], "ok")
        rows = {row["wbp_model_id"]: row for row in packet["rows"]}
        self.assertEqual(rows["gpt-5.4-mini"]["selection_source"], "catalog")
        self.assertEqual(rows["wbp-web-primary-openrouter"]["route_id"], "wbp-web-primary-openrouter")
        self.assertEqual(rows["wbp-web-primary-openrouter"]["route_provider"], "openrouter")
        self.assertEqual(rows["wbp-web-primary-openrouter"]["upstream_model"], "openai/gpt-5.4-mini")
        self.assertNotIn("OPENROUTER_API_KEY", json.dumps(packet))

    def test_no_route_account_mutation_guard_blocks_drift(self) -> None:
        packet = build_no_route_account_mutation_packet(
            route_snapshot_before={"routes": ["a"]},
            route_snapshot_after={"routes": ["b"]},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["route_mutated"])
        self.assertFalse(packet["route_account_mutation_allowed"])

    def test_no_route_account_mutation_guard_blocks_account_drift(self) -> None:
        packet = build_no_route_account_mutation_packet(
            account_snapshot_before={"active": ["stable"]},
            account_snapshot_after={"active": ["changed"]},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["account_mutated"])
        self.assertFalse(packet["route_account_mutation_allowed"])

    def test_layer_boundary_keeps_native_egress_and_final_e2e_out(self) -> None:
        packet = build_layer_boundary_packet()

        self.assertTrue(packet["proves_model_availability_only"])
        self.assertTrue(packet["direct_only_contour"])
        self.assertEqual(packet["proof_transport"], "direct_wbp_http_non_stream")
        self.assertFalse(packet["native_app_usability_proven"])
        self.assertFalse(packet["direct_egress_absence_proven"])
        self.assertFalse(packet["final_e2e_proven"])

    def test_model_availability_false_green_audit_ties_required_packets(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )
        audit = build_model_availability_false_green_audit(
            matrix_packet=matrix,
            freshness_packet=build_validation_freshness_packet(
                observed_at_utc="2026-05-26T11:59:30Z",
                captured_at_utc="2026-05-26T12:00:00Z",
                validation_actor="fixture",
                validation_scope="gpt-5.4-mini",
                max_age_seconds=60,
            ),
            layer_boundary_packet=build_layer_boundary_packet(),
            mutation_guard_packet=build_no_route_account_mutation_packet(),
            normalization_packet=build_model_id_normalization_packet(
                candidate_packet={"candidate_model_ids": ["gpt-5.4-mini"]},
                catalog_packet=catalog_packet(),
            ),
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["direct_wbp_200_counted_as_codex_acceptance"])

    def test_validate_model_availability_contour_packets_reports_all_missing_required_packets(self) -> None:
        findings = validate_model_availability_contour_packets({})

        for packet_name in (
            "candidate_partition_packet.json",
            "default_model_source_packet.json",
            "route_family_classification_packet.json",
            "external_route_admission_packet.json",
            "model_availability_matrix.json",
        ):
            self.assertIn(f"missing.{packet_name}", findings)
        self.assertIn("model_availability_matrix.json", findings)

    def test_model_availability_candidate_partition_required(self) -> None:
        candidates = build_candidate_model_list(
            configured_model="gpt-5.4-mini",
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        normalization = build_model_id_normalization_packet(
            candidate_packet=candidates,
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        route_family = build_route_family_classification_packet(
            candidate_packet=candidates,
            normalization_packet=normalization,
        )
        partition = build_candidate_partition_packet(
            candidate_packet=candidates,
            route_family_packet=route_family,
        )

        self.assertEqual(partition["status"], "ok")
        self.assertIn("gpt-5.4-mini", partition["catalog_visible_candidates"])
        self.assertIn("wbp-web-primary-openrouter", partition["route_backed_candidates"])
        self.assertFalse(partition["catalog_visible_counted_as_availability"])

    def test_default_model_source_packet_required(self) -> None:
        candidates = build_candidate_model_list(
            configured_model="gpt-5.4-mini",
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        normalization = build_model_id_normalization_packet(
            candidate_packet=candidates,
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        route_family = build_route_family_classification_packet(
            candidate_packet=candidates,
            normalization_packet=normalization,
        )
        packet = build_default_model_source_packet(
            configured_model="gpt-5.4-mini",
            candidate_packet=candidates,
            route_family_packet=route_family,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["route_family"], "codex_native_account_route")
        self.assertFalse(packet["browser_authority"])

    def test_route_family_required_for_each_candidate(self) -> None:
        candidates = build_candidate_model_list(
            configured_model="gpt-5.4-mini",
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        normalization = build_model_id_normalization_packet(
            candidate_packet=candidates,
            catalog_packet=catalog_packet(),
            routes_packet=routes_packet(),
        )
        packet = build_route_family_classification_packet(
            candidate_packet=candidates,
            normalization_packet=normalization,
        )
        by_model = {row["model_id"]: row for row in packet["classifications"]}

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(by_model["gpt-5.4-mini"]["route_family"], "codex_native_account_route")
        self.assertEqual(by_model["wbp-web-primary-openrouter"]["route_family"], "wbp_api_external_route")

    def test_unknown_unrouted_candidate_not_smoked(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="mystery-model",
            source="unknown",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            request_sent_to_wbp=True,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertIn("models[0].unknown_unrouted_smoked", validate_model_availability_matrix(matrix))

    def test_catalog_visible_not_admitted_smoke(self) -> None:
        partition = {
            "candidate_partition_packet.json": {
                "catalog_visible_counted_as_availability": False,
                "catalog_visible_counted_as_admitted_smoke": True,
                "unknown_unrouted_smoked": False,
            },
            "model_availability_matrix.json": build_model_availability_matrix(
                [
                    build_model_direct_preflight_packet(
                        model_id="gpt-5.4-mini",
                        source="catalog",
                        listed=True,
                        selectable=True,
                        route_selected=True,
                        runtime_ready=True,
                    )
                ],
                candidate_packet={"candidate_count": 1, "sampling_limit": 5},
                runtime_packet={"runtime_ready": True},
            ),
        }

        self.assertIn(
            "candidate_partition.catalog_visible_counted_as_admitted_smoke",
            validate_model_availability_contour_packets(partition),
        )

    def test_route_backed_not_upstream_accepts_without_smoke(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            request_sent_to_wbp=False,
        )

        self.assertIn("route_selected", model["availability_levels"])
        self.assertNotIn("upstream_accepts", model["availability_levels"])
        self.assertEqual(model["claim_level"], "listed_only")

    def test_external_route_admission_requires_secret_ref_and_adapter_boundary(self) -> None:
        candidates = {"candidate_model_ids": ["wbp-web-primary-openrouter"]}
        normalization = build_model_id_normalization_packet(
            candidate_packet=candidates,
            routes_packet=routes_packet(),
        )
        route_family = build_route_family_classification_packet(
            candidate_packet=candidates,
            normalization_packet=normalization,
        )
        packet = build_external_route_admission_packet(
            route_family_packet=route_family,
            normalization_packet=normalization,
        )

        self.assertEqual(packet["status"], "ok")
        candidate = packet["external_route_candidates"][0]
        self.assertTrue(candidate["secret_ref_present"])
        self.assertTrue(candidate["adapter_boundary_packet"]["auth_boundary_classified"])
        self.assertFalse(candidate["provider_family_compatibility_claimed"])

    def test_external_route_smoke_does_not_claim_provider_family_compatibility(self) -> None:
        packet = {
            "external_route_admission_packet.json": {
                "provider_family_compatibility_claimed": True,
                "external_route_candidates": [],
            },
            "model_availability_matrix.json": build_model_availability_matrix(
                [
                    build_model_direct_preflight_packet(
                        model_id="gpt-5.4-mini",
                        source="catalog",
                        listed=True,
                        selectable=True,
                        route_selected=True,
                        runtime_ready=True,
                    )
                ],
                candidate_packet={"candidate_count": 1, "sampling_limit": 5},
                runtime_packet={"runtime_ready": True},
            ),
        }

        self.assertIn(
            "external_route_admission.provider_family_compatibility_claimed",
            validate_model_availability_contour_packets(packet),
        )

    def test_direct_wbp_non_stream_response_shape_not_codex_acceptance(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
        )

        self.assertIn("direct_wbp_non_stream_response_shape_accepted", model["availability_levels"])
        self.assertFalse(model["response_accepted_by_codex"])
        self.assertEqual(model["codex_acceptance_status"], "not_tested")

    def test_non_stream_result_not_streaming_or_tool_loop(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
        )

        self.assertFalse(model["non_stream_result_counts_for_streaming"])
        self.assertFalse(model["non_stream_result_counts_for_tool_loop"])
        self.assertEqual(model["streaming_classified"], "live_not_tested")
        self.assertEqual(model["tool_loop_classified"], "live_not_tested")

    def test_gpt_5_5_visibility_not_availability(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.5",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            request_sent_to_wbp=False,
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertEqual(matrix["gpt_5_5_claim"], "own_packet_listed_but_not_proven")

    def test_blocked_model_remains_in_matrix(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=429,
            error_payload={"error": {"type": "rate_limit_error"}},
            request_sent_to_wbp=True,
            prompt_text="Reply OK",
        )
        matrix = build_model_availability_matrix(
            [model],
            candidate_packet={"candidate_count": 1, "sampling_limit": 5},
            runtime_packet={"runtime_ready": True},
        )

        self.assertIn("gpt-5.4", matrix["models_tested"])
        self.assertEqual(matrix["models"][0]["failure_cause"], "quota_or_rate_limit")
        self.assertEqual(matrix["models"][0]["claim_level"], "blocked_with_reason")

    def test_raw_prompt_auth_secret_not_recorded(self) -> None:
        model = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
            source="catalog",
            listed=True,
            selectable=True,
            route_selected=True,
            runtime_ready=True,
            http_status=200,
            upstream_status=200,
            response_payload={"status": "completed", "output_text": "OK"},
            prompt_text="very secret prompt",
            request_sent_to_wbp=True,
        )
        serialized = json.dumps(model)

        self.assertNotIn("very secret prompt", serialized)
        self.assertFalse(model["auth_header_recorded"])
        self.assertFalse(model["raw_upstream_secret_recorded"])

    def test_model_availability_admission_requires_fresh_validation(self) -> None:
        partition = {
            "admitted_smoke_candidates": ["gpt-5.4-mini"],
            "blocked_candidates": [],
        }
        stale = build_validation_freshness_packet(
            observed_at_utc="2026-05-25T00:00:00Z",
            captured_at_utc="2026-05-26T12:00:00Z",
            validation_actor="fixture",
            validation_scope="gpt-5.4-mini",
            max_age_seconds=60,
        )
        packet = build_model_availability_admission_packet(
            candidate_partition_packet=partition,
            validation_freshness_packet=stale,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["admitted_smoke_candidates"], [])

    def test_catalog_availability_lattice_distinguishes_current_and_historical_proof(self) -> None:
        catalog = {
            "models": [
                {"model_id": "gpt-5.4-mini", "lane": "codex_native"},
                {"model_id": "wbp-web-primary-openrouter", "lane": "wbp_api"},
                {"model_id": "gpt-image-2", "lane": "codex_native"},
            ]
        }
        current = build_model_direct_preflight_packet(
            model_id="gpt-5.4-mini",
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
        historical = build_model_direct_preflight_packet(
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
        lattice = build_catalog_availability_lattice_packet(
            catalog_packet=catalog,
            current_model_packets=[current],
            historical_model_packets=[historical],
        )

        self.assertEqual(lattice["status"], "ok")
        rows = {row["model_id"]: row for row in lattice["rows"]}
        self.assertEqual(
            rows["gpt-5.4-mini"]["availability_claim_level"],
            "direct_wbp_non_stream_response_accepted",
        )
        self.assertTrue(rows["gpt-5.4-mini"]["live_availability_proven"])
        self.assertEqual(
            rows["wbp-web-primary-openrouter"]["availability_claim_level"],
            "historically_direct_wbp_non_stream_response_accepted",
        )
        self.assertFalse(rows["wbp-web-primary-openrouter"]["live_availability_proven"])
        self.assertEqual(rows["gpt-image-2"]["availability_claim_level"], "listed_not_live_proven")

    def test_catalog_availability_lattice_keeps_out_of_catalog_negative_observation(self) -> None:
        negative = build_model_direct_preflight_packet(
            model_id="gpt-5.3-codex-spark",
            source="fresh_negative_anchor",
            listed=False,
            selectable=False,
            route_selected=False,
            runtime_ready=True,
            http_status=400,
            error_payload={"error": {"type": "unsupported_model_for_chatgpt_account"}},
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
            route_family="codex_native_account_route",
        )
        lattice = build_catalog_availability_lattice_packet(
            catalog_packet={"models": [{"model_id": "gpt-5.5", "lane": "codex_native"}]},
            out_of_catalog_model_packets=[negative],
        )

        self.assertEqual(len(lattice["out_of_catalog_observations"]), 1)
        observation = lattice["out_of_catalog_observations"][0]
        self.assertEqual(observation["model_id"], "gpt-5.3-codex-spark")
        self.assertFalse(observation["listed_in_current_operator_catalog"])
        self.assertFalse(observation["catalog_expansion_allowed"])


if __name__ == "__main__":
    unittest.main()
