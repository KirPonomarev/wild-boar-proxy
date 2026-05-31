# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest
from pathlib import Path

from wild_boar_proxy.provider_auth_strategy import (
    build_auth_command_output_format_packet,
    build_auth_strategy_decision_matrix,
    build_auth_strategy_false_green_audit,
    build_auth_token_boundary_packet,
    build_authority_boundary_packet,
    build_current_codex_auth_independence_packet,
    build_file_auth_fallback_deferred_packet,
    build_file_auth_fallback_exclusion_packet,
    build_file_auth_non_substitution_packet,
    build_no_ambient_authority_packet,
    build_provider_auth_account_boundary_packet,
    build_provider_auth_ambient_authority_guard_packet,
    build_provider_auth_browser_authority_packet,
    build_provider_auth_client_authority_rejection_packet,
    build_provider_auth_credential_reference_packet,
    build_provider_auth_env_authority_limit_packet,
    build_provider_auth_failure_semantics_packet,
    build_provider_auth_fallback_matrix_packet,
    build_provider_auth_file_vs_proxy_boundary_packet,
    build_provider_auth_precedence_false_green_audit,
    build_provider_auth_precedence_contract_packet,
    build_provider_auth_precedence_discovery_packet,
    build_provider_auth_precedence_packet,
    build_provider_auth_reserve_account_non_promotion_packet,
    build_provider_auth_runtime_claim_limits_packet,
    build_provider_auth_secret_boundary_packet,
    build_provider_auth_secret_redaction_packet,
    build_provider_auth_source_inventory_packet,
    build_provider_auth_strategy_contract_packet,
    build_provider_auth_strategy_packet,
    build_provider_auth_summary_packet,
    redact_provider_auth_text,
    build_secret_source_confusion_guard_packet,
    classify_native_config_auth_surface,
    validate_provider_auth_strategy_packet,
)


AUTH_COMMAND = Path(__file__).resolve().parents[1] / "wbp_codex_auth_command.py"


def auth_command_config() -> str:
    return (
        'model = "gpt-5.4-mini"\n'
        'model_provider = "wbp"\n\n'
        "[model_providers.wbp]\n"
        'base_url = "http://127.0.0.1:8318/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n\n"
        "[model_providers.wbp.auth]\n"
        f'command = "{AUTH_COMMAND}"\n'
    )


def bearer_config(token: str = "fixture-token") -> str:
    return (
        'model = "gpt-5.4-mini"\n'
        'model_provider = "wbp"\n\n'
        "[model_providers.wbp]\n"
        'base_url = "http://127.0.0.1:8318/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n"
        f'experimental_bearer_token = "{token}"\n'
    )


