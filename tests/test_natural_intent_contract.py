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


def _assert_no_dispatch(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    testcase.assertEqual(packet["dispatch_status"], contract.DISPATCH_STATUS_NOT_ATTEMPTED)
    testcase.assertFalse(packet["api_lane_called"])
    testcase.assertFalse(packet["dispatch_proven"])
    testcase.assertFalse(packet["fallback_used"])
    testcase.assertFalse(packet["local_imitation_used"])
    testcase.assertFalse(packet["native_codex_subagent_used"])
    testcase.assertFalse(packet["native_codex_subagent_used_as_dip"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertTrue(packet["does_not_prove_dispatch"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])


class NaturalIntentContractTests(unittest.TestCase):
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
