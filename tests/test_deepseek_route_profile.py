# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for the DeepSeek route profile and credential
lifecycle contract (W07).

Covers route definition shape, credential provenance classification (owner env
admitted; browser/none not admitted), dispatch error taxonomy normalization,
profile packet contract semantics, dispatch test matrix, no-auth-material leak,
and the synthetic profile proof summary.
"""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import deepseek_route_profile as d
from wild_boar_proxy.core import packets
from wild_boar_proxy.external_models.routes import validate_route_schema
from wild_boar_proxy.external_models.transforms import build_check_request, extract_check_response


def _assert_packet_semantics(testcase: unittest.TestCase, packet: dict) -> None:
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing required: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"semantic violations: {violations}")
    if packet["status"] == "ok":
        testcase.assertEqual(packet["exit_code"], packets.COMMAND_EXIT_OK)
    else:
        testcase.assertEqual(packet["status"], "error")
        testcase.assertEqual(packet["exit_code"], packets.COMMAND_EXIT_ERROR)


class RouteDefinitionTests(unittest.TestCase):
    def test_default_route_is_deepseek_provider(self) -> None:
        route = d.build_deepseek_route_definition()
        self.assertEqual(route["provider"], d.DEEPSEEK_PROVIDER_ID)
        self.assertEqual(route["base_url"], d.DEEPSEEK_DEFAULT_BASE_URL)
        self.assertEqual(route["endpoint_path"], d.DEEPSEEK_DEFAULT_ENDPOINT_PATH)
        self.assertEqual(route["upstream_model"], d.DEEPSEEK_DEFAULT_UPSTREAM_MODEL)
        self.assertEqual(route["lane_role"], d.DEEPSEEK_LANE_ROLE)
        self.assertFalse(route["enabled"])  # disabled by default

    def test_auth_uses_bearer_with_secret_ref(self) -> None:
        route = d.build_deepseek_route_definition()
        self.assertEqual(route["auth"]["type"], "bearer")
        self.assertEqual(route["auth"]["secret_ref"], d.DEEPSEEK_CREDENTIAL_REF)

    def test_route_never_embeds_credential_value(self) -> None:
        route = d.build_deepseek_route_definition()
        body = json.dumps(route)
        self.assertNotIn("sk-", body)

    def test_default_route_passes_external_models_schema_validation(self) -> None:
        # B07: the DEFAULT deepseek route id must be schema-valid
        # (wbp- prefix required by the route schema).
        route = d.build_deepseek_route_definition()
        self.assertEqual(route["route_id"], d.DEEPSEEK_DEFAULT_ROUTE_ID)
        self.assertIs(validate_route_schema(route), route)

    def test_default_route_transform_builds_and_extracts_chat_completion(self) -> None:
        route = d.build_deepseek_route_definition(route_id="wbp-deepseek-chat")
        request_payload, request_metadata = build_check_request(
            route,
            user_prompt="ping",
        )
        self.assertEqual(request_payload["model"], d.DEEPSEEK_DEFAULT_UPSTREAM_MODEL)
        self.assertEqual(request_metadata["transform_profile"], "deepseek_default")
        text, response_metadata = extract_check_response(
            route,
            {
                "choices": [
                    {"message": {"role": "assistant", "content": "pong"}}
                ]
            },
        )
        self.assertEqual(text, "pong")
        self.assertEqual(
            response_metadata["response_profile"],
            "openai_chat_completions",
        )


class CredentialProvenanceTests(unittest.TestCase):
    def test_owner_env_present_is_proven(self) -> None:
        p = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=True,
            source_kind="owner_env",
            permissions_safe=True,
            credential_value_digest="a" * 64,
        )
        self.assertTrue(p.proven)
        self.assertTrue(p.source_admitted)

    def test_owner_cli_present_is_proven(self) -> None:
        p = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=True,
            source_kind="owner_cli",
        )
        self.assertTrue(p.proven)

    def test_missing_credential_not_proven(self) -> None:
        p = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=False,
            source_kind="owner_env",
        )
        self.assertFalse(p.proven)
        self.assertFalse(p.present)

    def test_browser_source_not_admitted(self) -> None:
        p = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=True,
            source_kind="browser",  # not admitted
        )
        self.assertFalse(p.proven)
        self.assertFalse(p.source_admitted)

    def test_provenance_digest_only_when_admitted(self) -> None:
        admitted = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=True,
            source_kind="owner_env",
            credential_value_digest="a" * 64,
        )
        not_admitted = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=True,
            source_kind="browser",
            credential_value_digest="a" * 64,
        )
        self.assertIsNotNone(admitted.provenance_digest)
        self.assertIsNone(not_admitted.provenance_digest)


class DispatchErrorTaxonomyTests(unittest.TestCase):
    def test_401_normalizes_to_invalid_credential(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=401, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_INVALID_CREDENTIAL)

    def test_403_normalizes_to_invalid_credential(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=403, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_INVALID_CREDENTIAL)

    def test_404_normalizes_to_model_not_available(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=404, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_MODEL_NOT_AVAILABLE)

    def test_429_normalizes_to_quota(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=429, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_QUOTA)

    def test_500_normalizes_to_network(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=500, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_NETWORK)

    def test_no_response_normalizes_to_network(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=None, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=False,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_NETWORK)

    def test_200_no_response_observed_normalizes_to_invalid_response(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=200, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=False,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_INVALID_RESPONSE)

    def test_200_response_observed_normalizes_to_ok(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=200, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_NON_STREAM, response_observed=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_OK)

    def test_stream_incomplete_normalizes_to_stream_incomplete(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=200, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_STREAM, response_observed=True,
            stream_complete=False,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_STREAM_INCOMPLETE)

    def test_stream_complete_normalizes_to_ok(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=200, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_STREAM, response_observed=True,
            stream_complete=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_OK)

    def test_tool_unsupported_normalizes_to_tool_unsupported(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=200, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_TOOL, response_observed=True,
            tool_call_admitted=False,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_TOOL_UNSUPPORTED)

    def test_tool_admitted_normalizes_to_ok(self) -> None:
        code = d.normalize_deepseek_dispatch_error(
            http_status=200, engine_error_code=None,
            dispatch_mode=d.DEEPSEEK_DISPATCH_MODE_TOOL, response_observed=True,
            tool_call_admitted=True,
        )
        self.assertEqual(code, d.DEEPSEEK_ERROR_OK)


class ProfilePacketContractTests(unittest.TestCase):
    def _ready_route_and_provenance(self):
        route = d.build_deepseek_route_definition(enabled=True)
        provenance = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF,
            present=True,
            source_kind="owner_env",
            permissions_safe=True,
            credential_value_digest="a" * 64,
        )
        return route, provenance

    def test_ready_profile_packet_is_ok_contract_compliant(self) -> None:
        route, provenance = self._ready_route_and_provenance()
        packet = d.build_deepseek_profile_packet(route=route, provenance=provenance)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["ready_for_live_dispatch"])

    def test_disabled_route_profile_is_ok_with_disabled_code(self) -> None:
        route = d.build_deepseek_route_definition(enabled=False)
        provenance = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF, present=True, source_kind="owner_env"
        )
        packet = d.build_deepseek_profile_packet(route=route, provenance=provenance)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], d.DEEPSEEK_ERROR_DISABLED)
        self.assertFalse(packet["ready_for_live_dispatch"])

    def test_missing_credential_profile_is_error(self) -> None:
        route = d.build_deepseek_route_definition(enabled=True)
        provenance = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF, present=False, source_kind="owner_env"
        )
        packet = d.build_deepseek_profile_packet(route=route, provenance=provenance)
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], d.DEEPSEEK_ERROR_MISSING_CREDENTIAL)

    def test_profile_packet_never_exposes_credential_value(self) -> None:
        route, provenance = self._ready_route_and_provenance()
        packet = d.build_deepseek_profile_packet(route=route, provenance=provenance)
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)


class DispatchTestMatrixTests(unittest.TestCase):
    def test_matrix_covers_all_dispatch_modes_and_error_classes(self) -> None:
        route = d.build_deepseek_route_definition(enabled=True)
        provenance = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF, present=True, source_kind="owner_env"
        )
        matrix = d.build_dispatch_test_matrix_receipt(route=route, provenance=provenance)
        self.assertGreaterEqual(len(matrix), 12)
        labels = {p["scenario"] for p in matrix}
        for required in (
            "non_stream_success", "non_stream_401", "non_stream_403",
            "non_stream_404", "non_stream_429", "non_stream_500",
            "non_stream_network_failed", "non_stream_invalid_response",
            "stream_success", "stream_incomplete",
            "tool_success", "tool_unsupported",
        ):
            self.assertIn(required, labels)

    def test_matrix_packets_contract_compliant(self) -> None:
        route = d.build_deepseek_route_definition(enabled=True)
        provenance = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF, present=True, source_kind="owner_env"
        )
        for packet in d.build_dispatch_test_matrix_receipt(route=route, provenance=provenance):
            _assert_packet_semantics(self, packet)

    def test_matrix_never_exposes_credential_value(self) -> None:
        route = d.build_deepseek_route_definition(enabled=True)
        provenance = d.classify_credential_provenance(
            credential_ref=d.DEEPSEEK_CREDENTIAL_REF, present=True, source_kind="owner_env"
        )
        for packet in d.build_dispatch_test_matrix_receipt(route=route, provenance=provenance):
            self.assertNotIn("sk-", json.dumps(packet))


class SyntheticProfileProofTests(unittest.TestCase):
    def test_synthetic_proof_is_ok_contract_compliant(self) -> None:
        packet = d.run_deepseek_synthetic_profile_proof()
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["profile_ready"])
        self.assertTrue(packet["no_auth_material_leak"])
        self.assertEqual(packet["packet_violations"], [])

    def test_synthetic_proof_never_exposes_credential_value(self) -> None:
        packet = d.run_deepseek_synthetic_profile_proof()
        self.assertNotIn("sk-", json.dumps(packet))


if __name__ == "__main__":
    unittest.main()