class ProviderAuthStrategyTests(unittest.TestCase):
    def test_provider_auth_strategy_precedence_required(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=auth_command_config(),
        )

        self.assertEqual(packet["preferred_strategy"], "auth.command")
        self.assertEqual(packet["selected_strategy"], "auth.command")
        self.assertEqual(validate_provider_auth_strategy_packet(packet), [])

    def test_auth_command_is_preferred_strategy(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        auth_command = packet["auth_command"]
        self.assertTrue(auth_command["server_owned_path"])
        self.assertEqual(auth_command["output_shape"], "plain_token_stdout")
        self.assertEqual(auth_command["scope"], "owner_local_listener")
        self.assertFalse(auth_command["raw_upstream_secret"])
        self.assertFalse(auth_command["browser_supplied"])

    def test_experimental_bearer_token_requires_explicit_contract(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "experimental_bearer_token_without_explicit_contract",
            validate_provider_auth_strategy_packet(packet),
        )

    def test_bounded_bearer_fallback_redacts_secret(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=True,
        )

        self.assertEqual(packet["status"], "ok")
        serialized = json.dumps(packet)
        self.assertNotIn("fixture-token", serialized)
        self.assertIn("<redacted>", packet["native_config_auth_surface"]["redacted_config"])
        self.assertTrue(packet["fallbacks"]["bounded_local_bearer"]["allowed"])
        self.assertTrue(packet["fallbacks"]["bounded_local_bearer"]["temporary"])
        self.assertFalse(packet["fallbacks"]["bounded_local_bearer"]["silent_fallback_allowed"])

    def test_file_auth_cannot_satisfy_proxy_auth_contract(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        file_auth = packet["fallbacks"]["file_auth_separate_contour"]
        self.assertFalse(file_auth["allowed_in_this_contour"])
        self.assertTrue(file_auth["requires_separate_contour"])
        self.assertFalse(file_auth["can_satisfy_proxy_auth_contract"])

    def test_secret_redaction_for_provider_auth_packets(self) -> None:
        surface = classify_native_config_auth_surface(
            bearer_config(),
            explicit_bearer_contract=True,
        )

        self.assertTrue(surface["raw_secret_in_input_config"])
        self.assertFalse(surface["raw_secret_after_redaction"])
        self.assertNotIn("fixture-token", json.dumps(surface))

    def test_redact_provider_auth_text_covers_bearer_and_openai_key_shapes(self) -> None:
        text = (
            'experimental_bearer_token = "fixture-token"\n'
            "Authorization: Bearer abcdefghijklmnop\n"
            "OPENAI_API_KEY=sk-test-secret-value\n"
        )
        redacted = redact_provider_auth_text(text)

        self.assertNotIn("fixture-token", redacted)
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertNotIn("sk-test-secret-value", redacted)
        self.assertIn('experimental_bearer_token = "<redacted>"', redacted)
        self.assertIn("Bearer <redacted-token>", redacted)
        self.assertIn("OPENAI_API_KEY=<redacted-token>", redacted)

    def test_no_browser_authority_for_auth_strategy(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            browser_payload={"token": "sk-browser-forged", "model": "gpt-5.5"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("browser_auth_authority_detected", packet["failed_checks"])
        self.assertIn("token", packet["browser_authority"]["forbidden_fields"])
        self.assertIn("model", packet["browser_authority"]["forbidden_fields"])

    def test_remote_client_cannot_supply_auth_authority(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            remote_payload={
                "auth_command": "/tmp/evil",
                "provider": "forged",
                "token": "remote-token",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("remote_auth_authority_detected", packet["failed_checks"])
        self.assertIn("auth_command", packet["remote_authority"]["forbidden_fields"])
        self.assertIn("provider", packet["remote_authority"]["forbidden_fields"])
        self.assertIn("token", packet["remote_authority"]["forbidden_fields"])

    def test_auth_strategy_false_green_blocks_silent_fallback(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=False,
        )

        self.assertIn("experimental_bearer_token_without_explicit_contract", packet["failed_checks"])
        self.assertNotEqual(validate_provider_auth_strategy_packet(packet), [])

    def test_native_provider_config_does_not_silently_choose_bearer(self) -> None:
        surface = classify_native_config_auth_surface(
            bearer_config(),
            explicit_bearer_contract=True,
        )

        self.assertTrue(surface["experimental_bearer_token_configured"])
        self.assertTrue(surface["bounded_bearer_contract_explicit"])
        self.assertFalse(surface["silent_bearer_fallback_allowed"])
        self.assertEqual(surface["classification_scope"], "auth_surface_only")

    def test_auth_strategy_packet_marks_native_launch_not_attempted(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        self.assertFalse(packet["claims"]["native_launch_attempted"])
        self.assertFalse(packet["claims"]["native_safety_proven"])
        self.assertFalse(packet["claims"]["native_routing_proven"])
        self.assertFalse(packet["claims"]["native_ux_proven"])

    def test_auth_strategy_packet_marks_model_availability_not_proven(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        self.assertFalse(packet["claims"]["model_availability_proven"])
        self.assertFalse(packet["claims"]["account_pool_validity_proven"])
        self.assertFalse(packet["claims"]["direct_egress_absence_proven"])
        self.assertFalse(packet["claims"]["final_e2e_proven"])

    def test_auth_strategy_decision_matrix_classifies_all_lanes(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=True,
        )
        matrix = build_auth_strategy_decision_matrix(packet)

        self.assertEqual(matrix["status"], "ok")
        self.assertTrue(matrix["auth_command_supported"])
        self.assertTrue(matrix["auth_command_available"])
        self.assertTrue(matrix["auth_command_selected"])
        self.assertTrue(matrix["bounded_bearer_available"])
        self.assertFalse(matrix["bounded_bearer_selected"])
        self.assertFalse(matrix["file_auth_selected"])
        self.assertTrue(matrix["file_auth_deferred_to_separate_contour"])
        self.assertFalse(matrix["current_codex_auth_json_used"])
        self.assertFalse(matrix["browser_authority_used"])
        self.assertFalse(matrix["remote_authority_used"])
        self.assertFalse(matrix["browser_authority_detected"])
        self.assertFalse(matrix["remote_client_authority_detected"])
        self.assertFalse(matrix["current_codex_auth_runtime_dependency_detected"])
        self.assertFalse(matrix["silent_fallback_detected"])
        self.assertIn("bounded_local_bearer", matrix["rejected_strategies"])
        self.assertTrue(matrix["all_unselected_strategies_have_rejection_reasons"])
        self.assertEqual(
            [
                row["strategy_id"]
                for row in matrix["strategy_rows"]
            ],
            [
                "auth.command",
                "bounded_local_bearer",
                "file_auth_separate_contour",
                "experimental_bearer_token",
                "current_codex_auth_json",
                "browser_supplied_auth",
                "remote_client_supplied_auth",
            ],
        )

    def test_auth_command_output_format_classified(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        output = build_auth_command_output_format_packet(packet)

        self.assertEqual(output["status"], "ok")
        self.assertEqual(output["output_shape"], "plain_token_stdout")
        self.assertTrue(output["plain_token_stdout"])
        self.assertFalse(output["json_access_token_stdout"])
        self.assertFalse(output["raw_upstream_secret"])
        self.assertFalse(output["secret_value_emitted_in_packet"])

    def test_file_auth_fallback_deferred_to_separate_contour(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        deferred = build_file_auth_fallback_deferred_packet(packet)
        exclusion = build_file_auth_fallback_exclusion_packet(packet)
        non_substitution = build_file_auth_non_substitution_packet(packet)

        self.assertEqual(deferred["status"], "ok")
        self.assertEqual(exclusion["status"], "ok")
        self.assertTrue(exclusion["file_auth_excluded_from_proxy_auth_contour"])
        self.assertFalse(exclusion["file_auth_silent_substitution_allowed"])
        self.assertFalse(deferred["allowed_in_this_contour"])
        self.assertTrue(deferred["requires_separate_contour"])
        self.assertFalse(deferred["can_satisfy_proxy_auth_contract"])
        self.assertFalse(deferred["file_auth_silently_replaced_proxy_auth"])
        self.assertFalse(deferred["copy_current_auth_json_allowed"])
        self.assertEqual(non_substitution["status"], "ok")
        self.assertFalse(non_substitution["file_auth_equals_proxy_auth"])
        self.assertFalse(non_substitution["file_auth_may_satisfy_proxy_auth"])
        self.assertFalse(non_substitution["file_auth_selected_as_provider_auth"])

    def test_bounded_bearer_requires_scope_and_redaction_packet(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=True,
        )
        matrix = build_auth_strategy_decision_matrix(packet)

        self.assertTrue(matrix["bounded_bearer_available"])
        self.assertFalse(matrix["bounded_bearer_selected"])
        self.assertEqual(matrix["bounded_bearer_scope"], "owner_local_listener")
        self.assertEqual(matrix["bounded_bearer_locality"], "local_wbp_listener_only")
        self.assertTrue(matrix["bounded_bearer_redaction"])

    def test_authority_boundary_blocks_token_path_model_provider(self) -> None:
        clean = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        blocked = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            browser_payload={
                "token": "sk-browser-forged",
                "path": "/tmp/auth",
                "model": "forged",
                "provider": "forged",
            },
            remote_payload={
                "token": "remote-token",
                "model": "remote-model",
                "provider": "remote-provider",
            },
        )
        clean_boundary = build_authority_boundary_packet(clean)
        blocked_boundary = build_authority_boundary_packet(blocked)

        self.assertEqual(clean_boundary["status"], "ok")
        self.assertEqual(blocked_boundary["status"], "blocked")
        self.assertFalse(
            clean_boundary["browser_can_supply_token_path_model_provider_authority"]
        )
        self.assertFalse(
            clean_boundary["remote_can_supply_token_path_model_provider_authority"]
        )
        self.assertEqual(
            clean_boundary["authority_filter_method"], "recursive_key_name_match"
        )
        self.assertFalse(clean_boundary["semantic_alias_coverage_proven"])
        self.assertIn("semantic aliases", clean_boundary["authority_filter_limit"])
        self.assertIn("token", blocked_boundary["browser_detected_forbidden_fields"])
        self.assertIn("provider", blocked_boundary["remote_detected_forbidden_fields"])

    def test_current_codex_auth_json_not_runtime_dependency(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        independence = build_current_codex_auth_independence_packet(packet)

        self.assertEqual(independence["status"], "ok")
        self.assertFalse(independence["current_codex_auth_json_execution_dependency"])
        self.assertFalse(independence["current_codex_auth_json_read_as_runtime_input"])
        self.assertFalse(independence["current_codex_auth_json_copied"])
        self.assertFalse(independence["current_codex_auth_json_symlinked"])

    def test_secret_source_confusion_guard(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        guard = build_secret_source_confusion_guard_packet(packet)
        boundary = build_auth_token_boundary_packet(packet)

        self.assertEqual(guard["status"], "ok")
        self.assertFalse(guard["local_wbp_bearer_equals_upstream_provider_token"])
        self.assertFalse(guard["auth_command_output_equals_raw_upstream_secret"])
        self.assertFalse(guard["file_auth_token_equals_proxy_auth_token"])
        self.assertFalse(guard["current_codex_auth_json_allowed_execution_input"])
        self.assertFalse(guard["browser_hidden_field_allowed_authority"])
        self.assertFalse(guard["remote_client_allowed_authority"])
        self.assertEqual(boundary["status"], "ok")
        self.assertFalse(boundary["wbp_local_bearer_token_is_upstream_provider_secret"])
        self.assertFalse(boundary["auth_command_output_is_raw_upstream_secret"])
        self.assertFalse(boundary["upstream_provider_secret_in_evidence"])

    def test_no_ambient_authority_packet_blocks_browser_or_remote_authority(self) -> None:
        clean = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        clean_packet = build_no_ambient_authority_packet(clean)
        remote = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            remote_payload={"token": "remote-token"},
        )
        blocked_packet = build_no_ambient_authority_packet(remote)

        self.assertEqual(clean_packet["status"], "ok")
        self.assertFalse(clean_packet["current_codex_auth_json_runtime_input"])
        self.assertFalse(clean_packet["env_auth_runtime_input"])
        self.assertFalse(clean_packet["ambient_host_auth_runtime_input"])
        self.assertFalse(clean_packet["browser_token_path_model_provider_authority"])
        self.assertFalse(clean_packet["remote_token_path_model_provider_authority"])
        self.assertEqual(blocked_packet["status"], "blocked")

    def test_provider_auth_sources_are_classified(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        inventory = build_provider_auth_source_inventory_packet(packet)

        self.assertEqual(inventory["status"], "ok")
        self.assertTrue(inventory["all_auth_sources_classified"])
        self.assertEqual(inventory["unknown_source_count"], 0)
        self.assertFalse(inventory["runtime_usage_proven"])
        self.assertFalse(inventory["raw_secret_recorded"])
        classes = {row["source_class"] for row in inventory["source_rows"]}
        self.assertIn("server_owned", classes)
        self.assertIn("ambient_host", classes)
        self.assertIn("browser_supplied", classes)

    def test_provider_auth_current_vs_declared_precedence_separated(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        matrix = build_auth_strategy_decision_matrix(packet)
        discovery = build_provider_auth_precedence_discovery_packet(packet, matrix)
        contract = build_provider_auth_precedence_contract_packet(packet, matrix)

        self.assertEqual(discovery["status"], "ok")
        self.assertFalse(discovery["current_behavior_live_observed"])
        self.assertFalse(discovery["runtime_trace_present"])
        self.assertTrue(discovery["current_behavior_separated_from_declared_precedence"])
        self.assertFalse(discovery["selected_auth_claimed_as_live_used_auth"])
        self.assertEqual(contract["status"], "ok")
        self.assertTrue(contract["selected_strategy_is_contract_only"])
        self.assertFalse(contract["selected_strategy_runtime_usage_proven"])

    def test_env_file_fallback_forbidden_by_default(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        fallback = build_provider_auth_fallback_matrix_packet(packet)

        self.assertEqual(fallback["status"], "ok")
        self.assertTrue(fallback["ambient_fallback_forbidden_by_default"])
        by_id = {row["fallback_id"]: row for row in fallback["fallback_rows"]}
        self.assertFalse(by_id["env_openai_api_key"]["allowed"])
        self.assertFalse(by_id["current_codex_auth_json"]["allowed"])
        self.assertFalse(by_id["file_auth_separate_contour"]["allowed"])
        self.assertFalse(by_id["env_openai_api_key"]["silent_fallback_allowed"])

    def test_auth_command_selection_does_not_claim_live_usage(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        limits = build_provider_auth_runtime_claim_limits_packet(packet)

        self.assertEqual(limits["status"], "ok")
        self.assertEqual(limits["selected_strategy"], "auth.command")
        self.assertTrue(limits["selected_auth_source_classified"])
        self.assertFalse(limits["runtime_trace_present"])
        self.assertFalse(limits["selected_auth_live_used"])
        self.assertFalse(limits["provider_request_proven"])
        self.assertFalse(limits["route_proof_claimed"])

    def test_auth_command_live_usage_claim_requires_runtime_trace(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        limits = build_provider_auth_runtime_claim_limits_packet(
            packet,
            runtime_trace_present=False,
            selected_auth_live_used=True,
        )

        self.assertEqual(limits["status"], "blocked")
        self.assertTrue(limits["selected_auth_claimed_as_live_used_without_trace"])

    def test_account_session_auth_not_provider_adapter_auth(self) -> None:
        packet = build_provider_auth_account_boundary_packet(account_validation_observed=True)

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["account_session_auth_equals_provider_adapter_auth"])
        self.assertFalse(packet["account_validation_counts_as_model_availability"])
        self.assertFalse(packet["account_validation_counts_as_provider_compatibility"])
        self.assertFalse(packet["runtime_route_claimed"])

    def test_provider_auth_secret_and_browser_boundary_packets(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=True,
        )
        token_boundary = build_auth_token_boundary_packet(packet)
        secret = build_provider_auth_secret_boundary_packet(packet, token_boundary)
        browser = build_provider_auth_browser_authority_packet(packet)

        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["raw_upstream_secret_in_evidence"])
        self.assertFalse(secret["browser_secret_intake"])
        self.assertEqual(browser["status"], "ok")
        self.assertFalse(browser["browser_client_supplied_token_authority"])
        self.assertFalse(browser["remote_client_supplied_account_authority"])

    def test_auth_strategy_false_green_blocks_silent_fallback_with_matrix(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=False,
        )
        matrix = build_auth_strategy_decision_matrix(packet)
        file_auth = build_file_auth_fallback_deferred_packet(packet)
        independence = build_current_codex_auth_independence_packet(packet)
        guard = build_secret_source_confusion_guard_packet(packet)
        audit = build_auth_strategy_false_green_audit(
            provider_auth_strategy_packet=packet,
            decision_matrix_packet=matrix,
            file_auth_fallback_deferred_packet=file_auth,
            current_codex_auth_independence_packet=independence,
            secret_source_confusion_guard_packet=guard,
            runtime_claim_limits_packet=build_provider_auth_runtime_claim_limits_packet(
                packet,
                runtime_trace_present=False,
                selected_auth_live_used=True,
            ),
            account_boundary_packet=build_provider_auth_account_boundary_packet(),
            fallback_matrix_packet=build_provider_auth_fallback_matrix_packet(packet),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(matrix["silent_fallback_detected"])
        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["selected_auth_live_used_without_trace_claimed"])

    def test_auth_strategy_false_green_allows_clean_auth_command_contract(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
        matrix = build_auth_strategy_decision_matrix(packet)
        file_auth = build_file_auth_fallback_deferred_packet(packet)
        independence = build_current_codex_auth_independence_packet(packet)
        guard = build_secret_source_confusion_guard_packet(packet)
        audit = build_auth_strategy_false_green_audit(
            provider_auth_strategy_packet=packet,
            decision_matrix_packet=matrix,
            file_auth_fallback_deferred_packet=file_auth,
            current_codex_auth_independence_packet=independence,
            secret_source_confusion_guard_packet=guard,
            runtime_claim_limits_packet=build_provider_auth_runtime_claim_limits_packet(packet),
            account_boundary_packet=build_provider_auth_account_boundary_packet(),
            fallback_matrix_packet=build_provider_auth_fallback_matrix_packet(packet),
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["native_launch_claimed"])
        self.assertFalse(audit["model_availability_claimed"])
        self.assertFalse(audit["direct_egress_claimed"])
        self.assertFalse(audit["file_auth_used"])
        self.assertFalse(audit["remote_authority_used"])

    def test_provider_auth_contract_freezes_server_owned_precedence(self) -> None:
        contract = build_provider_auth_strategy_contract_packet()

        self.assertEqual(contract["status"], "ok")
        self.assertEqual(
            contract["precedence_order"],
            [
                "explicit_wbp_route_policy_account_binding",
                "active_wbp_provider_account_registry_entry",
                "wbp_server_owned_configured_provider_credential_reference",
                "explicit_bounded_fallback_contour_auth",
                "reject",
            ],
        )
        self.assertTrue(contract["server_owns_provider_account_selection"])
        self.assertFalse(contract["client_supplied_auth_authority_allowed"])
        self.assertFalse(contract["provider_reachability_claimed"])
        self.assertFalse(contract["model_availability_claimed"])

    def test_credential_reference_is_not_raw_secret_or_reachability_proof(self) -> None:
        packet = build_provider_auth_credential_reference_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["credential_reference_kind"], "server_owned_reference")
        self.assertTrue(packet["credential_reference_id"].startswith("sha256:"))
        self.assertFalse(packet["credential_reference_recorded_raw"])
        self.assertFalse(packet["raw_secret_value_recorded"])
        self.assertFalse(packet["credential_reference_proves_provider_reachability"])
        self.assertFalse(packet["account_validation_counts_as_model_availability"])

        blocked = build_provider_auth_credential_reference_packet(
            raw_secret_value_recorded=True,
            provider_reachability_claimed=True,
            account_validated=True,
            model_availability_claimed=True,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("raw_secret_value_recorded", blocked["failed_checks"])
        self.assertIn(
            "credential_reference_treated_as_provider_reachability",
            blocked["failed_checks"],
        )
        self.assertIn(
            "account_validation_treated_as_model_availability",
            blocked["failed_checks"],
        )

    def test_provider_auth_precedence_selects_first_server_owned_source(self) -> None:
        packet = build_provider_auth_precedence_packet(
            route_policy_account_binding_present=True,
            active_provider_account_present=True,
            server_credential_reference_present=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["selected_source"],
            "explicit_wbp_route_policy_account_binding",
        )
        self.assertTrue(packet["route_policy_wins_over_registry"])
        self.assertFalse(packet["silent_fallback_allowed"])
        self.assertFalse(packet["runtime_route_claimed"])

        registry = build_provider_auth_precedence_packet(
            route_policy_account_binding_present=False,
            active_provider_account_present=True,
            server_credential_reference_present=True,
        )
        self.assertEqual(registry["status"], "ok")
        self.assertEqual(
            registry["selected_source"],
            "active_wbp_provider_account_registry_entry",
        )
        self.assertTrue(registry["registry_wins_over_server_credential_reference"])

    def test_provider_auth_precedence_blocks_missing_or_ambiguous_auth(self) -> None:
        missing = build_provider_auth_precedence_packet(
            route_policy_account_binding_present=False,
            active_provider_account_present=False,
            server_credential_reference_present=False,
            bounded_fallback_contour_declared=False,
        )
        ambiguous = build_provider_auth_precedence_packet(
            ambiguous_same_precedence_sources=True,
        )

        self.assertEqual(missing["status"], "blocked")
        self.assertTrue(missing["missing_auth_blocks_request"])
        self.assertEqual(missing["selected_source"], "reject")
        self.assertEqual(ambiguous["status"], "blocked")
        self.assertTrue(ambiguous["ambiguous_auth_blocks_request"])

    def test_ambient_file_env_and_client_authority_guards_are_separate(self) -> None:
        ambient = build_provider_auth_ambient_authority_guard_packet()
        file_boundary = build_provider_auth_file_vs_proxy_boundary_packet()
        env_limit = build_provider_auth_env_authority_limit_packet()
        client = build_provider_auth_client_authority_rejection_packet()

        self.assertEqual(ambient["status"], "ok")
        self.assertEqual(file_boundary["status"], "ok")
        self.assertEqual(env_limit["status"], "ok")
        self.assertEqual(client["status"], "ok")
        self.assertFalse(ambient["ambient_authority_allowed"])
        self.assertFalse(file_boundary["file_auth_equals_proxy_auth"])
        self.assertFalse(env_limit["env_var_presence_proves_safe_runtime_auth"])
        self.assertFalse(client["client_supplied_account_authority_allowed"])
        self.assertIn("account_id", client["client_forbidden_fields_detected"])
        self.assertIn("credential_ref", client["client_forbidden_fields_detected"])

    def test_env_auth_cannot_silently_override_route_policy(self) -> None:
        blocked = build_provider_auth_env_authority_limit_packet(
            env_auth_used=True,
            env_source_declared=False,
            overrides_route_policy=True,
            raw_env_value_recorded=True,
            silent_env_fallback_allowed=True,
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("env_auth_used_without_declaration", blocked["failed_checks"])
        self.assertIn("env_auth_overrides_route_policy", blocked["failed_checks"])
        self.assertIn("raw_env_value_recorded", blocked["failed_checks"])
        self.assertIn("silent_env_fallback_allowed", blocked["failed_checks"])

    def test_reserve_account_cannot_promote_without_explicit_contour(self) -> None:
        clean = build_provider_auth_reserve_account_non_promotion_packet()
        blocked = build_provider_auth_reserve_account_non_promotion_packet(
            reserve_account_selected_as_active=True,
            explicit_promotion_contour=False,
            active_route_mutated=True,
        )

        self.assertEqual(clean["status"], "ok")
        self.assertFalse(clean["reserve_account_equals_active_route"])
        self.assertFalse(clean["reserve_account_validates_model_availability"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn(
            "reserve_account_promoted_without_explicit_contour",
            blocked["failed_checks"],
        )
        self.assertIn("active_route_mutated_by_reserve_account", blocked["failed_checks"])

    def test_missing_and_ambiguous_auth_failure_semantics_reject_without_live_claim(self) -> None:
        packet = build_provider_auth_failure_semantics_packet()
        blocked = build_provider_auth_failure_semantics_packet(
            missing_auth_result="fallback",
            silent_fallback_on_missing_auth=True,
            live_failure_semantics_claimed=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["missing_auth_blocks_request"])
        self.assertTrue(packet["ambiguous_auth_blocks_request"])
        self.assertFalse(packet["live_failure_semantics_claimed"])
        self.assertFalse(packet["responses_live_failure_semantics_completed"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("missing_auth_does_not_reject", blocked["failed_checks"])
        self.assertIn("silent_fallback_on_missing_auth", blocked["failed_checks"])
        self.assertIn(
            "auth_contract_claimed_live_failure_semantics",
            blocked["failed_checks"],
        )

    def test_provider_auth_precedence_false_green_and_summary_require_clean_packets(self) -> None:
        packets = {
            "provider_auth_strategy_contract_packet.json": (
                build_provider_auth_strategy_contract_packet()
            ),
            "provider_auth_source_inventory_packet.json": (
                build_provider_auth_source_inventory_packet(
                    build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)
                )
            ),
            "provider_auth_credential_reference_packet.json": (
                build_provider_auth_credential_reference_packet()
            ),
            "provider_auth_precedence_packet.json": build_provider_auth_precedence_packet(),
            "provider_auth_ambient_authority_guard_packet.json": (
                build_provider_auth_ambient_authority_guard_packet()
            ),
            "provider_auth_file_vs_proxy_boundary_packet.json": (
                build_provider_auth_file_vs_proxy_boundary_packet()
            ),
            "provider_auth_client_authority_rejection_packet.json": (
                build_provider_auth_client_authority_rejection_packet()
            ),
            "provider_auth_env_authority_limit_packet.json": (
                build_provider_auth_env_authority_limit_packet()
            ),
            "provider_auth_reserve_account_non_promotion_packet.json": (
                build_provider_auth_reserve_account_non_promotion_packet()
            ),
            "provider_auth_failure_semantics_packet.json": (
                build_provider_auth_failure_semantics_packet()
            ),
        }
        packets["provider_auth_secret_redaction_packet.json"] = (
            build_provider_auth_secret_redaction_packet(packets)
        )
        packets["provider_auth_false_green_audit.json"] = (
            build_provider_auth_precedence_false_green_audit(packets)
        )
        summary = build_provider_auth_summary_packet(packets)

        self.assertEqual(packets["provider_auth_secret_redaction_packet.json"]["status"], "ok")
        self.assertEqual(packets["provider_auth_false_green_audit.json"]["status"], "ok")
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(
            summary["final_status"],
            "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        )
        self.assertFalse(summary["model_availability_claimed"])
        self.assertFalse(summary["responses_live_failure_semantics_claimed"])


if __name__ == "__main__":
    unittest.main()
