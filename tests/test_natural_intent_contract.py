# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import natural_intent_contract as contract
from wild_boar_proxy.core import packets


ROUTE_ID = "wbp-deepseek-chat"


def _runtime_context(*, allowed_routes: list[str] | None = None) -> dict[str, object]:
    allowed_routes = [ROUTE_ID] if allowed_routes is None else allowed_routes
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "context_truth_source": "server_launch_selection_packet",
        "agent_bindings_status": "ok",
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1"],
                "lane": "primary_chatgpt",
                "enabled": True,
                "model_id": "gpt-5.4",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": ["DIP", "Agent 2", "Worker"],
                "lane": "api_route",
                "enabled": True,
                "route_id": ROUTE_ID,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "alias_to_agent_id": {
            "Codex": "codex",
            "Agent 1": "codex",
            "DIP": "dip",
            "Agent 2": "dip",
            "Worker": "dip",
        },
        "agent_id_to_route": {"dip": ROUTE_ID},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": allowed_routes,
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _packet(
    *,
    prompt: str = "Codex, дай задачу DIP: верни короткий план.",
    alias: str = "DIP",
    runtime_context: dict[str, object] | None = None,
    source_surface: str = contract.SOURCE_SURFACE_TEST_FIXTURE,
    ambiguous: bool = False,
    secret_values: list[str] | None = None,
) -> dict[str, object]:
    return contract.build_natural_intent_contract_packet(
        prompt_text=prompt,
        alias_candidate=alias,
        runtime_context=_runtime_context() if runtime_context is None else runtime_context,
        source_surface=source_surface,
        ambiguous=ambiguous,
        secret_values=secret_values,
    )


def _parser_packet(
    *,
    prompt: str = "Codex, дай задачу DIP: верни короткий план.",
    runtime_context: dict[str, object] | None = None,
    source_surface: str = contract.SOURCE_SURFACE_TEST_FIXTURE,
    secret_values: list[str] | None = None,
) -> dict[str, object]:
    return contract.build_natural_intent_parser_packet(
        prompt_text=prompt,
        runtime_context=_runtime_context() if runtime_context is None else runtime_context,
        source_surface=source_surface,
        secret_values=secret_values,
    )


def _assert_no_dispatch(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    testcase.assertEqual(packet["dispatch_status"], contract.DISPATCH_STATUS_NOT_ATTEMPTED)
    testcase.assertFalse(packet["api_lane_called"])
    testcase.assertFalse(packet["dispatch_proven"])
    testcase.assertFalse(packet["fallback_used"])
    testcase.assertFalse(packet["local_imitation_used"])
    testcase.assertFalse(packet["native_codex_subagent_used"])
    testcase.assertFalse(packet["native_codex_subagent_used_as_dip"])
    testcase.assertFalse(packet["router_dispatch_admitted"])
    testcase.assertFalse(packet["router_owned_dispatch_decision_bound"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertTrue(packet["does_not_prove_dispatch"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])


class NaturalIntentContractTests(unittest.TestCase):
    def test_parser_extracts_api_alias_from_codex_to_dip_phrase_without_dispatch(self) -> None:
        raw_prompt = "Codex, дай задачу DIP: верни короткий план."
        packet = _parser_packet(prompt=raw_prompt)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["parser_used"])
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(packet["alias_match_status"], contract.ALIAS_MATCH_STATUS_EXACT)
        self.assertEqual(
            packet["parser_target_selection_rule"],
            "single_api_target_with_optional_primary_address",
        )
        self.assertTrue(packet["parser_primary_address_present"])
        self.assertTrue(packet["parser_api_target_present"])
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["slot_candidate"], "dip")
        self.assertEqual(packet["lane_candidate"], "api_route")
        self.assertTrue(packet["natural_alias_command_detected"])
        self.assertTrue(packet["natural_api_alias_command_detected"])
        self.assertTrue(packet["router_preflight_admitted"])
        self.assertEqual(packet["intent_status"], contract.INTENT_PASS)
        self.assertEqual(packet["contract_preflight_status"], contract.PREFLIGHT_PASS)
        self.assertFalse(contract.packet_contains_text(packet, raw_prompt))
        self.assertFalse(packet["parser_prompt_text_recorded"])
        self.assertFalse(packet["parser_raw_prompt_recorded"])
        self.assertTrue(packet["parser_does_not_dispatch"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_normalizes_case_whitespace_nfkc_and_contained_aliases(self) -> None:
        cases = [
            ("  codex , дай   задачу   aGeNt   2  ", "Agent 2"),
            ("\uff23\uff4f\uff44\uff45\uff58, попроси \uff24\uff29\uff30 ответить.", "DIP"),
            ("Agent 2, проверь контракт.", "Agent 2"),
            (f"{'очень длинный контекст ' * 8}DIP, проверь контракт.", "DIP"),
        ]

        for prompt, expected_alias in cases:
            with self.subTest(prompt=prompt):
                packet = _parser_packet(prompt=prompt)

                self.assertEqual(packet["status"], "ok")
                self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
                self.assertEqual(packet["alias_candidate"], expected_alias)
                self.assertEqual(packet["slot_candidate"], "dip")
                self.assertEqual(packet["intent_status"], contract.INTENT_PASS)
                self.assertFalse(packet["ambiguous_intent"])
                _assert_no_dispatch(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_does_not_match_numeric_alias_inside_machine_marker(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["agent_bindings"][0]["aliases"].append("1")
        runtime_context["agent_bindings"][1]["aliases"].append("2")
        runtime_context["alias_to_agent_id"]["1"] = "codex"
        runtime_context["alias_to_agent_id"]["2"] = "dip"

        packet = _parser_packet(
            prompt=(
                "DIP: prove bridge response WBP_REPEATABLE_FRESH_LIVE_"
                "20260619T204138Z_2"
            ),
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["parser_api_alias_match_count"], 1)
        self.assertFalse(packet["ambiguous_intent"])
        self.assertEqual(packet["intent_status"], contract.INTENT_PASS)
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

        direct_numeric = _parser_packet(
            prompt="2, проверь контракт.",
            runtime_context=runtime_context,
        )
        self.assertEqual(direct_numeric["status"], "ok")
        self.assertEqual(direct_numeric["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(direct_numeric["alias_candidate"], "2")
        self.assertEqual(direct_numeric["slot_candidate"], "dip")
        self.assertEqual(direct_numeric["intent_status"], contract.INTENT_PASS)

    def test_parser_does_not_match_numeric_alias_inside_code_expression(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["agent_bindings"][0]["aliases"].append("1")
        runtime_context["agent_bindings"][1]["aliases"].append("2")
        runtime_context["alias_to_agent_id"]["1"] = "codex"
        runtime_context["alias_to_agent_id"]["2"] = "dip"

        packet = _parser_packet(
            prompt=(
                "DIP: fix active repo bug. tests/test_app.py expects "
                "add(2,3)==5. Use apply_patch and run tests."
            ),
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["parser_alias_match_count"], 1)
        self.assertEqual(packet["parser_api_alias_match_count"], 1)
        self.assertFalse(packet["ambiguous_intent"])
        self.assertEqual(packet["intent_status"], contract.INTENT_PASS)

    def test_parser_accepts_custom_alias_from_runtime_context_only(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["agent_bindings"][1]["aliases"] = [
            "DIP",
            "Agent 2",
            "Worker",
            "Кодер",
        ]
        runtime_context["alias_to_agent_id"]["Кодер"] = "dip"

        packet = _parser_packet(
            prompt="Codex, передай Кодер короткую проверку.",
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(packet["alias_candidate"], "Кодер")
        self.assertEqual(packet["slot_candidate"], "dip")
        self.assertEqual(packet["intent_status"], contract.INTENT_PASS)
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_accepts_explicit_delegate_tool_instruction_alias(self) -> None:
        packet = _parser_packet(
            prompt=(
                "Call the WBP MCP tool delegate_to_dip for DIP: "
                "докажи dispatch admission."
            )
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(packet["alias_match_status"], contract.ALIAS_MATCH_STATUS_EXACT)
        self.assertEqual(
            packet["parser_target_selection_rule"],
            "explicit_delegate_tool_instruction_alias",
        )
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["slot_candidate"], "dip")
        self.assertTrue(packet["parser_api_target_present"])
        self.assertEqual(packet["intent_status"], contract.INTENT_PASS)
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_rejects_unknown_leading_alias_even_with_delegate_instruction(
        self,
    ) -> None:
        packet = _parser_packet(
            prompt=(
                "DIPP:Call the WBP MCP tool delegate_to_dip for DIP: "
                "докажи dispatch admission."
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.NO_ALIAS_DETECTED)
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_NO_ALIAS)
        self.assertFalse(packet["alias_candidate_present"])
        self.assertIn("leading_alias_not_bound", packet["parser_blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_unknown_or_missing_alias_fails_closed_without_candidate_guessing(self) -> None:
        for prompt in (
            "Просто составь план без второго агента.",
            "Ghost, проверь маршрут.",
        ):
            with self.subTest(prompt=prompt):
                packet = _parser_packet(prompt=prompt)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], contract.NO_ALIAS_DETECTED)
                self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_NO_ALIAS)
                self.assertEqual(packet["alias_match_status"], contract.ALIAS_MATCH_STATUS_NONE)
                self.assertFalse(packet["alias_candidate_present"])
                self.assertFalse(packet["parser_selected_alias_from_runtime_context"])
                self.assertIn("alias_not_detected", packet["parser_blocking_reasons"])
                _assert_no_dispatch(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_multiple_api_aliases_for_same_target_are_ambiguous(self) -> None:
        packet = _parser_packet(prompt="Codex, пусть DIP и Worker проверят одно и то же.")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.INTENT_AMBIGUOUS_NO_DISPATCH)
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_AMBIGUOUS)
        self.assertEqual(
            packet["alias_match_status"],
            contract.ALIAS_MATCH_STATUS_AMBIGUOUS,
        )
        self.assertTrue(packet["ambiguous_intent"])
        self.assertIn(
            "multiple_aliases_for_api_target",
            packet["parser_blocking_reasons"],
        )
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_multiple_api_targets_are_ambiguous(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["agent_bindings"].append(
            {
                "agent_id": "reviewer",
                "display_name": "Reviewer",
                "role": "coding_reviewer",
                "aliases": ["Reviewer"],
                "lane": "api_route",
                "enabled": True,
                "route_id": "wbp-reviewer-route",
                "allowed_actions": ["code_review"],
            }
        )
        runtime_context["alias_to_agent_id"]["Reviewer"] = "reviewer"
        runtime_context["agent_id_to_route"]["reviewer"] = "wbp-reviewer-route"
        runtime_context["allowed_api_route_ids"].append("wbp-reviewer-route")

        packet = _parser_packet(
            prompt="Codex, попроси DIP и Reviewer сравнить контракт.",
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.INTENT_AMBIGUOUS_NO_DISPATCH)
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_AMBIGUOUS)
        self.assertIn("multiple_api_targets", packet["parser_blocking_reasons"])
        self.assertTrue(packet["ambiguous_intent"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_overlapping_aliases_for_different_agents_are_ambiguous(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["agent_bindings"][0]["aliases"].append("Agent")
        runtime_context["alias_to_agent_id"]["Agent"] = "codex"

        packet = _parser_packet(
            prompt="Agent 2, проверь контракт.",
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.INTENT_AMBIGUOUS_NO_DISPATCH)
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_AMBIGUOUS)
        self.assertIn("overlapping_alias_conflict", packet["parser_blocking_reasons"])
        self.assertTrue(packet["ambiguous_intent"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_multiple_non_api_aliases_are_ambiguous(self) -> None:
        packet = _parser_packet(prompt="Codex и Agent 1, проверьте план.")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.INTENT_AMBIGUOUS_NO_DISPATCH)
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_AMBIGUOUS)
        self.assertIn("multiple_non_api_aliases", packet["parser_blocking_reasons"])
        self.assertTrue(packet["ambiguous_intent"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_primary_alias_only_is_recognized_but_not_api_lane(self) -> None:
        packet = _parser_packet(prompt="Codex, проверь план.")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.FAIL_ALIAS_NOT_API_LANE)
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertEqual(packet["alias_candidate"], "Codex")
        self.assertEqual(packet["slot_candidate"], "codex")
        self.assertEqual(packet["lane_candidate"], "primary_chatgpt")
        self.assertEqual(packet["intent_status"], contract.FAIL_ALIAS_NOT_API_LANE)
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_empty_or_invalid_context_remains_contract_blocked(self) -> None:
        invalid_context = _runtime_context()
        invalid_context["packet_kind"] = "wrong_kind"

        for prompt, runtime_context, expected_parser_status in (
            ("", _runtime_context(), contract.PARSER_STATUS_PROMPT_EMPTY),
            ("Codex, дай задачу DIP.", {}, contract.PARSER_STATUS_CONTEXT_MISSING),
            (
                "Codex, дай задачу DIP.",
                invalid_context,
                contract.PARSER_STATUS_CONTEXT_MISSING,
            ),
        ):
            with self.subTest(prompt=prompt, parser_status=expected_parser_status):
                packet = _parser_packet(prompt=prompt, runtime_context=runtime_context)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["parser_status"], expected_parser_status)
                self.assertNotEqual(packet["contract_preflight_status"], contract.PREFLIGHT_PASS)
                _assert_no_dispatch(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_parser_redacts_raw_prompt_secret_and_backend_details(self) -> None:
        sensitive_value = "owner-redaction-fixture-value"
        raw_prompt = (
            "Codex, дай задачу DIP: проверь Authorization: Bearer "
            f"{sensitive_value} и backend=https://example.invalid/internal"
        )
        packet = _parser_packet(
            prompt=raw_prompt,
            secret_values=[sensitive_value],
        )
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["parser_status"], contract.PARSER_STATUS_MATCHED)
        self.assertFalse(contract.packet_contains_text(packet, raw_prompt))
        self.assertNotIn(sensitive_value, encoded)
        self.assertNotIn("Authorization: Bearer", encoded)
        self.assertNotIn("https://example.invalid/internal", encoded)
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["parser_prompt_text_recorded"])
        self.assertFalse(packet["parser_raw_prompt_recorded"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[sensitive_value],
            ),
            [],
        )

    def test_positive_fixture_builds_sanitized_preflight_packet_without_dispatch(self) -> None:
        raw_prompt = "Codex, дай задачу DIP: верни короткий план."
        packet = _packet(prompt=raw_prompt, alias="DIP")

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], contract.NATURAL_INTENT_CONTRACT_PACKET_KIND)
        self.assertEqual(packet["source_surface"], contract.SOURCE_SURFACE_TEST_FIXTURE)
        self.assertFalse(packet["source_surface_observed"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertTrue(packet["alias_bound"])
        self.assertEqual(packet["slot_candidate"], "dip")
        self.assertEqual(packet["lane_candidate"], "api_route")
        self.assertEqual(packet["route_candidate"], ROUTE_ID)
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 1)
        self.assertEqual(packet["runtime_context_source"], "server_launch_selection_packet")
        self.assertTrue(packet["runtime_context_present"])
        self.assertTrue(packet["runtime_context_kind_valid"])
        self.assertEqual(packet["intent_status"], contract.INTENT_PASS)
        self.assertEqual(packet["contract_preflight_status"], contract.PREFLIGHT_PASS)
        self.assertEqual(len(str(packet["prompt_digest"])), 64)
        self.assertTrue(packet["prompt_digest_present"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["natural_phrase_recorded"])
        self.assertFalse(contract.packet_contains_text(packet, raw_prompt))
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_stale_route_guard_fails_closed(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["forbidden_stale_route_ids"] = []
        packet = _packet(runtime_context=runtime_context)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.FAIL_ROUTE_NOT_ALLOWED)
        self.assertEqual(packet["intent_status"], contract.FAIL_ROUTE_NOT_ALLOWED)
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertFalse(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 0)
        self.assertFalse(packet["route_id_allowed"])
        self.assertIn("stale_route_guard_missing", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_runtime_context_fails_closed(self) -> None:
        packet = _packet(runtime_context={})

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.FAIL_ALIAS_CONTEXT_MISSING)
        self.assertEqual(packet["intent_status"], contract.FAIL_ALIAS_CONTEXT_MISSING)
        self.assertEqual(packet["contract_preflight_status"], contract.PREFLIGHT_BLOCKED)
        self.assertFalse(packet["runtime_context_present"])
        self.assertFalse(packet["alias_bound"])
        self.assertIn("alias_context_missing_or_invalid", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_empty_prompt_fails_closed_without_digest_presence(self) -> None:
        for prompt in ("", "   \n\t", None):
            with self.subTest(prompt=repr(prompt)):
                packet = _packet(prompt=prompt, alias="DIP")

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], contract.FAIL_PROMPT_EMPTY)
                self.assertEqual(packet["intent_status"], contract.FAIL_PROMPT_EMPTY)
                self.assertEqual(
                    packet["contract_preflight_status"],
                    contract.PREFLIGHT_BLOCKED,
                )
                self.assertEqual(packet["prompt_digest"], "")
                self.assertFalse(packet["prompt_digest_present"])
                self.assertIn("prompt_empty", packet["blocking_reasons"])
                _assert_no_dispatch(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_alias_outside_context_fails_closed(self) -> None:
        packet = _packet(alias="Ghost")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.FAIL_ALIAS_NOT_BOUND)
        self.assertEqual(packet["intent_status"], contract.FAIL_ALIAS_NOT_BOUND)
        self.assertFalse(packet["alias_bound"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertIn("alias_not_bound_to_runtime_context", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_route_outside_allowlist_fails_closed(self) -> None:
        packet = _packet(runtime_context=_runtime_context(allowed_routes=["wbp-other-route"]))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.FAIL_ROUTE_NOT_ALLOWED)
        self.assertEqual(packet["intent_status"], contract.FAIL_ROUTE_NOT_ALLOWED)
        self.assertEqual(packet["route_candidate"], ROUTE_ID)
        self.assertFalse(packet["route_id_allowed"])
        self.assertIn("route_not_allowed_by_runtime_context", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_no_alias_fixture_fails_closed_without_dispatch(self) -> None:
        packet = _packet(alias="")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.NO_ALIAS_DETECTED)
        self.assertEqual(packet["intent_status"], contract.NO_ALIAS_DETECTED)
        self.assertFalse(packet["alias_candidate_present"])
        self.assertFalse(packet["alias_bound"])
        self.assertIn("alias_not_detected", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ambiguous_fixture_blocks_even_when_alias_is_present(self) -> None:
        packet = _packet(
            prompt="Пусть второй агент посмотрит это.",
            alias="Agent 2",
            ambiguous=True,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.INTENT_AMBIGUOUS_NO_DISPATCH)
        self.assertEqual(packet["intent_status"], contract.INTENT_AMBIGUOUS_NO_DISPATCH)
        self.assertEqual(packet["contract_preflight_status"], contract.PREFLIGHT_BLOCKED)
        self.assertTrue(packet["ambiguous_intent"])
        self.assertIn("ambiguous_intent_no_dispatch", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_primary_codex_alias_is_not_api_lane_and_does_not_dispatch(self) -> None:
        packet = _packet(
            prompt="Codex, проверь план.",
            alias="Codex",
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], contract.FAIL_ALIAS_NOT_API_LANE)
        self.assertEqual(packet["intent_status"], contract.FAIL_ALIAS_NOT_API_LANE)
        self.assertTrue(packet["alias_bound"])
        self.assertEqual(packet["slot_candidate"], "codex")
        self.assertEqual(packet["lane_candidate"], "primary_chatgpt")
        self.assertFalse(packet["route_id_allowed"])
        self.assertIn("alias_not_bound_to_api_lane", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_declared_custom_codex_flow_is_allowed_but_not_observed(self) -> None:
        packet = _packet(source_surface=contract.SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW)

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["source_surface_allowed"])
        self.assertFalse(packet["source_surface_observed"])
        self.assertFalse(packet["custom_codex_flow_observed"])
        self.assertFalse(packet["command_origin_proven"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_observed_custom_codex_flow_source_is_not_admitted_in_contract_v1(self) -> None:
        packet = _packet(source_surface=contract.SOURCE_SURFACE_CUSTOM_CODEX_FLOW)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            contract.FAIL_SOURCE_SURFACE_NOT_ADMITTED,
        )
        self.assertFalse(packet["source_surface_allowed"])
        self.assertIn("source_surface_not_admitted", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_raw_prompt_secret_and_backend_details_are_not_recorded(self) -> None:
        sensitive_value = "owner-redaction-fixture-value"
        raw_prompt = (
            "Codex, дай задачу DIP: проверь Authorization: Bearer "
            f"{sensitive_value} и backend=https://example.invalid/internal"
        )
        packet = _packet(
            prompt=raw_prompt,
            alias="DIP",
            secret_values=[sensitive_value],
        )
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(contract.packet_contains_text(packet, raw_prompt))
        self.assertNotIn(sensitive_value, encoded)
        self.assertNotIn("Authorization: Bearer", encoded)
        self.assertNotIn("https://example.invalid/internal", encoded)
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[sensitive_value],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
